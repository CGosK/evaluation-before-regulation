"""
Prevention on a model that colludes: Claude Haiku 4.5 (extended thinking off), nine arms from round 1
(succession/prevention45.py), 100-round P1 duopolies through headless Claude Code.

The screen's 150-round games (succession/runs/screen) join the baseline (seeds 1-4) and thinking-on
(seeds 1-2) arms, cut at round 100: up to round 100 they are the same game.

Pre-set outcome: the market collusion index over rounds 51-100, each arm against baseline, two-sample
permutation test, with Holm's correction over the eight comparisons. Because the baseline is bimodal (games
either learn down or lock high), two robustness tests added after seeing the data: Fisher's exact test on the
share of games above 0.3, and a Mann-Whitney test. Also reported per arm:
    share of games above 0.3   the bimodal baseline: games either lock high or learn down
    profit index               (mean profit - Nash profit) / (monopoly profit - Nash profit), Lee's measure
    index 91-100               where games end: several arms are still descending at round 100
    move rate                  share of firm-rounds, 51-100, with a price change above 0.5%
    welfare                    consumer surplus, joint profit and total surplus per round at alpha = 1,
                               change from baseline in percent
    forced arm                 the index with the forced rounds left out, so the effect is not mechanical

Games are read from the committed copies in succession/runs/screen/games and succession/runs/prevention45/games
(copied from experiments_synthetic/experiments_runs/2_agents, which is not committed).

With --firms 4: the four-firm generalisation (baseline, forced10, brinfo; succession/runs/prevention45_4firm/games),
written with the suffix _4firm.

Usage:  uv run --extra analysis python theory/prevention45_results.py [--firms 4]
Writes: theory/out/prevention45{,_4firm}.csv, .json, .png
"""

import json
import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from scipy.stats import fisher_exact, mannwhitneyu

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from remedies_existing import welfare

ROOT = Path(__file__).resolve().parents[1]
RUNS = [ROOT / "succession/runs/screen/games", ROOT / "succession/runs/prevention45/games"]
OUT = Path(__file__).resolve().parent / "out"
MODEL = "claude-haiku-4-5"
ROUNDS = 100
LATE = slice(50, 100)  # rounds 51-100
ARMS = ("baseline", "p2", "forced10", "nashopen10", "brinfo", "rpe", "hidden", "reset50", "think4096")
LABELS = {"baseline": "baseline (P1)", "p2": "P2 prompt", "forced10": "forced Nash round every 10",
          "nashopen10": "Nash-held opening (1-10)", "brinfo": "best-response information",
          "rpe": "relative-performance pay", "hidden": "hidden rival prices", "reset50": "memory reset at 50",
          "think4096": "extended thinking on"}
COLORS = {"baseline": "#555555", "p2": "#2a6fdb", "forced10": "#c0392b", "nashopen10": "#e67e22",
          "brinfo": "#16a085", "rpe": "#8e44ad", "hidden": "#7f8c8d", "reset50": "#b7950b",
          "think4096": "#e84393"}


def arm_of(name: str) -> str:
    for tag, arm in (("_P2_", "p2"), ("_forced10_", "forced10"), ("_nashopen10_", "nashopen10"),
                     ("_brinfo_", "brinfo"), ("_rpe_", "rpe"), ("_hidden_", "hidden"), ("_reset50_", "reset50"),
                     ("_think4096_", "think4096")):
        if tag in name:
            return arm
    return "baseline" if "_think0_" in name else ""


def games() -> dict:
    """arm -> list of games, each {"seed", "P", "Pi", "forced", "pn", "pm", "pin", "pim"}, first 100 rounds."""
    out = {a: [] for a in ARMS}
    for f in sorted(f for d in RUNS for f in d.glob("*/results.json")):
        meta = json.loads((f.parent / "metadata.json").read_text())
        if MODEL not in str(meta.get("agents_models", "")) or meta.get("num_rounds", 0) < ROUNDS:
            continue  # other models, and the 2-3 round smoke tests
        arm = arm_of(f.parent.name)
        if not arm or (meta["num_rounds"] != ROUNDS and arm not in ("baseline", "think4096")):
            continue
        res = json.loads(f.read_text())
        if min(len(v) for v in res.values()) < meta["num_rounds"]:
            continue  # unfinished
        env = meta["environment"]["environment_params"]
        alpha = env["alpha"][0]
        firms = sorted(res)
        rec = [[res[firm][str(t)] for firm in firms] for t in range(1, ROUNDS + 1)]
        out[arm].append({
            "seed": meta["seed"], "name": f.parent.name,
            "P": np.array([[o["chosen_price"] for o in r] for r in rec]) / alpha,
            "Pi": np.array([[o["profit"] for o in r] for r in rec]),
            "forced": np.array([[bool(o.get("forced")) for o in r] for r in rec]),
            "pn": env["nash_prices"][0] / alpha, "pm": env["monopoly_prices"][0] / alpha,
            "pin": env["nash_profits"][0], "pim": env["monopoly_profits"][0]})
    return out


