"""
Anti-collusion mechanisms on Claude Haiku 5.5 (or, with the argument haiku45, Claude Haiku 4.5 with extended
thinking off), from the same 8 high-price states as the forced-cut test.

After 3 settling rounds (branch round B), each state continues under:
    control  no change
    hidden   rival prices dropped from new market data (targets enforcement: deviations can't be seen)
    rpe      relative-performance pay: score = own profit - rival's profit (targets the gain from colluding)
    brinfo   the platform reports each firm's static best response to the rival's price (targets slow learning)

Outcome: market collusion index (0 = Nash, 1 = monopoly), mechanism minus control, paired by source.
Late window = the last 12 rounds of the 24-round arms (B+13..B+24); hidden ran 12 rounds, so it is
compared on B+1..B+12. Exact sign-flip test over sources (two-sided).

Usage:  uv run --extra analysis python theory/mechanism_results.py [haiku | haiku45]
Writes: theory/out/mechanisms.csv, theory/out/mechanisms.json, theory/out/mechanisms.png
        (mechanisms_haiku45.* for haiku45)
"""

import itertools
import json
import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from bandit import benchmarks, profits

FRONTIER = Path(__file__).resolve().parents[1] / "succession/runs/frontier"
MODEL = sys.argv[1] if len(sys.argv) > 1 else "haiku"
RUNS = FRONTIER / MODEL
SUFFIX = "" if MODEL == "haiku" else f"_{MODEL}"
MODEL_NAMES = {"haiku": "Claude Haiku 5.5", "haiku45": "Claude Haiku 4.5", "haiku45_enforcer": "Haiku 4.5, first enforcer attempt",
               "haiku45_enforcer2": "Haiku 4.5, told to enforce"}
OUT = Path(__file__).resolve().parent / "out"
FIRMS = ("Firm A", "Firm B")
ARMS = ("control", "hidden", "rpe", "brinfo", "deviate")
LABELS = {"control": "control", "hidden": "hidden rival prices", "rpe": "relative-performance pay",
          "brinfo": "best-response information", "deviate": "forced cut, after B+12"}
COLORS = {"control": "#555555", "hidden": "#8e44ad", "rpe": "#c0392b", "brinfo": "#2a6fdb", "deviate": "#e67e22"}


def read() -> dict:
    """source -> arm -> rounds x 2 index (and profit) arrays, arms starting at B+1."""
    out = {}
    for f in sorted(RUNS.glob("*.jsonl")):
        if f.name == "usage.jsonl":
            continue
        source, arm = f.stem.rsplit("_", 1)
        rows = [json.loads(line) for line in f.read_text().splitlines() if line.strip()]
        rounds = sorted({r["round"] for r in rows})
        d = {k: np.full((len(rounds), 2), np.nan) for k in ("delta", "profit")}
        for r in rows:
            for k, arr in d.items():
                arr[rounds.index(r["round"]), FIRMS.index(r["firm"])] = r[k]
        out.setdefault(source, {})[arm] = d
    return out


def sign_flip_p(diffs) -> float:
    """Exact two-sided paired sign-flip test of mean zero."""
    diffs = np.asarray(diffs)
    obs = abs(diffs.mean())
    flips = np.array(list(itertools.product((-1, 1), repeat=len(diffs))))
    return float((np.abs((flips * diffs).mean(1)) >= obs - 1e-12).mean())


def boot_ci(v, rng, n=5000):
    v = np.asarray(v)
    return np.percentile(v[rng.integers(len(v), size=(n, len(v)))].mean(1), [2.5, 97.5]).tolist()


def relative_profit_equilibrium() -> float:
    """Symmetric equilibrium price when each firm maximises own profit minus the rival's (alpha = 1)."""
    grid = np.linspace(1.0, 2.5, 3001)
    p = 1.6
    for _ in range(200):
        P = np.stack([grid, np.full_like(grid, p)], 1)
        pi = profits(P)
        p_new = grid[np.argmax(pi[:, 0] - pi[:, 1])]
        if abs(p_new - p) < 1e-6:
            break
        p = p_new
    return p


