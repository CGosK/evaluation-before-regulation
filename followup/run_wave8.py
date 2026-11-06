"""
Wave-8 games (followup/WAVE8_PLAN.md; November 2026, not part of the submission): mixed-model markets. Every
game is a P1 duopoly of followup/mixed_game.py through headless Claude Code on the subscription login.

    --check   one 3-round game per arm, and one with the slots swapped, in runs/wave8/checks/ (not results):
              each slot's model, each model's effort, and the best-response line only where expected
    default   the plan's three arms, 10 games of 100 rounds each, seeds 1-10; Opus is Firm A in odd seeds

Launches append the time, the command and the SHA-256 of the plan and the code to runs/wave8/launch.txt.

Usage:  .venv/bin/python followup/run_wave8.py [--check] [--parallel 30] [--dry-run]
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "followup"), str(ROOT / "succession")]
from prevention45 import active, done  # noqa: E402
from run_wave2 import FAMILIES  # noqa: E402
from run_wave5 import CODE, sha  # noqa: E402

OUT = ROOT / "followup/runs/wave8"
PLAN = ROOT / "followup/WAVE8_PLAN.md"
FILES = CODE + [
    "followup/mixed_game.py",
    "followup/run_wave8.py",
    "src/agents/llm_providers.py",
    "succession/branch.py",
]
ARMS = {  # arm -> (rival family, mechanism)
    "opus-haiku55": ("haiku55", None),
    "opus-haiku45": ("haiku45", None),
    "opus-haiku45-brinfo": ("haiku45", "brinfo"),
}
CHECKS = [(arm, 1) for arm in ARMS] + [("opus-haiku45", 2)]  # seed 2 checks the slot swap


def slots(arm: str, seed: int) -> tuple:
    rival = ARMS[arm][0]
    return ("opus55", rival) if seed % 2 else (rival, "opus55")


async def play(arm, seed, rounds, out, sem, config_dir, dry) -> str:
    rival, mech = ARMS[arm]
    models = [FAMILIES[f][0] for f in slots(arm, seed)]
    log = out / "logs" / f"{arm}_s{seed}.txt"
    cmd = [
        str(ROOT / ".venv/bin/python"),
        "followup/mixed_game.py",
        "--models",
        *models,
        "--name",
        arm,
        *(["--mechanism", mech] if mech else []),
        "--provider",
        "claude-code",
        "--model",
        FAMILIES["opus55"][0],
        "--rounds",
        str(rounds),
        "--seeds",
        str(seed),
        "--plot-every",
        "0",
        "-y",
    ]
    if dry:
        return f"{arm} s{seed}: {' '.join(cmd[1:])}"
    if done(log):
        return f"{arm} s{seed}: already done"
    if active(log):
        async with sem:
            while active(log):
                await asyncio.sleep(20)
        return f"{arm} s{seed}: {'done' if done(log) else 'STALLED (adopted)'}"
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_EFFORT"}
    # medium for Opus 5.5 and Haiku 5.5, as in their own games; Haiku 4.5 has no effort setting
    env.update(
        CLAUDE_EFFORT="medium",
        CLAUDE_THINKING_BUDGET="0",
        MAX_THINKING_TOKENS="0",
        CLAUDE_USAGE_LOG=str(out / "usage.jsonl"),
        CLAUDE_CONFIG_DIR=config_dir,
        FOLLOWUP_GAMES=str(out / "games"),
    )
    env.setdefault("CLAUDE_PAUSE_FILE", str(OUT / "pause.json"))
    log.parent.mkdir(parents=True, exist_ok=True)
    async with sem:
        with open(log, "w") as fh:
            proc = await asyncio.create_subprocess_exec(
                *cmd, cwd=ROOT, env=env, stdout=fh, stderr=fh
            )
            code = await proc.wait()
    return f"{arm} s{seed}: {'done' if done(log) else f'FAILED (exit {code})'}"


async def main(jobs: list, out: Path, parallel: int, config_dir: str, dry: bool):
    sem = asyncio.Semaphore(parallel)
    tasks = [asyncio.ensure_future(play(*j, out, sem, config_dir, dry)) for j in jobs]
    for t in asyncio.as_completed(tasks):
        print(await t, flush=True)


def check(out: Path) -> bool:
    ok = True
    calls = [json.loads(line) for line in open(out / "usage.jsonl")]
    effort = {c["model"]: c.get("effort") for c in calls}
    want = {"claude-opus-5-5": "medium", "claude-haiku-5-5": "medium", "claude-haiku-4-5": None}
    for model, e in want.items():
        good = model in effort and effort[model] == e
        print(f"{model}: effort {effort.get(model, 'NO CALLS')}: {'OK' if good else 'FAIL'}")
        ok &= good
    for arm, seed in CHECKS:
        mech = ARMS[arm][1]
        found = sorted((out / "games/2_agents").glob(f"*_mixed-{arm}_*seed{seed}/results.json"))
        if not found:
            print(f"{arm} s{seed}: no game")
            ok = False
            continue
        meta = json.loads((found[-1].parent / "metadata.json").read_text())
        res = json.loads(found[-1].read_text())
        intended = dict(zip(["Firm A", "Firm B"], (FAMILIES[f][0] for f in slots(arm, seed))))
        good = meta["agents_models"] == intended
        later = [o["market_data"] for r in res.values() for t, o in r.items() if int(t) >= 2]
        br = [("Platform estimate" in m) for m in later]
        good &= all(br) if mech else not any(br)
        print(
            f"{arm} s{seed}: models {meta['agents_models']}, best-response line in "
            f"{sum(br)} of {len(br)} firm-rounds: {'OK' if good else 'FAIL'}"
        )
        ok &= good
    return ok


def record():
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    code = "; ".join(f"{c} {sha(ROOT / c)}" for c in FILES)
    with open(OUT / "launch.txt", "a") as fh:
        fh.write(f"{stamp} games: {' '.join(sys.argv)}\n")
        fh.write(f"WAVE8_PLAN.md sha256 {sha(PLAN)}\n")
        fh.write(f"code sha256: {code}\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--parallel", type=int, default=30)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--config-dir", default=os.path.expanduser("~/.claude"))
    a = ap.parse_args()
    if a.check:
        out = OUT / "checks"
        asyncio.run(main([(arm, s, 3) for arm, s in CHECKS], out, 4, a.config_dir, a.dry_run))
        sys.exit(0 if a.dry_run or check(out) else 1)
    if not a.dry_run:
        record()
    jobs = [(arm, s, 100) for s in range(1, 11) for arm in ARMS]
    asyncio.run(main(jobs, OUT, a.parallel, a.config_dir, a.dry_run))
