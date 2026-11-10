"""
Wave-12 results (study 3, followup/WAVE12_PLAN.md; not part of the submission): the limit in a mixed market,
and the cap's split.

    part 1       the mixed market's index over rounds 51-100, under the limit (A2) against no rule (mixed), by a
                 two-sided permutation test (20,000 shuffles) with a 95% bootstrap interval; the plan's reading
    part 2       three tests with Holm: the spread of C2 (wave 11's cap, fresh games) against Sonnet's 20 baseline
                 games (log SD ratio, permutation); games held at the cap, D (the cap from round 31) against C2
                 (Fisher's exact test); D's index against the baseline (permutation); the plan's readings
    secondary    each model's own index in the mixed arms; each model's follow rate under A2 (rounds 11-99);
                 Sonnet's own index under A2 against wave 11's Sonnet-only limit games; C2's mean and D's spread
                 against the baseline; the new baselines against the earlier 15; where firms priced against the
                 cap over rounds 51-100; how many D games had a price above the cap in round 30
    exploratory  10-round blocks; both firms' notes at rounds 30, 60 and 90 (and 32 in D) to
                 runs/wave12/notes.jsonl

Usage:  uv run --extra analysis python followup/wave12_results.py
Writes: followup/out/wave12.json, followup/runs/wave12/notes.jsonl
"""

import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import fisher_exact

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "theory")]
import bandit  # noqa: E402
import prevention45_results as p  # noqa: E402
import wave2_results as w2r  # noqa: E402
import wave5_results as w5  # noqa: E402
import wave6_results as w6  # noqa: E402

OUT = HERE / "out"
RUNS = HERE / "runs/wave12"
W11 = HERE / "runs/wave11/games/2_agents"
CAP = 1.74
FULL_FOCAL = 0.55
COMPETITIVE, FOCAL_RISE, LOW = 0.1, 0.1, 0.2
MIXED = "opus55+sonnet55"
MODELS = {"claude-opus-5-5": "opus55", "claude-sonnet-5-5": "sonnet55"}
NOTE_ROUNDS = (30, 60, 90)
D_EXTRA = 32  # the first notes written after a round under the cap


def folder_games(folder: Path, pattern: str, rounds: int = 100) -> list:
    xs = []
    for f in sorted(folder.glob(pattern)):
        x = w5.load(f)
        if x["P"].shape[0] >= rounds:
            meta = json.loads((f / "metadata.json").read_text())
            x["models"] = [
                MODELS.get(meta["agents_models"][k], "") for k in sorted(meta["agents_models"])
            ]
            xs.append(x)
    return sorted(xs, key=lambda x: x["seed"])


def single(family: str, rule: str, folder: Path = RUNS / "games/2_agents") -> list:
    return folder_games(folder, f"*_{family}_rule-{rule}_*")


def mixed(rule: str) -> list:
    return folder_games(RUNS / "games/2_agents", f"*_mixed-{MIXED}_rule-{rule}_*")


def late(x: dict) -> float:
    return float(p.index(x)[50:100].mean())


def own(x: dict, family: str) -> float:
    i = x["models"].index(family)
    return float(((x["P"][50:100, i] - x["pn"]) / (x["pm"] - x["pn"])).mean())


def held(x: dict) -> bool:
    """Every market price over rounds 51-100 at the cap."""
    return bool((np.round(x["P"][50:100], 2) == CAP).all())


def boot_diff(a, b, rng, n=10000) -> list:
    a, b = np.asarray(a), np.asarray(b)
    d = rng.choice(a, (n, len(a))).mean(1) - rng.choice(b, (n, len(b))).mean(1)
    return [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]


def spread_p(a, b, rng, n=20000) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    pool = np.concatenate([a, b])
    obs = abs(np.log(np.std(a, ddof=1) / np.std(b, ddof=1)))
    hits = 0
    for _ in range(n):
        rng.shuffle(pool)
        x, y = pool[: len(a)], pool[len(a) :]
        hits += abs(np.log(np.std(x, ddof=1) / np.std(y, ddof=1))) >= obs - 1e-12
    return hits / n


def follow(xs: list, family: str, rounds: range = range(11, 100)) -> float | None:
    """Share of the family's firm-rounds whose next price is within 1% of the limit shown, as in waves 5-7."""
    hits = []
    for x in xs:
        res = json.loads((RUNS / "games/2_agents" / x["name"] / "results.json").read_text())
        firm = sorted(res)[x["models"].index(family)]
        for t in rounds:
            m = w6.SHOWN.search(res[firm][str(t)]["market_data"])
            if m:
                nxt = res[firm][str(t + 1)]
                price = float(nxt.get("model_price", nxt["chosen_price"]))
                hits.append(abs(np.log(price / float(m.group(1)))) < 0.01)
    return float(np.mean(hits)) if hits else None


