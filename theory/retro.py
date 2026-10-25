"""
Retroactive test of two accounts of LLM tacit collusion on the thesis's 216 saved games.

Enforcement (repeated-game) account: high prices are held up by the threat of punishment.
    Predicts: a rival's cut is answered with a cut, then both prices return; cuts draw a
    stronger response than raises; the sustainable price falls with the number of firms the
    way the incentive constraint says.
Convention account: agents anchor on a salient price and follow the leader.
    Predicts: a rival's cut is followed (or ignored) with no return; cuts and raises are
    followed alike; the opening rounds predict the final price better than market structure.

Usage:  uv run --extra analysis python theory/retro.py
Writes: theory/out/*.csv and theory/out/*.png
"""

import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
import statsmodels.formula.api as smf

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.environment.pricing_market_logic_multiproduct import (
    get_monopoly_prices,
    get_nash_prices,
    get_profits,
)

DATA = Path(__file__).resolve().parents[1] / "data/results/all_experiments.parquet"
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)
RNG = np.random.default_rng(0)

SHOCK = 0.10  # a "move" is a one-round change of at least this much in the 0-1 collusion index
QUIET = 0.05  # the mover was still (|change| below this) for the 3 rounds before
HORIZON = 10  # rounds of response tracked
FIRST, LAST = 51, 300 - HORIZON  # skip the opening exploration phase


def load() -> pl.DataFrame:
    d = pl.read_parquet(DATA).filter(pl.col("num_agents") >= 2)
    d = d.with_columns(
        run=pl.col("experiment_timestamp"),
        prompt=pl.col("experiment_name").str.extract(r"_(P\d)"),
        delta=(pl.col("chosen_price") - pl.col("nash_prices"))
        / (pl.col("monopoly_prices") - pl.col("nash_prices")),
    )
    return d.select("run", "experiment_name", "num_agents", "alpha", "prompt", "is_symmetric",
                    "agent_memory_length", "agent", "round", "delta", "plans", "insights")


def panel(d: pl.DataFrame) -> dict:
    """run -> (agents, rounds x agents matrix of the collusion index)."""
    out = {}
    for (run,), g in d.group_by(["run"]):
        w = g.pivot(on="agent", index="round", values="delta").sort("round")
        agents = [c for c in w.columns if c != "round"]
        out[run] = (agents, w.select(agents).to_numpy())
    return out


# 1. Event study ----------------------------------------------------------------------------
def events(P: dict, meta: dict, direction: int) -> list:
    """One record per (mover's clean move, each other firm). direction -1 = cut, +1 = raise."""
    rec = []
    for run, (agents, X) in P.items():
        dX = np.diff(X, axis=0, prepend=X[:1])
        for j in range(len(agents)):
            for t in range(FIRST - 1, LAST - 1):  # t is a 0-based row; round = t + 1
                if direction * dX[t, j] < SHOCK or np.abs(dX[t - 3:t, j]).max() >= QUIET:
                    continue
                for i in range(len(agents)):
                    if i == j or abs(dX[t, i]) >= QUIET:  # responder must not have moved the same round
                        continue
                    rec.append({
                        "run": run, "n": meta[run], "t": t + 1,
                        "mover_move": dX[t, j],
                        "resp": X[t - 3:t + HORIZON + 1, i] - X[t, i],
                        "mover": X[t - 3:t + HORIZON + 1, j] - X[t - 1, j],
                    })
    return rec


def cluster_ci(rows: list, key: str) -> tuple:
    """Mean path with a run-clustered bootstrap 95% CI."""
    runs = sorted({r["run"] for r in rows})
    by = {u: np.array([r[key] for r in rows if r["run"] == u]) for u in runs}
    mean = np.concatenate(list(by.values())).mean(0)
    boots = []
    for _ in range(1000):
        pick = RNG.choice(runs, len(runs))
        boots.append(np.concatenate([by[u] for u in pick]).mean(0))
    lo, hi = np.percentile(boots, [2.5, 97.5], axis=0)
    return mean, lo, hi


