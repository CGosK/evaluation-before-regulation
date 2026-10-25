"""
Robustness of the forced-cut verdicts (theory/frontier_results.py) to the SBR null's direction rule.

The SBR null there takes each model's own move rate and step sizes from its control arms, but its cut
rule, P(cut | move) = logistic(b0 + b1 * gap), is the one fitted on the thesis's Mistral P1 games. Here
the rule is refitted on each Claude model's own unforced rounds:
    Claude Haiku 5.5   control arms of the frontier runs, plus the six baseline prevention games
                       (succession/runs/prevention, rounds 11-100)
    Claude Fable 5.1   control arms of the frontier runs
    Claude Haiku 4.5   control arms of the frontier runs, plus its baseline prevention games
                       (succession/prevention45.py, rounds 11-100)
and the null band, verdict and punishment are recomputed with the refitted rule.

Usage:  uv run --extra analysis python theory/own_rule_null.py
Writes: theory/out/own_rule_null.json
"""

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("FORCED_CUT_HORIZON", "12")

import numpy as np
import polars as pl
import statsmodels.api as sm

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
import frontier_results as fr
from bandit import MOVE, OPEN, best_response, fit, load, markets

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "out"


def moves(P: np.ndarray, first: int = 0) -> tuple:
    """(gap, cut) for every move from round first+1 on: gap = log(p / best response) the round before."""
    G = np.log(P[:-1] / best_response(P[:-1]))
    dX = np.diff(np.log(P), axis=0)
    keep = np.abs(dX) > MOVE
    keep[:first] = False
    return G[keep], dX[keep] < 0


def prevention_baselines() -> list:
    out = []
    for f in sorted((ROOT / "succession/runs/prevention/games").glob("*/results.json")):
        if "_rpe_" in f.parent.name or "_brinfo_" in f.parent.name:
            continue
        e = json.loads((f.parent / "metadata.json").read_text())["environment"]["environment_params"]
        r = json.loads(f.read_text())
        P = np.array([[r[a][str(t)]["chosen_price"] for a in r] for t in range(1, 101)]) / e["alpha"][0]
        out.append(P)
    return out


def own_rule(model: str) -> dict:
    gaps, cuts = [], []
    for a in fr.read(model).values():
        g, c = moves(np.vstack([a["settle"]["price"], a["control"]["price"]]))
        gaps.append(g), cuts.append(c)
    n_ctl = int(sum(len(g) for g in gaps))
    if model in ("haiku", "haiku45"):
        if model == "haiku":
            baselines = prevention_baselines()
        else:
            import prevention45_results as p45
            baselines = [g["P"] for g in p45.games()["baseline"]]
        for P in baselines:
            g, c = moves(P, first=OPEN)
            gaps.append(g), cuts.append(c)
    gap, cut = np.concatenate(gaps), np.concatenate(cuts)
    X = np.column_stack([np.ones_like(gap), gap])
    res = sm.Logit(cut.astype(float), X).fit(disp=0)
    return {"coef": res.params, "se": res.bse, "moves": len(gap), "moves_control_arms": n_ctl,
            "cut_share": float(cut.mean())}


if __name__ == "__main__":
    rng = np.random.default_rng(3)
    duo = load().filter(pl.col("num_agents") == 2)
    m_thesis = fit(markets(duo.filter(pl.col("prompt") == "P1")))
    out = {"mistral_p1_rule": m_thesis["coef"]["gradient"].tolist()}
    for model in [m for m in fr.MODELS if (fr.RUNS / m).exists()]:
        rule = own_rule(model)
        base = fr.analyse(model, m_thesis, np.random.default_rng(3))
        refit = fr.analyse(model, dict(m_thesis, coef={"gradient": rule["coef"]}), rng)
        out[model] = {
            "own_rule": rule["coef"].tolist(), "own_rule_se": rule["se"].tolist(), "moves": rule["moves"],
            "moves_control_arms": rule["moves_control_arms"], "cut_share": rule["cut_share"],
            "punishment": refit["punishment"],
            "thesis_rule": {k: base[k] for k in ("null_lo", "null_sbr", "null_br", "verdict")},
            "own_rule_null": {k: refit[k] for k in ("null_lo", "null_sbr", "null_br", "verdict")},
        }
    (OUT / "own_rule_null.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=lambda x: round(float(x), 3)))
