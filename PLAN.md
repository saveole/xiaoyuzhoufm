# 小宇宙播客工具 — 实现计划

> 本文档基于 `roadmap.md` 的三项需求，结合现有代码（`src/download.py`、`src/transcribe.py`、`src/app.py`）给出可落地的实现方案、模块拆分、实施顺序与风险点。

---

## 0. 背景与现状分析

### 0.1 现有架构

```
download.py  ──(Selenium)──▶  audio.mp3 + 标题
transcribe.py ─(faster-whisper)─▶ TXT / SRT 字符串
app.py ───────(Streamlit)──────  下载 ▶ 转录 ▶ 下载文件
```

### 0.2 制约三项需求的两个共性缺口

| 缺口 | 影响 |
|------|------|
| **A. 下载阶段只拿到标题和音频**，未抓取 show notes、主播/嘉宾、发布日期等元信息 | 需求 1（AI 修正）和需求 3（按 shownotes 区分发言人）都依赖这些上下文 |
| **B. 转录结果是扁平字符串**，没有「带时间戳 + 说话人」的结构化片段 | 需求 2（MD/PDF 排版）、需求 3（说话人标注）、需求 1（分块送 LLM）都需要结构化数据 |

> 结论：先做一次**基础重构**补上 A、B 两缺口，三项功能就能在统一的数据流上干净地叠加，避免互相打架。

---

## 1. 目标数据流（重构后）

```
download.py
  └─▶ EpisodeMeta {title, podcast, hosts[], guests[], published_at, duration, shownotes}
        + audio.mp3
            │
transcribe.py  (faster-whisper, word_timestamps=True)
  └─▶ list[Segment(start, end, text, speaker=None)]
            │
            ├──▶ (可选) diarize.py  ── pyannote ──▶ 给每个 Segment 打 speaker 标签
            │            │
            │            └──▶ names.py ── 结合 shownotes + 用户确认 ──▶ speaker 映射到真实姓名
            │
            ├──▶ (可选) correct.py ── LLM + EpisodeMeta 上下文 ──▶ 修正后的 Segment.text
            │
            └─▶ exporters/  ──▶ txt / srt / md / pdf
```

核心抽象：**`Segment` 是贯穿全流程的唯一数据结构**。

```python
# src/models.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class Segment:
    start: float        # 秒
    end: float
    text: str
    speaker: Optional[str] = None   # 真实姓名或 "SPEAKER_00"

@dataclass
class EpisodeMeta:
    title: str
    podcast: str = ""
    hosts: list[str] = None
    guests: list[str] = None
    published_at: str = ""
    duration: float = 0.0
    shownotes: str = ""
    source_url: str = ""
```

---

## 2. 阶段拆分与实施顺序

> **推荐顺序：阶段 0 ▶ 阶段 2 ▶ 阶段 3 ▶ 阶段 1**
>
> - 阶段 0 是所有人的前置依赖；
> - 阶段 2（MD/PDF）最独立、风险最低，先交付见效；
> - 阶段 3（说话人区分）产出带标签的 Segment，是阶段 1（AI 修正）高质量输入的前提（按说话人分块修正效果显著更好）；
> - 阶段 1（AI 修正）放最后，依赖最重（外部 API、成本、Prompt 调优）。

| 阶段 | 对应 roadmap 需求 | 主要交付 | 依赖外部服务 |
|------|------------------|---------|-------------|
| 0 基础重构 | — | `models.py`、`Segment` 化、`config.py`、下载抓取 shownotes | 无 |
| 2 多格式导出 | 需求 2 | MD + PDF（含中文排版） | 无 |
| 3 说话人区分 | 需求 3 | pyannote 对齐 + 姓名映射 | HuggingFace Token |
| 1 AI 修正 | 需求 1 | LLM 分块修正 | LLM API（OpenAI 兼容） |

---

## 3. 阶段 0：基础重构（前置必做）

### 3.1 `src/models.py`
定义上文的 `Segment` / `EpisodeMeta` 两个 dataclass。

