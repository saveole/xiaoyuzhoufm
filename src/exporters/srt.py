from models import Segment, EpisodeMeta


def format_timestamp(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millisec = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisec:03d}"


def export(segments: list[Segment], meta: EpisodeMeta, out_path: str) -> str:
    lines = []
    for i, seg in enumerate(segments, start=1):
        start_ts = format_timestamp(seg.start)
        end_ts = format_timestamp(seg.end)
        text = seg.text.strip()
        if seg.speaker:
            text = f"{seg.speaker}: {text}"
        lines.append(f"{i}\n{start_ts} --> {end_ts}\n{text}\n")
    content = "\n".join(lines)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    return content
