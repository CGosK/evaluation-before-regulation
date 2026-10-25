"""
Checks the numbers in PAPER_DRAFT.md against the saved outputs in theory/out/. Each check formats a value
from an output file the way the paper prints it and looks for that exact string in the paper. Prints every
check and exits non-zero if any fails.

Covers Tables 2-4, B1 and C1 and the in-text numbers of §4.2-4.5 and the appendices that come from these
outputs. Not covered: numbers quoted from other papers.

Usage:  .venv/bin/python theory/check_paper.py
"""

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
PAPER = (HERE / "PAPER_DRAFT.md").read_text().replace("\n", " ")
results = []


def f(x: float, d: int = 2, plus: bool = False) -> str:
    """The paper's number style: Unicode minus, optional plus sign."""
    s = f"{x:+.{d}f}" if plus else f"{x:.{d}f}"
    return s.replace("-", "−")


def ci(lo: float, hi: float, d: int = 2) -> str:
    return f"[{f(lo, d, True)}, {f(hi, d, True)}]"


def check(label: str, text: str):
    ok = text in PAPER
    results.append(ok)
    print(f"{'ok  ' if ok else 'FAIL'} {label}: {text}")


def load(name):
    return json.loads((OUT / name).read_text())


# Table 2: forced cut
fc = load("frontier_forced_cut.json")
for m in ("haiku", "fable", "haiku45", "haiku45_enforcer2"):
    r = fc[m]
    check(f"T2 {m} punishment", f"{f(r['punishment'])} {ci(*r['punishment_ci'])}")
    check(f"T2 {m} band", f"| {f(r['null_lo'])} ")
    check(f"T2 {m} return", f"| {f(r['return'])} ")
    check(f"T2 {m} cutter", f"| {f(r['cutter_gap'])} ")
    check(f"T2 {m} verdict", r["verdict"])

# Table 3: removal. p-values print with 3 decimals below 0.05, else 2.
def pv(x: float, cut: float = 0.05) -> str:
    return f"{x:.3f}" if x < cut else f"{x:.2f}"


rem = load("remedies_existing.json")
for m, mech, w in (("Haiku 5.5", "mechanisms.json", "removal_welfare_haiku"),
                   ("Haiku 4.5", "mechanisms_haiku45.json", "removal_welfare_haiku45")):
    s = load(mech)["summary"]
    for arm in ("hidden", "rpe", "brinfo"):
        v, t = s[arm], rem[w][arm]
        check(f"T3 {m} {arm}", f"| {m} | {f(v['effect'], 2, True)} {ci(*v['effect_ci'])} | {v['lower_in']} / 8 | "
              f"{pv(v['p_sign_flip'])} | {f(t['ts_change'], 1, True)} {ci(*t['ts_ci'], d=1)} |")
fe = rem["forced_experiment"]["haiku45"]
check("T3 forced cut", f"| {f(fe['market_index_effect'], 2, True)} {ci(*fe['ci'])} | {fe['states_lower']} / 8 | "
      f"{pv(fe['p_signflip'])} | {f(fe['ts_change'], 1, True)} |")
en = load("mechanisms_haiku45_enforcer2.json")["summary"]
ew = rem["removal_welfare_haiku45_enforcer2"]
ef = rem["forced_experiment"]["haiku45_enforcer2"]
check("T3 enforcer forced early", f"| Enforcer | {f(ef['market_index_effect'], 2, True)} {ci(*ef['ci'])} | {ef['states_lower']} / 8 | "
      f"{pv(ef['p_signflip'])} | {f(ef['ts_change'], 1, True)} |")
check("T3 enforcer forced late", f"| Enforcer | {f(en['deviate']['effect'], 2, True)} {ci(*en['deviate']['effect_ci'])} | "
      f"{en['deviate']['lower_in']} / 8 | {pv(en['deviate']['p_sign_flip'])} |")
for arm in ("brinfo", "hidden"):
    v, t = en[arm], ew[arm]
    check(f"T3 enforcer {arm}", f"| Enforcer | {f(v['effect'], 2, True)} {ci(*v['effect_ci'])} | {v['lower_in']} / 8 | "
          f"{pv(v['p_sign_flip'])} | {f(t['ts_change'], 1, True)} {ci(*t['ts_ci'], d=1)} |")
fb = rem["forced_experiment"]["fable"]
check("C1 text: Fable forced cut", f"by {f(-fb['market_index_effect'])} {ci(*fb['ci'])}")