def where(xs: list) -> dict:
    """Shares of firm-rounds 51-100 whose own price was under the cap, at it (within 1% below) or above it."""
    under = at = above = 0
    for x in xs:
        res = json.loads((RUNS / "games/2_agents" / x["name"] / "results.json").read_text())
        for firm in res:
            for t in range(51, 101):
                o = res[firm][str(t)]
                price = float(o.get("model_price", o["chosen_price"]))
                if price > CAP + 1e-9:
                    above += 1
                elif price >= CAP * 0.99:
                    at += 1
                else:
                    under += 1
    n = under + at + above
    return {"under": under / n, "at": at / n, "above_replaced": above / n, "firm_rounds": n}


def blocks(xs: list) -> list:
    return [float(np.mean([p.index(x)[b : b + 10].mean() for x in xs])) for b in range(0, 100, 10)]


def leader_follower() -> float:
    """The market index if one firm sets its best response to the other's price and the other leads."""
    grid = np.arange(1.40, 2.60, 0.001)
    fol = [float(bandit.best_response(np.array([[0.0, g]]))[0, 0]) for g in grid]
    i = int(np.argmax([bandit.profits(np.array([[g, b]]))[0][0] for g, b in zip(grid, fol)]))
    pn, pm = (float(v) for v in bandit.benchmarks(2))
    return float(np.mean([(v - pn) / (pm - pn) for v in (grid[i], fol[i])]))


def reading_limit(diff: float, pv: float, level: float) -> str:
    if pv < 0.05 and diff < 0:
        return "holds: competitive" if level < COMPETITIVE else "partway, not competitive"
    if pv < 0.05:
        return "raises prices"
    return "no detectable effect"


def reading_split(p_holm: float, sd: float, base_sd: float, n_held: int, n_low: int) -> str:
    if p_holm < 0.05 and sd > base_sd:
        return "the split replicates" if n_held >= 3 and n_low >= 3 else "wider, but not split"
    if p_holm < 0.05:
        return "narrower than baseline"
    return "doesn't replicate"


def reading_opening(p_holm: float, held_d: int, held_c: int) -> str:
    if p_holm < 0.05:
        return (
            "the opening drives the split" if held_d < held_c else "the late cap holds more games"
        )
    return "no detectable difference"


def reading_focal(diff: float, p_holm: float, ci: list, base: float) -> str:
    if p_holm < 0.05 and diff >= FOCAL_RISE:
        return "focal: the late cap raises prices"
    if p_holm < 0.05 and diff > 0:
        return "raises prices a little"
    if p_holm < 0.05:
        return "lowers prices"
    full = FULL_FOCAL - base
    return "no detectable effect; " + (
        "rules out the full focal effect"
        if ci[1] < full
        else "can't rule out the full focal effect"
    )


def notes(rows: list):
    with open(RUNS / "notes.jsonl", "w") as fh:
        for arm, x in rows:
            res = json.loads((RUNS / "games/2_agents" / x["name"] / "results.json").read_text())
            for t in NOTE_ROUNDS + ((D_EXTRA,) if arm == "D" else ()):
                for i, firm in enumerate(sorted(res)):
                    o = res[firm][str(t)]
                    row = {
                        "arm": arm,
                        "game": x["name"],
                        "seed": x["seed"],
                        "round": t,
                        "firm": firm,
                    }
                    row["model"] = x["models"][i] or "sonnet55"
                    row.update(
                        {k: o.get(k) for k in ("observations", "plans", "insights", "chosen_price")}
                    )
                    fh.write(json.dumps(row) + "\n")


