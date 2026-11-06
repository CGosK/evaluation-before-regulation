"""
Platform rules for wave 5 (followup/WAVE5_PLAN.md; November 2026, not part of the submission).

A rule is a subclass of Rule, built once per game with that game's seed. Each round the harness calls, in order:
    override(round_num, prices) -> prices   after the agents choose; return the prices the market uses
    notice(firm, prices, profits) -> str     after the market clears; extra market-data lines for that firm
and show_rivals decides whether each firm's market data keeps the rival-price line. self.round holds the current
round in both calls. A rule may use only these arguments, its own state and the demand model in theory/bandit.py
(best_response, NASH, MONOPOLY). It must not falsify anything it shows.

A rule file defines one subclass and names it RULE. check_source() rejects files that import anything outside
ALLOWED or touch files, the process or other games.

The six rules already tested are here (KNOWN), rewritten to this interface; WAVE5_PLAN.md's check games show
they behave as their originals.
"""

import ast
import random
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {"math", "random", "numpy", "bandit", "platform_rules", "statistics", "collections"}
BANNED = {
    "open",
    "exec",
    "eval",
    "compile",
    "__import__",
    "globals",
    "locals",
    "getattr",
    "setattr",
}


def _benchmarks():
    import sys

    sys.path.insert(0, str(ROOT / "theory"))
    from bandit import benchmarks

    return benchmarks(2)


NASH, MONOPOLY = (float(v) for v in _benchmarks())


def best_response(own: float, rival: float) -> float:
    from bandit import best_response as br

    return float(br(np.array([[own, rival]]))[0, 0])


class Rule:
    name = "none"
    show_rivals = True

    def __init__(self, seed: int):
        self.rng = random.Random(f"{self.name}-{seed}")
        self.round = 0

    def override(self, round_num: int, prices: dict) -> dict:
        return prices

    def notice(self, firm: str, prices: dict, profits: dict) -> str:
        return ""


class BestResponseInfo(Rule):
    name = "brinfo"

    def notice(self, firm, prices, profits):
        rival = next(p for f, p in prices.items() if f != firm)
        br = best_response(prices[firm], rival)
        return f"- Platform estimate of my profit-maximizing price given the competitor's price: {round(br, 2)}\n"


class Cut(Rule):
    name, every, cut = "cut10", 10, 0.10

    def override(self, round_num, prices):
        if round_num > 10 and round_num % self.every == 0:
            firm = self.rng.choice(sorted(prices))
            prices[firm] = max(1.0, prices[firm] * (1 - self.cut))
        return prices


class ForcedNash(Rule):
    name, every = "forced10", 10

    def override(self, round_num, prices):
        if round_num > 10 and round_num % self.every == 0:
            prices[self.rng.choice(sorted(prices))] = NASH
        return prices


class ForcedNash5(ForcedNash):
    name, every = "forced5", 5


class Hidden(Rule):
    name, show_rivals = "hidden", False


KNOWN = {r.name: r for r in (Rule, BestResponseInfo, Cut, ForcedNash, ForcedNash5, Hidden)}


def check_source(path: Path) -> list:
    """Problems that bar a rule file from screening; an empty list means it may run."""
    problems = []
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [(node.module or "").split(".")[0]]
        else:
            names = []
        problems += [f"imports {n}" for n in names if n not in ALLOWED]
        if isinstance(node, ast.Name) and node.id in BANNED:
            problems.append(f"uses {node.id}")
        if (
            isinstance(node, ast.Attribute)
            and node.attr.startswith("__")
            and node.attr != "__init__"
        ):
            problems.append(f"uses {node.attr}")
    if not any(
        isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "RULE" for t in n.targets)
        for n in tree.body
    ):
        problems.append("defines no RULE")
    return problems


def load_rule(path_or_name: str):
    """A known rule's name, or a rule file's path."""
    if path_or_name in KNOWN:
        return KNOWN[path_or_name]
    path = Path(path_or_name)
    problems = check_source(path)
    if problems:
        raise SystemExit(f"{path}: {'; '.join(problems)}")
    namespace: dict = {}
    exec(compile(path.read_text(), str(path), "exec"), namespace)  # checked by check_source above
    return namespace["RULE"]
