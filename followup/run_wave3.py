"""
Third wave of follow-up games (November 2026, after the sprint review; not part of the submission): forced Nash
rounds on Claude Opus 5.5, as fixed in followup/WAVE3_PLAN.md. Every game is a fresh 100-round P1 duopoly of
followup/duopoly_followup.py through headless Claude Code on the subscription login, with wave 2's Opus settings.

    stage A  5 baseline games (seeds 11-15) and forced10 (seeds 1-10)
    stage B  forced5 (seeds 1-10), only if out/wave3.json says the plan's rule calls for it
    --stub   one 21-round game per new arm on Haiku 4.5, in runs/wave3/stubs/, checking that the forced
             rounds land where the rule puts them; not results

A real launch appends the time, the command and the SHA-256 of the plan and the game code to
runs/wave3/launch.txt. Games resume and pause as in followup/run_wave2.py.

Usage:  .venv/bin/python followup/run_wave3.py --stage A|B [--parallel 20] [--dry-run]
        .venv/bin/python followup/run_wave3.py --stub
Writes: followup/runs/wave3/{launch.txt,usage.jsonl,logs/,games/2_agents/}
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
from run_wave2 import FAMILIES, games  # noqa: E402

OUT = ROOT / "followup/runs/wave3"
PLAN = ROOT / "followup/WAVE3_PLAN.md"
CODE = ["followup/duopoly_followup.py", "followup/run_wave3.py", "followup/run_wave2.py"]
CODE += ["followup/usage_guard.py", "experiments_synthetic/common.py"]
STAGES = {
    "A": [("opus55", "baseline", range(11, 16)), ("opus55", "forced10", range(1, 11))],
    "B": [("opus55", "forced5", range(1, 11))],
    "stub": [("haiku45", "forced10", range(1, 2)), ("haiku45", "forced5", range(1, 2))],
}
STUB_FORCED = {"forced10": [20], "forced5": [15, 20]}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def play(
    family: str,
    arm: str,
    seed: int,
    sem: asyncio.Semaphore,
    out: Path,
    rounds: int,
    dry: bool,
    config_dir: str,
) -> str:
    model, effort, strategy = FAMILIES[family]
    log = out / "logs" / f"{family}_{arm}_s{seed}.txt"
    if done(log):
        return f"{family} {arm} s{seed}: already done"
    if active(log) and not dry:
        async with sem:
            while active(log):
                await asyncio.sleep(20)
        return f"{family} {arm} s{seed}: {'done' if done(log) else 'STALLED (adopted)'}"
    every = arm.removeprefix("forced") if arm.startswith("forced") else None
    cmd = [
        str(ROOT / ".venv/bin/python"),
        "followup/duopoly_followup.py",
        "--followup-arm",
        arm,
        *(["--followup-strategy", strategy] if strategy else []),
        *(["--forced-every", every] if every else []),
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
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_EFFORT"}
    env.update(
        CLAUDE_THINKING_BUDGET="0",
        MAX_THINKING_TOKENS="0",
        CLAUDE_USAGE_LOG=str(out / "usage.jsonl"),
        CLAUDE_CONFIG_DIR=config_dir,
        FOLLOWUP_GAMES=str(out / "games"),
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


async def main(plan: list, out: Path, rounds: int, parallel: int, dry: bool, config_dir: str):
    (out / "logs").mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(parallel)
    tasks = [asyncio.create_task(play(*g, sem, out, rounds, dry, config_dir)) for g in games(plan)]
    for t in asyncio.as_completed(tasks):
        print(await t, flush=True)


def check_stubs(out: Path) -> bool:
    ok = True
    for arm, want in STUB_FORCED.items():
        found = sorted((out / "games/2_agents").glob(f"*_haiku45_{arm}_*/results.json"))
        if not found:
            print(f"stub {arm}: no game")
            ok = False
            continue
        res = json.loads(found[-1].read_text())
        got = sorted({int(t) for firm in res.values() for t, o in firm.items() if o.get("forced")})
        print(
            f"stub {arm}: forced rounds {got}, expected {want}: {'OK' if got == want else 'FAIL'}"
        )
        ok &= got == want
    return ok


def stage_b_allowed() -> bool:
    res = ROOT / "followup/out/wave3.json"
    if not res.exists():
        sys.exit("stage B needs followup/out/wave3.json: run followup/wave3_results.py first")
    rule = json.loads(res.read_text())["stage_b_rule"]
    print(f"stage B rule: {rule}")
    return rule["run"]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--stage", choices=["A", "B"])
    ap.add_argument("--stub", action="store_true", help="run the 21-round checks of the new arms")
    ap.add_argument("--parallel", type=int, default=20, help="games at a time")
    ap.add_argument("--dry-run", action="store_true", help="print the commands only")
    ap.add_argument(
        "--config-dir",
        default=os.path.expanduser("~/.claude"),
        help="Claude Code config root whose login pays for the calls",
    )
    a = ap.parse_args()
    if a.stub:
        out = OUT / "stubs"
        asyncio.run(main(STAGES["stub"], out, 21, 2, a.dry_run, a.config_dir))
        sys.exit(0 if a.dry_run or check_stubs(out) else 1)
    if not a.stage:
        sys.exit("--stage A, --stage B or --stub")
    if a.stage == "B" and not a.dry_run and not stage_b_allowed():
        sys.exit("the plan's rule says stage B does not run")
    if not a.dry_run:
        OUT.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        code = "; ".join(f"{c} {sha(ROOT / c)}" for c in CODE)
        with open(OUT / "launch.txt", "a") as fh:
            fh.write(f"{stamp} stage {a.stage}: {' '.join(sys.argv)}\n")
            fh.write(f"WAVE3_PLAN.md sha256 {sha(PLAN)}\ncode sha256: {code}\n")
    sys.exit(asyncio.run(main(STAGES[a.stage], OUT, 100, a.parallel, a.dry_run, a.config_dir)))