if __name__ == "__main__":
    rng = np.random.default_rng(5)
    runs = {s: a for s, a in read().items() if {"settle", "control"} <= a.keys()}
    pn, pm = benchmarks(2)
    p_rel = relative_profit_equilibrium()
    rows, summary = [], {}
    for s, a in runs.items():
        ctl = a["control"]["delta"].mean(1)
        row = {"source": s, "index_at_branch": float(a["settle"]["delta"][-1].mean())}
        for arm in ARMS[1:]:
            if arm not in a:
                continue
            m = a[arm]["delta"].mean(1)
            if arm == "hidden":
                window = slice(0, 12)
            else:
                window = slice(12, 24)
                if len(m) < 24 or len(ctl) < 24:
                    continue
            row[f"{arm}_index"] = float(m[window].mean())
            row[f"{arm}_control_index"] = float(ctl[window].mean())
            row[f"{arm}_effect"] = float(m[window].mean() - ctl[window].mean())
            row[f"{arm}_profit_effect"] = float(a[arm]["profit"][window].sum(1).mean()
                                                - a["control"]["profit"][window].sum(1).mean())
        rows.append(row)
    for arm in ARMS[1:]:
        eff = [r[f"{arm}_effect"] for r in rows if f"{arm}_effect" in r]
        if not eff:
            continue
        prof = [r[f"{arm}_profit_effect"] for r in rows if f"{arm}_profit_effect" in r]
        lvl = [r[f"{arm}_index"] for r in rows if f"{arm}_index" in r]
        summary[arm] = {"sources": len(eff), "effect": float(np.mean(eff)), "effect_ci": boot_ci(eff, rng),
                        "p_sign_flip": sign_flip_p(eff), "lower_in": int(np.sum(np.array(eff) < 0)),
                        "index": float(np.mean(lvl)),
                        "control_index": float(np.mean([r[f"{arm}_control_index"] for r in rows
                                                        if f"{arm}_control_index" in r])),
                        "near_nash": int(np.sum(np.abs(lvl) <= 0.1)),
                        "profit_effect": float(np.mean(prof))}
    summary["benchmarks"] = {"nash_index": 0.0, "relative_profit_eq_price": p_rel,
                             "relative_profit_eq_index": float((p_rel - pn) / (pm - pn))}
    pl.DataFrame(rows).write_csv(OUT / f"mechanisms{SUFFIX}.csv")
    (OUT / f"mechanisms{SUFFIX}.json").write_text(json.dumps({"summary": summary, "per_source": rows}, indent=1))

    fig, ax = plt.subplots(figsize=(6.6, 3.8))
    for arm in ARMS:
        paths = [a[arm]["delta"].mean(1) for a in runs.values() if arm in a]
        n = min(len(p) for p in paths) if paths else 0
        if not n or (arm == "deviate" and n < 24):  # 12-round forced-cut arms are in frontier_forced_cut.png
            continue
        P = np.array([p[:n] for p in paths])
        k = np.arange(1, n + 1)
        ax.plot(k, P.mean(0), color=COLORS[arm], lw=1.8, label=f"{LABELS[arm]} (n={len(P)})")
        lo, hi = np.percentile(P[rng.integers(len(P), size=(2000, len(P)))].mean(1), [2.5, 97.5], axis=0)
        ax.fill_between(k, lo, hi, color=COLORS[arm], alpha=0.12)
    ax.axhline(0, color="k", lw=0.6)
    ax.text(0.6, 0.02, "Nash", fontsize=7, va="bottom")
    ax.axhline(summary["benchmarks"]["relative_profit_eq_index"], color=COLORS["rpe"], lw=0.6, ls=":")
    ax.set_xlabel("rounds after the branch")
    ax.set_ylabel("market collusion index")
    ax.set_title(f"{MODEL_NAMES[MODEL]} from {len(runs)} high-price states")
    ax.legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / f"mechanisms{SUFFIX}.png", dpi=160)
    panels = [OUT / "mechanisms.png", OUT / "mechanisms_haiku45.png"]
    if all(p.exists() for p in panels):  # the paper's figure: both models side by side
        both, axes = plt.subplots(1, 2, figsize=(13.2, 3.8))
        for ax, path in zip(axes, panels):
            ax.imshow(plt.imread(path))
            ax.axis("off")
        both.tight_layout(pad=0)
        both.savefig(OUT / "mechanisms_two_models.png", dpi=160)

    print(f"relative-profit equilibrium price {p_rel:.3f} (index {summary['benchmarks']['relative_profit_eq_index']:+.2f})")
    for arm, v in summary.items():
        if arm == "benchmarks":
            continue
        print(f"{LABELS[arm]:<27} effect {v['effect']:+.3f} CI [{v['effect_ci'][0]:+.3f}, {v['effect_ci'][1]:+.3f}]"
              f"  p={v['p_sign_flip']:.3f}  lower in {v['lower_in']}/{v['sources']}"
              f"  index {v['index']:+.2f} vs control {v['control_index']:+.2f}"
              f"  near Nash {v['near_nash']}/{v['sources']}  profit {v['profit_effect']:+.1f}/round")
