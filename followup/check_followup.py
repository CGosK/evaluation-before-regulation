"""
Checks the numbers in FOLLOWUP_NOTE.md and CLAIMS_STATUS.md against the follow-up's saved outputs (out/*.json),
in the style of theory/check_paper.py. Each check formats a value the way the docs print it and looks for that
exact string. Numbers that no output file stores are recomputed here from the saved games. A permutation
p-value recomputed here is checked within its sampling error, not to the digit.

Not covered, and listed at the end: counts read by hand from the agents' notes, design constants (rounds,
games per arm, sizes fixed in the plans), and numbers quoted from the paper's text. Every other number in the
two docs that no check matched is printed for review.

Usage:  uv run --extra analysis python followup/check_followup.py
Exits 1 if any check fails.
"""

import json
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "theory")]
OUT = HERE / "out"
from bandit import benchmarks  # noqa: E402

benchmarks_pn, benchmarks_pm = (float(v) for v in benchmarks(2))
NOTE = (HERE / "FOLLOWUP_NOTE.md").read_text().replace("\n", " ")
CLAIMS = (HERE / "CLAIMS_STATUS.md").read_text().replace("\n", " ")
DOCS = {"note": NOTE, "claims": CLAIMS}
results, matched = [], {"note": [], "claims": []}


def f(x: float, d: int = 2, plus: bool = False) -> str:
    s = f"{x:+.{d}f}" if plus else f"{x:.{d}f}"
    s = s.replace("-", "−")
    return s.replace("−0.00", "0.00") if not plus else s


def pc(x: float, d: int = 0) -> str:
    return f"{100 * x:.{d}f}%"


def check(label: str, text: str, doc: str = "note"):
    ok = text in DOCS[doc]
    results.append(ok)
    if ok:
        matched[doc].append(text)
    print(f"{'ok  ' if ok else 'FAIL'} [{doc}] {label}: {text}")


def check_true(label: str, ok: bool, detail: str = ""):
    results.append(bool(ok))
    print(f"{'ok  ' if ok else 'FAIL'} [data] {label}{': ' + detail if detail else ''}")


def approx(label: str, pattern: str, value: float, tol: float, doc: str = "note"):
    """The doc's number after `pattern` is within tol of the recomputed value."""
    m = re.search(pattern + r"\s*(\d+(?:\.\d+)?)", DOCS[doc])
    ok = bool(m) and abs(float(m.group(1)) - value) <= tol
    results.append(ok)
    if m:
        matched[doc].append(m.group(0))
    shown = m.group(1) if m else "not found"
    print(
        f"{'ok  ' if ok else 'FAIL'} [{doc}] {label}: printed {shown}, recomputed {value:.4f} (±{tol})"
    )


def load(name: str):
    return json.loads((OUT / name).read_text())


def late(xs):
    import prevention45_results as p

    return np.array([float(p.index(x)[p.LATE].mean()) for x in xs])


# ---------------------------------------------------------------- wave 1 (followup.json) and the placebo (wave 4)
w1 = load("followup.json")
row1 = {r["arm"]: r for r in w1["rows"]}
dfr = w1["deference"]
check(
    "W1 deference to the exact number",
    f"in {pc(dfr['brinfo']['within_1pct_of_shown'])} of firm-rounds",
)
check(
    "W1 +10%: shown number set",
    f"in {pc(dfr['brinfo_bias']['within_1pct_of_shown'])} of firm-rounds",
)
check_true(
    "W1 +10%: true best response never set",
    dfr["brinfo_bias"]["within_1pct_of_true_best_response"] == 0,
)
check("W1 obedience predicts", f"a market at {f(w1['obedient_index_for_bias'])}")
bias_games = [g["index_51_100"] for g in w1["games"]["brinfo_bias"]]
check("W1 +10% games range", f"settled at {f(min(bias_games))}–{f(max(bias_games))}")
check("W1 +10% p", f"p = {row1['brinfo_bias']['p_permutation']:.3f}")
check("W1 noise index", f"with an index of {f(row1['brinfo_noise']['index_51_100'])}")
w4 = load("wave4.json")
pl = w4["deference_placebo"]["haiku45"]
check(
    "W4 placebo, number shown",
    f"{pc(pl['best_response_shown']['below 0.1']['share_within_1pct'])} of the time",
)
check(
    "W4 placebo, no number",
    f"and {pc(pl['no_number']['below 0.1']['share_within_1pct'])} without it",
)

