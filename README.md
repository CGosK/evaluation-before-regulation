# Evaluation Before Regulation

Code, data and paper for *Evaluation Before Regulation: How LLM Pricing Agents Come to Collude, and What
Stops It* (Chris Graham, AI Collusion Research Sprint, Apart Research, October 2026).

**Paper:** [`theory/PAPER_DRAFT.pdf`](theory/PAPER_DRAFT.pdf) (source: [`theory/PAPER_DRAFT.md`](theory/PAPER_DRAFT.md))

LLM pricing agents reach prices above the competitive level without being told to. I tested whether they hold
those prices the way a cartel does, by punishing whoever cuts. They do not. When one agent was forced to cut,
its rival ignored the cut or followed it down. The high prices come from agents that start high and learn too
slowly to leave. The diagnosis picks the remedy. Telling each agent its best response, or holding one agent at
the competitive price for a single round every ten, prevented collusion in every Claude Haiku 4.5 game, with
two firms and with four. Hiding rivals' prices, a standard anti-cartel remedy, did not prevent it, and
resetting the agents' memory made it worse. The agents' own talk of coordination was more common in the
markets that ended competitive, so monitors that read their reasoning ranked the markets backwards.

## What predates the sprint

| Part | Origin |
| --- | --- |
| The pricing-game harness: `src/`, `experiments_synthetic/`, `pyproject.toml`, `LICENSE` | Peist, Romero & Sauer (2025), [luciasauer/algorithmic_pricing_llms](https://github.com/luciasauer/algorithmic_pricing_llms), MIT licence. Taken from the sprint's starter repository, [poseidon-research/collusion_hackathon](https://github.com/poseidon-research/collusion_hackathon), which trimmed it to run on a laptop and routes model calls through its `poseidon_compute` package. |
| The 210 Mistral-Large-2411 games in `data/results/all_experiments.parquet` | Peist, Romero & Sauer (2025), via the starter repository |
| `poseidon_compute` (installed as a dependency, not copied here) | The starter repository's `util/` folder |

Everything else was written during the sprint (October 23–25, 2026):

- all of `theory/` (analyses, outputs, paper) and `succession/` (runners and every Claude run);
- changes to four harness files:
    - `src/agents/llm_providers.py`: a headless Claude Code provider, the Anthropic API provider, the per-call
      usage log, waiting out usage limits, and a shared pause file;
    - `src/agents/LLM_agent.py`: structured-output schemas and per-provider retry limits;
    - `src/experiment/experiment.py`: price overrides (forced rounds), memory resets and hidden rival prices;
    - `experiments_synthetic/common.py`: the command-line flags for those interventions;
- the `claude` extra in `pyproject.toml`.

## Reproduce the tables and figures

Every number in the paper is computed from the saved runs in this repository. Recomputing them makes no model
calls. You need [uv](https://github.com/astral-sh/uv) and Python 3.11+.

```bash
uv sync --extra analysis
```

Then run any of the scripts below with `uv run --extra analysis python <script>`. Each one writes to
`theory/out/`.

| Paper | Script |
| --- | --- |
| §4.1, Figure 1 (SBR model) | `theory/bandit.py` |
| §4.1 (Fish et al. regression) | `theory/fish_replication.py` |
| Table B1, Figure B1 | `theory/retro.py` |
| Table 2, Figure 2 (forced cut) | `theory/frontier_results.py` |
| §3 and Appendix B (decision rule on scripted firms) | `theory/forced_cut.py` |
| Appendix B (own-rule null) | `theory/own_rule_null.py` |
| §4.2 (following cuts and raises) | `theory/following_test.py` |
| §4.3 (keyword monitor) | `theory/notes_monitor.py` |
| §4.3 (LLM judge, from saved scores) | `theory/llm_monitor.py --score-only` |
| Table 3, Figure 3 (removal) | `theory/mechanism_results.py` with `haiku`, `haiku45` and `haiku45_enforcer2`, then `theory/remedies_existing.py` |
| Table 4, Figure 4 (prevention) | `theory/prevention45_results.py`, `theory/prevention45_results.py --firms 4` |
| §4.5 (deference) | `theory/deference_test.py` |
| Table C1, Figure C1 (P2 prompt; SBR platform rules) | `theory/remedies_existing.py`, `theory/policy_sim.py` |
| Appendix C (Haiku 5.5 from round 1) | `theory/prevention_results.py` |

To check the paper against the outputs (81 checks, each looking for the exact printed string):

```bash
uv run --extra analysis python theory/check_paper.py
```

To build the PDF (needs Google Chrome installed):

```bash
uv run --with markdown --with playwright --with pypdf python theory/build_paper.py
```

## Rerun the experiments

These make model calls. The Claude runs go through headless Claude Code (`--provider claude-code`) on a Claude
subscription login; `CLAUDE_CONFIG_DIR` picks which login. The Mistral games and the `poseidon_compute` route
use the starter repository's inference config (a `compute.env` with a Nebius or OpenRouter key; see its
README).

| Run | Command | Calls |
| --- | --- | --- |
| Forced cut and removal, from 8 high-price Mistral states | `succession/frontier.py` (see its docstring and `theory/FRONTIER_TEST.md`; the enforcer runs' commands are in `succession/runs/frontier/*.launch.txt`) | 432 (Fable, two arms) to about 1,600 per model |
| Prevention, Haiku 4.5 duopolies (9 arms) | `succession/prevention45.py` | 32,925 |
| Prevention, Haiku 4.5 with four firms | `succession/prevention45.py --firms 4` | 12,000 |
| LLM judge of the agents' notes | `theory/llm_monitor.py` | 110 |

Claude models cannot be seeded, so a rerun gives new draws, not the same games. A game's seed fixes only the
platform's own random choices, such as which firm a forced round holds.

## Data

- `data/results/all_experiments.parquet`: the 210 Mistral games (predates the sprint).
- `succession/runs/frontier/<model>/`: the forced-cut and removal arms, one JSON line per firm-round
  (`<state>_<arm>.jsonl`), with `usage.jsonl` logging every call's tokens and cost.
- `succession/runs/screen/`, `prevention45/`, `prevention45_4firm/`: the Haiku 4.5 prevention games
  (`games/<run>/results.json`, `metadata.json`), with run logs and usage logs.
- `succession/runs/prevention/`: the Haiku 5.5 games of Appendix C.
- `succession/runs/llm_monitor/`: the LLM judge's scores.
- `theory/out/`: every output behind the tables and figures.

## Notes

- `theory/FINDINGS.md`, `theory/FRONTIER_TEST.md`, `theory/FRONTIER_RESULTS.md` and `succession/DESIGN.md` are
  working notes written as the sprint went. Where they differ from the paper, the paper is current.
- Info hazard: `succession/branch.py` contains an instruction that tells agents to punish price cuts (the
  `enforcer` strategies). It was used only as a positive control in simulation, and it adds nothing beyond the
  strategies in the economics literature.
- Everything here is under the MIT licence (`LICENSE`): the harness is copyright Peist, Romero & Sauer, and
  the sprint additions are copyright Chris Graham.