if __name__ == "__main__":
    rng = np.random.default_rng(12)
    out = {"part1": {}, "part2": {}, "secondary": {}, "exploratory": {}}
    planned = {"mixed": 10, "A2": 10, "C2": 20, "D": 20, "sonnet_baseline": 5}

    # part 1: the limit in a mixed market
    mx, a2 = mixed("none"), mixed("w6-limit-no-threat")
    if not (mx and a2):
        sys.exit(f"part 1 needs both mixed arms: found {len(mx)} and {len(a2)} games")
    vm, va = [late(x) for x in mx], [late(x) for x in a2]
    p1 = p.perm_p(va, vm, rng)
    d1 = float(np.mean(va) - np.mean(vm))
    out["part1"] = {
        "games": {"mixed": len(mx), "A2": len(a2)},
        "mixed_index": float(np.mean(vm)),
        "A2_index": float(np.mean(va)),
        "index_by_game": {"mixed": [round(v, 3) for v in vm], "A2": [round(v, 3) for v in va]},
        "difference": d1,
        "difference_ci": boot_diff(va, vm, rng),
        "p": p1,
        "reading": reading_limit(d1, p1, float(np.mean(va))),
        "leader_follower_index": leader_follower(),
    }

    # part 2: the cap's split
    base_old = w2r.family_games("sonnet55", ("baseline",))["baseline"] + single(
        "sonnet55", "none", W11
    )
    base_new = single("sonnet55", "none")
    base = [late(x) for x in base_old + base_new]
    c2, d = single("sonnet55", "w11-cap174"), single("sonnet55", "w12-cap174-from31")
    vc, vd = [late(x) for x in c2], [late(x) for x in d]
    hc, hd = sum(held(x) for x in c2), sum(held(x) for x in d)
    raw = {
        "spread_C2": spread_p(vc, base, rng),
        "held_D_vs_C2": float(fisher_exact([[hd, len(d) - hd], [hc, len(c2) - hc]])[1]),
        "index_D": p.perm_p(vd, base, rng),
    }
    adj = p.holm(raw)
    sd_c, sd_b = float(np.std(vc, ddof=1)), float(np.std(base, ddof=1))
    low_c = int(sum(v < LOW for v in vc))
    ci_d = boot_diff(vd, base, rng)
    out["part2"] = {
        "games": {"C2": len(c2), "D": len(d), "baseline": len(base), "new_baseline": len(base_new)},
        "baseline_index": float(np.mean(base)),
        "baseline_sd": sd_b,
        "C2": {
            "index": float(np.mean(vc)),
            "index_by_game": [round(v, 3) for v in vc],
            "sd": sd_c,
            "held_cap": hc,
            "below_0.2": low_c,
        },
        "D": {
            "index": float(np.mean(vd)),
            "index_by_game": [round(v, 3) for v in vd],
            "sd": float(np.std(vd, ddof=1)),
            "held_cap": hd,
            "below_0.2": int(sum(v < LOW for v in vd)),
            "difference": float(np.mean(vd) - np.mean(base)),
            "difference_ci": ci_d,
        },
        "p_raw": raw,
        "p_holm": adj,
        "readings": {
            "split": reading_split(adj["spread_C2"], sd_c, sd_b, hc, low_c),
            "opening": reading_opening(adj["held_D_vs_C2"], hd, hc),
            "late_cap": reading_focal(
                float(np.mean(vd) - np.mean(base)), adj["index_D"], ci_d, float(np.mean(base))
            ),
        },
    }
    focal = out["part2"]["readings"]["late_cap"].startswith("focal")
    out["follows"] = {"own_project": focal, "stop": not focal}

    # secondary
    a11 = single("sonnet55", "w6-limit-no-threat", W11)
    out["secondary"] = {
        "own_index": {
            arm: {f: float(np.mean([own(x, f) for x in xs])) for f in ("opus55", "sonnet55")}
            for arm, xs in (("mixed", mx), ("A2", a2))
            if xs
        },
        "follow_A2_11_99": {f: follow(a2, f) for f in ("opus55", "sonnet55")} if a2 else None,
        "sonnet_own_A2_vs_wave11_limit": {
            "A2": float(np.mean([own(x, "sonnet55") for x in a2])) if a2 else None,
            "wave11": float(np.mean([late(x) for x in a11])),
            "p": p.perm_p([own(x, "sonnet55") for x in a2], [late(x) for x in a11], rng)
            if a2
            else None,
        },
        "C2_index_vs_baseline": {
            "difference": float(np.mean(vc) - np.mean(base)),
            "p": p.perm_p(vc, base, rng),
        },
        "D_spread_vs_baseline_p": spread_p(vd, base, rng),
        "new_vs_earlier_baselines_p": p.perm_p(
            [late(x) for x in base_new], [late(x) for x in base_old], rng
        )
        if base_new
        else None,
        "where_against_cap": {arm: where(xs) for arm, xs in (("C2", c2), ("D", d)) if xs},
        "D_above_cap_in_round_30": int(sum((x["P"][29] > CAP + 1e-9).any() for x in d)),
    }
    out["exploratory"] = {
        "blocks_10": {
            arm: blocks(xs) for arm, xs in (("mixed", mx), ("A2", a2), ("C2", c2), ("D", d)) if xs
        }
    }
    found = {
        "mixed": len(mx),
        "A2": len(a2),
        "C2": len(c2),
        "D": len(d),
        "sonnet_baseline": len(base_new),
    }
    if found != planned:
        print(f"note: finished games differ from the plan: {found} against {planned}")
    (OUT / "wave12.json").write_text(json.dumps(out, indent=2))
    notes([(a, x) for a, xs in (("mixed", mx), ("A2", a2), ("C2", c2), ("D", d)) for x in xs])
    p1o = out["part1"]
    print(
        f"part 1: A2 {p1o['A2_index']:.3f} vs mixed {p1o['mixed_index']:.3f}, diff {p1o['difference']:+.3f} "
        f"{np.round(p1o['difference_ci'], 3)}, p {p1o['p']:.4f}: {p1o['reading']}"
    )
    for k, v in raw.items():
        print(f"part 2 {k}: p {v:.4f} (Holm {adj[k]:.4f})")
    print("readings:", out["part2"]["readings"], "follows:", out["follows"])