# ---------------------------------------------------------------- wave 2 (wave2.json)
w2j = load("wave2.json")
bias = {(r["family"], r["arm"]): r for r in w2j["bias"]}
down = bias[("haiku45", "brinfo_biasdown")]
check("W2 −10%: set", f"set it in {pc(down['deference']['within_1pct_of_shown'])} of firm-rounds")
low = sorted(v for v in down["index_by_game"] if abs(v - down["obedient_index"]) < 0.03)
check(
    "W2 −10%: games near obedience",
    f"{['Six', 'Seven'][len(low) - 6] if 6 <= len(low) <= 7 else len(low)} of the 10",
)
check("W2 −10%: their range", f"settled at {f(max(low))} to {f(min(low))}")
check("W2 −10%: obedience", f"against the {f(down['obedient_index'])} that obedience")
check("W2 −10%: profit", f"Profit fell {pc(-down['profit_change_pct'] / 100)}")
enf = bias[("haiku45enf", "brinfo_bias")]
check(
    "W2 enforcer: set", f"number in {pc(enf['deference']['within_1pct_of_shown'])} of firm-rounds"
)
h55 = bias[("haiku55", "brinfo_bias")]
check(
    "W2 Haiku 5.5: set",
    f"set it in {pc(h55['deference']['within_1pct_of_shown'])}, and its index stayed at {f(h55['index_51_100'])}",
)
sc = w2j["screen"]
check("W2 screen Opus", f"Opus 5.5 passed with {sc['opus55']['ends_high']} of 5")
check("W2 screen Sonnet", f"Sonnet 5.5 passed with {sc['sonnet55']['ends_high']} of 5")
sb = {fam: {r["arm"]: r for r in rows} for fam, rows in w2j["stage_b"].items()}
check(
    "W2 baselines",
    f"Opus averages {f(sb['opus55']['baseline']['index_51_100'])} and Sonnet {f(sb['sonnet55']['baseline']['index_51_100'])}",
)
usage2 = [
    json.loads(line)
    for line in (HERE / "runs/wave2/usage.jsonl").read_text().splitlines()
    if line.strip()
]
opus_t = [u.get("thinking_tokens") or 0 for u in usage2 if u.get("model") == "claude-opus-5-5"]
pos = [t for t in opus_t if t > 0]
check(
    "W2 Opus thinking", f"on {pc(len(pos) / len(opus_t))} of calls (median {int(np.median(pos))})"
)
names = {"brinfo": "best response, exact", "cut10": "forced 10% cut every 10"}
for fam, model in (("opus55", "Opus 5.5"), ("sonnet55", "Sonnet 5.5")):
    b = sb[fam]["baseline"]
    check(
        f"W2 table {fam} baseline",
        f"| {f(b['index_51_100'])} | {round(10 * b['share_above_0.3'])} of 10 |",
    )
    for arm in ("brinfo", "cut10"):
        r = sb[fam][arm]
        lo, hi = r["effect_ci"]
        p_h = f"{r['p_holm']:.3f}" if r["p_holm"] < 0.05 else f"{r['p_holm']:.2f}"
        check(
            f"W2 table {fam} {arm}",
            f"| {names[arm]} | {f(r['index_51_100'])} | {round(10 * r['share_above_0.3'])} of 10 | "
            f"{f(r['effect'])} [{f(lo)}, {f(hi)}] | {p_h} |",
        )
check(
    "W2 Haiku 4.5 remedies",
    f"from {f(row1['baseline']['index_51_100'])} to {f(row1['brinfo']['index_51_100'])} and {f(row1['cut10']['index_51_100'])}",
)
check(
    "W2 Opus CI bounds",
    f"drops of up to {f(-sb['opus55']['brinfo']['effect_ci'][0])} and {f(-sb['opus55']['cut10']['effect_ci'][0])}",
)
check(
    "W2 Opus deference",
    f"in {pc(sb['opus55']['brinfo']['deference']['within_1pct_of_shown'])} of firm-rounds, against {pc(dfr['brinfo']['within_1pct_of_shown'])} for Haiku 4.5",
)
w3j = load("wave3.json")
check(
    "W3 notes mention the estimate (Opus)",
    f"in {pc(w3j['notes']['opus55']['share_mentioning'], 1)} of them",
)
check("W2 Sonnet holm", f"(p = {sb['sonnet55']['brinfo']['p_holm']:.3f} each)")
check(
    "W2 Sonnet levels",
    f"from {f(sb['sonnet55']['baseline']['index_51_100'])} to {f(sb['sonnet55']['brinfo']['index_51_100'])}, and the cut to {f(sb['sonnet55']['cut10']['index_51_100'])}",
)
check(
    "W2 Sonnet deference",
    f"in {pc(sb['sonnet55']['brinfo']['deference']['within_1pct_of_shown'])} of firm-rounds",
)