def index(g: dict) -> np.ndarray:
    return ((g["P"] - g["pn"]) / (g["pm"] - g["pn"])).mean(1)


def perm_p(a, b, rng, n=20000) -> float:
    a, b = np.asarray(a), np.asarray(b)
    pooled, obs = np.concatenate([a, b]), abs(a.mean() - b.mean())
    hits = 0
    for _ in range(n):
        rng.shuffle(pooled)
        hits += abs(pooled[:len(a)].mean() - pooled[len(a):].mean()) >= obs - 1e-12
    return hits / n


def holm(ps: dict) -> dict:
    order = sorted(ps, key=ps.get)
    out, running = {}, 0.0
    for i, k in enumerate(order):
        running = max(running, min(1.0, (len(order) - i) * ps[k]))
        out[k] = running
    return out


def summarise(g: dict, rng) -> tuple:
    rows, late = [], {}
    for arm in ARMS:
        G = g[arm]
        if not G:
            continue
        late[arm] = np.array([index(x)[LATE].mean() for x in G])
        w = [welfare(x["P"][LATE]) for x in G]
        dlog = [np.abs(np.diff(np.log(x["P"]), axis=0))[49:] for x in G]  # changes into rounds 51-100
        row = {"arm": arm, "label": LABELS[arm], "games": len(G), "seeds": sorted(int(x["seed"]) for x in G),
               "index_51_100": float(late[arm].mean()), "sd": float(late[arm].std(ddof=1)) if len(G) > 1 else None,
               "share_above_0.3": float((late[arm] > 0.3).mean()),
               "index_1_10": float(np.mean([index(x)[:10].mean() for x in G])),
               "index_91_100": float(np.mean([index(x)[90:].mean() for x in G])),
               "share_above_0.3_at_91_100": float(np.mean([index(x)[90:].mean() > 0.3 for x in G])),
               "profit_index_51_100": float(np.mean([((x["Pi"][LATE].mean(1) - x["pin"]) / (x["pim"] - x["pin"])).mean()
                                                    for x in G])),
               "move_rate_51_100": float(np.mean([(d > 0.005).mean() for d in dlog])),
               "cs": float(np.mean([v["cs"].mean() for v in w])), "profit": float(np.mean([v["profit"].mean() for v in w])),
               "ts": float(np.mean([v["ts"].mean() for v in w]))}
        if arm == "forced10":
            keep = [~x["forced"][LATE].any(1) for x in G]
            row["index_51_100_unforced_rounds"] = float(np.mean([index(x)[LATE][k].mean() for x, k in zip(G, keep)]))
        rows.append(row)
    base = next(r for r in rows if r["arm"] == "baseline")
    ps = {}
    for r in rows:
        for k in ("cs", "profit", "ts"):
            r[f"{k}_change_pct"] = 100 * (r[k] / base[k] - 1)
        if r["arm"] == "baseline" or len(late[r["arm"]]) < 2:
            continue
        a, b = late[r["arm"]], late["baseline"]
        diffs = [rng.choice(a, len(a)).mean() - rng.choice(b, len(b)).mean() for _ in range(5000)]
        r["effect"] = float(a.mean() - b.mean())
        r["effect_ci"] = np.percentile(diffs, [2.5, 97.5]).round(3).tolist()
        ps[r["arm"]] = r["p_permutation"] = perm_p(a, b, rng)
        hi_a, hi_b = int((a > 0.3).sum()), int((b > 0.3).sum())
        r["p_fisher_share_above_0.3"] = float(fisher_exact([[hi_a, len(a) - hi_a], [hi_b, len(b) - hi_b]])[1])
        r["p_mann_whitney"] = float(mannwhitneyu(a, b, alternative="two-sided").pvalue)
    for arm, p in holm(ps).items():
        next(r for r in rows if r["arm"] == arm)["p_holm"] = p
    return rows, late


