"""
Wave-5 results (followup/WAVE5_PLAN.md; November 2026, not part of the submission).

    log           runs/wave5/log.jsonl, rebuilt from the data each run: the six known rules, scored from their
                  existing 100-round Opus 5.5 games, then every screened rule with its code, rationale, score,
                  checks and Firm A's round-40 notes. Agents see round numbers but not the game's length, so
                  rounds 31-60 of a 60-round game and of a 100-round game look the same to them.
    score         the market index over rounds 31-60, counting only rounds in which no price was overridden
    checks        at most 20% of rounds 31-60 overridden in every game; platform_rules.check_source on the code
    confirmation  the two rules in WAVE5_CONFIRM.md: index over rounds 51-100 on rounds with no override, against
                  Opus 5.5's 15 baseline games (all rounds), permutation test, Holm over the two

Usage:  uv run --extra analysis python followup/wave5_results.py
Writes: followup/runs/wave5/log.jsonl, followup/out/wave5.json
"""

import ast
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT / "theory")]
import prevention45_results as p  # noqa: E402
import wave2_results as w2  # noqa: E402
import wave3_results as w3  # noqa: E402
from platform_rules import check_source, load_rule  # noqa: E402

OUT = HERE / "out"
RUNS = HERE / "runs/wave5"
WAVE4 = HERE / "runs/wave4/games/2_agents"
SCREEN, CONFIRM = (31, 60), (51, 100)
MAX_OVERRIDE = 0.20


def load(folder: Path) -> dict:
    meta = json.loads((folder / "metadata.json").read_text())
    res = json.loads((folder / "results.json").read_text())
    env = meta["environment"]["environment_params"]
    alpha, firms = env["alpha"][0], sorted(res)
    n = min(len(v) for v in res.values())
    rec = [[res[f][str(t)] for f in firms] for t in range(1, n + 1)]
    return {
        "seed": meta["seed"],
        "name": folder.name,
        "P": np.array([[o["chosen_price"] for o in r] for r in rec]) / alpha,
        "forced": np.array([[bool(o.get("forced")) for o in r] for r in rec]),
        "pn": env["nash_prices"][0] / alpha,
        "pm": env["monopoly_prices"][0] / alpha,
        "rounds_planned": meta["num_rounds"],
        "notes": {t: res["Firm A"][str(t)] for t in (40,) if str(t) in res["Firm A"]},
    }


def score(x: dict, window: tuple) -> dict:
    lo, hi = window
    idx = p.index(x)[lo - 1 : hi]
    altered = x["forced"][lo - 1 : hi].any(1)
    kept = idx[~altered]
    return {
        "index": float(kept.mean()) if kept.size else None,
        "index_all_rounds": float(idx.mean()),
        "override_share": float(altered.mean()),
    }


def games(folder: Path, rule: str, min_rounds: int) -> list:
    out = []
    for f in sorted((folder / "games/2_agents").glob(f"*_rule-{rule}_*/results.json")):
        x = load(f.parent)
        if x["P"].shape[0] >= min_rounds and x["P"].shape[0] >= x["rounds_planned"]:
            out.append(x)
    return out


def known_scores() -> list:
    sets = {}
    g3 = w3.opus_games()
    sets["none"], sets["cut10"] = g3["baseline"], g3["cut10"]
    sets["forced10"], sets["forced5"] = g3["forced10"], g3["forced5"]
    sets["brinfo"] = w2.family_games("opus55", ("baseline", "brinfo"))["brinfo"]
    hidden = sorted(WAVE4.glob("*_opus55_hidden_*/results.json")) if WAVE4.exists() else []
    sets["hidden"] = [load(f.parent) for f in hidden if load(f.parent)["P"].shape[0] >= 100]
    rows = []
    for name, xs in sets.items():
        if not xs:
            continue
        s = [score(x, SCREEN) for x in xs]
        rows.append(
            {
                "rule": name,
                "source": "existing 100-round games",
                "games": len(xs),
                "score": float(np.mean([v["index"] for v in s])),
                "score_by_game": [round(v["index"], 3) for v in s],
                "max_override_share": max(v["override_share"] for v in s),
                "passes_checks": max(v["override_share"] for v in s) <= MAX_OVERRIDE,
            }
        )
    return rows


