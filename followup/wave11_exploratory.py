"""
Wave 11's exploratory numbers (followup/WAVE11_PLAN.md lists none of these; not part of the submission), chosen after
the planned analysis had run. wave11_results.py, whose hash launch.txt records, is left unchanged.

    limit      arm A's follow rate by game, rounds 11-99, against each game's index
    split      Sonnet and Haiku 5.5 under the cap: the games that held the cap, the round and prices of their dip,
               the games below 0.2, and two tests of the spread against the 15 baseline games (a permutation test of
               the log SD ratio and Fisher's exact test of the share below 0.2)
    openings   the opening prices under the cap, the prices above the cap after round 1, and the round each
               baseline game first fell below the cap's level
    notes      the codes in runs/wave11/notes_coded.jsonl, counted by arm and round, and the agreement of a second
               coder on 20 notes
    thinking   the share of each model's answered calls that reported thinking tokens

Usage:  uv run --extra analysis python followup/wave11_exploratory.py
Writes: followup/out/wave11_exploratory.json
"""

import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import fisher_exact

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "theory")]
import prevention45_results as p  # noqa: E402
import wave2_results as w2r  # noqa: E402
import wave11_results as w11  # noqa: E402

RUNS = w11.RUNS
CAP = w11.CAP
CAP_INDEX = None  # set from the games' benchmarks below
CODES = {
    "A": ("limit_mentioned", "limit_kept", "limit_set_aside", "penalty_inferred"),
    "cap": ("cap_best", "higher_blocked", "cut_lost", "plans_below_cap", "demand_unlearnable"),
}


def results(x: dict) -> dict:
    return json.loads((RUNS / "games/2_agents" / x["name"] / "results.json").read_text())


def market(x: dict) -> np.ndarray:
    return np.round(x["P"] * 1.0, 2)


def held(x: dict) -> dict | None:
    """A game that held the cap: every market price from round 2 at the cap, except in at most one round."""
    P = market(x)
    off = [t + 1 for t in range(1, 100) if (P[t] != CAP).any()]
    if len(off) > 1:
        return None
    t = off[0] if off else None
    return {
        "seed": x["seed"],
        "dip_round": t,
        "dip_prices": [float(v) for v in P[t - 1]] if t else [],
    }


def first_below(x: dict) -> int | None:
    P = market(x)
    return next((t + 1 for t in range(1, 100) if (P[t] < CAP - 1e-9).any()), None)


def spread_p(a, b, rng, n=50000) -> float:
    pool = np.concatenate([a, b])
    obs = abs(np.log(np.std(a, ddof=1) / np.std(b, ddof=1)))
    hits = 0
    for _ in range(n):
        rng.shuffle(pool)
        x, y = pool[: len(a)], pool[len(a) :]
        hits += abs(np.log(np.std(x, ddof=1) / np.std(y, ddof=1))) >= obs - 1e-12
    return hits / n


def cap_arm(xs, base, rng) -> dict:
    vals = np.array([w11.late(x) for x in xs])
    b = np.array([w11.late(x) for x in base])
    hold = [h for h in (held(x) for x in xs) if h]
    held_seeds = {h["seed"] for h in hold}
    others = [x for x in xs if x["seed"] not in held_seeds]
    below = vals < 0.2
    return {
        "games": len(xs),
        "held_cap": hold,
        "index_by_game": {str(x["seed"]): w11.late(x) for x in xs},
        "others_first_below_round": sorted(first_below(x) for x in others),
        "others_rounds_below_after_first": [
            int(sum((market(x)[t] < CAP - 1e-9).any() for t in range(first_below(x) - 1, 100)))
            - (101 - first_below(x))
            for x in others
        ],
        "at_cap_51_100": sorted(x["seed"] for x in xs if (market(x)[50:100] == CAP).all()),
        "firms_at_cap_51_100": int(
            sum((market(x)[50:100, i] == CAP).all() for x in xs for i in (0, 1))
        ),
        "one_firm_at_cap_51_100": [
            {"seed": x["seed"], "rival_mean_price": float(market(x)[50:100, 1 - i].mean())}
            for x in xs
            for i in (0, 1)
            if (market(x)[50:100, i] == CAP).all() and not (market(x)[50:100, 1 - i] == CAP).all()
        ],
        "below_0.2": int(below.sum()),
        "below_0.2_index": [float(vals[below].min()), float(vals[below].max())]
        if below.any()
        else None,
        "between_index": sorted(float(v) for v in vals if 0.2 <= v and abs(v - CAP_INDEX) > 1e-3),
        "baseline_below_0.2": int((b < 0.2).sum()),
        "baseline_min": float(b.min()),
        "baseline_max": float(b.max()),
        "sd": float(np.std(vals, ddof=1)),
        "baseline_sd": float(np.std(b, ddof=1)),
        "sd_p": spread_p(vals, b, rng),
        "below_0.2_fisher_p": float(
            fisher_exact(
                [
                    [below.sum(), len(vals) - below.sum()],
                    [(b < 0.2).sum(), len(b) - (b < 0.2).sum()],
                ]
            )[1]
        ),
        "opening_model_prices": sorted(
            {
                float(results(x)[f]["1"].get("model_price", results(x)[f]["1"]["chosen_price"]))
                for x in xs
                for f in ("Firm A", "Firm B")
            }
        ),
        "replaced_after_round_1": [
            {"seed": x["seed"], "firm": f, "round": int(t)}
            for x in xs
            for f, rows in results(x).items()
            for t, o in rows.items()
            if o.get("forced") and t != "1"
        ],
        "replaced_round_1": int(
            sum(bool(results(x)[f]["1"].get("forced")) for x in xs for f in ("Firm A", "Firm B"))
        ),
    }


