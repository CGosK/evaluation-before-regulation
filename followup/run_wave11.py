"""
Wave-11 games (study 2, followup/WAVE11_PLAN.md; not part of the submission): posted limits beyond Opus 5.5.
100-round games through followup/platform_game.py with wave 2's settings, all arms interleaved:

    A          Sonnet 5.5 under wave 6's limit with no threat (rules6/limit_no_threat.py), seeds 1-10
    B          Haiku 5.5 under a fixed cap of 1.74 (rules11/cap_fixed.py), seeds 1-10
    C          Sonnet 5.5 under the same cap, seeds 1-20
    baselines  Sonnet 5.5 and Haiku 5.5 with no rule, seeds 11-15 each, alongside wave 2's 10 each

    --check        no calls: the cap rule against random prices, check_source on both rules, the limit rule's hash
                   against runs/wave6/launch.txt, and the job list
    --check-game   one 6-round Haiku 4.5 game under the cap in runs/wave11/checks/ (not a result): the limit line
                   from round 2, and every price above 1.74 replaced by 1.74 with a notice; records the hashes too
    (default)      the games; appends the time, the command and the SHA-256 of the plan and the code to
                   runs/wave11/launch.txt

Run the usage guard alongside:  usage_guard.py --runs followup/runs/wave11 --games 50
Usage:  .venv/bin/python followup/run_wave11.py [--check | --check-game] [--parallel 15] [--dry-run]
            [--config-dir ~/.claude]
"""

import argparse
import asyncio
import json
import os
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "followup"), str(ROOT / "succession")]
from platform_rules import check_source, load_rule  # noqa: E402
from prevention45 import active, done  # noqa: E402
from run_wave2 import FAMILIES  # noqa: E402
from run_wave5 import sha  # noqa: E402

OUT = ROOT / "followup/runs/wave11"
PLAN = ROOT / "followup/WAVE11_PLAN.md"
LIMIT = "followup/rules6/limit_no_threat.py"
CAP = "followup/rules11/cap_fixed.py"
LIMIT_SHA = "e658a5557f62c956ff3c13fc311bad31fbb91331fe04d73d9b755a47bff1b3a3"
ARMS = [
    ("A", "sonnet55", LIMIT, range(1, 11)),
    ("B", "haiku55", CAP, range(1, 11)),
    ("C", "sonnet55", CAP, range(1, 21)),
    ("sonnet_baseline", "sonnet55", "none", range(11, 16)),
    ("haiku_baseline", "haiku55", "none", range(11, 16)),
]
CODE = [
    "followup/platform_rules.py",
    "followup/platform_game.py",
    "followup/run_wave2.py",
    "followup/run_wave5.py",
    "followup/run_wave11.py",
    "followup/wave11_results.py",
    "followup/usage_guard.py",
    "experiments_synthetic/common.py",
    LIMIT,
    CAP,
]


def jobs() -> list:
    """Every game, interleaved: the first game of each arm, then the second, and so on."""
    queues = [[(arm, fam, rule, s) for s in seeds] for arm, fam, rule, seeds in ARMS]
    out = []
    while any(queues):
        out += [q.pop(0) for q in queues if q]
    return out


def check(seed: int = 0) -> bool:
    rng = random.Random(seed)
    cap = load_rule(str(ROOT / CAP))(1)
    fails = []
    for t in range(1, 201):
        prices = {f: round(rng.uniform(1.3, 2.2), 2) for f in ("Firm A", "Firm B")}
        cap.round = t
        out = cap.override(t, dict(prices))
        for f, p in prices.items():
            want = min(p, 1.74)
            line = cap.notice(f, out, {})
            told = "Platform notice: my price of" in line
            if (
                out[f] != want
                or told != (p > 1.74)
                or "Platform price limit for my next price: 1.74." not in line
            ):
                fails.append(f"round {t} {f}")
    ok_rule = not fails
    ok_src = not check_source(ROOT / CAP) and not check_source(ROOT / LIMIT)
    ok_sha = sha(ROOT / LIMIT) == LIMIT_SHA
    n = len(jobs())
    print(f"cap rule: {'OK' if ok_rule else f'FAIL in {fails[:5]}'}")
    print(f"check_source on both rules: {'OK' if ok_src else 'FAIL'}")
    print(f"limit rule unchanged since wave 6: {'OK' if ok_sha else 'FAIL'}")
    print(f"jobs: {n} games, {n * 200:,} calls; first six: {[j[:2] + (j[3],) for j in jobs()[:6]]}")
    return ok_rule and ok_src and ok_sha and n == 50


