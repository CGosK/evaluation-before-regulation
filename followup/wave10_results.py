"""
Wave-10 results (study 1, followup/WAVE10_PLAN.md; not part of the submission): wave 7's 10 estimate games and
wave 3's 5 Opus 5.5 baseline games, continued from round 100 to round 200.

    primary      each game's change in index from rounds 51-100 to 151-200. The estimate arm's change by an
                 exact sign-flip test, and against the baseline arm's change by an exact permutation test, with
                 Holm across the two. The estimate arm's index over 151-200 with a bootstrap interval, and the
                 plan's reading
    secondary    the estimate arm's follow rate, rounds 11-99 against 101-199, by an exact sign-flip test
    exploratory  10-round blocks over rounds 1-200, the index in round 200, estimate games below 0.1 over
                 151-200, and both firms' notes at rounds 130, 160 and 190 to runs/wave10/notes.jsonl

Usage:  uv run --extra analysis python followup/wave10_results.py
Writes: followup/out/wave10.json, followup/runs/wave10/notes.jsonl
"""

import itertools
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "theory")]
import prevention45_results as p  # noqa: E402
import wave5_results as w5  # noqa: E402
import wave6_results as w6  # noqa: E402

OUT = HERE / "out"
RUNS = HERE / "runs/wave10"
ROUNDS = 200
FIRST, SECOND = (51, 100), (151, 200)
NOTE_ROUNDS = (130, 160, 190)
COMPETITIVE = 0.1


def window(i: np.ndarray, w: tuple) -> float:
    return float(i[w[0] - 1 : w[1]].mean())


def sign_flip_p(d) -> float:
    d = np.asarray(d, float)
    signs = np.array(list(itertools.product((1, -1), repeat=len(d))))
    return float(np.mean(np.abs((signs * d).mean(1)) >= abs(d.mean()) - 1e-12))


def perm_exact_p(a, b) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    pooled, obs, hits, n = np.concatenate([a, b]), abs(a.mean() - b.mean()), 0, 0
    for pick in itertools.combinations(range(len(pooled)), len(a)):
        mask = np.zeros(len(pooled), bool)
        mask[list(pick)] = True
        hits += abs(pooled[mask].mean() - pooled[~mask].mean()) >= obs - 1e-12
        n += 1
    return float(hits / n)


def boot_ci(x, rng, n=10000) -> list:
    x = np.asarray(x, float)
    means = rng.choice(x, (n, len(x))).mean(1)
    return [float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))]


def reading(change: float, change_p: float, did: float, did_p: float, level: float) -> str:
    if change_p < 0.05 and change > 0:
        return "fades: the estimate's effect wears off over a longer game"
    if change_p < 0.05 and did_p < 0.05 and did < 0:
        if level < COMPETITIVE:
            return "competitive: the estimate reaches competitive prices given time"
        return "keeps falling: the estimate keeps working past round 100 but is above competitive at 200"
    if change_p < 0.05:
        return "falls, not separated: the estimate arm falls, but not distinguishably from the baseline arm"
    return "stands: no change after round 100; the estimate takes prices only partway down"


