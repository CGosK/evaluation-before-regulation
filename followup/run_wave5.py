"""
Wave-5 games (followup/WAVE5_PLAN.md; November 2026, not part of the submission): an automated search for a
platform rule that brings Claude Opus 5.5 to competitive prices, then a confirmation. Every game is a P1 duopoly
of followup/platform_game.py through headless Claude Code on the subscription login, with wave 2's settings.

    --check-known        each known rule in a 21-round Haiku 4.5 game, in runs/wave5/checks/ (not results):
                         forced rounds, cut prices, the rival line and the best-response line where expected
    --screen RULE ...    each rule (a known name or a rule file) in 3 games of 60 rounds, seeds 1-3
    --confirm            the two rules frozen in followup/WAVE5_CONFIRM.md ("rule: <file>" lines), 10 games
                         of 100 rounds each, seeds 1-10

Screening and confirmation launches append the time, the command and the SHA-256 of the plan, the code, the
rule files and (for --confirm) WAVE5_CONFIRM.md to runs/wave5/launch.txt.

Usage:  .venv/bin/python followup/run_wave5.py --screen followup/rules/r1_a.py ... [--dry-run]
"""

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "followup"), str(ROOT / "succession")]
from platform_rules import KNOWN, NASH, load_rule  # noqa: E402
from prevention45 import active, done  # noqa: E402
from run_wave2 import FAMILIES  # noqa: E402

