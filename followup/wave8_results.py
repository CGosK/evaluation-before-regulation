"""
Wave-8 results (followup/WAVE8_PLAN.md; November 2026, not part of the submission).

    primary      each firm's own index over rounds 51-100 in the two mixed pairings against its model's own
                 baseline games, and the brinfo arm's market index against opus-haiku45's: five permutation
                 tests with Holm's correction, and the plan's decisions
    exploratory  games above 0.3, 10-round blocks, own indices by game, each arm against both baselines,
                 follow rate by model and each model against its own brinfo games, the leader-follower
                 benchmark, and which firm's moves the other follows
    notes        both firms' notes at rounds 30, 60 and 90, to runs/wave8/notes.jsonl for reading by hand

Usage:  uv run --extra analysis python followup/wave8_results.py
Writes: followup/out/wave8.json, followup/runs/wave8/notes.jsonl
"""

import json
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "theory")]
import bandit  # noqa: E402
import prevention45_results as p  # noqa: E402
import wave2_results as w2  # noqa: E402
import wave3_results as w3  # noqa: E402

OUT = HERE / "out"
RUNS = HERE / "runs/wave8"
OPUS = "claude-opus-5-5"
ARMS = ("opus-haiku55", "opus-haiku45", "opus-haiku45-brinfo")
RIVAL = {"opus-haiku55": "haiku55", "opus-haiku45": "haiku45", "opus-haiku45-brinfo": "haiku45"}
EST = re.compile(r"profit-maximizing price given the competitor'?s'? prices?: ([0-9.]+)")
NOTE_ROUNDS = (30, 60, 90)
MOVE = 0.01


def games() -> dict:
    out = {a: [] for a in ARMS}
    for f in sorted((RUNS / "games/2_agents").glob("*/results.json")):
        m = re.search(r"_mixed-([a-z0-9-]+)_", f.parent.name)
        meta = json.loads((f.parent / "metadata.json").read_text())
        res = json.loads(f.read_text())
        if not m or meta.get("num_rounds") != 100 or min(len(v) for v in res.values()) < 100:
            continue
        env = meta["environment"]["environment_params"]
        firms = sorted(res)
        P = np.array([[res[k][str(t)]["chosen_price"] for k in firms] for t in range(1, 101)])
        out[m.group(1)].append(
            {
                "seed": meta["seed"],
                "folder": f.parent,
                "firms": firms,
                "models": [meta["agents_models"][k] for k in firms],
                "P": P,
                "pn": env["nash_prices"][0],
                "pm": env["monopoly_prices"][0],
            }
        )
    return out


def own(x: dict) -> np.ndarray:
    return ((x["P"] - x["pn"]) / (x["pm"] - x["pn"]))[p.LATE].mean(0)


def split(xs: list) -> tuple:
    """Opus's own index and the rival's, per game."""
    o, r = [], []
    for x in xs:
        v, i = own(x), x["models"].index(OPUS)
        o.append(float(v[i]))
        r.append(float(v[1 - i]))
    return np.array(o), np.array(r)


def market(xs: list) -> np.ndarray:
    return np.array([float(own(x).mean()) for x in xs])


def late(xs: list) -> np.ndarray:
    return np.array([float(p.index(x)[p.LATE].mean()) for x in xs])


def blocks(xs: list) -> list:
    idx = np.array([((x["P"] - x["pn"]) / (x["pm"] - x["pn"])).mean(1) for x in xs])
    return [round(float(idx[:, i : i + 10].mean()), 3) for i in range(0, 100, 10)]


def follow(xs: list) -> dict:
    hits, by_game = {}, []
    for x in sorted(xs, key=lambda z: z["seed"]):
        res = json.loads((x["folder"] / "results.json").read_text())
        row = {"seed": int(x["seed"])}
        for k, model in zip(x["firms"], x["models"]):
            game = []
            for t in range(11, 100):
                m = EST.search(res[k][str(t)]["market_data"])
                if m:
                    nxt = res[k][str(t + 1)]["chosen_price"]
                    game.append(abs(np.log(nxt / float(m.group(1)))) < 0.01)
            hits.setdefault(model, []).extend(game)
            row[model] = round(float(np.mean(game)), 3)
        by_game.append(row)
    out = {k: {"firm_rounds": len(v), "within_1pct": float(np.mean(v))} for k, v in hits.items()}
    return {**out, "by_game": by_game}


