"""
Sources and exact rows for check_readme.py: which saved outputs back each README section, plus values that no
output stores, recomputed from the saved games.
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
THEORY = HERE.parent / "theory/out"


def j(name: str, folder: Path = OUT):
    return json.loads((folder / name).read_text())


def sources() -> dict:
    w1, w2, w3, w4 = j("followup.json"), j("wave2.json"), j("wave3.json"), j("wave4.json")
    w5, w6, w7, w8, w9 = (
        j("wave5.json"),
        j("wave6.json"),
        j("wave7.json"),
        j("wave8.json"),
        j("wave9.json"),
    )
    fol, nb, exp = j("following.json"), j("null_band_scale.json"), j("exploratory.json")
    paper = [j("prevention45.json", THEORY), j("frontier_forced_cut.json", THEORY)]
    every = [w1, w2, w3, w4, w5, w6, w7, w8, w9, fol, nb, exp, *paper]
    return {
        "*": [],
        "Follow-up work after the sprint review": every,
        "Contents": [],
        "Files": every,
        "Wave 1": [w1, exp, *paper],
        "Corrections to wave 1": [w1, exp],
        "A scaling error": [nb, *paper],
        "Wave 2": [w2, w1, w3, exp, *paper],
        "Wave 3": [w3, w2, w1, exp, *paper],
        "Wave 4": [w4, nb, w2, w3, w1, exp, *paper],
        "Wave 5": [w5, w3, w2, w4],
        "Wave 6": [w6, w5, w2, w3],
        "Wave 7": [w7, w6, w5, w2, w3],
        "Wave 8": [w8, w2, w3, w1],
        "Raise and cut following": [fol, w8],
        "Wave 9": [w9, fol, w4],
        "Limits that apply": [w3],
        "Running it": [],
    }


def computed() -> dict:
    """Values the README prints that no output stores, recomputed from the saved games, by section."""
    import statistics
    import sys

    import numpy as np

    sys.path[:0] = [str(HERE), str(HERE.parent / "theory")]
    import wave5_results as w5
    import wave6_results as w6
    import wave8_results as w8

    drift = j("wave3.json")["drift_check"]
    kept = w5.games(w5.RUNS / "confirm", "r1b-br-limit", 100)
    path = [float(v) for x in kept for t in range(6) for v in np.round(x["P"][t], 2)]
    by_game = [w6.follow([x], range(11, 100))["within_1pct"] for x in kept]
    held = []
    for x in w8.games()["opus-haiku45-brinfo"]:
        rival = np.round(x["P"][:99, 1 - x["models"].index(w8.OPUS)], 2)
        held.append(float(statistics.mode(rival)))
    return {
        "Wave 3": [float(np.mean(v["index_by_game"])) for v in drift.values()],
        "Wave 5": [w6.follow(kept, range(11, 100))["within_1pct"], *by_game, *path],
        "Wave 8": held,
    }


from decimal import ROUND_HALF_UP, Decimal  # noqa: E402


def r(x: float, d: int = 2, plus: bool = False) -> str:
    """Half-up rounding, Unicode minus, optional plus: the README's number style."""
    q = Decimal(str(x)).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP)
    s = f"{q:+f}" if plus else f"{q:f}"
    if not plus and q == 0:
        s = s.lstrip("-")
    return s.replace("-", "−")


def pct(x: float, d: int = 0, plus: bool = False) -> str:
    s = r(100 * x, d, plus)
    if plus and Decimal(s.replace("−", "-")) == 0:
        s = s.lstrip("+−")
    return s + "%"


def ci(lo: float, hi: float, d: int = 2, plus: bool = False) -> str:
    return f"[{r(lo, d, plus)}, {r(hi, d, plus)}]"


def kof(share: float, n: int) -> str:
    return f"{round(share * n)} of {n}"


def ph(p: float, d: int = 2) -> str:
    """p as the README prints it: < 0.001, three decimals below 0.05, else d decimals."""
    return "< 0.001" if p < 0.001 else (r(p, 3) if p < 0.05 else r(p, d))


