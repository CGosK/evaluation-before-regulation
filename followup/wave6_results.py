"""
Wave-6 results (followup/WAVE6_PLAN.md; November 2026, not part of the submission).

    primary      index over rounds 51-100 on rounds with no override, for each rule in rules6/; four permutation
                 tests (lifted against the limit kept and against baseline, the two wording rules against
                 baseline), Holm over the four, and the plan's decisions
    exploratory  index over all of 51-100, games above 0.3, 10-round blocks, follow rate, overrides fired
    notes        Firm A's and Firm B's notes at the plan's rounds, to runs/wave6/notes.jsonl for reading by hand

Usage:  uv run --extra analysis python followup/wave6_results.py
Writes: followup/out/wave6.json, followup/runs/wave6/notes.jsonl
"""

import json
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "theory")]
import prevention45_results as p  # noqa: E402
import wave3_results as w3  # noqa: E402
import wave5_results as w5  # noqa: E402
from platform_rules import NASH, best_response  # noqa: E402

OUT = HERE / "out"
RUNS = HERE / "runs/wave6"
WINDOW = (51, 100)
LIFT_AFTER = 50
RULES = ("w6-lifted", "w6-limit-no-threat", "w6-estimate-threat")
SHOWN = re.compile(
    r"Platform (?:price limit for my next price|estimate of my profit-maximizing next price): (\d+\.\d+)"
)
NOTE_ROUNDS = {
    "w6-lifted": (51, 60, 75, 100),
    "w6-limit-no-threat": (30, 60, 90),
    "w6-estimate-threat": (30, 60, 90),
}


def results(x: dict) -> dict:
    folder = next(
        f
        for f in (RUNS / "games/2_agents", w5.RUNS / "confirm/games/2_agents")
        if (f / x["name"]).exists()
    )
    return json.loads((folder / x["name"] / "results.json").read_text())


def follow(xs: list, rounds: range, would_have=False) -> dict:
    hits = []
    for x in xs:
        res = results(x)
        firms = sorted(res)
        for t in rounds:
            for firm in firms:
                rival = next(f for f in firms if f != firm)
                if would_have:
                    shown = round(
                        max(best_response(NASH, res[rival][str(t)]["chosen_price"]), NASH), 2
                    )
                else:
                    m = SHOWN.search(res[firm][str(t)]["market_data"])
                    if not m:
                        continue
                    shown = float(m.group(1))
                nxt = res[firm][str(t + 1)]
                own = nxt.get("model_price", nxt["chosen_price"])
                hits.append(abs(np.log(own / shown)) < 0.01)
    return {"firm_rounds": len(hits), "within_1pct": float(np.mean(hits)) if hits else None}


def summary(xs: list) -> dict:
    s = [w5.score(x, WINDOW) for x in xs]
    idx = np.array([p.index(x)[:100] for x in xs])
    return {
        "games": len(xs),
        "primary_index": float(np.mean([v["index"] for v in s])),
        "primary_by_game": sorted(round(v["index"], 3) for v in s),
        "index_all_rounds": float(np.mean([v["index_all_rounds"] for v in s])),
        "games_above_0.3": int(sum(v["index_all_rounds"] > 0.3 for v in s)),
        "blocks_of_10": [round(float(idx[:, i : i + 10].mean()), 3) for i in range(0, 100, 10)],
        "overrides": [int(x["forced"].any(1).sum()) for x in xs],
    }


def notes(sets: dict):
    with open(RUNS / "notes.jsonl", "w") as fh:
        for name, xs in sets.items():
            for x in xs:
                res = results(x)
                for firm in sorted(res):
                    for t in NOTE_ROUNDS[name]:
                        o = res[firm].get(str(t))
                        if o:
                            keep = {k: o.get(k, "") for k in ("observations", "plans", "insights")}
                            row = {
                                "rule": name,
                                "seed": x["seed"],
                                "firm": firm,
                                "round": t,
                                **keep,
                            }
                            fh.write(json.dumps(row) + "\n")