def leads(xs: list) -> dict:
    """Share of each side's price moves (over 1%) that the other matches in direction the next round."""
    opus_led, rival_led, by_game = [], [], []
    for x in sorted(xs, key=lambda z: z["seed"]):
        d = np.diff(np.log(x["P"][10:]), axis=0)
        i = x["models"].index(OPUS)
        game = ([], [])
        for t in range(len(d) - 1):
            for a, side in ((i, game[0]), (1 - i, game[1])):
                if abs(d[t, a]) > MOVE:
                    side.append(
                        bool(np.sign(d[t + 1, 1 - a]) == np.sign(d[t, a]))
                        and abs(d[t + 1, 1 - a]) > MOVE
                    )
        opus_led += game[0]
        rival_led += game[1]
        share = [round(float(np.mean(s)), 3) if s else None for s in game]
        by_game.append(
            {
                "seed": int(x["seed"]),
                "opus_moves_followed": share[0],
                "rival_moves_followed": share[1],
            }
        )
    return {
        "opus_moves": len(opus_led),
        "opus_moves_followed": float(np.mean(opus_led)) if opus_led else None,
        "rival_moves": len(rival_led),
        "rival_moves_followed_by_opus": float(np.mean(rival_led)) if rival_led else None,
        "by_game": by_game,
    }


def at_best_response(P: np.ndarray, i: int) -> np.ndarray:
    """Rounds 12-100: is firm i's price within 1% of its best response to the rival's price a round before?"""
    br = bandit.best_response(np.column_stack([P[10:99, i], P[10:99, 1 - i]]))[:, 0]
    return np.abs(np.log(P[11:100, i] / br)) < 0.01


def br_shares(xs: list) -> dict:
    """Beyond the plan: each model's share of firm-rounds at its true best response, pooled and by game."""
    pooled, by_game = {}, []
    for x in sorted(xs, key=lambda z: z["seed"]):
        row = {"seed": int(x["seed"])}
        for i, model in enumerate(x["models"]):
            hit = at_best_response(x["P"], i)
            pooled.setdefault(model, []).append(hit)
            row[model] = round(float(hit.mean()), 3)
        by_game.append(row)
    return {
        "pooled": {k: float(np.concatenate(v).mean()) for k, v in pooled.items()},
        "by_game": by_game,
    }


def br_share_self(xs: list) -> float:
    return float(np.concatenate([at_best_response(x["P"], i) for x in xs for i in (0, 1)]).mean())


def leader_follower() -> dict:
    pn, pm = bandit.benchmarks(2)
    best = None
    for lead in np.arange(1.40, 2.60, 0.001):
        f = float(bandit.best_response(np.array([[0.0, lead]]))[0, 0])
        pi = bandit.profits(np.array([[lead, f]]))[0][0]
        if best is None or pi > best[0]:
            best = (pi, lead, f)
    _, lead, f = best
    lo, fo = (lead - pn) / (pm - pn), (f - pn) / (pm - pn)
    return {"opus": round(lo, 3), "haiku45": round(fo, 3), "market": round((lo + fo) / 2, 3)}


def reading(o_moves: bool, r_moves: bool) -> str:
    return {
        (
            False,
            False,
        ): "each model prices as it does against itself; collusion belongs to the model",
        (False, True): "Opus sets the market, and the rival adapts to it",
        (True, False): "the rival sets the market, and Opus adapts to it",
        (True, True): "the pairing changes how both models price",
    }[(o_moves, r_moves)]