### 3.2 重构 `src/transcribe.py`
- `transcribe_audio(...)` 改为返回 `list[Segment]`（开启 `word_timestamps=True` 以便后续对齐）。
- 保留命令行入口与旧的 txt/srt 行为，通过 `exporters` 适配，**不破坏现有用法**。
- 模型加载缓存逻辑（`@lru_cache`）保持不变。

### 3.3 新增 `src/config.py`
统一管理配置，优先级：环境变量 > `.env` > 默认值。

```python
# 关键配置项
LLM_BASE_URL       # OpenAI 兼容 endpoint（如 DeepSeek、GLM、Moonshot）
LLM_API_KEY
LLM_MODEL          # 如 deepseek-chat / glm-4-flash
HF_TOKEN           # pyannote 模型授权
PDF_FONT_PATH      # 中文字体路径（默认系统 PingFang / Noto Sans CJK）
```
- 新增 `.env.example`，`.gitignore` 已存在，确认 `.env` 被忽略。
- 新增 `requirements.txt`（当前仓库缺失，README 引用了它）。

### 3.4 扩展 `src/download.py`
在现有 Selenium 抓取基础上**增量抓取元信息**：

```python
def fetch_episode(url, progress_callback=None) -> tuple[str, EpisodeMeta]:
    # 原有：标题、audio src、下载 mp3
    # 新增：
    #   - shownotes 容器（DOM class 含 "description"/"content"，需先在真实页面定位选择器）
    #   - 主播 / 嘉宾节点（作者栏）
    #   - 发布时间、时长
    #   - 落盘 audio_files/<title>.mp3 与 audio_files/<title>.meta.json
```

**实现注意：**
- 小宇宙页面 class 名带动态 hash（如 `jsx-399326063`），统一用 `contains(@class, 'xxx')` 的 XPath，并写**多重兜底选择器**。
- 抓取后把 `EpisodeMeta` 序列化成 `<title>.meta.json`，供后续阶段离线复用（避免重复跑 Selenium）。
- **待确认（DOM 调研）**：shownotes 在页面里是 SSR HTML 还是 JS 动态渲染？若动态，需 `WebDriverWait` 等待节点出现。这一步建议先打开一个真实 episode 页面用 DevTools 确认选择器，再写代码。

---

## 4. 阶段 2：MD / PDF 导出（需求 2）

### 4.1 `src/exporters/md.py`
按说话人分段排版，带 front-matter 元信息：

```markdown
---
title: <标题>
podcast: <播客名>
hosts: [A, B]
date: 2025-xx-xx
duration: "1h23m"
---

# <标题>

> 主播：A、B　|　嘉宾：C

## 📝 Shownotes
<shownotes 原文>

---

## 💬 对话记录

**[00:01:23] A：**
今天我们聊一下……

**[00:02:10] B：**
没错，……
```

- 无说话人信息时退化为「带时间戳的段落」格式。
- 时间戳格式可配置（隐藏 / 显示）。

### 4.2 `src/exporters/pdf.py`
**推荐方案：MD ▶ HTML ▶ weasyprint**，排版可控、中文友好。

```
Segment[] ──md.py──▶ markdown 字符串 ──markdown(lib)──▶ HTML
                                                      │
                                          + 自定义 CSS ─▶ weasyprint ─▶ PDF
```

- **中文字体**：CSS 指定 `font-family: "PingFang SC", "Noto Sans CJK SC", sans-serif;`；weasyprint 需系统装好字体或通过 `PDF_FONT_PATH` 指定。
- **排版要点**：
  - 封面页：标题 + 播客名 + 日期 + 时长
  - 目录 / Shownotes 独立分页
  - 正文：说话人名加粗、时间戳灰色小字、合理行距（1.6）与段间距
  - 页眉页脚：页码 + episode 短标题
- **备选方案**：若 weasyprint 在目标机器装系统依赖困难，退回 `reportlab` + 注册 CJK 字体（代码更繁琐但依赖更轻）。

