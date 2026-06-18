import json
import time
from typing import Optional

from config import LLM_BASE_URL, LLM_API_KEY, LLM_MODEL
from models import Segment, EpisodeMeta

SYSTEM_PROMPT = """你是播客转录校对员。你的任务是对 ASR（自动语音识别）输出的文本进行最小必要的修正。

## 输入格式
JSON 数组，每个元素包含：
- index: 片段序号（保持原样输出）
- text: ASR 识别的原始文本
- speaker（可选）：说话人
- 同时提供本期播客的元信息（标题、播客名、shownotes、主播/嘉宾列表）作为上下文

## 修正规则
1. 仅修正 ASR 错误：专有名词、同音错字、断句标点、数字单位
2. 不得增删语义：不添加原文没有的内容，不臆造
3. 专业术语以 shownotes 为准
4. 专有名词（人名、地名、品牌名）优先以主播/嘉宾列表和 shownotes 为准
5. 修正断句和标点符号
6. 保持原始的说话人标签不变
7. 如果原始文本无明显错误，保持原样

## 输出格式
严格输出 JSON 数组，与输入结构一致，仅修改 text 字段。
不要输出任何其他内容。"""


def _build_chunk_prompt(
    chunk: list[dict],
    meta: EpisodeMeta,
) -> str:
    context_parts = []
    context_parts.append(f"播客：{meta.podcast}")
    context_parts.append(f"标题：{meta.title}")
    if meta.hosts:
        context_parts.append(f"主播：{'、'.join(meta.hosts)}")
    if meta.guests:
        context_parts.append(f"嘉宾：{'、'.join(meta.guests)}")

    shownotes_preview = meta.shownotes[:800] if meta.shownotes else ""
    if shownotes_preview:
        context_parts.append(f"Shownotes（节选）：\n{shownotes_preview}")

    context_parts.append("---")
    context_parts.append("请修正以下转录片段（JSON 数组）：")

    return "\n".join(context_parts)


def _chunk_segments(
    segments: list[Segment],
    max_chars: int = 1200,
    overlap: int = 1,
) -> list[list[dict]]:
    chunked = []
    current_chunk = []
    current_chars = 0

    for i, seg in enumerate(segments):
        seg_dict = {
            "index": i,
            "text": seg.text.strip(),
        }
        if seg.speaker:
            seg_dict["speaker"] = seg.speaker

        seg_len = len(seg.text)

        if current_chars + seg_len > max_chars and current_chunk:
            chunked.append(current_chunk)

            overlap_items = current_chunk[-overlap:] if overlap > 0 else []
            current_chunk = list(overlap_items)
            current_chars = sum(len(s["text"]) for s in overlap_items)
            current_chunk.append(seg_dict)
            current_chars += seg_len
        else:
            current_chunk.append(seg_dict)
            current_chars += seg_len

    if current_chunk:
        chunked.append(current_chunk)

    return chunked


def correct_segments(
    segments: list[Segment],
    meta: EpisodeMeta,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    max_retries: int = 2,
) -> list[Segment]:
    key = api_key or LLM_API_KEY
    url = base_url or LLM_BASE_URL
    mdl = model or LLM_MODEL

    if not key:
        print("LLM_API_KEY 未设置，跳过修正")
        return segments

    try:
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url=url)
    except ImportError:
        print("openai 库未安装，跳过修正。请运行：pip install openai")
        return segments

    chunks = _chunk_segments(segments)
    corrected_segments = list(segments)

    total_chunks = len(chunks)
    print(f"共 {total_chunks} 个片段需要修正")

    for chunk_idx, chunk in enumerate(chunks):
        chunk_prompt = _build_chunk_prompt(chunk, meta)
        user_msg = json.dumps(chunk, ensure_ascii=False, indent=2)

        for attempt in range(max_retries + 1):
            try:
                kwargs = dict(
                    model=mdl,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"{chunk_prompt}\n\n{user_msg}"},
                    ],
                    temperature=0.1,
                )
                try:
                    kwargs["response_format"] = {"type": "json_object"}
                    response = client.chat.completions.create(**kwargs)
                except Exception:
                    kwargs.pop("response_format", None)
                    response = client.chat.completions.create(**kwargs)
                result_text = response.choices[0].message.content
                result = json.loads(result_text)

                if isinstance(result, list):
                    for item in result:
                        idx = item.get("index")
                        if idx is not None and 0 <= idx < len(corrected_segments):
                            corrected_segments[idx].text = item["text"]
                elif isinstance(result, dict) and "segments" in result:
                    for item in result["segments"]:
                        idx = item.get("index")
                        if idx is not None and 0 <= idx < len(corrected_segments):
                            corrected_segments[idx].text = item["text"]

                print(f"  片段 {chunk_idx + 1}/{total_chunks} 修正完成")
                break

            except Exception as e:
                if attempt < max_retries:
                    print(f"  片段 {chunk_idx + 1}/{total_chunks} 重试 ({attempt + 1}/{max_retries}): {e}")
                    time.sleep(1)
                else:
                    print(f"  片段 {chunk_idx + 1}/{total_chunks} 修正失败: {e}")

    return corrected_segments