import followup_results as fr  # noqa: E402
import prevention45_results as p  # noqa: E402
import wave2_results as w2  # noqa: E402

son = w2.family_games("sonnet55", ("baseline", "brinfo"))["brinfo"]
per = [(fr.deference([x])["within_1pct_of_shown"], float(p.index(x)[p.LATE].mean())) for x in son]
heavy = [(d, v) for d, v in per if d >= 0.45]
word = ["three", "four", "five"][len(heavy) - 3]
dmin, dmax = pc(min(d for d, _ in heavy)), pc(max(d for d, _ in heavy))
vmin, vmax = f(min(v for _, v in heavy)), f(max(v for _, v in heavy))
check(
    "W2 Sonnet heavy deferrers",
    f"The {word} games that set it in {dmin[:-1]}–{dmax} of firm-rounds end at {vmin} to {vmax}",
)

# ---------------------------------------------------------------- wave 3 (wave3.json, plus recomputed extras)
r3 = {r["arm"]: r for r in w3j["rows"]}
for arm, lead in (("forced10", "falls from 0.76 to"), ("forced5", "it falls to")):
    r = r3[arm]
    lo, hi = r["effect_ci"]
    check(f"W3 {arm} index", f"{lead} {f(r['index_51_100'])}")
    check(f"W3 {arm} effect", f"{f(r['effect'])} [{f(lo)}, {f(hi)}]")
check("W3 forced10 p", f"p = {r3['forced10']['p_holm']:.3f})")
check_true("W3 forced5 p < 0.001", r3["forced5"]["p_holm"] < 0.001, f"{r3['forced5']['p_holm']}")
check(
    "W3 forced10 above 0.3",
    f"with {round(10 * r3['forced10']['share_above_0.3'])} of 10 games still above 0.3",
)
check("W3 forced5 above 0.3", f"with {round(10 * r3['forced5']['share_above_0.3'])} of 10 above")
check("W3 Haiku 4.5 forced10", f"took Haiku 4.5 to {f(row1['forced10']['index_51_100'])}")

import prevention45_results as p  # noqa: E402
import wave2_results as w2  # noqa: E402
import wave3_results as w3  # noqa: E402

g3 = w3.opus_games()
paths = {a: np.array([p.index(x)[:100] for x in g3[a]]) for a in ("forced10", "forced5")}
blocks = {a: min(paths[a][:, i : i + 10].mean() for i in range(0, 100, 10)) for a in paths}
check("W3 lowest blocks", f"the lowest are {f(blocks['forced10'])} and {f(blocks['forced5'])}")
P10 = paths["forced10"].mean(0)
after = np.mean([P10[t] for t in range(60, 91, 10)])  # round t+1 is index t (0-based)
before = np.mean([P10[t + 8] for t in range(60, 91, 10)])
check(
    "W3 sawtooth",
    f"averages {f(after)} the round after a forced round and {f(before)} just before the next",
)
unf = []
for x in g3["forced5"]:
    idx = p.index(x)[50:100]
    keep = ~x["forced"][50:100].any(1)
    unf.append(float(idx[keep].mean()))
check(
    "W3 every-5 without forced rounds",
    f"without them its index is {f(np.mean(unf))}, with {sum(v > 0.3 for v in unf)} of 10 games above 0.3",
)
forced5_rounds = int(g3["forced5"][0]["forced"][:100].any(1).sum())
check("W3 every-5 forced rounds", f"overridden in {forced5_rounds} of the 100 rounds")
rng = np.random.default_rng(2026)
cut10 = late(w2.family_games("opus55", ("baseline", "brinfo", "cut10"))["cut10"])
approx(
    "W3 size (cut vs Nash round)",
    r"every 10 against wave 2's 10% cut gives p =",
    p.perm_p(late(g3["forced10"]), cut10, rng),
    0.003,
)
approx(
    "W3 frequency (5 vs 10)",
    r"every 5 rounds against every 10 gives p =",
    p.perm_p(late(g3["forced5"]), late(g3["forced10"]), rng),
    0.006,
)

