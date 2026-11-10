"""
One mixed-model duopoly under a platform rule (followup/WAVE12_PLAN.md; not part of the submission): wave 8's
mixed_game.py, which gives each firm its own Claude Code provider, with wave 5's platform_game.py hooks for the
rule. The sprint harness runs unchanged.

Usage:  .venv/bin/python followup/mixed_rule_game.py --models MODEL_A MODEL_B --name TAG --rule NAME_OR_FILE
            <duopoly flags>
Writes: $FOLLOWUP_GAMES/2_agents/<timestamp>_duopoly_setting_P1_mem100_mixed-<TAG>_rule-<name>_think<b>_seed<s>/
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "followup"), str(ROOT), str(ROOT / "experiments_synthetic")]
import common  # noqa: E402
from platform_rules import load_rule  # noqa: E402

from src.agents.llm_providers import make_provider  # noqa: E402


def take(flag: str, n: int) -> list:
    if flag not in sys.argv:
        sys.exit(f"{flag} is required")
    i = sys.argv.index(flag)
    vals = sys.argv[i + 1 : i + 1 + n]
    del sys.argv[i : i + 1 + n]
    return vals


MODELS = dict(zip(common.FIRM_NAMES, take("--models", 2)))
TAG = take("--name", 1)[0]
RULE = load_rule(take("--rule", 1)[0])
SEED = int(sys.argv[sys.argv.index("--seeds") + 1])
GAMES = Path(os.getenv("FOLLOWUP_GAMES", ROOT / "followup/runs/wave12/games"))


class MixedAgent(common.LLMAgent):
    def __init__(self, name, **kw):
        kw["provider"] = make_provider("claude-code", model=MODELS[name])
        super().__init__(name, **kw)


class RuleExperiment(common.Experiment):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        rule = RULE(SEED)

        def override(round_num, prices):
            rule.round = round_num
            return rule.override(round_num, prices)

        self.hide_rivals = not rule.show_rivals
        self.feedback = rule.notice
        self.price_override = override


_run_setting = common.run_setting


async def run_setting(**kw):
    if kw["n_firms"] != 2 or kw.get("mechanism") or kw.get("forced_every") or kw.get("nash_open"):
        sys.exit("a mixed game under a rule is a duopoly with no other mechanism")
    budget = os.getenv("CLAUDE_THINKING_BUDGET")
    kw["experiment_name"] = (
        f"duopoly_setting_P1_mem100_mixed-{TAG}_rule-{RULE.name}_think{budget}_seed{kw['seed']}"
    )
    kw["runs_dir"] = GAMES
    return await _run_setting(**kw)


common.run_setting = run_setting
common.Experiment = RuleExperiment
common.LLMAgent = MixedAgent

if __name__ == "__main__":
    common.main_from_cli(2, "Follow-up mixed-model duopoly under a platform rule (wave 12)")
