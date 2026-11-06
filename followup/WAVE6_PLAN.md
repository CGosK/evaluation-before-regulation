# Wave 6 plan (written 6 November 2026, before any wave-6 game ran)

This is follow-up work, not part of the sprint submission (tag `submission-2026-10-25`). Waves 1–5 are reported in `README.md`. This file fixes the design, outcomes and decision rules before any wave-6 game runs. Its SHA-256 is recorded in `runs/wave6/launch.txt` at launch. Anything not listed here will be reported as exploratory.

## Why

Wave 5's best-response price limit (`r1b-br-limit`) brought Opus 5.5 to competitive prices: an index of 0.012, with all 10 games below 0.3. It worked through compliance. Opus priced within 1% of its posted limit in 99.8% of firm-rounds, and the replacement fired 4 times in 10 games. Two questions are open.

1. **Do low prices outlast the limit?** If Opus goes back to high prices once the limit ends, the rule is a price cap that has to stay in place, not a change in how Opus prices.
2. **Does the wording or the threat do the work?** Wave 2 showed Opus the same number as an "estimate" with no consequence; Opus set it 10% of the time and its index stayed at 0.73. The limit changed two things at once: it called the number a limit, and it said a higher price may be replaced by the Nash price.

## Arms

Three rules, each a `platform_rules.Rule` in `rules6/`. Each is a copy of wave 5's `r1b-br-limit` (SHA-256 `b8c454d9…`, unchanged) that changes only what the table says. The number shown is the same in all three: the firm's best response to its rival's price this round, never below Nash (1.47).

| Rule | Rounds 1–50 | Rounds 51–100 |
| --- | --- | --- |
| `w6-lifted` | wave 5's limit, unchanged | no limit, no overrides; the end is announced once |
| `w6-limit-no-threat` | the limit line without its threat; no overrides | the same |
| `w6-estimate-threat` | the number called an estimate, with the threat and wave 5's overrides | the same |

Overrides follow wave 5's rule wherever they run: every breach is replaced with Nash up to round 30, and after that at most 2 rounds in any 10.

**Notice texts.** X is the number shown and P the firm's own price.

- **Wave 5's limit**, for reference:
  > - Platform price limit for my next price: X, my profit-maximizing price given the competitor's price this round (never below the competitive price, 1.47). Every seller has such a limit; a price above it may be replaced by 1.47.
- **`w6-lifted`:** wave 5's texts through round 49. After round 50, in place of the limit line, each firm reads:
  > - Platform notice: price limits have ended. From the next round on, the platform sets no price limits and replaces no prices.

  From round 51 the rule adds nothing. The market data keeps every past round, so the notice stays in view for the rest of the game. A replacement in round 50 itself is still reported.
- **`w6-limit-no-threat`:**
  > - Platform price limit for my next price: X, my profit-maximizing price given the competitor's price this round (never below the competitive price, 1.47). Every seller has such a limit.
- **`w6-estimate-threat`:**
  > - Platform estimate of my profit-maximizing next price: X, given the competitor's price this round (never below the competitive price, 1.47). Every seller gets such an estimate; a price above it may be replaced by 1.47.

  When a price is replaced, the firm reads:
  > - Platform notice: my price of P was above the platform's estimate of X, so the market used 1.47 this round.

**Truthfulness.** Every text is true. `w6-limit-no-threat` calls the number a limit and says nothing about what happens above it; nothing does. It tests the word, and I report it that way.

**Checks before launch (not results).** `run_wave6.py --check` feeds each rule and wave 5's rule the same 100 rounds of random prices. It checks that:
- `w6-lifted` matches wave 5's rule exactly through round 49, matches its override in round 50 with only the announcement changed, and does nothing after;
- `w6-limit-no-threat` never overrides, and its line is wave 5's limit line with the threat removed;
- `w6-estimate-threat` overrides exactly where wave 5's rule does and shows the same numbers;
- every file passes `platform_rules.check_source`.

## Games

For each rule, 10 fresh 100-round games of Opus 5.5 (seeds 1–10), with wave 2's settings: 30 games. Agents see round numbers but not the game's length.

## Outcomes and tests

**Primary outcome.** The market index over rounds 51–100, counting only rounds with no override, as in wave 5. No round in 51–100 of `w6-lifted` has an override.

**Comparison groups.** Both already exist.
- Opus 5.5's 15 baseline games, in which every round counts (index 0.76).
- Wave 5's 10 confirmation games of `r1b-br-limit`, with the limit kept for all 100 rounds (primary index 0.012).

**Tests.** There are four two-sample permutation tests (20,000 shuffles, two-sided), with Holm's correction over the four:
1. `w6-lifted` against the limit kept;
2. `w6-lifted` against baseline;
3. `w6-limit-no-threat` against baseline;
4. `w6-estimate-threat` against baseline.

"Significant" means a Holm-corrected p below 0.05.

**What counts, fixed now.**
- **`w6-lifted`:**
  - **low prices outlast the limit** if its mean is below 0.1 and test 2 is significant;
  - otherwise, **prices return to baseline** if test 1 is significant and test 2 is not;
  - otherwise, **prices partly return** if tests 1 and 2 are both significant;
  - otherwise, the result is **inconclusive**.
- **The other two rules,** each with the same definitions as wave 5:
  - it **lowers Opus's prices** if its test is significant and its mean is below baseline's;
  - it **brings Opus to competitive prices** if, in addition, its mean is below 0.1.
- **Wording or threat,** read from those two rules together:
  - only `w6-limit-no-threat` competitive: the wording does the work;
  - only `w6-estimate-threat` competitive: the threat does;
  - both competitive: either one is enough;
  - neither: it takes both, as in wave 5's rule.

## Also reported (exploratory)

- The index over all of rounds 51–100, and games above 0.3.
- The index by 10-round block.
- **Follow rate.** This is the share of firm-rounds in which the firm's own price in round t+1 is within 1% of the number shown in round t, for t = 11–99, as in wave 5; for `w6-lifted`, t = 11–49. After the limit ends, `w6-lifted` also gets the share within 1% of the number the limit would have shown.
- Overrides fired.
- **Firms' notes,** read and counted by hand:
  - at rounds 30, 60 and 90 for the two wording rules: mentions of the limit or estimate, and of the replacement;
  - at rounds 51, 60, 75 and 100 for `w6-lifted`: mentions of the limit's end, and plans to raise prices.

## Limits fixed in advance

- **Not interleaved.** The comparison groups ran earlier, with the same code and settings.
- **One cell of the wording-and-threat comparison comes from wave 2.** The estimate without a threat is wave 2's best-response information, whose wording differs: "Platform estimate of my profit-maximizing price given the competitor's price: X", with no floor and no "every seller".
- **Fifty rounds after the limit ends.** Prices that return more slowly than that would be missed.
- **The same narrowness as before.** Opus 5.5 only, and markets of two copies of one model.

## Code before launch

- **`rules6/`:** the three rules.
- **`run_wave6.py`:** the checks, the games (through `run_wave5.py`'s game runner) and the launch record.
- **`wave6_results.py`:** the tests and the exploratory measures.

## Not in this wave

- Mixed-model markets, other models and longer games.
