from models import Segment, EpisodeMeta


def export(segments: list[Segment], meta: EpisodeMeta, out_path: str) -> str:
    lines = []
    for seg in segments:
        text = seg.text.strip()
        if seg.speaker:
            lines.append(f"[{seg.speaker}] {text}")
        else:
            lines.append(text)
    content = "\n".join(lines)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    return content
