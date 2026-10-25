"""
A bandit model of the LLM pricing agents, fitted on duopolies and used to predict 3-5 firm markets.

The agent never looks at its rivals. Each firm:
  1. Opening (rounds 1-10): plays a planned exploration sequence. The simulation replays opening
     sequences sampled from the training games, so plans are as alike as the LLM's were.
  2. Commit (round 11): with probability RHO jumps to the price that paid best in the opening.
  3. Hill-climb (rounds 12-300): moves with a phase-dependent probability; if it moves, it cuts with
     a probability that depends on its last move's direction and whether that move raised profit
     (four cells), with a step size drawn from the training games' steps in that phase.

Every number is estimated from symmetric duopolies of the same prompt. Market size never enters the
fit, so the 3-5 firm results are out-of-sample predictions.

Usage:  uv run --extra analysis python theory/bandit.py
Writes: theory/out/bandit_*.csv, theory/out/bandit_by_n.png
"""

import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
import statsmodels.api as sm

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.environment.pricing_market_logic_multiproduct import (
    get_monopoly_prices,
    get_nash_prices,
)

DATA = Path(__file__).resolve().parents[1] / "data/results/all_experiments.parquet"
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)

OPEN = 10  # opening rounds replayed from the data
MOVE = 0.005  # a "move" is a log-price change above 0.5%
PHASES = [(11, 25), (26, 50), (51, 100), (101, 300)]
ROUNDS = 300
SIMS = 2000


def profits(p: np.ndarray) -> np.ndarray:
    """Calvano logit demand at the thesis parameters (a=2, c=1, mu=0.25, beta=100, a0=0), alpha=1.
    Checked against get_profits to 4 decimals. p: games x firms."""
    e = np.exp((2.0 - p) / 0.25)
    return (p - 1.0) * 100 * e / (e.sum(1, keepdims=True) + 1.0)


def best_response(p: np.ndarray) -> np.ndarray:
    """Each firm's static best response to its rivals' prices. Logit FOC: p - c = mu / (1 - s)."""
    e = np.exp((2.0 - p) / 0.25)
    others = e.sum(-1, keepdims=True) - e + 1.0
    lo, hi = np.full_like(p, 1.0), np.full_like(p, 6.0)
    for _ in range(50):  # bisection: x - c - mu / (1 - s(x)) is increasing in x
        x = (lo + hi) / 2
        ex = np.exp((2.0 - x) / 0.25)
        above = x - 1.0 - 0.25 / (1.0 - ex / (ex + others)) > 0
        hi, lo = np.where(above, x, hi), np.where(above, lo, x)
    return (lo + hi) / 2


def benchmarks(n: int) -> tuple:
    kw = {"a0": 0.0, "a": (2.0,) * n, "mu": 0.25, "alpha": (1.0,) * n, "multiplier": 100, "sigma": 0.0,
              "group_idxs": (1,) * n, "c": (1.0,) * n}
    return get_nash_prices(**kw)[0], get_monopoly_prices(**kw)[0]


def load() -> pl.DataFrame:
    d = pl.read_parquet(DATA).filter(pl.col("num_agents") >= 2, pl.col("is_symmetric"))
    return d.with_columns(
        run=pl.col("experiment_timestamp"),
        prompt=pl.col("experiment_name").str.extract(r"_(P\d)"),
        p=pl.col("chosen_price") / pl.col("alpha"),  # alpha only rescales prices
    ).sort("run", "agent", "round")


def markets(d: pl.DataFrame) -> list:
    """One (prices, profits) pair of rounds x firms arrays per game."""
    def wide(g: pl.DataFrame, v: str) -> np.ndarray:
        return g.pivot(on="agent", index="round", values=v).sort("round").drop("round").to_numpy()

    return [(wide(g, "p"), wide(g, "profit")) for _, g in d.sort("run", "round").group_by(["run"], maintain_order=True)]


RULES = ("feedback", "gradient", "both")


def features(gap: np.ndarray, last_dir: np.ndarray, last_won: np.ndarray, rule: str) -> np.ndarray:
    """Design matrix for P(cut | move). Cells: last move up/down x won/lost; no move yet is the base."""
    cols = [np.ones_like(gap)]
    if rule in ("gradient", "both"):
        cols.append(gap)
    if rule in ("feedback", "both"):
        for up in (True, False):
            for won in (True, False):
                cols.append(((last_dir > 0) == up) & (last_dir != 0) & (last_won == won))
    return np.stack([c.astype(float) for c in cols], -1)