def exact_rows() -> list:
    import sys

    sys.path[:0] = [str(HERE), str(HERE.parent / "theory")]
    import followup_results as fr
    import prevention45_results as p

    rows = []
    w1 = j("followup.json")
    R1 = {x["arm"]: x for x in w1["rows"]}
    base1 = R1["baseline"]["index_51_100"]
    rows.append(
        (
            "W1 baseline",
            f"| Baseline (submission) | 20 | {r(base1)} | {kof(R1['baseline']['share_above_0.3'], 20)} | | | |",
        )
    )
    for arm, label in (
        ("brinfo", "Best response, exact (submission)"),
        ("forced10", "Forced Nash round every 10 (submission)"),
    ):
        x = R1[arm]
        rows.append(
            (
                f"W1 {arm}",
                f"| {label} | 10 | {r(x['index_51_100'])} | {kof(x['share_above_0.3'], 10)} | {r(x['index_51_100'] - base1)} | Table 4 | {pct(x['cs_change_pct'] / 100, plus=True)} |",
            )
        )
    for arm, label in (
        ("brinfo_noise", "**Best response, noisy**"),
        ("brinfo_bias", "**Best response, biased +10%**"),
        ("cut10", "**Forced 10% cut every 10**"),
    ):
        x = R1[arm]
        rows.append(
            (
                f"W1 {arm}",
                f"| {label} | 10 | {r(x['index_51_100'])} | {kof(x['share_above_0.3'], 10)} | {r(x['effect'])} {ci(*x['effect_ci'])} | {ph(x['p_holm'], 3)} | {pct(x['cs_change_pct'] / 100, plus=True)} |",
            )
        )
    # per-game deference, wave 1
    p.arm_of, p.RUNS, p.ARMS = fr.arm_of, p.RUNS + [HERE / "runs/games/2_agents"], fr.REF + fr.NEW
    g1 = p.games()
    for arm, label, fmt in (
        ("brinfo", "Best response, exact (submission)", "{} ({}–{} by game) | {} |"),
        ("brinfo_noise", "Best response, noisy", "{} ({}–{}) | {} |"),
        ("brinfo_bias", "Best response, biased +10%", "{} ({}–{}) | {} |"),
    ):
        pooled = fr.deference(g1[arm])
        per = [fr.deference([x])["within_1pct_of_shown"] for x in g1[arm]]
        cell = fmt.format(
            pct(pooled["within_1pct_of_shown"], 1),
            r(100 * min(per), 0),
            pct(max(per)),
            pct(pooled["within_1pct_of_true_best_response"], 1),
        )
        rows.append((f"W1 deference {arm}", f"| {label} | {cell}"))
    rows += scaling_rows() + w2_rows() + w3_rows() + w4_rows() + w5_rows() + w6_rows() + w7_rows()
    return rows + w8_rows() + following_rows() + w9_rows()


def signed_pct(x: float) -> str:
    """A change already in percent: +133%, −46%, 0%."""
    return pct(x / 100, plus=True)


def scaling_rows() -> list:
    nb = j("null_band_scale.json")
    names = {
        "haiku": "Haiku 5.5",
        "fable": "Fable 5.1",
        "haiku45": "Haiku 4.5",
        "haiku45_enforcer": "Haiku 4.5, told to enforce (first instruction)",
        "haiku45_enforcer2": "Haiku 4.5, told to enforce (positive control)",
        "opus55": "Opus 5.5 (wave 4)",
        "sonnet55": "Sonnet 5.5 (wave 4)",
    }
    rows = []
    for key, name in names.items():
        a, b = nb[key]["as_published"], nb[key]["base_scale"]
        assert a["verdict"] == b["verdict"], key
        rows.append(
            (
                f"Scaling {key}",
                f"| {name} | {r(a['punishment'])} | {r(a['null_lo'])} | {r(b['null_lo'])} | {a['verdict']} |",
            )
        )
    return rows


def by_game_ranges(fam: str, arm: str) -> dict:
    """Per-game deference ranges from the saved games, unrounded (exploratory.json stores them to 3 places)."""
    import followup_results as fr
    import wave2_results as w2r

    g = w2r.family_games(fam, ("baseline", arm))[arm]
    per = [fr.deference([x]) for x in g]
    shown = [d["within_1pct_of_shown"] for d in per]
    true = [d["within_1pct_of_true_best_response"] for d in per]
    return {"shown_range": [min(shown), max(shown)], "true_range": [min(true), max(true)]}


