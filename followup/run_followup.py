"""
Runs the follow-up arms of followup/duopoly_followup.py on Claude Haiku 4.5: 10 fresh 100-round P1 duopolies per
arm, seeds 1-10, with succession/prevention45.py's runner unchanged. That means headless Claude Code on the
subscription login in --config-dir, extended thinking off, resumable logs, and the shared pause file
(CLAUDE_PAUSE_FILE, default followup/runs/pause.json) that holds every game while it exists.

Usage:  .venv/bin/python followup/run_followup.py [--parallel 15] [--dry-run] [--config-dir ~/.claude]
Writes: followup/runs/logs/<arm>_s<seed>.txt, followup/runs/usage.jsonl, games in followup/runs/games/2_agents/
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "succession"))
import prevention45 as runner  # noqa: E402

ARMS = {
    "brinfo_noise": ["--followup-arm", "brinfo_noise", "--mechanism", "brinfo"],
    "brinfo_bias": ["--followup-arm", "brinfo_bias", "--mechanism", "brinfo"],
    "cut10": ["--followup-arm", "cut10"],
}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--parallel", type=int, default=15, help="games at a time")
    ap.add_argument(
        "--dry-run", action="store_true", help="print the commands without running them"
    )
    ap.add_argument(
        "--config-dir",
        default=os.path.expanduser("~/.claude"),
        help="Claude Code config root whose login pays for the calls",
    )
    a = ap.parse_args()
    runner.OUT, runner.SCRIPT = ROOT / "followup/runs", "followup/duopoly_followup.py"
    runner.ARMS = {arm: (args, 0, range(1, 11)) for arm, args in ARMS.items()}
    sys.exit(asyncio.run(runner.main(a.parallel, a.dry_run, a.config_dir)))
