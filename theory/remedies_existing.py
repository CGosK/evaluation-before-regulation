"""
What the data already collected says about remedies, with no new model calls.

A. Prompt design as prevention (Mistral-Large, the thesis's randomized prompts, games played from round 1).
   P2 differs from P1 only in its instruction: keep exploring, try aggressive options, remember that pricing
   below the competitor sells more, and lock in only when confident. Effect of P2 vs P1 on the market
   collusion index over rounds 251-300, by number of firms, with a two-sample permutation test.
B. A forced price experiment as a remedy (Claude Haiku 5.5 and Fable 5.1, the forced-cut runs).
   Market index after one round in which Firm B is forced to Nash, deviate minus control, paired by state.
C. Welfare. Consumer surplus (logit inclusive value), joint profit and total surplus, in the market's own
   units at alpha = 1, for A, B and the mechanism arms (removal: rounds B+13..B+24; prevention: 51-100).

Usage:  uv run --extra analysis python theory/remedies_existing.py
Writes: theory/out/remedies_existing.json, theory/out/prompt_prevention.png
"""

import glob
import itertools
import json
import os
import zlib
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from bandit import benchmarks, load

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "out"
RNG = np.random.default_rng(11)


def reseed(*key) -> None:
    """Each analysis restarts the random stream from its own fixed seed, so its intervals do not move when
    other analyses (or models) are added before it."""
    global RNG
    RNG = np.random.default_rng([11, zlib.crc32(repr(key).encode())])
MU, A, C, BETA = 0.25, 2.0, 1.0, 100.0


def welfare(P: np.ndarray) -> dict:
    """Per-round consumer surplus, joint profit and total surplus; P is rounds x firms at alpha = 1."""
    e = np.exp((A - P) / MU)
    denom = e.sum(1) + 1.0  # outside good a0 = 0
    cs = BETA * MU * np.log(denom)
    profit = ((P - C) * BETA * e / denom[:, None]).sum(1)
    return {"cs": cs, "profit": profit, "ts": cs + profit}


def index(P: np.ndarray) -> np.ndarray:
    pn, pm = benchmarks(P.shape[1])
    return ((P - pn) / (pm - pn)).mean(1)


def boot(v, n=5000) -> list:
    v = np.asarray(v)
    return np.percentile([RNG.choice(v, len(v)).mean() for _ in range(n)], [2.5, 97.5]).round(3).tolist()


def perm2(a, b, n=20000) -> float:
    a, b = np.asarray(a), np.asarray(b)
    pooled, obs = np.concatenate([a, b]), abs(a.mean() - b.mean())
    hits = 0
    for _ in range(n):
        RNG.shuffle(pooled)
        hits += abs(pooled[: len(a)].mean() - pooled[len(a):].mean()) >= obs - 1e-12
    return hits / n


def signflip(d) -> float:
    d = np.asarray(d)
    obs = abs(d.mean())
    return float(np.mean([abs((d * np.array(s)).mean()) >= obs - 1e-12
                          for s in itertools.product([1, -1], repeat=len(d))]))


def prompt_prevention() -> dict:
    reseed("prompt_prevention")
    d = load()
    games = defaultdict(list)
    for (run, n, prompt), g in d.sort("run", "round").group_by(["run", "num_agents", "prompt"], maintain_order=True):
        P = g.pivot(on="agent", index="round", values="p").sort("round").drop("round").to_numpy()
        games[(n, prompt)].append(P)
    out, paths = {}, {}
    for n in (2, 3, 4, 5):
        r = {}
        for prompt in ("P1", "P2"):
            G = games[(n, prompt)]
            idx = np.array([index(P) for P in G])
            paths[(n, prompt)] = idx.mean(0)
            w = [welfare(P[250:]) for P in G]
            r[prompt] = {"games": len(G), "index_251_300": float(idx[:, 250:].mean()),
                         "index_51_100": float(idx[:, 50:100].mean()),
                         "share_games_above_0.3": float((idx[:, 250:].mean(1) > 0.3).mean()),
                         "cs": float(np.mean([x["cs"].mean() for x in w])),
                         "profit": float(np.mean([x["profit"].mean() for x in w])),
                         "ts": float(np.mean([x["ts"].mean() for x in w]))}
        f1 = np.array([index(P)[250:].mean() for P in games[(n, "P1")]])
        f2 = np.array([index(P)[250:].mean() for P in games[(n, "P2")]])
        diffs = [RNG.choice(f2, len(f2)).mean() - RNG.choice(f1, len(f1)).mean() for _ in range(5000)]
        r["effect_P2_minus_P1"] = float(f2.mean() - f1.mean())
        r["ci"] = np.percentile(diffs, [2.5, 97.5]).round(3).tolist()
        r["p_permutation"] = perm2(f2, f1)
        r["cs_change_pct"] = 100 * (r["P2"]["cs"] / r["P1"]["cs"] - 1)
        r["profit_change_pct"] = 100 * (r["P2"]["profit"] / r["P1"]["profit"] - 1)
        r["ts_change_pct"] = 100 * (r["P2"]["ts"] / r["P1"]["ts"] - 1)
        out[n] = r
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.3), sharey=True)
    for ax, n in zip(axes, (2, 5)):
        for prompt, color in (("P1", "#555555"), ("P2", "#2a6fdb")):
            ax.plot(np.arange(1, 301), paths[(n, prompt)], color=color, lw=1.2,
                    label=f"{prompt} ({len(games[(n, prompt)])} games)")
        ax.axhline(0, color="k", lw=0.5)
        ax.set_ylim(-0.3, 2.5)
        ax.set_title(f"{n} firms")
        ax.set_xlabel("round")
    axes[0].set_ylabel("market collusion index")
    axes[0].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "prompt_prevention.png", dpi=160)
    return out