def w2_rows() -> list:
    w2, ex = j("wave2.json"), j("exploratory.json")["wave2"]
    ranges = {k: by_game_ranges(*k.split()) for k in ex["deference_by_game"]}
    rows = []
    sb = w2["stage_b"]
    for fam, name in (("opus55", "Opus 5.5"), ("sonnet55", "Sonnet 5.5")):
        s, base = w2["screen"][fam], sb[fam][0]
        lo, hi = min(s["index_by_game"]), max(s["index_by_game"])
        rows.append(
            (
                f"W2 screen {fam}",
                f"| {name} | {s['ends_high']} of {s['games']} | {r(lo, 3)}–{r(hi, 3)} | mean {r(base['index_51_100'])}, {round(base['share_above_0.3'] * 10)} of 10 above 0.3 |",
            )
        )
    hb = w2["bias"][0]
    rows.append(
        (
            "W2 screen haiku55",
            f"| Haiku 5.5 (not screened; baseline for its bias arm) | | | mean {r(hb['index_51_100'])}, {round(hb['share_above_0.3'] * 10)} of 10 above 0.3 |",
        )
    )
    labels = (
        ("Haiku 5.5, +10%", "10 games", "haiku55 brinfo_bias"),
        ("Haiku 4.5, −10%", "the submission's 20", "haiku45 brinfo_biasdown"),
        ("Haiku 4.5 told to enforce, +10%", "10 games", "haiku45enf brinfo_bias"),
    )
    for k, (label, n, dkey) in enumerate(labels):
        base, x = w2["bias"][2 * k], w2["bias"][2 * k + 1]
        rows.append(
            (
                f"W2 bias {label}",
                f"| {label} | {r(base['index_51_100'])} ({n}) | {r(x['index_51_100'])} | {r(x['obedient_index'])} | {kof(x['share_above_0.3'], 10)} | {r(x['effect'])} {ci(*x['effect_ci'])} | {ph(x['p_holm'])} | {signed_pct(x['cs_change_pct'])} | {signed_pct(x['profit_change_pct'])} |",
            )
        )
        d, g = x["deference"], ranges[dkey]
        lo, hi = g["shown_range"]
        tlo, thi = g["true_range"]
        true = pct(d["within_1pct_of_true_best_response"])
        true_cell = true if tlo == thi else f"{true} ({r(100 * tlo, 0)}–{pct(thi)})"
        by = " by game" if k == 0 else ""
        rows.append(
            (
                f"W2 deference {label}",
                f"| {label} | {pct(d['within_1pct_of_shown'])} ({r(100 * lo, 0)}–{pct(hi)}{by}) | {true_cell} |",
            )
        )
    for fam, name in (("sonnet55", "Sonnet 5.5"), ("opus55", "Opus 5.5")):
        x, g = sb[fam][1], ranges[f"{fam} brinfo"]
        d = x["deference"]
        assert pct(d["within_1pct_of_shown"]) == pct(d["within_1pct_of_true_best_response"])
        lo, hi = g["shown_range"]
        rows.append(
            (
                f"W2 deference {fam}",
                f"| {name}, exact | {pct(d['within_1pct_of_shown'])} ({r(100 * lo, 0)}–{pct(hi)}) | the same |",
            )
        )
        base = sb[fam][0]
        rows.append(
            (
                f"W2 stage B {fam} baseline",
                f"| {name} | baseline | {r(base['index_51_100'])} | {kof(base['share_above_0.3'], 10)} | | | |",
            )
        )
        for x, arm in zip(sb[fam][1:], ("best response, exact", "forced 10% cut every 10")):
            rows.append(
                (
                    f"W2 stage B {fam} {arm}",
                    f"| | {arm} | {r(x['index_51_100'])} | {kof(x['share_above_0.3'], 10)} | {r(x['effect'])} {ci(*x['effect_ci'])} | {ph(x['p_holm'])} | {signed_pct(x['cs_change_pct'])} |",
                )
            )
    cr = ex["cut_response"]
    for key, name in (("opus55", "Opus 5.5"), ("haiku45 (wave 1)", "Haiku 4.5")):
        c = cr[key]
        rows.append(
            (
                f"W2 cut response {key}",
                f"| {name} | {r(c['rival_median_change_pct'], 1)}% | {pct(c['rival_share_cutting_5pct'])} |",
            )
        )
    # deference by model: Haiku 4.5's four arms with an exact or biased number
    w1 = j("followup.json")["deference"]
    four = [w1["brinfo"], w1["brinfo_bias"]]
    four += [w2["bias"][3]["deference"], w2["bias"][5]["deference"]]
    shares = [d["within_1pct_of_shown"] for d in four]
    rows.append(
        (
            "W2 by model haiku45",
            f"| Haiku 4.5, exact or biased number (four arms) | {r(100 * min(shares), 0)}–{pct(max(shares))} |",
        )
    )
    for fam, name in (("sonnet55", "Sonnet 5.5"), ("opus55", "Opus 5.5")):
        rows.append(
            (
                f"W2 by model {fam}",
                f"| {name} | {pct(sb[fam][1]['deference']['within_1pct_of_shown'])} |",
            )
        )
    rows.append(
        (
            "W2 by model haiku55",
            f"| Haiku 5.5, biased number only | {pct(w2['bias'][1]['deference']['within_1pct_of_shown'])} |",
        )
    )
    return rows