def notes() -> dict:
    rows = [json.loads(line) for line in (RUNS / "notes_coded.jsonl").read_text().splitlines()]
    out = {}
    for arm in ("A", "B", "C"):
        codes = CODES["A"] if arm == "A" else CODES["cap"]
        out[arm] = {
            str(t): {
                c: sum(bool(r[c]) for r in rows if r["arm"] == arm and r["round"] == t)
                for c in codes
            }
            | {"notes": sum(1 for r in rows if r["arm"] == arm and r["round"] == t)}
            for t in w11.NOTE_ROUNDS
        }
    second = [
        json.loads(line) for line in (RUNS / "notes_coded_second20.jsonl").read_text().splitlines()
    ]
    first = {(r["arm"], r["seed"], r["round"], r["firm"]): r for r in rows}
    agree = total = 0
    for r in second:
        codes = CODES["A"] if r["arm"] == "A" else CODES["cap"]
        mine = first[(r["arm"], r["seed"], r["round"], r["firm"])]
        agree += sum(bool(r[c]) == bool(mine[c]) for c in codes)
        total += len(codes)
    out["second_coder"] = {"notes": len(second), "codes_agreeing": agree, "codes": total}
    return out


if __name__ == "__main__":
    rng = np.random.default_rng(1111)
    base = {
        f: w2r.family_games(f, ("baseline",))["baseline"] + w11.games(f, "none")
        for f in ("sonnet55", "haiku55")
    }
    arms = {a: w11.games(fam, rule) for a, (fam, rule, _) in w11.ARMS.items()}
    x0 = arms["C"][0]
    CAP_INDEX = float((CAP - x0["pn"]) / (x0["pm"] - x0["pn"]))
    out = {"cap": CAP, "cap_index": CAP_INDEX, "low_threshold": 0.2}
    res = json.loads((w11.OUT / "wave11.json").read_text())
    out["full_focal"] = {"index": w11.FULL_FOCAL} | {
        f: w11.FULL_FOCAL - b["pooled_index"] for f, b in res["baselines"].items()
    }
    follow = {x["seed"]: w11.follow([x], range(11, 100)) for x in arms["A"]}
    late = {x["seed"]: w11.late(x) for x in arms["A"]}
    kept = sorted(s for s in follow if follow[s] >= 0.5)
    rest = sorted(s for s in follow if follow[s] < 0.5)
    out["limit"] = {
        "follow_by_game": {str(s): follow[s] for s in sorted(follow)},
        "index_by_game": {str(s): late[s] for s in sorted(late)},
        "kept_games": kept,
        "kept_follow": [min(follow[s] for s in kept), max(follow[s] for s in kept)],
        "kept_index": [min(late[s] for s in kept), max(late[s] for s in kept)],
        "other_follow": [min(follow[s] for s in rest), max(follow[s] for s in rest)],
        "other_index": [min(late[s] for s in rest), max(late[s] for s in rest)],
    }
    out["cap_sonnet"] = cap_arm(arms["C"], base["sonnet55"], rng)
    out["cap_haiku"] = cap_arm(arms["B"], base["haiku55"], rng)
    first = sorted(int(np.argmax(p.index(x)[:100] < CAP_INDEX)) + 1 for x in base["sonnet55"])
    mean_path = np.mean([p.index(x)[:100] for x in base["sonnet55"]], axis=0)
    out["sonnet_baseline_opening"] = {
        "first_round_below_cap_level": [first[0], first[-1]],
        "mean_index_rounds_1_10_20": [
            float(mean_path[0]),
            float(mean_path[9]),
            float(mean_path[19]),
        ],
    }
    out["notes"] = notes()
    calls = [json.loads(line) for line in (RUNS / "usage.jsonl").read_text().splitlines()]
    calls = [c for c in calls if not c["is_error"] and c["model"] != "claude-haiku-4-5"]
    out["thinking_share"] = {
        m: float(np.mean([(c.get("thinking_tokens") or 0) > 0 for c in calls if c["model"] == m]))
        for m in sorted({c["model"] for c in calls})
    }
    out["answers"] = len(calls)
    (w11.OUT / "wave11_exploratory.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=1)[:4000])
