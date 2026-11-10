"""
Wave-11 results (study 2, followup/WAVE11_PLAN.md; not part of the submission): posted limits beyond Opus 5.5.

    primary      each arm's market index over rounds 51-100, every round counted at the price the market used,
                 against its model's 15 baseline games (wave 2's 10 and wave 11's 5) by a two-sided permutation
                 test (20,000 shuffles), Holm across A, B and C; a 95% bootstrap interval for each difference;
                 the plan's readings, and whether stage B or arm A2 is triggered
    secondary    the new baselines against wave 2's; each arm against its model's 5 new baselines alone; arm A's
                 follow rate (rounds 11-99); where firms in B and C priced against the cap over rounds 51-100
                 (under, at, above and replaced)
    exploratory  10-round blocks, games above 0.3, both firms' notes at rounds 30, 60 and 90 to
                 runs/wave11/notes.jsonl

Usage:  uv run --extra analysis python followup/wave11_results.py
Writes: followup/out/wave11.json, followup/runs/wave11/notes.jsonl
"""

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "theory")]
import prevention45_results as p  # noqa: E402
import wave2_results as w2r  # noqa: E402
import wave5_results as w5  # noqa: E402
import wave6_results as w6  # noqa: E402

OUT = HERE / "out"
RUNS = HERE / "runs/wave11"
CAP = 1.74
FULL_FOCAL = 0.55  # the index if prices settle just under the cap
COMPETITIVE, FOCAL_RISE = 0.1, 0.1
ARMS = {  # arm: family, rule name, games planned
    "A": ("sonnet55", "w6-limit-no-threat", 10),
    "B": ("haiku55", "w11-cap174", 10),
    "C": ("sonnet55", "w11-cap174", 20),
}
NOTE_ROUNDS = (30, 60, 90)


def games(family: str, rule: str) -> list:
    folder = RUNS / "games/2_agents"
    xs = [w5.load(f) for f in sorted(folder.glob(f"*_{family}_rule-{rule}_*"))]
    return sorted([x for x in xs if x["P"].shape[0] >= 100], key=lambda x: x["seed"])


def late(x: dict) -> float:
    return float(p.index(x)[50:100].mean())


def boot_diff(a, b, rng, n=10000) -> list:
    a, b = np.asarray(a), np.asarray(b)
    d = rng.choice(a, (n, len(a))).mean(1) - rng.choice(b, (n, len(b))).mean(1)
    return [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]


def reading(arm: str, diff: float, p_holm: float, level: float, ci: list, base: float) -> str:
    sig = p_holm < 0.05
    if arm == "A":
        if sig and diff < 0:
            return "obeys: competitive" if level < COMPETITIVE else "lowers, not competitive"
        return "no detectable effect"
    if sig and diff >= FOCAL_RISE:
        return "focal: the cap raises prices"
    if sig and diff > 0:
        return "raises prices a little"
    if sig and diff < 0:
        return "lowers prices"
    full = FULL_FOCAL - base
    return "no detectable effect; " + (
        "rules out the full focal effect"
        if ci[1] < full
        else "can't rule out the full focal effect"
    )


def where(xs: list) -> dict:
    """Shares of firm-rounds 51-100 whose own price was under the cap, at it (within 1% below) or above it."""
    under = at = above = 0
    for x in xs:
        res = json.loads((RUNS / "games/2_agents" / x["name"] / "results.json").read_text())
        for firm in res:
            for t in range(51, 101):
                o = res[firm][str(t)]
                own = float(o.get("model_price", o["chosen_price"]))
                if own > CAP + 1e-9:
                    above += 1
                elif own >= CAP * 0.99:
                    at += 1
                else:
                    under += 1
    n = under + at + above
    return {"under": under / n, "at": at / n, "above_replaced": above / n, "firm_rounds": n}


def follow(xs: list, rounds: range) -> float:
    """Share of firm-rounds whose next price is within 1% of the number shown, as in waves 5-7."""
    hits = []
    for x in xs:
        res = json.loads((RUNS / "games/2_agents" / x["name"] / "results.json").read_text())
        for t in rounds:
            for firm in sorted(res):
                m = w6.SHOWN.search(res[firm][str(t)]["market_data"])
                if m:
                    nxt = res[firm][str(t + 1)]
                    own = float(nxt.get("model_price", nxt["chosen_price"]))
                    hits.append(abs(np.log(own / float(m.group(1)))) < 0.01)
    return float(np.mean(hits)) if hits else None


