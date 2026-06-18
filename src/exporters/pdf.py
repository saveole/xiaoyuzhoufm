import os
import tempfile

from config import PDF_FONT_PATH
from models import Segment, EpisodeMeta
from exporters import md as md_exporter


def export(segments: list[Segment], meta: EpisodeMeta, out_path: str) -> str:
    md_content = md_exporter.export(segments, meta, out_path + ".md")
    import markdown

    html_body = markdown.markdown(
        md_content,
        extensions=["extra", "codehilite", "toc"],
    )

    font_family = ("'PingFang SC', 'Noto Sans CJK SC', 'Microsoft YaHei', "
                   "'SimHei', sans-serif")
    if PDF_FONT_PATH:
        font_family = f"'{PDF_FONT_PATH}', {font_family}"

    css = f"""
    @page {{
        size: A4;
        margin: 2.5cm 2cm;
        @top-right {{
            content: "{meta.title}";
            font-size: 9pt;
            color: #888;
            font-family: {font_family};
        }}
        @bottom-center {{
            content: counter(page);
            font-size: 9pt;
            color: #888;
            font-family: {font_family};
        }}
    }}
    body {{
        font-family: {font_family};
        font-size: 11pt;
        line-height: 1.8;
        color: #1a1a1a;
    }}
    h1 {{
        font-size: 20pt;
        margin-top: 0;
        margin-bottom: 12pt;
        color: #111;
    }}
    h2 {{
        font-size: 14pt;
        margin-top: 18pt;
        margin-bottom: 8pt;
        color: #333;
        border-bottom: 1px solid #ddd;
        padding-bottom: 4pt;
    }}
    blockquote {{
        margin: 8pt 0;
        padding: 6pt 12pt;
        background: #f5f5f5;
        border-left: 3px solid #999;
        color: #555;
    }}
    strong {{
        color: #222;
    }}
    hr {{
        border: none;
        border-top: 1px solid #ccc;
        margin: 16pt 0;
    }}
    p {{
        margin: 4pt 0 8pt 0;
        text-indent: 0;
    }}
    .page-break {{
        page-break-before: always;
    }}
    """

    full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>{css}</style>
</head>
<body>
{html_body}
</body>
</html>"""

    try:
        from weasyprint import HTML
        HTML(string=full_html).write_pdf(out_path)
    except ImportError:
        raise ImportError(
            "weasyprint 未安装，无法生成 PDF。请运行：pip install weasyprint\n"
            "如果安装失败，请先安装系统依赖：\n"
            "  Ubuntu/Debian: sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0\n"
            "  macOS: brew install weasyprint"
        )

    return md_content
