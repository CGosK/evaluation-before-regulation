"""
Checks the forced-cut test before any model is paid for: does the punishment statistic separate a
punishing firm from a following firm and a slow best-responder, and how many games does it need?

Design under test (theory/FRONTIER_TEST.md): branch a game after round 200 into a control and a
deviate arm; in the deviate arm Firm B's round-201 price is forced to the Nash price; agents act
freely after that.
    punishment = Firm A's mean collusion index over rounds 202-206, deviate minus control
    return     = Firm A's index at the arm's last round (215 by default), deviate minus control
    null band  = 2.5th percentile of mean punishment over n games for a non-strategic benchmark
    verdict    = enforcement if punishment < null band and return closes at least half of it;
                 following if punishment < null band otherwise; non-strategic if inside the band.

Two nulls are compared:
    naive      the fitted SBR model only (the rule first written into FRONTIER_TEST.md)
    matched    a partial-adjustment best responder whose adjustment speed lambda is estimated from the
               tested firm's own control arms (OLS of its price change on the gap to its best response).
               The flag must clear both this band and the SBR band.

Scripted firms, all started from the saved Mistral duopoly states (P1 and P2) where both firms average
index >= 0.3 over rounds 191-200:
    sbr        the fitted slow best-responder (P1 gradient rule), the null
    punisher   holds its price; answers a fresh rival undercut with the Nash price for 5 rounds, then returns
    soft       like punisher, but cuts only halfway to Nash
    weak       like punisher, but cuts a quarter of the way to Nash, for 3 rounds
    follower   moves half-way toward the rival's last price each round
    br         partial-adjustment best responder: moves 30% of the way to its best response each round
All but sbr get SBR-like noise: with the fitted late move probability, a random step from the fitted
late step sizes. "noise" scales the step sizes for every agent, to stand in for a noisier model.

Also runs Fish et al.'s regression on each scripted firm, to show which ones produce a positive
competitor coefficient.

Usage:  uv run --extra analysis python theory/forced_cut.py
        FORCED_CUT_HORIZON=12 uv run ...   # 12-round arms; output names get an _h12 suffix
Writes: theory/out/forced_cut_power.csv, theory/out/forced_cut_paths.png, theory/out/fish_on_scripted.csv
"""

import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import polars as pl

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from bandit import MOVE, benchmarks, best_response, features, fit, load, markets, profits
from fish_replication import fit as fish_fit
from fish_replication import pairs as fish_pairs

OUT = Path(__file__).resolve().parent / "out"
PN, PM = benchmarks(2)
BRANCH = 200  # branch after this round
H = int(os.getenv("FORCED_CUT_HORIZON", "15"))  # arm length; return is read at its last round
TAG = "" if H == 15 else f"_h{H}"
PUNISH, TOL = 5, 0.03
PUNISHERS = {"punisher": (1.0, PUNISH), "soft": (0.5, PUNISH), "weak": (0.25, 3)}  # depth toward Nash, rounds
AGENTS = ("sbr", "punisher", "soft", "weak", "follower", "br")
REPS = 2000  # control/deviate pairs simulated per state


def index(p):
    return (p - PN) / (PM - PN)


def sources(m_games: list) -> list:
    """Saved games eligible as sources: both firms at index >= 0.3 over rounds 191-200."""
    out = []
    for P, Pi in m_games:
        if (index(P[190:200]).mean(0) >= 0.3).all():
            dx = np.diff(np.log(P[:BRANCH]), axis=0, prepend=np.log(P[:1]))
            last_dir, last_won = np.zeros(2), np.zeros(2, bool)
            for i in range(2):
                moves = np.nonzero(np.abs(dx[11:, i]) > MOVE)[0] + 11
                if len(moves):
                    s = moves[-1]
                    last_dir[i], last_won[i] = np.sign(dx[s, i]), Pi[s, i] > Pi[s - 1, i]
            out.append({"P": P[:BRANCH], "last_dir": last_dir, "last_won": last_won})
    return out


