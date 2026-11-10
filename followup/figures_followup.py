"""
Figures for the follow-up (November 2026, not part of the submission). Per-game values come from each
wave's out/*.json; the per-round paths and the best-response curve are computed from the saved games.

    out/forced_cut_schematic.png  an illustration of the forced-cut test (not data)
    out/models_baseline.png    each model against itself, each game's index over rounds 51-100
    out/haiku45_number.png     Haiku 4.5 and Haiku 5.5 shown a right or a wrong best-response number
    out/opus_sawtooth.png      Opus 5.5's mean index by round under forced Nash rounds
    out/diagnosis_summary.png  every forced-cut and forced-raise response against its null band (base scale)
    out/opus_remedies.png   every remedy tested on Opus 5.5, each game's index over rounds 51-100
    out/wave6_lifted.png    mean index by round: the limit kept, lifted after round 50, the estimate, baseline
    out/wave8_mixed.png     each mixed game's Opus index against its rival's
    out/wave1_arms.png      wave 1: every Haiku 4.5 arm, each game's index over rounds 51-100
    out/wave2_remedies.png  wave 2: best-response information and the 10% cut on Sonnet 5.5 and Opus 5.5
    out/wave4_paths.png     wave 4: Firm A's path after the forced cut against the base-scale null band
    out/wave10_continued.png  wave 10: the estimate and baseline games continued to round 200
    out/wave11_caps.png     wave 11: Sonnet 5.5 and Haiku 5.5 under the limit and the cap, by game and by round

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
        ("opus-haiku45-brinfo", "Opus and Haiku 4.5, best-response information", SERIES[2], "^"),
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


def dot_rows(ax, rows, xlim, mean_x, refs=(), clip=None):
    """One row per (label, values, colour, obedience-or-None); dots per game, a bar at the mean."""
    n = len(rows)
    for x, text in refs:
        ax.axvline(
            x, color=AXIS if x == 0 else GRID, lw=1, ls="-" if x == 0 else (0, (2, 2)), zorder=0
        )
        ax.text(x, n - 0.35, text, color=MUTED, fontsize=7.5, ha="center", va="bottom")
    rng = np.random.default_rng(2026)
    for i, (label, vals, color, obey) in enumerate(rows):
        y = n - 1 - i
        vals = np.asarray(vals, float)
        right = clip if clip is not None else xlim[1] - 0.06
        off = vals > right
        if off.any():
            ax.scatter(
                [right] * int(off.sum()),
                y + np.linspace(-0.12, 0.12, int(off.sum())),
                marker=">",
                s=28,
                color=color,
                edgecolors=SURFACE,
                linewidths=0.6,
                zorder=3,
            )
            lo_v, hi_v = vals[off].min(), vals[off].max()
            span = f"{lo_v:.1f}" if abs(hi_v - lo_v) < 0.05 else f"{lo_v:.1f}–{hi_v:.1f}"
            ax.text(
                right - 0.06,
                y + 0.3,
                f"{int(off.sum())} off the scale, at {span}",
                color=INK2,
                fontsize=7,
                ha="right",
                va="bottom",
            )
        ax.scatter(
            np.minimum(vals, right),
            y + rng.uniform(-0.18, 0.18, len(vals)),
            s=22,
            color=color,
            alpha=0.85,
            edgecolors=SURFACE,
            linewidths=0.8,
            zorder=3,
        )
        ax.plot([vals.mean()] * 2, [y - 0.32, y + 0.32], color=INK, lw=1.6, zorder=4)
        if obey is not None:
            ax.plot([obey] * 2, [y - 0.36, y + 0.36], color=INK2, lw=1, ls=(0, (2, 1.5)), zorder=2)
        ax.text(
            mean_x,
            y,
            f"{vals.mean():.2f}".replace("-0.00", "0.00").replace("-", "−"),
            color=INK,
            fontsize=8,
            va="center",
            ha="right",
        )
    ax.text(mean_x, n - 0.35, "mean", color=MUTED, fontsize=7.5, ha="right", va="bottom")
    ax.set_yticks(range(n), [r[0] for r in rows][::-1])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlim(*xlim)
    ax.set_ylim(-0.6, n + 0.1)
    ax.set_xlabel("Market index, rounds 51–100 (0 = Nash, 1 = monopoly)")


def models_baseline():
    w2, w3j = load("wave2.json"), load("wave3.json")
    bias = {(r["family"], r["arm"]): r["index_by_game"] for r in w2["bias"]}
    sonnet = next(r["index_by_game"] for r in w2["stage_b"]["sonnet55"] if r["arm"] == "baseline")
    opus = next(r["index_by_game"] for r in w3j["rows"] if r["arm"] == "baseline")
    rows = [
        ("Haiku 4.5  (20 games, the paper's)", bias[("haiku45", "baseline")], SERIES[0], None),
        ("Haiku 5.5  (10)", bias[("haiku55", "baseline")], SERIES[0], None),
        ("Sonnet 5.5  (10)", sonnet, SERIES[0], None),
        ("Opus 5.5  (15)", opus, SERIES[0], None),
    ]
    fig, ax = plt.subplots(figsize=(7.6, 2.6), layout="constrained")
    dot_rows(ax, rows, (-0.3, 3.15), 3.1, refs=((0, "Nash"), (0.3, "ends high"), (1, "monopoly")))
    fig.savefig(OUT / "models_baseline.png", dpi=200)
    plt.close(fig)


def haiku_number():
    w1, w2 = load("followup.json"), load("wave2.json")
    g1 = {a: [g["index_51_100"] for g in v] for a, v in w1["games"].items()}
    bias = {(r["family"], r["arm"]): r for r in w2["bias"]}
    up, down = w1["obedient_index_for_bias"], bias[("haiku45", "brinfo_biasdown")]["obedient_index"]
    rows = [
        ("Haiku 4.5: no number (baseline)", g1["baseline"], MUTED, None),
        ("Haiku 4.5: its best response", g1["brinfo"], SERIES[0], None),
        ("Haiku 4.5: best response with 10% noise", g1["brinfo_noise"], SERIES[0], None),
        ("Haiku 4.5: best response +10%", g1["brinfo_bias"], SERIES[0], up),
        (
            "Haiku 4.5: best response −10%",
            bias[("haiku45", "brinfo_biasdown")]["index_by_game"],
            SERIES[0],
            down,
        ),
        (
            "Haiku 4.5 told to enforce: no number",
            bias[("haiku45enf", "baseline")]["index_by_game"],
            MUTED,
            None,
        ),
        (
            "Haiku 4.5 told to enforce: +10%",
            bias[("haiku45enf", "brinfo_bias")]["index_by_game"],
            SERIES[0],
            up,
        ),
        ("Haiku 5.5: no number", bias[("haiku55", "baseline")]["index_by_game"], MUTED, None),
        (
            "Haiku 5.5: best response +10%",
            bias[("haiku55", "brinfo_bias")]["index_by_game"],
            SERIES[0],
            up,
        ),
    ]
    fig, ax = plt.subplots(figsize=(7.6, 4.1), layout="constrained")
    dot_rows(ax, rows, (-0.7, 3.55), 3.5, refs=((0, "Nash"), (1, "monopoly")), clip=3.05)
    ax.text(
        up + 0.03, -0.55, "dashed tick: where obeying the number leads", color=MUTED, fontsize=7.5
    )
    fig.savefig(OUT / "haiku45_number.png", dpi=200)
    plt.close(fig)


def opus_sawtooth():
    g = w3.opus_games()
    t = np.arange(1, 101)
    fig, ax = plt.subplots(figsize=(7.6, 3.4), layout="constrained")
    ax.axhline(0, color=AXIS, lw=1, zorder=0)
    ax.axhline(0.3, color=GRID, lw=1, ls=(0, (2, 2)), zorder=0)
    ax.text(7, 1.55, "every arm opens above the scale", color=MUTED, fontsize=7.5, va="top")
    ax.text(2, 0.315, "ends high", color=MUTED, fontsize=7.5, va="bottom")
    lines = [
        ("Baseline (15 games)", g["baseline"], MUTED),
        ("Forced Nash round every 10", g["forced10"], SERIES[0]),
        ("Forced Nash round every 5", g["forced5"], SERIES[1]),
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
    fig.savefig(OUT / "opus_sawtooth.png", dpi=200)
    plt.close(fig)


def diagnosis_summary():
    nb, w9 = load("null_band_scale.json"), load("wave9.json")
    rows = []
    for key, label in (
        ("haiku", "Haiku 5.5, forced cut (paper)"),
        ("fable", "Fable 5.1, forced cut (paper)"),
        ("haiku45", "Haiku 4.5, forced cut (paper)"),
        ("haiku45_enforcer2", "Haiku 4.5 told to enforce, forced cut (paper)"),
        ("sonnet55", "Sonnet 5.5, forced cut (wave 4)"),
        ("opus55", "Opus 5.5, forced cut (wave 4)"),
    ):
        b = nb[key]["base_scale"]
        lo = min(b["null_sbr"][0], b["null_br"][0])
        hi = max(b["null_sbr"][1], b["null_br"][1])
        verdict = b["verdict"] if key != "haiku45_enforcer2" else "can't be called: band too wide"
        rows.append((label, b["punishment"], lo, hi, verdict))
    for key, label in (
        ("haiku45", "Haiku 4.5, forced raise (wave 9)"),
        ("opus55", "Opus 5.5, forced raise (wave 9)"),
    ):
        v = w9[key]
        rows.append((label, v["response"], v["band_lower"], v["band_upper"], v["verdict"]))
    n = len(rows)
    fig, ax = plt.subplots(figsize=(7.6, 3.8), layout="constrained")
    ax.axvline(0, color=AXIS, lw=1, zorder=0)
    for i, (label, resp, lo, hi, verdict) in enumerate(rows):
        y = n - 1 - i
        ax.plot([lo, hi], [y, y], color=GRID, lw=7, solid_capstyle="round", zorder=1)
        ax.scatter(
            [resp],
            [y],
            s=46,
            color=SERIES[0] if "cut" in label else SERIES[1],
            edgecolors=SURFACE,
            linewidths=1,
            zorder=3,
        )
        ax.text(
            1.02,
            y,
            verdict,
            color=INK2,
            fontsize=7.5,
            va="center",
            ha="left",
            transform=ax.get_yaxis_transform(),
        )
    ax.axhline(1.5, color=GRID, lw=0.8, zorder=0)
    ax.set_yticks(range(n), [r[0] for r in rows][::-1])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlim(-1.0, 1.0)
    ax.set_xlabel(
        "Firm A's response over the five rounds after the forced move (bar: non-strategic null band)"
    )
    fig.savefig(OUT / "diagnosis_summary.png", dpi=200)
    plt.close(fig)


def wave1_arms():
    w1 = load("followup.json")
    g = {a: [x["index_51_100"] for x in v] for a, v in w1["games"].items()}
    up = w1["obedient_index_for_bias"]
    rows = [
        ("Baseline  (20 games)", g["baseline"], MUTED, None),
        ("Best response, exact  (paper)", g["brinfo"], SERIES[0], None),
        ("Forced Nash round every 10  (paper)", g["forced10"], SERIES[0], None),
        ("Best response, 10% noise", g["brinfo_noise"], SERIES[0], None),
        ("Best response, biased +10%", g["brinfo_bias"], SERIES[0], up),
        ("Forced 10% cut every 10", g["cut10"], SERIES[0], None),
    ]
    fig, ax = plt.subplots(figsize=(7.6, 3.0), layout="constrained")
    dot_rows(ax, rows, (-0.4, 3.2), 3.15, refs=((0, "Nash"), (0.3, "ends high"), (1, "monopoly")))
    ax.text(
        up + 0.04, -0.55, "dashed tick: where obeying the number leads", color=MUTED, fontsize=7.5
    )
    fig.savefig(OUT / "wave1_arms.png", dpi=200)
    plt.close(fig)


def wave2_remedies():
    sb = load("wave2.json")["stage_b"]
    rows = []
    for fam, name in (("sonnet55", "Sonnet 5.5"), ("opus55", "Opus 5.5")):
        base, exact, cut = sb[fam]
        rows += [
            (f"{name}: baseline", base["index_by_game"], MUTED, None),
            (f"{name}: best response, exact", exact["index_by_game"], SERIES[0], None),
            (f"{name}: 10% cut every 10", cut["index_by_game"], SERIES[0], None),
        ]
    fig, ax = plt.subplots(figsize=(7.6, 3.0), layout="constrained")
    dot_rows(ax, rows, (-0.15, 1.25), 1.22, refs=((0, "Nash"), (0.3, "ends high"), (1, "monopoly")))
    ax.axhline(2.5, color=GRID, lw=0.8, zorder=0)
    fig.savefig(OUT / "wave2_remedies.png", dpi=200)
    plt.close(fig)


def wave4_paths():
    """Firm A's path after the forced cut, deviate minus control, against the base-scale null band."""
    import frontier_results as fres
    import null_band_scale as nbs
    import polars as pl
    from bandit import fit, load as load_games, markets

    nb = load("null_band_scale.json")
    duo = load_games().filter(pl.col("num_agents") == 2)
    m = fit(markets(duo.filter(pl.col("prompt") == "P1")))
    fres.RUNS, fres.read = nbs.RUNS["opus55"], nbs.base_scale_read
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 2.8), sharey=True, layout="constrained")
    for ax, (key, name) in zip(axes, (("opus55", "Opus 5.5"), ("sonnet55", "Sonnet 5.5"))):
        fres.MODELS = {key: key}
        r = fres.analyse(key, m, np.random.default_rng(11))
        b = nb[key]["base_scale"]
        assert (
            abs(r["punishment"] - b["punishment"]) < 1e-12
            and abs(r["null_lo"] - b["null_lo"]) < 1e-12
        )
        k = np.arange(1, fres.H + 1)
        ctl, dev = np.array(r["paths"]["control"]), np.array(r["paths"]["deviate"])
        lo = np.minimum(r["path_band"]["sbr"][0], r["path_band"]["br"][0])
        hi = np.maximum(r["path_band"]["sbr"][1], r["path_band"]["br"][1])
        ax.axvspan(1.5, 6.5, color=GRID, alpha=0.35, lw=0, zorder=0)
        ax.fill_between(k, lo, hi, color=GRID, alpha=0.9, lw=0, zorder=1, label="Null band (95%)")
        ax.axhline(0, color=AXIS, lw=1, zorder=2)
        firm_b = dev[:, 1] - ctl[:, 1]
        ax.plot(
            k,
            firm_b,
            color=MUTED,
            lw=1.4,
            ls=(0, (3, 2)),
            zorder=3,
            label="Firm B, forced to Nash at round 1",
        )
        ax.plot(
            k, dev[:, 0] - ctl[:, 0], color=SERIES[0], lw=2, zorder=4, label="Firm A, the responder"
        )
        ax.scatter(
            k, dev[:, 0] - ctl[:, 0], s=14, color=SERIES[0], edgecolors=SURFACE, lw=0.6, zorder=5
        )
        ax.set_title(f"{name}: {b['verdict']}", fontsize=9, color=INK, loc="left")
        ax.set_xlabel("Rounds after the branch")
        ax.set_xlim(0.6, 12.4)
        ax.text(4, 0.62, "scored rounds", color=MUTED, fontsize=7.5, ha="center")
    axes[0].set_ylabel("Index, deviate minus control")
    axes[1].legend(loc="lower right", frameon=False, fontsize=7.5, labelcolor=INK2)
    axes[0].set_ylim(-0.85, 0.7)
    fig.savefig(OUT / "wave4_paths.png", dpi=200)
    plt.close(fig)


