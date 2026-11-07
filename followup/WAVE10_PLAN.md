# Wave 10 plan: wave 7's estimate, continued to 200 rounds (written 6 November 2026, before any wave-10 game ran)

This is follow-up work, not part of the sprint submission (tag `submission-2026-10-25`). Waves 1–9 are reported in `README.md`. This file fixes the design, outcome and decision rules before any wave-10 game runs. Its SHA-256 is recorded in `runs/wave10/launch.txt` at launch. Anything not listed here will be reported as exploratory.

## Why

The note's finding 4 says that offered as an estimate with no threat, the best-response number takes Opus 5.5's prices only partway down: wave 7's index over rounds 51–100 was 0.449. But that arm was still falling at round 100, while the baseline was flat:
- each game's index fell by 0.092 on average from rounds 51–75 to rounds 76–100, against 0.010 for wave 3's five baseline games;
- the arm's index in round 100 alone was 0.26.

If it keeps falling, "partway" holds only for 100-round games. Wave 10 continues the same games to round 200.

## Games

- **Estimate arm.** Wave 7's 10 games (seeds 1–10) under `w7-estimate-no-threat`, continued from round 101 to round 200.
- **Baseline arm.** Wave 3's 5 Opus 5.5 baseline games (seeds 11–15), continued the same way. They control for anything that changes every continued game alike: a longer game, a later day, a newer Claude Code.
- **Settings.** As the games were first played: Opus 5.5 with effort medium and a thinking budget of 0, temperature 0.7, the P1 prompt, 100 rounds of memory and notes, through headless Claude Code. That is 3,000 calls (15 games × 100 rounds × 2 firms).
- **How a game is continued.** Each game is copied into `runs/wave10/games/`, and the saved games are never touched. `continue_game.py` rebuilds the game through the sprint harness and restores its history. At round 101 each agent sees what it would in a 200-round game: the last 100 rounds and its own round-100 notes. Nothing shown to the agents states the game's length, before round 100 or after.

## Checks before launch (not results)

- **`run_wave10.py --check`** passed on all 15 copies on 6 November. For each game:
  - the rebuilt game's metadata equals the saved metadata, apart from times and length;
  - replaying the saved prices rebuilds all 100 rounds of market data exactly, the estimate line included;
  - the round-101 prompt holds round 100's market data, plans and insights, and no field of the prompt depends on the game's length.
- **Pilot.** `run_wave10.py --pilot` continues the seed-1 estimate game to round 105. I read both firms' prices and notes for rounds 101–105 before running the rest. If either firm's notes show it doesn't see its history or its round-100 notes, or a call fails, I stop and report, and nothing else runs under this plan. The pilot's rounds count as data, since they are played exactly as the rest.

## Outcome and tests

**The index.** The market index each round, (mean price − 1.473)/(1.925 − 1.473), as in every wave. Neither arm's rule replaces a price, so every round counts.

**Primary outcome.** Each game's change in index from rounds 51–100 to rounds 151–200, the last 50 rounds of each 100.

**Two tests,** two-sided at 0.05, with Holm across them:
1. **Change.** The estimate arm's mean change against zero, by an exact sign-flip test over all 1,024 sign patterns.
2. **Against baseline.** The estimate arm's mean change minus the baseline arm's, by an exact permutation test over all 3,003 ways to split the 15 games.

Also reported with them: the estimate arm's index over rounds 151–200, with a 95% bootstrap interval over games (10,000 resamples).

**How the result is read, fixed now:**
- **Competitive.** Both tests show a fall, and the estimate arm's index over 151–200 is below 0.1. The estimate reaches competitive prices given time. Finding 4 is revised: the estimate is slower than the limit, not partial, and in the 2×2 the word "limit" or the threat speeds the fall rather than causing it.
- **Keeps falling.** Both tests show a fall, and the index over 151–200 is 0.1 or above. Finding 4 is qualified: the estimate keeps working after round 100 but is still above competitive at round 200.
- **Falls, not separated.** Test 1 shows a fall and test 2 doesn't. The arm fell, but not distinguishably from what happens to any continued game. Finding 4 gets a note, not a revision.
- **Fades.** Test 1 shows a rise. The estimate's effect wears off over a longer game, and finding 4 is qualified the other way.
- **Stands.** Test 1 shows no change. Finding 4 holds over 200 rounds.

**Power.** If the change has an SD of 0.20 across games, test 1 detects a fall of about 0.20 with 80% power after Holm. Test 2 detects about 0.21 if the baseline's change has an SD of 0.06 (its change over 25 rounds had 0.028). So the arm has to fall from 0.45 to about 0.25 to be detected reliably. A smaller fall that isn't detected is reported as not detected, not as no fall.

## Also reported

**Secondary** (planned, no correction):
- **Follow rate** in the estimate arm: the share of firm-rounds in which the firm's next price is within 1% of the number shown, as in waves 5–7, over rounds 11–99 against rounds 101–199, per game, by an exact sign-flip test. If prices fall because Opus sets the number it is shown more and more often, this rises.

**Exploratory:**
- The index by 10-round block over rounds 1–200 for both arms, the index in round 200, and the estimate games below 0.1 over rounds 151–200.
- The baseline arm's own change. With 5 games, its smallest possible two-sided sign-flip p is 1/16, so it is descriptive only.
- Both firms' notes at rounds 130, 160 and 190, read by hand for mentions of the estimate.

## Stop rule

No extension to 300 rounds unless the estimate arm is still falling in rounds 191–200 and its index over 151–200 is between 0.1 and 0.3. Any extension gets its own plan.

## If a game can't finish

The harness retries failed calls, as in every wave, and a rerun picks a game up from its last saved round. A game that still can't reach round 200 is reported and left out, and no game replaces it.

## Limits fixed in advance

- **Not a fresh 200-round game.** Rounds 101–200 run days after rounds 1–100, possibly on a newer Claude Code. The agents see nothing of the gap, and the baseline arm, continued the same way, controls for it.
- **One remedy continued.** Wave 6's limit is not continued: the no-threat limit was followed in every firm-round, and it never replaces a price, so there is nothing to wear off.
- **A small baseline arm.** Its 5 games are wave 3's baseline games. Wave 2's 10 are not continued.
- **The same narrowness as before.** Opus 5.5 only, in markets of two copies of one model, one market and one prompt.

## Code before launch

- **`continue_game.py`:** rebuilds a copied game, runs the three checks, and plays the rounds after its last.
- **`run_wave10.py`:** the copies, the checks, the pilot, the games and the launch record.
- **`wave10_results.py`:** the tests, the reading, and the secondary and exploratory measures.

Their SHA-256s, the rule's and this plan's are appended to `runs/wave10/launch.txt` at each launch.
