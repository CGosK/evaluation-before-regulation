# Wave 3 plan (written 4 November 2026, before any wave-3 game ran)

This is follow-up work, not part of the sprint submission (tag `submission-2026-10-25`). Waves 1 and 2 are reported in `README.md`. This file fixes the design, outcomes and decision rules before any game runs. Its SHA-256 is recorded in `runs/wave3/launch.txt` at launch, so any later edit would show. Anything analysed that is not listed here will be reported as exploratory.

## Why

In wave 2, neither remedy that stopped Haiku 4.5 moved Claude Opus 5.5:

| Arm | Opus 5.5 index |
| --- | ---: |
| Baseline | 0.76 |
| Exact best-response information | 0.73 |
| Forced 10% cut every 10 rounds | 0.67 |

Opus set the number it was shown in 10% of firm-rounds. Its notes give a reason. In one game, Firm A writes that the platform's estimates "ignore how B reacts to my price, and following them would invite more cuts from B".

Wave 3 asks whether any remedy brings Opus down when it needs no cooperation from the agent: holding one firm at the Nash price, as the submission's strongest remedy did.

## Setup

Every game is a fresh 100-round P1 duopoly of Claude Opus 5.5, with the remedy on from round 1, through `duopoly_followup.py` and headless Claude Code on the subscription.

The settings are wave 2's for Opus:

- effort medium;
- `CLAUDE_THINKING_BUDGET=0` and `MAX_THINKING_TOKENS=0`.

In wave 2, Opus still thought on 95% of calls with these settings, with a median of 143 tokens. Wave 3 keeps them so its games compare with wave 2's baseline, and reports the share of calls with thinking again.

A game's seed fixes only the platform's random choices. The outcome is Table 4's market index over rounds 51–100, where 0 is Nash and 1 is monopoly. A game "ends high" if its index is above 0.3.

## Arms

| Stage | Arm | Rule | Seeds | Games |
| --- | --- | --- | --- | ---: |
| A | baseline | no remedy | 11–15 | 5 |
| A | `forced10` | every 10 rounds after round 10, one firm chosen at random is held at its Nash price for that round | 1–10 | 10 |
| B | `forced5` | the same every 5 rounds after round 10 | 1–10 | 10 |

`forced10` is the submission's forced-Nash rule (`--forced-every 10` in `experiments_synthetic/common.py`), unchanged. It took Haiku 4.5 from 1.09 to 0.00. `forced5` is the same rule at twice the frequency.

Together with wave 2's 10% cut, the arms separate two questions:

- **Size:** `forced10` against wave 2's `cut10`, both every 10 rounds.
- **Frequency:** `forced5` against `forced10`, both to Nash.

**Stage B rule.** Stage B runs only if `forced10`'s mean index is above 0.3, that is, if Opus still colludes on average under it. Otherwise I report stage A and stop.

## Comparisons

The baseline is Opus 5.5's 15 baseline games:

- the 10 from wave 2;
- the 5 run here, interleaved with `forced10`.

Each remedy is compared with these 15 games, using the same measures as wave 2:

- the mean index;
- the share of games that end high;
- the effect, with a two-sample permutation test.

Holm's correction runs over the remedies actually run: one or two.

**Descriptive measures, fixed now but not tested:**

- each game's index, and the index over rounds 91–100;
- the first 10-round block whose mean index falls below 0.1, as in wave 1;
- after each forced round, the rival's next price change: its median, and the share of rivals cutting by 5% or more;
- the 5 new baseline games against wave 2's 10, as a drift check;
- the share of calls with thinking.

## Notes analysis (no new games)

This uses wave 2's exact-information games, plus the submission's Haiku 4.5 exact-information games. It is exploratory.

- For each model, the share of firm-rounds whose notes (observations, plans, insights) mention the platform's estimate.
- Firm A's notes at round 30 of each Opus 5.5 and Sonnet 5.5 game, written verbatim to `out/wave3_notes.md`. I had already read round 30 of one Opus game (seed 9, quoted above) when I chose it. The other 19 were unread.

## Code before launch

- **`duopoly_followup.py`:** add the arms `forced10` and `forced5`. They pass `--forced-every` through to the harness, and stop if the flag doesn't match the arm.
- **`run_wave3.py`:**
  - runs stage A, or stage B, in `runs/wave3/`, with wave 2's environment;
  - records this plan's and the code's hashes in `launch.txt`.
- **`wave3_results.py`:** the comparisons and descriptive measures above, plus the notes analysis.
- **Check before launch:** one 21-round stub game per new arm on Haiku 4.5. Each must record forced rounds in the right places: round 20 for `forced10`; rounds 15 and 20 for `forced5`. The stubs are not results.

## Usage

The guard runs as in wave 2: every game pauses when the 5-hour window reaches 90% or the weekly window reaches 80%, until that window resets. It also pauses if credits are in use.

In wave 2, an Opus call cost about $0.059 at notional API prices. Stage B's 10,000 calls moved the weekly window by about 46 points. On that basis:

| | Opus games | Calls | Weekly window |
| --- | ---: | ---: | --- |
| Stage A | 15 | 3,000 | about 20 points |
| Stage B | 10 | 2,000 | about 13 points |

Each 5-hour window fits about 2,000 Opus calls, so stage A spans two windows.

Stage A starts on 4 November, with the weekly window at 61%. If the weekly window reaches the guard's 80% before stage A ends, the remaining games wait for the weekly reset on Monday 9 November at 21:00 UTC (11:00 HST).

## Not in this wave

- **Opus with thinking fully off.** That needs the API key, which costs money, so it is Chris's call.
- **More Sonnet 5.5 games.**
- Other markets, prompts or numbers of firms.