# ---------------------------------------------------------------- wave 4 (wave4.json, null_band_scale.json, paper)
dg = w4["diagnosis"]
check("W4 Opus punishment", f"Opus's mean punishment, {f(dg['opus55']['punishment'])}")
check("W4 Opus band, as first computed", f"Opus's lower bound was {f(dg['opus55']['null_lo'])}")
check("W4 Opus CI", f"interval reaches {f(dg['opus55']['punishment_ci'][0])}")
nb = load("null_band_scale.json")
check(
    "W4 base-scale band",
    f"whose lower bound is {f(nb['opus55']['base_scale']['null_lo'])} on the base demand scale",
)
check_true(
    "W4/paper verdicts unchanged on the base scale",
    all(v["as_published"]["verdict"] == v["base_scale"]["verdict"] for v in nb.values()),
)
check("W4 Sonnet punishment", f"Sonnet's mean punishment is {f(dg['sonnet55']['punishment'])}")
hp = next(r for r in w4["prevention"] if r["arm"] == "hidden")
check(
    "W4 hidden prevention",
    f"fell from 0.76 to {f(hp['index_51_100'])} (effect {f(hp['effect'])} [{f(hp['effect_ci'][0])}, {f(hp['effect_ci'][1])}], Holm p = {w4['opus_hidden_holm']['prevention']:.3f})",
)
check(
    "W4 hidden prevention above 0.3",
    f"with {round(10 * hp['share_above_0.3'])} of 10 games still above 0.3",
)
check(
    "W4 hidden removal",
    f"it changed nothing ({f(dg['opus55']['hidden'])}, p = {dg['opus55']['hidden_sign_flip_p']:.2f})",
)
paper = {
    r["arm"]: r
    for r in json.loads((HERE.parent / "theory/out/prevention45.json").read_text())["rows"]
}
check(
    "Paper Haiku 4.5 hidden",
    f"{f(paper['hidden']['index_51_100'])} against {f(paper['baseline']['index_51_100'])}, p = {paper['hidden']['p_permutation']:.3f} before correction and {paper['hidden']['p_holm']:.2f} after",
)
fo = load("following.json")["self_play"]
o, h45, h55s = fo["claude-opus-5-5"], fo["claude-haiku-4-5"], fo["claude-haiku-5-5"]
check(
    "Following Opus",
    f"raise {pc(o['follow_raise'])} of the time and a cut {pc(o['follow_cut'])} (Fisher p = {o['p_fisher_cut_vs_raise']:.3f})",
)
check(
    "Following Opus by game",
    f"raises more in {o['games_raises_followed_more']} of {o['eligible_games']} games",
)
check("Following Haiku 4.5", f"{pc(h45['follow_raise'])} and {pc(h45['follow_cut'])}")
check("Following Haiku 5.5", f"({pc(h55s['follow_raise'])} against {pc(h55s['follow_cut'])})")

# ---------------------------------------------------------------- wave 5 (wave5.json, plus recomputed extras)
import wave5_results as w5  # noqa: E402
import wave6_results as w6  # noqa: E402

c5 = load("wave5.json")["confirmation"]
lim, hid = c5["r1b-br-limit"], c5["r1d-hidden-br-trial"]
base = r3["baseline"]
check(
    "W5 table baseline",
    f"| Baseline (15 games) | {f(base['index_51_100'])} | {round(15 * base['share_above_0.3'])} of 15 |",
)
check(
    "W5 table limit",
    f"| {f(lim['primary_index'])} | {lim['games_above_0.3']} of 10 | {f(lim['effect'])} | < 0.001 |",
)
check(
    "W5 table hidden rule",
    f"| {f(hid['primary_index'])} | {hid['games_above_0.3']} of 10 | {f(hid['effect'])} | < 0.001 |",
)
check_true("W5 both rules p < 0.001", lim["p_holm"] < 0.001 and hid["p_holm"] < 0.001)
check_true(
    "W5 all 20 games below every baseline game",
    max(lim["primary_by_game"] + hid["primary_by_game"]) < min(r3["baseline"]["index_by_game"]),
)
check("W5 best hand-picked", f"every 5 rounds, reached {f(r3['forced5']['index_51_100'])}")
kept = w5.games(w5.RUNS / "confirm", "r1b-br-limit", 100)
fol = w6.follow(kept, range(11, 100))["within_1pct"]
check(
    "W5 limit followed",
    f"in {pc(fol, 1)} of firm-rounds, and the replacement fired only {int(sum(x['forced'].any(1).sum() for x in kept))} times",
)
check_true(
    "W5 prices at 1.48 by round 6", all(np.allclose(np.round(x["P"][5], 2), 1.48) for x in kept)
)
check("W5 1.48 by round 6 (text)", "prices reached 1.48, within a cent of Nash, by round 6")
trial = w5.games(w5.RUNS / "confirm", "r1d-hidden-br-trial", 100)
check(
    "W5 second rule overrides",
    f"up to {max(int(x['forced'][50:100].any(1).sum()) for x in trial)} of a game's 50 scored rounds",
)
check(
    "W5 second rule all rounds",
    f"gives {hid['index_all_rounds']:.3f} rather than {f(hid['primary_index'])}",
)