def check_game_ok() -> bool:
    found = sorted((OUT / "checks/games/2_agents").glob("*_rule-w11-cap174_*/results.json"))
    if not found:
        print("check game: none found")
        return False
    res = json.loads(found[-1].read_text())
    rows = [(int(t), o) for r in res.values() for t, o in r.items()]
    line = all("Platform price limit for my next price: 1.74." in o["market_data"] for _, o in rows)
    clipped = [(t, o) for t, o in rows if o.get("forced")]
    clip_ok = all(o["chosen_price"] == 1.74 and o["model_price"] > 1.74 for _, o in clipped)
    told = all("Platform notice" in o["market_data"] for _, o in clipped)
    above = [o for _, o in rows if not o.get("forced") and o["chosen_price"] > 1.74]
    print(
        f"check game: limit line every round {line}; {len(clipped)} clipped, all to 1.74 {clip_ok}, "
        f"all told {told}; unclipped prices above 1.74: {len(above)}"
    )
    return line and clip_ok and told and not above


def env_for(family: str, config_dir: str, games: Path) -> dict:
    _, effort, _ = FAMILIES[family]
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_EFFORT"}
    env.update(
        CLAUDE_THINKING_BUDGET="0",
        MAX_THINKING_TOKENS="0",
        CLAUDE_USAGE_LOG=str(OUT / "usage.jsonl"),
        CLAUDE_CONFIG_DIR=config_dir,
        CLAUDE_PAUSE_FILE=str(OUT / "pause.json"),
        FOLLOWUP_GAMES=str(games),
        FOLLOWUP_FAMILY=family,
    )
    if effort:
        env["CLAUDE_EFFORT"] = effort
    return env


async def play(arm, family, rule, seed, rounds, games, sem, config_dir, dry) -> str:
    log = OUT / "logs" / f"{arm}_{family}_s{seed}.txt"
    model = FAMILIES[family][0]
    cmd = [str(ROOT / ".venv/bin/python"), "followup/platform_game.py", "--rule", rule]
    cmd += ["--provider", "claude-code", "--model", model, "--rounds", str(rounds)]
    cmd += ["--seeds", str(seed), "--plot-every", "0", "-y"]
    if dry:
        return f"{arm} {family} s{seed}: {' '.join(cmd[1:])}"
    if done(log):
        return f"{arm} {family} s{seed}: already done"
    if active(log):
        return f"{arm} {family} s{seed}: still running elsewhere"
    log.parent.mkdir(parents=True, exist_ok=True)
    async with sem:
        with open(log, "w") as fh:
            proc = await asyncio.create_subprocess_exec(
                *cmd, cwd=ROOT, env=env_for(family, config_dir, games), stdout=fh, stderr=fh
            )
            code = await proc.wait()
    return f"{arm} {family} s{seed}: {'done' if done(log) else f'FAILED (exit {code})'}"


async def main(todo, rounds, games, parallel, config_dir, dry):
    sem = asyncio.Semaphore(parallel)
    tasks = [asyncio.ensure_future(play(*j, rounds, games, sem, config_dir, dry)) for j in todo]
    for t in asyncio.as_completed(tasks):
        print(await t, flush=True)


def record(mode: str):
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(OUT / "launch.txt", "a") as fh:
        fh.write(f"{stamp} {mode}: {' '.join(sys.argv)}\n")
        fh.write(f"WAVE11_PLAN.md sha256 {sha(PLAN)}\n")
        fh.write(f"code sha256: {'; '.join(f'{c} {sha(ROOT / c)}' for c in CODE)}\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--check-game", action="store_true")
    ap.add_argument("--parallel", type=int, default=15)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--config-dir", default=os.path.expanduser("~/.claude"))
    a = ap.parse_args()
    if a.check:
        sys.exit(0 if check() else 1)
    if a.check_game:
        if not check():
            sys.exit("check failed")
        if not a.dry_run:
            record("check game")
        job = [("check", "haiku45", CAP, 1)]
        asyncio.run(main(job, 6, OUT / "checks/games", 1, a.config_dir, a.dry_run))
        sys.exit(0 if a.dry_run or check_game_ok() else 1)
    if not a.dry_run:
        if not PLAN.exists():
            sys.exit("no plan: WAVE11_PLAN.md must be written before any game runs")
        if not check():
            sys.exit("check failed")
        if not check_game_ok():
            sys.exit("run --check-game first")
        record("games")
    asyncio.run(main(jobs(), 100, OUT / "games", a.parallel, a.config_dir, a.dry_run))