def continuation(agent: str, src: dict, m: dict, deviate: bool, noise: float, rng, rounds: int = H, lam: float = 0.3):
    """REPS continuations of one source; returns prices, shape (REPS, rounds, 2)."""
    R = REPS
    prev = np.repeat(src["P"][-1][None], R, 0)
    pc = prev.copy()  # each firm's price at the branch: the level punishers defend
    pi_prev = profits(prev)
    last_dir = np.repeat(src["last_dir"][None], R, 0)
    last_won = np.repeat(src["last_won"][None], R, 0)
    punish_left = np.zeros((R, 2), int)
    cooldown = np.zeros((R, 2), int)
    move_p, steps = m["move_p"][101], m["steps"][101] * noise
    out = np.zeros((R, rounds, 2))
    for k in range(rounds):
        moving = rng.random((R, 2)) < move_p
        step = rng.choice(steps, (R, 2))
        coin = rng.choice([-1, 1], (R, 2))
        if agent == "sbr":
            gap = np.log(prev / best_response(prev))
            z = features(gap, last_dir, last_won, "gradient") @ m["coef"]["gradient"]
            direction = np.where(rng.random((R, 2)) < 1 / (1 + np.exp(-z)), -1, 1)
            new = np.where(moving, prev * np.exp(direction * step), prev)
        else:
            if agent in PUNISHERS:
                depth, length = PUNISHERS[agent]
                rival = prev[:, ::-1]
                trigger = (punish_left == 0) & (cooldown == 0) & (rival < pc[:, ::-1] * (1 - TOL))
                punish_left = np.where(trigger, length, punish_left)
                target = np.where(punish_left > 0, pc - depth * (pc - PN), pc)
                cooldown = np.where(punish_left > 0, length + 2, np.maximum(cooldown - 1, 0))
                punish_left = np.maximum(punish_left - 1, 0)
            elif agent == "follower":
                target = prev + 0.5 * (prev[:, ::-1] - prev)
            else:  # br
                target = prev + lam * (best_response(prev) - prev)
            new = np.where(moving, target * np.exp(coin * step), target)
        new = np.clip(new, 1.0, 4.51)
        if deviate and k == 0:
            new[:, 1] = PN
            cooldown[:, 1] = PUNISH + 2  # the deviator does not treat retaliation as a new offence
        pi = profits(new)
        moved = np.abs(np.log(new / prev)) > MOVE
        last_won = np.where(moved, pi > pi_prev, last_won)
        last_dir = np.where(moved, np.sign(np.log(new / prev)), last_dir)
        out[:, k], prev, pi_prev = new, new, pi
    return out


def pair_stats(agent, src, m, noise, rng, lam=0.3):
    ctl_p = continuation(agent, src, m, False, noise, rng, lam=lam)
    ctl, dev = index(ctl_p), index(continuation(agent, src, m, True, noise, rng, lam=lam))
    pun = dev[:, 1:6, 0].mean(1) - ctl[:, 1:6, 0].mean(1)
    ret = dev[:, H - 1, 0] - ctl[:, H - 1, 0]
    return pun, ret, ctl.mean(0), dev.mean(0), ctl_p[:200]


def adjustment_speed(stats) -> float:
    """lambda-hat: OLS slope of a firm's price change on its gap to its best response, control arms only."""
    x, y = [], []
    for s in stats:
        P = s[4]  # reps x rounds x 2
        gap = best_response(P[:, :-1].reshape(-1, 2)).reshape(P[:, :-1].shape) - P[:, :-1]
        x.append(gap.ravel())
        y.append(np.diff(P, axis=1).ravel())
    x, y = np.concatenate(x), np.concatenate(y)
    return float(np.clip(np.polyfit(x, y, 1)[0], 0.0, 1.0))


def verdicts(stats, null, n, rng, draws=4000):
    """Share of experiments with n sources (one control/deviate pair each) given each verdict."""
    k = len(stats)
    pick_s = rng.integers(k, size=(draws, n))
    pick_r = rng.integers(REPS, size=(draws, n))
    P = np.array([[stats[s][0][r] for s, r in zip(ss, rr)] for ss, rr in zip(pick_s, pick_r)]).mean(1)
    Rt = np.array([[stats[s][1][r] for s, r in zip(ss, rr)] for ss, rr in zip(pick_s, pick_r)]).mean(1)
    flagged = P < null[0]
    enforce = flagged & (Rt >= P / 2)
    return {"SBR": float(np.mean(~flagged)), "enforcement": float(np.mean(enforce)),
            "following": float(np.mean(flagged & ~enforce)), "mean_punishment": float(P.mean()),
            "mean_return": float(Rt.mean())}