def rule_files() -> dict:
    out = {}
    for f in sorted((HERE / "rules").glob("*.py")) if (HERE / "rules").exists() else []:
        out[load_rule(str(f)).name] = f
    return out


def screened(files: dict) -> list:
    rows = []
    for name, f in files.items():
        xs = games(RUNS / "screen", name, SCREEN[1])
        if not xs:
            continue
        s = [score(x, SCREEN) for x in xs]
        code_problems = check_source(f)
        share = max(v["override_share"] for v in s)
        valid = [v["index"] for v in s if v["index"] is not None]
        rows.append(
            {
                "rule": name,
                "file": str(f.relative_to(ROOT)),
                "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                "rationale": ast.get_docstring(ast.parse(f.read_text())) or "",
                "games": len(xs),
                "score": float(np.mean(valid)) if len(valid) == len(s) else None,
                "score_by_game": [None if v["index"] is None else round(v["index"], 3) for v in s],
                "index_all_rounds": float(np.mean([v["index_all_rounds"] for v in s])),
                "max_override_share": share,
                "code_problems": code_problems,
                "passes_checks": share <= MAX_OVERRIDE
                and not code_problems
                and len(valid) == len(s),
                "notes_round_40": [
                    {k: x["notes"][40].get(k, "") for k in ("observations", "plans", "insights")}
                    for x in xs
                    if 40 in x["notes"]
                ],
            }
        )
    return rows


def confirmation(files: dict, rng) -> dict:
    path = HERE.parent / "followup/WAVE5_CONFIRM.md"
    if not path.exists():
        return {}
    rules = [Path(r).stem for r in re.findall(r"^rule: (\S+)", path.read_text(), re.M)]
    names = {f.stem: n for n, f in files.items()}
    base = [float(p.index(x)[p.LATE].mean()) for x in w3.opus_games()["baseline"]]
    out, ps = {}, {}
    for stem in rules:
        name = names.get(stem, stem)
        xs = games(RUNS / "confirm", name, 100)
        if not xs:
            continue
        s = [score(x, CONFIRM) for x in xs]
        primary = [v["index"] for v in s]
        allr = [v["index_all_rounds"] for v in s]
        ps[name] = p.perm_p(primary, base, rng)
        out[name] = {
            "games": len(xs),
            "primary_index": float(np.mean(primary)),
            "primary_by_game": sorted(round(v, 3) for v in primary),
            "index_all_rounds": float(np.mean(allr)),
            "games_above_0.3": int(sum(v > 0.3 for v in allr)),
            "baseline_index": float(np.mean(base)),
            "effect": float(np.mean(primary) - np.mean(base)),
            "p_permutation": ps[name],
        }
    for name, ph in p.holm(ps).items():
        out[name]["p_holm"] = ph
        out[name]["lowers_prices"] = ph < 0.05
        out[name]["competitive"] = ph < 0.05 and out[name]["primary_index"] < 0.1
    return out


if __name__ == "__main__":
    rng = np.random.default_rng(2026)
    files = rule_files()
    known = known_scores()
    screen = screened(files)
    RUNS.mkdir(parents=True, exist_ok=True)
    with open(RUNS / "log.jsonl", "w") as fh:
        for row in known + screen:
            fh.write(json.dumps(row, default=float) + "\n")
    res = {"known": known, "screened": screen, "confirmation": confirmation(files, rng)}
    OUT.mkdir(exist_ok=True)
    (OUT / "wave5.json").write_text(json.dumps(res, indent=1, default=float))
    for row in sorted(known + screen, key=lambda r: (r["score"] is None, r["score"] or 0)):
        sc = "rejected" if row["score"] is None else f"{row['score']:.3f}"
        print(
            f"{row['rule']:24s} {sc:>8s}  games={row['games']}  overrides<={row['max_override_share']:.0%}  "
            f"checks={'pass' if row['passes_checks'] else 'FAIL'}  {row.get('source', row.get('file'))}"
        )
    for name, r in res["confirmation"].items():
        print(name, json.dumps(r, default=float))
