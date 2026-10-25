"""
Forced-cut test on the cloud runs (theory/FRONTIER_TEST.md): Claude Haiku 5.5 and Fable 5.1, each taking
over the same saved Mistral states, 3 settling rounds, then 12-round control / deviate (/ hidden) arms.

Branch round B = the last settling round. Firm B's price in B+1 is forced to Nash.
    punishment  Firm A's mean collusion index over B+2..B+6, deviate minus control
    return      Firm A's index at B+12, deviate minus control
    null band   the lower of two 2.5th percentiles of mean punishment over the same n sources:
                (1) SBR (thesis P1 direction rule) with the model's own move rate and step sizes,
                (2) a partial-adjustment best responder whose speed lambda is the OLS slope of the
                    model's own price changes on its gap to its best response, control arms only.
                Both are simulated from each source's real state at B (theory/forced_cut.py).
    verdict     enforcement: punishment below the band and return closing at least half of it;
                following: below the band without return; non-strategic: inside the band.

Usage:  uv run --extra analysis python theory/frontier_results.py
Writes: theory/out/frontier_forced_cut.csv, theory/out/frontier_forced_cut.json,
        theory/out/frontier_forced_cut.png
"""

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("FORCED_CUT_HORIZON", "12")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
import forced_cut as fc
from bandit import MOVE, best_response, fit, load, markets

RUNS = Path(__file__).resolve().parents[1] / "succession/runs/frontier"
OUT = Path(__file__).resolve().parent / "out"
MODELS = {"haiku": "Claude Haiku 5.5", "fable": "Claude Fable 5.1", "haiku45": "Claude Haiku 4.5",
          "haiku45_enforcer": "Haiku 4.5, first enforcer attempt", "haiku45_enforcer2": "Haiku 4.5, told to enforce"}
H = fc.H
FIRMS = ("Firm A", "Firm B")


def read(model: str) -> dict:
    """source -> arm -> {"delta": rounds x 2, "price": rounds x 2, "rounds": list}."""
    out = {}
    for f in sorted((RUNS / model).glob("*.jsonl")):
        if f.name == "usage.jsonl":
            continue
        source, arm = f.stem.rsplit("_", 1)
        rows = [json.loads(line) for line in f.read_text().splitlines() if line.strip()]
        rounds = sorted({r["round"] for r in rows})
        d = {k: np.full((len(rounds), 2), np.nan) for k in ("delta", "price")}
        for r in rows:
            for k, arr in d.items():
                arr[rounds.index(r["round"]), FIRMS.index(r["firm"])] = r[k]
        n = len(rounds) if arm == "settle" else H  # arms may run longer (mechanism runs extend control)
        out.setdefault(source, {})[arm] = {"delta": d["delta"][:n], "price": d["price"][:n], "rounds": rounds[:n]}
    return {s: a for s, a in out.items() if {"settle", "control", "deviate"} <= a.keys()
            and len(a["control"]["rounds"]) == H and len(a["deviate"]["rounds"]) == H}


def observed(runs: dict) -> list:
    rows = []
    for s, a in runs.items():
        c, d = a["control"]["delta"], a["deviate"]["delta"]
        row = {"source": s, "branch_round": a["settle"]["rounds"][-1],
               "index_at_branch": float(a["settle"]["delta"][-1].mean()),
               "punishment": float(d[1:6, 0].mean() - c[1:6, 0].mean()),
               "return": float(d[H - 1, 0] - c[H - 1, 0]),
               "cutter_gap": float(d[1:, 1].mean() - c[1:, 1].mean()),  # Firm B after its forced round
               "hidden": np.nan}
        if "hidden" in a and len(a["hidden"]["rounds"]) == H:
            row["hidden"] = float(a["hidden"]["delta"].mean() - c.mean())
        rows.append(row)
    return rows


def own_noise(runs: dict) -> tuple:
    """Move rate, step sizes (|d log p| of moves) and lambda-hat from the control arms."""
    dlog, gap, dp = [], [], []
    for a in runs.values():
        P = np.vstack([a["settle"]["price"][-1:], a["control"]["price"]])  # branch state, then the arm
        dlog.append(np.abs(np.diff(np.log(P), axis=0)).ravel())
        gap.append((best_response(P[:-1]) - P[:-1]).ravel())
        dp.append(np.diff(P, axis=0).ravel())
    dlog = np.concatenate(dlog)
    lam = float(np.clip(np.polyfit(np.concatenate(gap), np.concatenate(dp), 1)[0], 0.0, 1.0))
    steps = dlog[dlog > MOVE]
    return float((dlog > MOVE).mean()), steps if steps.size else np.array([MOVE]), lam


