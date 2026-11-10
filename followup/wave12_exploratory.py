"""
Wave 12's exploratory numbers (followup/WAVE12_PLAN.md lists none of these; not part of the submission), chosen after
the planned analysis had run. wave12_results.py, whose hash launch.txt records, is left unchanged.

    t4         T4's p-value, which sits near 0.05, with 1,000,000 shuffles, and by two other tests
    mixed      each game's index and own indices, each model's share of rounds at its true best response with no
               rule, each model's follow rate by game under A2, which side of the limit Sonnet's misses fell on, and
               each model's own index in the mixed market against its own baseline
    cap        C2's groups as in wave 11, C2 and wave 11's cap arm pooled, and the late cap's arrival: who was above
               it at round 30, what they did in round 31, every replacement, the rounds both firms sat at the cap, and
               the 10-round blocks against the baseline's
    notes      the codes in runs/wave12/notes_coded.jsonl by arm, round and model, and the agreement of a second coder
               on 30 notes
    thinking   the share of each model's calls that reported thinking tokens

Usage:  uv run --extra analysis python followup/wave12_exploratory.py
Writes: followup/out/wave12_exploratory.json
"""

import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import mannwhitneyu, ttest_ind

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "theory")]
import prevention45_results as p  # noqa: E402
import wave2_results as w2r  # noqa: E402
import wave3_results as w3  # noqa: E402
import wave8_results as w8  # noqa: E402
import wave12_results as w12  # noqa: E402

RUNS, CAP = w12.RUNS, w12.CAP
MIX = ("raise_to_lead", "rival_follows", "rival_undercuts")
LIM = ("limit_mentioned", "limit_kept", "limit_set_aside", "penalty_inferred")
CAPC = (
    "cap_mentioned",
    "cap_best",
    "higher_blocked",
    "cut_lost",
    "plans_below_cap",
    "demand_unlearnable",
)
CODES = {"mixed": MIX, "A2": MIX + LIM, "C2": CAPC, "D": CAPC}


def results(x: dict) -> dict:
    return json.loads((RUNS / "games/2_agents" / x["name"] / "results.json").read_text())


def market(x: dict) -> np.ndarray:
    return np.round(x["P"], 2)


