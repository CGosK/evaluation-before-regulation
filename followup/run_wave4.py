"""
Fourth wave of follow-up games (November 2026, after the sprint review; not part of the submission), as fixed in
followup/WAVE4_PLAN.md. Calls go through headless Claude Code on the subscription login, with wave 2's settings.

    --part 1  the paper's forced-deviation test, succession/frontier.py unchanged, on Opus 5.5 and Sonnet 5.5:
              8 sources, 3 settling rounds, 12-round control, deviate and hidden arms
    --part 2  10 Opus 5.5 games of followup/duopoly_followup.py with hidden rival prices from round 1
    --check   the checks before launch, in runs/wave4/checks/ (not results): the 8 sources are the paper's,
              a 1-source 1-round frontier pilot on Haiku 4.5 forces Firm B in the deviate arm, and a 3-round
              hidden-prices game on Haiku 4.5 shows no rival price

A real launch appends the time, the command and the SHA-256 of the plan and the code to runs/wave4/launch.txt.
A finished part-1 run gets "✅ done" appended to its log, so followup/usage_guard.py counts it with the games.

Usage:  .venv/bin/python followup/run_wave4.py --part 1 2 [--dry-run]
        .venv/bin/python followup/run_wave4.py --check
Writes: followup/runs/wave4/{launch.txt,logs/,frontier/<family>/,games/2_agents/,usage.jsonl}
"""

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "followup"), str(ROOT / "succession")]
from prevention45 import active, done  # noqa: E402
from run_wave2 import FAMILIES  # noqa: E402

OUT = ROOT / "followup/runs/wave4"
PLAN = ROOT / "followup/WAVE4_PLAN.md"
CODE = [
    "followup/duopoly_followup.py",
    "followup/run_wave4.py",
    "followup/run_wave2.py",
    "followup/usage_guard.py",
    "experiments_synthetic/common.py",
    "succession/frontier.py",
    "succession/branch.py",
]
PAPER_SOURCES = ROOT / "succession/runs/frontier/haiku45"
TEST = ["--settle", "3", "--rounds", "12", "--arms", "control", "deviate", "hidden"]
CALL_COST = {
    "opus55": "0.06",
    "sonnet55": "0.025",
    "haiku45": "0.01",
}  # frontier.py's per-source reserve


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def environment(family: str, config_dir: str, **extra) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_EFFORT", "CLAUDE_USAGE_LOG")}
    env.update(
        LLM_PROVIDER="claude-code",
        CLAUDE_THINKING_BUDGET="0",
        MAX_THINKING_TOKENS="0",
        CLAUDE_CONFIG_DIR=config_dir,
        **extra,
    )
    env.setdefault("CLAUDE_PAUSE_FILE", str(OUT / "pause.json"))
    effort = FAMILIES[family][1]
    if effort:
        env["CLAUDE_EFFORT"] = effort
    return env


async def run(cmd: list, env: dict, log: Path) -> int:
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a") as fh:
        proc = await asyncio.create_subprocess_exec(*cmd, cwd=ROOT, env=env, stdout=fh, stderr=fh)
        return await proc.wait()


def frontier_cmd(family: str, out: Path, sources: int, settle_rounds: list) -> list:
    model, effort, _ = FAMILIES[family]
    return [
        str(ROOT / ".venv/bin/python"),
        "succession/frontier.py",
        "--model",
        model,
        *(["--effort", effort] if effort else []),
        "--sources",
        str(sources),
        *settle_rounds,
        "--budget-usd",
        "1000",
        "--call-cost-usd",
        CALL_COST[family],
        "--parallel",
        "8",
        "--out",
        str(out),
        "-y",
    ]


def complete(out: Path, n: int = 8) -> bool:
    stems = [f.stem.rsplit("_", 1) for f in out.glob("*.jsonl") if f.name != "usage.jsonl"]
    sources = {s for s, a in stems}
    arms = {s: {a for t, a in stems if t == s} for s in sources}
    return sum({"settle", "control", "deviate", "hidden"} <= a for a in arms.values()) >= n


async def part1(family: str, config_dir: str, dry: bool) -> str:
    out = OUT / "frontier" / family
    log = OUT / "logs" / f"frontier_{family}.txt"
    cmd = frontier_cmd(family, out, 8, TEST)
    if dry:
        return f"{family} test: {' '.join(cmd[1:])}"
    if done(log):
        return f"{family} test: already done"
    code = await run(cmd, environment(family, config_dir), log)
    if code == 0 and complete(out):
        with open(log, "a") as fh:
            fh.write("✅ done\n")
        return f"{family} test: done"
    return f"{family} test: FAILED (exit {code})"


