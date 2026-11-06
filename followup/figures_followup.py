"""
Figures for follow-up waves 5-8 (November 2026, not part of the submission). Per-game values come from each
wave's out/*.json; the per-round paths and the best-response curve are computed from the saved games.

    out/opus_remedies.png   every remedy tested on Opus 5.5, each game's index over rounds 51-100
    out/wave6_lifted.png    mean index by round: the limit kept, lifted after round 50, the estimate, baseline
    out/wave8_mixed.png     each mixed game's Opus index against its rival's

Usage:  uv run --extra analysis python followup/figures_followup.py
"""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "theory")]
import bandit  # noqa: E402
import prevention45_results as p  # noqa: E402
import wave3_results as w3  # noqa: E402
import wave5_results as w5  # noqa: E402
import wave6_results as w6  # noqa: E402
import wave7_results as w7  # noqa: E402

OUT = HERE / "out"
SURFACE, INK, INK2, MUTED, GRID, AXIS = (
    "#fcfcfb",
    "#0b0b0b",
    "#52514e",
    "#898781",
    "#e1e0d9",
    "#c3c2b7",
)
SERIES = ("#2a78d6", "#eb6834", "#1baf7a")  # validated light slots 1-3, all pairs
plt.rcParams.update(
    {
        "font.family": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
        "font.size": 9,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "axes.edgecolor": AXIS,
        "axes.labelcolor": INK2,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelcolor": INK2,
        "ytick.labelcolor": INK2,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
    }
)


def load(name: str) -> dict:
    return json.loads((OUT / name).read_text())


def opus_remedies():
    w2, w3j, w4, w5j = (
        load("wave2.json"),
        load("wave3.json"),
        load("wave4.json"),
        load("wave5.json"),
    )
    w6j, w7j = load("wave6.json"), load("wave7.json")
    rows3 = {r["arm"]: r["index_by_game"] for r in w3j["rows"]}
    stage = {r["arm"]: r["index_by_game"] for r in w2["stage_b"]["opus55"]}
    hidden = next(r["index_by_game"] for r in w4["prevention"] if r["arm"] == "hidden")
    arms = [
        ("Baseline", "", rows3["baseline"]),
        ("Best-response information", "wave 2", stage["brinfo"]),
        ("10% cut every 10 rounds", "wave 2", stage["cut10"]),
        ("Forced Nash every 10 rounds", "wave 3", rows3["forced10"]),
        ("Forced Nash every 5 rounds", "wave 3", rows3["forced5"]),
        ("Hidden rival prices", "wave 4", hidden),
        (
            "Hidden prices, best-price trials",
            "wave 5",
            w5j["confirmation"]["r1d-hidden-br-trial"]["primary_by_game"],
        ),
        (
            "Best-response price limit",
            "wave 5",
            w5j["confirmation"]["r1b-br-limit"]["primary_by_game"],
        ),
        ("Limit lifted after round 50", "wave 6", w6j["rules"]["w6-lifted"]["primary_by_game"]),
        ("Limit, no threat", "wave 6", w6j["rules"]["w6-limit-no-threat"]["primary_by_game"]),
        ("Estimate, with threat", "wave 6", w6j["rules"]["w6-estimate-threat"]["primary_by_game"]),
        ("Estimate, no threat", "wave 7", w7j["w7-estimate-no-threat"]["primary_by_game"]),
    ]
    base_mean = float(np.mean(arms[0][2]))
    fig, ax = plt.subplots(figsize=(7.6, 4.9), layout="constrained")
    n = len(arms)
    ax.axvline(0, color=AXIS, lw=1, zorder=0)
    ax.axvline(0.3, color=GRID, lw=1, ls=(0, (2, 2)), zorder=0)
    ax.axvline(base_mean, color=MUTED, lw=1, ls=(0, (4, 3)), zorder=0)
    ax.text(0, n - 0.35, "Nash", color=MUTED, fontsize=7.5, ha="center", va="bottom")
    ax.text(0.3, n - 0.35, "ends high", color=MUTED, fontsize=7.5, ha="center", va="bottom")
    ax.text(
        base_mean + 0.015,
        n - 0.35,
        f"baseline {base_mean:.2f}",
        color=MUTED,
        fontsize=7.5,
        ha="left",
        va="bottom",
    )
    rng = np.random.default_rng(2026)
    for i, (label, wave, vals) in enumerate(arms):
        y = n - 1 - i
        vals = np.asarray(vals, float)
        color = MUTED if i == 0 else SERIES[0]
        ax.scatter(
            vals,
            y + rng.uniform(-0.18, 0.18, len(vals)),
            s=22,
            color=color,
            alpha=0.85,
            edgecolors=SURFACE,
            linewidths=0.8,
            zorder=3,
        )
        ax.plot([vals.mean()] * 2, [y - 0.32, y + 0.32], color=INK, lw=1.6, zorder=4)
        ax.text(
            1.3,
            y,
            f"{vals.mean():.2f}".replace("-0.00", "0.00"),
            color=INK,
            fontsize=8,
            va="center",
            ha="right",
        )
    ax.text(1.3, n - 0.35, "mean", color=MUTED, fontsize=7.5, ha="right", va="bottom")
    ax.set_yticks(
        range(n), [f"{a}" + (f"  ({w})" if w else f"  ({len(v)} games)") for a, w, v in arms][::-1]
    )
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlim(-0.15, 1.32)
    ax.set_ylim(-0.6, n + 0.1)
    ax.set_xlabel("Market index, rounds 51–100 (0 = Nash, 1 = monopoly)")
    fig.savefig(OUT / "opus_remedies.png", dpi=200)
    plt.close(fig)