# ---------------------------------------------------------------- wave 6 (wave6.json, plus recomputed extras)
w6j = load("wave6.json")
R6, T6 = w6j["rules"], w6j["tests"]
check(
    "W6 table kept", f"| Limit kept (wave 5) | {f(w6j['limit_kept']['primary_index'])} | 0 of 10 |"
)
li = R6["w6-lifted"]
check(
    "W6 table lifted",
    f"| {f(li['primary_index'])} | {li['games_above_0.3']} of 10 | {f(T6['lifted_vs_baseline']['effect'])}, p = {T6['lifted_vs_baseline']['p_holm']:.3f} | {f(T6['lifted_vs_kept']['effect'], plus=True)}, p < 0.001 |",
)
check_true("W6 lifted vs kept p < 0.001", T6["lifted_vs_kept"]["p_holm"] < 0.001)
nt, et = R6["w6-limit-no-threat"], R6["w6-estimate-threat"]
check(
    "W6 table no threat",
    f"| {f(nt['primary_index'])} | {nt['games_above_0.3']} of 10 | {f(T6['limit-no-threat_vs_baseline']['effect'])}, p < 0.001 |",
)
check(
    "W6 table estimate threat",
    f"| {f(et['primary_index'])} | {et['games_above_0.3']} of 10 | {f(T6['estimate-threat_vs_baseline']['effect'])}, p < 0.001 |",
)
pg = li["primary_by_game"]
high, mid, back = (
    [v for v in pg if v >= 0.7],
    [v for v in pg if 0.2 <= v < 0.4],
    [v for v in pg if 0.03 < v < 0.1],
)
check(
    "W6 lifted: back to baseline",
    f"{['Three', 'Four', 'Five'][len(high) - 3]} went back to baseline levels or above ({f(min(high))}–{f(max(high))})",
)
check("W6 lifted: in between", f"{['Two', 'Three', 'Four'][len(mid) - 2]} settled in between")
check(
    "W6 lifted: fell back", f"{['One', 'Two', 'Three'][len(back) - 1]} rose and fell back to Nash"
)
check("W6 all the way back (closing)", f"all the way in {len(high)} of 10 games")
lifted = w5.games(w6.RUNS, "w6-lifted", 100)
raised = sum(bool((np.log(x["P"][50] / x["P"][49]) > 0.01).any()) for x in lifted)
check("W6 raised in round 51", f"In {raised} of 10 games, a firm raised its price in round 51")
nothreat = w5.games(w6.RUNS, "w6-limit-no-threat", 100)
check_true(
    "W6 no threat: 1.48 by round 6",
    all(np.allclose(np.round(x["P"][5], 2), 1.48) for x in nothreat),
)
check("W6 no threat 1.48 (text)", "prices at 1.48 by round 6")
ex6 = w6j["exploratory"]
check_true(
    "W6 no threat followed in every firm-round", ex6["follow_no_threat_11_99"]["within_1pct"] == 1.0
)
check(
    "W6 estimate threat followed",
    f"set the estimate in {pc(ex6['follow_estimate_threat_11_99']['within_1pct'], 1)} of firm-rounds",
)
check("W6 estimate threat overrides", f"fired {sum(et['overrides'])} times")
check(
    "W6 kept-limit overrides",
    f"under wave 5's limit it fired {int(sum(x['forced'].any(1).sum() for x in kept))} times",
)
check(
    "W2 estimate followed (for comparison)",
    f"Wave 2's version was set in {pc(sb['opus55']['brinfo']['deference']['within_1pct_of_shown'])}",
)

# ---------------------------------------------------------------- wave 7 (wave7.json, plus recomputed extras)
import wave7_results as w7  # noqa: E402

