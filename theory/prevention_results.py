"""
Prevention test: do anti-collusion mechanisms stop high prices from forming in the first place?

Fresh Claude duopolies played from round 1 with experiments_synthetic/duopoly.py, three arms:
    baseline  no mechanism
    rpe       relative-performance pay from round 1   (--mechanism rpe)
    brinfo    best-response information from round 1  (--mechanism brinfo)
Outcome: market collusion index (0 = Nash, 1 = monopoly), mean over the second half of each game,
each mechanism vs baseline (games are independent, so a two-sample permutation test).

Run locally (model calls bill to your own key, not the cloud credits):
    export PRICING_ANTHROPIC_API_KEY=...        # never commit it
    for m in "" "--mechanism rpe" "--mechanism brinfo"; do
      CLAUDE_EFFORT=medium uv run python experiments_synthetic/duopoly.py --provider anthropic \\
        --model claude-haiku-5-5 --rounds 100 --seeds 1 2 3 4 5 6 $m -y &
    done; wait
    uv run --extra analysis python theory/prevention_results.py

Writes: theory/out/prevention.csv, theory/out/prevention.png
"""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl

# the committed copy of the 18 games (experiments_synthetic/experiments_runs/ is not committed)
RUNS = Path(__file__).resolve().parents[1] / "succession/runs/prevention/games"
OUT = Path(__file__).resolve().parent / "out"
ARMS = ("baseline", "rpe", "brinfo")
ROUNDS = 100  # the protocol's game length; anything else is not a prevention game
LABELS = {"baseline": "baseline", "rpe": "relative-performance pay", "brinfo": "best-response information"}
COLORS = {"baseline": "#555555", "rpe": "#c0392b", "brinfo": "#2a6fdb"}
MODEL_NAMES = {"claude-haiku-5-5": "Claude Haiku 5.5", "claude-fable-5-1": "Claude Fable 5.1"}


def games(model: str) -> dict:
    """arm -> list of rounds-long market index paths, complete games of `model` only."""
    out = {a: [] for a in ARMS}
    for f in sorted(RUNS.glob("*/results.json")):
        meta = json.loads((f.parent / "metadata.json").read_text())
        if model not in str(meta.get("agents_models", "")):
            continue
        if "stub" in str(meta.get("agents_providers", "")) or meta.get("num_rounds") != ROUNDS:
            continue  # offline rehearsals and short smoke-test games are not part of the experiment
        name = f.parent.name
        arm = "rpe" if "_rpe_" in name else "brinfo" if "_brinfo_" in name else "baseline"
        env = meta["environment"]["environment_params"]
        pn, pm = env["nash_prices"][0], env["monopoly_prices"][0]
        res = json.loads(f.read_text())
        n = min(len(v) for v in res.values())
        if n < meta["num_rounds"]:
            continue  # unfinished
        P = np.array([[res[firm][str(r)]["chosen_price"] for firm in res] for r in range(1, n + 1)])
        out[arm].append(((P - pn) / (pm - pn)).mean(1))
    return out


def perm_p(a, b, rng, n=20000) -> float:
    """Two-sided permutation test of equal means."""
    a, b = np.asarray(a), np.asarray(b)
    pooled, obs = np.concatenate([a, b]), abs(a.mean() - b.mean())
    hits = 0
    for _ in range(n):
        rng.shuffle(pooled)
        hits += abs(pooled[:len(a)].mean() - pooled[len(a):].mean()) >= obs - 1e-12
    return hits / n


if __name__ == "__main__":
    model = sys.argv[1] if len(sys.argv) > 1 else "claude-haiku-5-5"
    rng = np.random.default_rng(3)
    g = games(model)
    rows = []
    base = [p[len(p) // 2:].mean() for p in g["baseline"]]
    for arm in ARMS:
        late = [p[len(p) // 2:].mean() for p in g[arm]]
        if not late:
            continue
        row = {"arm": arm, "games": len(late), "index_second_half": float(np.mean(late)),
               "sd": float(np.std(late, ddof=1)) if len(late) > 1 else float("nan")}
        if arm != "baseline" and len(base) > 1 and len(late) > 1:
            row["effect_vs_baseline"] = float(np.mean(late) - np.mean(base))
            row["p_permutation"] = perm_p(late, base, rng)
        rows.append(row)
        print(row)
    pl.DataFrame(rows).write_csv(OUT / "prevention.csv")

    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    for arm in ARMS:
        if not g[arm]:
            continue
        n = min(len(p) for p in g[arm])
        P = np.array([p[:n] for p in g[arm]])
        k = np.arange(1, n + 1)
        ax.plot(k, P.mean(0), color=COLORS[arm], lw=1.6, label=f"{LABELS[arm]} (n={len(P)})")
        # 95% bootstrap band of the mean over games, as in the removal figure (mechanisms.png)
        lo, hi = np.percentile(P[rng.integers(len(P), size=(2000, len(P)))].mean(1), [2.5, 97.5], axis=0)
        ax.fill_between(k, lo, hi, color=COLORS[arm], alpha=0.12)
    ax.axhline(0, color="k", lw=0.6)
    ax.text(0.6, 0.02, "Nash", fontsize=7, va="bottom")
    bench = OUT / "mechanisms.json"  # relative-profit equilibrium, computed by mechanism_results.py
    if bench.exists():
        eq = json.loads(bench.read_text())["summary"]["benchmarks"]["relative_profit_eq_index"]
        ax.axhline(eq, color=COLORS["rpe"], lw=0.6, ls=":", label="relative-profit equilibrium")
    ax.set_xlabel("round")
    ax.set_ylabel("market collusion index")
    ax.set_title(f"{MODEL_NAMES.get(model, model)}: mechanisms from round 1")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "prevention.png", dpi=160)