# Table 4: prevention
for r in load("prevention45.json")["rows"]:
    n_hi = round(r["share_above_0.3"] * r["games"])
    if r["arm"] == "baseline":
        check("T4 baseline", f"| {r['games']} | {f(r['index_51_100'])} | {n_hi} / {r['games']} |")
        continue
    check(f"T4 {r['arm']}", f"| {r['games']} | {f(r['index_51_100'])} | {n_hi} / {r['games']} | "
          f"{f(r['effect'], 2, True)} {ci(*r['effect_ci'])} | {pv(r['p_permutation'], 0.1)} ({pv(r['p_holm'], 0.1)}) | "
          f"{f(r['cs_change_pct'], 0, True)}% | {f(r['ts_change_pct'], 0, True)}% |")

# Table 4, four-firm rows
for r in load("prevention45_4firm.json")["rows"]:
    n_hi = round(r["share_above_0.3"] * r["games"])
    idx = f(r["index_51_100"]).replace("−0.00", "0.00")
    if r["arm"] == "baseline":
        check("T4 4-firm baseline", f"| {r['games']} | {idx} | {n_hi} / {r['games']} |")
        continue
    p_txt = "< 0.001" if r["p_permutation"] < 0.001 else pv(r["p_permutation"], 0.1)
    check(f"T4 4-firm {r['arm']}", f"| {r['games']} | {idx} | {n_hi} / {r['games']} | {f(r['effect'], 2, True)} "
          f"{ci(*r['effect_ci'])} | {p_txt} | {f(r['cs_change_pct'], 0, True)}% | {f(r['ts_change_pct'], 0, True)}% |")
    check(f"4.5 4-firm Fisher {r['arm']}", f"(Fisher's exact p = {r['p_fisher_share_above_0.3']:.4f} for each)")
b4 = next(r for r in load("prevention45_4firm.json")["rows"] if r["arm"] == "baseline")
check("4.5 4-firm profit gain", f"capturing {b4['profit_index_51_100']:.0%} of the monopoly profit gain")

# Table C1: P2 across market sizes
for n, v in load("remedies_existing.json")["prompt_prevention"].items():
    check(f"C1 {n} firms", f"| {n} | {f(v['P1']['index_251_300'])} → {f(v['P2']['index_251_300'])} | "
          f"{f(v['effect_P2_minus_P1'])} {ci(*v['ci'])} | {v['P1']['share_games_above_0.3']:.0%} → "
          f"{v['P2']['share_games_above_0.3']:.0%} | {f(v['cs_change_pct'], 0, True)}% | "
          f"{f(v['profit_change_pct'], 0, True)}% | {f(v['ts_change_pct'], 1, True)}% |")

# §4.3: monitoring
nm = load("notes_monitor.json")["summary"]
b = nm["baseline"]["coordination"]
check("4.3 coordination rates", f"({b['rate_low']:.0%} of firm-rounds) than in those that end high ({b['rate_high']:.0%})")
check("4.3 keyword AUC baseline", f"AUC of {b['auc']:.2f} {ci(*b['auc_ci']).replace('+', '')}")
a = nm["all_thinking_off"]["coordination"]
check("4.3 keyword AUC all", f"{a['auc']:.2f} {ci(*a['auc_ci']).replace('+', '')}")
check("4.3 hidden rate", f"({nm['hidden']['coordination_rate']:.1%} of firm-rounds)")
lm = load("llm_monitor.json")
check("4.3 judge AUC baseline", f"AUC of {lm['baseline']['auc']:.2f} {ci(*lm['baseline']['auc_ci']).replace('+', '')}")
check("4.3 judge AUC all", f"{lm['all_thinking_off']['auc']:.2f} {ci(*lm['all_thinking_off']['auc_ci']).replace('+', '')}")
check("4.3 judge brinfo", f"(mean {lm['by_arm']['brinfo']['mean_score']:.1f} of 10)")
check("4.3 judge reset", f"least ({lm['by_arm']['reset50']['mean_score']:.1f})")

# §4.1 and Appendix B/C: the SBR's out-of-sample fit and the platform-rule simulations
bn = list(csv.DictReader(open(OUT / "bandit_by_n.csv")))
test = [r for r in bn if r["split"] == "test"]
mae = sum(abs(float(r["gradient"]) - float(r["observed"])) for r in test) / len(test)
check("4.1 SBR error", f"mean absolute error {mae:.3f}")
p1 = [r for r in test if r["prompt"] == "P1"]
check("B SBR error on P1", f"error is {sum(abs(float(r['gradient']) - float(r['observed'])) for r in p1) / len(p1):.3f}")
ps = {r["scenario"]: r for r in csv.DictReader(open(OUT / "policy_sim.csv"))}
g = {k: (float(v["index_51_100"]), float(v["index_251_300"])) for k, v in ps.items()}
check("C P2 decomposition", f"from {f(g['P1 baseline'][1])} to {f(g['P2 opening only'][1])} with P2's opening alone "
      f"(the full P2 fit gives {f(g['P2 (all ingredients)'][1])}")