OUT = ROOT / "followup/runs/wave5"
PLAN = ROOT / "followup/WAVE5_PLAN.md"
CONFIRM = ROOT / "followup/WAVE5_CONFIRM.md"
CODE = [
    "followup/platform_rules.py",
    "followup/platform_game.py",
    "followup/run_wave5.py",
    "followup/run_wave2.py",
    "followup/usage_guard.py",
    "experiments_synthetic/common.py",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def play(family, rule, seed, rounds, out, sem, config_dir, dry) -> str:
    model, effort, _ = FAMILIES[family]
    name = load_rule(rule).name
    log = out / "logs" / f"{name}_s{seed}.txt"
    cmd = [
        str(ROOT / ".venv/bin/python"),
        "followup/platform_game.py",
        "--rule",
        rule,
        "--provider",
        "claude-code",
        "--model",
        model,
        "--rounds",
        str(rounds),
        "--seeds",
        str(seed),
        "--plot-every",
        "0",
        "-y",
    ]
    if dry:
        return f"{name} s{seed}: {' '.join(cmd[1:])}"
    if done(log):
        return f"{name} s{seed}: already done"
    if active(log):
        async with sem:
            while active(log):
                await asyncio.sleep(20)
        return f"{name} s{seed}: {'done' if done(log) else 'STALLED (adopted)'}"
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_EFFORT"}
    env.update(
        CLAUDE_THINKING_BUDGET="0",
        MAX_THINKING_TOKENS="0",
        CLAUDE_USAGE_LOG=str(out / "usage.jsonl"),
        CLAUDE_CONFIG_DIR=config_dir,
        FOLLOWUP_GAMES=str(out / "games"),
        FOLLOWUP_FAMILY=family,
    )
    env.setdefault("CLAUDE_PAUSE_FILE", str(OUT / "pause.json"))
    if effort:
        env["CLAUDE_EFFORT"] = effort
    log.parent.mkdir(parents=True, exist_ok=True)
    async with sem:
        with open(log, "w") as fh:
            proc = await asyncio.create_subprocess_exec(
                *cmd, cwd=ROOT, env=env, stdout=fh, stderr=fh
            )
            code = await proc.wait()
    return f"{name} s{seed}: {'done' if done(log) else f'FAILED (exit {code})'}"


async def main(jobs: list, out: Path, parallel: int, config_dir: str, dry: bool):
    sem = asyncio.Semaphore(parallel)
    tasks = [asyncio.ensure_future(play(*j, out, sem, config_dir, dry)) for j in jobs]
    for t in asyncio.as_completed(tasks):
        print(await t, flush=True)


def check_known(out: Path) -> bool:
    expect = {
        "none": dict(forced=[], rival=True, br=False),
        "brinfo": dict(forced=[], rival=True, br=True),
        "cut10": dict(forced=[20], rival=True, br=False, cut=0.10),
        "forced10": dict(forced=[20], rival=True, br=False, nash=True),
        "forced5": dict(forced=[15, 20], rival=True, br=False, nash=True),
        "hidden": dict(forced=[], rival=False, br=False),
    }
    ok = True
    for name, want in expect.items():
        found = sorted((out / "games/2_agents").glob(f"*_haiku45_rule-{name}_*/results.json"))
        if not found:
            print(f"{name}: no game")
            ok = False
            continue
        res = json.loads(found[-1].read_text())
        rows = [(int(t), firm, o) for firm, r in res.items() for t, o in r.items()]
        forced = sorted({t for t, _, o in rows if o.get("forced")})
        later = [o["market_data"] for t, _, o in rows if t >= 2]
        rival = all("Competitor" in m for m in later)
        hidden = not any("Competitor" in m for m in later)
        br = all("Platform estimate" in m for m in later)
        good = forced == want["forced"] and (rival if want["rival"] else hidden)
        good &= br == want["br"]
        for t, _, o in rows:
            if o.get("forced") and want.get("nash"):
                good &= abs(o["chosen_price"] - NASH) < 1e-9
            if o.get("forced") and want.get("cut"):
                good &= abs(o["chosen_price"] - max(1.0, o["model_price"] * 0.9)) < 1e-9
        print(
            f"{name}: forced rounds {forced}, rival line {'shown' if rival else 'hidden' if hidden else 'MIXED'}, "
            f"best-response line {br}: {'OK' if good else 'FAIL'}"
        )
        ok &= good
    return ok


def record(mode: str, rules: list):
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    files = CODE + [r for r in rules if r not in KNOWN]
    code = "; ".join(f"{c} {sha(ROOT / c)}" for c in files)
    with open(OUT / "launch.txt", "a") as fh:
        fh.write(f"{stamp} {mode}: {' '.join(sys.argv)}\n")
        fh.write(f"WAVE5_PLAN.md sha256 {sha(PLAN)}\n")
        if mode == "confirm":
            fh.write(f"WAVE5_CONFIRM.md sha256 {sha(CONFIRM)}\n")
        fh.write(f"code sha256: {code}\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check-known", action="store_true")
    ap.add_argument("--screen", nargs="+", metavar="RULE")
    ap.add_argument("--confirm", action="store_true")
    ap.add_argument("--parallel", type=int, default=20)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--config-dir", default=os.path.expanduser("~/.claude"))
    a = ap.parse_args()
    if a.check_known:
        out = OUT / "checks"
        jobs = [("haiku45", name, 1, 21) for name in KNOWN]
        asyncio.run(main(jobs, out, 6, a.config_dir, a.dry_run))
        sys.exit(0 if a.dry_run or check_known(out) else 1)
    if a.screen:
        names = [load_rule(r).name for r in a.screen]
        if len(set(names)) != len(names):
            sys.exit(f"rule names must be unique: {names}")
        if not a.dry_run:
            record("screen", a.screen)
        jobs = [("opus55", r, s, 60) for r in a.screen for s in (1, 2, 3)]
        asyncio.run(main(jobs, OUT / "screen", a.parallel, a.config_dir, a.dry_run))
    elif a.confirm:
        rules = re.findall(r"^rule: (\S+)", CONFIRM.read_text(), re.M)
        if len(rules) != 2:
            sys.exit(f"WAVE5_CONFIRM.md must name exactly two rules, found {rules}")
        if not a.dry_run:
            record("confirm", rules)
        jobs = [("opus55", r, s, 100) for r in rules for s in range(1, 11)]
        asyncio.run(main(jobs, OUT / "confirm", a.parallel, a.config_dir, a.dry_run))
    else:
        sys.exit("--check-known, --screen RULE ... or --confirm")