def w3_rows() -> list:
    w3, w2, ex = j("wave3.json"), j("wave2.json"), j("exploratory.json")["wave3"]
    R = {x["arm"]: x for x in w3["rows"]}
    b = R["baseline"]
    rows = [
        (
            "W3 baseline",
            f"| Baseline | {b['games']} | {r(b['index_51_100'])} | {kof(b['share_above_0.3'], b['games'])} | | | | |",
        )
    ]
    for arm, label in (
        ("forced10", "Forced Nash round every 10"),
        ("forced5", "Forced Nash round every 5"),
    ):
        x = R[arm]
        rows.append(
            (
                f"W3 {arm}",
                f"| {label} | {x['games']} | {r(x['index_51_100'])} | {kof(x['share_above_0.3'], 10)} | {r(x['effect'])} {ci(*x['effect_ci'])} | {ph(x['p_holm'])} | {signed_pct(x['cs_change_pct'])} | {signed_pct(x['profit_change_pct'])} |",
            )
        )
    cut = w2["stage_b"]["opus55"][2]
    rows.append(
        ("W3 remedies cut", f"| 10% cut every 10 rounds (wave 2) | {r(cut['index_51_100'])} |")
    )
    rows.append(("W3 remedies 10", f"| Nash round every 10 | {r(R['forced10']['index_51_100'])} |"))
    rows.append(("W3 remedies 5", f"| Nash round every 5 | {r(R['forced5']['index_51_100'])} |"))
    for arm, label in (("forced10", "Every 10"), ("forced5", "Every 5")):
        rec, rr = ex[arm]["recovery"], R[arm]["rival_response"]
        rows.append(
            (
                f"W3 recovery {arm}",
                f"| {label} | {r(rec['round_after'])} | {r(rec['round_before_next'])} |",
            )
        )
        rows.append(
            (
                f"W3 rival {arm}",
                f"| {label} | {r(rr['rival_median_change_pct'], 1)}% | {pct(rr['rival_share_cutting_5pct'])} |",
            )
        )
    for arm, label in (("forced5", "Every 5"), ("forced10", "Every 10")):
        x, u = R[arm], ex[arm]["without_forced_rounds"]
        rows.append(
            (
                f"W3 unforced {arm}",
                f"| {label} | {r(x['index_51_100'])} | {kof(x['share_above_0.3'], 10)} | {r(u['index_51_100'])} | {u['games_above_0.3']} of 10 |",
            )
        )
    return rows


