"""
Builds theory/PAPER_DRAFT.pdf from PAPER_DRAFT.md: Python-Markdown makes a self-contained HTML page (figures
embedded, styled by paper.css), then headless Chrome prints it to A4 with page numbers. Reports the page count
and where the References begin, against the sprint's limit of 8 pages before the references and appendices.

Refuses to build while {{placeholders}} remain; --draft builds anyway, blanking them.

Usage:  uv run --with markdown --with playwright --with pypdf python theory/build_paper.py [--draft]
Writes: theory/PAPER_DRAFT.html, theory/PAPER_DRAFT.pdf
"""

import base64
import html
import re
import sys
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright
from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
MD, HTML, PDF = HERE / "PAPER_DRAFT.md", HERE / "PAPER_DRAFT.html", HERE / "PAPER_DRAFT.pdf"


def figure(m: re.Match) -> str:
    """![caption](path){width=NN%} -> an embedded <figure>."""
    caption, path, width = m.group(1), m.group(2), m.group(3) or "100"
    data = base64.b64encode((HERE / path).read_bytes()).decode()
    return (f'\n<figure><img src="data:image/png;base64,{data}" style="width:{width}%" alt="{html.escape(caption)}">'
            f"<figcaption>{markdown.markdown(caption)[3:-4]}</figcaption></figure>\n")


def to_html(text: str) -> str:
    meta, body = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S).groups()
    fields = dict(re.findall(r'^(\w+): "(.*)"$', meta, re.M))
    body = re.sub(r"!\[(.*?)\]\((.*?)\)(?:\{width=(\d+)%\})?", figure, body)
    # bare URLs (the references) become links; ones already inside a markdown link are left alone
    body = re.sub(r"(?<![<(])\bhttps?://[^\s<>]+?(?=[.,;:]?(?:\s|$))", lambda m: f"<{m.group(0)}>", body)
    # headings get ids from their text, as pandoc's would, so the stylesheet can place page breaks
    page = markdown.markdown(body, extensions=["tables", "toc", "sane_lists"],
                             extension_configs={"toc": {"slugify": lambda s, sep: re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")}})
    css = (HERE / "paper.css").read_text()
    head = (f'<header><h1 class="title">{fields["title"]}</h1><p class="author">{fields["author"]}</p>'
            f'<p class="date">{fields.get("date", "")}</p></header>')
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{fields["title"]}</title>'
            f"<style>{css}</style></head><body>{head}{page}</body></html>")


def main(draft: bool):
    text = MD.read_text()
    holes = sorted(set(re.findall(r"\{\{[A-Z0-9_]+\}\}", text)))
    if holes and not draft:
        sys.exit(f"placeholders remain: {', '.join(holes)} (use --draft to build anyway)")
    text = re.sub(r"\{\{[A-Z0-9_]+\}\}", "", text)
    HTML.write_text(to_html(text))
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        page = browser.new_page()
        page.goto(HTML.as_uri())
        page.pdf(path=str(PDF), format="A4", print_background=True, display_header_footer=True,
                 header_template="<span></span>",
                 footer_template='<div style="font-size:8pt;width:100%;text-align:center;color:#555">'
                                 '<span class="pageNumber"></span></div>',
                 margin={"top": "18mm", "bottom": "18mm", "left": "18mm", "right": "18mm"})
        browser.close()
    reader = PdfReader(str(PDF))
    starts = {}
    for i, pg in enumerate(reader.pages, 1):
        t = pg.extract_text() or ""
        for key in ("References", "Appendix A.", "LLM Usage Statement"):
            if key not in starts and re.search(rf"^{re.escape(key)}", t, re.M):
                starts[key] = i
    abstract = text.split("## Abstract")[1].split("## 1.")[0]
    print(f"{len(reader.pages)} pages; abstract {len(re.findall(r'[A-Za-z0-9][A-Za-z0-9.,%–-]*', abstract))} words; "
          f"section starts: {starts}")
    print(f"main text ends on page {starts.get('References', '?')} (limit: 8 pages before the references)")


if __name__ == "__main__":
    main("--draft" in sys.argv)
