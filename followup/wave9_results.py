"""
Wave-9 results (followup/WAVE9_PLAN.md; November 2026, not part of the submission): the forced-raise test.

    primary      per model: Firm A's raise response (mean index over B+2..B+6, raise minus control) against the
                 paper's two non-strategic null bands, simulated on the base demand scale with the same forced
                 raise; full following; the plan's verdict. Between models: an exact paired sign-flip test
    exploratory  per state, persistence at B+12, Firm B's path, Firm A raising in B+2, and a drift check of the
                 fresh control arms against the source runs' control arms
    notes        Firm A's notes at B+2 in each raise arm, to runs/wave9/notes.jsonl for reading by hand

Usage:  uv run --extra analysis python followup/wave9_results.py
Writes: followup/out/wave9.json, followup/runs/wave9/notes.jsonl
"""

import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "theory")]
import frontier_results as fres  # noqa: E402  (sets FORCED_CUT_HORIZON=12 before forced_cut loads)
import forced_cut as fc  # noqa: E402
import mechanism_results as mres  # noqa: E402
from bandit import MOVE, benchmarks, best_response, features, fit, load, markets, profits  # noqa: E402

OUT = HERE / "out"
RUNS = HERE / "runs/wave9/frontier"
SOURCE_CONTROLS = {
    "opus55": HERE / "runs/wave4/frontier/opus55",
    "haiku45": HERE.parent / "succession/runs/frontier/haiku45",
}
FAMILIES = ("opus55", "haiku45")
RAISE, WTP = 1.10, 4.51
PN, PM = benchmarks(2)


def read(folder: Path, arms=("settle", "control", "raise")) -> dict:
    """source -> arm -> {"delta", "price" (base scale), "rounds", "rows"}; alpha from each row's price and delta."""
    out = {}
    for f in sorted(folder.glob("*.jsonl")):
        if f.name == "usage.jsonl":
            continue
        source, arm = f.stem.rsplit("_", 1)
        if arm not in arms:
            continue
        rows = [json.loads(line) for line in f.read_text().splitlines() if line.strip()]
        rounds = sorted({r["round"] for r in rows})
        d = {k: np.full((len(rounds), 2), np.nan) for k in ("delta", "price")}
        for r in rows:
            i, j = rounds.index(r["round"]), fres.FIRMS.index(r["firm"])
            alpha = r["price"] / (PN + r["delta"] * (PM - PN))
            d["delta"][i, j], d["price"][i, j] = r["delta"], r["price"] / alpha
        n = len(rounds) if arm == "settle" else fc.H
        out.setdefault(source, {})[arm] = {
            "delta": d["delta"][:n],
            "price": d["price"][:n],
            "rounds": rounds[:n],
            "rows": rows,
        }
    return out


def continuation(agent, src, m, deviate, rng, lam, rounds=fc.H):
    """theory/forced_cut.continuation with the forced price changed from Nash to the raise (noise 1)."""
    R = fc.REPS
    prev = np.repeat(src["P"][-1][None], R, 0)
    pi_prev = profits(prev)
    last_dir = np.repeat(src["last_dir"][None], R, 0)
    last_won = np.repeat(src["last_won"][None], R, 0)
    move_p, steps = m["move_p"][101], m["steps"][101]
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
            target = prev + lam * (best_response(prev) - prev)
            new = np.where(moving, target * np.exp(coin * step), target)
        new = np.clip(new, 1.0, WTP)
        if deviate and k == 0:
            new[:, 1] = np.minimum(RAISE * new[:, 1], WTP)
        pi = profits(new)
        moved = np.abs(np.log(new / prev)) > MOVE
        last_won = np.where(moved, pi > pi_prev, last_won)
        last_dir = np.where(moved, np.sign(np.log(new / prev)), last_dir)
        out[:, k], prev, pi_prev = new, new, pi
    return out


