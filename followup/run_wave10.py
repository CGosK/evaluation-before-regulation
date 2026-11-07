"""
Wave-10 games (study 1, followup/WAVE10_PLAN.md; not part of the submission): wave 7's 10 estimate games and
wave 3's 5 Opus 5.5 baseline games, continued from round 100 to round 200 through followup/continue_game.py,
with the settings they were first played with. Only copies are continued; the saved games are never touched.

    --copy       copy the 15 games into runs/wave10/games/2_agents/, under their own folder names
    --check      continue_game.py --check on every copy: no calls
    --pilot      continue the seed-1 estimate game to round 105, to read its first new rounds before the rest
    (default)    continue every copy to round 200; appends the time, the command and the SHA-256 of the plan and
                 the code to runs/wave10/launch.txt

The pilot logs to logs/pilot_s1.txt, so the games' own logs say "done" only at round 200. Run the usage guard
alongside, counting the pilot's log:  usage_guard.py --runs followup/runs/wave10 --games 1 (pilot) or 16
Usage:  .venv/bin/python followup/run_wave10.py [--copy | --check | --pilot] [--parallel 15] [--dry-run]
            [--config-dir ~/.claude]
"""

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "followup"), str(ROOT / "succession")]
from prevention45 import active, done  # noqa: E402
from run_wave2 import FAMILIES  # noqa: E402
from run_wave5 import sha  # noqa: E402

OUT = ROOT / "followup/runs/wave10"
GAMES = OUT / "games/2_agents"
PLAN = ROOT / "followup/WAVE10_PLAN.md"
RULE = "followup/rules7/estimate_no_threat.py"
ROUNDS, PILOT_ROUNDS = 200, 105
SOURCES = {
    "estimate": (
        ROOT / "followup/runs/wave7/games/2_agents",
        "*_rule-w7-estimate-no-threat_*_seed{s}",
        range(1, 11),
    ),
    "baseline": (
        ROOT / "followup/runs/wave3/games/2_agents",
        "*_opus55_baseline_*_seed{s}",
        range(11, 16),
    ),
}
CODE = [
    "followup/continue_game.py",
    "followup/run_wave10.py",
    "followup/wave10_results.py",
    "followup/platform_rules.py",
    RULE,
    "followup/usage_guard.py",
    "experiments_synthetic/common.py",
    "src/experiment/experiment.py",
    "src/prompts/prompt_manager.py",
    "src/agents/llm_providers.py",
]


def sources() -> list:
    out = []
    for arm, (folder, pattern, seeds) in SOURCES.items():
        for s in seeds:
            found = sorted(folder.glob(pattern.format(s=s)))
            if len(found) != 1:
                sys.exit(f"{arm} seed {s}: {len(found)} saved games match")
            out.append((arm, s, found[0]))
    return out


def jobs() -> list:
    return [(arm, s, GAMES / src.name) for arm, s, src in sources()]


def copy_games():
    for arm, s, src in sources():
        dest = GAMES / src.name
        if dest.exists():
            print(f"{arm} s{s}: already copied")
            continue
        shutil.copytree(src, dest)
        print(f"{arm} s{s}: copied {src.relative_to(ROOT)}")


def command(arm: str, game: Path, rounds: int) -> list:
    cmd = [
        str(ROOT / ".venv/bin/python"),
        "followup/continue_game.py",
        str(game),
        "--rounds",
        str(rounds),
    ]
    return cmd + (["--rule", RULE] if arm == "estimate" else [])


def check() -> bool:
    ok = True
    for arm, s, game in jobs():
        if not game.exists():
            print(f"{arm} s{s}: not copied")
            ok = False
            continue
        if reached(game) >= ROUNDS:
            print(f"{arm} s{s}: at round {ROUNDS}")
            continue
        r = subprocess.run(
            command(arm, game, ROUNDS) + ["--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        print(f"{arm} s{s}: {(r.stdout + r.stderr).strip().splitlines()[-1]}")
        ok &= r.returncode == 0
    return ok


def reached(game: Path) -> int:
    res = json.loads((game / "results.json").read_text())
    return min(max(int(t) for t in rounds) for rounds in res.values())


async def play(arm, seed, game, rounds, sem, config_dir, dry) -> str:
    log = OUT / "logs" / f"{'pilot' if rounds == PILOT_ROUNDS else arm}_s{seed}.txt"
    cmd = command(arm, game, rounds)
    if dry:
        return f"{arm} s{seed}: {' '.join(cmd[1:])}"
    if active(log):
        return f"{arm} s{seed}: still running elsewhere"
    _, effort, _ = FAMILIES["opus55"]
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_EFFORT"}
    env.update(
        CLAUDE_THINKING_BUDGET="0",
        MAX_THINKING_TOKENS="0",
        CLAUDE_EFFORT=effort,
        CLAUDE_USAGE_LOG=str(OUT / "usage.jsonl"),
        CLAUDE_CONFIG_DIR=config_dir,
        CLAUDE_PAUSE_FILE=str(OUT / "pause.json"),
    )
    log.parent.mkdir(parents=True, exist_ok=True)
    async with sem:
        with open(log, "a") as fh:
            proc = await asyncio.create_subprocess_exec(
                *cmd, cwd=ROOT, env=env, stdout=fh, stderr=fh
            )
            code = await proc.wait()
    last = reached(game)
    ok = last >= rounds and done(log)
    return f"{arm} s{seed}: {'done' if ok else f'FAILED at round {last} (exit {code})'}"


async def main(todo: list, rounds: int, parallel: int, config_dir: str, dry: bool):
    sem = asyncio.Semaphore(parallel)
    tasks = [asyncio.ensure_future(play(*j, rounds, sem, config_dir, dry)) for j in todo]
    for t in asyncio.as_completed(tasks):
        print(await t, flush=True)


def record(mode: str):
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(OUT / "launch.txt", "a") as fh:
        fh.write(f"{stamp} {mode}: {' '.join(sys.argv)}\n")
        fh.write(f"WAVE10_PLAN.md sha256 {sha(PLAN)}\n")
        fh.write(f"code sha256: {'; '.join(f'{c} {sha(ROOT / c)}' for c in CODE)}\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--copy", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--pilot", action="store_true")
    ap.add_argument("--parallel", type=int, default=15)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--config-dir", default=os.path.expanduser("~/.claude"))
    a = ap.parse_args()
    if a.copy:
        copy_games()
        sys.exit(0)
    if a.check:
        sys.exit(0 if check() else 1)
    if not a.dry_run:
        if not PLAN.exists():
            sys.exit("no plan: WAVE10_PLAN.md must be written before any game runs")
        if not check():
            sys.exit("check failed")
        record("pilot" if a.pilot else "games")
    todo = [j for j in jobs() if j[:2] == ("estimate", 1)] if a.pilot else jobs()
    todo = [j for j in todo if reached(j[2]) < (PILOT_ROUNDS if a.pilot else ROUNDS)]
    asyncio.run(
        main(todo, PILOT_ROUNDS if a.pilot else ROUNDS, a.parallel, a.config_dir, a.dry_run)
    )
