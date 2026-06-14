"""Render docs/technical_report.md to docs/technical_report.pdf.

Pure-Python markdown -> HTML, with inlined SVGs and a tight A4 stylesheet,
then Microsoft Edge headless prints the HTML to PDF. Edge ships with every
Windows install, so this avoids the GTK / wkhtmltopdf dependency mess that
weasyprint and pdfkit hit on Windows.

Usage:
    python scripts/build_report_pdf.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import markdown


REPO = Path(__file__).resolve().parent.parent
MD = REPO / "docs" / "technical_report.md"
HTML = REPO / "docs" / "technical_report.html"
PDF = REPO / "docs" / "technical_report.pdf"

EDGE_CANDIDATES = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]

CSS = """
@page { size: A4; margin: 14mm 16mm 14mm 16mm; }
html, body {
    font-family: -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    color: #111;
    font-size: 9.8pt;
    line-height: 1.32;
}
h1 { font-size: 16pt; margin: 0 0 4pt 0; }
h2 { font-size: 11.5pt; margin: 10pt 0 4pt 0; border-bottom: 0.6pt solid #555; padding-bottom: 1pt; }
h3 { font-size: 10pt; margin: 8pt 0 3pt 0; }
p  { margin: 0 0 5pt 0; text-align: justify; hyphens: auto; }
ul, ol { margin: 0 0 5pt 16pt; }
li { margin-bottom: 2pt; }
table { border-collapse: collapse; width: 100%; font-size: 8.6pt; margin: 4pt 0 6pt 0; }
th, td { border: 0.4pt solid #888; padding: 2pt 4pt; text-align: left; }
th { background: #eef2f7; }
code, pre {
    font-family: "JetBrains Mono", "Consolas", Menlo, monospace;
    font-size: 8.6pt;
    background: #f4f4f4;
    border-radius: 2pt;
    padding: 0 2pt;
}
pre { padding: 4pt 6pt; }
svg, img { max-width: 100%; height: auto; }
.subtitle { color: #555; font-size: 10pt; margin-top: -2pt; margin-bottom: 6pt; }
"""


def _inline_svgs(html: str) -> str:
    """Replace <img src="*.svg"> with the SVG contents so Edge embeds it cleanly."""
    pattern = re.compile(r'<img[^>]+src="([^"]+\.svg)"[^>]*/?>')

    def repl(match: re.Match[str]) -> str:
        rel = match.group(1)
        candidate = (MD.parent / rel).resolve()
        if not candidate.exists():
            return match.group(0)
        svg = candidate.read_text(encoding="utf-8")
        # Strip the XML prolog so the SVG sits inline in HTML.
        svg = re.sub(r"<\?xml[^>]*\?>\s*", "", svg)
        return f'<div class="svg-wrap">{svg}</div>'

    return pattern.sub(repl, html)


def _strip_front_matter(md_text: str) -> tuple[dict[str, str], str]:
    """Pull YAML-style front matter out of the markdown for use as <title>."""
    front: dict[str, str] = {}
    if not md_text.startswith("---"):
        return front, md_text
    end = md_text.find("\n---", 3)
    if end == -1:
        return front, md_text
    block = md_text[3:end]
    for line in block.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            front[k.strip()] = v.strip().strip('"')
    return front, md_text[end + 4 :].lstrip()


def _find_edge() -> Path:
    for candidate in EDGE_CANDIDATES:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "Microsoft Edge not found in the standard install locations."
    )


def build() -> None:
    md_source = MD.read_text(encoding="utf-8")
    front, body_md = _strip_front_matter(md_source)
    title = front.get("title", "Technical report")
    subtitle = front.get("subtitle", "")
    author = front.get("author", "")
    date = front.get("date", "")

    body_html = markdown.markdown(
        body_md,
        extensions=["tables", "fenced_code", "attr_list", "md_in_html"],
    )
    body_html = _inline_svgs(body_html)

    header_html = (
        f'<h1>{title}</h1>'
        f'<div class="subtitle">{subtitle}</div>'
        f'<div class="subtitle">{author} &middot; {date}</div>'
    )

    full_html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>{title}</title><style>{CSS}</style></head>
<body>{header_html}{body_html}</body></html>"""

    HTML.write_text(full_html, encoding="utf-8")
    print(f"Wrote {HTML.relative_to(REPO)}")

    edge = _find_edge()
    # Classic --headless honours --print-to-pdf; --headless=new silently drops it
    # in some Edge versions, so stay on classic until that is fixed upstream.
    cmd = [
        str(edge),
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        # Edge headless on Windows wants forward slashes in --print-to-pdf,
        # otherwise it silently exits 0 without writing the file.
        f"--print-to-pdf={PDF.as_posix()}",
        HTML.as_uri(),
    ]
    print(f"Calling Edge headless to render PDF ...")
    # Remove any stale PDF so the poll loop only sees a freshly written file.
    PDF.unlink(missing_ok=True)
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if res.returncode != 0:
        print(res.stderr, file=sys.stderr)
        raise SystemExit(f"Edge exited with {res.returncode}")
    # Edge spawns a child for PDF writing and returns before it finishes;
    # poll briefly for the file rather than failing on the race.
    import time
    deadline = time.time() + 20
    while not PDF.exists() and time.time() < deadline:
        time.sleep(0.2)
    if not PDF.exists():
        raise SystemExit("Edge returned OK but no PDF was written within 20 s.")
    print(f"Wrote {PDF.relative_to(REPO)}  ({PDF.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    build()
