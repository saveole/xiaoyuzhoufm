from models import Segment, EpisodeMeta


def export(segments: list[Segment], meta: EpisodeMeta, fmt: str, out_path: str) -> str:
    if fmt == "txt":
        from exporters import txt
        return txt.export(segments, meta, out_path)
    elif fmt == "srt":
        from exporters import srt
        return srt.export(segments, meta, out_path)
    elif fmt == "md":
        from exporters import md
        return md.export(segments, meta, out_path)
    elif fmt == "pdf":
        from exporters import pdf
        return pdf.export(segments, meta, out_path)
    else:
        raise ValueError(f"Unsupported format: {fmt}")