### 4.3 `src/exporters/__init__.py` 统一分发
```python
def export(segments, meta, fmt, out_path):
    if fmt == "txt":  ...
    elif fmt == "srt": ...
    elif fmt == "md":  md.export(...)
    elif fmt == "pdf": pdf.export(...)
```
原 `transcribe.py` 内联的 txt/srt 生成逻辑迁移到此，`transcribe_audio` 只负责产 `list[Segment]`。

### 4.4 UI 改动（`app.py`）
- 输出格式下拉框：`["txt", "srt", "md", "pdf"]`。
- PDF 生成耗时较短但仍可能 1–3 秒，加 `st.spinner`。
- 预览区对 MD 做渲染（`st.markdown`），PDF 提供 `st.download_button`。

---

## 5. 阶段 3：说话人区分（需求 3）

### 5.1 `src/diarize.py`（核心：时间戳对齐）
```
faster-whisper 段 ──┐
                    ├─▶ 按 [start,end] 重叠投票 ──▶ Segment.speaker = "SPEAKER_0X"
pyannote 说话人轨道 ─┘
```
- 用 `pyannote.audio` 的 `pyannote.audio.Pipeline.from_pretrained("pyannote/speaker-diarization-3.1")`，需 `HF_TOKEN` 并在该模型页同意条款。
- 开启 `word_timestamps=True` 后，**按词级别**对齐比按段更准（一个 whisper 段跨两人时尤其重要）。
- 缓存：同一音频的 diarization 结果落盘 `<title>.diarization.json`，避免重跑。

### 5.2 `src/names.py`（SPEAKER_0X ▶ 真实姓名）
自动映射不可靠（声纹→姓名无 Ground Truth），采用**半自动**：

1. 从 `EpisodeMeta.hosts/guests` + shownotes 正则提取候选姓名列表。
2. 启发式猜测（如：第一个发言的通常是主理人；若仅 1 位候选则直接赋值）。
3. **UI 兜底确认**：diarization 完成后弹出一个小表单——

   ```
   SPEAKER_00 ➡ [ 下拉选: 主播A / 主播B / 嘉宾C / 不标注 ]
   SPEAKER_01 ➡ [ ... ]
   ```

   用户一次确认后写回 `Segment.speaker`，并记住该 episode 的映射。

### 5.3 串联进流程
- `app.py` 转录区新增「区分说话人」复选框（默认开），关闭时跳过 diarize。
- 勾选后：转录 ▶ diarize ▶ (可选) names 确认 ▶ 进入导出。
- MD/PDF/SRT 导出在有 `speaker` 时按上文 4.1 的对话体排版；SRT 加 `Speaker: 文本`。

### 5.4 风险
- pyannote 首次运行需下载 ~3GB 模型 + 授权；在 README 增加说明。
- CPU 上 diarization 较慢（约为音频时长的 0.5–1x），需在 UI 提示预计耗时并支持跳过。

---

## 6. 阶段 1：AI 修正转录（需求 1）

### 6.1 `src/correct.py`
输入：`list[Segment]` + `EpisodeMeta`；输出：修正后的 `list[Segment]`（时间戳/说话人不变，仅 `text` 被校正）。

**分块策略（关键，避免超长上下文与高成本）：**
- 按**说话人切换边界**切块，每块目标 800–1200 字，块间 1–2 句重叠防止断句丢失。
- 每块携带**精简上下文**：播客名、主理人简介（截断）、shownotes 中与该块关键词相关的片段（可选，用简单关键词匹配裁剪以控 token）。

**Prompt 设计要点（写入 `prompts/correct.md`）：**
- 角色：你是该播客的转录校对员。
- 输入：主理人背景、本期 shownotes、待校对片段（带说话人）。
- 规则：① 仅修正 ASR 错误（专有名词、同音错字、断句标点）；② 不得增删语义、不得臆造；③ 专业术语优先以 shownotes 为准；④ 仅输出修正后的 JSON 片段，保持结构与说话人标签。
- 强约束 JSON 输出，便于程序回填，避免重新解析自由文本。

