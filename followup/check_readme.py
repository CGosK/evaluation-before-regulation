"""
Checks the numbers in the follow-up README.md, as check_followup.py does for the note, in two layers:

    source pools   every decimal and percentage in a section must match, at the precision printed, a value in
                   that section's saved outputs (out/*.json, the paper's outputs it cites) or a value recomputed
                   here from the saved games. Catches any number with nothing behind it.
    exact rows     the main results tables are rebuilt from the outputs and must appear row for row. Catches a
                   right value in the wrong cell.

Not covered: counts read by hand from the agents' notes, prices quoted from the notes, and integers (games,
rounds, seeds, counts of n), which the exact rows cover where they matter. Model versions, section references,
code, links and the fixed constants of the game are skipped.

Usage:  uv run --extra analysis python followup/check_readme.py
Exits 1 if any check fails or any number has no source.
"""

import json
import re
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "theory")]
OUT = HERE / "out"
TEXT = (HERE / "README.md").read_text()
NUM = re.compile(r"(?<![\w.])[−+]?\d+(?:\.\d+)?%?")
CONSTANTS = {
    "1.47",
    "1.473",
    "1.48",
    "1.925",
    "0.3",
    "0.1",
    "0.05",
    "0.5",
    "1%",
    "5%",
    "10%",
    "20%",
    "100%",
}
CONSTANTS |= {
    "4.51",
    "1.0",
    "1.10",
    "95%",
}  # top willingness to pay, cost, the forced raise, CI level
NOT_RESULTS = [
    r"\]\([^)]*\)|`[^`]*`|#[\w-]+",  # links, code, anchors
    r"\b(?:Haiku|Opus|Sonnet|Fable) \d\.\d\b",  # model versions
    r"§\s?\d+(?:\.\d+)*",  # section references
    r'"[^"\n]*"',  # agents' notes, quoted verbatim
]


def load(name: str):
    return json.loads((OUT / name).read_text())


def leaves(d):
    if isinstance(d, dict):
        for v in d.values():
            yield from leaves(v)
    elif isinstance(d, (list, tuple)):
        for v in d:
            yield from leaves(v)
    elif isinstance(d, (int, float)) and not isinstance(d, bool):
        yield float(d)


def forms(v: float) -> set:
    """The ways the README might print a value: 0-3 decimals, signed or not, and as a percentage."""
    out = set()
    for x in (v, -v):
        for d in (0, 1, 2, 3, 4):
            s = f"{x:.{d}f}"
            out |= {s, s.replace("-", "−"), "+" + s if x >= 0 else s.replace("-", "−")}
        if abs(x) <= 1.5:
            for d in (0, 1):
                p = f"{100 * x:.{d}f}%"
                out |= {p, p.replace("-", "−"), "+" + p if x >= 0 else p.replace("-", "−")}
        for d in (0, 1):
            p = f"{x:.{d}f}%"
            out |= {p, p.replace("-", "−"), "+" + p if x >= 0 else p.replace("-", "−")}
    return {s.replace("−0.00", "0.00") for s in out} | out


def pool(*sources) -> set:
    vals = set()
    for s in sources:
        for v in leaves(s):
            vals |= forms(v)
    return vals


def sections() -> list:
    parts = re.split(r"\n(?=## )", TEXT)
    return [(p.splitlines()[0].lstrip("# ").strip(), p) for p in parts]


results = []
unsourced = []


def check(label: str, text: str):
    ok = text in TEXT
    results.append(ok)
    print(f"{'ok  ' if ok else 'FAIL'} {label}: {text}")


# ---------------------------------------------------------------- sources for each section
import extras_readme as ex  # noqa: E402

SOURCES = ex.sources()
COMPUTED = ex.computed()

for title, body in sections():
    key = next((k for k in SOURCES if title.startswith(k)), None)
    allowed = (
        CONSTANTS
        | pool(*(SOURCES[key] if key else []), COMPUTED.get(key, []))
        | pool(*SOURCES["*"])
    )
    body_wo_links = body
    for pattern in NOT_RESULTS:
        body_wo_links = re.sub(pattern, "", body_wo_links)
    for m in NUM.finditer(body_wo_links):
        tok = m.group(0)
        if "." not in tok and "%" not in tok:
            continue
        if tok not in allowed and tok.lstrip("+−") not in allowed:
            ctx = body_wo_links[max(0, m.start() - 60) : m.end() + 20].replace("\n", " ")
            unsourced.append((title, tok, ctx))

LINES = TEXT.splitlines()
for row_label, row in ex.exact_rows():
    if isinstance(row, tuple):  # (start, end) of a row whose middle is prose
        ok = any(line.startswith(row[0]) and line.endswith(row[1]) for line in LINES)
        results.append(ok)
        print(f"{'ok  ' if ok else 'FAIL'} {row_label}: {row[0]} … {row[1]}")
    elif isinstance(row, list):  # these row starts appear in this order
        at = [next((i for i, line in enumerate(LINES) if line.startswith(h)), -1) for h in row]
        ok = -1 not in at and at == sorted(at)
        results.append(ok)
        print(f"{'ok  ' if ok else 'FAIL'} {row_label}")
    else:
        check(row_label, row)

print(f"\n{sum(results)} of {len(results)} exact row checks pass")
if unsourced:
    print(f"\n{len(unsourced)} numbers with no source in their section:")
    for title, tok, ctx in unsourced:
        print(f"  [{title[:40]}] {tok:>8}  …{ctx.strip()}…")
else:
    print("every decimal and percentage has a source in its section")
sys.exit(0 if all(results) and not unsourced else 1)
