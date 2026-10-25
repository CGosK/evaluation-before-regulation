"""
Prevention experiment on Claude Haiku 4.5, the Claude model that forms high prices on its own (screen:
succession/runs/screen). Every arm is a fresh 100-round P1 duopoly with the remedy on from round 1, played
through headless Claude Code on the subscription (--provider claude-code), extended thinking off unless the
arm says otherwise. Seeds 11-20 of baseline, nashopen10 and reset50 were added after the first 84 games, to
settle those arms. The pre-set outcome is the market collusion index over rounds 51-100.

    baseline    no remedy (seeds 5-20; the screen's seeds 1-4 are the same game up to round 100)
    p2          the P2 prompt
    forced10    every 10 rounds after round 10, one firm at random is held at Nash for that round
    nashopen10  both firms held at Nash for rounds 1-10 (seeds 1-20)
    brinfo      the platform reports each firm's best response to its rival's price
    rpe         relative-performance pay: each firm is scored on its profit minus its rival's
    hidden      rivals' prices removed from market data
    reset50     at round 50 both firms restart with no history and default notes (seeds 1-20)
    think4096   extended thinking on, 4,096-token budget (seeds 3-10; the screen has seeds 1-2)

Games run --parallel at a time in seed-major order, so a partial run stays balanced across arms. A game whose
log already ends in "done" is skipped, so rerunning resumes. A game whose log was written in the last 3 minutes
is taken to be running under an earlier launcher: it holds a slot until it finishes, and is not started again.

Calls run on the Claude login in --config-dir (default ~/.claude, Chris's personal account, as the
claude-personal shortcut uses); with CLAUDE_CONFIG_DIR unset, Claude Code falls back to the machine's default
login, which is a different account.

With --firms 4 it runs the generalisation to Lee's (2026) four-firm market instead: baseline, forced10 and
brinfo, seeds 1-10, written to succession/runs/prevention45_4firm.

Calls stop at the plan allowance: CLAUDE_PAUSE_FILE (default <out>/pause.json) pauses every game when a call
hits a usage limit or is paid from usage credits (src/agents/llm_providers.py).

Usage:  .venv/bin/python succession/prevention45.py [--firms 2|4] [--parallel 16] [--config-dir ~/.claude] [--dry-run]
Writes: <out>/logs/<arm>_s<seed>.txt, <out>/usage.jsonl; games in experiments_synthetic/experiments_runs/<n>_agents/
"""

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "succession/runs/prevention45"
SCRIPT = "experiments_synthetic/duopoly.py"
ARMS = {
    "baseline": ([], 0, range(5, 21)),
    "p2": (["--prompts", "P2"], 0, range(1, 11)),
    "forced10": (["--forced-every", "10"], 0, range(1, 11)),
    "nashopen10": (["--nash-open", "10"], 0, range(1, 21)),
    "brinfo": (["--mechanism", "brinfo"], 0, range(1, 11)),
    "rpe": (["--mechanism", "rpe"], 0, range(1, 11)),
    "hidden": (["--mechanism", "hidden"], 0, range(1, 11)),
    "reset50": (["--memory-reset", "50"], 0, range(1, 21)),
    "think4096": ([], 4096, range(3, 11)),
}
ARMS_4FIRM = {
    "baseline": ([], 0, range(1, 11)),
    "forced10": (["--forced-every", "10"], 0, range(1, 11)),
    "brinfo": (["--mechanism", "brinfo"], 0, range(1, 11)),
}


def games() -> list:
    """(arm, seed, args, thinking budget) in seed-major order."""
    out = [(arm, s, args, budget) for arm, (args, budget, seeds) in ARMS.items() for s in seeds]
    return sorted(out, key=lambda g: (g[1], list(ARMS).index(g[0])))


def done(log: Path) -> bool:
    return log.exists() and "✅ done" in log.read_text(errors="replace")


def active(log: Path) -> bool:
    return log.exists() and not done(log) and time.time() - log.stat().st_mtime < 180


async def play(arm: str, seed: int, args: list, budget: int, sem: asyncio.Semaphore, dry: bool,
               config_dir: str) -> str:
    log = OUT / "logs" / f"{arm}_s{seed}.txt"
    if done(log):
        return f"{arm} s{seed}: already done"
    if active(log) and not dry:
        async with sem:  # running under an earlier launcher: hold its slot until it ends
            while active(log):
                await asyncio.sleep(20)
        return f"{arm} s{seed}: {'done' if done(log) else 'STALLED (adopted)'}"
    cmd = [str(ROOT / ".venv/bin/python"), SCRIPT, "--provider", "claude-code",
           "--model", "claude-haiku-4-5", "--rounds", "100", "--seeds", str(seed), *args,
           "--plot-every", "0", "-y"]
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_EFFORT"}  # Haiku 4.5 has no effort setting
    env.update(CLAUDE_THINKING_BUDGET=str(budget), CLAUDE_USAGE_LOG=str(OUT / "usage.jsonl"),
               CLAUDE_CONFIG_DIR=config_dir)
    env.setdefault("CLAUDE_PAUSE_FILE", str(OUT / "pause.json"))
    if dry:
        return f"{arm} s{seed}: CLAUDE_THINKING_BUDGET={budget} {' '.join(cmd[1:])}"
    async with sem:
        with open(log, "w") as fh:
            proc = await asyncio.create_subprocess_exec(*cmd, cwd=ROOT, env=env, stdout=fh, stderr=fh)
            code = await proc.wait()
    return f"{arm} s{seed}: {'done' if done(log) else f'FAILED (exit {code})'}"


async def main(parallel: int, dry: bool, config_dir: str):
    (OUT / "logs").mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(parallel)
    tasks = [asyncio.create_task(play(*g, sem, dry, config_dir)) for g in games()]
    for t in asyncio.as_completed(tasks):
        print(await t, flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--parallel", type=int, default=16, help="games at a time")
    ap.add_argument("--dry-run", action="store_true", help="print the commands without running them")
    ap.add_argument("--config-dir", default=os.path.expanduser("~/.claude"),
                    help="Claude Code config root whose login pays for the calls")
    ap.add_argument("--firms", type=int, choices=[2, 4], default=2, help="2: the nine-arm experiment; 4: Lee's market")
    a = ap.parse_args()
    if a.firms == 4:
        OUT, SCRIPT, ARMS = ROOT / "succession/runs/prevention45_4firm", "experiments_synthetic/oligopoly_4.py", ARMS_4FIRM
    sys.exit(asyncio.run(main(a.parallel, a.dry_run, a.config_dir)))
