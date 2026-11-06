"""
Wave-6 games (followup/WAVE6_PLAN.md; November 2026, not part of the submission): whether wave 5's price limit
keeps Opus 5.5's prices low after it is lifted, and whether its wording or its threat does the work. Each rule in
followup/rules6/ plays 10 games of 100 rounds (seeds 1-10) on Opus 5.5 with wave 2's settings, through
run_wave5.py's game runner.

    --check      feed every rule and wave 5's limit the same random prices and compare them; no games
    (default)    the 30 games; appends the time, the command and the SHA-256 of the plan, the code and the rules
                 to runs/wave6/launch.txt

Usage:  .venv/bin/python followup/run_wave6.py [--check] [--parallel 30] [--dry-run] [--config-dir ~/.claude]
"""

import argparse
import asyncio
import os
import random
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "followup")]
from platform_rules import NASH, check_source, load_rule  # noqa: E402
from run_wave5 import CODE, main, sha  # noqa: E402

OUT = ROOT / "followup/runs/wave6"
PLAN = ROOT / "followup/WAVE6_PLAN.md"
RULES = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "followup/rules6").glob("*.py"))
WAVE5_LIMIT = "followup/rules/r1_b_br_limit.py"
THREAT = f"; a price above it may be replaced by {NASH:.2f}."
NUM = re.compile(r"\d+\.\d\d")


def step(rule, t, prices):
    rule.round = t
    out = rule.override(t, dict(prices))
    return out, {f: rule.notice(f, out, {}) for f in out}


def check(seed: int = 0) -> bool:
    rng = random.Random(seed)
    rules = {load_rule(str(ROOT / r)).name: load_rule(str(ROOT / r)) for r in RULES}
    ok = all(not check_source(ROOT / r) for r in RULES)
    print(f"check_source: {'OK' if ok else 'FAIL'}")
    ref_cls = load_rule(str(ROOT / WAVE5_LIMIT))
    ref, ref_free = ref_cls(1), ref_cls(1)
    lifted, nothreat, estimate = (
        rules[n](1) for n in ("w6-lifted", "w6-limit-no-threat", "w6-estimate-threat")
    )
    fails, overrides = [], 0
    for t in range(1, 101):
        prices = {f: round(rng.uniform(1.3, 2.2), 2) for f in ("Firm A", "Firm B")}
        r_out, r_note = step(ref, t, prices)
        overrides += r_out != prices
        l_out, l_note = step(lifted, t, prices)
        if t < 50 and (l_out, l_note) != (r_out, r_note):
            fails.append(f"lifted differs from wave 5 in round {t}")
        if t == 50:
            want = {f: r_note[f].split("- Platform price limit")[0] for f in r_note}
            if l_out != r_out or any(
                not l_note[f].startswith(want[f]) or "limits have ended" not in l_note[f]
                for f in l_note
            ):
                fails.append("lifted round 50 wrong")
        if t > 50 and (l_out != prices or any(l_note.values())):
            fails.append(f"lifted acts in round {t}")
        n_out, n_note = step(nothreat, t, prices)
        ref_free.replaced, ref_free.round = {}, t
        want = {f: ref_free.notice(f, prices, {}).replace(THREAT, ".") for f in prices}
        if n_out != prices or n_note != want:
            fails.append(f"no-threat wrong in round {t}")
        e_out, e_note = step(estimate, t, prices)
        if e_out != r_out or any(NUM.findall(e_note[f]) != NUM.findall(r_note[f]) for f in e_note):
            fails.append(f"estimate differs from wave 5 in round {t}")
        if any("limit" in e_note[f] or "estimate" not in e_note[f] for f in e_note):
            fails.append(f"estimate wording wrong in round {t}")
    print(f"wave 5's rule overrode {overrides} of 100 random rounds")
    for f in fails[:10]:
        print(f)
    print("rule checks:", "OK" if not fails else f"FAIL ({len(fails)})")
    return ok and not fails and overrides > 0


def record():
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    files = CODE + ["followup/run_wave6.py", WAVE5_LIMIT] + RULES
    with open(OUT / "launch.txt", "a") as fh:
        fh.write(f"{stamp} games: {' '.join(sys.argv)}\n")
        fh.write(f"WAVE6_PLAN.md sha256 {sha(PLAN)}\n")
        fh.write(f"code sha256: {'; '.join(f'{c} {sha(ROOT / c)}' for c in files)}\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--parallel", type=int, default=30)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--config-dir", default=os.path.expanduser("~/.claude"))
    a = ap.parse_args()
    if a.check:
        sys.exit(0 if check() else 1)
    if len(RULES) != 3:
        sys.exit(f"expected three rules in followup/rules6/, found {RULES}")
    if not a.dry_run:
        if not check():
            sys.exit("rule checks failed")
        record()
    jobs = [("opus55", r, s, 100) for r in RULES for s in range(1, 11)]
    asyncio.run(main(jobs, OUT, a.parallel, a.config_dir, a.dry_run))