check("C P2 move rates", f"{f(g['P2 move rates only'][1])} with its move rates and {f(g['P2 gradient rule only'][1])} with its")
check("C sim baseline", f"against {f(g['P1 baseline'][0])} and {f(g['P1 baseline'][1])} with no rule")
check("C sim forced 25", f"every 25 rounds, {f(g['forced experiment every 25'][0])} and {f(g['forced experiment every 25'][1])}")
check("C sim forced 10", f"every 10 rounds, {f(g['forced experiment every 10'][0])} and {f(g['forced experiment every 10'][1])}")
check("C sim exploration", f"opening level, {f(g['exploration mandate'][0])} and {f(g['exploration mandate'][1])}")
check("C sim reset", f"round 150, {f(g['memory reset at round 150'][0])} and {f(g['memory reset at round 150'][1])}")

# §4.2 and §4.5: following and deference
ft = load("following_test.json")
bl, hi = ft["baseline"], ft["locked_high"]
check("4.2 following", f"follows a rival's cut {bl['cut']['follow_same_direction']:.0%} of the time and a raise "
      f"{bl['raise']['follow_same_direction']:.0%} (Fisher p = {bl['p_fisher_cut_vs_raise']:.2f}), against "
      f"{bl['move_after_quiet_round']:.0%} after a round")
check("4.2 following when high", f"{hi['cut']['follow_same_direction']:.0%} against {hi['raise']['follow_same_direction']:.0%}")
dt = load("deference_test.json")
check("4.5 deference", f"within 1% in {dt['prevention']['brinfo']['within_1pct_of_best_response']:.0%} of firm-rounds")
check("4.5 baseline landing", f"best response {dt['prevention']['baseline']['within_1pct_of_best_response']:.1%} of the time")
check("4.5 removal adoption", f"adopt it {dt['removal_haiku45']['within_1pct_of_estimate']:.0%} of the time, and agents told "
      f"to enforce {dt['removal_haiku45_enforcer']['within_1pct_of_estimate']:.0%}")
check("C forced 10% cut 25", f"gives {f(g['forced 10% cut every 25'][0])} and {f(g['forced 10% cut every 25'][1])} every 25")
check("C forced 10% cut 10", f"{f(g['forced 10% cut every 10'][0])} and {f(g['forced 10% cut every 10'][1])} every 10")

# §4.1: Fish et al.'s regression on the Mistral games
fr = {(r["prompt"], r["spec"]): float(r["rival"]) for r in csv.DictReader(open(OUT / "fish_replication.csv"))}
imp = "partial-adjustment best responder (implied)"
check("4.1 Fish regression", f"({fr['P1', 'replication']:.3f} under P1 and {fr['P2', 'replication']:.3f} under P2, against "
      f"non-strategic benchmarks of {fr['P1', imp]:.3f} and {fr['P2', imp]:.3f})")

# §3 and Appendix B: the decision rule on scripted firms (percentages rounded half up)
pct = lambda x: f"{int(x * 100 + 0.5)}%"  # noqa: E731
fcp = list(csv.DictReader(open(OUT / "forced_cut_power.csv")))
mild = [r for r in fcp if float(r["noise"]) == 1.0]
ns = [float(r["SBR"]) for r in mild if r["rule"] == "matched" and r["agent"] in ("sbr", "br")]
pun = [float(r["enforcement"]) for r in fcp if r["rule"] == "matched" and r["agent"] == "punisher"]
check("3 validation", f"non-strategic {pct(min(ns))[:-1]}–{pct(max(ns))} of the time, and a firm that reverts to Nash "
      f"for five rounds an enforcer {pct(min(pun))[:-1]}–{pct(max(pun))} of the time")
nv = [float(r["enforcement"]) for r in mild if r["rule"] == "naive" and r["agent"] == "br"]
check("B naive rule", f"misread as an enforcer {pct(min(nv))[:-1]}–{pct(max(nv))} of the time")
m8 = {r["agent"]: float(r["mean_punishment"]) for r in mild if r["rule"] == "matched" and r["n_sources"] == "8"}
check("B punishment sizes", f"Nash reversion ({f(m8['punisher'])}) or a halfway cut for five rounds ({f(m8['soft'])}); "
      f"it would miss weak punishment of about {f(m8['weak'])}")

# Appendix Table B1 rows from saved CSVs
gs = list(csv.DictReader(open(OUT / "group_size.csv")))
check("B1 levels", ", ".join(f"{float(r['observed']):.2f}" for r in gs))
lang = next(csv.DictReader(open(OUT / "language.csv")))
check("B1 punish share", f"{float(lang['punish / retaliate']):.2%}")

print(f"\n{sum(results)} of {len(results)} checks pass")
sys.exit(0 if all(results) else 1)