def game_cmd(family: str, arm: str, seed: int, rounds: int) -> list:
    model, _, strategy = FAMILIES[family]
    return [
        str(ROOT / ".venv/bin/python"),
        "followup/duopoly_followup.py",
        "--followup-arm",
        arm,
        *(["--followup-strategy", strategy] if strategy else []),
        "--mechanism",
        "hidden",
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


async def part2_game(seed: int, sem, config_dir: str, dry: bool) -> str:
    log = OUT / "logs" / f"opus55_hidden_s{seed}.txt"
    cmd = game_cmd("opus55", "hidden", seed, 100)
    if dry:
        return f"opus55 hidden s{seed}: {' '.join(cmd[1:])}"
    if done(log):
        return f"opus55 hidden s{seed}: already done"
    if active(log):
        async with sem:
            while active(log):
                await asyncio.sleep(20)
        return f"opus55 hidden s{seed}: {'done' if done(log) else 'STALLED (adopted)'}"
    env = environment(
        "opus55",
        config_dir,
        CLAUDE_USAGE_LOG=str(OUT / "usage.jsonl"),
        FOLLOWUP_GAMES=str(OUT / "games"),
        FOLLOWUP_FAMILY="opus55",
    )
    async with sem:
        log.unlink(missing_ok=True)
        code = await run(cmd, env, log)
    return f"opus55 hidden s{seed}: {'done' if done(log) else f'FAILED (exit {code})'}"


async def main(parts: list, parallel: int, config_dir: str, dry: bool):
    sem = asyncio.Semaphore(parallel)
    tasks = []
    if 1 in parts:
        tasks += [part1(f, config_dir, dry) for f in ("opus55", "sonnet55")]
    if 2 in parts:
        tasks += [part2_game(s, sem, config_dir, dry) for s in range(1, 11)]
    for t in asyncio.as_completed([asyncio.ensure_future(t) for t in tasks]):
        print(await t, flush=True)


async def check(config_dir: str) -> bool:
    from branch import eligible_thesis_games

    ok = True
    pool = eligible_thesis_games(200, 0.3)
    ours = sorted(str(s["experiment_timestamp"][0]) for s in pool[:8])
    paper = sorted({f.stem.rsplit("_", 1)[0] for f in PAPER_SOURCES.glob("*_control.jsonl")})
    same = ours == paper
    print(f"sources: {ours} ({len(pool)} eligible); the paper's: {'same' if same else paper}")
    ok &= same

    checks = OUT / "checks"
    pilot = checks / "frontier"
    one_round = ["--settle", "1", "--rounds", "1", "--arms", "control", "deviate", "hidden"]
    cmd = frontier_cmd("haiku45", pilot, 1, one_round)
    await run(cmd, environment("haiku45", config_dir), checks / "logs/frontier.txt")
    dev = [json.loads(line) for f in pilot.glob("*_deviate.jsonl") for line in f.open()]
    forced = {r["firm"] for r in dev if str(r.get("forced")) == "True"}
    arms = {f.stem.rsplit("_", 1)[1] for f in pilot.glob("*.jsonl") if f.name != "usage.jsonl"}
    print(f"frontier pilot: arms {sorted(arms)}, forced firms in deviate {sorted(forced)}")
    ok &= {"settle", "control", "deviate", "hidden"} <= arms and forced == {"Firm B"}

    env = environment(
        "haiku45",
        config_dir,
        CLAUDE_USAGE_LOG=str(checks / "usage.jsonl"),
        FOLLOWUP_GAMES=str(checks / "games"),
        FOLLOWUP_FAMILY="haiku45",
    )
    await run(game_cmd("haiku45", "hidden", 1, 3), env, checks / "logs/hidden.txt")
    games = sorted((checks / "games/2_agents").glob("*_haiku45_hidden_*/results.json"))
    if games:
        res = json.loads(games[-1].read_text())
        shown = [
            t for firm in res.values() for t, o in firm.items() if "Competitor" in o["market_data"]
        ]
        rounds = len(next(iter(res.values())))
        print(f"hidden game: {rounds} rounds, rounds showing a rival price: {shown or 'none'}")
        ok &= rounds == 3 and not shown
    else:
        print("hidden game: no game written")
        ok = False
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--part", type=int, nargs="+", choices=[1, 2])
    ap.add_argument("--check", action="store_true", help="run the checks before launch")
    ap.add_argument("--parallel", type=int, default=20, help="part-2 games at a time")
    ap.add_argument("--dry-run", action="store_true", help="print the commands only")
    ap.add_argument(
        "--config-dir",
        default=os.path.expanduser("~/.claude"),
        help="Claude Code config root whose login pays for the calls",
    )
    a = ap.parse_args()
    if a.check:
        sys.exit(0 if asyncio.run(check(a.config_dir)) else 1)
    if not a.part:
        sys.exit("--part 1, --part 2, --part 1 2 or --check")
    if not a.dry_run:
        (OUT / "logs").mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        code = "; ".join(f"{c} {sha(ROOT / c)}" for c in CODE)
        with open(OUT / "launch.txt", "a") as fh:
            fh.write(f"{stamp} parts {a.part}: {' '.join(sys.argv)}\n")
            fh.write(f"WAVE4_PLAN.md sha256 {sha(PLAN)}\ncode sha256: {code}\n")
    asyncio.run(main(a.part, a.parallel, a.config_dir, a.dry_run))
