"""
Continue a finished follow-up game past its last round (study 1, followup/WAVE10_PLAN.md; not part of the
submission). DIR must be a copy, as run_wave10.py --copy makes them. Its saved history becomes the experiment's
own, and the harness plays the rounds after it into the same folder. The game is rebuilt by
experiments_synthetic/common.py as it was first built, and a platform rule is hooked up as platform_game.py
does it. A rerun picks up from the last saved round.

Before any round is played, three checks must pass:
    rebuild      the rebuilt game's metadata equals the saved metadata, except times and length
    replay       every saved round's market data is rebuilt exactly from its prices, rule line included
    prompt       the next round's prompt holds the last round's market data, plans and insights, and no field
                 of the template depends on the game's length

Usage:  .venv/bin/python followup/continue_game.py DIR --rounds 200 [--rule NAME_OR_FILE] [--check]
"""

import argparse
import asyncio
import copy
import datetime
import json
import logging
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "followup"), str(ROOT), str(ROOT / "experiments_synthetic")]
import common  # noqa: E402
from platform_rules import load_rule  # noqa: E402

from src.utils.logger import setup_logger  # noqa: E402

TEMPLATE_FIELDS = {
    "prompt_prefix",
    "marginal_cost",
    "willigness_to_pay",
    "plans",
    "insights",
    "market_data",
}
UNCHECKED = {"start_time", "end_time", "summary", "num_rounds", "continued_from", "continued_at"}

ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
ap.add_argument("dir", type=Path)
ap.add_argument("--rounds", type=int, required=True)
ap.add_argument("--rule")
ap.add_argument("--check", action="store_true")
A = ap.parse_args()
DIR = A.dir.resolve()
META = json.loads((DIR / "metadata.json").read_text())
HISTORY = {
    firm: {int(t): o for t, o in rounds.items()}
    for firm, rounds in json.loads((DIR / "results.json").read_text()).items()
}
LAST = min(max(rounds) for rounds in HISTORY.values())
FIRST_LENGTH = META.get("continued_from", META["num_rounds"])
RULE = load_rule(A.rule) if A.rule else None


def fail(msg: str):
    sys.exit(f"{DIR.name}: {msg}")


def drop_file_handlers(logger: logging.Logger):
    for h in [h for h in logger.handlers if isinstance(h, logging.FileHandler)]:
        h.close()
        logger.removeHandler(h)


class Continued(common.Experiment):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        if RULE:
            rule = RULE(META["seed"])

            def override(round_num, prices):
                rule.round = round_num
                return rule.override(round_num, prices)

            self.hide_rivals = not rule.show_rivals
            self.feedback = rule.notice
            self.price_override = override

    def check_rebuild(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.storage.base_dir = Path(tmp)
            self._setup_experiment()
            rebuilt = json.loads(json.dumps(self.storage.load_metadata()))
            drop_file_handlers(self.logger)
        diff = [
            k
            for k in set(rebuilt) | set(META)
            if k not in UNCHECKED and rebuilt.get(k) != META.get(k)
        ]
        if diff:
            fail(f"rebuild differs from the saved metadata in {sorted(diff)}")

    def check_replay(self):
        live, self.history = self.history, copy.deepcopy(HISTORY)
        for t in range(1, LAST + 1):
            prices = {firm: float(self.history[firm][t]["chosen_price"]) for firm in self.history}
            order = [(agent.name, agent.env_index) for agent in self.agents]
            self.environment.set_round(t)
            q, pi = self.environment.compute_quantities_and_profits(order, prices)
            self._store_environment_outputs(t, prices, q, pi)
            for firm in prices:
                if self.history[firm][t]["market_data"] != HISTORY[firm][t]["market_data"]:
                    fail(f"round {t}, {firm}: rebuilt market data differs from the saved")
        self.history = live

    def check_prompt(self) -> dict:
        prompts = {}
        for agent in self.agents:
            fields = set(self.prompt_manager._extract_prompt_fields(agent.prompt_template))
            if not fields <= TEMPLATE_FIELDS:
                fail(f"template fields {sorted(fields - TEMPLATE_FIELDS)} not checked")
            p = self.prompt_manager.generate_prompt(agent, self.history[agent.name], LAST + 1)
            last = self.history[agent.name][LAST]
            for part in (f"Round {LAST}\n{last['market_data']}", last["plans"], last["insights"]):
                if part not in p:
                    fail(f"{agent.name}'s round {LAST + 1} prompt is missing {part[:40]!r}")
            prompts[agent.name] = p
        return prompts

    async def run(self):
        if not META.get("end_time") and "continued_from" not in META:
            fail("not a finished game")
        if LAST < FIRST_LENGTH or LAST >= self.num_rounds:
            fail(f"saved rounds end at {LAST}; nothing to play up to {self.num_rounds}")
        self.check_rebuild()
        self.storage.experiment_path = DIR
        self.history = copy.deepcopy(HISTORY)
        self.check_replay()
        prompts = self.check_prompt()
        print(
            f"{DIR.name}: rebuild, replay of rounds 1-{LAST} and round-{LAST + 1} prompt OK "
            f"({', '.join(f'{k} {len(v):,} chars' for k, v in prompts.items())})"
        )
        if A.check:
            return
        meta = dict(META, num_rounds=self.num_rounds, end_time=None, summary=None)
        meta.setdefault("continued_from", FIRST_LENGTH)
        meta.setdefault("continued_at", []).append(datetime.datetime.now().isoformat())
        self.storage.save_metadata(meta)
        self.logger = setup_logger(log_file=DIR / "log.txt")
        for agent in self.agents:
            agent.logger = self.logger
        for t in range(LAST + 1, self.num_rounds + 1):
            self.logger.info(f"--- Round {t} ---")
            await self._run_round(t)
        self._finalize_experiment()


async def main():
    models = set(META["agents_models"].values())
    providers = set(META["agents_providers"].values())
    if len(models) != 1 or len(providers) != 1 or "_P1_" not in META["name"]:
        fail("only one-model P1 games can be continued")
    common.Experiment = Continued
    await common.run_setting(
        n_firms=META["num_agents"],
        prompt="P1",
        alpha=META["agent_environment_mapping"]["Firm A"]["alpha"],
        rounds=A.rounds,
        seed=META["seed"],
        memory_length=META["agents_memory_length"]["Firm A"],
        shuffle_names=META["shuffle_names"],
        temperature=META["agents_temperature"]["Firm A"],
        provider_kind=providers.pop(),
        model=models.pop(),
        experiment_name=META["name"],
        runs_dir=DIR.parent.parent,
        plot_every=0,
    )
    if not A.check:
        print("✅ done\n")


if __name__ == "__main__":
    asyncio.run(main())
