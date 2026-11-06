"""
Wave-7 results (followup/WAVE7_PLAN.md; November 2026, not part of the submission).

    primary      index over rounds 51-100 for w7-estimate-no-threat against Opus 5.5's 15 baseline games, one
                 permutation test, and the plan's decision and reading
    exploratory  index over all of 51-100, games above 0.3, 10-round blocks, follow rate (rounds 11-99)
    notes        both firms' notes at rounds 30, 60 and 90, to runs/wave7/notes.jsonl for reading by hand

Usage:  uv run --extra analysis python followup/wave7_results.py
Writes: followup/out/wave7.json, followup/runs/wave7/notes.jsonl
"""

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "theory")]
import prevention45_results as p  # noqa: E402
import wave3_results as w3  # noqa: E402
import wave5_results as w5  # noqa: E402
import wave6_results as w6  # noqa: E402
from platform_rules import MONOPOLY, NASH  # noqa: E402

OUT = HERE / "out"
RUNS = HERE / "runs/wave7"
RULE = "w7-estimate-no-threat"
NOTE_ROUNDS = (30, 60, 90)
READING = {
    "competitive": "the shared clauses are enough; neither the word nor the threat is needed",
    "lowers prices": "the clauses help, but the word or the threat is needed to reach competitive prices",
    "no detectable effect": "wave 6's reading stands",
}


def results(x: dict) -> dict:
    return json.loads((RUNS / "games/2_agents" / x["name"] / "results.json").read_text())


def follow(xs: list) -> dict:
    hits, by_game = [], []
    for x in xs:
        res, game = results(x), []
        for t in range(11, 100):
            for firm in sorted(res):
                m = w6.SHOWN.search(res[firm][str(t)]["market_data"])
                if m:
                    nxt = res[firm][str(t + 1)]
                    own = nxt.get("model_price", nxt["chosen_price"])
                    game.append(abs(np.log(own / float(m.group(1)))) < 0.01)
        hits += game
        by_game.append(round(float(np.mean(game)), 3))
    return {
        "firm_rounds": len(hits),
        "within_1pct": float(np.mean(hits)),
        "by_game": sorted(by_game),
    }


def late_by_game(xs: list) -> list:
    """Each game's index over rounds 51-100, 81-90 and 91-100, and in round 100."""
    out = []
    for x in sorted(xs, key=lambda z: z["seed"]):
        r = results(x)
        P = np.array(
            [
                [r[f][str(t)].get("model_price", r[f][str(t)]["chosen_price"]) for f in sorted(r)]
                for t in range(1, 101)
            ]
        )
        idx = ((P - NASH) / (MONOPOLY - NASH)).mean(1)
        out.append(
            {
                "seed": int(x["seed"]),
                "r51_100": round(float(idx[50:].mean()), 3),
                "r81_90": round(float(idx[80:90].mean()), 3),
                "r91_100": round(float(idx[90:].mean()), 3),
                "r100": round(float(idx[99]), 3),
            }
        )
    return out


if __name__ == "__main__":
    rng = np.random.default_rng(2026)
    xs = w5.games(RUNS, RULE, 100)
    if len(xs) != 10:
        print(f"incomplete: {len(xs)} games")
    base = [float(p.index(x)[p.LATE].mean()) for x in w3.opus_games()["baseline"]]
    s = w6.summary(xs)
    prim = [w5.score(x, w6.WINDOW)["index"] for x in xs]
    pv = p.perm_p(prim, base, rng)
    lowers = pv < 0.05 and np.mean(prim) < np.mean(base)
    verdict = (
        "competitive"
        if lowers and np.mean(prim) < 0.1
        else "lowers prices"
        if lowers
        else "no detectable effect"
    )
    w6json = json.loads((OUT / "wave6.json").read_text())["exploratory"]
    res = {
        "baseline": {"games": len(base), "index": float(np.mean(base))},
        RULE: s,
        "test": {"p": pv, "effect": float(np.mean(prim) - np.mean(base))},
        "decision": verdict,
        "reading": READING[verdict],
        "exploratory": {
            "follow_11_99": follow(xs),
            "wave6_follow_for_comparison": {
                "lifted_11_49": w6json["follow_lifted_11_49"]["within_1pct"],
                "limit_no_threat": w6json["follow_no_threat_11_99"]["within_1pct"],
                "estimate_threat": w6json["follow_estimate_threat_11_99"]["within_1pct"],
            },
            "late_by_game": late_by_game(xs),
        },
    }
    OUT.mkdir(exist_ok=True)
    (OUT / "wave7.json").write_text(json.dumps(res, indent=1, default=float))
    with open(RUNS / "notes.jsonl", "w") as fh:
        for x in xs:
            r = results(x)
            for firm in sorted(r):
                for t in NOTE_ROUNDS:
                    o = r[firm][str(t)]
                    keep = {k: o.get(k, "") for k in ("observations", "plans", "insights")}
                    fh.write(
                        json.dumps({"seed": x["seed"], "firm": firm, "round": t, **keep}) + "\n"
                    )
    print(json.dumps(res, indent=1, default=float))
