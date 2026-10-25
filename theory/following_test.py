"""
Does Claude Haiku 4.5 follow cuts only, or raises too? An event study on its 20 baseline duopolies
(succession/runs/screen and succession/runs/prevention45, rounds 11-100).

An event is a round t in which the rival changes its price by more than 1% (log) while the firm itself does not.
The response is the firm's own move in t+1: its direction, and the share of the rival's change it matches.
    Following cuts but not raises = defensive matching (the kinked-demand pattern): prices stick, no one leads up.
    Following raises as well     = price leadership: a coordination device.
The baseline is the chance of a move in either direction in a round after the rival did not move.

Usage:  uv run --extra analysis python theory/following_test.py
Writes: theory/out/following_test.json
"""

import json
import os
import sys
from pathlib import Path

import numpy as np
from scipy.stats import fisher_exact

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
import prevention45_results as p

OUT = Path(__file__).resolve().parent / "out"
MOVE = 0.01


def events(P: np.ndarray) -> dict:
    """P: rounds x 2 prices. Returns lists of (own response share, same direction, any move) per event type."""
    d = np.diff(np.log(P), axis=0)  # d[t] = change from round t to t+1 (0-based)
    out = {"cut": [], "raise": [], "quiet": []}
    for t in range(10, len(d) - 1):
        for i in (0, 1):
            j = 1 - i
            own, rival, nxt = d[t, i], d[t, j], d[t + 1, i]
            if abs(own) > MOVE:
                continue  # clean events only: the firm itself held in round t
            if abs(rival) <= MOVE:
                out["quiet"].append((0.0, False, abs(nxt) > MOVE))
            else:
                kind = "cut" if rival < 0 else "raise"
                out[kind].append((nxt / rival, np.sign(nxt) == np.sign(rival) and abs(nxt) > MOVE, abs(nxt) > MOVE))
    return out


if __name__ == "__main__":
    g = p.games()
    res = {}
    for scope, games in (("baseline", g["baseline"]), ("locked_high", [x for x in g["baseline"] if p.index(x)[50:].mean() > 0.3]),
                         ("learning_down", [x for x in g["baseline"] if p.index(x)[50:].mean() <= 0.3])):
        ev = {"cut": [], "raise": [], "quiet": []}
        for x in games:
            for k, v in events(x["P"]).items():
                ev[k] += v
        res[scope] = {"games": len(games)}
        for k in ("cut", "raise"):
            a = np.array(ev[k], dtype=float) if ev[k] else np.zeros((0, 3))
            res[scope][k] = {"events": len(a), "follow_same_direction": float(a[:, 1].mean()) if len(a) else None,
                             "median_share_matched": float(np.median(np.clip(a[:, 0], -1, 2))) if len(a) else None}
        q = np.array(ev["quiet"], dtype=float)
        res[scope]["move_after_quiet_round"] = float(q[:, 2].mean())
        fc, fr = (sum(e[1] for e in ev[k]) for k in ("cut", "raise"))
        res[scope]["p_fisher_cut_vs_raise"] = float(fisher_exact([[fc, len(ev["cut"]) - fc],
                                                                 [fr, len(ev["raise"]) - fr]])[1])
    (OUT / "following_test.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1, default=lambda v: round(v, 3)))