**实现要点：**
- 用 OpenAI 兼容 SDK（`openai` 包配 `base_url`），可对接 DeepSeek/GLM/Moonshot 等，成本低。
- 流式可选；带重试与超时；失败时保留原片段不中断整体流程。
- 成本可见：UI 显示「预计调用 N 次 / 约 X 千 token」。

### 6.2 UI 改动
- 转录区新增「AI 修正」复选框 + 模型选择（读 `config.py`）。
- 顺序：转录 ▶ (diarize) ▶ **correct** ▶ 导出。
- 修正前后对比预览（左右两栏 `st.text_area`），便于人工抽检。

### 6.3 风险
- **幻觉**：靠 Prompt 强约束 + 仅替换 text + 抽检 UI 缓解；可加「严格模式」开关（仅允许标点/错字，禁用整句改写）。
- **长播客成本**：分块 + 可选关闭 + 显示预估 token。
- **API 不可用**：`config.py` 校验失败时 UI 明确提示，并允许跳过修正直接导出。

---

## 7. 文件变更总览

```
src/
├── models.py              [新] Segment / EpisodeMeta
├── config.py              [新] 配置管理
├── download.py            [改] 抓取 shownotes/元信息，返回 EpisodeMeta
├── transcribe.py          [改] 返回 list[Segment]，剥离导出逻辑
├── diarize.py             [新] pyannote 对齐              (阶段3)
├── names.py               [新] 说话人姓名映射              (阶段3)
├── correct.py             [新] LLM 分块修正                (阶段1)
├── exporters/
│   ├── __init__.py        [新] 分发
│   ├── txt.py / srt.py    [新] 由 transcribe.py 迁入
│   ├── md.py              [新]                            (阶段2)
│   └── pdf.py             [新] weasyprint                 (阶段2)
├── app.py                 [改] 新格式选项 / 说话人 / 修正 UI
prompts/
└── correct.md             [新] 修正 Prompt 模板             (阶段1)
requirements.txt           [新/补]
.env.example               [新]
README.md                  [改] 新增能力与依赖说明
```

**新增依赖（写入 requirements.txt）：**
- 阶段 2：`markdown`、`weasyprint`（或备选 `reportlab`）
- 阶段 3：`pyannote.audio`、`torchaudio`（注意与现有 torch 版本兼容）
- 阶段 1：`openai`、`python-dotenv`

---

## 8. 测试策略

| 层次 | 做法 |
|------|------|
| 抓取 | 固定 2–3 个真实 episode URL 作为回归用例，断言关键字段非空 |
| 转录对齐 | 用一段已知双人对话音频，校验 speaker 分配准确率（人工标注小样本） |
| 导出 | 对同一组 `Segment` 生成 4 种格式，快照对比（snapshot）防回归 |
| 修正 | 准备含明显 ASR 错字的样本，断言关键专有名词被纠正且段数不变 |
| 端到端 | 手动跑完整链路，记录耗时与成本 |

---

## 9. 待确认事项（开工前需拍板）

1. **LLM 供应商**：默认建议 OpenAI 兼容接口（DeepSeek / GLM / Moonshot 任选其一）。用哪家？是否接受按量付费？
2. **pyannote 授权**：是否同意申请 HuggingFace token 并下载 ~3GB 模型？若否，需求 3 需降级为「仅 UI 手动标注说话人」。
3. **中文字体**：目标运行机是否有 PingFang/Noto Sans CJK？若无，需随项目内置一份可商用字体（如思源黑体）。
4. **shownotes DOM 选择器**：需在一个真实 episode 页面 DevTools 确认后再编码（见 3.4）。
5. **运行环境**：是否仍仅 CPU？GPU/MPS 可显著加速 diarize 与 whisper，影响默认参数。

---

## 10. 工作量预估（粗估，单人）

| 阶段 | 预估 |
|------|------|
| 0 基础重构 | 1–1.5 天 |
| 2 MD/PDF | 1–1.5 天 |
| 3 说话人区分 | 2–3 天（含 pyannote 调试与姓名映射 UI） |
| 1 AI 修正 | 1.5–2 天（含 Prompt 调优） |
| 联调 + 文档 | 0.5–1 天 |
| **合计** | **约 6–9 天** |
