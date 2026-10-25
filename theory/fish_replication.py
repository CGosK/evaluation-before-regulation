"""
Replicates Fish et al. (2024) Table 1 ("Responsiveness and Stickiness") on the thesis's saved duopolies,
and tests whether a positive competitor coefficient can tell punishment apart from other dynamics.

Fish et al., Eq. (1):  p[i,t] = a[i,run] + g * p[i,t-1] + d * p[-i,t-1] + e
estimated on disjoint pairs of periods in rounds 101-300, alternating which firm is "self" between
consecutive pairs, with firm-run fixed effects and robust standard errors. They read d > 0 as a
reward-punishment scheme (P1: g = 0.484, d = 0.103; P2: g = 0.280, d = 0.022; GPT-4, 21 runs each).

Checks:
  1. Replication on Mistral-Large (same harness, same prompts, 21 runs per prompt).
  2. Placebo: each firm paired with the rival from a different game, which it never saw. Any d > 0
     there comes from shared trends, not from responding to the rival.
  3. Same regression with game-specific linear trends.
  4. What a non-strategic partial-adjustment best responder implies: d = lambda * BR'(p_rival),
     with lambda = 1 - g. In a Bertrand market BR' > 0, so d > 0 without any punishment.

Usage:  uv run --extra analysis python theory/fish_replication.py
Writes: theory/out/fish_replication.csv
"""

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl
import statsmodels.formula.api as smf

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from bandit import best_response, load, markets

OUT = Path(__file__).resolve().parent / "out"
FISH = {"P1": (0.484, 0.103), "P2": (0.280, 0.022)}


def pairs(games: list, rivals: list | None = None) -> pd.DataFrame:
    """Fish's sample: rounds 101-300 in disjoint pairs, alternating "self". rivals: optional
    rival price paths to use in place of each game's own (the placebo)."""
    rows = []
    for g, (P, _) in enumerate(games):
        R = P if rivals is None else rivals[g]
        for k, t in enumerate(range(101, 300, 2)):  # 0-based row t is round t+1: pairs (102,103)...
            i = k % 2
            rows.append({"fr": f"{g}_{i}", "t": t, "y": P[t, i], "own": P[t - 1, i], "rival": R[t - 1, 1 - i]})
    return pd.DataFrame(rows)


def fit(df: pd.DataFrame, trends: bool = False) -> dict:
    f = "y ~ own + rival + C(fr)" + (" + C(fr):t" if trends else "")
    m = smf.ols(f, df).fit(cov_type="HC1")
    return {"own": m.params["own"], "own_se": m.bse["own"], "rival": m.params["rival"],
            "rival_se": m.bse["rival"], "n": int(m.nobs), "r2_within": None}


def br_slope(p_rival: float, h: float = 1e-4) -> float:
    """dBR/dp_rival in the duopoly at a symmetric point (alpha = 1)."""
    up = best_response(np.array([[1.5, p_rival + h]]))[0, 0]
    dn = best_response(np.array([[1.5, p_rival - h]]))[0, 0]
    return (up - dn) / (2 * h)


if __name__ == "__main__":
    d = load()
    rows = []
    for prompt in ("P1", "P2"):
        games = markets(d.filter(pl.col("num_agents") == 2, pl.col("prompt") == prompt))
        own_rivals = [P for P, _ in games]
        placebo = own_rivals[1:] + own_rivals[:1]  # each game's rival comes from another game
        late_rival = float(np.mean([P[100:].mean() for P, _ in games]))
        for name, df, trends in (
            ("replication", pairs(games), False),
            ("placebo: rival from another game", pairs(games, placebo), False),
            ("with game-specific trends", pairs(games), True),
        ):
            r = fit(df, trends)
            rows.append({"prompt": prompt, "spec": name, **r})
        g = rows[-3]["own"]
        rows.append({"prompt": prompt, "spec": "partial-adjustment best responder (implied)",
                     "own": g, "rival": (1 - g) * br_slope(late_rival), "n": None,
                     "own_se": None, "rival_se": None})
        rows.append({"prompt": prompt, "spec": "Fish et al. 2024, GPT-4 (reported)",
                     "own": FISH[prompt][0], "rival": FISH[prompt][1], "n": 2100,
                     "own_se": None, "rival_se": None})
        # Same environment, so the BR slope carries over; their prices are proxied by ours.
        rows.append({"prompt": prompt, "spec": "best responder with Fish's stickiness (implied)",
                     "own": FISH[prompt][0], "rival": (1 - FISH[prompt][0]) * br_slope(late_rival),
                     "n": None, "own_se": None, "rival_se": None})
        print(f"{prompt}: {len(games)} games; mean late price (alpha-normalised) {late_rival:.3f}; "
              f"BR slope there {br_slope(late_rival):.3f}")
    out = pd.DataFrame(rows).drop(columns="r2_within")
    out.to_csv(OUT / "fish_replication.csv", index=False)
    pd.set_option("display.width", 200)
    print(out.round(3).to_string(index=False))