if __name__ == "__main__":
    rng = np.random.default_rng(2026)
    g = games()
    for a in ARMS:
        if len(g[a]) != 10:
            print(f"{a}: {len(g[a])} games")
    p.RUNS = list(w2.SUBMITTED)
    h45_brinfo = p.games()["brinfo"]
    base = {
        "opus55": late(w3.opus_games()["baseline"]),
        "haiku55": late(w2.family_games("haiku55", ("baseline",))["baseline"]),
        "haiku45": late(w2.family_games("haiku45", ("baseline", "brinfo"))["baseline"]),
    }
    opus_brinfo = late(w2.family_games("opus55", ("baseline", "brinfo"))["brinfo"])
    own_ = {a: split(g[a]) for a in ARMS}
    mk = {a: market(g[a]) for a in ARMS}

    raw = {
        "1 opus-haiku55: Opus own vs Opus baseline": p.perm_p(
            own_["opus-haiku55"][0], base["opus55"], rng
        ),
        "2 opus-haiku55: Haiku 5.5 own vs Haiku 5.5 baseline": p.perm_p(
            own_["opus-haiku55"][1], base["haiku55"], rng
        ),
        "3 opus-haiku45: Opus own vs Opus baseline": p.perm_p(
            own_["opus-haiku45"][0], base["opus55"], rng
        ),
        "4 opus-haiku45: Haiku 4.5 own vs Haiku 4.5 baseline": p.perm_p(
            own_["opus-haiku45"][1], base["haiku45"], rng
        ),
        "5 brinfo vs opus-haiku45: market": p.perm_p(
            mk["opus-haiku45-brinfo"], mk["opus-haiku45"], rng
        ),
    }
    held = p.holm(raw)
    keys = list(raw)
    effects = [
        own_["opus-haiku55"][0].mean() - base["opus55"].mean(),
        own_["opus-haiku55"][1].mean() - base["haiku55"].mean(),
        own_["opus-haiku45"][0].mean() - base["opus55"].mean(),
        own_["opus-haiku45"][1].mean() - base["haiku45"].mean(),
        mk["opus-haiku45-brinfo"].mean() - mk["opus-haiku45"].mean(),
    ]
    tests = {k: {"p": raw[k], "p_holm": held[k], "effect": float(e)} for k, e in zip(keys, effects)}
    moves = [held[k] < 0.05 for k in keys]
    lowers = moves[4] and effects[4] < 0
    decisions = {
        "opus-haiku55": reading(moves[0], moves[1]),
        "opus-haiku45": reading(moves[2], moves[3]),
        "opus": "Opus's collusion depends on its rival"
        if moves[0] or moves[2]
        else "no detectable sign that Opus's collusion depends on its rival",
        "brinfo": "competitive"
        if lowers and mk["opus-haiku45-brinfo"].mean() < 0.1
        else "lowers prices in the mixed market"
        if lowers
        else "no detectable effect in the mixed market",
    }

    arms = {}
    for a in ARMS:
        o, r = own_[a]
        rb = base[RIVAL[a]]
        arms[a] = {
            "games": len(g[a]),
            "market_index": float(mk[a].mean()),
            "games_above_0.3": int((mk[a] > 0.3).sum()),
            "opus_own": float(o.mean()),
            "rival_own": float(r.mean()),
            "by_game": [
                {
                    "seed": int(x["seed"]),
                    "opus_slot": x["firms"][x["models"].index(OPUS)],
                    "opus": round(float(oi), 3),
                    "rival": round(float(ri), 3),
                }
                for x, oi, ri in sorted(zip(g[a], o, r), key=lambda z: z[0]["seed"])
            ],
            "blocks_of_10": blocks(g[a]),
            "leads": leads(g[a]),
            "market_vs_opus_baseline_p": p.perm_p(mk[a], base["opus55"], rng),
            "market_vs_rival_baseline_p": p.perm_p(mk[a], rb, rng),
        }
    b = g["opus-haiku45-brinfo"]
    o, r = own_["opus-haiku45-brinfo"]
    res = {
        "baselines": {k: {"games": len(v), "index": float(v.mean())} for k, v in base.items()},
        "brinfo_baselines": {
            "opus55": {"games": len(opus_brinfo), "index": float(opus_brinfo.mean())},
            "haiku45": {"games": len(h45_brinfo), "index": float(late(h45_brinfo).mean())},
        },
        "tests": tests,
        "decisions": decisions,
        "arms": arms,
        "exploratory_brinfo": {
            "follow_11_99": follow(b),
            "opus_own_vs_opus_brinfo_p": p.perm_p(o, opus_brinfo, rng),
            "haiku45_own_vs_haiku45_brinfo_p": p.perm_p(r, late(h45_brinfo), rng),
            "leader_follower_benchmark": leader_follower(),
        },
    }
    selfplay = {
        "opus55": w3.opus_games()["baseline"],
        "haiku55": w2.family_games("haiku55", ("baseline",))["baseline"],
        "haiku45": w2.family_games("haiku45", ("baseline", "brinfo"))["baseline"],
        "haiku45_brinfo": h45_brinfo,
    }
    res["beyond_plan"] = {
        "best_response_share": {a: br_shares(g[a]) for a in ARMS},
        "best_response_share_self_play": {k: br_share_self(v) for k, v in selfplay.items()},
        "own_indices_within_0.05": {
            a: int(sum(abs(oi - ri) < 0.05 for oi, ri in zip(*own_[a]))) for a in ARMS
        },
    }
    OUT.mkdir(exist_ok=True)
    (OUT / "wave8.json").write_text(json.dumps(res, indent=1, default=float))
    with open(RUNS / "notes.jsonl", "w") as fh:
        for a in ARMS:
            for x in sorted(g[a], key=lambda z: z["seed"]):
                rr = json.loads((x["folder"] / "results.json").read_text())
                for k, model in zip(x["firms"], x["models"]):
                    for t in NOTE_ROUNDS:
                        ob = rr[k][str(t)]
                        keep = {f: ob.get(f, "") for f in ("observations", "plans", "insights")}
                        row = {
                            "arm": a,
                            "seed": x["seed"],
                            "firm": k,
                            "model": model,
                            "round": t,
                            **keep,
                        }
                        fh.write(json.dumps(row) + "\n")
    print(json.dumps(res, indent=1, default=float))
