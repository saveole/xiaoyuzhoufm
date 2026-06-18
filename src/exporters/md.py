from models import Segment, EpisodeMeta


def format_duration(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}h{minutes:02d}m"
    return f"{minutes}m{secs:02d}s"


def format_ts(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def export(segments: list[Segment], meta: EpisodeMeta, out_path: str) -> str:
    lines = []
    lines.append("---")
    lines.append(f"title: \"{meta.title}\"")
    if meta.podcast:
        lines.append(f"podcast: \"{meta.podcast}\"")
    if meta.hosts:
        lines.append(f"hosts: [{', '.join(meta.hosts)}]")
    if meta.guests:
        lines.append(f"guests: [{', '.join(meta.guests)}]")
    if meta.published_at:
        lines.append(f"date: {meta.published_at}")
    if meta.duration:
        lines.append(f"duration: \"{format_duration(meta.duration)}\"")
    lines.append("---")
    lines.append("")
    lines.append(f"# {meta.title}")
    lines.append("")

    if meta.hosts or meta.guests:
        parts = []
        if meta.hosts:
            parts.append(f"主播：{'、'.join(meta.hosts)}")
        if meta.guests:
            parts.append(f"嘉宾：{'、'.join(meta.guests)}")
        if parts:
            lines.append(f"> {' ｜ '.join(parts)}")
            lines.append("")

    if meta.shownotes:
        lines.append("## Shownotes")
        lines.append("")
        lines.append(meta.shownotes.strip())
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## 对话记录")
    lines.append("")

    prev_speaker = None
    for seg in segments:
        ts = format_ts(seg.start)
        text = seg.text.strip()
        if not text:
            continue

        if seg.speaker:
            speaker_label = seg.speaker
            lines.append(f"**[{ts}] {speaker_label}：**")
            lines.append("")
            lines.append(text)
            lines.append("")
        else:
            lines.append(f"**[{ts}]**")
            lines.append("")
            lines.append(text)
            lines.append("")

    content = "\n".join(lines)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    return content
