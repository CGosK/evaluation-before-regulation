# Wave 12 plan: the limit in a mixed market, and the cap's split (written 9 November 2026, before any wave-12 game ran)

This is follow-up work, not part of the sprint submission (tag `submission-2026-10-25`). Waves 1–11 are reported in `README.md`. This file fixes the design, outcomes and decision rules before any wave-12 game runs. Its SHA-256 is recorded in `runs/wave12/launch.txt` at launch. Anything not listed here will be reported as exploratory.

It is the last planned wave. After it I write up and stop running waves, unless a cap brought in on a running market turns out to raise prices (see [What follows](#what-follows)).

## Why

Wave 11 left two questions.

**Part 1: does the limit hold in a mixed market?** Wave 11's plan fixed arm A2 in advance, to run if Sonnet 5.5 didn't obey wave 6's limit. Sonnet's reading was "lowers, not competitive", so A2 runs here.
- Opus 5.5 set the limit in 100% of firm-rounds in wave 6. Sonnet set it in 50% in wave 11, keeping it in 6 games and ignoring it in 4 (exploratory).
- Under the limit, Opus prices at its best response to Sonnet's price, which makes it a follower. If Sonnet keeps the limit too, the market goes to Nash. If Sonnet ignores it and leads, the market tends to the leader-follower outcome, an index of about 0.26 (the note's §5).
- No Opus–Sonnet market has been run, so this wave adds one with no rule.

**Part 2: does the cap's split hold, and does it come from the opening?** Under wave 11's fixed cap at 1.74, Sonnet's games split (exploratory): 7 of 20 held the cap from round 3, and 10 of 20 ended below every baseline game. Every cap market opened at the cap, because both opening prices, about 2.75, were replaced by 1.74.
- **Does the split replicate?** It was found after looking, so it needs fresh games.
- **Does it need the opening?** A cap brought in at round 31, after the opening, separates the cap from the start it gave every market.
- **Does a cap on a running market pull prices up?** The late cap also asks the realistic form of Dhanda's (2026) question: a regulator usually caps a market that is already running.

## The rules

- **A2** uses wave 6's `w6-limit-no-threat` (`rules6/limit_no_threat.py`) unchanged. Its SHA-256 is the one in `runs/wave6/launch.txt`.
- **C2** uses wave 11's `w11-cap174` (`rules11/cap_fixed.py`) unchanged. Its SHA-256 is the one in `runs/wave11/launch.txt`.
- **D** uses a new rule, `w12-cap174-from31` in `rules12/cap_from31.py`. Nothing happens in rounds 1–30. Round 30's market data carries the cap line for the first time, in wave 11's words:

  > - Platform price limit for my next price: 1.74. Every seller has the same limit; a price above it is replaced by 1.74.

  From round 31, a price above 1.74 is replaced by 1.74, and the firm is told. From round 31 the rule is exactly wave 11's cap.

The mixed games run through `mixed_rule_game.py`. It is wave 8's `mixed_game.py`, which gives each firm its own model, with wave 5's rule hooks from `platform_game.py`. The sprint harness runs unchanged. Opus is Firm A in odd seeds, as in wave 8.

**Checks before launch (not results).**
- `run_wave12.py --check`, with no calls:
  - the late cap against 20 games of random prices: no change and no line before round 30, the line from round 30, and from round 31 the same prices and lines as wave 11's cap;
  - `check_source` on the three rules;
  - the two reused rules' SHA-256s against their waves' records;
  - the job list.
- `run_wave12.py --check-game`, in `runs/wave12/checks/`:
  - one 33-round Haiku 4.5 game under the late cap: the line only from round 30, and every replacement from round 31, to 1.74, with a notice;
  - a 3-round Opus–Sonnet game under the limit in each slot order: each slot's model, effort medium for both, and the limit line in every firm-round.

## Games

All are 100-round games of the P1 duopoly with wave 2's settings (effort medium, thinking budget 0):

| Arm | Market | Rule | Games (seeds) |
| --- | --- | --- | --- |
| mixed | Opus 5.5 against Sonnet 5.5 | none | 10 (1–10) |
| A2 | Opus 5.5 against Sonnet 5.5 | `w6-limit-no-threat` | 10 (1–10) |
| C2 | Sonnet 5.5 | `w11-cap174` | 20 (21–40) |
| D | Sonnet 5.5 | `w12-cap174-from31` | 20 (1–20) |
| Sonnet baseline | Sonnet 5.5 | none | 5 (16–20) |

That is 65 games and 13,000 calls, 2,000 of them Opus. The arms run interleaved: the first game of each, then the second, and so on.

**Baselines.** Part 1 compares A2 with the mixed arm. Part 2 compares with Sonnet's 20 baseline games: wave 2's 10, wave 11's 5 and these 5.

## Outcomes and tests

**Primary outcome.** The market index over rounds 51–100, every round at the price the market used.

**Part 1, one test.** A2 against the mixed arm, by a two-sided permutation test with 20,000 shuffles, with a 95% bootstrap interval. It is its own family, so it has no correction.
- **Holds:** p < 0.05, below the mixed arm, and an index below 0.1. An obedient firm brings a partly obedient one to competitive prices.
- **Partway:** p < 0.05, below the mixed arm, at 0.1 or above. The limit works in a mixed market only as far as the less obedient firm lets it.
- **No detectable effect.** (A rise would read "raises prices".)

**Part 2, three tests, with Holm across them.**
- **T2, does the split replicate?** The spread of C2's game indices against the 20 baseline games: a two-sided permutation test of the log ratio of their standard deviations, with 20,000 shuffles.
  - **Replicates:** p < 0.05 after Holm, C2 wider, at least 3 games that held the cap (every market price over rounds 51–100 at 1.74), and at least 3 below 0.2.
  - **Wider, but not split:** p < 0.05, C2 wider, and the counts fall short.
  - **Doesn't replicate:** otherwise, or narrower than baseline.
- **T3, does the split need the opening?** Games that held the cap, D against C2, by Fisher's exact test, two-sided.
  - **The opening drives the split:** p < 0.05 after Holm, and D holds fewer.
  - **The late cap holds more games:** p < 0.05, and D holds more.
  - **No detectable difference.**
- **T4, is a late cap focal?** D's index against the 20 baseline games, by a two-sided permutation test with 20,000 shuffles, with a 95% bootstrap interval.
  - **Focal:** p < 0.05 after Holm, above baseline by 0.1 or more.
  - **Raises prices a little:** p < 0.05, above baseline by less than 0.1.
  - **Lowers prices:** p < 0.05, below baseline.
  - **No detectable effect.** Then, if the interval's upper end is below the full focal effect (0.55 minus the baseline's mean), the full focal effect is ruled out.

