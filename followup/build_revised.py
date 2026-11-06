"""
Builds followup/PAPER_REVISED.pdf (the post-review revision) with the sprint's build, and checks its numbers with
the sprint's checker. The submitted files, theory/PAPER_DRAFT.md and .pdf, are not touched.

Usage:  uv run --with markdown --with playwright --with pypdf python followup/build_revised.py
Writes: followup/PAPER_REVISED.html, followup/PAPER_REVISED.pdf
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "theory"))
import build_paper  # noqa: E402

if __name__ == "__main__":
    md = HERE / "PAPER_REVISED.md"
    if not md.exists():
        sys.exit(
            f"{md.name} is not in the repository yet: it is added once Chris has reviewed the revision"
        )
    # the checker reads the paper it is pointed at; figures resolve against theory/ as in the submitted build
    checker = ROOT / "theory/check_paper.py"
    src = f"__file__ = {str(checker)!r}\n" + checker.read_text().replace(
        'HERE / "PAPER_DRAFT.md"', f'Path("{md}")'
    )
    check = subprocess.run(
        [sys.executable, "-c", src], capture_output=True, text=True, cwd=ROOT / "theory"
    )
    if not check.stdout.strip():
        sys.exit(f"the checker printed nothing:\n{check.stderr}")
    print(check.stdout.strip().splitlines()[-1])
    if check.returncode:
        sys.exit("\n".join(line for line in check.stdout.splitlines() if line.startswith("FAIL")))
    build_paper.MD, build_paper.HTML, build_paper.PDF = (
        md,
        HERE / "PAPER_REVISED.html",
        HERE / "PAPER_REVISED.pdf",
    )
    build_paper.main(draft=False)
