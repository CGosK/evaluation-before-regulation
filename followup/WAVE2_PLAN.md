# Wave 2 plan (written 3 November 2026, before any wave-2 game ran)

This is follow-up work, not part of the sprint submission (tag `submission-2026-10-25`). Wave 1 is reported in `README.md`. This file fixes the design, outcomes and decision rules before any game runs. Its SHA-256 is recorded in `runs/wave2/launch.txt` at launch, so any later edit would show. Anything analysed that is not listed here will be reported as exploratory.

## Setup

Every game is a fresh 100-round P1 duopoly with the remedy on from round 1, run through `duopoly_followup.py` and `run_wave2.py`. Calls go through headless Claude Code on the subscription.

Settings:

- Extended thinking is off for every model, the setting under which Haiku 4.5 colluded. The launcher also sets `MAX_THINKING_TOKENS=0`, because 3-round stub games showed Opus 5.5 still thinking a little without it.
  - Haiku 5.5 reported 300–1,800 thinking tokens per call even with both settings, and I found no way to switch that off through Claude Code.
  - So Haiku 5.5's arms are compared only with its own baseline, under the same settings.
- Effort is medium for the models that have it, as in the paper's Haiku 5.5 and Fable runs.
- A game's seed fixes only the platform's own random choices.

The outcome is Table 4's market index over rounds 51–100, where 0 is Nash and 1 is monopoly. A game "ends high" if its index is above 0.3.

## Stage A

| Family | Model | Arm | Games |
| --- | --- | --- | ---: |
| `opus55` | Claude Opus 5.5 | baseline | 5 |
| `sonnet55` | Claude Sonnet 5.5 | baseline | 5 |
| `haiku55` | Claude Haiku 5.5 | baseline | 10 |
| `haiku55` | Claude Haiku 5.5 | best response biased +10% | 10 |
| `haiku45` | Claude Haiku 4.5 | best response biased −10% | 10 |
| `haiku45enf` | Claude Haiku 4.5, told to enforce (the paper's `enforcer2`) | baseline | 10 |
| `haiku45enf` | Claude Haiku 4.5, told to enforce | best response biased +10% | 10 |

### The screen for a second colluding model

**Rule.** A model colludes on its own if at least 3 of its 5 baseline games end high. For comparison, 14 of Haiku 4.5's 20 baseline games did.

**What follows.** Stage B runs on every model that passes. If neither passes, I report that and run no stage B.

### The bias arms

If agents set the shown number exactly, the market settles at a predictable index: 0.62 at +10% and −0.50 at −10%. At −10%, both firms earn less than at Nash. Each arm is compared with its own baseline.

| Arm | Compared with | Question |
| --- | --- | --- |
| Haiku 5.5, +10% | the 10 fresh Haiku 5.5 baseline games | Can a platform's number create high prices among agents that compete on their own? |
| Haiku 4.5, −10% | the submission's 20 Haiku 4.5 baseline games | Do agents follow advice that costs them profit? |
| Haiku 4.5 told to enforce, +10% | the 10 enforcer baseline games | Does a strategic instruction weaken deference? |

**Measures for each arm:**

- the mean index;
- the share of games that end high;
- the effect against its baseline, with a two-sample permutation test and Holm's correction over these three comparisons;
- deference: the share of firm-rounds 11–99 whose next price is within 1% of the number shown, and within 1% of the true best response.

## Stage B (only for models that pass the screen)

| Arm | Games |
| --- | ---: |
| baseline, seeds 6–10 (joining the screen's 5) | 5 |
| best-response information, exact | 10 |
| forced 10% cut every 10 rounds | 10 |

Each remedy is compared with that model's 10 baseline games, with the same test and Holm's correction over its two remedies.

## Usage

The guard (`usage_guard.py`) pauses every game when the 5-hour window reaches 90% or the weekly window reaches 80%, until that window resets. The weekly cap leaves headroom for Chris's own work. It also pauses if a call would be paid from usage credits.
