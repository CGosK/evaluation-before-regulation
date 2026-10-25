"""
Policy simulator: the slow best-responder (SBR) model fitted on the thesis's Mistral duopolies, run under
counterfactual remedies, to rank them before any LLM is paid for and to decompose the P2 prompt's effect.

The SBR model (theory/bandit.py, gradient rule) predicts 3-5 firm markets out of sample. Each remedy here
changes one of its ingredients, or adds a platform intervention:

    P1 baseline                 the P1 fit
    P2 opening only             P2's opening plans and commit probability, the rest from P1
    P2 gradient rule only       P2's cut-probability rule (sensitivity to the gap to best response)
    P2 move rates only          P2's move probabilities and step sizes
    P2 (all ingredients)        the P2 fit, checked against the observed P2 games
    exploration mandate         the move rate held at its opening-phase level instead of decaying
    gradient disclosure         the cut rule's gradient sensitivity raised to 3x P2's
    forced experiment / K       every K rounds one firm, at random, is held at the Nash price for a round
    forced 10% cut / K          the same, but the firm's own price is cut by 10%: no demand model needed
    memory reset at 150         both firms restart their opening plan at round 150
    5 firms                     the P1 fit in a five-firm market, for scale

All are model predictions, not observations; the P1 and P2 rows show how close the model gets to the data.

Usage:  uv run --extra analysis python theory/policy_sim.py
Writes: theory/out/policy_sim.csv, theory/out/policy_sim.png
"""

import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from bandit import OPEN, PHASES, benchmarks, best_response, features, fit, load, markets, profits
from remedies_existing import welfare

OUT = Path(__file__).resolve().parent / "out"
ROUNDS, SIMS = 300, 2000


def simulate(m: dict, n: int, rng, *, opens=None, rho=None, coef=None, move_p=None, steps=None,
             forced_every=None, forced_cut=None, reset_at=None) -> np.ndarray:
    """The SBR gradient-rule simulation with optional overrides and interventions. games x rounds x firms."""
    opens = m["opens"] if opens is None else opens
    rho = m["rho"] if rho is None else rho
    coef = m["coef"]["gradient"] if coef is None else coef
    move_p = m["move_p"] if move_p is None else move_p
    steps = m["steps"] if steps is None else steps
    pn = benchmarks(n)[0]
    G = SIMS
    P = np.zeros((G, ROUNDS, n))
    Pi = np.zeros((G, ROUNDS, n))
    plan = opens[rng.integers(len(opens), size=(G, n))].transpose(0, 2, 1)  # games x OPEN x firms
    last_dir = np.zeros((G, n))
    last_won = np.zeros((G, n), bool)
    start = 0  # first round of the current opening plan
    x = None
    for t in range(ROUNDS):
        if reset_at is not None and t == reset_at:
            start = t
            plan = opens[rng.integers(len(opens), size=(G, n))].transpose(0, 2, 1)
            last_dir[:] = 0
        k = t - start
        if k < OPEN:  # replay the opening plan
            x = plan[:, k].copy()
            moving = np.ones((G, n), bool)
            direction = np.zeros((G, n))
        else:
            if k == OPEN:  # commit to the opening's best-paying price
                best = np.take_along_axis(P[:, start:t], Pi[:, start:t].argmax(1)[:, None, :], 1)[:, 0]
                x = np.where(rng.random((G, n)) < rho, best, x)
            phase = max(lo for lo, _ in PHASES if lo <= k + 1)
            moving = rng.random((G, n)) < move_p[phase]
            gap = np.log(P[:, t - 1] / best_response(P[:, t - 1]))
            z = features(gap, last_dir, last_won, "gradient") @ coef
            direction = np.where(rng.random((G, n)) < 1 / (1 + np.exp(-z)), -1, 1)
            step = rng.choice(steps[phase], (G, n))
            x = np.where(moving, np.clip(x * np.exp(direction * step), 1.0, 4.51), x)
            if forced_every and k > OPEN and t % forced_every == 0:
                firm = rng.integers(n, size=G)
                rows = np.arange(G)
                x[rows, firm] = np.maximum(1.0, x[rows, firm] * (1 - forced_cut)) if forced_cut else pn
        P[:, t] = x
        Pi[:, t] = profits(x)
        if k > OPEN:
            moved = np.abs(np.log(P[:, t] / P[:, t - 1])) > 1e-9
            last_won = np.where(moved, Pi[:, t] > Pi[:, t - 1], last_won)
            last_dir = np.where(moved, np.sign(np.log(P[:, t] / P[:, t - 1])), last_dir)
    return P


