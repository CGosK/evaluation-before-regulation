"""
The forced-cut null bands with prices on the base demand scale (November 2026, not part of the submission).

theory/frontier_results.py passes each saved state's prices to the null simulation as they are. Six of the 8
states come from markets scaled by alpha = 3.2 or 10, and the simulation assumes alpha = 1, so their bands and
the best responder's speed come out mis-scaled. This reruns the paper's analysis twice for every model it
diagnosed (the paper's §4.2 and wave 4): as published, and with each arm's prices divided by its alpha.
theory/ is not edited; its read() is wrapped.

Usage:  uv run --extra analysis python followup/null_band_scale.py
Writes: followup/out/null_band_scale.json
"""

import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "theory")]
import frontier_results as fres  # noqa: E402
from bandit import benchmarks, fit, load, markets  # noqa: E402

PN, PM = benchmarks(2)
RUNS = {
    "haiku": HERE.parent / "succession/runs/frontier",
    "fable": HERE.parent / "succession/runs/frontier",
    "haiku45": HERE.parent / "succession/runs/frontier",
    "haiku45_enforcer": HERE.parent / "succession/runs/frontier",
    "haiku45_enforcer2": HERE.parent / "succession/runs/frontier",
    "opus55": HERE / "runs/wave4/frontier",
    "sonnet55": HERE / "runs/wave4/frontier",
}
KEEP = ("verdict", "punishment", "return", "null_lo", "null_sbr", "null_br", "lambda_hat")
published_read = fres.read


def base_scale_read(model: str) -> dict:
    runs = published_read(model)
    for arms in runs.values():
        for a in arms.values():
            alpha = float(np.nanmedian(a["price"] / (PN + a["delta"] * (PM - PN))))
            a["price"] = a["price"] / alpha
    return runs


if __name__ == "__main__":
    duo = load().filter(pl.col("num_agents") == 2)
    m = fit(markets(duo.filter(pl.col("prompt") == "P1")))
    out = {}
    for model, runs in RUNS.items():
        fres.RUNS, fres.MODELS = runs, {model: model}
        out[model] = {}
        for label, reader in (("as_published", published_read), ("base_scale", base_scale_read)):
            fres.read = reader
            r = fres.analyse(model, m, np.random.default_rng(11))
            out[model][label] = {k: r[k] for k in KEEP}
        fres.read = published_read
    (HERE / "out/null_band_scale.json").write_text(json.dumps(out, indent=1, default=float))
    for model, v in out.items():
        a, b = v["as_published"], v["base_scale"]
        print(
            f"{model:18s} {a['verdict']:>14s} -> {b['verdict']:<14s} punishment {a['punishment']:+.3f}"
            f"  band lower bound {a['null_lo']:+.3f} -> {b['null_lo']:+.3f}"
            f"  lambda {a['lambda_hat']:.3f} -> {b['lambda_hat']:.3f}"
        )
