"""
Exploratory numbers in followup/README.md that the planned analyses (followup_results.py, wave2_results.py,
wave3_results.py) do not produce. None of them is a test the plans fixed; the permutation p-values here are
exploratory comparisons.

    wave 2  deference by game for the bias arms and the exact best-response arms; the rival's next price change
            after each forced 10% cut (Haiku 4.5 in wave 1, Sonnet 5.5 and Opus 5.5 in wave 2); thinking by model
    wave 3  each forced arm's lowest 10-round block, its index over rounds 51-100 without the forced rounds, the
            index just after a forced round and just before the next; forced Nash every 5 against every 10, and
            wave 2's 10% cut against forced Nash every 10; the submission's Haiku 4.5 forced-Nash games

Usage:  uv run --extra analysis python followup/exploratory_results.py
Writes: followup/out/exploratory.json
"""

import json
import statistics
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "theory")]
import followup_results as fr  # noqa: E402
import prevention45_results as p  # noqa: E402
import wave2_results as w2  # noqa: E402
import wave3_results as w3  # noqa: E402

SUBMITTED_ARMS = p.ARMS
OUT = HERE / "out"


def late(x: dict) -> float:
    return float(p.index(x)[p.LATE].mean())


def deference_by_game(games: list) -> dict:
    rows = []
    for x in sorted(games, key=lambda x: int(x["seed"])):
        d = fr.deference([x])
        rows.append(
            {
                "seed": int(x["seed"]),
                "index_51_100": round(late(x), 3),
                "shown": round(d["within_1pct_of_shown"], 3),
                "true_best_response": round(d["within_1pct_of_true_best_response"], 3),
            }
        )
    return {
        "shown_range": [min(r["shown"] for r in rows), max(r["shown"] for r in rows)],
        "true_range": [
            min(r["true_best_response"] for r in rows),
            max(r["true_best_response"] for r in rows),
        ],
        "games": rows,
    }


def thinking_by_model(usage: Path) -> dict:
    tokens = {}
    for line in usage.open():
        d = json.loads(line)
        tokens.setdefault(d["model"], []).append(d.get("thinking_tokens") or 0)
    out = {}
    for model, t in tokens.items():
        used = [v for v in t if v > 0]
        out[model] = {
            "calls": len(t),
            "share_with_thinking": len(used) / len(t),
            "median_thinking_tokens": statistics.median(used) if used else 0,
        }
    return out


def unforced(games: list) -> dict:
    idx = [p.index(x)[p.LATE][~x["forced"][p.LATE].any(1)].mean() for x in games]
    return {"index_51_100": float(np.mean(idx)), "games_above_0.3": int(sum(v > 0.3 for v in idx))}


def lowest_block(games: list) -> dict:
    blocks = np.mean([p.index(x) for x in games], axis=0).reshape(10, 10).mean(1)
    k = int(blocks.argmin())
    return {"rounds": f"{10 * k + 1}-{10 * k + 10}", "mean_index": float(blocks[k])}


def recovery(games: list, every: int) -> dict:
    """Cycles that start after forced rounds 51-99: the round after the forced round, and the round before the next."""
    path = np.mean([p.index(x) for x in games], axis=0)  # path[r - 1] is round r
    starts = [r for r in range(51, 100) if r % every == 0]
    return {
        "forced_rounds": starts,
        "round_after": float(np.mean([path[r] for r in starts])),
        "round_before_next": float(np.mean([path[r + every - 2] for r in starts])),
    }


def perm(a: list, b: list, rng) -> float:
    return p.perm_p([late(x) for x in a], [late(x) for x in b], rng)


def set_runs(model: str, runs: list, arm_of, arms: tuple):
    p.MODEL, p.RUNS, p.arm_of, p.ARMS = model, runs, arm_of, arms


if __name__ == "__main__":
    rng = np.random.default_rng(2026)
    res = {"wave2": {"deference_by_game": {}, "cut_response": {}}, "wave3": {}}

    for fam, arm in w2.BIAS + [("sonnet55", "brinfo"), ("opus55", "brinfo")]:
        g = w2.family_games(fam, ("baseline", arm))[arm]
        res["wave2"]["deference_by_game"][f"{fam} {arm}"] = deference_by_game(g)

    set_runs(
        "claude-haiku-4-5",
        w2.SUBMITTED + [HERE / "runs/games/2_agents"],
        fr.arm_of,
        fr.REF + fr.NEW,
    )
    res["wave2"]["cut_response"]["haiku45 (wave 1)"] = w3.rival_response(p.games()["cut10"])
    for fam in ("sonnet55", "opus55"):
        g = w2.family_games(fam, ("baseline", "cut10"))["cut10"]
        res["wave2"]["cut_response"][fam] = w3.rival_response(g)
    res["wave2"]["thinking"] = thinking_by_model(HERE / "runs/wave2/usage.jsonl")

    g = w3.opus_games()
    for arm, every in (("forced10", 10), ("forced5", 5)):
        res["wave3"][arm] = {
            "without_forced_rounds": unforced(g[arm]),
            "lowest_block": lowest_block(g[arm]),
            "recovery": recovery(g[arm], every),
            "forced_rounds_per_game": int(np.mean([x["forced"].any(1).sum() for x in g[arm]])),
        }
    res["wave3"]["p_forced5_vs_forced10"] = perm(g["forced5"], g["forced10"], rng)
    res["wave3"]["p_cut10_wave2_vs_forced10"] = perm(g["cut10"], g["forced10"], rng)

    set_runs("claude-haiku-4-5", w2.SUBMITTED, w2.SUBMITTED_ARM_OF, SUBMITTED_ARMS)
    h = p.games()["forced10"]
    path = np.mean([p.index(x) for x in h], axis=0)
    first = next((k for k in range(0, 100, 10) if path[k : k + 10].mean() < 0.1), None)
    res["wave3"]["haiku45_submission_forced10"] = {
        "games": len(h),
        "first_block_below_0.1": f"{first + 1}-{first + 10}" if first is not None else None,
        "index_51_100_range_by_round": [float(path[50:100].min()), float(path[50:100].max())],
        "without_forced_rounds": unforced(h),
    }

    OUT.mkdir(exist_ok=True)
    (OUT / "exploratory.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(res["wave3"], indent=1, default=float))
    print(json.dumps(res["wave2"]["cut_response"], indent=1, default=float))
    for k, v in res["wave2"]["deference_by_game"].items():
        print(k, "shown", v["shown_range"], "true", v["true_range"])
    print(json.dumps(res["wave2"]["thinking"], indent=1, default=float))
