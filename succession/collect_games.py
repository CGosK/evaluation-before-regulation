"""
Copies finished Claude Haiku 4.5 games from experiments_synthetic/experiments_runs/<n>_agents/ (not committed)
into a committed run folder, keeping results.json, metadata.json and environment_history.parquet. A game is
copied once, only if every firm played all its rounds and the folder was written at or after --since (a unix
timestamp, the folder-name prefix), so smoke tests and set-aside partial runs stay out.

Usage:  .venv/bin/python succession/collect_games.py --firms 4 --since 1792946900 --to succession/runs/prevention45_4firm/games
"""

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--firms", type=int, required=True)
    ap.add_argument("--since", type=int, required=True, help="earliest folder timestamp to copy")
    ap.add_argument("--to", type=Path, required=True)
    ap.add_argument("--model", default="claude-haiku-4-5")
    a = ap.parse_args()
    dest = ROOT / a.to
    dest.mkdir(parents=True, exist_ok=True)
    copied = 0
    for d in sorted((ROOT / f"experiments_synthetic/experiments_runs/{a.firms}_agents").iterdir()):
        if not d.name[:10].isdigit() or int(d.name.split("_")[0]) < a.since or (dest / d.name).exists():
            continue
        meta_f, res_f = d / "metadata.json", d / "results.json"
        if not meta_f.exists() or not res_f.exists():
            continue
        meta = json.loads(meta_f.read_text())
        if a.model not in str(meta.get("agents_models", "")):
            continue
        if min(len(v) for v in json.loads(res_f.read_text()).values()) < meta["num_rounds"]:
            continue
        (dest / d.name).mkdir()
        for f in ("results.json", "metadata.json", "environment_history.parquet"):
            shutil.copy2(d / f, dest / d.name / f)
        copied += 1
    print(f"copied {copied}; {len(list(dest.iterdir()))} games in {a.to}")
