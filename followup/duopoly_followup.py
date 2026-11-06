"""
Follow-up arms (November 2026, after the sprint review). Not part of the sprint submission, which is tagged
submission-2026-10-25. Each arm is a fresh 100-round P1 duopoly run through the sprint harness unchanged:

    baseline         no remedy
    brinfo           the sprint's best-response information, unchanged
    brinfo_noise     best-response information with noise: the number shown is the best response times exp(e),
                     e ~ N(0, 0.10), drawn per firm and round
    brinfo_bias      best-response information biased upward: the number shown is 1.10 times the best response;
                     agents that set it exactly would settle at collusion index 0.62
    brinfo_biasdown  the same, biased downward: 0.90 times the best response
    cut10            every 10 rounds after round 10, one firm at random has its chosen price cut by 10% (floor at
                     marginal cost), the rule the SBR model tested and that needs no demand model
    forced10         the submission's forced-Nash rule, unchanged: every 10 rounds after round 10, one firm at
                     random is held at Nash for that round (needs --forced-every 10)
    forced5          the same rule every 5 rounds (needs --forced-every 5)
    hidden           the harness's hidden-prices mechanism, unchanged: market data omits rival prices
                     (needs --mechanism hidden)

The brinfo arms give the agents the sprint's brinfo notice; nothing tells them the number is noisy or biased.
--followup-strategy enforcer2 adds the paper's enforcer instruction (succession/branch.py STRATEGIES) to both
firms' prompts, in the place the branch runs put it. FOLLOWUP_FAMILY, if set, is written into the game's name
(e.g. haiku55), so games of different models and strategies can share a folder.

The script patches hooks of experiments_synthetic/common.py at import (the prompt, the best-response line in
market data, the experiment's price override, and the game's name and folder), then hands over to the
harness's own command line. No file of the submission is edited.

Usage:  .venv/bin/python followup/duopoly_followup.py --followup-arm ARM [--followup-strategy enforcer2]
            <experiments_synthetic/duopoly.py flags>
Writes: $FOLLOWUP_GAMES/2_agents/<timestamp>_duopoly_setting_P1_mem100_[<family>_]<arm>_<settings>_seed<s>/
        (default followup/runs/games)
"""

import math
import os
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "experiments_synthetic")]
import common  # noqa: E402
import succession.branch as branch  # noqa: E402

ARMS = (
    "baseline",
    "brinfo",
    "brinfo_noise",
    "brinfo_bias",
    "brinfo_biasdown",
    "cut10",
    "forced10",
    "forced5",
    "hidden",
)
NOISE_SD, CUT = 0.10, 0.10
FACTOR = {"brinfo_bias": 1.10, "brinfo_biasdown": 0.90}
GAMES = Path(os.getenv("FOLLOWUP_GAMES", ROOT / "followup/runs/games"))
FAMILY = os.getenv("FOLLOWUP_FAMILY", "")


def take(argv: list, flag: str, choices) -> str | None:
    if flag not in argv:
        return None
    i = argv.index(flag)
    value = argv[i + 1]
    del argv[i : i + 2]
    if value not in choices:
        sys.exit(f"{flag} must be one of {', '.join(choices)}")
    return value


ARM = take(sys.argv, "--followup-arm", ARMS) or sys.exit("--followup-arm is required")
STRATEGY = take(sys.argv, "--followup-strategy", branch.STRATEGIES)
SEED = int(sys.argv[sys.argv.index("--seeds") + 1])
RNG = random.Random(f"{ARM}-{SEED}")


def settings() -> str:
    """The name's settings tag: think0 for the Haiku 4.5 arms, think0_effort-medium for models with effort."""
    budget, effort = os.getenv("CLAUDE_THINKING_BUDGET"), os.getenv("CLAUDE_EFFORT")
    tags = [f"think{budget}" if budget is not None else "thinkdefault"]
    return "_".join(tags + ([f"effort-{effort}"] if effort else []))


def shown_best_response(mechanism, firm, prices, profits, alpha):
    """The brinfo line of succession/branch.py, with the number made noisy or biased."""
    rivals = [f for f in prices if f != firm]
    br = (
        branch.best_response(np.array([[prices[firm], *(prices[r] for r in rivals)]]) / alpha)[0, 0]
        * alpha
    )
    factor = math.exp(RNG.gauss(0.0, NOISE_SD)) if ARM == "brinfo_noise" else FACTOR[ARM]
    return f"- Platform estimate of my profit-maximizing price given the competitor's price: {round(br * factor, 2)}\n"


def cut(round_num: int, prices: dict) -> dict:
    if round_num > 10 and round_num % 10 == 0:
        name = RNG.choice(sorted(prices))
        prices[name] = max(1.0, prices[name] * (1 - CUT))
    return prices


class CutExperiment(common.Experiment):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.price_override = cut


_run_setting = common.run_setting


async def run_setting(**kw):
    if kw["n_firms"] != 2:
        sys.exit("the follow-up arms are duopolies")
    mechanism = "brinfo" if ARM.startswith("brinfo") else "hidden" if ARM == "hidden" else None
    if kw.get("mechanism") != mechanism:
        sys.exit(f"--followup-arm {ARM} needs --mechanism {mechanism or '(none)'}")
    every = int(ARM.removeprefix("forced")) if ARM.startswith("forced") else None
    if kw.get("forced_every") != every:
        sys.exit(f"--followup-arm {ARM} needs --forced-every {every or '(none)'}")
    family = f"{FAMILY}_" if FAMILY else ""
    kw["experiment_name"] = f"duopoly_setting_P1_mem100_{family}{ARM}_{settings()}_seed{kw['seed']}"
    kw["runs_dir"] = GAMES
    return await _run_setting(**kw)


common.run_setting = run_setting
if STRATEGY:
    common.PROMPTS = {k: v + branch.STRATEGIES[STRATEGY] for k, v in common.PROMPTS.items()}
if ARM in FACTOR or ARM == "brinfo_noise":
    branch.mechanism_feedback = shown_best_response
elif ARM == "cut10":
    common.Experiment = CutExperiment

if __name__ == "__main__":
    common.main_from_cli(2, "Follow-up duopoly arms (after the sprint review)")
