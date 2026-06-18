# 小宇宙播客工具 — 实现总览

> 本文档基于 `roadmap.md` 的三项需求，记录了完整的实现方案与当前状态。所有需求已实现。

---

## 0. 架构

### 0.1 数据流

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

### 0.2 核心数据结构

```python
@dataclass
class Segment:
    start: float
    end: float
    text: str
    speaker: Optional[str] = None

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

## 1. 实现状态

| 阶段 | 对应需求 | 状态 | 关键文件 |
|------|---------|------|---------|
| 0 基础重构 | 前置依赖 | ✅ 已完成 | `models.py`, `config.py`, 重构 `download.py`/`transcribe.py` |
| 2 多格式导出 | 需求 2 | ✅ 已完成 | `exporters/md.py`, `exporters/pdf.py` |
| 3 说话人区分 | 需求 3 | ✅ 已完成 | `diarize.py`, `names.py` |
| 1 AI 修正 | 需求 1 | ✅ 已完成 | `correct.py`, `prompts/correct.md` |

---

## 2. 模块说明

### 2.1 `src/models.py`
`Segment` / `EpisodeMeta` 两个 dataclass，贯穿全流程的唯一数据结构。

### 2.2 `src/config.py`
配置管理，优先级：环境变量 > `.env` > 默认值。

关键配置项：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `LLM_BASE_URL` | OpenAI 兼容 API 端点 | `https://api.deepseek.com` |
| `LLM_API_KEY` | API Key | `""` |
| `LLM_MODEL` | 模型名 | `deepseek-chat` |
| `HF_TOKEN` | HuggingFace Token（pyannote） | `""` |
| `PDF_FONT_PATH` | 中文字体路径 | `""` |

### 2.3 `src/download.py`
- Selenium 无头浏览器抓取页面
- 获取标题、播客名、主播/嘉宾、发布日期、shownotes
- 下载音频到 `audio_files/`，同时落盘 `<title>.meta.json`
- DOM 选择器使用 `contains(@class, ...)` XPath + 多重兜底

### 2.4 `src/transcribe.py`
- `transcribe_audio()` 返回 `list[Segment]`
- 启用 `word_timestamps=True`（为说话人对齐做准备）
- 模型缓存 `@lru_cache` 保持
- 保留 CLI 入口，通过 `exporters` 适配输出

### 2.5 `src/exporters/`

| 模块 | 格式 | 说明 |
|------|------|------|
| `txt.py` | TXT | 纯文本，有 speaker 时加 `[Speaker]` 前缀 |
| `srt.py` | SRT | 字幕格式，有 speaker 时加 `Speaker:` |
| `md.py` | Markdown | front-matter + 对话体排版 + shownotes |
| `pdf.py` | PDF | weasyprint 渲染，含页眉页脚 + 中文排版 |

`__init__.py` 统一分发 `export(segments, meta, fmt, out_path)`。

### 2.6 `src/diarize.py`
- 使用 `pyannote/speaker-diarization-3.1`
- whisper 段与 pyannote 轨道的重叠投票对齐
- 结果缓存到 `<title>.diarization.json`

### 2.7 `src/names.py`
- 从 `hosts`/`guests` + shownotes 中 `@` 提及提取候选名单
- 核心映射逻辑在 `app.py` UI 中完成（SPEAKER_0X ➡ 下拉选人）

### 2.8 `src/correct.py`
- 按字数量切块（目标 1200 字/块），块间 1 段重叠
- 每块携带精简上下文（播客名、主播、shownotes 节选）
- OpenAI 兼容 SDK，`response_format` 有兼容性回退
- 失败时保留原片段，不中断流程

### 2.9 `src/app.py`
Streamlit 主界面，三步骤：

1. **下载**：URL 输入 → 下载 + 元信息展示（标题/播客/主播/shownotes）
2. **转录**：设备选择 + 格式选择 + 说话人区分复选框 + AI 修正复选框 + 模型选择
3. **后处理与导出**：
   - 说话人映射 UI（下拉选人 → 应用到全部片段）
   - 格式切换预览（MD 渲染、PDF 文字预览、TXT/SRT 文本域）
   - 下载按钮
   - 修正前后对比（仅显示有差异的片段）

---

## 3. 文件清单

```
src/
├── app.py                 Streamlit 主界面
├── models.py              数据模型 Segment / EpisodeMeta
├── config.py              配置管理
├── download.py            下载 + 元信息抓取
├── transcribe.py          转录 → list[Segment]
├── diarize.py             pyannote 说话人区分
├── names.py               说话人姓名映射
├── correct.py             LLM 分块修正
├── exporters/
│   ├── __init__.py        分发入口
│   ├── txt.py             TXT 导出
│   ├── srt.py             SRT 导出
│   ├── md.py              Markdown 导出
│   └── pdf.py             PDF 导出 (weasyprint)
prompts/
└── correct.md             修正 Prompt 模板
.env.example                配置模板
requirements.txt            依赖清单
```

---

## 4. 注意事项

### 4.1 pyannote / 说话人区分
- 首次运行下载 ~3GB 模型
- 需 HuggingFace token 并在模型页同意条款
- CPU 上较慢（约 0.5–1x 音频时长）

### 4.2 PDF 导出
- 依赖 weasyprint，需安装系统库（见 README）
- 中文排版需系统安装中文字体

### 4.3 AI 修正
- 按片段数调用 LLM，注意 token 消耗
- 仅支持 OpenAI 兼容 API（DeepSeek / GLM / Moonshot 等）

### 4.4 DOM 选择器
- 小宇宙页面 class 带动态 hash
- 使用 `contains(@class, ...)` XPath + 多重兜底
- shownotes 为 SSR HTML，`WebDriverWait` 等待加载