def plot(g: dict, late: dict, rng, suffix: str = "", title: str = ""):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 4.6), gridspec_kw={"width_ratios": [1, 1.15]},
                                   layout="constrained")
    arms = [a for a in ARMS if a in late]
    for i, arm in enumerate(arms):
        y = len(arms) - 1 - i
        v = late[arm]
        ax1.scatter(v, y + rng.uniform(-0.15, 0.15, len(v)), s=14, color=COLORS[arm], alpha=0.8, lw=0)
        ax1.plot([v.mean()] * 2, [y - 0.32, y + 0.32], color="k", lw=1.6)
    ax1.set_yticks(range(len(arms)), [f"{LABELS[a]} ({len(late[a])})" for a in arms][::-1], fontsize=7.5)
    ax1.axvline(0, color="k", lw=0.5)
    ax1.axvline(1, color="k", lw=0.5, ls=":")
    ax1.set_xlabel("market index, rounds 51-100 (dot = game, bar = mean)")
    for arm in ("baseline", "p2", "forced10", "nashopen10", "brinfo", "think4096"):
        if not g.get(arm):
            continue
        P = np.array([index(x) for x in g[arm]])
        k = np.arange(1, ROUNDS + 1)
        ax2.plot(k, P.mean(0), color=COLORS[arm], lw=1.4, label=LABELS[arm])
        lo, hi = np.percentile(P[rng.integers(len(P), size=(2000, len(P)))].mean(1), [2.5, 97.5], axis=0)
        ax2.fill_between(k, lo, hi, color=COLORS[arm], alpha=0.10)
    ax2.axhline(0, color="k", lw=0.5)
    ax2.set_ylim(-0.4, 2.5)
    ax2.set_xlabel("round")
    ax2.set_ylabel("market index (mean, 95% band)")
    ax2.legend(frameon=False, fontsize=7)
    fig.suptitle(title, fontsize=10)
    fig.savefig(OUT / f"prevention45{suffix}.png", dpi=160)


if __name__ == "__main__":
    SUFFIX, TITLE = "", "Claude Haiku 4.5, thinking off: remedies from round 1"
    if "--firms" in sys.argv and sys.argv[sys.argv.index("--firms") + 1] == "4":
        RUNS, ARMS = [ROOT / "succession/runs/prevention45_4firm/games"], ("baseline", "forced10", "brinfo")
        SUFFIX, TITLE = "_4firm", "Claude Haiku 4.5, thinking off, four firms: remedies from round 1"
    rng = np.random.default_rng(45)
    g = games()
    rows, late = summarise(g, rng)
    pl.DataFrame([{k: v for k, v in r.items() if not isinstance(v, list)} for r in rows]).write_csv(
        OUT / f"prevention45{SUFFIX}.csv")
    (OUT / f"prevention45{SUFFIX}.json").write_text(json.dumps(
        {"rows": rows, "games": {a: [{"seed": int(x["seed"]), "name": x["name"],
                                       "index_51_100": float(index(x)[LATE].mean())} for x in g[a]] for a in ARMS}},
        indent=1, default=float))
    plot(g, late, rng, SUFFIX, TITLE)
    pl.Config.set_tbl_width_chars(250)
    pl.Config.set_tbl_cols(30)
    cols = ["label", "games", "index_51_100", "share_above_0.3", "index_91_100", "profit_index_51_100",
            "move_rate_51_100",
            "effect", "p_permutation", "p_holm", "p_fisher_share_above_0.3", "p_mann_whitney", "cs_change_pct",
            "profit_change_pct", "ts_change_pct"]
    t = pl.DataFrame([{c: r.get(c) for c in cols} for r in rows])
    print(t.with_columns(pl.col(pl.Float64).round(3)))
    for r in rows:
        if "effect_ci" in r:
            print(f"{r['label']}: effect {r['effect']:+.3f} {r['effect_ci']}")
        if "index_51_100_unforced_rounds" in r:
            print(f"forced arm, unforced rounds only: {r['index_51_100_unforced_rounds']:+.3f}")