def market_index(P: np.ndarray) -> np.ndarray:
    pn, pm = benchmarks(P.shape[2])
    return ((P - pn) / (pm - pn)).mean(2)  # games x rounds


if __name__ == "__main__":
    rng = np.random.default_rng(5)
    d = load()
    m1 = fit(markets(d.filter(pl.col("num_agents") == 2, pl.col("prompt") == "P1")))
    m2 = fit(markets(d.filter(pl.col("num_agents") == 2, pl.col("prompt") == "P2")))
    phase1 = min(m1["move_p"])
    disclosure = m2["coef"]["gradient"].copy()
    disclosure[1] *= 3
    scenarios = {
        "P1 baseline": dict(m=m1),
        "P2 opening only": dict(m=m1, opens=m2["opens"], rho=m2["rho"]),
        "P2 gradient rule only": dict(m=m1, coef=m2["coef"]["gradient"]),
        "P2 move rates only": dict(m=m1, move_p=m2["move_p"], steps=m2["steps"]),
        "P2 (all ingredients)": dict(m=m2),
        "exploration mandate": dict(m=m1, move_p={k: m1["move_p"][phase1] for k in m1["move_p"]}),
        "gradient disclosure (3x P2)": dict(m=m1, coef=disclosure),
        "forced experiment every 50": dict(m=m1, forced_every=50),
        "forced experiment every 25": dict(m=m1, forced_every=25),
        "forced experiment every 10": dict(m=m1, forced_every=10),
        "memory reset at round 150": dict(m=m1, reset_at=150),
        "forced 10% cut every 25": dict(m=m1, forced_every=25, forced_cut=0.10),
        "forced 10% cut every 10": dict(m=m1, forced_every=10, forced_cut=0.10),
    }
    observed = {}
    for prompt in ("P1", "P2"):
        g = markets(d.filter(pl.col("num_agents") == 2, pl.col("prompt") == prompt))
        pn, pm = benchmarks(2)
        observed[prompt] = np.mean([((P - pn) / (pm - pn)).mean(1)[250:].mean() for P, _ in g])
    rows, paths = [], {}
    base_w = None
    for name, kw in scenarios.items():
        m = kw.pop("m")
        P = simulate(m, 2, rng, **kw)
        ix = market_index(P)
        w = welfare(P[:, 250:].reshape(-1, 2))
        row = {"scenario": name, "index_51_100": float(ix[:, 50:100].mean()), "index_251_300": float(ix[:, 250:].mean()),
               "share_games_above_0.3": float((ix[:, 250:].mean(1) > 0.3).mean()),
               "cs": float(w["cs"].mean()), "profit": float(w["profit"].mean()), "ts": float(w["ts"].mean())}
        if base_w is None:
            base_w = row
        for k in ("cs", "profit", "ts"):
            row[f"{k}_change_pct"] = 100 * (row[k] / base_w[k] - 1)
        rows.append(row)
        paths[name] = ix.mean(0)
    P5 = simulate(m1, 5, rng)
    I5 = market_index(P5)
    rows.append({"scenario": "5 firms (P1 fit)", "index_51_100": float(I5[:, 50:100].mean()),
                 "index_251_300": float(I5[:, 250:].mean()),
                 "share_games_above_0.3": float((I5[:, 250:].mean(1) > 0.3).mean())})
    t = pl.DataFrame(rows)
    t.write_csv(OUT / "policy_sim.csv")
    pl.Config.set_tbl_width_chars(220)
    pl.Config.set_tbl_cols(20)
    print(f"observed (Mistral duopolies, rounds 251-300): P1 {observed['P1']:+.3f}, P2 {observed['P2']:+.3f}")
    print(t.select("scenario", "index_51_100", "index_251_300", "share_games_above_0.3", "cs_change_pct",
                   "profit_change_pct", "ts_change_pct"))

    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    show = ["P1 baseline", "P2 opening only", "P2 gradient rule only", "P2 (all ingredients)",
            "exploration mandate", "forced experiment every 25", "memory reset at round 150"]
    colors = ["#555555", "#e67e22", "#8e44ad", "#2a6fdb", "#27ae60", "#c0392b", "#999999"]
    for name, color in zip(show, colors):
        ax.plot(np.arange(1, ROUNDS + 1), paths[name], color=color, lw=1.2, label=name)
    ax.axhline(0, color="k", lw=0.5)
    ax.set_ylim(-0.3, 2.5)
    ax.set_xlabel("round")
    ax.set_ylabel("market collusion index (model)")
    ax.set_title("Slow best-responder model (Mistral P1 fit): remedies from round 1, duopoly")
    ax.legend(frameon=False, fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(OUT / "policy_sim.png", dpi=160)
