"""
Checks the numbers in FOLLOWUP_NOTE.md, CLAIMS_STATUS.md and PAPER_DEFERENCE.md against the follow-up's saved outputs (out/*.json),
in the style of theory/check_paper.py. Each check formats a value the way the docs print it and looks for that
exact string. Numbers that no output file stores are recomputed here from the saved games. A permutation
p-value recomputed here is checked within its sampling error, not to the digit.

Not covered, and listed at the end: counts read by hand from the agents' notes, design constants (rounds,
games per arm, sizes fixed in the plans), numbers quoted from the paper's text, and numbers quoted from other
work, which must still appear as listed. Every other number in the two docs that no check matched, outside
model versions, links and the references, is printed for review.

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
PAPER = (HERE / "PAPER_DEFERENCE.md").read_text().replace("\n", " ")
DOCS = {"note": NOTE, "claims": CLAIMS, "paper": PAPER}
results, matched = [], {"note": [], "claims": [], "paper": []}


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
    (
        "The limit, no threat",
        "wave 6",
        "–",
        f"{f(load('wave11.json')['arms']['A']['index_51_100'])} (wave 11)",
        f(nt["primary_index"]),
    ),
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

# ---------------------------------------------------------------- wave 10 (wave10.json, plus per-game windows)
import extras_readme as ex  # noqa: E402

w10 = load("wave10.json")
P10, S10, E10 = w10["primary"], w10["secondary"], w10["exploratory"]
g10 = ex.wave10_games()["estimate"]
a51 = {s: float(i[50:100].mean()) for s, i in g10.items()}
b151 = {s: float(i[150:200].mean()) for s, i in g10.items()}
fell = sorted(g10, key=lambda s: b151[s] - a51[s])[:3]
check_true("W10 the three that fell are seeds 4, 5 and 7", sorted(fell) == [4, 5, 7])
check(
    "W10 table estimate",
    f"| Estimate, no threat (10 games) | {f(P10['estimate_index_51_100'])} | {f(P10['estimate_index_151_200'])} | {f(P10['estimate_change'])} |",
)
check(
    "W10 table baseline",
    f"| Baseline (5 games) | {f(P10['baseline_index_51_100'])} | {f(P10['baseline_index_151_200'])} | {f(P10['baseline_change'])} |",
)
check(
    "W10 tests",
    f"isn't significant (p = {f(P10['p_holm']['change'])}, Holm), and neither is its difference from the baseline's change (p = {f(P10['p_holm']['against_baseline'])})",
)
lo10, hi10 = P10["estimate_index_151_200_ci"]
check(
    "W10 level",
    f"the arm's index is {f(P10['estimate_index_151_200'])} (95% interval {f(lo10)}–{f(hi10)}), and no game is below 0.1",
)
check_true("W10 no game below 0.1", E10["estimate_games_below_0.1_151_200"] == 0)
check(
    "W10 remedy table",
    f"| The same, over rounds 151–200 of 200 | wave 10 | – | – | {f(P10['estimate_index_151_200'])} |",
)
check(
    "W10 fell",
    f"from {f(min(a51[s] for s in fell))}–{f(max(a51[s] for s in fell))} over rounds 51–100 to {f(min(b151[s] for s in fell))}–{f(max(b151[s] for s in fell))} over rounds 151–200",
)
check("W10 rose", f"one from {f(a51[3])} to {f(b151[3])}")
blocks10 = E10["blocks_10"]["estimate"][10:]
check("W10 blocks", f"sits between {f(min(blocks10))} and {f(max(blocks10))}")
check(
    "W10 spread",
    f"from {f(min(b151.values()))} to {f(max(b151.values()))}, against {f(min(a51.values()))} to {f(max(a51.values()))}",
)
check(
    "W10 follow",
    f"in {pc(S10['follow_101_199'])} of firm-rounds over rounds 101–199 against {pc(S10['follow_11_99'])} over rounds 11–99, but the rise isn't significant (p = {ex.r(S10['p'])})",
)

# ---------------------------------------------------------------- wave 11 (wave11.json, wave11_exploratory.json)
w11, x11 = load("wave11.json"), load("wave11_exploratory.json")
A11, B11, C11 = (w11["arms"][a] for a in "ABC")
SB, HB = w11["baselines"]["sonnet55"], w11["baselines"]["haiku55"]
lim11, cs, ch = x11["limit"], x11["cap_sonnet"], x11["cap_haiku"]
check_true(
    "W11 readings",
    A11["reading"] == "lowers, not competitive"
    and all(
        r["reading"] == "no detectable effect; rules out the full focal effect" for r in (B11, C11)
    ),
)
check_true(
    "W11 triggers", w11["triggers"] == {"stage_B": False, "stage_B_because": [], "arm_A2": True}
)
check(
    "W11 new Sonnet baselines",
    f"which match them ({f(SB['wave11_index'])} against {f(SB['wave2_index'])}, p = {f(SB['new_against_old_p'])})",
)
base_high = sum(v > 0.3 for v in SB["wave11_by_game"]) + round(
    10
    * next(
        r["share_above_0.3"]
        for r in load("wave2.json")["stage_b"]["sonnet55"]
        if r["arm"] == "baseline"
    )
)
check(
    "W11 limit table baseline",
    f"| Baseline (15 games) | {f(SB['pooled_index'])} | {base_high} of 15 | |",
)
check(
    "W11 limit table arm",
    f"| Limit, no threat | {f(A11['index_51_100'])} | {A11['games_above_0.3']} of 10 | {f(A11['difference'])} [{f(A11['difference_ci'][0])}, {f(A11['difference_ci'][1])}], p = {f(A11['p_holm'], 3)} (Holm) |",
)
check("W11 limit level", f"Its index of {f(A11['index_51_100'])} is above the 0.1")
check(
    "W11 Opus under the same rule",
    f"On Opus the same rule reached {f(w6j['rules']['w6-limit-no-threat']['primary_index'])} (§4.2)",
)
check(
    "W11 follow",
    f"in {pc(w11['secondary']['A_follow_11_99'])} of firm-rounds; Opus set the same line in {pc(w6j['exploratory']['follow_no_threat_11_99']['within_1pct'])}",
)
kf, ki, of_, oi = (
    lim11["kept_follow"],
    lim11["kept_index"],
    lim11["other_follow"],
    lim11["other_index"],
)
check(
    "W11 follow by game",
    f"In {len(lim11['kept_games'])} games, firms set the limit in {100 * kf[0]:.0f}–{pc(kf[1])} of firm-rounds and ended at {f(ki[0])}–{f(ki[1])}. "
    f"In the other {10 - len(lim11['kept_games'])}, they set it in {100 * of_[0]:.0f}–{pc(of_[1])} and ended at {f(oi[0])}–{f(oi[1])}.",
)
bl = A11["blocks_10"]
check("W11 limit blocks", f"went from {f(bl[1])} in rounds 11–20 to {f(bl[9])} in rounds 91–100")
for label, r_, b_ in (("Sonnet 5.5", C11, SB), ("Haiku 5.5", B11, HB)):
    lo, hi = r_["difference_ci"]
    check(
        f"W11 cap table {label}",
        f"| {label} | {f(b_['pooled_index'])} | {f(r_['index_51_100'])} | {f(r_['difference'], plus=True)} [{f(lo)}, {f(hi)}] | {f(r_['p_holm'])} |",
    )
ff = x11["full_focal"]
check_true("W11 full focal index is the plan's 0.55", ff["index"] == 0.55)
check(
    "W11 full focal",
    f"a rise of {f(ff['sonnet55'])} for Sonnet and {f(ff['haiku55'])} for Haiku 5.5",
)
check_true(
    "W11 both intervals end below the full focal effect",
    C11["difference_ci"][1] < ff["sonnet55"] and B11["difference_ci"][1] < ff["haiku55"],
)
check("W11 Haiku raw p", f"(p = {f(B11['p_raw'])} before correction)")
check_true(
    "W11 seven held the cap, after a dip in round 2 or 3",
    len(cs["held_cap"]) == 7
    and {h["dip_round"] for h in cs["held_cap"]} <= {2, 3}
    and cs["at_cap_51_100"] == sorted(h["seed"] for h in cs["held_cap"]),
)
check_true(
    "W11 the other 13 priced below the cap from round 2 or 3, in every round after",
    set(cs["others_first_below_round"]) <= {2, 3}
    and not any(cs["others_rounds_below_after_first"]),
)
check_true(
    "W11 ten below 0.2, none of the baseline",
    cs["below_0.2"] == 10 and cs["baseline_below_0.2"] == 0,
)
check_true(
    "W11 held games level with the top baseline game", f(x11["cap_index"]) == f(cs["baseline_max"])
)
check(
    "W11 the cap's index", f"a fixed cap of 1.74, an index of {f(x11['cap_index'])}, in the limit"
)
check(
    "W11 held games' index",
    f"Their index, {f(x11['cap_index'])}, is level with the highest baseline game",
)
check("W11 baseline minimum", f"whose lowest is {f(cs['baseline_min'])}")
check(
    "W11 spread",
    f"their standard deviation is {f(cs['sd'])} against the baseline's {f(cs['baseline_sd'])} (p < 0.001), and 10 of 20 ended below 0.2 against none of 15 (p = {f(cs['below_0.2_fisher_p'], 3)})",
)
check_true("W11 spread p below 0.001", cs["sd_p"] < 0.001)
op = sorted(cs["opening_model_prices"] + ch["opening_model_prices"])
check("W11 openings", f"at {op[0]:.2f}–{op[-1]:.2f}")
check_true(
    "W11 every opening price replaced",
    cs["replaced_round_1"] == 40 and ch["replaced_round_1"] == 20,
)
fb = x11["sonnet_baseline_opening"]["first_round_below_cap_level"]
check("W11 baseline passes the cap level", f"between rounds {fb[0]} and {fb[1]}")
check_true(
    "W11 two prices above the cap after round 1, one Haiku 5.5 firm",
    not cs["replaced_after_round_1"]
    and len(ch["replaced_after_round_1"]) == 2
    and len({(r["seed"], r["firm"]) for r in ch["replaced_after_round_1"]}) == 1,
)
wa = w11["secondary"]["where_against_cap"]
check(
    "W11 at the cap",
    f"{pc(wa['C']['at'])} of Sonnet's firm-rounds and {pc(wa['B']['at'])} of Haiku 5.5's were at the cap",
)
check_true(
    "W11 none above the cap, rounds 51-100",
    wa["B"]["above_replaced"] == 0 == wa["C"]["above_replaced"],
)
near = [v for v in ch["index_by_game"].values() if 0.5 < v < x11["cap_index"] - 1e-3]
check_true(
    "W11 Haiku: two at the cap, one just under", len(ch["at_cap_51_100"]) == 2 and len(near) == 1
)
check(
    "W11 Haiku near and spread",
    f"one just under it, at {f(near[0])}, but its spread didn't change (p = {f(ch['sd_p'])})",
)
one = cs["one_firm_at_cap_51_100"]
check_true(
    "W11 one firm at the cap in two more games",
    cs["firms_at_cap_51_100"] == 16 and [o["seed"] for o in one] == [3, 9],
)
check("W11 their rivals", f"whose rival sat at {one[0]['rival_mean_price']:.2f}")
check_true(
    "W11 both rivals at the same price", len({round(o["rival_mean_price"], 2) for o in one}) == 1
)
check("W11 Haiku baseline max", f"above the cap's level, at {f(ch['baseline_max'])}")
check(
    "W11 remedy table",
    f"| The limit, no threat | wave 6 | – | {f(A11['index_51_100'])} (wave 11) | {f(w6j['rules']['w6-limit-no-threat']['primary_index'])} |",
)
check(
    "W11 remedy table cap",
    f"| A fixed cap at 1.74, enforced | wave 11 | – | {f(C11['index_51_100'])} | – |",
)
check(
    "W11 Haiku 5.5 note",
    f"under which its index was {f(B11['index_51_100'])} (§4.7). Wave 11's Sonnet arms are compared with 15 baseline games, which average {f(SB['pooled_index'])}",
)

# ---------------------------------------------------------------- wave 12 (wave12.json, wave12_exploratory.json)
w12, x12 = load("wave12.json"), load("wave12_exploratory.json")
P1, P2, S12 = w12["part1"], w12["part2"], w12["secondary"]
M12, CAP12, N12 = x12["mixed"], x12["cap"], x12["notes"]
own12 = S12["own_index"]
check_true(
    "W12 readings",
    P1["reading"] == "holds: competitive"
    and P2["readings"]
    == {
        "split": "the split replicates",
        "opening": "the opening drives the split",
        "late_cap": "lowers prices",
    }
    and w12["follows"] == {"own_project": False, "stop": True},
)
check(
    "W12 remedy table limit",
    f"| The limit, no threat, Opus and Sonnet together | wave 12 | – | {f(own12['A2']['sonnet55'])} | {f(own12['A2']['opus55'])} |",
)
check(
    "W12 remedy table C2",
    f"| The same cap, repeated on fresh games | wave 12 | – | {f(P2['C2']['index'])} | – |",
)
check(
    "W12 remedy table D",
    f"| The same cap, from round 31 | wave 12 | – | {f(P2['D']['index'])} | – |",
)
check(
    "W12 table note",
    f"and wave 12's with {P2['games']['baseline']}, which average {f(P2['baseline_index'])}. In the Opus–Sonnet row, each cell is that model's own index, and the market's was {f(P1['A2_index'])} (§4.6)",
)
check(
    "W12 leader-follower",
    f"the leader-follower outcome, an index of {f(P1['leader_follower_index'])} (§5)",
)
check(
    "W12 part 1 table",
    f"| No rule | {f(P1['mixed_index'])} | {f(own12['mixed']['opus55'])} | {f(own12['mixed']['sonnet55'])} |",
)
check(
    "W12 part 1 table A2",
    f"| Limit, no threat | {f(P1['A2_index'])} | {f(own12['A2']['opus55'])} | {f(own12['A2']['sonnet55'])} |",
)
lo, hi = P1["difference_ci"]
check(
    "W12 part 1 test",
    f"The index fell by {f(-P1['difference'])} [{f(lo)}, {f(hi)}] (p < 0.001), and no game ended above 0.05",
)
check_true("W12 part 1 p below 0.001", P1["p"] < 0.001)
check_true("W12 no A2 game above 0.05", max(M12["A2"]["index_by_game"].values()) < 0.05)
fo = S12["follow_A2_11_99"]
w11f = w11["secondary"]["A_follow_11_99"]
check(
    "W12 follow",
    f"Opus set it within 1% in {pc(fo['opus55'], 1)} of its firm-rounds, and Sonnet in {pc(fo['sonnet55'])}, against {pc(w11f)} next to another Sonnet (§4.5)",
)
so = S12["sonnet_own_A2_vs_wave11_limit"]
check(
    "W12 Sonnet own",
    f"Sonnet's own index fell to {f(so['A2'])},** against {f(so['wave11'])} under the limit in its own markets (p = {f(so['p'], 3)}, across waves)",
)
na = N12["A2"]
check_true(
    "W12 notes: Opus kept the limit in all 30, set it aside in none",
    sum(v["limit_kept"] for v in na["opus55"]["by_round"].values()) == 30
    and na["opus55"]["firms_any_note"]["limit_set_aside"] == 0,
)
check_true(
    "W12 notes: 10 Opus firms lead with no rule, 1 under the limit, 3 say the limit stops them",
    N12["mixed"]["opus55"]["firms_any_note"]["raise_to_lead"] == 10
    and na["opus55"]["firms_any_note"]["raise_to_lead"] == 1
    and na["opus55"]["firms_any_note"]["penalty_inferred"] == 3,
)
w11A = [
    json.loads(line) for line in (HERE / "runs/wave11/notes_coded.jsonl").read_text().splitlines()
]
w11A = [r for r in w11A if r["arm"] == "A"]
sk = sum(v["limit_kept"] for v in na["sonnet55"]["by_round"].values())
sa = sum(v["limit_set_aside"] for v in na["sonnet55"]["by_round"].values())
check(
    "W12 notes: Sonnet keeps",
    f"{sk} of 30, against {sum(bool(r['limit_kept']) for r in w11A)} of {len(w11A)} in wave 11. Thirteen set it aside",
)
check_true("W12 notes: thirteen set aside", sa == 13)
check_true(
    "W12 notes: four Sonnet firms plan raises, one Sonnet firm leads with no rule",
    na["sonnet55"]["firms_any_note"]["raise_to_lead"] == 4
    and N12["mixed"]["sonnet55"]["firms_any_note"]["raise_to_lead"] == 1,
)
mi = M12["A2"]["sonnet_misses"]
check("W12 misses", f"in {mi['above']} of its {mi['above'] + mi['below']} misses")
fs = M12["A2"]["follow_by_game"]["sonnet55"]
hi_f = sorted(v for v in fs.values() if v >= 0.5)
lo_f = [k for k, v in fs.items() if v < 0.5]
check(
    "W12 follow by game",
    f"In {len(hi_f)} games it set the limit in {100 * hi_f[0]:.0f}–{pc(hi_f[-1])} of its firm-rounds. In the tenth it set it in only {pc(fs[lo_f[0]])}",
)
check("W12 that market", f"and that market still ended at {f(M12['A2']['index_by_game'][lo_f[0]])}")
# §4.8
check("W12 new baselines", f"which match them (p = {f(S12['new_vs_earlier_baselines_p'])})")
D12 = CAP12["D"]
r30 = D12["index_round_30"]
check_true("W12 round 30 the same", f(r30["D"]) == f(r30["baseline"]))
check("W12 round 30", f"these games averaged {f(r30['D'])}, the same as the baseline's")
c2, d2 = P2["C2"], P2["D"]
check(
    "W12 T2 row",
    f"| Does the split replicate? | {c2['held_cap']} of 20 games held the cap and {c2['below_0.2']} ended below 0.2, the same counts as wave 11. Their standard deviation is {f(c2['sd'])} against the baseline's {f(P2['baseline_sd'])}. | < 0.001 | It replicates |",
)
check_true(
    "W12 T2 Holm below 0.001, same counts as wave 11",
    P2["p_holm"]["spread_C2"] < 0.001
    and c2["held_cap"] == len(cs["held_cap"])
    and c2["below_0.2"] == cs["below_0.2"],
)
check(
    "W12 T3 row",
    f"| Does it need the opening? | No game under the late cap held it, against {c2['held_cap']} of 20 under the cap from round 1 | {f(P2['p_holm']['held_D_vs_C2'], 3)} | The opening drives it |",
)
check_true("W12 D held none", d2["held_cap"] == 0)
dlo, dhi = d2["difference_ci"]
check(
    "W12 T4 row",
    f"| Does a late cap pull prices up? | Index {f(d2['index'])} against the baseline's {f(P2['baseline_index'])}: {f(d2['difference'])} [{f(dlo)}, {f(dhi)}] | {f(P2['p_holm']['index_D'], 3)} | It lowers them |",
)
t4 = x12["t4"]
check(
    "W12 T4 sensitivity",
    f"with a million shuffles it is {f(t4['p_1m'], 3)} again, and a rank test gives {f(t4['mann_whitney_p'])}",
)
bd = D12["blocks"]
check(
    "W12 blocks",
    f"largest in rounds 41–50, at {f(bd['difference'][4])}, and shrank to {f(bd['difference'][9])} by rounds 91–100, as the baseline came down to {f(bd['baseline'][9])} against {f(bd['D'][9])}",
)
check_true("W12 rounds 41-50 the largest gap", min(bd["difference"]) == bd["difference"][4])
r31 = D12["their_round_31_prices"]
oth = sorted((v for v in r31 if v != 1.74), reverse=True)
check(
    "W12 round 30 and 31",
    f"At round 30, {D12['firms_above_cap_round_30']} firms in {D12['games_above_cap_round_30']} games priced above 1.74. In round 31, {D12['round_31_at_cap']} of them set exactly 1.74, and the other two set {oth[0]:.2f} and {oth[1]:.2f}",
)
check_true("W12 the late cap replaced nothing", not D12["replaced"] and len(oth) == 2)
check(
    "W12 both at the cap",
    f"Both firms sat at 1.74 in the same round in {D12['games_both_at_cap_some_round']} games, never for more than {D12['longest_both_at_cap_run']} rounds in a row",
)
wa12 = S12["where_against_cap"]
check(
    "W12 at the cap",
    f"{pc(wa12['D']['at'])} of firm-rounds were at the cap, against {pc(wa12['C2']['at'])} under the cap from round 1",
)
op12 = CAP12["C2"]["opening_model_prices"]
check(
    "W12 openings",
    f"All 40 of its replacements were opening prices, of {op12[0]:.2f}–{op12[-1]:.2f}",
)
check_true(
    "W12 C2 replaced only in round 1, 40 times; held games dipped in round 2 or 3",
    {r["round"] for r in CAP12["C2"]["replaced"]} == {1}
    and len(CAP12["C2"]["replaced"]) == 40
    and {h["dip_round"] for h in CAP12["C2"]["held_cap"]} <= {2, 3},
)
nc = N12["C2"]["sonnet55"]
one12 = CAP12["C2"]["one_firm_at_cap_51_100"]
check_true(
    "W12 notes: the same 16 firms treat 1.74 as best, are the firms at the cap, all 16 blocked, 24 plan below",
    N12["C2_cap_best"]["same_firms_each_round"]
    and N12["C2_cap_best"]["are_the_firms_at_the_cap_51_100"]
    and N12["C2_cap_best"]["all_others_plan_below_cap"]
    and all(v["cap_best"] == 16 and v["plans_below_cap"] == 24 for v in nc["by_round"].values())
    and nc["firms_any_note"]["higher_blocked"] >= 16
    and len(one12) == 2,
)
check("W12 their rivals", f"whose rival sat at {one12[0]['rival_mean_price']:.2f}")
nd = N12["D"]["sonnet55"]["by_round"]
check_true(
    "W12 notes: late cap 0 at round 30, then 12, 3, 2",
    nd["30"]["cap_mentioned"] == 0
    and [nd[t]["cap_best"] for t in ("32", "60", "90")] == [12, 3, 2],
)
# §5
o12 = M12["own_against_baseline"]
check(
    "W12 §5 row",
    f"| Opus and Sonnet 5.5 ({f(o12['sonnet55']['baseline'])} against itself), wave 12 | {f(P1['mixed_index'])} | {f(own12['mixed']['opus55'])} | {f(own12['mixed']['sonnet55'])} |",
)
check(
    "W12 §5 own",
    f"from {f(o12['opus55']['baseline'])} to {f(o12['opus55']['mixed'])} (p = {f(o12['opus55']['p'])}), and Sonnet's didn't change ({f(o12['sonnet55']['mixed'])} against {f(o12['sonnet55']['baseline'])}, p = {f(o12['sonnet55']['p'])})",
)
check_true("W12 Opus above Sonnet in all 10", M12["mixed"]["opus_above_sonnet"] == 10)
br = M12["mixed"]["at_best_response"]
check(
    "W12 §5 best response",
    f"in {pc(br['sonnet55'])} of firm-rounds, against {pc(M12['mixed']['sonnet_at_best_response_against_itself'])} next to another Sonnet. Opus did so in {pc(br['opus55'])}",
)
check("W12 §5 market", f"But the market ended at {f(P1['mixed_index'])},** well above")

# ---------------------------------------------------------------- CLAIMS_STATUS.md
check(
    "Claims: wave 11",
    f"the same limit lowered the index to {f(A11['index_51_100'])}, not to competitive prices",
    "claims",
)
check(
    "Claims: wave 12",
    f"In a market of Opus and Sonnet it brought the index to {f(P1['A2_index'])}",
    "claims",
)
check(
    "Claims: wave 12 late cap",
    f"lowered the index a little, to {f(P2['D']['index'])} against {f(P2['baseline_index'])}",
    "claims",
)
check_true(
    "Claims: wave 11 split counts",
    len(cs["held_cap"]) == 7
    and cs["below_0.2"] == 10
    and "holding 7 of 20 at the cap and sending 10 below every baseline game" in CLAIMS,
)
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
    "Claims: wave 10",
    f"settled at {f(P10['estimate_index_151_200'])} over rounds 151–200, with no significant change",
    "claims",
)
check(
    "Claims: following",
    f"raise {pc(o['follow_raise'])} of the time and a cut {pc(o['follow_cut'])}; Haiku 4.5 follows {pc(h45['follow_raise'])} and {pc(h45['follow_cut'])}",
    "claims",
)


# ---------------------------------------------------------------- PAPER_DEFERENCE.md (the short paper)
PP = "paper"
ob, oi = sb["opus55"]["baseline"], sb["opus55"]["brinfo"]
sbb, si = sb["sonnet55"]["baseline"], sb["sonnet55"]["brinfo"]
d_h, d_s, d_o = (
    dfr["brinfo"]["within_1pct_of_shown"],
    si["deference"]["within_1pct_of_shown"],
    oi["deference"]["within_1pct_of_shown"],
)
check(
    "Paper abstract: information",
    f"On Claude Opus 5.5 it had no detectable effect ({f(oi['index_51_100'])} against {f(ob['index_51_100'])} on an index",
    PP,
)
check(
    "Paper abstract: Sonnet",
    f"on Sonnet 5.5 it helped partly ({f(si['index_51_100'])} against {f(sbb['index_51_100'])})",
    PP,
)
check(
    "Paper abstract: deference",
    f"Haiku 4.5 sets the number it is shown in {pc(d_h)} of firm-rounds, and one biased 10% too high in {pc(dfr['brinfo_bias']['within_1pct_of_shown'])}. Opus sets it in {pc(d_o)}.",
    PP,
)
check(
    "Paper abstract: limit and estimate",
    f"took Opus to {f(nt['primary_index'])}. Called an estimate, it took prices only to {f(r7['primary_index'])}.",
    PP,
)
check(
    "Paper abstract: mixed",
    f"The limit took Sonnet's own markets only partway ({f(A11['index_51_100'])}). Next to Opus, every market ended competitive ({f(P1['A2_index'])})",
    PP,
)
pool12 = CAP12["pooled_with_wave11"]
check("Paper abstract: cap", f"holding {pool12['held_cap']} of {pool12['games']} at the cap", PP)
check_true(
    "Paper: Nash and monopoly prices",
    f"The one-shot Nash price is {benchmarks_pn:.3f} and the joint-monopoly price {benchmarks_pm:.3f}."
    in PAPER,
)
matched[PP] += [f"{benchmarks_pn:.3f}", f"{benchmarks_pm:.3f}"]
h55b = bias[("haiku55", "baseline")]
check(
    "Paper: screen",
    f"Opus and Sonnet collude on their own ({f(r3['baseline']['index_51_100'])} and {f(sbb['index_51_100'])}), and Haiku 5.5 competes ({f(h55b['index_51_100'])})",
    PP,
)
check("Paper: limit line", "(never below the competitive price, 1.47)", PP)
check(
    "Paper: cap line", "Every seller has the same limit; a price above it is replaced by 1.74.", PP
)
check(
    "Paper §3: Haiku 4.5",
    f"It took Haiku 4.5 from {f(paper['baseline']['index_51_100'])} to {f(paper['brinfo']['index_51_100'])} in the sprint paper.",
    PP,
)
lo, hi = oi["effect_ci"]
check(
    "Paper §3: Opus",
    f"On Opus 5.5 the index was {f(oi['index_51_100'])} against a baseline of {f(ob['index_51_100'])} ({f(oi['effect'])} [{f(lo)}, {f(hi)}], p = {oi['p_holm']:.2f})",
    PP,
)
lo, hi = si["effect_ci"]
check(
    "Paper §3: Sonnet",
    f"on Sonnet 5.5 it was {f(si['index_51_100'])} against {f(sbb['index_51_100'])} ({f(si['effect'])} [{f(lo)}, {f(hi)}], p = {si['p_holm']:.3f})",
    PP,
)
check(
    "Paper §3: forced Nash",
    f"took Haiku 4.5 to {f(row1['forced10']['index_51_100'])} and Opus only to {f(r3['forced10']['index_51_100'])}",
    PP,
)
check(
    "Paper §3: set rates",
    f"Haiku 4.5 set the number in {pc(d_h)} of firm-rounds, Sonnet in {pc(d_s)} and Opus in {pc(d_o)}.",
    PP,
)
check(
    "Paper §3: Opus notes",
    f"its notes mention it in {pc(w3j['notes']['opus55']['share_mentioning'], 1)} of firm-rounds",
    PP,
)
check(
    "Paper §3: limit on Opus",
    f"took Opus to {f(nt['primary_index'])}, and Opus set it in {pc(ex6['follow_no_threat_11_99']['within_1pct'])} of firm-rounds",
    PP,
)
check(
    "Paper §3: limit on Sonnet",
    f"at {f(A11['index_51_100'])} against {f(SB['pooled_index'])} (p = {f(A11['p_holm'], 3)}), with Sonnet setting it in {pc(w11['secondary']['A_follow_11_99'])}",
    PP,
)
check(
    "Paper §3: placebo",
    f"lands within 1% of its best response {pc(pl['best_response_shown']['below 0.1']['share_within_1pct'])} of the time with the number shown and {pc(pl['no_number']['below 0.1']['share_within_1pct'])} without it",
    PP,
)
check(
    "Paper §4: +10%",
    f"set it in {pc(dfr['brinfo_bias']['within_1pct_of_shown'])} of firm-rounds and never set the true one. Obedience predicts a market at {f(w1['obedient_index_for_bias'])}, and all 10 games settled at {f(min(bias_games))}–{f(max(bias_games))}",
    PP,
)
check(
    "Paper §4: −10%",
    f"the number was set in {pc(down['deference']['within_1pct_of_shown'])} of firm-rounds, and profit fell {pc(-down['profit_change_pct'] / 100)}",
    PP,
)
check(
    "Paper §4: enforcers and Haiku 5.5",
    f"still set the inflated number in {pc(enf['deference']['within_1pct_of_shown'])} of firm-rounds. Haiku 5.5, which competes on its own, set it in {pc(h55['deference']['within_1pct_of_shown'])}.",
    PP,
)
check("Paper Table 1 baseline", f"The baseline is {f(r3['baseline']['index_51_100'])}.", PP)
check(
    "Paper Table 1 estimate",
    f"| Called an estimate | {f(r7['primary_index'])} | {f(et['primary_index'])} |",
    PP,
)
check(
    "Paper Table 1 limit",
    f"| Called a limit | {f(nt['primary_index'])} | {f(lim['primary_index'])} |",
    PP,
)
check(
    "Paper §4: estimate and 200 rounds",
    f"the same number took Opus only partway, to {f(r7['primary_index'])}, and in games continued to 200 rounds it settled at {f(P10['estimate_index_151_200'])}",
    PP,
)
check("Paper §4: lifted", f"the index rose to {f(li['primary_index'])}", PP)
check(
    "Paper §4: diagnosis",
    f"Opus's response, {f(dg['opus55']['punishment'])}, sits inside the non-strategic band",
    PP,
)
check_true(
    "Paper §4: inside the band",
    dg["opus55"]["punishment"] > load("null_band_scale.json")["opus55"]["base_scale"]["null_lo"],
)
lo, hi = P1["difference_ci"]
check(
    "Paper §5: mixed",
    f"With no remedy, the market ended at {f(P1['mixed_index'])}. Under the posted limit with no threat, it ended at {f(P1['A2_index'])} ({f(P1['difference'])} [{f(lo)}, {f(hi)}], p < 0.001), and no game ended above 0.05.",
    PP,
)
check(
    "Paper §5: Sonnet own",
    f"Sonnet's own index fell to {f(so['A2'])}, against {f(so['wave11'])} under the same limit in its own markets.",
    PP,
)
check(
    "Paper §5: follow",
    f"Sonnet set the limit in {pc(fo['sonnet55'])} of firm-rounds, against {pc(w11f)} next to another Sonnet.",
    PP,
)
check(
    "Paper §5: Sonnet notes",
    f"Sonnet kept the limit in {sk} of its 30 notes and set it aside in {sa}",
    PP,
)
T8b = T8["5 brinfo vs opus-haiku45: market"]
check(
    "Paper §5: wave 8",
    f"best-response information had no detectable effect: {f(A8['opus-haiku45-brinfo']['market_index'])} against {f(A8['opus-haiku45']['market_index'])} (p = {T8b['p_holm']:.2f})",
    PP,
)
check(
    "Paper §5: Haiku 4.5 set",
    f"Haiku 4.5 set the number in {pc(fl8['claude-haiku-4-5']['within_1pct'])} of firm-rounds",
    PP,
)
check(
    "Paper §5: leader-follower",
    f"the leader-follower outcome of {f(P1['leader_follower_index'])}",
    PP,
)
check(
    "Paper §6: cap index", f"a fixed, enforced cap of 1.74, an index of {f(x11['cap_index'])}", PP
)
check(
    "Paper §6: wave 11",
    f"On Sonnet the index was {f(C11['index_51_100'])} against {f(SB['pooled_index'])} (p = {f(C11['p_holm'])}), and on Haiku 5.5 it was {f(B11['index_51_100'])} against {f(HB['pooled_index'])} (p = {f(B11['p_holm'])})",
    PP,
)
check(
    "Paper §6: pooled",
    f"{pool12['held_cap']} of {pool12['games']} held the cap to the end, and {pool12['below_0.2']} of {pool12['games']} ended below 0.2",
    PP,
)
check(
    "Paper §6: spread",
    f"(standard deviation {f(c2['sd'])} against {f(P2['baseline_sd'])}, p < 0.001)",
    PP,
)
check_true(
    "Paper §6: the same 16 of 40 firms in each set, all blocked",
    cs["firms_at_cap_51_100"] == 16
    and N12["C2_cap_best"]["same_firms_each_round"]
    and all(v["cap_best"] == 16 for v in nc["by_round"].values()),
)
check(
    "Paper §6: round 30",
    f"At round 30, these games averaged {f(r30['D'])}, the same as the baseline's.",
    PP,
)
check(
    "Paper §6: T3",
    f"The cap held none of 20 games, against {c2['held_cap']} of 20 under the cap from round 1 (p = {f(P2['p_holm']['held_D_vs_C2'], 3)})",
    PP,
)
check_true("Paper §6: all came down", all(v <= 1.74 for v in D12["their_round_31_prices"]))
check(
    "Paper §6: firms above",
    f"the {D12['firms_above_cap_round_30']} firms above it at round 30 all came down to it or below in round 31",
    PP,
)
check(
    "Paper §6: T4",
    f"to {f(d2['index'])} against {f(P2['baseline_index'])} ({f(d2['difference'])} [{f(dlo)}, {f(dhi)}], p = {f(P2['p_holm']['index_D'], 3)})",
    PP,
)
check("Paper §6: rank test", f"a rank test gives {f(t4['mann_whitney_p'])}", PP)

# ---------------------------------------------------------------- summary and coverage
print(f"\n{sum(results)} of {len(results)} checks pass")
HAND = {
    "note": "notes counts read by hand: wave 4's 8 of 8 and 7 of 8; wave 5's 59 of 60 and 2 of 20; wave 6's 15 of 20 and "
    "13 of 20; wave 7's 12 of 20; wave 9's 3 of 8 and 4 of 8; wave 10's 9 of 20 and four; "
    "wave 11's 7 of 8, 8 of 12, 16 of the 40, All 16, 15 and 24 (coded by a subagent)",
}
print(f"Not covered: {HAND['note']}; design constants; numbers quoted from the paper's text.")
QUOTED = [
    "from 31% of the time (Claude Opus) to 63% (GPT-3.5)",
    "ranging from 43.5% to 89.5%",
    "in 98–99% of replays",
    "by 11.5 points",
]
missing = [q for q in QUOTED if q not in NOTE] + [q for q in ("by 11.5 points",) if q not in PAPER]
matched["paper"] += [q for q in ("by 11.5 points",) if q in PAPER]
results += [not missing]
matched["note"] += [q for q in QUOTED if q in NOTE]
print(
    f"Quoted from other work (§7, Limits), checked against the sources by hand: {'; '.join(QUOTED)}"
)
if missing:
    print(f"FAIL quoted text no longer in the note: {missing}")
NUM = re.compile(r"[−+]?\d+(?:\.\d+)?%?")
NOT_RESULTS = r"## References.*|\]\([^)]*\)|(?:GPT-|DeepSeek-V|Llama-|(?:Claude|Fable|Haiku|Opus|Sonnet) )\d+(?:\.\d+)?"
for doc, text in DOCS.items():
    text = re.sub(NOT_RESULTS, lambda m: " " * len(m.group(0)), text)
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
