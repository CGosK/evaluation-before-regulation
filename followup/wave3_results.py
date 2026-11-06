"""
Wave-3 follow-up results (November 2026, after the sprint review; not part of the submission), as fixed in
followup/WAVE3_PLAN.md: forced Nash rounds on Claude Opus 5.5 against its 15 baseline games (wave 2's 10 and
wave 3's 5), with Holm's correction over the remedies run; the plan's descriptive measures; the stage-B rule;
and the notes analysis of the exact best-response games. Statistics are Table 4's, from
theory/prevention45_results.py.

Usage:  uv run --extra analysis python followup/wave3_results.py
Writes: followup/out/wave3.json, followup/out/wave3.png, followup/out/wave3_notes.md
"""

import json
import re
import statistics
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "theory")]
import prevention45_results as p  # noqa: E402
import wave2_results as w2  # noqa: E402

OUT = HERE / "out"
WAVE2 = HERE / "runs/wave2/games/2_agents"
WAVE3 = HERE / "runs/wave3/games/2_agents"
TESTED = ("baseline", "forced10", "forced5")
SHOWN = TESTED + ("cut10",)  # wave 2's cut is drawn for reference, not tested again
LABELS = {
    "baseline": "baseline",
    "forced10": "forced Nash round every 10",
    "forced5": "forced Nash round every 5",
    "cut10": "forced 10% cut every 10 (wave 2)",
}
COLORS = {"baseline": "#555555", "forced10": "#c0392b", "forced5": "#8e44ad", "cut10": "#e67e22"}
NOTES = re.compile(r"platform|estimate", re.I)
SNAPSHOT_ROUND = "30"


def arm_of(name: str) -> str:
    fam, _, rest = name.split("_mem100_", 1)[-1].partition("_")
    if fam != "opus55":
        return ""
    return next((a for a in SHOWN if rest.startswith(f"{a}_")), "")


def opus_games() -> dict:
    p.MODEL, p.RUNS, p.arm_of, p.ARMS = "claude-opus-5-5", [WAVE2, WAVE3], arm_of, SHOWN
    p.LABELS.update(LABELS)
    p.COLORS.update(COLORS)
    return p.games()


def first_block_below(games: list, level: float = 0.1) -> str | None:
    path = np.mean([p.index(x) for x in games], axis=0)
    for k in range(0, p.ROUNDS, 10):
        if path[k : k + 10].mean() < level:
            return f"{k + 1}-{k + 10}"
    return None


def rival_response(games: list) -> dict:
    """After each forced round with a following round: the rival's next price change."""
    change = []
    for x in games:
        P, F = x["P"], x["forced"]
        for t in range(1, p.ROUNDS - 1):
            if F[t].any():
                j = 1 - int(np.argmax(F[t]))
                change.append(P[t + 1, j] / P[t, j] - 1)
    c = np.array(change)
    if not len(c):
        return {"forced_rounds": 0}
    return {
        "forced_rounds": len(c),
        "rival_median_change_pct": float(np.median(c) * 100),
        "rival_share_cutting_5pct": float((c <= -0.05).mean()),
    }


def thinking(usage: Path) -> dict:
    tokens = [
        json.loads(line).get("thinking_tokens") or 0
        for line in usage.open()
        if json.loads(line).get("model") == "claude-opus-5-5"
    ]
    used = [t for t in tokens if t > 0]
    return {
        "calls": len(tokens),
        "share_with_thinking": len(used) / len(tokens) if tokens else None,
        "median_thinking_tokens": statistics.median(used) if used else 0,
    }


def note_text(o: dict) -> str:
    return "\n".join(str(o.get(k, "")) for k in ("observations", "plans", "insights"))


def notes_share(folders: list) -> dict:
    hits = []
    for folder in folders:
        res = json.loads((folder / "results.json").read_text())
        for firm in res.values():
            hits += [bool(NOTES.search(note_text(firm[str(t)]))) for t in range(11, 100)]
    return {
        "games": len(folders),
        "firm_rounds": len(hits),
        "share_mentioning": float(np.mean(hits)),
    }


def folder(name: str, runs: list) -> Path:
    return next(d / name for d in runs if (d / name).exists())


def notes_analysis() -> dict:
    out, snapshot = {}, ["# Wave 3 notes snapshot", ""]
    snapshot.append(
        f"Firm A's notes at round {SNAPSHOT_ROUND} of each exact best-response game in wave 2, verbatim. "
        "Exploratory; WAVE3_PLAN.md fixed the round after one game (Opus 5.5, seed 9) had been read."
    )
    saved = (p.MODEL, list(p.RUNS), p.arm_of, p.ARMS)
    p.MODEL, p.RUNS, p.arm_of, p.ARMS = (
        "claude-haiku-4-5",
        w2.SUBMITTED,
        w2.SUBMITTED_ARM_OF,
        p.ARMS,
    )
    haiku = p.games().get("brinfo", [])
    out["haiku45"] = notes_share([folder(x["name"], w2.SUBMITTED) for x in haiku])
    p.MODEL, p.RUNS, p.arm_of, p.ARMS = saved
    for fam in ("sonnet55", "opus55"):
        g = w2.family_games(fam, ("baseline", "brinfo"))["brinfo"]
        folders = [folder(x["name"], [WAVE2]) for x in g]
        out[fam] = notes_share(folders)
        for x, f in sorted(zip(g, folders), key=lambda z: int(z[0]["seed"])):
            o = json.loads((f / "results.json").read_text())["Firm A"][SNAPSHOT_ROUND]
            snapshot += [
                "",
                f"## {w2.NAMES[fam]}, seed {x['seed']} (index {p.index(x)[p.LATE].mean():.2f})",
                "",
            ]
            for k in ("observations", "plans", "insights"):
                snapshot += [f"**{k.capitalize()}**", "", str(o.get(k, "")).strip(), ""]
    (OUT / "wave3_notes.md").write_text("\n".join(snapshot))
    return out