def w4_rows() -> list:
    w4, nb = j("wave4.json"), j("null_band_scale.json")
    o, s = w4["diagnosis"]["opus55"], w4["diagnosis"]["sonnet55"]
    rows = [
        (
            "W4 punishment",
            f"| Punishment [95% CI] | {r(o['punishment'])} {ci(*o['punishment_ci'], plus=True)} | {r(s['punishment'])} {ci(*s['punishment_ci'], plus=True)} |",
        ),
        (
            "W4 band",
            f"| Null band, lower bound | {r(o['null_lo'])} ({r(nb['opus55']['base_scale']['null_lo'])} on the base scale) | {r(s['null_lo'])} ({r(nb['sonnet55']['base_scale']['null_lo'])} on the base scale) |",
        ),
        (
            "W4 return",
            f"| Return at B+12 | {r(o['return'], plus=True)} | {r(s['return'], plus=True)} |",
        ),
        (
            "W4 cutter",
            f"| The cutter afterwards (B+2..B+12) | {r(o['cutter_gap'])} | {r(s['cutter_gap'])} |",
        ),
        (
            "W4 moves",
            f"| Move rate, median step | {pct(o['move_rate'])}, {pct(o['median_step'], 1)} | {pct(s['move_rate'])}, {pct(s['median_step'], 1)} |",
        ),
        ("W4 verdict", f"| Verdict | {o['verdict']} | {s['verdict']} |"),
    ]
    assert o["verdict"] == o["verdict_plan"] and s["verdict"] == s["verdict_plan"]
    holm, (base, hid) = w4["opus_hidden_holm"], w4["prevention"]
    rows.append(
        (
            "W4 removal",
            f"| Removal: hidden minus control over B+1..B+12, 8 states | {r(o['hidden'])} {ci(*o['hidden_ci'], plus=True)} | {ph(holm['removal'])} | {r(s['hidden'], plus=True)} {ci(*s['hidden_ci'], plus=True)}, p {r(s['hidden_sign_flip_p'])} (secondary, uncorrected) |",
        )
    )
    rows.append(
        (
            "W4 prevention",
            f"| Prevention: index over rounds 51–100, 10 games against Opus's {base['games']} baseline games | {r(hid['index_51_100'])} against {r(base['index_51_100'])}; effect {r(hid['effect'])} {ci(*hid['effect_ci'])}; {kof(hid['share_above_0.3'], 10)} games above 0.3 | {ph(holm['prevention'], 3)} | not run |",
        )
    )
    names = {"haiku45": "Haiku 4.5", "sonnet55": "Sonnet 5.5", "opus55": "Opus 5.5"}
    for fam, name in names.items():
        for arm, label in (
            ("best_response_shown", "best response shown"),
            ("no_number", "no number"),
        ):
            cells = []
            for band in ("below 0.1", "0.1-0.3", "0.3 or above"):
                c = w4["deference_placebo"][fam][arm][band]
                n = f"{c['firm_rounds']:,}"
                cells.append(
                    f"({n})"
                    if c["share_within_1pct"] is None
                    else f"{pct(c['share_within_1pct'])} ({n})"
                )
            first = name if arm == "best_response_shown" else " "
            rows.append(
                (
                    f"W4 placebo {fam} {arm}",
                    f"| {first} | {label} | {' | '.join(cells)} |".replace("|   |", "|  |"),
                )
            )
    return rows


def w5_rows() -> list:
    w5 = j("wave5.json")
    names = {
        "none": "No rule (known)",
        "cut10": "10% cut every 10 (known)",
        "forced10": "Forced Nash every 10 (known)",
        "forced5": "Forced Nash every 5 (known)",
        "brinfo": "Best-response information (known)",
        "hidden": "Hidden rival prices (known)",
    }
    rows, order = [], []
    for x in w5["known"] + w5["screened"]:
        tail = f"| {x['games']} | {r(x['score'], 3)} | {pct(x['max_override_share'])} |"
        head = f"| {names[x['rule']]} |" if x["rule"] in names else f"| `{x['rule']}` |"
        rows.append((f"W5 screen {x['rule']}", (head, tail)))
        order.append((x["score"], head))
    rows.append(("W5 screen sorted by score", [h for _, h in sorted(order)]))
    base = w5["confirmation"]["r1b-br-limit"]["baseline_index"]
    rows.append(("W5 baseline", f"| Baseline | {r(base)} | {r(base)} | 14 of 15 | | | |"))
    for name, c in w5["confirmation"].items():
        verdict = (
            "competitive"
            if c["competitive"]
            else ("lowers prices" if c["lowers_prices"] else "no effect")
        )
        rows.append(
            (
                f"W5 confirm {name}",
                f"| `{name}` | {r(c['primary_index'], 3)} | {r(c['index_all_rounds'], 3)} | {c['games_above_0.3']} of {c['games']} | {r(c['effect'])} | {ph(c['p_holm'])} | {verdict} |",
            )
        )
    return rows