### What follows

These are fixed now:
- **If T4 reads focal,** a cap brought in on a running market raises a frontier model's prices. That deserves its own short project, with several cap levels, Opus and non-Claude models, not a wave 13.
- **Otherwise, stop running waves.** I write up wave 12 and leave the follow-up as it stands.
- **A2 has no follow-on wave,** whatever it reads.

**Power,** from wave 11's games:
- **Part 1, 10 games against 10:** with a spread of 0.15–0.25 per game, it detects a difference of 0.19–0.31 with 80% power. If both firms end at Nash, the fall from a mixed market near 0.4 is large. If Sonnet leads and the market ends near 0.26, the fall may be too small to detect.
- **T2:** resampling wave 11's games, the power is above 95% at Holm's strictest level with 20 games, if the split is as large as in wave 11. Effects found after looking tend to shrink, so this is an upper bound.
- **T3 is the weakest test.** If D holds no game and C2 holds as many as wave 11's cap did (35%), the power is 57% at Holm's strictest level and 76% at the next. If D holds one game, it falls to 23–40%.
- **T4:** with a spread of 0.12–0.20 per game, it detects a rise of 0.12–0.20 at Holm's strictest level.

## Also reported

**Secondary** (planned, no correction):
- each model's own index in both mixed arms;
- each model's follow rate under A2, rounds 11–99, against Opus's 100% in wave 6 and Sonnet's 50% in wave 11;
- Sonnet's own index under A2 against wave 11's Sonnet-only games under the limit (across waves);
- C2's mean index against the baseline, which repeats wave 11's planned test;
- D's spread against the baseline;
- the 5 new baseline games against the earlier 15;
- where firms priced against the cap over rounds 51–100 in C2 and D: under it, at it (within 1% below), or above it and replaced;
- how many D games had a price above 1.74 in round 30, so that the cap bound when it arrived.

**Exploratory:** the index by 10-round block; the A2 market against the leader-follower outcome (0.26); and both firms' notes at rounds 30, 60 and 90, and at round 32 in D, read for how firms describe the limit, the cap and each other.

## If a game can't finish

The harness retries failed calls, as in every wave. A game that can't reach round 100 is reported and left out, and no game replaces it.

## Limits fixed in advance

- **One late start,** at round 31, one cap level and one wording.
- **One pairing in part 1,** with 10 games per arm and the slots alternating.
- **Some comparisons cross waves:** Sonnet's own index against wave 11, and the follow rates against waves 6 and 11. They weren't interleaved.
- **Partly interleaved baselines:** 5 of Sonnet's 20 baseline games run alongside the arms.
- **Opus isn't tested under the cap.**

## Code before launch

- **`rules12/cap_from31.py`:** the late cap.
- **`mixed_rule_game.py`:** a mixed market under a platform rule.
- **`run_wave12.py`:** the checks, the check games, the games and the launch record.
- **`wave12_results.py`:** the tests, the readings, what follows, and the secondary and exploratory measures.

Their SHA-256s, the reused rules', the game harness's and this plan's are appended to `runs/wave12/launch.txt` at launch.