def alpha_of() -> dict:
    d = pl.read_parquet(ROOT / "data/results/all_experiments.parquet").select("experiment_timestamp", "alpha")
    return dict(d.unique().iter_rows())


def arm_prices(path: str, alpha: float) -> dict:
    by = defaultdict(dict)
    for line in open(path):
        r = json.loads(line)
        by[r["round"]][r["firm"]] = r["price"] / alpha
    return {t: (v["Firm A"], v["Firm B"]) for t, v in by.items()}


def forced_experiment(model: str, alphas: dict) -> dict:
    reseed("forced_experiment", model)
    base = ROOT / "succession/runs/frontier" / model
    eff, cs, prof, ts = [], [], [], []
    for f in sorted(glob.glob(str(base / "*_deviate.jsonl"))):
        src = Path(f).name.split("_")[0]
        a = alphas[src]
        B = max(json.loads(line)["round"] for line in open(base / f"{src}_settle.jsonl"))
        rs = range(B + 2, B + 13)
        dv, ct = arm_prices(f, a), arm_prices(str(base / f"{src}_control.jsonl"), a)
        Pd, Pc = np.array([dv[t] for t in rs]), np.array([ct[t] for t in rs])
        eff.append(index(Pd).mean() - index(Pc).mean())
        wd, wc = welfare(Pd), welfare(Pc)
        cs.append(wd["cs"].mean() - wc["cs"].mean())
        prof.append(wd["profit"].mean() - wc["profit"].mean())
        ts.append(wd["ts"].mean() - wc["ts"].mean())
    return {"states": len(eff), "market_index_effect": float(np.mean(eff)), "ci": boot(eff),
            "states_lower": int(np.sum(np.array(eff) < 0)), "p_signflip": signflip(eff),
            "cs_change": float(np.mean(cs)), "profit_change": float(np.mean(prof)), "ts_change": float(np.mean(ts))}


def mechanism_welfare(alphas: dict, model: str = "haiku") -> dict:
    reseed("mechanism_welfare", model)
    base = ROOT / "succession/runs/frontier" / model
    out = {}
    for arm, rs_of in (("rpe", lambda B: range(B + 13, B + 25)), ("brinfo", lambda B: range(B + 13, B + 25)),
                       ("hidden", lambda B: range(B + 1, B + 13))):
        cs, prof, ts = [], [], []
        for f in sorted(glob.glob(str(base / f"*_{arm}.jsonl"))):
            src = Path(f).name.split("_")[0]
            a = alphas[src]
            B = max(json.loads(line)["round"] for line in open(base / f"{src}_settle.jsonl"))
            m, c = arm_prices(f, a), arm_prices(str(base / f"{src}_control.jsonl"), a)
            rs = rs_of(B)
            wm, wc = welfare(np.array([m[t] for t in rs])), welfare(np.array([c[t] for t in rs]))
            cs.append(wm["cs"].mean() - wc["cs"].mean())
            prof.append(wm["profit"].mean() - wc["profit"].mean())
            ts.append(wm["ts"].mean() - wc["ts"].mean())
        if not cs:
            continue  # this run has no such arm
        out[arm] = {"states": len(cs), "cs_change": float(np.mean(cs)), "profit_change": float(np.mean(prof)),
                    "ts_change": float(np.mean(ts)), "ts_ci": boot(ts)}
    return out


def prevention_welfare() -> dict:
    runs = ROOT / "succession/runs/prevention/games"
    by = defaultdict(list)
    for f in sorted(runs.glob("*/results.json")):
        arm = "rpe" if "_rpe_" in f.parent.name else "brinfo" if "_brinfo_" in f.parent.name else "baseline"
        r = json.loads(f.read_text())
        P = np.array([[r[a][str(t)]["chosen_price"] for a in r] for t in range(1, 101)])
        w = welfare(P[50:])
        by[arm].append({k: v.mean() for k, v in w.items()})
    base = {k: np.mean([g[k] for g in by["baseline"]]) for k in ("cs", "profit", "ts")}
    return {arm: {f"{k}_change": float(np.mean([g[k] for g in v]) - base[k]) for k in ("cs", "profit", "ts")}
            for arm, v in by.items() if arm != "baseline"} | {"baseline_levels": {k: float(v) for k, v in base.items()}}


if __name__ == "__main__":
    alphas = alpha_of()
    res = {"prompt_prevention": prompt_prevention(),
           "forced_experiment": {m: forced_experiment(m, alphas) for m in ("haiku", "fable", "haiku45", "haiku45_enforcer", "haiku45_enforcer2")
                                 if (ROOT / "succession/runs/frontier" / m).exists()},
           "removal_welfare_haiku": mechanism_welfare(alphas),
           "prevention_welfare_haiku": prevention_welfare()}
    if (ROOT / "succession/runs/frontier/haiku45").exists():
        res["removal_welfare_haiku45"] = mechanism_welfare(alphas, "haiku45")
    if (ROOT / "succession/runs/frontier/haiku45_enforcer/1751052703_brinfo.jsonl").exists():
        res["removal_welfare_haiku45_enforcer"] = mechanism_welfare(alphas, "haiku45_enforcer")
    if (ROOT / "succession/runs/frontier/haiku45_enforcer2/1751052703_brinfo.jsonl").exists():
        res["removal_welfare_haiku45_enforcer2"] = mechanism_welfare(alphas, "haiku45_enforcer2")
    (OUT / "remedies_existing.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(res, indent=1, default=lambda x: round(float(x), 3)))