def forced_cut_schematic():
    """An illustration, not data: the two arms of the forced-cut test and where it scores."""
    t = np.arange(0, 13)
    ctl_b = np.full(13, 0.7)
    dev_b = ctl_b.copy()
    dev_b[1] = 0.0
    dev_b[2:] = 0.55 + 0.1 * (1 - np.exp(-(t[2:] - 2) / 3))
    ctl_a = np.full(13, 0.72)
    follow_a = ctl_a.copy()
    follow_a[2:] = 0.72 - 0.35 * np.exp(-(t[2:] - 2) / 6)
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 2.6), layout="constrained", sharey=True)
    for ax, title in zip(axes, ("Firm B (the one forced)", "Firm A (the one watched)")):
        ax.axvspan(1.5, 6.5, color=GRID, alpha=0.6, lw=0, zorder=0)
        ax.set_title(title, fontsize=8.5, color=INK2, loc="left")
        ax.set_xticks([0, 1, 2, 6, 12], ["B", "B+1", "B+2", "B+6", "B+12"])
        ax.set_ylim(-0.08, 0.95)
        ax.axhline(0, color=AXIS, lw=1, zorder=0)
    axes[0].plot(t, ctl_b, color=MUTED, lw=1.6)
    axes[0].plot(t, dev_b, color=SERIES[0], lw=1.6)
    axes[0].annotate(
        "forced to Nash for one round",
        (1, 0.0),
        (2.4, 0.16),
        color=INK2,
        fontsize=7.5,
        arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 0.8},
    )
    axes[1].plot(t, ctl_a, color=MUTED, lw=1.6)
    axes[1].plot(t, follow_a, color=SERIES[0], lw=1.6)
    axes[1].text(12, 0.76, "control arm", color=MUTED, fontsize=7.5, ha="right")
    axes[1].text(12, 0.47, "deviate arm", color=SERIES[0], fontsize=7.5, ha="right")
    axes[1].text(4, 0.9, "scored: B+2 to B+6", color=INK2, fontsize=7.5, ha="center")
    axes[0].set_ylabel("Market index")
    fig.savefig(OUT / "forced_cut_schematic.png", dpi=200)
    plt.close(fig)