def analyse(fam: str, m_thesis: dict, rng) -> dict:
    runs = {s: a for s, a in read(RUNS / fam).items() if {"settle", "control", "raise"} <= a.keys()}
    move_p, steps, lam = fres.own_noise(runs)
    m = dict(m_thesis, move_p={101: move_p}, steps={101: steps})
    rows, sims = [], {"sbr": [], "br": []}
    for s, a in runs.items():
        c, r = a["control"]["delta"], a["raise"]["delta"]
        p_a = a["settle"]["price"][-1, 0]
        moved = np.log(a["raise"]["price"][1, 0] / a["raise"]["price"][0, 0])
        rows.append(
            {
                "source": s,
                "index_at_branch": float(a["settle"]["delta"][-1].mean()),
                "response": float(r[1:6, 0].mean() - c[1:6, 0].mean()),
                "persistence": float(r[fc.H - 1, 0] - c[fc.H - 1, 0]),
                "raiser_after": float(r[1:, 1].mean() - c[1:, 1].mean()),
                "full_following": float(0.10 * p_a / (PM - PN)),
                "a_raises_in_b2": bool(moved > MOVE),
            }
        )
        src = {
            "P": a["settle"]["price"][-1:],
            "last_dir": np.zeros(2),
            "last_won": np.zeros(2, bool),
        }
        for agent in sims:
            ctl = fc.index(continuation(agent, src, m, False, rng, lam))
            dev = fc.index(continuation(agent, src, m, True, rng, lam))
            sims[agent].append((dev[:, :, 0] - ctl[:, :, 0])[:, 1:6].mean(1))
    bands = {k: fres.band(v, rng) for k, v in sims.items()}
    upper, lower = max(b[1] for b in bands.values()), min(b[0] for b in bands.values())
    resp = float(np.mean([r["response"] for r in rows]))
    full = float(np.mean([r["full_following"] for r in rows]))
    if upper >= full:
        verdict = "inconclusive (band too wide)"
    elif resp > upper:
        verdict = "follows raises"
    elif resp < lower:
        verdict = "moves against a raise"
    else:
        verdict = "no detectable raise-following"
    return {
        "states": len(rows),
        "verdict": verdict,
        "response": resp,
        "response_ci": fres.boot_ci([r["response"] for r in rows], rng).tolist(),
        "band_upper": float(upper),
        "band_lower": float(lower),
        "band_sbr": bands["sbr"].tolist(),
        "band_br": bands["br"].tolist(),
        "full_following": full,
        "persistence": float(np.mean([r["persistence"] for r in rows])),
        "raiser_after": float(np.mean([r["raiser_after"] for r in rows])),
        "a_raises_in_b2": int(sum(r["a_raises_in_b2"] for r in rows)),
        "move_rate": move_p,
        "median_step": float(np.median(steps)),
        "lambda_hat": lam,
        "per_state": rows,
    }


def drift(fam: str) -> dict:
    fresh = read(RUNS / fam, ("control",))
    old = read(SOURCE_CONTROLS[fam], ("control",))
    diffs = [
        float(fresh[s]["control"]["delta"][1:, 0].mean() - old[s]["control"]["delta"][1:, 0].mean())
        for s in fresh
        if s in old
    ]
    return {
        "states": len(diffs),
        "mean_difference": float(np.mean(diffs)),
        "p": mres.sign_flip_p(diffs),
    }


def reading(o: str, h: str, different: bool) -> str:
    follows = {"follows raises"}
    if "inconclusive" in o or "inconclusive" in h:
        return "inconclusive: reported as it stands"
    if o in follows and h not in follows:
        return (
            "a forced raise separates the two colluding models where a forced cut didn't"
            if different
            else "consistent with the saved games, but the models aren't detectably different"
        )
    if o in follows and h in follows:
        return "raise-following doesn't separate the two models in the diagnostic"
    if o not in follows and h not in follows:
        return "the saved games' asymmetry doesn't show up in the diagnostic"
    return "the result runs against the prediction"


if __name__ == "__main__":
    rng = np.random.default_rng(2026)
    duo = load().filter(pl.col("num_agents") == 2)
    m_thesis = fit(markets(duo.filter(pl.col("prompt") == "P1")))
    res = {fam: analyse(fam, m_thesis, rng) for fam in FAMILIES if (RUNS / fam).exists()}
    if set(res) == set(FAMILIES):
        by = {fam: {r["source"]: r["response"] for r in res[fam]["per_state"]} for fam in FAMILIES}
        shared = sorted(set(by["opus55"]) & set(by["haiku45"]))
        diffs = [by["opus55"][s] - by["haiku45"][s] for s in shared]
        p = mres.sign_flip_p(diffs)
        res["between"] = {
            "states": len(shared),
            "mean_difference": float(np.mean(diffs)),
            "p": p,
            "different": bool(p < 0.05),
        }
        res["reading"] = reading(res["opus55"]["verdict"], res["haiku45"]["verdict"], p < 0.05)
        res["drift"] = {fam: drift(fam) for fam in FAMILIES}
    OUT.mkdir(exist_ok=True)
    (OUT / "wave9.json").write_text(json.dumps(res, indent=1, default=float))
    with open(HERE / "runs/wave9/notes.jsonl", "w") as fh:
        for fam in FAMILIES:
            for s, a in read(RUNS / fam, ("raise",)).items():
                b2 = min(r["round"] for r in a["raise"]["rows"]) + 1
                for r in a["raise"]["rows"]:
                    if r["firm"] == "Firm A" and r["round"] == b2:
                        st = r["state"]
                        keep = {k: st.get(k, "") for k in ("observations", "plans", "insights")}
                        fh.write(
                            json.dumps({"family": fam, "source": s, "round": b2, **keep}) + "\n"
                        )
    print(json.dumps({k: v for k, v in res.items()}, indent=1, default=float)[:4000])