def perm_big(a, b, rng, n=1_000_000, chunk=20_000) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    pool, k = np.concatenate([a, b]), len(a)
    obs = abs(a.mean() - b.mean())
    hits = 0
    for _ in range(n // chunk):
        s = pool[np.argsort(rng.random((chunk, len(pool))), axis=1)]
        hits += int((np.abs(s[:, :k].mean(1) - s[:, k:].mean(1)) >= obs - 1e-12).sum())
    return hits / n


def held(x: dict) -> dict | None:
    """Wave 11's definition: every market price from round 2 at the cap, except in at most one round."""
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


def replaced(xs: list) -> list:
    return [
        {"seed": x["seed"], "firm": f, "round": int(t), "model_price": float(o["model_price"])}
        for x in xs
        for f, rows in results(x).items()
        for t, o in rows.items()
        if o.get("forced")
    ]


def cap_groups(xs: list, cap_index: float) -> dict:
    vals = {x["seed"]: w12.late(x) for x in xs}
    hold = [h for h in (held(x) for x in xs) if h]
    held_seeds = {h["seed"] for h in hold}
    others = [x for x in xs if x["seed"] not in held_seeds]
    low = sorted(v for v in vals.values() if v < w12.LOW)
    return {
        "index_by_game": {str(s): v for s, v in sorted(vals.items())},
        "held_cap": hold,
        "at_cap_51_100": sorted(x["seed"] for x in xs if w12.held(x)),
        "others_first_below_round": sorted(first_below(x) for x in others),
        "others_rounds_without_a_price_below_after_first": [
            int(sum(not (market(x)[t] < CAP - 1e-9).any() for t in range(first_below(x) - 1, 100)))
            for x in others
        ],
        "below_0.2": [low[0], low[-1]] if low else None,
        "between": sorted(v for v in vals.values() if v >= w12.LOW and abs(v - cap_index) > 1e-3),
        "firms_at_cap_51_100": int(
            sum((market(x)[50:100, i] == CAP).all() for x in xs for i in (0, 1))
        ),
        "one_firm_at_cap_51_100": [
            {"seed": x["seed"], "rival_mean_price": float(market(x)[50:100, 1 - i].mean())}
            for x in xs
            for i in (0, 1)
            if (market(x)[50:100, i] == CAP).all() and not (market(x)[50:100, 1 - i] == CAP).all()
        ],
    }


def blocks(xs: list) -> list:
    return [float(np.mean([p.index(x)[b : b + 10].mean() for x in xs])) for b in range(0, 100, 10)]


def mixed_part(mx: list, a2: list, rng) -> dict:
    out = {}
    for arm, xs in (("mixed", mx), ("A2", a2)):
        out[arm] = {
            "slots": {str(x["seed"]): x["models"] for x in xs},
            "index_by_game": {str(x["seed"]): w12.late(x) for x in xs},
            "own_by_game": {
                f: {str(x["seed"]): w12.own(x, f) for x in xs} for f in ("opus55", "sonnet55")
            },
        }
    out["mixed"]["opus_above_sonnet"] = int(
        sum(w12.own(x, "opus55") > w12.own(x, "sonnet55") for x in mx)
    )
    out["mixed"]["at_best_response"] = {
        f: float(
            np.concatenate([w8.at_best_response(x["P"], x["models"].index(f)) for x in mx]).mean()
        )
        for f in ("opus55", "sonnet55")
    }
    out["mixed"]["sonnet_at_best_response_against_itself"] = w8.br_share_self(sonnet_baseline())
    out["A2"]["follow_by_game"] = {
        f: {str(x["seed"]): w12.follow([x], f) for x in a2} for f in ("opus55", "sonnet55")
    }
    above = below = 0
    for x in a2:
        res = results(x)
        firm = sorted(res)[x["models"].index("sonnet55")]
        for t in range(11, 100):
            m = w12.w6.SHOWN.search(res[firm][str(t)]["market_data"])
            nxt = float(res[firm][str(t + 1)]["chosen_price"])
            if m and abs(np.log(nxt / float(m.group(1)))) >= 0.01:
                above += nxt > float(m.group(1))
                below += nxt < float(m.group(1))
    out["A2"]["sonnet_misses"] = {"above": above, "below": below}
    opus_base = [w12.late(x) for x in w3.opus_games()["baseline"]]
    sonnet_base = [w12.late(x) for x in sonnet_baseline()]
    out["own_against_baseline"] = {
        "opus55": {
            "baseline": float(np.mean(opus_base)),
            "baseline_games": len(opus_base),
            "mixed": float(np.mean([w12.own(x, "opus55") for x in mx])),
            "p": p.perm_p([w12.own(x, "opus55") for x in mx], opus_base, rng),
        },
        "sonnet55": {
            "baseline": float(np.mean(sonnet_base)),
            "baseline_games": len(sonnet_base),
            "mixed": float(np.mean([w12.own(x, "sonnet55") for x in mx])),
            "p": p.perm_p([w12.own(x, "sonnet55") for x in mx], sonnet_base, rng),
        },
    }
    return out


def sonnet_baseline() -> list:
    return (
        w2r.family_games("sonnet55", ("baseline",))["baseline"]
        + w12.single("sonnet55", "none", w12.W11)
        + w12.single("sonnet55", "none")
    )


def late_cap(d: list, base: list) -> dict:
    above30 = [(x, i) for x in d for i in (0, 1) if x["P"][29, i] > CAP + 1e-9]
    r31 = [float(market(x)[30, i]) for x, i in above30]
    both = [(market(x)[30:100] == CAP).all(1) for x in d]
    runs = [
        max((len(s) for s in "".join("1" if v else "0" for v in b).split("0")), default=0)
        for b in both
    ]
    bd, bb = blocks(d), blocks(base)
    return {
        "index_by_game": {str(x["seed"]): w12.late(x) for x in d},
        "games_above_cap_round_30": len({x["seed"] for x, _ in above30}),
        "firms_above_cap_round_30": len(above30),
        "round_30_prices_above": [float(np.round(x["P"][29, i], 2)) for x, i in above30],
        "their_round_31_prices": r31,
        "round_31_at_cap": int(sum(v == CAP for v in r31)),
        "replaced": replaced(d),
        "firm_rounds_at_cap_31_100": int(sum((market(x)[30:100] == CAP).sum() for x in d)),
        "firm_rounds_31_100": 2 * 70 * len(d),
        "share_at_cap_31_100": float(
            sum((market(x)[30:100] == CAP).sum() for x in d) / (2 * 70 * len(d))
        ),
        "games_both_at_cap_some_round": int(sum(b.any() for b in both)),
        "longest_both_at_cap_run": max(runs),
        "index_round_30": {
            "D": float(np.mean([p.index(x)[29] for x in d])),
            "baseline": float(np.mean([p.index(x)[29] for x in base])),
        },
        "blocks": {"D": bd, "baseline": bb, "difference": [a - b for a, b in zip(bd, bb)]},
        "below_0.2": int(sum(w12.late(x) < w12.LOW for x in d)),
        "baseline_below_0.2": int(sum(w12.late(x) < w12.LOW for x in base)),
        "min": float(min(w12.late(x) for x in d)),
        "max": float(max(w12.late(x) for x in d)),
        "baseline_min": float(min(w12.late(x) for x in base)),
        "baseline_max": float(max(w12.late(x) for x in base)),
    }


def notes() -> dict | None:
    path = RUNS / "notes_coded.jsonl"
    if not path.exists():
        return None
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    out = {}
    for arm, codes in CODES.items():
        mine = [r for r in rows if r["arm"] == arm]
        groups = sorted({r["model"] for r in mine}) if arm in ("mixed", "A2") else ["sonnet55"]
        out[arm] = {}
        for m in groups:
            sub = [r for r in mine if r["model"] == m]
            by_round = {
                str(t): {c: sum(bool(r[c]) for r in sub if r["round"] == t) for c in codes}
                | {"notes": sum(1 for r in sub if r["round"] == t)}
                for t in sorted({r["round"] for r in sub})
            }
            firms = {(r["seed"], r["firm"]) for r in sub}
            any_note = {
                c: sum(any(r[c] for r in sub if (r["seed"], r["firm"]) == k) for k in firms)
                for c in codes
            } | {"firms": len(firms)}
            out[arm][m] = {"by_round": by_round, "firms_any_note": any_note}
    c2 = {
        t: {
            (r["seed"], r["firm"])
            for r in rows
            if r["arm"] == "C2" and r["round"] == t and r["cap_best"]
        }
        for t in w12.NOTE_ROUNDS
    }
    held_firms = {
        (x["seed"], f)
        for x in w12.single("sonnet55", "w11-cap174")
        for i, f in enumerate(sorted(results(x)))
        if (market(x)[50:100, i] == CAP).all()
    }
    out["C2_cap_best"] = {
        "same_firms_each_round": len({frozenset(v) for v in c2.values()}) == 1,
        "are_the_firms_at_the_cap_51_100": c2[30] == held_firms,
        "also_plan_below_cap": sum(
            1 for r in rows if r["arm"] == "C2" and r["cap_best"] and r["plans_below_cap"]
        ),
        "all_others_plan_below_cap": all(
            r["plans_below_cap"] for r in rows if r["arm"] == "C2" and not r["cap_best"]
        ),
    }
    second = [
        json.loads(line) for line in (RUNS / "notes_coded_second30.jsonl").read_text().splitlines()
    ]
    first = {(r["arm"], r["seed"], r["round"], r["firm"]): r for r in rows}
    agree = total = 0
    for r in second:
        a = first[(r["arm"], r["seed"], r["round"], r["firm"])]
        agree += sum(bool(r[c]) == bool(a[c]) for c in CODES[r["arm"]])
        total += len(CODES[r["arm"]])
    out["second_coder"] = {"notes": len(second), "codes_agreeing": agree, "codes": total}
    out["notes"] = len(rows)
    return out


if __name__ == "__main__":
    rng = np.random.default_rng(1212)
    res = json.loads((w12.OUT / "wave12.json").read_text())
    mx, a2 = w12.mixed("none"), w12.mixed("w6-limit-no-threat")
    c2 = w12.single("sonnet55", "w11-cap174")
    d = w12.single("sonnet55", "w12-cap174-from31")
    base = sonnet_baseline()
    vd, vb = [w12.late(x) for x in d], [w12.late(x) for x in base]
    assert abs(np.mean(vd) - res["part2"]["D"]["index"]) < 1e-12
    assert abs(np.mean(vb) - res["part2"]["baseline_index"]) < 1e-12
    x0 = c2[0]
    cap_index = float((CAP - x0["pn"]) / (x0["pm"] - x0["pn"]))
    out = {"cap_index": cap_index}
    out["t4"] = {
        "p_1m": perm_big(vd, vb, rng),
        "shuffles": 1_000_000,
        "mann_whitney_p": float(mannwhitneyu(vd, vb, alternative="two-sided").pvalue),
        "welch_p": float(ttest_ind(vd, vb, equal_var=False).pvalue),
    }
    out["mixed"] = mixed_part(mx, a2, rng)
    w11c = w12.single("sonnet55", "w11-cap174", w12.W11)
    out["cap"] = {
        "C2": cap_groups(c2, cap_index)
        | {
            "replaced": replaced(c2),
            "opening_model_prices": sorted(
                {r["model_price"] for r in replaced(c2) if r["round"] == 1}
            ),
        },
        "pooled_with_wave11": {
            "games": len(c2) + len(w11c),
            "held_cap": int(sum(w12.held(x) for x in c2 + w11c)),
            "below_0.2": int(sum(w12.late(x) < w12.LOW for x in c2 + w11c)),
        },
        "D": late_cap(d, base),
    }
    out["notes"] = notes()
    calls = [json.loads(line) for line in (RUNS / "usage.jsonl").read_text().splitlines()]
    out["thinking_share"] = {
        m: float(np.mean([(c.get("thinking_tokens") or 0) > 0 for c in calls if c["model"] == m]))
        for m in sorted({c["model"] for c in calls})
    }
    out["answers"] = len(calls)
    (w12.OUT / "wave12_exploratory.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=1)[:6000])