def w6_rows() -> list:
    import wave5_results as w5r
    import wave6_results as w6r

    w6, w2 = j("wave6.json"), j("wave2.json")
    R, T, D = w6["rules"], w6["tests"], w6["decisions"]
    rows = [
        ("W6 baseline", f"| Baseline | {r(w6['baseline']['index'])} | 14 of 15 | | | |"),
        (
            "W6 kept",
            f"| Limit kept (wave 5) | {r(w6['limit_kept']['primary_index'], 3)} | 0 of 10 | | | |",
        ),
    ]
    L, lb, lk = R["w6-lifted"], T["lifted_vs_baseline"], T["lifted_vs_kept"]
    rows.append(
        (
            "W6 lifted",
            f"| `w6-lifted` | {r(L['primary_index'])} | {L['games_above_0.3']} of 10 | {r(lb['effect'])}, p = {r(lb['p_holm'], 3)} | {r(lk['effect'], plus=True)}, p {ph(lk['p_holm']) if lk['p_holm'] < 0.001 else '= ' + r(lk['p_holm'], 3)} | {D['w6-lifted']} |",
        )
    )
    for rule, test in (
        ("w6-limit-no-threat", "limit-no-threat_vs_baseline"),
        ("w6-estimate-threat", "estimate-threat_vs_baseline"),
    ):
        x, t = R[rule], T[test]
        assert t["p_holm"] < 0.001
        rows.append(
            (
                f"W6 {rule}",
                f"| `{rule}` | {r(x['primary_index'], 3)} | {x['games_above_0.3']} of 10 | {r(t['effect'])}, p < 0.001 | | {D[rule]} |",
            )
        )
    # where the lifted games went, from unrounded per-game indices
    lifted = sorted(w5r.score(x, (51, 100))["index"] for x in w5r.games(w6r.RUNS, "w6-lifted", 100))
    groups = [lifted[6:], lifted[3:6], lifted[1:3], lifted[:1]]
    assert (
        [len(g) for g in groups] == [4, 3, 2, 1] and min(groups[0]) > 0.7 and max(groups[2]) < 0.1
    )
    rows += [
        (
            "W6 went back",
            f"| Back to baseline or above | 4 | {r(groups[0][0])}–{r(groups[0][-1])} |",
        ),
        (
            "W6 went between",
            f"| In between: one firm holds a higher price, the other best-responds | 3 | {r(groups[1][0])}–{r(groups[1][-1])} |",
        ),
        (
            "W6 went fell",
            f"| Rose, then fell back near Nash by round 70 | 2 | {r(groups[2][0])} and {r(groups[2][1])} |",
        ),
        ("W6 went never", f"| Never left Nash | 1 | {r(groups[3][0], 3)} |"),
    ]
    e = w6["exploratory"]
    rows += [
        (
            "W6 follow while",
            f"| 11–49, while the limit ran | {pct(e['follow_lifted_11_49']['within_1pct'], 1)} |",
        ),
        (
            "W6 follow after",
            f"| 51–99, after it ended | {pct(e['follow_lifted_would_have_51_99']['within_1pct'])} |",
        ),
        (
            "W6 follow kept",
            f"| 51–99, wave 5's games with the limit kept | {pct(e['follow_kept_51_99']['within_1pct'], 1)} |",
        ),
    ]
    est = w2["stage_b"]["opus55"][1]["index_51_100"]
    nt, et, kept = R["w6-limit-no-threat"], R["w6-estimate-threat"], w6["limit_kept"]
    rows += [
        (
            "W6 2x2 estimate",
            f"| Called an estimate | {r(est)} (wave 2, different wording) | {r(et['primary_index'], 3)} |",
        ),
        (
            "W6 2x2 limit",
            f"| Called a limit | {r(nt['primary_index'], 3)} | {r(kept['primary_index'], 3)} (wave 5) |",
        ),
    ]
    return rows


