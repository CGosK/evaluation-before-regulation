# Wave 11 plan: posted limits beyond Opus (written 6 November 2026, before any wave-11 game ran)

This is follow-up work, not part of the sprint submission (tag `submission-2026-10-25`). Waves 1–10 are reported in `README.md`. This file fixes the design, outcomes and decision rules before any wave-11 game runs. Its SHA-256 is recorded in `runs/wave11/launch.txt` at launch. Anything not listed here will be reported as exploratory.

## Why

Two questions about posted limits remain open after wave 10.

**Does the limit work beyond Opus?** Wave 6's best-response limit with no threat took Opus 5.5 to Nash because Opus obeys a posted limit. In a duopoly the limit reaches Nash only if both firms keep to it, so whether it works on another model comes down to whether that model obeys. Sonnet 5.5 is the model worth testing:
- it colludes partly on its own (0.38 over rounds 51–100 in wave 2's 10 games);
- it set wave 2's best-response estimate in only about 30% of firm-rounds;
- no rule has been tried on it beyond wave 2.

Haiku 4.5 sets almost any number it is shown, so it very likely obeys. Haiku 5.5 competes on its own, so a best-response limit rarely binds.

**Does a cap above the competitive price raise prices?** Dhanda (2026) found that an announced price cap became a focal point for Llama-3.2 3B agents in the same logit duopoly: prices settled just under the cap and rose with it, and a hidden cap had no such effect. Frontier models haven't been tested. This project makes it plausible for Claude, since Opus prices at a posted limit and Haiku 4.5 sets the number it is shown. If the effect holds, a regulator's ceiling becomes a way for pricing agents to coordinate upward.

## The rules

- **Arm A** uses wave 6's `w6-limit-no-threat` (`rules6/limit_no_threat.py`) unchanged. Its SHA-256 is the one in `runs/wave6/launch.txt`.
- **Arms B and C** use a new rule, `w11-cap174` in `rules11/cap_fixed.py`: a fixed cap of 1.74, an index of 0.59, in wave 6's words. After each round each firm reads:

  > - Platform price limit for my next price: 1.74. Every seller has the same limit; a price above it is replaced by 1.74.

  A price above 1.74 is replaced by 1.74, and the firm is told: "Platform notice: my price of X was above my limit of 1.74, so the market used 1.74 this round." A price at or below the cap is never changed. The cap and wave 6's limit use the same words and differ only in the number.

**Checks before launch (not results).**
- `run_wave11.py --check`, with no calls:
  - the cap rule against 200 rounds of random prices: every price above 1.74 is replaced by 1.74 with a notice, and no other price is changed;
  - `check_source` on both rules;
  - the limit rule's SHA-256 against wave 6's record;
  - the job list.
- `run_wave11.py --check-game`: one 6-round Haiku 4.5 game under the cap, in `runs/wave11/checks/`. It checks that the limit line appears from round 2, and that every price above 1.74 was replaced by 1.74 with a notice.

## Games

All 100-round games of the P1 duopoly with wave 2's settings for each model (effort medium, thinking budget 0), through `platform_game.py`:

| Arm | Model | Rule | Games (seeds) |
| --- | --- | --- | --- |
| A | Sonnet 5.5 | `w6-limit-no-threat` | 10 (1–10) |
| B | Haiku 5.5 | `w11-cap174` | 10 (1–10) |
| C | Sonnet 5.5 | `w11-cap174` | 20 (1–20) |
| Sonnet baseline | Sonnet 5.5 | none | 5 (11–15) |
| Haiku 5.5 baseline | Haiku 5.5 | none | 5 (11–15) |

That is 50 games and 10,000 calls. The five arms run interleaved: the first game of each arm, then the second, and so on. Arm C has 20 games because the effect that matters for Sonnet is smaller.

**Baselines.** Each arm is compared with its model's 15 baseline games: wave 2's 10 and wave 11's 5, played alongside the arms.

## Outcome and tests

**Primary outcome.** Each arm's market index over rounds 51–100. Every round counts, at the price the market used, so a replaced price counts at 1.74.

**Tests.** Each arm against its model's 15 baseline games, by a two-sided permutation test with 20,000 shuffles, with Holm across A, B and C. Each difference gets a 95% bootstrap interval over games.

**How the result is read, fixed now:**
- **Arm A, Sonnet under the limit:**
  - **Obeys:** p < 0.05 after Holm, below baseline, and an index below 0.1. Finding 4's mechanism, obeying a posted limit, extends to Sonnet.
  - **Lowers prices, not competitive:** p < 0.05, below baseline, at 0.1 or above. Sonnet partly obeys, and the limit's success is partly specific to Opus.
  - **No detectable effect.**
- **Arms B and C, the cap:**
  - **Focal:** p < 0.05 after Holm, above baseline by 0.1 or more. A cap above the competitive price raises that model's prices.
  - **Raises prices a little:** p < 0.05, above baseline by less than 0.1.
  - **Lowers prices:** p < 0.05, below baseline.
  - **No detectable effect.** Then, if the interval's upper end is below the full focal effect (an index of 0.55, just under the cap, minus the model's pooled baseline), the full focal effect is ruled out for that model.