def fit(games: list) -> dict:
    firms = [(P[:, i], Pi[:, i]) for P, Pi in games for i in range(P.shape[1])]
    opens = np.array([p[:OPEN] for p, _ in firms])
    near_best = [abs(np.log(p[OPEN + 2] / p[:OPEN][np.argmax(pi[:OPEN])])) < 0.03 for p, pi in firms]
    move_p, steps = {}, {}
    for lo, hi in PHASES:
        dx = np.concatenate([np.diff(np.log(p))[lo - 2:hi - 1] for p, _ in firms])
        move_p[lo] = np.mean(np.abs(dx) > MOVE)
        steps[lo] = np.abs(dx[np.abs(dx) > MOVE])
    gap, ld, lw, cut = [], [], [], []
    for P, Pi in games:
        G = np.log(P / best_response(P))  # rounds x firms
        dX = np.diff(np.log(P), axis=0, prepend=np.log(P[:1]))
        for i in range(P.shape[1]):
            last_dir, last_won = 0.0, False
            for t in range(OPEN, ROUNDS - 1):  # decision for round t+1, seeing the market at t
                if t > OPEN and abs(dX[t, i]) > MOVE:
                    last_dir, last_won = np.sign(dX[t, i]), bool(Pi[t, i] > Pi[t - 1, i])
                if abs(dX[t + 1, i]) > MOVE:
                    gap.append(G[t, i])
                    ld.append(last_dir)
                    lw.append(last_won)
                    cut.append(dX[t + 1, i] < 0)
    gap, ld, lw, cut = map(np.array, (gap, ld, lw, cut))
    coef = {}
    for rule in RULES:
        X = features(gap, ld, lw, rule)
        coef[rule] = sm.Logit(cut.astype(float), X).fit(disp=0).params
    return {"opens": opens, "rho": float(np.mean(near_best)), "move_p": move_p, "steps": steps,
            "coef": coef}


def simulate(m: dict, n: int, rng, rule="both", commit=True) -> np.ndarray:
    """Returns games x rounds x firms prices."""
    G = SIMS
    P = np.zeros((G, ROUNDS, n))
    P[:, :OPEN] = m["opens"][rng.integers(len(m["opens"]), size=(G, n))].transpose(0, 2, 1)
    Pi = np.zeros((G, ROUNDS, n))
    for t in range(OPEN):
        Pi[:, t] = profits(P[:, t])
    last_dir = np.zeros((G, n))
    last_won = np.zeros((G, n), bool)
    x = P[:, OPEN - 1].copy()
    if commit:
        best = np.take_along_axis(P[:, :OPEN], Pi[:, :OPEN].argmax(1)[:, None, :], 1)[:, 0]
        x = np.where(rng.random((G, n)) < m["rho"], best, x)
    for t in range(OPEN, ROUNDS):
        if t > OPEN:
            phase = max(lo for lo, _ in PHASES if lo <= t + 1)
            moving = rng.random((G, n)) < m["move_p"][phase]
            gap = np.log(P[:, t - 1] / best_response(P[:, t - 1]))
            z = features(gap, last_dir, last_won, rule) @ m["coef"][rule]
            direction = np.where(rng.random((G, n)) < 1 / (1 + np.exp(-z)), -1, 1)
            step = rng.choice(m["steps"][phase], (G, n))
            x = np.where(moving, np.clip(x * np.exp(direction * step), 1.0, 4.51), x)
        P[:, t] = x
        Pi[:, t] = profits(x)
        if t > OPEN:
            last_won = np.where(moving, Pi[:, t] > Pi[:, t - 1], last_won)
            last_dir = np.where(moving, direction, last_dir)
    return P


def index(P: np.ndarray, n: int) -> np.ndarray:
    pn, pm = benchmarks(n)
    return (P - pn) / (pm - pn)


def observed(d: pl.DataFrame) -> pl.DataFrame:
    rows = []
    for (run, n, prompt), g in d.sort("run", "round").group_by(["run", "num_agents", "prompt"], maintain_order=True):
        pn, pm = benchmarks(n)
        w = g.pivot(on="agent", index="round", values="p").sort("round").drop("round").to_numpy()
        D = (w - pn) / (pm - pn)
        rows.append({"run": run, "n": n, "prompt": prompt, "final": D[250:].mean(),
                     "early": D[30:50].mean()})
    return pl.DataFrame(rows)


VARIANTS = {"both": {}, "gradient": {"rule": "gradient"}, "feedback": {"rule": "feedback"},
            "both_no_commit": {"commit": False}}