w7j = load("wave7.json")
r7 = w7j["w7-estimate-no-threat"]
check(
    "W7 index",
    f"Opus's index was {f(r7['primary_index'])}, and {r7['games_above_0.3']} of 10 games",
)
check("W7 test", f"below baseline ({f(w7j['test']['effect'])}, p = {w7j['test']['p']:.3f})")
check("W7 2x2", f"| Called an estimate | {f(r7['primary_index'])} | {f(et['primary_index'])} |")
check(
    "W7 2x2 limit row", f"| Called a limit | {f(nt['primary_index'])} | {f(lim['primary_index'])} |"
)
check("W7 follow", f"in {pc(w7j['exploratory']['follow_11_99']['within_1pct'])} of firm-rounds")
xs7 = sorted(w5.games(w7.RUNS, w7.RULE, 100), key=lambda x: x["seed"])
idx7 = np.array([w5.score(x, w6.WINDOW)["index"] for x in xs7])
fol7 = np.array([w7.follow([x])["within_1pct"] for x in xs7])
least = np.argsort(fol7)[:3]
check("W7 least-following games", f"({f(idx7[least].min())}–{f(idx7[least].max())})")
check_true(
    "W7 the least-following three have the highest indices",
    set(least) == set(np.argsort(idx7)[-3:]),
)
most = int(np.argmax(fol7))
check_true(
    "W7 the game that followed throughout sat at Nash",
    fol7[most] > 0.95 and idx7[most] < 0.05,
    f"follow {fol7[most]:.2f}, index {idx7[most]:.3f}",
)
ob = late(w2.family_games("opus55", ("baseline", "brinfo"))["brinfo"])
approx(
    "W7 against wave 2's estimate",
    r"isn't significant \(p =",
    p.perm_p(idx7, ob, np.random.default_rng(2026)),
    0.006,
)
lb = {g["seed"]: g for g in w7j["exploratory"]["late_by_game"]}
r100 = sorted(lb[xs7[i]["seed"]]["r100"] for i in least)
check("W7 late fall", f"dropped to {f(r100[0])}–{f(r100[-1])} by round 100")
bl = r7["blocks_of_10"]
check("W7 blocks", f"from {f(bl[5])} in rounds 51–60 to {f(bl[9])} in rounds 91–100")

# ---------------------------------------------------------------- wave 8 (wave8.json, notes_coded.jsonl)
w8j = load("wave8.json")
A8, T8 = w8j["arms"], w8j["tests"]
k = list(T8)
for key, label in (
    ("opus-haiku55", "Opus and Haiku 5.5 (0.15 against itself)"),
    ("opus-haiku45", "Opus and Haiku 4.5 (1.09 against itself)"),
    ("opus-haiku45-brinfo", "Opus and Haiku 4.5, best-response information"),
):
    a = A8[key]
    check(
        f"W8 table {key}",
        f"| {label} | {f(a['market_index'])} | {f(a['opus_own'])} | {f(a['rival_own'])} |",
    )
check(
    "W8 Opus falls",
    f"by {f(-T8[k[0]]['effect'])} and {f(-T8[k[2]]['effect'])} (Holm p = {T8[k[0]]['p_holm']:.3f} and {T8[k[2]]['p_holm']:.3f})",
)
check("W8 Haiku 5.5 unchanged", f"For Haiku 5.5, p = {T8[k[1]]['p_holm']:.2f}")
check(
    "W8 Haiku 4.5",
    f"fell from {f(w8j['baselines']['haiku45']['index'])} to {f(A8['opus-haiku45']['rival_own'])}, but its baseline is so spread that the drop misses after correction (Holm p = {T8[k[3]]['p_holm']:.3f})",
)
check(
    "W8 remedy",
    f"{f(A8['opus-haiku45-brinfo']['market_index'])} against {f(A8['opus-haiku45']['market_index'])} (Holm p = {T8[k[4]]['p_holm']:.2f})",
)
bp = w8j["beyond_plan"]
brs = {a: v["pooled"] for a, v in bp["best_response_share"].items()}
check(
    "W8 BR shares",
    f"in {pc(brs['opus-haiku55']['claude-haiku-5-5'])} of firm-rounds, with no number shown ({pc(bp['best_response_share_self_play']['haiku55'])} against itself)",
)
fl8 = w8j["exploratory_brinfo"]["follow_11_99"]
check(
    "W8 Haiku 4.5 set the estimate",
    f"Haiku 4.5 set the estimate in {pc(fl8['claude-haiku-4-5']['within_1pct'])}",
)
check(
    "W8 Opus did neither",
    f"({pc(brs['opus-haiku55']['claude-opus-5-5'])} and {pc(fl8['claude-opus-5-5']['within_1pct'])})",
)
lf = w8j["exploratory_brinfo"]["leader_follower_benchmark"]
check(
    "W8 Haiku 4.5 own brinfo",
    f"took Haiku 4.5's own markets to {f(w8j['brinfo_baselines']['haiku45']['index'])}",
)
check(
    "W8 matched prices",
    f"matched prices in {bp['own_indices_within_0.05']['opus-haiku45']} of 10 games",
)
coded = [
    json.loads(line)
    for line in (HERE / "runs/wave8/notes_coded.jsonl").read_text().splitlines()
    if line.strip()
]
lead = {}
for c in coded:
    if c["raise_to_lead"]:
        lead.setdefault((c["arm"], c["model"] == "claude-opus-5-5"), set()).add(c["seed"])
