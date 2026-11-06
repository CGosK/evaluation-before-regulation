"""
Wave-4 follow-up results (November 2026, after the sprint review; not part of the submission), as fixed in
followup/WAVE4_PLAN.md:

    part 1  the paper's forced-deviation test on Opus 5.5 and Sonnet 5.5, through theory/frontier_results.py's
            own analyse(), pointed at runs/wave4/frontier/; a band lower bound below -0.74 (the paper's positive
            control) is reported as inconclusive
    part 2  hidden rival prices on Opus 5.5: the removal arm (hidden minus control over B+1..B+12, the paper's
            exact sign-flip test) and 10 prevention games against Opus 5.5's 15 baseline games (permutation
            test), with Holm's correction over the two; Sonnet 5.5's removal arm on its own
    exploratory  the deference placebo check, Opus's Firm A notes at B+2 in each deviate arm, move rates

Usage:  uv run --extra analysis python followup/wave4_results.py
Writes: followup/out/wave4.json, followup/out/wave4_forced_cut.png, followup/out/wave4_notes.md
"""

import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "theory")]
import frontier_results as fres  # noqa: E402
import mechanism_results as mres  # noqa: E402
import prevention45_results as p  # noqa: E402
import wave2_results as w2  # noqa: E402
import wave3_results as w3  # noqa: E402
from bandit import best_response, fit, load, markets  # noqa: E402

OUT = HERE / "out"
FRONTIER = HERE / "runs/wave4/frontier"
WAVE4 = HERE / "runs/wave4/games/2_agents"
NAMES = {"opus55": "Claude Opus 5.5", "sonnet55": "Claude Sonnet 5.5"}
WIDE = -0.74  # the paper's positive control punished by -0.74 yet could not be called
BINS = (("below 0.1", -np.inf, 0.1), ("0.1-0.3", 0.1, 0.3), ("0.3 or above", 0.3, np.inf))
SUBMITTED_ARMS = p.ARMS


def diagnosis(rng) -> dict:
    fres.RUNS, fres.MODELS, fres.OUT = FRONTIER, NAMES, OUT
    duo = load().filter(pl.col("num_agents") == 2)
    m_thesis = fit(markets(duo.filter(pl.col("prompt") == "P1")))
    out = {}
    for fam in NAMES:
        if not (FRONTIER / fam).exists():
            continue
        r = fres.analyse(fam, m_thesis, rng)
        r["verdict_plan"] = "inconclusive (band too wide)" if r["null_lo"] < WIDE else r["verdict"]
        diffs = [row["hidden"] for row in r["per_source"] if np.isfinite(row["hidden"])]
        r["hidden_sign_flip_p"] = mres.sign_flip_p(diffs) if diffs else None
        out[fam] = r
    if out:
        fres.plot(out)
        (OUT / "frontier_forced_cut.png").rename(OUT / "wave4_forced_cut.png")
    return out


def opus_arm_of(name: str) -> str:
    fam, _, rest = name.split("_mem100_", 1)[-1].partition("_")
    if fam != "opus55":
        return ""
    return next((a for a in ("baseline", "hidden") if rest.startswith(f"{a}_")), "")


def opus_games() -> dict:
    p.MODEL, p.RUNS, p.arm_of = "claude-opus-5-5", [w3.WAVE2, w3.WAVE3, WAVE4], opus_arm_of
    p.ARMS = ("baseline", "hidden")
    return p.games()


def prevention(g: dict, rng) -> list:
    if not g["hidden"]:
        return []
    rows, _ = p.summarise(g, rng)
    for r in rows:
        r.pop("p_holm", None)
        r["index_by_game"] = sorted(round(float(p.index(x)[p.LATE].mean()), 3) for x in g[r["arm"]])
    return rows


def placebo(games: list) -> dict:
    """Share of next prices within 1% of the true best response, by the current round's market index."""
    hits = {name: [] for name, _, _ in BINS}
    for x in games:
        P, idx = x["P"], p.index(x)
        for t in range(10, 99):  # rounds 11-99, as fr.deference
            name = next(n for n, lo, hi in BINS if lo <= idx[t] < hi)
            row = P[t : t + 1]
            for i in range(2):
                br = best_response(row if i == 0 else row[:, ::-1])[0, 0]
                hits[name].append(abs(np.log(P[t + 1, i] / br)) < 0.01)
    return {
        n: {"firm_rounds": len(v), "share_within_1pct": float(np.mean(v)) if v else None}
        for n, v in hits.items()
    }