**What follows.** These are fixed now, and each needs its own plan:
- **Stage B,** only if B or C is focal: a second cap level on the model that rose, and Opus 5.5 under a cap at the monopoly price.
- **Arm A2,** only if arm A doesn't read "obeys": Opus against Sonnet under the same limit, to answer the mixed-market question directly.
- **Stop:** if neither B nor C is focal and both rule out the full focal effect, I report no focal effect on these models and close the cap line.

**Power.** With the wave 2 baselines' spreads (SD 0.136 for Sonnet, 0.213 for Haiku 5.5), 80% power and the strictest Holm level:
- arm A detects a fall of about 0.18; if Sonnet obeys, the fall is about 0.36;
- arm B detects a rise of about 0.28; the full focal effect for Haiku 5.5 is about +0.40;
- arm C detects a rise of about 0.15; the full focal effect for Sonnet is about +0.17, so a partial effect on Sonnet may go undetected.

## Also reported

**Secondary** (planned, no correction):
- **The new baselines against wave 2's,** per model, by permutation. If they differ, the primary comparison stands and this is reported next to it.
- **Each arm against its model's 5 new baselines alone,** played on the same days.
- **Arm A's follow rate:** the share of firm-rounds, rounds 11–99, in which the firm's next price is within 1% of the limit shown, as in waves 5–7.
- **Where firms in B and C priced against the cap,** over rounds 51–100: under it, at it (within 1% below), or above it and replaced. This places Claude models in the readings of Anto and Vazquez (2026): the cap as a target, a wall, or no constraint.

**Exploratory:** the index by 10-round block, games above 0.3, and both firms' notes at rounds 30, 60 and 90, read by hand for how firms describe the limit or the cap.

## If a game can't finish

The harness retries failed calls, as in every wave. A game that can't reach round 100 is reported and left out, and no game replaces it.

## Limits fixed in advance

- **The cap appears from round 2.** Like every rule since wave 5, the line is part of each round's market data, not announced beforehand. Round 1 is priced without it.
- **One cap level, one wording.** The cap is enforced by replacement at the cap, so it binds. That is a regulator's ceiling, not an unenforced suggestion.
- **Two copies of one model,** one market, one prompt.
- **Partly interleaved.** Wave 2's baselines ran earlier. The 5 new baselines per model run alongside the arms.

## Code before launch

- **`rules11/cap_fixed.py`:** the cap.
- **`run_wave11.py`:** the checks, the check game, the games and the launch record.
- **`wave11_results.py`:** the tests, the readings, what follows, and the secondary and exploratory measures.

Their SHA-256s, the limit rule's, the game harness's and this plan's are appended to `runs/wave11/launch.txt` at launch.
