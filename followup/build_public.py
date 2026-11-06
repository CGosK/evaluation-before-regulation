"""
Build the public copy of this project into a clone of the public repository. Nothing is committed or pushed.

The rules are the October release's (theory/HANDOFF.md) plus the follow-up's:
    excluded     the thesis PDFs and LaTeX, the notebooks, CLAUDE.md, the lint workflow and pre-commit config,
                 theory/references/, HANDOFF.md, CLOUD_RUN.md and build_paper.sh, and the usage guard's
                 plan-window readings (usage_guard.jsonl and .log, pause files). Only committed files are
                 copied, so nothing outside git can reach the public copy
    kept as is   pyproject.toml and uv.lock, which the public copy points at the public starter repository
    rewritten    this folder's absolute path becomes ./ and any other home path becomes ~
    added        a pointer to the follow-up in README.md, after the paper line (the README itself is frozen)

Usage:  .venv/bin/python followup/build_public.py PUBLIC_CLONE
Then:   .venv/bin/python followup/check_clean.py PUBLIC_CLONE, and git -C PUBLIC_CLONE status
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = str(Path.home())
EXCLUDE = re.compile(
    r"^(BSE_DSDM_.*\.pdf|main\.tex|final_presentation\.tex|CLAUDE\.md|\.pre-commit-config\.yaml"
    r"|\.github/.*|latex/.*|notebooks/.*|theory/references/.*"
    r"|theory/(HANDOFF\.md|CLOUD_RUN\.md|build_paper\.sh)"
    r"|followup/.*(usage_guard\.(jsonl|log)|pause[^/]*\.json)|followup/PAPER_REVISED\.html)$"
)
KEEP_PUBLIC = {"pyproject.toml", "uv.lock"}
PAPER_LINE = "**Paper:** [`theory/PAPER_DRAFT.pdf`]"
POINTER = """
**Follow-up (November 2026).** After the sprint review I ran nine more waves of experiments. They narrow the
summary below: the remedies that prevented collusion in Haiku 4.5 worked only partly or not at all on Claude
Opus 5.5, and Opus's prices depend on which model it competes with. The work is in [`followup/`](followup/):

- [`FOLLOWUP_NOTE.md`](followup/FOLLOWUP_NOTE.md) ([PDF](followup/FOLLOWUP_NOTE.pdf)): the findings first, then the evidence;
- [`CLAIMS_STATUS.md`](followup/CLAIMS_STATUS.md): each of the paper's claims, marked as holding, narrowed or
  not retested;
- [`PAPER_REVISED.pdf`](followup/PAPER_REVISED.pdf): a wording-only revision of the paper.

The paper linked above is the version submitted on 25 October 2026, tagged `submission-2026-10-25`.
"""


def tracked() -> list:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
    ).stdout
    return [p for p in out.decode().split("\0") if p]


def rewrite(rel: str, raw: bytes) -> bytes:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw
    text = text.replace(str(ROOT) + "/", "./").replace(str(ROOT), ".").replace(HOME, "~")
    if rel == "README.md":
        lines = text.split("\n")
        at = next(i for i, line in enumerate(lines) if line.startswith(PAPER_LINE))
        lines[at + 1 : at + 1] = POINTER.rstrip("\n").split("\n")
        text = "\n".join(lines)
    return text.encode("utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("clone", type=Path)
    a = ap.parse_args()
    if not (a.clone / ".git").exists():
        sys.exit(f"{a.clone} is not a git clone of the public repository")
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no", "."],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    if dirty:
        sys.exit(f"commit these first, so the public copy matches a commit:\n{dirty}")
    written = skipped = 0
    for rel in tracked():
        if EXCLUDE.match(rel) or rel in KEEP_PUBLIC:
            skipped += 1
            continue
        dest = a.clone / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        new = rewrite(rel, (ROOT / rel).read_bytes())
        if not dest.exists() or dest.read_bytes() != new:
            dest.write_bytes(new)
            written += 1
    print(f"wrote {written} files, left out {skipped}, into {a.clone}")