def simulate(agent: str, src: dict, m: dict, rng, lam: float):
    """Firm A's deviate-minus-control index per rep and round, and the hidden-arm null (control vs control)."""
    ctl = fc.index(fc.continuation(agent, src, m, False, 1.0, rng, lam=lam))
    dev = fc.index(fc.continuation(agent, src, m, True, 1.0, rng, lam=lam))
    ctl2 = fc.index(fc.continuation(agent, src, m, False, 1.0, rng, lam=lam))
    return dev[:, :, 0] - ctl[:, :, 0], ctl2.mean((1, 2)) - ctl.mean((1, 2))


def band(draws: list, rng, n_draws=4000) -> np.ndarray:
    """Percentiles of the mean over sources, one simulated rep per source; draws: sources x reps (x rounds)."""
    D = np.array(draws)
    pick = rng.integers(D.shape[1], size=(n_draws, D.shape[0]))
    means = D[np.arange(D.shape[0]), pick].mean(1)
    return np.percentile(means, [2.5, 97.5], axis=0)


def boot_ci(v, rng, n=5000):
    v = np.asarray(v)
    return np.percentile(v[rng.integers(len(v), size=(n, len(v)))].mean(1), [2.5, 97.5])


def analyse(model: str, m_thesis: dict, rng) -> dict:
    runs = read(model)
    rows = observed(runs)
    move_p, steps, lam = own_noise(runs)
    m = dict(m_thesis, move_p={101: move_p}, steps={101: steps})
    sims = {"sbr": [], "br": []}
    hidden_null = []
    for a in runs.values():
        src = {"P": a["settle"]["price"][-1:], "last_dir": np.zeros(2), "last_won": np.zeros(2, bool)}
        for agent, draws in sims.items():
            dA, hid = simulate(agent, src, m, rng, lam)
            draws.append(dA)
            if agent == "sbr":
                hidden_null.append(hid)
    pun_bands = {k: band([d[:, 1:6].mean(1) for d in v], rng) for k, v in sims.items()}
    lo = min(b[0] for b in pun_bands.values())
    pun = float(np.mean([r["punishment"] for r in rows]))
    ret = float(np.mean([r["return"] for r in rows]))
    if pun < lo:
        verdict = "enforcement" if ret >= pun / 2 else "following"
    else:
        verdict = "non-strategic"
    hid = [r["hidden"] for r in rows if np.isfinite(r["hidden"])]
    res = {
        "model": MODELS[model], "sources": len(rows), "verdict": verdict,
        "punishment": pun, "punishment_ci": boot_ci([r["punishment"] for r in rows], rng).tolist(),
        "return": ret, "return_ci": boot_ci([r["return"] for r in rows], rng).tolist(),
        "null_lo": lo, "null_sbr": pun_bands["sbr"].tolist(), "null_br": pun_bands["br"].tolist(),
        "cutter_gap": float(np.mean([r["cutter_gap"] for r in rows])),
        "move_rate": move_p, "median_step": float(np.median(steps)),
        "step_vs_mistral": float(np.median(steps) / np.median(m_thesis["steps"][101])),
        "lambda_hat": lam,
        "path_band": {k: band(v, rng).tolist() for k, v in sims.items()},
        "per_source": rows,
    }
    if hid:
        res["hidden"] = float(np.mean(hid))
        res["hidden_ci"] = boot_ci(hid, rng).tolist()
        res["hidden_null_sbr"] = band([hidden_null[i] for i, r in enumerate(rows)
                                       if np.isfinite(r["hidden"])], rng).tolist()
    usage = [json.loads(line) for line in (RUNS / model / "usage.jsonl").read_text().splitlines() if line.strip()]
    res["calls"], res["errors"] = len(usage), sum(bool(u.get("is_error")) for u in usage)
    res["refusals"] = sum(u.get("stop_reason") == "refusal" for u in usage)
    res["cost_usd"] = sum(u.get("cost_usd", 0) for u in usage)
    res["paths"] = {arm: np.nanmean([runs[s][arm]["delta"] for s in runs if arm in runs[s]], 0).tolist()
                    for arm in ("control", "deviate")}
    return res