if __name__ == "__main__":
    rng = np.random.default_rng(2026)
    sets = {r: w5.games(RUNS, r, 100) for r in RULES}
    missing = [r for r, xs in sets.items() if len(xs) != 10]
    if missing:
        print("incomplete:", {r: len(sets[r]) for r in RULES})
    base = [float(p.index(x)[p.LATE].mean()) for x in w3.opus_games()["baseline"]]
    kept_games = w5.games(w5.RUNS / "confirm", "r1b-br-limit", 100)
    kept = [w5.score(x, WINDOW)["index"] for x in kept_games]
    out = {r: summary(xs) for r, xs in sets.items() if xs}
    prim = {r: [w5.score(x, WINDOW)["index"] for x in xs] for r, xs in sets.items() if xs}
    tests = {}
    if "w6-lifted" in prim:
        tests["lifted_vs_kept"] = ("w6-lifted", kept)
        tests["lifted_vs_baseline"] = ("w6-lifted", base)
    for r in ("w6-limit-no-threat", "w6-estimate-threat"):
        if r in prim:
            tests[f"{r[3:]}_vs_baseline"] = (r, base)
    ps = {k: p.perm_p(prim[r], ref, rng) for k, (r, ref) in tests.items()}
    holm = p.holm(ps)
    t = {
        k: {
            "p": ps[k],
            "p_holm": holm[k],
            "significant": holm[k] < 0.05,
            "effect": float(np.mean(prim[r]) - np.mean(ref)),
        }
        for k, (r, ref) in tests.items()
    }
    dec = {}
    if "w6-lifted" in prim and len(tests) == 4:
        m, s1, s2 = (
            np.mean(prim["w6-lifted"]),
            t["lifted_vs_kept"]["significant"],
            t["lifted_vs_baseline"]["significant"],
        )
        dec["w6-lifted"] = (
            "low prices outlast the limit"
            if m < 0.1 and s2
            else "prices return to baseline"
            if s1 and not s2
            else "prices partly return"
            if s1 and s2
            else "inconclusive"
        )
        comp = {}
        for r in ("w6-limit-no-threat", "w6-estimate-threat"):
            k = f"{r[3:]}_vs_baseline"
            lowers = t[k]["significant"] and t[k]["effect"] < 0
            comp[r] = lowers and np.mean(prim[r]) < 0.1
            dec[r] = (
                "competitive" if comp[r] else "lowers prices" if lowers else "no detectable effect"
            )
        a, b = comp["w6-limit-no-threat"], comp["w6-estimate-threat"]
        dec["wording_or_threat"] = (
            "either is enough"
            if a and b
            else "the wording"
            if a
            else "the threat"
            if b
            else "it takes both"
        )
    expl = {}
    if sets["w6-limit-no-threat"]:
        expl["follow_no_threat_11_99"] = follow(sets["w6-limit-no-threat"], range(11, 100))
    if sets["w6-estimate-threat"]:
        expl["follow_estimate_threat_11_99"] = follow(sets["w6-estimate-threat"], range(11, 100))
    if sets["w6-lifted"]:
        expl["follow_lifted_11_49"] = follow(sets["w6-lifted"], range(11, 50))
        expl["follow_lifted_would_have_51_99"] = follow(
            sets["w6-lifted"], range(51, 100), would_have=True
        )
    expl["follow_kept_51_99"] = follow(kept_games, range(51, 100))
    res = {
        "baseline": {"games": len(base), "index": float(np.mean(base))},
        "limit_kept": {"games": len(kept), "primary_index": float(np.mean(kept))},
        "rules": out,
        "tests": t,
        "decisions": dec,
        "exploratory": expl,
    }
    OUT.mkdir(exist_ok=True)
    (OUT / "wave6.json").write_text(json.dumps(res, indent=1, default=float))
    notes(sets)
    print(json.dumps(res, indent=1, default=float))
