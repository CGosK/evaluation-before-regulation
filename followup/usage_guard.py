"""
Keeps the follow-up games inside the plan allowance. Every --every seconds it makes one tiny headless Claude Code
call on the same login and reads the rate_limit_event that call reports: each window's utilisation (5-hour and
weekly) and whether usage credits (overage) are in use. If the 5-hour window reaches --stop-at, the weekly window
reaches --weekly-stop-at, credits are in use, or the call is refused, it writes the shared pause file
(CLAUDE_PAUSE_FILE, as src/agents/llm_providers.py reads it) with that window's reset time, so every game waits
for the reset instead of failing partway or spilling onto credits. It sleeps through its own pauses, since a
reading taken on a full window is itself billed to credits. "allowed_warning" is not a refusal: it is sent
once weekly use passes 50%. It exits once --games logs under <runs>/logs/ end in "done".

Usage:  CLAUDE_CONFIG_DIR=~/.claude .venv/bin/python followup/usage_guard.py [--runs followup/runs] [--games 30]
            [--stop-at 0.75] [--weekly-stop-at 1.0] [--every 60]
Writes: <runs>/usage_guard.jsonl (one line per reading), <runs>/pause.json when it pauses
"""

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CALL = [
    "claude",
    "-p",
    "Reply with the word ok.",
    "--model",
    "claude-haiku-4-5",
    "--max-turns",
    "1",
    "--no-session-persistence",
    "--output-format",
    "stream-json",
    "--verbose",
]


def reading() -> dict:
    out = subprocess.run(CALL, capture_output=True, text=True, timeout=180)
    for line in out.stdout.splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") == "rate_limit_event":
            info = d["rate_limit_info"]
            windows = info.get("unifiedWindows", {})
            five, week = windows.get("five_hour", {}), windows.get("seven_day", {})
            return {
                "utilization": five.get("utilization"),
                "resets_at": five.get("resetsAt", info.get("resetsAt")),
                "weekly_utilization": week.get("utilization"),
                "weekly_resets_at": week.get("resetsAt"),
                "status": info.get("status"),
                "using_overage": info.get("isUsingOverage"),
            }
    return {"utilization": None, "resets_at": None, "status": "no reading", "using_overage": None}


def finished(runs: Path) -> int:
    return sum("✅ done" in f.read_text(errors="replace") for f in (runs / "logs").glob("*.txt"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--runs", type=Path, default=ROOT / "followup/runs", help="folder with logs/ to watch"
    )
    ap.add_argument("--games", type=int, default=30, help="exit once this many logs are done")
    ap.add_argument(
        "--stop-at", type=float, default=0.75, help="5-hour utilisation at which every game pauses"
    )
    ap.add_argument(
        "--weekly-stop-at",
        type=float,
        default=1.0,
        help="weekly utilisation at which every game pauses",
    )
    ap.add_argument("--every", type=int, default=60, help="seconds between readings")
    a = ap.parse_args()
    pause = Path(os.getenv("CLAUDE_PAUSE_FILE", a.runs / "pause.json"))
    while finished(a.runs) < a.games:
        r = {"time": time.time(), **reading()}
        weekly = (r.get("weekly_utilization") or 0) >= a.weekly_stop_at
        over = (
            r["utilization"] is None
            or r["utilization"] >= a.stop_at
            or weekly
            or r["using_overage"]
            or r["status"] not in ("allowed", "allowed_warning")
        )
        until = time.time() + a.every
        if over:
            reset = r.get("weekly_resets_at") if weekly else r["resets_at"]
            until = (reset or time.time() + 3600) + 120
            pause.write_text(json.dumps({"until": until, "reason": f"usage guard: {r}"}))
            r["paused_until"] = until
        with open(a.runs / "usage_guard.jsonl", "a") as fh:
            fh.write(json.dumps(r) + "\n")
        while time.time() < until:  # wall clock, so a Mac that slept still wakes on time
            time.sleep(min(a.every, max(1.0, until - time.time())))
