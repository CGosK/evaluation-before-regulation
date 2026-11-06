"""
Raise and cut following on saved games (November 2026, not part of the submission; exploratory, no new games).

The paper's event measure (theory/following_test.py): an event is a round in which the rival changes its price
by more than 1% while the firm holds, and the firm follows if it moves the same way by more than 1% in the next
round. Rounds 11-100. The paper found Haiku 4.5 follows cuts more than raises (34% against 22%).

    self-play    each model's own baseline games: Haiku 4.5 (the submission's 20), Haiku 5.5 and Sonnet 5.5
                 (wave 2), Opus 5.5 (waves 2-3)
    mixed        wave 8's two pairings without a remedy, each model following the other

For each set: pooled shares with the paper's Fisher test, and by game the share of raises followed minus the
share of cuts followed, among games with at least 3 events of each kind, with a two-sided sign test.

Usage:  uv run --extra analysis python followup/following_results.py
Writes: followup/out/following.json
"""

import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import binomtest, fisher_exact

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "theory")]
import prevention45_results as p  # noqa: E402
import wave2_results as w2  # noqa: E402
import wave3_results as w3  # noqa: E402
import wave8_results as w8  # noqa: E402

OUT = HERE / "out"
MOVE = 0.01
MIN_EVENTS = 3


def firm_events(P: np.ndarray, i: int) -> dict:
    """Firm i's responses to its rival's moves, as in theory/following_test.events."""
    d = np.diff(np.log(P), axis=0)
    out = {"cut": [], "raise": [], "quiet": []}
    for t in range(10, len(d) - 1):
        own, rival, nxt = d[t, i], d[t, 1 - i], d[t + 1, i]
        if abs(own) > MOVE:
            continue
        if abs(rival) <= MOVE:
            out["quiet"].append(abs(nxt) > MOVE)
        else:
            kind = "cut" if rival < 0 else "raise"
            out[kind].append(bool(np.sign(nxt) == np.sign(rival) and abs(nxt) > MOVE))
    return out


def summarise(per_game: list) -> dict:
    """per_game: one dict of event lists per game (one firm, or both firms pooled)."""
    pooled = {k: sum((g[k] for g in per_game), []) for k in ("cut", "raise", "quiet")}
    fc, fr = sum(pooled["cut"]), sum(pooled["raise"])
    nc, nr = len(pooled["cut"]), len(pooled["raise"])
    diffs = [
        float(np.mean(g["raise"]) - np.mean(g["cut"]))
        for g in per_game
        if len(g["raise"]) >= MIN_EVENTS and len(g["cut"]) >= MIN_EVENTS
    ]
    more, fewer = sum(v > 0 for v in diffs), sum(v < 0 for v in diffs)
    return {
        "games": len(per_game),
        "cut_events": nc,
        "raise_events": nr,
        "follow_cut": fc / nc if nc else None,
        "follow_raise": fr / nr if nr else None,
        "move_after_quiet_round": float(np.mean(pooled["quiet"])) if pooled["quiet"] else None,
        "p_fisher_cut_vs_raise": float(fisher_exact([[fc, nc - fc], [fr, nr - fr]])[1]),
        "eligible_games": len(diffs),
        "games_raises_followed_more": int(more),
        "games_cuts_followed_more": int(fewer),
        "p_sign": float(binomtest(more, more + fewer).pvalue) if more + fewer else None,
    }


def self_play(games: list) -> dict:
    per_game = []
    for x in games:
        a, b = firm_events(x["P"], 0), firm_events(x["P"], 1)
        per_game.append({k: a[k] + b[k] for k in a})
    return summarise(per_game)


def mixed(games: list) -> dict:
    out = {}
    for x in games:
        for i, model in enumerate(x["models"]):
            out.setdefault(model, []).append(firm_events(x["P"], i))
    return {m: summarise(v) for m, v in out.items()}


if __name__ == "__main__":
    p.RUNS = list(w2.SUBMITTED)
    sets = {
        "claude-haiku-4-5": p.games()["baseline"],
        "claude-haiku-5-5": w2.family_games("haiku55", ("baseline",))["baseline"],
        "claude-sonnet-5-5": w2.family_games("sonnet55", ("baseline",))["baseline"],
        "claude-opus-5-5": w3.opus_games()["baseline"],
    }
    g8 = w8.games()
    res = {
        "self_play": {m: self_play(xs) for m, xs in sets.items()},
        "mixed": {a: mixed(g8[a]) for a in ("opus-haiku55", "opus-haiku45")},
    }
    OUT.mkdir(exist_ok=True)
    (OUT / "following.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1, default=float))