opus_lead = [len(lead.get((a, True), ())) for a in A8]
rival_lead = [len(lead.get((a, False), ())) for a in A8]
check("W8 Opus tries to lead", f"{min(opus_lead)}–{max(opus_lead)} of 10 Opus firms plan to raise")
check("W8 rivals rarely", f"At most {max(rival_lead)} of 10 of their rivals do")

# ---------------------------------------------------------------- wave 9 (wave9.json)
w9 = load("wave9.json")
for fam, col in (("opus55", 0), ("haiku45", 1)):
    v = w9[fam]
    check(
        f"W9 {fam} response",
        f"| {f(w9['opus55']['response'], plus=True)} | {f(w9['haiku45']['response'], plus=True)} |",
    )
    check(f"W9 {fam} band", f"{f(v['band_lower'])} to {f(v['band_upper'], plus=True)}")
    check(f"W9 {fam} verdict", v["verdict"])
check("W9 between", f"the two don't differ (p = {w9['between']['p']:.2f})")
check_true(
    "W9 reading", w9["reading"] == "the saved games' asymmetry doesn't show up in the diagnostic"
)
small = 0
for path in sorted((HERE / "runs/wave9/frontier/opus55").glob("*_raise.jsonl")):
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    settle = [
        json.loads(line)
        for line in Path(str(path).replace("_raise", "_settle")).read_text().splitlines()
    ]
    pb = next(
        r["price"]
        for r in settle
        if r["firm"] == "Firm B" and r["round"] == max(s["round"] for s in settle)
    )
    forced = next(r for r in rows if r["forced"])
    small += forced["price"] / pb - 1 < 0.01
check(
    "W9 Opus states with no visible raise",
    f"In {['one', 'two', 'three'][small - 1]} Opus states, B's model was already cutting",
)

# ---------------------------------------------------------------- the remedy-by-model table and Figure 8
import bandit  # noqa: E402

grid = np.arange(1.40, 2.60, 0.001)
fol = [float(bandit.best_response(np.array([[0.0, g]]))[0, 0]) for g in grid]
lead_i = int(np.argmax([bandit.profits(np.array([[g, b]]))[0][0] for g, b in zip(grid, fol)]))
lf_full = tuple(
    (v - benchmarks_pn) / (benchmarks_pm - benchmarks_pn) for v in (grid[lead_i], fol[lead_i])
)
mat = [
    (
        "None (baseline)",
        "",
        f"{f(row1['baseline']['index_51_100'])} (paper)",
        f(sb["sonnet55"]["baseline"]["index_51_100"]),
        f(base["index_51_100"]),
    ),
    (
        "Best-response information",
        "paper",
        f"{f(row1['brinfo']['index_51_100'])} (paper)",
        f(sb["sonnet55"]["brinfo"]["index_51_100"]),
        f(sb["opus55"]["brinfo"]["index_51_100"]),
    ),
    (
        "10% cut every 10 rounds",
        "paper's simulations",
        f"{f(row1['cut10']['index_51_100'])} (wave 1)",
        f(sb["sonnet55"]["cut10"]["index_51_100"]),
        f(sb["opus55"]["cut10"]["index_51_100"]),
    ),
    (
        "Forced Nash round every 10",
        "paper",
        f"{f(row1['forced10']['index_51_100'])} (paper)",
        "–",
        f(r3["forced10"]["index_51_100"]),
    ),
    ("Forced Nash round every 5", "wave 3", "–", "–", f(r3["forced5"]["index_51_100"])),
    (
        "Hidden rival prices",
        "paper",
        f"{f(paper['hidden']['index_51_100'])} (paper)",
        "–",
        f(hp["index_51_100"]),
    ),
    ("Hidden prices, best-price trials", "wave 5 search", "–", "–", f(hid["primary_index"])),
    ("Best-response price limit", "wave 5 search", "–", "–", f(lim["primary_index"])),
    ("The limit, lifted after round 50", "wave 6", "–", "–", f(li["primary_index"])),
    ("The limit, no threat", "wave 6", "–", "–", f(nt["primary_index"])),
    ("The number as an estimate, with the threat", "wave 6", "–", "–", f(et["primary_index"])),
    ("The number as an estimate, no threat", "wave 7", "–", "–", f(r7["primary_index"])),
]
for row in mat:
    check(f"Matrix: {row[0]}", ("| " + " | ".join(row) + " |").replace("|  |", "| |"))
