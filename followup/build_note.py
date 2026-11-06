"""
Builds followup/FOLLOWUP_NOTE.pdf from FOLLOWUP_NOTE.md, with the paper's stylesheet (theory/paper.css) and
headless Chrome, as theory/build_paper.py does. Headings keep GitHub's anchors, so the note's contents list
works in the PDF, and links to other files in the repository point at the public repository. Checks the
note's numbers with check_followup.py first and refuses to build if any fails.

Usage:  uv run --extra analysis --with markdown --with playwright --with pypdf python followup/build_note.py
Writes: followup/FOLLOWUP_NOTE.html, followup/FOLLOWUP_NOTE.pdf
"""

import base64
import html
import re
import subprocess
import sys
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright
from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
MD, HTML, PDF = HERE / "FOLLOWUP_NOTE.md", HERE / "FOLLOWUP_NOTE.html", HERE / "FOLLOWUP_NOTE.pdf"
REPO = "https://github.com/CGosK/evaluation-before-regulation/blob/main/followup/"


def github_slug(text: str, sep: str = "-") -> str:
    return re.sub(r"[^\w\- ]", "", text.strip().lower()).replace(" ", sep)


def figure(m: re.Match) -> str:
    caption, path = m.group(1), m.group(2)
    data = base64.b64encode((HERE / path).read_bytes()).decode()
    return f'\n<figure><img src="data:image/png;base64,{data}" style="width:100%" alt="{html.escape(caption)}"></figure>\n'


LIST = re.compile(r"\s*(?:[-*]|\d+\.)\s")


def blank_before_lists(text: str) -> str:
    """Python-Markdown needs a blank line before a list that follows a paragraph; GitHub doesn't."""
    out, prev = [], ""
    for line in text.split("\n"):
        if LIST.match(line) and prev.strip() and not LIST.match(prev) and not prev.startswith(" "):
            out.append("")
        if LIST.match(line) and line.startswith(
            " "
        ):  # GitHub nests at 2 spaces, Python-Markdown at 4
            line = " " * (2 * (len(line) - len(line.lstrip(" ")))) + line.lstrip(" ")
        out.append(line)
        prev = line
    return "\n".join(out)


def to_html(text: str) -> str:
    title = re.match(r"# (.+)\n", text).group(1)
    body = blank_before_lists(text.split("\n", 1)[1])
    body = re.sub(r"!\[(.*?)\]\((out/.*?)\)", figure, body)
    body = re.sub(r"\]\((?!https?://|#)([^)]+)\)", lambda m: f"]({REPO}{m.group(1)})", body)
    page = markdown.markdown(
        body,
        extensions=["tables", "toc", "sane_lists", "fenced_code"],
        extension_configs={"toc": {"slugify": github_slug}},
    )
    css = (HERE.parent / "theory/paper.css").read_text()
    css += "\nfigure{margin:1em 0 .3em} figure+p em{font-size:.9em} pre{font-size:.8em;white-space:pre-wrap;word-break:break-word}\n"
    head = f'<header><h1 class="title">{html.escape(title)}</h1></header>'
    return (
        f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title>'
        f"<style>{css}</style></head><body>{head}{page}</body></html>"
    )


if __name__ == "__main__":
    check = subprocess.run(
        [sys.executable, str(HERE / "check_followup.py")], capture_output=True, text=True
    )
    summary = next((line for line in check.stdout.splitlines() if "checks pass" in line), "")
    print(summary or check.stderr[-400:])
    if check.returncode:
        sys.exit("\n".join(line for line in check.stdout.splitlines() if line.startswith("FAIL")))
    HTML.write_text(to_html(MD.read_text()))
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        page = browser.new_page()
        page.goto(HTML.as_uri())
        page.pdf(
            path=str(PDF),
            format="A4",
            print_background=True,
            display_header_footer=True,
            header_template="<span></span>",
            footer_template='<div style="font-size:8pt;width:100%;text-align:center;color:#555">'
            '<span class="pageNumber"></span></div>',
            margin={"top": "18mm", "bottom": "18mm", "left": "18mm", "right": "18mm"},
        )
        browser.close()
    print(f"{len(PdfReader(str(PDF)).pages)} pages: {PDF.relative_to(HERE.parent)}")
