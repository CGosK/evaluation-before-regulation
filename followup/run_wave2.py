"""
Second wave of follow-up games (November 2026, after the sprint review; not part of the submission). Every game
is a fresh 100-round P1 duopoly of followup/duopoly_followup.py through headless Claude Code on the
subscription login, extended thinking off for every model, effort medium for the models that have it (as in
the paper's Haiku 5.5 and Fable runs). The plan, with the screen's decision rule, is followup/WAVE2_PLAN.md.

    stage A  the screen for a second colluding model (Sonnet 5.5, Opus 5.5: 5 baseline games each) and the
             bias arms (Haiku 5.5 baseline and +10% bias; Haiku 4.5 -10% bias; Haiku 4.5 told to enforce,
             baseline and +10% bias; 10 games each)
    stage B  for each family named with --families (the screen's colluders): 5 more baseline games, then
             best-response information and the forced 10% cut, 10 games each

Games run --parallel at a time in seed-major order. A game whose log ends in "done" is skipped, so rerunning
resumes; the shared pause file (CLAUDE_PAUSE_FILE, default followup/runs/wave2/pause.json) holds every game
while it exists, as followup/usage_guard.py writes it.

Usage:  .venv/bin/python followup/run_wave2.py --stage A|B [--families sonnet55 ...] [--parallel 20] [--dry-run]
Writes: followup/runs/wave2/logs/<family>_<arm>_s<seed>.txt, followup/runs/wave2/usage.jsonl,
        games in followup/runs/wave2/games/2_agents/
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "succession"))
from prevention45 import active, done  # noqa: E402

OUT = ROOT / "followup/runs/wave2"
FAMILIES = {  # model, effort, strategy
    "haiku45": ("claude-haiku-4-5", None, None),
    "haiku45enf": ("claude-haiku-4-5", None, "enforcer2"),
    "haiku55": ("claude-haiku-5-5", "medium", None),
    "sonnet55": ("claude-sonnet-5-5", "medium", None),
    "opus55": ("claude-opus-5-5", "medium", None),
}
STAGE_A = [
    ("opus55", "baseline", range(1, 6)),
    ("sonnet55", "baseline", range(1, 6)),
    ("haiku55", "baseline", range(1, 11)),
    ("haiku55", "brinfo_bias", range(1, 11)),
    ("haiku45", "brinfo_biasdown", range(1, 11)),
    ("haiku45enf", "baseline", range(1, 11)),
    ("haiku45enf", "brinfo_bias", range(1, 11)),
]


def stage_b(family: str) -> list:
    return [
        (family, "baseline", range(6, 11)),
        (family, "brinfo", range(1, 11)),
        (family, "cut10", range(1, 11)),
    ]


def games(plan: list) -> list:
    out = [(fam, arm, s) for fam, arm, seeds in plan for s in seeds]
    return sorted(out, key=lambda g: (g[2], plan.index(next(p for p in plan if p[:2] == g[:2]))))


async def play(
    family: str, arm: str, seed: int, sem: asyncio.Semaphore, dry: bool, config_dir: str
) -> str:
    model, effort, strategy = FAMILIES[family]
    log = OUT / "logs" / f"{family}_{arm}_s{seed}.txt"
    if done(log):
        return f"{family} {arm} s{seed}: already done"
    if active(log) and not dry:
        async with sem:  # running under an earlier launcher: hold its slot until it ends
            while active(log):
                await asyncio.sleep(20)
        return f"{family} {arm} s{seed}: {'done' if done(log) else 'STALLED (adopted)'}"
    cmd = [
        str(ROOT / ".venv/bin/python"),
        "followup/duopoly_followup.py",
        "--followup-arm",
        arm,
        *(["--followup-strategy", strategy] if strategy else []),
        *(["--mechanism", "brinfo"] if arm.startswith("brinfo") else []),
        "--provider",
        "claude-code",
        "--model",
        model,
        "--rounds",
        "100",
        "--seeds",
        str(seed),
        "--plot-every",
        "0",
        "-y",
    ]
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_EFFORT"}
    # MAX_THINKING_TOKENS=0 as well: without it Opus 5.5 still thinks a little with thinking switched off
    env.update(
        CLAUDE_THINKING_BUDGET="0",
        MAX_THINKING_TOKENS="0",
        CLAUDE_USAGE_LOG=str(OUT / "usage.jsonl"),
        CLAUDE_CONFIG_DIR=config_dir,
        FOLLOWUP_GAMES=str(OUT / "games"),
        FOLLOWUP_FAMILY=family,
    )
    if effort:
        env["CLAUDE_EFFORT"] = effort
    env.setdefault("CLAUDE_PAUSE_FILE", str(OUT / "pause.json"))
    if dry:
        return f"{family} {arm} s{seed}: CLAUDE_EFFORT={effort} {' '.join(cmd[1:])}"
    async with sem:
        with open(log, "w") as fh:
            proc = await asyncio.create_subprocess_exec(
                *cmd, cwd=ROOT, env=env, stdout=fh, stderr=fh
            )
            code = await proc.wait()
    return f"{family} {arm} s{seed}: {'done' if done(log) else f'FAILED (exit {code})'}"


async def main(plan: list, parallel: int, dry: bool, config_dir: str):
    (OUT / "logs").mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(parallel)
    tasks = [asyncio.create_task(play(*g, sem, dry, config_dir)) for g in games(plan)]
    for t in asyncio.as_completed(tasks):
        print(await t, flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--stage", choices=["A", "B"], required=True)
    ap.add_argument(
        "--families",
        nargs="*",
        default=[],
        choices=[f for f in FAMILIES if f != "haiku45"],
        help="stage B: the families the screen found colluding",
    )
    ap.add_argument("--parallel", type=int, default=20, help="games at a time")
    ap.add_argument(
        "--dry-run", action="store_true", help="print the commands without running them"
    )
    ap.add_argument(
        "--config-dir",
        default=os.path.expanduser("~/.claude"),
        help="Claude Code config root whose login pays for the calls",
    )
    a = ap.parse_args()
    plan = STAGE_A if a.stage == "A" else [g for f in a.families for g in stage_b(f)]
    if not plan:
        sys.exit("stage B needs --families")
    sys.exit(asyncio.run(main(plan, a.parallel, a.dry_run, a.config_dir)))