check("Matrix: Haiku 5.5 note", f"Haiku 5.5 competes without a remedy ({f(h55['index_51_100'])})")
check(
    "Fig 8 caption",
    f"Opus at {f(lf_full[0])} and its rival at {f(lf_full[1])}, a market index of {f(sum(lf_full) / 2)}",
)
check(
    "W8 markets near the leader-follower outcome",
    f"best-response information both ended near {f(lf['market'])}",
)
check("Base-market prices", f"those prices are {benchmarks_pn:.3f} and {benchmarks_pm:.3f}")

# ---------------------------------------------------------------- limits
dc = w3j["drift_check"]
check(
    "Limits: Opus baseline pools two waves",
    f"({np.mean(dc['wave3_baseline']['index_by_game']):.3f} against {np.mean(dc['wave2_baseline']['index_by_game']):.3f})",
)

# ---------------------------------------------------------------- CLAIMS_STATUS.md
check(
    "Claims: Opus info and forced10",
    f"left the index at {f(sb['opus55']['brinfo']['index_51_100'])} and forced Nash every 10 rounds took it to {f(r3['forced10']['index_51_100'])}, with {round(10 * r3['forced10']['share_above_0.3'])} of 10 games",
    "claims",
)
check(
    "Claims: +10% set",
    f"in {pc(dfr['brinfo_bias']['within_1pct_of_shown'])} of firm-rounds",
    "claims",
)
check(
    "Claims: −10% set",
    f"set in {pc(down['deference']['within_1pct_of_shown'])} of firm-rounds, at a cost of {pc(-down['profit_change_pct'] / 100)} of profit",
    "claims",
)
check(
    "Claims: hidden",
    f"Haiku 4.5 to {f(paper['hidden']['index_51_100'])} (paper) and Opus 5.5 to {f(hp['index_51_100'])} (wave 4)",
    "claims",
)
check(
    "Claims: screen",
    f"({f(r3['baseline']['index_51_100'])} and {f(sb['sonnet55']['baseline']['index_51_100'])}), and Haiku 5.5 competes ({f(h55['index_51_100'])})",
    "claims",
)
check("Claims: limit", f"at an index of {lim['primary_index']:.3f}", "claims")
check("Claims: lifted", f"the index rose to {f(li['primary_index'])}", "claims")
check("Claims: estimate", f"partway down, to {f(r7['primary_index'])}", "claims")
check(
    "Claims: following",
    f"raise {pc(o['follow_raise'])} of the time and a cut {pc(o['follow_cut'])}; Haiku 4.5 follows {pc(h45['follow_raise'])} and {pc(h45['follow_cut'])}",
    "claims",
)

# ---------------------------------------------------------------- summary and coverage
print(f"\n{sum(results)} of {len(results)} checks pass")
HAND = {
    "note": "notes counts read by hand: wave 4's 8 of 8 and 7 of 8; wave 5's 59 of 60 and 2 of 20; wave 6's 15 of 20 and "
    "13 of 20; wave 7's 12 of 20; wave 9's 3 of 8 and 4 of 8",
}
print(f"Not covered: {HAND['note']}; design constants; numbers quoted from the paper's text.")
NUM = re.compile(r"[−+]?\d+(?:\.\d+)?%?")
for doc, text in DOCS.items():
    covered = " ".join(matched[doc])
    left = [m for m in NUM.finditer(text) if "." in m.group(0) or "%" in m.group(0)]
    left = [m for m in left if m.group(0).lstrip("−+") not in covered]
    left = [
        m
        for m in left
        if not re.search(r"(#+ |§|\(#)\s*$", text[max(0, m.start() - 4) : m.start()])
    ]
    if left:
        print(f"\nDecimals and percentages in {doc} that no check matched ({len(left)}):")
        for m in left:
            print(f"  {m.group(0):>8}  …{text[max(0, m.start() - 50) : m.end() + 15].strip()}…")
sys.exit(0 if all(results) else 1)