def event_study(P, meta):
    k = np.arange(-3, HORIZON + 1)
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
    summary = []
    for ax, direction, name in zip(axes, (-1, 1), ("Rival cuts", "Rival raises")):
        ev = events(P, meta, direction)
        for key, label, color in (("mover", "mover (rival)", "#888"), ("resp", "responding firm", "#2a6fdb")):
            m, lo, hi = cluster_ci(ev, key)
            ax.plot(k, m, color=color, label=label)
            ax.fill_between(k, lo, hi, color=color, alpha=0.2)
        ax.axhline(0, color="k", lw=0.5)
        ax.axvline(0, color="k", lw=0.5, ls=":")
        ax.set_title(f"{name} (n={len(ev)} responses, {len({e['run'] for e in ev})} games)")
        ax.set_xlabel("rounds after the move")
        m, lo, hi = cluster_ci(ev, "resp")
        mv, _, _ = cluster_ci(ev, "mover")
        for h in (1, 3, 10):
            summary.append({"event": name, "k": h, "responder": m[h + 3], "lo": lo[h + 3],
                            "hi": hi[h + 3], "mover": mv[h + 3],
                            "share_followed": m[h + 3] / mv[h + 3]})
    axes[0].set_ylabel("change in collusion index")
    axes[0].legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "event_study.png", dpi=160)
    s = pl.DataFrame(summary)
    s.write_csv(OUT / "event_study.csv")
    return s


# 2. Reaction function ----------------------------------------------------------------------
def reaction(P, meta):
    rows = []
    for run, (agents, X) in P.items():
        dX = np.diff(X, axis=0, prepend=X[:1])
        for i in range(len(agents)):
            others = [j for j in range(len(agents)) if j != i]
            for t in range(FIRST - 1, 299):
                rival = dX[t - 1, others].mean()
                rows.append({"run": run, "n": meta[run], "dy": dX[t, i],
                             "rival_cut": min(rival, 0), "rival_raise": max(rival, 0),
                             "gap": X[t - 1, others].mean() - X[t - 1, i], "own_lag": dX[t - 1, i]})
    df = pl.DataFrame(rows).to_pandas()
    fit = smf.ols("dy ~ rival_cut + rival_raise + gap + own_lag", df).fit(
        cov_type="cluster", cov_kwds={"groups": df["run"]})
    test = fit.t_test("rival_cut - rival_raise = 0")
    return fit, test


# 3. Opening prices vs market structure -----------------------------------------------------
def anchors(d: pl.DataFrame):
    m = d.group_by("run", "round").agg(pl.col("delta").mean(), pl.col("num_agents").first(),
                                      pl.col("alpha").first(), pl.col("prompt").first(),
                                      pl.col("is_symmetric").first(),
                                      pl.col("agent_memory_length").first().is_null().alias("mem_all"))
    win = lambda a, b: pl.col("delta").filter(pl.col("round").is_between(a, b)).mean()
    r = m.group_by("run").agg(
        pl.col("num_agents", "alpha", "prompt", "is_symmetric", "mem_all").first(),
        final=win(251, 300), early10=win(1, 10), early30=win(11, 30), early50=win(31, 50),
    ).to_pandas()
    r["n"] = r["num_agents"].astype(str)
    r["a"] = r["alpha"].astype(str)
    structure = "C(n) + C(prompt) + C(a) + C(is_symmetric) + C(mem_all)"
    specs = {
        "structure only": f"final ~ {structure}",
        "rounds 1-10 only": "final ~ early10",
        "rounds 11-30 only": "final ~ early30",
        "rounds 31-50 only": "final ~ early50",
        "structure + rounds 31-50": f"final ~ {structure} + early50",
    }
    res = []
    for name, f in specs.items():
        full = smf.ols(f, r).fit()
        # leave-one-out predictive R^2
        err = []
        for k in range(len(r)):
            fk = smf.ols(f, r.drop(index=r.index[k])).fit()
            err.append(r["final"].iloc[k] - fk.predict(r.iloc[[k]]).iloc[0])
        press = np.sum(np.square(err))
        res.append({"model": name, "R2": full.rsquared,
                    "LOO_R2": 1 - press / np.sum((r["final"] - r["final"].mean()) ** 2)})
    # how much of the final-price variance sits inside identical market settings
    cell = r.groupby(["n", "prompt", "a", "is_symmetric", "mem_all"])["final"]
    within = ((r["final"] - cell.transform("mean")) ** 2).sum() / ((r["final"] - r["final"].mean()) ** 2).sum()
    out = pl.DataFrame(res)
    out.write_csv(OUT / "anchors.csv")
    return out, within, r


