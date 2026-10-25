"""
Does best-response information work by teaching agents or by agents deferring to the platform's number?

For each firm-round in which the market data showed the platform's estimate of the firm's best response, the
firm "adopts" it if its next price is within 1% of that estimate. Reference: in the baseline games, how often
a firm's next price lands within 1% of its best response with no one telling it.
    Prevention: Claude Haiku 4.5, best-response arm vs baseline (succession/runs/prevention45), rounds 11-99.
    Removal: the best-response arms from the eight high-price states, for Haiku 4.5 and for Haiku 4.5 told to
    enforce (succession/runs/frontier/haiku45*, all arm rounds).

Usage:  uv run --extra analysis python theory/deference_test.py
Writes: theory/out/deference_test.json
"""

import glob
import json
import os
import re
import sys
from pathlib import Path

import numpy as np

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
import prevention45_results as p
from bandit import best_response

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "out"
EST = re.compile(r"profit-maximizing price given the competitor'?s'? prices?: ([0-9.]+)")


def adoption(seq: list) -> float:
    """seq: (estimate shown at t, own price at t+1) pairs."""
    return float(np.mean([abs(np.log(nxt / est)) < 0.01 for est, nxt in seq])) if seq else float("nan")


def prevention() -> dict:
    out = {}
    for arm in ("brinfo", "baseline"):
        seq = []
        for x in p.games()[arm]:
            folder = next(d / x["name"] for d in p.RUNS if (d / x["name"]).exists())
            res = json.loads((folder / "results.json").read_text())
            alpha = json.loads((folder / "metadata.json").read_text())["environment"]["environment_params"]["alpha"][0]
            firms = sorted(res)
            for t in range(11, 100):
                for i, firm in enumerate(firms):
                    if arm == "brinfo":
                        m = EST.search(res[firm][str(t)]["market_data"])
                        est = float(m.group(1)) if m else None
                    else:
                        est = best_response(np.array([[res[f][str(t)]["chosen_price"] / alpha for f in firms]]))[0, i] * alpha
                    if est:
                        seq.append((est, res[firm][str(t + 1)]["chosen_price"]))
        out[arm] = {"firm_rounds": len(seq), "within_1pct_of_best_response": adoption(seq)}
    return out


def removal(model: str) -> dict:
    seq = []
    for f in sorted(glob.glob(str(ROOT / f"succession/runs/frontier/{model}/*_brinfo.jsonl"))):
        rows = [json.loads(line) for line in open(f)]
        by = {(r["round"], r["firm"]): r for r in rows}
        for (t, firm), r in by.items():
            m = EST.search(r["state"]["market_data"])
            if m and (t + 1, firm) in by:
                seq.append((float(m.group(1)), by[(t + 1, firm)]["price"]))
    return {"firm_rounds": len(seq), "within_1pct_of_estimate": adoption(seq)}


if __name__ == "__main__":
    res = {"prevention": prevention(), "removal_haiku45": removal("haiku45"),
           "removal_haiku45_enforcer": removal("haiku45_enforcer2")}
    (OUT / "deference_test.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1, default=lambda v: round(v, 3)))
