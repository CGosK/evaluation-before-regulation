"""
Wave-7 games (followup/WAVE7_PLAN.md; November 2026, not part of the submission): wave 6's estimate line without
its threat, the matched cell of wave 6's wording-and-threat comparison. 10 games of 100 rounds (seeds 1-10) on
Opus 5.5 with wave 2's settings, through run_wave5.py's game runner.

    --check      feed the rule and w6-estimate-threat the same random prices and compare them; no games
    (default)    the 10 games; appends the time, the command and the SHA-256 of the plan, the code and the rule
                 to runs/wave7/launch.txt

Usage:  .venv/bin/python followup/run_wave7.py [--check] [--parallel 10] [--dry-run] [--config-dir ~/.claude]
"""

import argparse
import asyncio
import os
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "followup")]
from platform_rules import NASH, check_source, load_rule  # noqa: E402
from run_wave5 import CODE, main, sha  # noqa: E402

OUT = ROOT / "followup/runs/wave7"
PLAN = ROOT / "followup/WAVE7_PLAN.md"
RULE = "followup/rules7/estimate_no_threat.py"
WAVE6_ESTIMATE = "followup/rules6/estimate_threat.py"
THREAT = f"; a price above it may be replaced by {NASH:.2f}."


def check(seed: int = 0) -> bool:
    rng = random.Random(seed)
    ok = not check_source(ROOT / RULE)
    print(f"check_source: {'OK' if ok else 'FAIL'}")
    rule, ref = load_rule(str(ROOT / RULE))(1), load_rule(str(ROOT / WAVE6_ESTIMATE))(1)
    fails = []
    for t in range(1, 101):
        prices = {f: round(rng.uniform(1.3, 2.2), 2) for f in ("Firm A", "Firm B")}
        rule.round = ref.round = t
        out = rule.override(t, dict(prices))
        ref.replaced = {}
        want = {f: ref.notice(f, prices, {}).replace(THREAT, ".") for f in prices}
        got = {f: rule.notice(f, out, {}) for f in out}
        if out != prices or got != want or any(THREAT in w for w in want.values()):
            fails.append(f"round {t}")
    print("rule check:", "OK" if not fails else f"FAIL in {fails[:5]}")
    return ok and not fails


def record():
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    files = CODE + ["followup/run_wave7.py", WAVE6_ESTIMATE, RULE]
    with open(OUT / "launch.txt", "a") as fh:
        fh.write(f"{stamp} games: {' '.join(sys.argv)}\n")
        fh.write(f"WAVE7_PLAN.md sha256 {sha(PLAN)}\n")
        fh.write(f"code sha256: {'; '.join(f'{c} {sha(ROOT / c)}' for c in files)}\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--parallel", type=int, default=10)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--config-dir", default=os.path.expanduser("~/.claude"))
    a = ap.parse_args()
    if a.check:
        sys.exit(0 if check() else 1)
    if not a.dry_run:
        if not check():
            sys.exit("rule check failed")
        record()
    jobs = [("opus55", RULE, s, 100) for s in range(1, 11)]
    asyncio.run(main(jobs, OUT, a.parallel, a.config_dir, a.dry_run))