def mean_path(xs: list) -> np.ndarray:
    return np.mean([p.index(x)[:100] for x in xs], axis=0)


def wave6_lifted():
    kept = w5.games(w5.RUNS / "confirm", "r1b-br-limit", 100)
    lifted = w5.games(w6.RUNS, "w6-lifted", 100)
    estimate = w5.games(w7.RUNS, w7.RULE, 100)
    base = w3.opus_games()["baseline"]
    t = np.arange(1, 101)
    fig, ax = plt.subplots(figsize=(7.6, 3.8), layout="constrained")
    ax.axhline(0, color=AXIS, lw=1, zorder=0)
    ax.axvline(50.5, color=GRID, lw=1, zorder=0)
    ax.text(
        51.5,
        1.55,
        "limit ends after round 50\n(lifted games only)",
        color=MUTED,
        fontsize=7.5,
        va="top",
    )
    ax.text(
        7, 1.55, "every arm opens above the scale, up to 3.9", color=MUTED, fontsize=7.5, va="top"
    )
    lines = [
        ("Baseline (15 games)", base, MUTED),
        ("Estimate, no threat (wave 7)", estimate, SERIES[2]),
        ("Limit lifted after round 50 (wave 6)", lifted, SERIES[1]),
        ("Limit kept (wave 5)", kept, SERIES[0]),
    ]
    for label, xs, color in lines:
        y = mean_path(xs)
        ax.plot(t, y, color=color, lw=1.6, solid_capstyle="round")
        ax.text(101.5, float(y[-5:].mean()), label, color=INK2, fontsize=7.5, va="center")
    ax.set_xlim(1, 100)
    ax.set_ylim(-0.1, 1.6)
    ax.set_xlabel("Round")
    ax.set_ylabel("Mean market index")
    ax.yaxis.grid(True, color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    fig.savefig(OUT / "wave6_lifted.png", dpi=200)
    plt.close(fig)


def br_index(x: np.ndarray) -> np.ndarray:
    pn, pm = bandit.benchmarks(2)
    rival = pn + x * (pm - pn)
    br = bandit.best_response(np.column_stack([np.full_like(rival, pn), rival]))[:, 0]
    return (br - pn) / (pm - pn)


def wave8_mixed():
    w8 = load("wave8.json")
    lf = w8["exploratory_brinfo"]["leader_follower_benchmark"]
    arms = [
        ("opus-haiku55", "Opus and Haiku 5.5", SERIES[0], "o"),
        ("opus-haiku45", "Opus and Haiku 4.5", SERIES[1], "s"),
        ("opus-haiku45-brinfo", "Opus and Haiku 4.5, with the estimate", SERIES[2], "^"),
    ]
    top = 0.95
    fig, ax = plt.subplots(figsize=(6.4, 5.0), layout="constrained")
    grid = np.linspace(0, 0.9, 200)
    ax.plot(grid, grid, color=MUTED, lw=1, ls=(0, (4, 3)), zorder=1)
    ax.text(0.64, 0.72, "matched prices", color=MUTED, fontsize=7.5, rotation=45, ha="center")
    ax.plot(grid, br_index(grid), color=INK2, lw=1, zorder=1)
    ax.text(
        0.66,
        float(br_index(np.array([0.66]))[0]) - 0.03,
        "rival at its best response",
        color=INK2,
        fontsize=7.5,
        rotation=23,
        va="top",
        ha="center",
    )
    ax.scatter([lf["opus"]], [lf["haiku45"]], marker="+", s=140, color=INK, lw=1.4, zorder=5)
    ax.annotate(
        "leader-follower outcome",
        (lf["opus"], lf["haiku45"]),
        (0.43, 0.04),
        color=INK,
        fontsize=7.5,
        arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 0.8},
    )
    for key, label, color, marker in arms:
        g = w8["arms"][key]["by_game"]
        x = np.array([v["opus"] for v in g])
        y = np.array([v["rival"] for v in g])
        off = y > top
        ax.scatter(
            x[~off],
            y[~off],
            s=46,
            marker=marker,
            color=color,
            edgecolors=SURFACE,
            linewidths=1,
            zorder=4,
            label=label,
        )
        for xi, yi in zip(x[off], y[off]):
            ax.scatter(
                [xi], [top - 0.01], s=46, marker=marker, color=color, edgecolors=SURFACE, zorder=4
            )
            ax.annotate(
                f"off the scale:\nrival at {yi:.2f}",
                (xi, top - 0.01),
                (xi + 0.04, top - 0.07),
                color=INK2,
                fontsize=7.5,
                arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 0.8},
            )
    ax.set_xlim(-0.05, 0.9)
    ax.set_ylim(-0.05, top)
    ax.set_xlabel("Opus 5.5's own index, rounds 51–100")
    ax.set_ylabel("Rival's own index, rounds 51–100")
    ax.legend(frameon=False, fontsize=8, loc="upper left", labelcolor=INK2)
    ax.set_aspect("equal")
    fig.savefig(OUT / "wave8_mixed.png", dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    opus_remedies()
    wave6_lifted()
    wave8_mixed()
    print("wrote out/opus_remedies.png, out/wave6_lifted.png, out/wave8_mixed.png")