def wave10_continued():
    folder = HERE / "runs/wave10/games/2_agents"
    arms = {
        arm: [w5.load(f) for f in sorted(folder.glob(pattern))]
        for arm, pattern in (
            ("estimate", "*_rule-w7-estimate-no-threat_*"),
            ("baseline", "*_baseline_*"),
        )
    }
    idx = {arm: [p.index(x) for x in xs] for arm, xs in arms.items()}
    res = load("wave10.json")["primary"]
    assert (
        abs(np.mean([i[150:200].mean() for i in idx["estimate"]]) - res["estimate_index_151_200"])
        < 1e-9
    )
    fig, (ax, bx) = plt.subplots(
        1, 2, figsize=(8.4, 3.6), layout="constrained", gridspec_kw={"width_ratios": [2.6, 1]}
    )
    t = np.arange(1, 201)
    ax.axhline(0, color=AXIS, lw=1, zorder=0)
    ax.axvline(100.5, color=GRID, lw=1, zorder=0)
    ax.text(102, 1.25, "continued from here\n(wave 10)", color=MUTED, fontsize=7.5, va="top")
    ax.text(24, 1.25, "both arms open above the scale", color=MUTED, fontsize=7.5, va="top")
    for label, arm, color in (
        ("Baseline (5 games)", "baseline", MUTED),
        ("Estimate, no threat (10 games)", "estimate", SERIES[2]),
    ):
        y = np.mean(idx[arm], axis=0)
        ax.plot(t, y, color=color, lw=1.6, solid_capstyle="round")
        ax.text(150, float(y[140:160].mean()) + 0.07, label, color=INK2, fontsize=7.5, ha="center")
    ax.set_xlim(1, 200)
    ax.set_ylim(-0.1, 1.3)
    ax.set_xlabel("Round")
    ax.set_ylabel("Mean market index")
    ax.yaxis.grid(True, color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for arm, color, z in (("baseline", MUTED, 1), ("estimate", SERIES[2], 2)):
        for i in idx[arm]:
            a, b = i[50:100].mean(), i[150:200].mean()
            bx.plot([0, 1], [a, b], color=color, lw=1.2, alpha=0.9, zorder=z)
            bx.scatter([0, 1], [a, b], s=14, color=color, edgecolor=SURFACE, lw=1, zorder=z + 1)
    bx.axhline(0.1, color=GRID, lw=1, ls=(0, (3, 3)), zorder=0)
    bx.text(0.5, 0.06, "competitive (0.1)", color=MUTED, fontsize=7, ha="center", va="top")
    bx.set_xticks([0, 1], ["Rounds\n51–100", "Rounds\n151–200"])
    bx.set_xlim(-0.25, 1.25)
    bx.set_ylim(-0.1, 1.3)
    bx.set_ylabel("Each game's index")
    handles = [
        plt.Line2D([], [], color=SERIES[2], lw=1.2, marker="o", ms=3.5, label="Estimate"),
        plt.Line2D([], [], color=MUTED, lw=1.2, marker="o", ms=3.5, label="Baseline"),
    ]
    bx.legend(
        handles=handles, loc="upper center", ncol=2, frameon=False, fontsize=7.5, handlelength=1.6
    )
    bx.yaxis.grid(True, color=GRID, lw=0.6)
    bx.set_axisbelow(True)
    fig.savefig(OUT / "wave10_continued.png", dpi=200)
    plt.close(fig)


def wave11_caps():
    import wave2_results as w2r
    import wave11_results as w11

    res = load("wave11.json")
    base = {
        f: w2r.family_games(f, ("baseline",))["baseline"] + w11.games(f, "none")
        for f in ("sonnet55", "haiku55")
    }
    arms = {a: w11.games(fam, rule) for a, (fam, rule, _) in w11.ARMS.items()}
    for a, xs in arms.items():
        assert abs(np.mean([w11.late(x) for x in xs]) - res["arms"][a]["index_51_100"]) < 1e-9

    def late(xs):
        return [w11.late(x) for x in xs]

    rows = [
        ("Sonnet 5.5, baseline  (15)", late(base["sonnet55"]), MUTED, None),
        ("Sonnet 5.5, limit  (10)", late(arms["A"]), SERIES[0], None),
        ("Sonnet 5.5, cap  (20)", late(arms["C"]), SERIES[1], None),
        ("Haiku 5.5, baseline  (15)", late(base["haiku55"]), MUTED, None),
        ("Haiku 5.5, cap  (10)", late(arms["B"]), SERIES[1], None),
    ]
    cap = (1.74 - 1.4729) / (1.925 - 1.4729)
    fig, (ax, bx) = plt.subplots(
        1, 2, figsize=(8.6, 3.5), layout="constrained", gridspec_kw={"width_ratios": [1.3, 1]}
    )
    dot_rows(ax, rows, (-0.12, 0.95), 0.93, refs=((0, "Nash"), (cap, "cap")))
    n_at = sum(abs(v - cap) < 1e-3 for v in rows[2][1])
    ax.text(cap + 0.03, 2.28, f"{n_at} games\nat the cap", color=INK2, fontsize=7, va="center")
    t = np.arange(1, 101)
    bx.axhline(0, color=AXIS, lw=1, zorder=0)
    bx.axhline(cap, color=GRID, lw=1, ls=(0, (3, 3)), zorder=0)
    for x in arms["C"]:
        bx.plot(t, p.index(x)[:100], color=SERIES[1], lw=0.9, alpha=0.55, zorder=2)
    y = np.mean([p.index(x)[:100] for x in base["sonnet55"]], axis=0)
    bx.plot(t, y, color=MUTED, lw=1.8, zorder=3)
    bx.text(45, float(y[44]) + 0.05, "baseline mean (15 games)", color=INK2, fontsize=7.5)
    bx.text(35, 0.98, "baseline opens above the scale", color=MUTED, fontsize=7.5, va="top")
    bx.text(35, 0.73, f"each cap game (20); {n_at} held the cap, 1.74", color=INK2, fontsize=7.5)
    bx.set_xlim(1, 100)
    bx.set_ylim(-0.1, 1.0)
    bx.set_xlabel("Round")
    bx.set_ylabel("Market index, Sonnet 5.5")
    bx.yaxis.grid(True, color=GRID, lw=0.6)
    bx.set_axisbelow(True)
    fig.savefig(OUT / "wave11_caps.png", dpi=200)
    plt.close(fig)


def wave12_limit_cap():
    import wave12_exploratory as w12x
    import wave12_results as w12

    res = load("wave12.json")
    mx, a2 = w12.mixed("none"), w12.mixed("w6-limit-no-threat")
    c2 = w12.single("sonnet55", "w11-cap174")
    d = w12.single("sonnet55", "w12-cap174-from31")
    base = w12x.sonnet_baseline()
    for xs, want in ((a2, res["part1"]["A2_index"]), (d, res["part2"]["D"]["index"])):
        assert abs(np.mean([w12.late(x) for x in xs]) - want) < 1e-9

    def late(xs):
        return [w12.late(x) for x in xs]

    rows = [
        ("Opus and Sonnet, no rule  (10)", late(mx), MUTED, None),
        ("Opus and Sonnet, limit  (10)", late(a2), SERIES[0], None),
        ("Sonnet, baseline  (20)", late(base), MUTED, None),
        ("Sonnet, cap from round 1  (20)", late(c2), SERIES[1], None),
        ("Sonnet, cap from round 31  (20)", late(d), SERIES[2], None),
    ]
    cap = (1.74 - 1.4729) / (1.925 - 1.4729)
    fig, (ax, bx) = plt.subplots(
        1, 2, figsize=(8.6, 3.5), layout="constrained", gridspec_kw={"width_ratios": [1.3, 1]}
    )
    dot_rows(ax, rows, (-0.12, 1.07), 1.05, refs=((0, "Nash"), (cap, "cap")))
    n_at = sum(abs(v - cap) < 1e-3 for v in rows[3][1])
    ax.text(cap + 0.03, 1.28, f"{n_at} games\nat the cap", color=INK2, fontsize=7, va="center")
    t = np.arange(1, 101)
    bx.axhline(0, color=AXIS, lw=1, zorder=0)
    bx.axhline(cap, color=GRID, lw=1, ls=(0, (3, 3)), zorder=0)
    bx.axvline(31, color=AXIS, lw=1, ls=(0, (2, 2)), zorder=0)
    for x in d:
        bx.plot(t, p.index(x)[:100], color=SERIES[2], lw=0.9, alpha=0.5, zorder=2)
    y = np.mean([p.index(x)[:100] for x in base], axis=0)
    bx.plot(t, y, color=MUTED, lw=1.8, zorder=3)
    bx.text(33, -0.08, "cap from round 31", color=INK2, fontsize=7.5, va="bottom")
    bx.legend(
        handles=[
            plt.Line2D([], [], color=SERIES[2], lw=1.2),
            plt.Line2D([], [], color=MUTED, lw=1.8),
        ],
        labels=["each late-cap game (20);\nnone held the cap", "baseline mean (20 games)"],
        loc="upper right",
        frameon=False,
        fontsize=7.5,
        labelcolor=INK2,
    )
    bx.set_xlim(1, 100)
    bx.set_ylim(-0.1, 1.0)
    bx.set_xlabel("Round")
    bx.set_ylabel("Market index, Sonnet 5.5")
    bx.yaxis.grid(True, color=GRID, lw=0.6)
    bx.set_axisbelow(True)
    fig.savefig(OUT / "wave12_limit_cap.png", dpi=200)
    plt.close(fig)


def paper_remedies():
    """The short paper's Figure 1: the same remedies on each model, and how often each model set the number."""
    import wave12_exploratory as w12x

    w1, w2, w3j = load("followup.json"), load("wave2.json"), load("wave3.json")
    w6j, w7j, w11j, w12j = (
        load("wave6.json"),
        load("wave7.json"),
        load("wave11.json"),
        load("wave12.json"),
    )
    x11, x12 = load("wave11_exploratory.json"), load("wave12_exploratory.json")
    bias = {(r["family"], r["arm"]): r for r in w2["bias"]}
    sb = {fam: {r["arm"]: r for r in rows} for fam, rows in w2["stage_b"].items()}
    w12 = __import__("wave12_results")
    son_base = [w12.late(x) for x in w12x.sonnet_baseline()]
    assert abs(np.mean(son_base) - w12j["part2"]["baseline_index"]) < 1e-9
    opus_base = next(r["index_by_game"] for r in w3j["rows"] if r["arm"] == "baseline")
    g1 = {a: [g["index_51_100"] for g in v] for a, v in w1["games"].items()}
    sets = {
        "h_info": pct_txt(w1["deference"]["brinfo"]["within_1pct_of_shown"]),
        "s_info": pct_txt(sb["sonnet55"]["brinfo"]["deference"]["within_1pct_of_shown"]),
        "s_lim": pct_txt(w11j["secondary"]["A_follow_11_99"]),
        "o_info": pct_txt(sb["opus55"]["brinfo"]["deference"]["within_1pct_of_shown"]),
        "o_est": pct_txt(w7j["exploratory"]["follow_11_99"]["within_1pct"]),
        "o_lim": pct_txt(w6j["exploratory"]["follow_no_threat_11_99"]["within_1pct"]),
        "m_lim": "Opus {}\nSonnet {}".format(
            *(pct_txt(w12j["secondary"]["follow_A2_11_99"][m]) for m in ("opus55", "sonnet55"))
        ),
    }
    rows = [
        ("Haiku 4.5: no remedy  (20)", bias[("haiku45", "baseline")]["index_by_game"], MUTED, ""),
        ("best-response information  (10)", g1["brinfo"], SERIES[0], sets["h_info"]),
        ("Sonnet 5.5: no remedy  (20)", son_base, MUTED, ""),
        (
            "best-response information  (10)",
            sb["sonnet55"]["brinfo"]["index_by_game"],
            SERIES[0],
            sets["s_info"],
        ),
        (
            "posted limit  (10)",
            list(x11["limit"]["index_by_game"].values()),
            SERIES[1],
            sets["s_lim"],
        ),
        ("Opus 5.5: no remedy  (15)", opus_base, MUTED, ""),
        (
            "best-response information  (10)",
            sb["opus55"]["brinfo"]["index_by_game"],
            SERIES[0],
            sets["o_info"],
        ),
        (
            "the limit's number, as an estimate  (10)",
            w7j["w7-estimate-no-threat"]["primary_by_game"],
            SERIES[0],
            sets["o_est"],
        ),
        (
            "posted limit  (10)",
            w6j["rules"]["w6-limit-no-threat"]["primary_by_game"],
            SERIES[1],
            sets["o_lim"],
        ),
        (
            "Opus and Sonnet: no remedy  (10)",
            list(x12["mixed"]["mixed"]["index_by_game"].values()),
            MUTED,
            "",
        ),
        (
            "posted limit  (10)",
            list(x12["mixed"]["A2"]["index_by_game"].values()),
            SERIES[1],
            sets["m_lim"],
        ),
    ]
    fig, ax = plt.subplots(figsize=(8.2, 4.9), layout="constrained")
    dot_rows(
        ax,
        [(a, v, c, None) for a, v, c, _ in rows],
        (-0.15, 1.75),
        1.38,
        refs=((0, "Nash"), (1, "monopoly")),
        clip=1.2,
    )
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    n = len(rows)
    for i, (_, _, _, txt) in enumerate(rows):
        ax.text(1.74, n - 1 - i, txt, color=INK2, fontsize=7.5, va="center", ha="right")
    ax.text(1.74, n - 0.35, "sets the number", color=MUTED, fontsize=7.5, ha="right", va="bottom")
    for y in (n - 2.5, n - 5.5, n - 9.5):
        ax.axhline(y, color=GRID, lw=0.6, zorder=0)
    fig.savefig(OUT / "paper_remedies.png", dpi=200)
    plt.close(fig)


def pct_txt(v: float) -> str:
    return f"{100 * v:.0f}%"


def paper_caps():
    """The short paper's Figure 2: the cap from round 1 (waves 11 and 12) against the cap from round 31."""
    import wave12_exploratory as w12x
    import wave12_results as w12

    c = w12.single("sonnet55", "w11-cap174", w12.W11) + w12.single("sonnet55", "w11-cap174")
    d = w12.single("sonnet55", "w12-cap174-from31")
    y = np.mean([p.index(x)[:100] for x in w12x.sonnet_baseline()], axis=0)
    cap = (1.74 - 1.4729) / (1.925 - 1.4729)
    n_held = sum(w12.held(x) for x in c)
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.2), layout="constrained", sharey=True)
    t = np.arange(1, 101)
    for ax, xs, color, title in (
        (axes[0], c, SERIES[1], f"Cap from round 1: {len(c)} games, {n_held} held the cap"),
        (axes[1], d, SERIES[2], f"Cap from round 31: {len(d)} games, none held the cap"),
    ):
        ax.axhline(0, color=AXIS, lw=1, zorder=0)
        ax.axhline(cap, color=GRID, lw=1, ls=(0, (3, 3)), zorder=0)
        for x in xs:
            ax.plot(t, p.index(x)[:100], color=color, lw=0.8, alpha=0.45, zorder=2)
        ax.plot(t, y, color=MUTED, lw=1.8, zorder=3)
        ax.set_title(title, fontsize=8.5, color=INK, loc="left")
        ax.set_xlim(1, 100)
        ax.set_ylim(-0.1, 1.0)
        ax.set_xlabel("Round")
        ax.yaxis.grid(True, color=GRID, lw=0.6)
        ax.set_axisbelow(True)
    axes[1].axvline(31, color=AXIS, lw=1, ls=(0, (2, 2)), zorder=0)
    axes[0].text(60, cap + 0.03, "the cap, 1.74", color=INK2, fontsize=7.5)
    axes[0].text(16, 0.86, "baseline mean (20 games)", color=INK2, fontsize=7.5)
    axes[0].set_ylabel("Market index, Sonnet 5.5")
    fig.savefig(OUT / "paper_caps.png", dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    forced_cut_schematic()
    models_baseline()
    haiku_number()
    opus_sawtooth()
    diagnosis_summary()
    opus_remedies()
    wave6_lifted()
    wave8_mixed()
    wave1_arms()
    wave2_remedies()
    wave4_paths()
    wave10_continued()
    wave11_caps()
    wave12_limit_cap()
    paper_remedies()
    paper_caps()
    print("wrote the sixteen figures in out/")
