# 小宇宙播客下载与转录工具

基于 Streamlit 开发的小宇宙播客下载、转录与后处理工具。

## 功能特点

- 下载播客音频 + 自动抓取元信息（标题、播客名、主播、Shownotes）
- 音频转文字转录（faster-whisper）
- 说话人区分（pyannote.audio）——自动区分不同发言人
- AI 修正转录 —— 结合上下文用 LLM 校正 ASR 错误
- 多格式导出：TXT、SRT、MD、PDF
- 说话人映射 UI —— 将标签映射为真实姓名

## 安装说明

```bash
pip install -r requirements.txt
```

### 可选依赖

- **PDF 导出**：需安装 system 依赖（weasyprint）
  ```bash
  # Ubuntu/Debian
  sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0
  # macOS
  brew install weasyprint
  ```

- **说话人区分**：需在 HuggingFace 同意 [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1) 条款，并将 token 写入 `.env`

## 配置

复制 `.env.example` 为 `.env` 并填写：

| 配置项 | 说明 | 是否必需 |
|--------|------|---------|
| `LLM_API_KEY` | OpenAI 兼容 API Key（用于 AI 修正） | 选填 |
| `LLM_BASE_URL` | API 端点，默认 DeepSeek | 选填 |
| `LLM_MODEL` | 模型名，默认 deepseek-chat | 选填 |
| `HF_TOKEN` | HuggingFace Token（用于说话人区分） | 选填 |
| `PDF_FONT_PATH` | 中文字体路径 | 选填 |

## 使用方法

```bash
streamlit run src/app.py
```

1. 粘贴小宇宙播客链接 → 点击下载
2. 选择输出格式、开启说话人区分 / AI 修正 →
3. 点击转录
4. 映射说话人姓名 → 预览并下载结果

## 项目结构

```
src/
├── app.py           # Streamlit 主界面
├── download.py      # 播客下载 + 元信息抓取
├── transcribe.py    # faster-whisper 转录
├── models.py        # 数据模型（Segment / EpisodeMeta）
├── config.py        # 配置管理（环境变量）
├── diarize.py       # 说话人区分（pyannote）
├── names.py         # 说话人姓名映射
├── correct.py       # LLM 修正
└── exporters/       # 导出模块
    ├── txt.py / srt.py / md.py / pdf.py
prompts/
└── correct.md       # AI 修正 Prompt 模板
```

## 技术栈

Python / Streamlit / faster-whisper / pyannote.audio / weasyprint