def w7_rows() -> list:
    w7, w6 = j("wave7.json"), j("wave6.json")
    x, t = w7["w7-estimate-no-threat"], w7["test"]
    assert w7["decision"] == "lowers prices"
    R6 = w6["rules"]
    return [
        ("W7 baseline", f"| Baseline | {r(w7['baseline']['index'])} | 14 of 15 | | |"),
        (
            "W7 rule",
            f"| `w7-estimate-no-threat` | {r(x['primary_index'])} | {x['games_above_0.3']} of 10 | {r(t['effect'])}, p = {r(t['p'], 3)} | lowers prices, not competitive |",
        ),
        (
            "W7 2x2 estimate",
            f"| Called an estimate | {r(x['primary_index'])} (wave 7) | {r(R6['w6-estimate-threat']['primary_index'], 3)} (wave 6) |",
        ),
        (
            "W7 2x2 limit",
            f"| Called a limit | {r(R6['w6-limit-no-threat']['primary_index'], 3)} (wave 6) | {r(w6['limit_kept']['primary_index'], 3)} (wave 5) |",
        ),
    ]


def w8_rows() -> list:
    w8 = j("wave8.json")
    B, BB, A, T = w8["baselines"], w8["brinfo_baselines"], w8["arms"], w8["tests"]
    rows = [
        (
            "W8 design haiku55",
            f"| `opus-haiku55` | Opus 5.5 and Haiku 5.5 | Opus colludes ({r(B['opus55']['index'])}); Haiku 5.5 competes ({r(B['haiku55']['index'])}) |",
        ),
        (
            "W8 design haiku45",
            f"| `opus-haiku45` | Opus 5.5 and Haiku 4.5 | both collude ({r(B['opus55']['index'])} and {r(B['haiku45']['index'])}) |",
        ),
        (
            "W8 design brinfo",
            f"| `opus-haiku45-brinfo` | Opus 5.5 and Haiku 4.5, with best-response information | the information takes Haiku 4.5 to {r(BB['haiku45']['index'])} and leaves Opus at {r(BB['opus55']['index'])} |",
        ),
    ]
    for arm, a in A.items():
        rows.append(
            (
                f"W8 arm {arm}",
                f"| `{arm}` | {r(a['market_index'])} | {a['games_above_0.3']} of {a['games']} | {r(a['opus_own'])} | {r(a['rival_own'])} |",
            )
        )
    t = list(T.values())
    labels = [
        (f"1. `opus-haiku55`: Opus's own against Opus's baseline ({r(B['opus55']['index'])})", 3),
        (
            f"2. `opus-haiku55`: Haiku 5.5's own against Haiku 5.5's baseline ({r(B['haiku55']['index'])})",
            2,
        ),
        ("3. `opus-haiku45`: Opus's own against Opus's baseline", 3),
        (
            f"4. `opus-haiku45`: Haiku 4.5's own against Haiku 4.5's baseline ({r(B['haiku45']['index'])})",
            3,
        ),
        ("5. `opus-haiku45-brinfo` against `opus-haiku45`, market index", 2),
    ]
    for (label, d), x in zip(labels, t):
        rows.append(
            (
                f"W8 test {label[:2]}",
                f"| {label} | {r(x['effect'], plus=True)} | {r(x['p_holm'], d)} |",
            )
        )
    br = w8["beyond_plan"]["best_response_share"]
    for arm, x in br.items():
        rival = next(k for k in x["pooled"] if k != "claude-opus-5-5")
        rows.append(
            (
                f"W8 br {arm}",
                f"| `{arm}` | {pct(x['pooled']['claude-opus-5-5'])} | {pct(x['pooled'][rival])} |",
            )
        )
    rival_base = {
        "opus-haiku55": B["haiku55"]["index"],
        "opus-haiku45": B["haiku45"]["index"],
        "opus-haiku45-brinfo": B["haiku45"]["index"],
    }
    for arm, a in A.items():
        po, pr = a["market_vs_opus_baseline_p"], a["market_vs_rival_baseline_p"]
        po_s = "p < 0.001" if po < 0.001 else f"p = {r(po, 4)}"
        rows.append(
            (
                f"W8 market {arm}",
                f"| `{arm}` | {r(a['market_index'])} | {po_s} | {r(rival_base[arm])}, p = {ph(pr)} |",
            )
        )
        L = a["leads"]
        rows.append(
            (
                f"W8 leads {arm}",
                f"| `{arm}` | {pct(L['opus_moves_followed'])} | {pct(L['rival_moves_followed_by_opus'])} |",
            )
        )
    # coded notes: games (of 10) in which the model's coded notes say so at least once
    coded = [json.loads(line) for line in (HERE / "runs/wave8/notes_coded.jsonl").open()]
    short = {
        "claude-opus-5-5": "Opus 5.5",
        "claude-haiku-5-5": "Haiku 5.5",
        "claude-haiku-4-5": "Haiku 4.5",
    }
    for arm in A:
        for model in (
            "claude-opus-5-5",
            "claude-haiku-5-5" if arm == "opus-haiku55" else "claude-haiku-4-5",
        ):
            cells = []
            for key in ("follows", "undercuts", "raise_to_lead"):
                seeds = {
                    c["seed"] for c in coded if c["arm"] == arm and c["model"] == model and c[key]
                }
                cells.append(str(len(seeds)))
            first = f"| `{arm}` |" if model == "claude-opus-5-5" else "| |"
            rows.append(
                (f"W8 notes {arm} {model}", f"{first} {short[model]} | {' | '.join(cells)} |")
            )
    return rows