def analyse(est: list, base: list, follow_first: list, follow_second: list, rng) -> dict:
    """est and base are per-game index series over rounds 1-200; the follow lists are per estimate game."""
    d_est = [window(i, SECOND) - window(i, FIRST) for i in est]
    d_base = [window(i, SECOND) - window(i, FIRST) for i in base]
    raw = {"change": sign_flip_p(d_est), "against_baseline": perm_exact_p(d_est, d_base)}
    adj = p.holm(raw)
    level = [window(i, SECOND) for i in est]
    change, did = float(np.mean(d_est)), float(np.mean(d_est) - np.mean(d_base))
    d_follow = np.asarray(follow_second) - np.asarray(follow_first)
    blocks = {
        arm: [float(np.mean([i[b : b + 10].mean() for i in xs])) for b in range(0, ROUNDS, 10)]
        for arm, xs in (("estimate", est), ("baseline", base))
    }
    return {
        "primary": {
            "estimate_index_51_100": float(np.mean([window(i, FIRST) for i in est])),
            "estimate_index_151_200": float(np.mean(level)),
            "estimate_index_151_200_ci": boot_ci(level, rng),
            "estimate_change": change,
            "estimate_change_by_game": [round(x, 3) for x in d_est],
            "baseline_index_51_100": float(np.mean([window(i, FIRST) for i in base])),
            "baseline_index_151_200": float(np.mean([window(i, SECOND) for i in base])),
            "baseline_change": float(np.mean(d_base)),
            "baseline_change_by_game": [round(x, 3) for x in d_base],
            "change_minus_baseline_change": did,
            "p_raw": raw,
            "p_holm": adj,
            "reading": reading(
                change, adj["change"], did, adj["against_baseline"], float(np.mean(level))
            ),
        },
        "secondary": {
            "follow_11_99": float(np.mean(follow_first)),
            "follow_101_199": float(np.mean(follow_second)),
            "follow_change_by_game": [round(float(x), 3) for x in d_follow],
            "p": sign_flip_p(d_follow),
        },
        "exploratory": {
            "blocks_10": blocks,
            "index_round_200": {
                "estimate": float(np.mean([i[ROUNDS - 1] for i in est])),
                "baseline": float(np.mean([i[ROUNDS - 1] for i in base])),
            },
            "estimate_games_below_0.1_151_200": int(sum(x < COMPETITIVE for x in level)),
        },
    }


def games(arm: str) -> list:
    pattern = "*_rule-w7-estimate-no-threat_*" if arm == "estimate" else "*_opus55_baseline_*"
    xs = [w5.load(f) for f in sorted((RUNS / "games/2_agents").glob(pattern))]
    short = [x["name"] for x in xs if x["P"].shape[0] < ROUNDS]
    if short:
        sys.exit(f"{arm}: {len(short)} games end before round {ROUNDS}: {short}")
    if any(x["forced"].any() for x in xs):
        sys.exit(f"{arm}: a price was overridden, which neither arm's rule does")
    return sorted(xs, key=lambda x: x["seed"])


def follow(x: dict, rounds: range) -> float:
    res = json.loads((RUNS / "games/2_agents" / x["name"] / "results.json").read_text())
    hits = []
    for t in rounds:
        for firm in sorted(res):
            m = w6.SHOWN.search(res[firm][str(t)]["market_data"])
            if m:
                hits.append(
                    abs(np.log(float(res[firm][str(t + 1)]["chosen_price"]) / float(m.group(1))))
                    < 0.01
                )
    return float(np.mean(hits))


def notes(xs: list):
    with open(RUNS / "notes.jsonl", "w") as fh:
        for x in xs:
            res = json.loads((RUNS / "games/2_agents" / x["name"] / "results.json").read_text())
            for t in NOTE_ROUNDS:
                for firm in sorted(res):
                    o = res[firm][str(t)]
                    row = {"game": x["name"], "seed": x["seed"], "round": t, "firm": firm}
                    row.update(
                        {k: o.get(k) for k in ("observations", "plans", "insights", "chosen_price")}
                    )
                    fh.write(json.dumps(row) + "\n")


if __name__ == "__main__":
    est, base = games("estimate"), games("baseline")
    if (len(est), len(base)) != (10, 5):
        print(
            f"note: {len(est)} estimate and {len(base)} baseline games finished; the plan has 10 and 5"
        )
    out = analyse(
        [p.index(x) for x in est],
        [p.index(x) for x in base],
        [follow(x, range(11, 100)) for x in est],
        [follow(x, range(101, 200)) for x in est],
        np.random.default_rng(10),
    )
    out["games"] = {"estimate": [x["name"] for x in est], "baseline": [x["name"] for x in base]}
    (OUT / "wave10.json").write_text(json.dumps(out, indent=2))
    notes(est + base)
    print(json.dumps(out["primary"], indent=2))