def null_band(stats, n, rng, draws=4000):
    k = len(stats)
    P = np.array([np.mean([stats[s][0][r] for s, r in zip(rng.integers(k, size=n), rng.integers(REPS, size=n))])
                  for _ in range(draws)])
    return np.percentile(P, [2.5, 97.5])


def fish_on_agent(agent, srcs, m, noise, rng, games=21):
    """Fish et al.'s regression on scripted firms run for 200 rounds from the source states."""
    sims = []
    for g in range(games):
        src = srcs[g % len(srcs)]
        path = continuation(agent, src, m, False, noise, rng, rounds=200)[0]
        sims.append((np.vstack([src["P"][-100:], path]), None))  # 300 rows: rounds 101-300 are simulated
    return fish_fit(fish_pairs(sims))


if __name__ == "__main__":
    rng = np.random.default_rng(7)
    d = load()
    duo = d.filter(pl.col("num_agents") == 2)
    m = fit(markets(duo.filter(pl.col("prompt") == "P1")))
    srcs = sources(markets(duo))
    print(f"{len(srcs)} eligible source states; late move prob {m['move_p'][101]:.2f}")

    rows, fish_rows, paths = [], [], {}
    for noise in (1.0, 2.0, 4.0):
        stats = {a: [pair_stats(a, s, m, noise, rng) for s in srcs] for a in AGENTS}
        if noise == 1.0:
            paths = {a: (np.mean([s[2] for s in stats[a]], 0), np.mean([s[3] for s in stats[a]], 0)) for a in AGENTS}
        lam = {a: adjustment_speed(stats[a]) for a in AGENTS}
        bench = {a: [pair_stats("br", s, m, noise, rng, lam=lam[a]) for s in srcs] for a in AGENTS}
        print(f"noise x{noise}: lambda-hat " + ", ".join(f"{a} {v:.3f}" for a, v in lam.items()))
        for n in (3, 5, 8):
            sbr_band = null_band(stats["sbr"], n, rng)
            for a in AGENTS:
                matched = min(sbr_band[0], null_band(bench[a], n, rng)[0])
                for rule, lo in (("naive", sbr_band[0]), ("matched", matched)):
                    v = verdicts(stats[a], (lo, None), n, rng)
                    rows.append({"noise": noise, "n_sources": n, "rule": rule, "agent": a,
                                 "lambda_hat": lam[a], "null_lo": lo, **v})
        for a in AGENTS:
            fish_rows.append({"noise": noise, "agent": a, **fish_on_agent(a, srcs, m, noise, rng)})

    res = pd.DataFrame(rows)
    res.to_csv(OUT / f"forced_cut_power{TAG}.csv", index=False)
    fr = pd.DataFrame(fish_rows).drop(columns="r2_within")
    fr.to_csv(OUT / f"fish_on_scripted{TAG}.csv", index=False)
    pd.set_option("display.width", 220)
    print(res.pivot_table(index=["rule", "noise", "n_sources"], columns="agent", values=["SBR", "enforcement", "following"]).round(2).to_string())
    print("\nFish et al. regression on scripted firms:")
    print(fr.round(3).to_string(index=False))

    fig, axes = plt.subplots(1, len(AGENTS), figsize=(14, 2.8), sharey=True)
    r = np.arange(BRANCH + 1, BRANCH + H + 1)
    for ax, a in zip(axes, AGENTS):
        ctl, dev = paths[a]
        ax.plot(r, dev[:, 0] - ctl[:, 0], color="#2a6fdb", label="Firm A")
        ax.plot(r, dev[:, 1] - ctl[:, 1], color="#999", label="Firm B (forced)")
        ax.axhline(0, color="k", lw=0.5)
        ax.axvspan(201.5, 206.5, color="#f2f2f2", zorder=-1)
        ax.set_title(a)
        ax.set_xlabel("round")
    axes[0].set_ylabel("index, deviate - control")
    axes[0].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / f"forced_cut_paths{TAG}.png", dpi=160)
