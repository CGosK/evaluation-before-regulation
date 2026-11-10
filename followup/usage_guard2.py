"""
usage_guard.py's loop with one fix, used from wave 11 on: a reading that has the weekly window but no 5-hour window,
as just after a weekly reset, counts as an empty 5-hour window. usage_guard.py read it as a failed reading and paused
every game until the next weekly reset. usage_guard.py is left unchanged, since earlier launches record its hash.

Usage:  CLAUDE_CONFIG_DIR=~/.claude .venv/bin/python followup/usage_guard2.py [usage_guard.py's options]
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import usage_guard as ug  # noqa: E402


def reading() -> dict:
    r = ug.reading()
    if r["utilization"] is None and r.get("weekly_utilization") is not None:
        r.update(utilization=0.0, resets_at=None, five_hour_window="none reported")
    return r


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--runs", type=Path, default=ug.ROOT / "followup/runs")
    ap.add_argument("--games", type=int, default=30)
    ap.add_argument("--stop-at", type=float, default=0.75)
    ap.add_argument("--weekly-stop-at", type=float, default=1.0)
    ap.add_argument("--every", type=int, default=60)
    a = ap.parse_args()
    pause = Path(os.getenv("CLAUDE_PAUSE_FILE", a.runs / "pause.json"))
    while ug.finished(a.runs) < a.games:
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
        while time.time() < until:
            time.sleep(min(a.every, max(1.0, until - time.time())))