if __name__ == "__main__":
    pl.Config.set_tbl_width_chars(200)
    pl.Config.set_tbl_cols(20)
    d = load()
    obs = observed(d)
    rng = np.random.default_rng(0)
    table, paths = [], {}
    for prompt in ("P1", "P2"):
        m = fit(markets(d.filter(pl.col("num_agents") == 2, pl.col("prompt") == prompt)))
        print(f"{prompt}: commit {m['rho']:.2f}; move prob "
              + ", ".join(f"{k}+: {v:.2f}" for k, v in m["move_p"].items())
              + f"; gradient-only logit {np.round(m['coef']['gradient'], 2)}"
              + f"; both {np.round(m['coef']['both'], 2)}")
        for n in (2, 3, 4, 5):
            o = obs.filter(pl.col("n") == n, pl.col("prompt") == prompt)["final"].to_numpy()
            row = {"prompt": prompt, "n": n, "split": "train" if n == 2 else "test",
                   "observed": o.mean(), "obs_se": o.std(ddof=1) / np.sqrt(len(o)), "games": len(o)}
            for name, kw in VARIANTS.items():
                D = index(simulate(m, n, rng, **kw), n).mean(2)  # market mean per round
                f = D[:, 250:].mean(1)
                row[name] = f.mean()
                if name == "gradient":
                    row["gradient_sd"] = f.std()
                    row["gradient_early_final_r2"] = np.corrcoef(D[:, 30:50].mean(1), f)[0, 1] ** 2
                    paths[(prompt, n)] = D.mean(0)
            row["nash"], row["grim_trigger"] = 0.0, 1.0
            table.append(row)
    t = pl.DataFrame(table)
    t.write_csv(OUT / "bandit_by_n.csv")
    print(t.select("prompt", "n", "split", "observed", "obs_se", *VARIANTS, "gradient_sd"))

    test = t.filter(pl.col("split") == "test")
    for col in (*VARIANTS, "nash", "grim_trigger"):
        err = (test[col] - test["observed"]).to_numpy()
        print(f"{col:>15}: test-set mean abs error {np.abs(err).mean():.3f}")
    o = obs.to_pandas()
    print(f"early(31-50) vs final R2: observed {np.corrcoef(o.early, o.final)[0, 1] ** 2:.2f}, "
          f"model {t['gradient_early_final_r2'].mean():.2f}")

    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.6), sharey=True)
    for ax, prompt in zip(axes, ("P1", "P2")):
        s = t.filter(pl.col("prompt") == prompt)
        ax.errorbar(s["n"], s["observed"], yerr=1.96 * s["obs_se"], fmt="o", color="k", label="LLM games (95% CI)")
        ax.plot(s["n"], s["gradient"], "-s", color="#2a6fdb", label="bandit model (gradient rule)")
        ax.axhline(1.0, color="#c0392b", lw=0.8, ls="--", label="enforcement (grim trigger)")
        ax.axhline(0.0, color="k", lw=0.5)
        ax.axvspan(2.5, 5.5, color="#f2f2f2", zorder=-1)
        ax.set_title(f"Prompt {prompt}: fitted on 2 firms, 3-5 predicted")
        ax.set_xlabel("number of firms")
        ax.set_xticks([2, 3, 4, 5])
    axes[0].set_ylabel("collusion index, rounds 251-300")
    axes[0].legend(frameon=False, fontsize=8, loc="center left")
    fig.tight_layout()
    fig.savefig(OUT / "bandit_by_n.png", dpi=160)

    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.4), sharey=True)
    for ax, prompt in zip(axes, ("P1", "P2")):
        for n, color in zip((2, 5), ("#2a6fdb", "#e67e22")):
            g = d.filter(pl.col("num_agents") == n, pl.col("prompt") == prompt)
            pn, pm = benchmarks(n)
            ob = np.mean([(P - pn) / (pm - pn) for P, _ in markets(g)], axis=0).mean(1)
            ax.plot(np.arange(1, ROUNDS + 1), ob, color=color, lw=1, label=f"{n} firms, LLM")
            ax.plot(np.arange(1, ROUNDS + 1), paths[(prompt, n)], color=color, ls="--", lw=1, label=f"{n} firms, model")
        ax.axhline(0, color="k", lw=0.5)
        ax.set_ylim(-0.5, 2.5)
        ax.set_title(f"Prompt {prompt}")
        ax.set_xlabel("round")
    axes[0].set_ylabel("mean collusion index")
    axes[0].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "bandit_paths.png", dpi=160)