# 4. Group size vs the incentive constraint -------------------------------------------------
def sustainable(n: int, delta_disc: float, kw: dict) -> float:
    """Highest symmetric collusion index sustainable under grim trigger with discount delta."""
    c = (1.0,) * n
    a = (2.0,) * n
    al = (1.0,) * n
    g = (1,) * n
    base = {"a0": 0.0, "a": a, "mu": 0.25, "alpha": al, "multiplier": 100, "sigma": 0.0, "group_idxs": g}
    pn = get_nash_prices(**base, c=c)[0]
    pm = get_monopoly_prices(**base, c=c)[0]
    pi_n = get_profits(p=(pn,) * n, c=c, **base)[0]
    grid = np.linspace(pn, pm, 201)
    best = 0.0
    for p in grid:
        pi_c = get_profits(p=(p,) * n, c=c, **base)[0]
        devs = np.linspace(pn * 0.8, p, 120)
        pi_d = max(get_profits(p=(x,) + (p,) * (n - 1), c=c, **base)[0] for x in devs)
        if pi_d - pi_c <= delta_disc / (1 - delta_disc) * (pi_c - pi_n) + 1e-9:
            best = (p - pn) / (pm - pn)
    return best


def group_size(r):
    obs = r[r["is_symmetric"]].groupby("num_agents")["final"].agg(["mean", "count", "std"])
    rows = []
    for n in (2, 3, 4, 5):
        row = {"n": n, "observed": obs.loc[n, "mean"], "obs_se": obs.loc[n, "std"] / np.sqrt(obs.loc[n, "count"])}
        for dd in (0.5, 0.7, 0.8, 0.9):
            row[f"grim_delta_{dd}"] = sustainable(n, dd, {})
        rows.append(row)
    out = pl.DataFrame(rows)
    out.write_csv(OUT / "group_size.csv")
    return out


# 5. What the notes talk about --------------------------------------------------------------
TERMS = {
    "punish / retaliate": r"punish|retaliat",
    "price war": r"price war",
    "undercut": r"undercut",
    "match / follow": r"\bmatch|\bfollow",
    "stable / maintain": r"stabl|maintain",
    "cooperat / collu / coordinat": r"cooperat|collu|coordinat|tacit",
}


def language(d: pl.DataFrame):
    t = d.filter(pl.col("round") >= FIRST).with_columns(
        text=(pl.col("plans").fill_null("") + " " + pl.col("insights").fill_null("")).str.to_lowercase())
    out = t.select([pl.col("text").str.contains(p).mean().alias(k) for k, p in TERMS.items()])
    out.write_csv(OUT / "language.csv")
    return out


if __name__ == "__main__":
    pl.Config.set_tbl_width_chars(200)
    d = load()
    meta = dict(d.select("run", "num_agents").unique().iter_rows())
    P = panel(d)
    print(f"{len(P)} games, {d.height:,} firm-rounds\n")

    print("== 1. Event study: change in the responder's index after a clean rival move ==")
    print(event_study(P, meta))

    print("\n== 2. Reaction function (cluster-robust by game) ==")
    fit, test = reaction(P, meta)
    print(fit.summary().tables[1])
    print("H0 response to cuts = response to raises:", test)

    print("\n== 3. What predicts the final price (rounds 251-300)? ==")
    a, within, r = anchors(d)
    print(a)
    print(f"Share of final-price variance inside identical market settings: {within:.2f}")

    print("\n== 4. Group size: observed vs grim-trigger sustainable collusion index ==")
    print(group_size(r))

    print("\n== 5. Share of firm-rounds whose notes use each term (round >= 51) ==")
    print(language(d))