def plot(results: dict):
    results = {k: v for k, v in results.items() if k != "haiku45_enforcer"}  # the first enforcer attempt: text only
    cols = 2 if len(results) == 4 else len(results)  # four models read better as a 2 x 2 grid
    rows = -(-len(results) // cols)
    fig, axes = plt.subplots(rows, cols, figsize=(5.2 * cols, 3.4 * rows), sharey=True, squeeze=False)
    for ax, (model, r) in zip(axes.flat, results.items()):
        k = np.arange(1, H + 1)
        ctl, dev = np.array(r["paths"]["control"]), np.array(r["paths"]["deviate"])
        for name, color in (("sbr", "#2a6fdb"), ("br", "#e67e22")):
            lo, hi = r["path_band"][name]
            ax.fill_between(k, lo, hi, color=color, alpha=0.15,
                            label=f"null: {'SBR' if name == 'sbr' else 'best responder'} (95%)")
        ax.plot(k, dev[:, 0] - ctl[:, 0], "-o", ms=3, color="k", label="Firm A (responder)")
        ax.plot(k, dev[:, 1] - ctl[:, 1], "--", color="#888", label="Firm B (forced to Nash at +1)")
        ax.axhline(0, color="k", lw=0.5)
        ax.axvspan(1.5, 6.5, color="#f2f2f2", zorder=-1)
        ax.set_title(f"{r['model']}: {r['verdict']} (n={r['sources']})")
        ax.set_xlabel("rounds after the branch")
    for ax in axes[:, 0]:
        ax.set_ylabel("collusion index, deviate - control")
    axes[0, 0].legend(frameon=False, fontsize=7, loc="lower right")
    fig.tight_layout()
    fig.savefig(OUT / "frontier_forced_cut.png", dpi=160)


if __name__ == "__main__":
    rng = np.random.default_rng(11)
    duo = load().filter(pl.col("num_agents") == 2)
    m_thesis = fit(markets(duo.filter(pl.col("prompt") == "P1")))
    results = {k: analyse(k, m_thesis, rng) for k in MODELS if (RUNS / k).exists()}
    plot(results)
    pl.DataFrame([{"model": r["model"], **row} for r in results.values() for row in r["per_source"]]) \
        .write_csv(OUT / "frontier_forced_cut.csv")
    (OUT / "frontier_forced_cut.json").write_text(json.dumps(results, indent=1))
    for r in results.values():
        print(f"\n{r['model']}: {r['verdict']}  ({r['sources']} sources, {r['calls']} calls, "
              f"${r['cost_usd']:.2f}, {r['errors']} errors, {r['refusals']} refusals)")
        print(f"  punishment {r['punishment']:+.3f}  CI [{r['punishment_ci'][0]:+.3f}, {r['punishment_ci'][1]:+.3f}]"
              f"  band lo {r['null_lo']:+.3f}  (SBR [{r['null_sbr'][0]:+.3f}, {r['null_sbr'][1]:+.3f}],"
              f" BR [{r['null_br'][0]:+.3f}, {r['null_br'][1]:+.3f}])")
        print(f"  return {r['return']:+.3f}  CI [{r['return_ci'][0]:+.3f}, {r['return_ci'][1]:+.3f}];"
              f"  cutter B after the cut {r['cutter_gap']:+.3f}")
        print(f"  own noise: move rate {r['move_rate']:.2f}, median step {r['median_step']:.4f} "
              f"(x{r['step_vs_mistral']:.1f} Mistral), lambda-hat {r['lambda_hat']:.3f}")
        if "hidden" in r:
            print(f"  hidden {r['hidden']:+.3f}  CI [{r['hidden_ci'][0]:+.3f}, {r['hidden_ci'][1]:+.3f}]"
                  f"  SBR null [{r['hidden_null_sbr'][0]:+.3f}, {r['hidden_null_sbr'][1]:+.3f}]")
        for row in r["per_source"]:
            print(f"    {row['source']}: index {row['index_at_branch']:.2f}  punishment {row['punishment']:+.3f}"
                  f"  return {row['return']:+.3f}  B {row['cutter_gap']:+.3f}")