def following_rows() -> list:
    sp = j("following.json")["self_play"]
    names = {
        "claude-haiku-4-5": "Haiku 4.5 (20 games)",
        "claude-haiku-5-5": "Haiku 5.5 (10)",
        "claude-sonnet-5-5": "Sonnet 5.5 (10)",
        "claude-opus-5-5": "Opus 5.5 (15)",
    }
    rows = []
    for model, label in names.items():
        x = sp[model]
        more = x["games_raises_followed_more"]
        fisher = (
            r(x["p_fisher_cut_vs_raise"], 1)
            if x["p_fisher_cut_vs_raise"] == 1
            else r(x["p_fisher_cut_vs_raise"], 3)
        )
        sign = "sign p" if model == "claude-haiku-4-5" else "p"
        ps = r(x["p_sign"], 3) if x["p_sign"] < 0.05 else r(x["p_sign"], 2)
        rows.append(
            (
                f"Following {model}",
                f"| {label} | {pct(x['follow_raise'])} | {pct(x['follow_cut'])} | {pct(x['move_after_quiet_round'])} | {fisher} | {more} of {x['eligible_games']} ({sign} = {ps}) |",
            )
        )
    return rows


def w9_rows() -> list:
    w9 = j("wave9.json")
    o, h = w9["opus55"], w9["haiku45"]
    return [
        (
            "W9 response",
            f"| Raise response [95% CI] | {r(o['response'], plus=True)} {ci(*o['response_ci'], plus=True)} | {r(h['response'], plus=True)} {ci(*h['response_ci'], plus=True)} |",
        ),
        (
            "W9 band",
            f"| Null band | {r(o['band_lower'], plus=True)} to {r(o['band_upper'], plus=True)} | {r(h['band_lower'], plus=True)} to {r(h['band_upper'], plus=True)} |",
        ),
        (
            "W9 full",
            f"| Full following, for comparison | {r(o['full_following'])} | {r(h['full_following'])} |",
        ),
        (
            "W9 persistence",
            f"| Persistence at B+12 | {r(o['persistence'], plus=True)} | {r(h['persistence'], plus=True)} |",
        ),
        ("W9 verdict", f"| Verdict | {o['verdict']} | {h['verdict']} |"),
        (
            "W9 raises in B+2",
            f"| Raises its own price this round | {o['a_raises_in_b2']} | {h['a_raises_in_b2']} |",
        ),
    ]
