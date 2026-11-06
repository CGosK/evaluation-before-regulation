"""
One duopoly game under a wave-5 platform rule (followup/WAVE5_PLAN.md; not part of the submission). The sprint
harness runs unchanged: the rule reaches it only through the experiment's own hooks (hide_rivals, feedback,
price_override), set when the experiment is built. Overridden prices are marked by the harness itself.

Usage:  .venv/bin/python followup/platform_game.py --rule NAME_OR_FILE <experiments_synthetic/duopoly.py flags>
Writes: $FOLLOWUP_GAMES/2_agents/<timestamp>_duopoly_setting_P1_mem100_[<family>_]rule-<name>_<settings>_seed<s>/
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "followup"), str(ROOT), str(ROOT / "experiments_synthetic")]
import common  # noqa: E402
from platform_rules import load_rule  # noqa: E402

if "--rule" not in sys.argv:
    sys.exit("--rule is required")
i = sys.argv.index("--rule")
RULE = load_rule(sys.argv[i + 1])
del sys.argv[i : i + 2]
SEED = int(sys.argv[sys.argv.index("--seeds") + 1])
GAMES = Path(os.getenv("FOLLOWUP_GAMES", ROOT / "followup/runs/wave5/games"))
FAMILY = os.getenv("FOLLOWUP_FAMILY", "")


def settings() -> str:
    budget, effort = os.getenv("CLAUDE_THINKING_BUDGET"), os.getenv("CLAUDE_EFFORT")
    tags = [f"think{budget}" if budget is not None else "thinkdefault"]
    return "_".join(tags + ([f"effort-{effort}"] if effort else []))


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
    if kw["n_firms"] != 2 or kw.get("mechanism") or kw.get("forced_every"):
        sys.exit("a platform rule runs alone, in a duopoly with no other mechanism")
    family = f"{FAMILY}_" if FAMILY else ""
    kw["experiment_name"] = (
        f"duopoly_setting_P1_mem100_{family}rule-{RULE.name}_{settings()}_seed{kw['seed']}"
    )
    kw["runs_dir"] = GAMES
    return await _run_setting(**kw)


common.run_setting = run_setting
common.Experiment = RuleExperiment

if __name__ == "__main__":
    common.main_from_cli(2, "Follow-up duopoly under a platform rule (wave 5)")
