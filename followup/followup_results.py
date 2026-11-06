"""
Follow-up results (November 2026, after the sprint review; not part of the submission). Compares the three follow-up
arms of followup/duopoly_followup.py with the submission's Claude Haiku 4.5 baseline, best-response and forced-Nash
games, read unchanged through theory/prevention45_results.py. The outcome is Table 4's: the market index over rounds
51-100, each arm against the 20 baseline games, with Holm's correction over the three follow-up arms.

For the best-response arms it also measures deference as theory/deference_test.py does: how often an agent's next
price lands within 1% of the number it was shown, and how often within 1% of its true best response. Agents that
set a +10% number exactly would settle at index 0.62 (OBEDIENT).

Usage:  uv run --extra analysis python followup/followup_results.py
Writes: followup/out/followup.json, followup/out/followup.png
"""

import json
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "theory"))
import prevention45_results as p  # noqa: E402
from bandit import best_response, benchmarks  # noqa: E402

OUT = HERE / "out"
NEW = ("brinfo_noise", "brinfo_bias", "cut10")
REF = ("baseline", "brinfo", "forced10")
EST = re.compile(r"profit-maximizing price given the competitor'?s'? prices?: ([0-9.]+)")
LABELS = {
    "brinfo_noise": "best response, noisy (sd 10%)",
    "brinfo_bias": "best response, biased +10%",
    "cut10": "forced 10% cut every 10",
}
COLORS = {"brinfo_noise": "#2a6fdb", "brinfo_bias": "#d35400", "cut10": "#8e44ad"}
_submitted_arm_of = p.arm_of


def arm_of(name: str) -> str:
    arm = next((a for a in NEW if f"_{a}_" in name), None) or _submitted_arm_of(name)
    return arm if arm in REF + NEW else ""


def obedient_index(bias: float = 0.10) -> float:
    pn, pm = benchmarks(2)
    x = pn
    for _ in range(500):
        x = (1 + bias) * best_response(np.array([[x, x]]))[0, 0]
    return float((x - pn) / (pm - pn))


def deference(games: list) -> dict:
    shown, true = [], []
    for x in games:
        folder = next(d / x["name"] for d in p.RUNS if (d / x["name"]).exists())
        res = json.loads((folder / "results.json").read_text())
        firms = sorted(res)
        for t in range(11, 100):
            P = np.array([[res[f][str(t)]["chosen_price"] for f in firms]])
            for i, firm in enumerate(firms):
                m = EST.search(res[firm][str(t)]["market_data"])
                if not m:
                    continue
                nxt = res[firm][str(t + 1)]["chosen_price"]
                br = best_response(P if i == 0 else P[:, ::-1])[0, 0]
                shown.append(abs(np.log(nxt / float(m.group(1)))) < 0.01)
                true.append(abs(np.log(nxt / br)) < 0.01)
    return {
        "firm_rounds": len(shown),
        "within_1pct_of_shown": float(np.mean(shown)) if shown else None,
        "within_1pct_of_true_best_response": float(np.mean(true)) if true else None,
    }


def plot(g: dict, late: dict, rng, obedient: float):
    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(12.5, 4.4), gridspec_kw={"width_ratios": [1, 1.15]}, layout="constrained"
    )
    arms = [a for a in REF + NEW if a in late]
    for i, arm in enumerate(arms):
        y = len(arms) - 1 - i
        v = late[arm]
        ax1.scatter(
            v, y + rng.uniform(-0.15, 0.15, len(v)), s=14, color=p.COLORS[arm], alpha=0.8, lw=0
        )
        ax1.plot([v.mean()] * 2, [y - 0.32, y + 0.32], color="k", lw=1.6)
    ax1.set_yticks(
        range(len(arms)), [f"{p.LABELS[a]} ({len(late[a])})" for a in arms][::-1], fontsize=7.5
    )
    for xv, ls in ((0, "-"), (1, ":"), (obedient, "--")):
        ax1.axvline(xv, color="k", lw=0.5, ls=ls)
    ax1.set_xlabel(
        "market index, rounds 51-100 (dot = game, bar = mean; dashed = obeying the +10% number)"
    )
    k = np.arange(1, p.ROUNDS + 1)
    for arm in arms:
        P = np.array([p.index(x) for x in g[arm]])
        ax2.plot(k, P.mean(0), color=p.COLORS[arm], lw=1.4, label=p.LABELS[arm])
        lo, hi = np.percentile(
            P[rng.integers(len(P), size=(2000, len(P)))].mean(1), [2.5, 97.5], axis=0
        )
        ax2.fill_between(k, lo, hi, color=p.COLORS[arm], alpha=0.10)
    ax2.axhline(0, color="k", lw=0.5)
    ax2.axhline(obedient, color="k", lw=0.5, ls="--")
    ax2.set_ylim(-1.0, 2.5)
    ax2.set_xlabel("round")
    ax2.set_ylabel("market index (mean, 95% band)")
    ax2.legend(frameon=False, fontsize=7)
    fig.suptitle(
        "Follow-up (Nov 2026): Claude Haiku 4.5, thinking off, remedies from round 1", fontsize=10
    )
    fig.savefig(OUT / "followup.png", dpi=160)


if __name__ == "__main__":
    p.arm_of = arm_of
    p.RUNS = p.RUNS + [HERE / "runs/games/2_agents"]
    p.ARMS = REF + NEW
    p.LABELS.update(LABELS)
    p.COLORS.update(COLORS)
    rng = np.random.default_rng(2026)
    g = p.games()
    rows, late = p.summarise(g, rng)
    new = {r["arm"]: r for r in rows if r["arm"] in NEW and "p_permutation" in r}
    for arm, ph in p.holm({a: r["p_permutation"] for a, r in new.items()}).items():
        new[arm]["p_holm"] = (
            ph  # over the follow-up arms only; the submitted arms keep Table 4's correction
        )
    for r in rows:
        if r["arm"] in REF:
            r.pop("p_holm", None)
        if r["arm"] == "cut10":
            keep = [~x["forced"][p.LATE].any(1) for x in g["cut10"]]
            r["index_51_100_unforced_rounds"] = float(
                np.mean([p.index(x)[p.LATE][k].mean() for x, k in zip(g["cut10"], keep)])
            )
            r["share_firm_rounds_below_nash_51_100"] = float(
                np.mean([(x["P"][p.LATE] < x["pn"]).mean() for x in g["cut10"]])
            )
    obedient = obedient_index()
    res = {
        "obedient_index_for_bias": obedient,
        "rows": rows,
        "deference": {
            a: deference(g[a]) for a in ("brinfo", "brinfo_noise", "brinfo_bias") if g.get(a)
        },
        "games": {
            a: [
                {
                    "seed": int(x["seed"]),
                    "name": x["name"],
                    "index_51_100": float(p.index(x)[p.LATE].mean()),
                }
                for x in g[a]
            ]
            for a in p.ARMS
        },
    }
    OUT.mkdir(exist_ok=True)
    (OUT / "followup.json").write_text(json.dumps(res, indent=1, default=float))
    plot(g, late, rng, obedient)
    for r in rows:
        print(
            f"{r['label']:32s} n={r['games']:2d} index={r['index_51_100']:+.2f} high={r['share_above_0.3']:.0%} "
            f"effect={r.get('effect', 0):+.2f} {r.get('effect_ci', '')} p={r.get('p_permutation', float('nan')):.3f} "
            f"holm={r.get('p_holm', float('nan')):.3f} cs={r['cs_change_pct']:+.0f}%"
        )
    print(json.dumps(res["deference"], indent=1), f"\nobedient index for +10%: {obedient:.2f}")