def deference_placebo(opus: dict) -> dict:
    out = {}
    p.MODEL, p.RUNS, p.arm_of, p.ARMS = (
        "claude-haiku-4-5",
        w2.SUBMITTED,
        w2.SUBMITTED_ARM_OF,
        SUBMITTED_ARMS,
    )
    h = p.games()
    out["haiku45"] = {
        "best_response_shown": placebo(h["brinfo"]),
        "no_number": placebo(h["baseline"]),
    }
    s = w2.family_games("sonnet55", ("baseline", "brinfo"))
    out["sonnet55"] = {
        "best_response_shown": placebo(s["brinfo"]),
        "no_number": placebo(s["baseline"]),
    }
    o = w2.family_games("opus55", ("baseline", "brinfo"))["brinfo"]
    out["opus55"] = {"best_response_shown": placebo(o), "no_number": placebo(opus["baseline"])}
    return out


def notes_after_cut() -> str:
    lines = [
        "# Wave 4 notes: Opus 5.5 after a forced cut",
        "",
        "Firm A's notes at B+2 in each deviate arm, verbatim: the first round Firm A sets after seeing Firm B "
        "forced to Nash in B+1. Exploratory, fixed in WAVE4_PLAN.md before any wave-4 game ran.",
    ]
    for f in sorted((FRONTIER / "opus55").glob("*_deviate.jsonl")):
        source = f.stem.rsplit("_", 1)[0]
        settle = [json.loads(x) for x in (f.parent / f"{source}_settle.jsonl").open()]
        target = max(int(r["round"]) for r in settle) + 2
        rows = [json.loads(x) for x in f.open()]
        hit = [r for r in rows if r["firm"] == "Firm A" and int(r["round"]) == target]
        if not hit:
            continue
        state = hit[0]["state"]
        lines += ["", f"## Source {source}, round {target}", ""]
        for k in ("observations", "plans", "insights"):
            lines += [f"**{k.capitalize()}**", "", str(state.get(k, "")).strip(), ""]
    return "\n".join(lines)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    res = {"plan": "followup/WAVE4_PLAN.md"}
    res["diagnosis"] = diagnosis(np.random.default_rng(11))
    rng = np.random.default_rng(2026)
    g = opus_games()
    res["prevention"] = prevention(g, rng)
    tests = {}
    if (
        "opus55" in res["diagnosis"]
        and res["diagnosis"]["opus55"]["hidden_sign_flip_p"] is not None
    ):
        tests["removal"] = res["diagnosis"]["opus55"]["hidden_sign_flip_p"]
    hidden_row = next((r for r in res["prevention"] if r["arm"] == "hidden"), None)
    if hidden_row:
        tests["prevention"] = hidden_row["p_permutation"]
    res["opus_hidden_holm"] = p.holm(tests) if tests else {}
    res["deference_placebo"] = deference_placebo(g)
    if (FRONTIER / "opus55").exists():
        (OUT / "wave4_notes.md").write_text(notes_after_cut())
    for r in res["diagnosis"].values():
        r.pop("path_band", None)
    (OUT / "wave4.json").write_text(json.dumps(res, indent=1, default=float))
    for fam, r in res["diagnosis"].items():
        print(
            f"{r['model']}: {r['verdict_plan']} (rule: {r['verdict']}) punishment {r['punishment']:+.3f} "
            f"{[round(v, 3) for v in r['punishment_ci']]} band lo {r['null_lo']:+.3f} return {r['return']:+.3f} "
            f"move rate {r['move_rate']:.2f} median step {r['median_step']:.4f} sources {r['sources']}"
        )
        if "hidden" in r:
            print(
                f"  hidden (removal) {r['hidden']:+.3f} {[round(v, 3) for v in r['hidden_ci']]} "
                f"sign-flip p {r['hidden_sign_flip_p']:.3f}"
            )
    for r in res["prevention"]:
        print(
            f"prevention {r['arm']:8s} n={r['games']:2d} index={r['index_51_100']:+.2f} "
            f"high={r['share_above_0.3']:.0%} effect={r.get('effect', 0):+.2f} {r.get('effect_ci', '')} "
            f"p={r.get('p_permutation', float('nan')):.4f}"
        )
    print("Holm over removal and prevention:", res["opus_hidden_holm"])
    for m, d in res["deference_placebo"].items():
        for arm, bins in d.items():
            print(
                m,
                arm,
                {
                    k: (
                        v["firm_rounds"],
                        round(v["share_within_1pct"], 3)
                        if v["share_within_1pct"] is not None
                        else None,
                    )
                    for k, v in bins.items()
                },
            )