def plot(g: dict, rng):
    arms = [a for a in SHOWN if g.get(a)]
    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(12.5, 4.2), gridspec_kw={"width_ratios": [1, 1.15]}, layout="constrained"
    )
    for i, arm in enumerate(arms):
        y = len(arms) - 1 - i
        v = np.array([p.index(x)[p.LATE].mean() for x in g[arm]])
        ax1.scatter(v, y + rng.uniform(-0.15, 0.15, len(v)), s=14, color=COLORS[arm], lw=0)
        ax1.plot([v.mean()] * 2, [y - 0.32, y + 0.32], color="k", lw=1.6)
    ax1.set_yticks(range(len(arms)), [f"{LABELS[a]} ({len(g[a])})" for a in arms][::-1], fontsize=8)
    for xv, ls in ((0, "-"), (0.3, (0, (1, 3))), (1, ":")):
        ax1.axvline(xv, color="k", lw=0.5, ls=ls)
    ax1.set_xlabel("market index, rounds 51-100\ndot = game, bar = mean")
    k = np.arange(1, p.ROUNDS + 1)
    for arm in arms:
        P = np.array([p.index(x) for x in g[arm]])
        ax2.plot(k, P.mean(0), color=COLORS[arm], lw=1.4, label=LABELS[arm])
    ax2.axhline(0, color="k", lw=0.5)
    ax2.set_xlabel("round")
    ax2.set_ylabel("market index (mean)")
    ax2.legend(frameon=False, fontsize=7)
    fig.suptitle("Follow-up wave 3 (Nov 2026): forced Nash rounds on Claude Opus 5.5", fontsize=10)
    fig.savefig(OUT / "wave3.png", dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    rng = np.random.default_rng(2026)
    res = {"plan": "followup/WAVE3_PLAN.md", "notes": notes_analysis()}
    g = opus_games()
    n10 = len(g["forced10"])
    mean10 = float(np.mean([p.index(x)[p.LATE].mean() for x in g["forced10"]])) if n10 else None
    res["stage_b_rule"] = {
        "forced10_games": n10,
        "forced10_mean_index": mean10,
        "run": n10 == 10 and mean10 > 0.3,
        "rule": "stage B runs if forced10's mean index over rounds 51-100 is above 0.3",
    }
    tested = {a: g[a] for a in TESTED if g.get(a)}
    if len(tested) > 1:
        p.ARMS = tuple(tested)
        rows, _ = p.summarise(tested, rng)
        remedies = [r for r in rows if r["arm"] != "baseline"]
        holm = p.holm({r["arm"]: r["p_permutation"] for r in remedies})
        for r in rows:
            r.pop("p_holm", None)
            r["index_by_game"] = sorted(
                round(float(p.index(x)[p.LATE].mean()), 3) for x in g[r["arm"]]
            )
            r["first_block_below_0.1"] = first_block_below(g[r["arm"]])
            if r["arm"] in holm:
                r["p_holm"] = holm[r["arm"]]
                r["rival_response"] = rival_response(g[r["arm"]])
        res["rows"] = rows
    base = g["baseline"]
    new = [x for x in base if (WAVE3 / x["name"]).exists()]
    old = [x for x in base if not (WAVE3 / x["name"]).exists()]
    res["drift_check"] = {
        name: {
            "games": len(xs),
            "index_by_game": sorted(round(float(p.index(x)[p.LATE].mean()), 3) for x in xs),
        }
        for name, xs in (("wave2_baseline", old), ("wave3_baseline", new))
    }
    usage = HERE / "runs/wave3/usage.jsonl"
    res["thinking"] = thinking(usage) if usage.exists() else None
    (OUT / "wave3.json").write_text(json.dumps(res, indent=1, default=float))
    if any(g.get(a) for a in ("forced10", "forced5")):
        plot(g, rng)
    print(json.dumps({k: res[k] for k in ("notes", "stage_b_rule", "drift_check")}, indent=1))
    for r in res.get("rows", []):
        print(
            f"{LABELS[r['arm']]:28s} n={r['games']:2d} index={r['index_51_100']:+.2f} "
            f"high={r['share_above_0.3']:.0%} effect={r.get('effect', 0):+.2f} {r.get('effect_ci', '')} "
            f"p={r.get('p_permutation', float('nan')):.3f} holm={r.get('p_holm', float('nan')):.3f} "
            f"first<0.1={r['first_block_below_0.1']} rival={r.get('rival_response')}"
        )
