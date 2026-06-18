- [x] 目前的转录文本不够精准，我希望将转录出来的文本结合主播背景，当前 episode show notes 等上下文进行 AI 修正
  > 实现：`src/correct.py` — LLM 分块修正，`prompts/correct.md` — 修正 Prompt

- [x] 转录格式较少，希望添加 md 和 pdf 格式，并注意排版
  > 实现：`src/exporters/md.py` — front-matter + 对话体排版；`src/exporters/pdf.py` — weasyprint PDF

- [x] 要区分出播客不同人的不同发言内容，不同人等信息可以通过 shownotes 查看
  > 实现：`src/diarize.py` — pyannote 说话人区分；`src/names.py` + UI — 说话人姓名映射