def notes(xs: list):
    with open(RUNS / "notes.jsonl", "w") as fh:
        for arm, x in xs:
            res = json.loads((RUNS / "games/2_agents" / x["name"] / "results.json").read_text())
            for t in NOTE_ROUNDS:
                for firm in sorted(res):
                    o = res[firm][str(t)]
                    row = {
                        "arm": arm,
                        "game": x["name"],
                        "seed": x["seed"],
                        "round": t,
                        "firm": firm,
                    }
                    row.update(
                        {k: o.get(k) for k in ("observations", "plans", "insights", "chosen_price")}
                    )
                    fh.write(json.dumps(row) + "\n")


def blocks(xs: list) -> list:
    return [float(np.mean([p.index(x)[b : b + 10].mean() for x in xs])) for b in range(0, 100, 10)]


if __name__ == "__main__":
    rng = np.random.default_rng(11)
    base_old = {f: w2r.family_games(f, ("baseline",))["baseline"] for f in ("sonnet55", "haiku55")}
    base_new = {f: games(f, "none") for f in ("sonnet55", "haiku55")}
    base = {f: [late(x) for x in base_old[f] + base_new[f]] for f in base_old}
    arms = {arm: games(fam, rule) for arm, (fam, rule, _) in ARMS.items()}
    short = {arm: len(xs) for arm, xs in arms.items() if len(xs) != ARMS[arm][2]}
    if short or any(len(v) != 5 for v in base_new.values()):
        print(
            f"note: finished games differ from the plan: arms {short}, "
            f"new baselines {[len(v) for v in base_new.values()]}"
        )
    raw, out = {}, {"arms": {}, "baselines": {}}
    for arm, xs in arms.items():
        fam = ARMS[arm][0]
        vals = [late(x) for x in xs]
        raw[arm] = p.perm_p(vals, base[fam], rng)
        out["arms"][arm] = {
            "family": fam,
            "rule": ARMS[arm][1],
            "games": len(xs),
            "index_51_100": float(np.mean(vals)),
            "index_by_game": [round(v, 3) for v in vals],
            "games_above_0.3": int(sum(v > 0.3 for v in vals)),
            "difference": float(np.mean(vals) - np.mean(base[fam])),
            "difference_ci": boot_diff(vals, base[fam], rng),
            "p_raw": raw[arm],
            "blocks_10": blocks(xs),
        }
    adj = p.holm(raw)
    for arm, r in out["arms"].items():
        fam = r["family"]
        r["p_holm"] = adj[arm]
        r["reading"] = reading(
            arm,
            r["difference"],
            adj[arm],
            r["index_51_100"],
            r["difference_ci"],
            float(np.mean(base[fam])),
        )
    for fam, old_games in base_old.items():
        old, new = [late(x) for x in old_games], [late(x) for x in base_new[fam]]
        out["baselines"][fam] = {
            "pooled_index": float(np.mean(base[fam])),
            "pooled_sd": float(np.std(base[fam], ddof=1)),
            "wave2_index": float(np.mean(old)),
            "wave11_index": float(np.mean(new)) if new else None,
            "wave11_by_game": [round(v, 3) for v in new],
            "new_against_old_p": p.perm_p(new, old, rng) if new else None,
        }
    out["secondary"] = {
        "A_follow_11_99": follow(arms["A"], range(11, 100)) if arms["A"] else None,
        "where_against_cap": {arm: where(arms[arm]) for arm in ("B", "C") if arms[arm]},
        "against_wave11_baseline_only": {
            arm: {
                "difference": float(
                    r["index_51_100"] - np.mean([late(x) for x in base_new[r["family"]]])
                ),
                "p": p.perm_p(r["index_by_game"], [late(x) for x in base_new[r["family"]]], rng),
            }
            for arm, r in out["arms"].items()
            if base_new[r["family"]]
        },
    }
    focal = [a for a in ("B", "C") if out["arms"][a]["reading"].startswith("focal")]
    out["triggers"] = {
        "stage_B": bool(focal),
        "stage_B_because": focal,
        "arm_A2": not out["arms"]["A"]["reading"].startswith("obeys"),
    }
    (OUT / "wave11.json").write_text(json.dumps(out, indent=2))
    notes([(arm, x) for arm, xs in arms.items() for x in xs])
    for arm, r in out["arms"].items():
        print(
            f"{arm}: {r['index_51_100']:.3f} vs {out['baselines'][r['family']]['pooled_index']:.3f}, "
            f"diff {r['difference']:+.3f} {np.round(r['difference_ci'], 3)}, p {r['p_raw']:.4f} "
            f"(Holm {r['p_holm']:.4f}): {r['reading']}"
        )
    print("triggers:", out["triggers"])
