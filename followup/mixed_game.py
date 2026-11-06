"""
One mixed-model duopoly (followup/WAVE8_PLAN.md; not part of the submission). The sprint harness runs
unchanged, except that each firm gets its own Claude Code provider for the model named for its slot.

Usage:  .venv/bin/python followup/mixed_game.py --models MODEL_A MODEL_B --name TAG <duopoly flags>
Writes: $FOLLOWUP_GAMES/2_agents/<timestamp>_duopoly_setting_P1_mem100_mixed-<TAG>_[brinfo_]think0_seed<s>/
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "followup"), str(ROOT), str(ROOT / "experiments_synthetic")]
import common  # noqa: E402
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
GAMES = Path(os.getenv("FOLLOWUP_GAMES", ROOT / "followup/runs/wave8/games"))


class MixedAgent(common.LLMAgent):
    def __init__(self, name, **kw):
        kw["provider"] = make_provider("claude-code", model=MODELS[name])
        super().__init__(name, **kw)


_run_setting = common.run_setting


async def run_setting(**kw):
    if kw["n_firms"] != 2 or kw.get("forced_every") or kw.get("nash_open"):
        sys.exit("a mixed game is a duopoly with at most a mechanism")
    mech = f"{kw['mechanism']}_" if kw.get("mechanism") else ""
    budget = os.getenv("CLAUDE_THINKING_BUDGET")
    kw["experiment_name"] = (
        f"duopoly_setting_P1_mem100_mixed-{TAG}_{mech}think{budget}_seed{kw['seed']}"
    )
    kw["runs_dir"] = GAMES
    return await _run_setting(**kw)


common.run_setting = run_setting
common.LLMAgent = MixedAgent

if __name__ == "__main__":
    common.main_from_cli(2, "Follow-up mixed-model duopoly (wave 8)")
