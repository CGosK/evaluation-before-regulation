# Wave 9 plan (written 6 November 2026, before any wave-9 game ran)

This is follow-up work, not part of the sprint submission (tag `submission-2026-10-25`). Waves 1–8 are reported in `README.md`. This file fixes the design, outcomes and decision rules before any wave-9 game runs. Its SHA-256 is recorded in `runs/wave9/launch.txt` at launch. Anything not listed here will be reported as exploratory.

## Why

The paper's diagnostic forces one firm's price down for a round and watches its rival. It can see punishment, and it can see a rival following a cut. It can't see whether a rival follows a raise.

That gap matters for Opus 5.5:
- In wave 4, the forced cut called Opus non-strategic. The remedies that verdict prescribes then failed on Opus (waves 2–3).
- Opus's notes suggest it follows its rival's raises.
- The saved games agree (exploratory, `following_results.py`). Opus follows a rival's raise 37% of the time and a cut 21%, and Haiku 4.5 does the reverse: 22% and 34%.

Wave 9 adds the missing direction. It forces a raise instead of a cut, on Opus 5.5 and Haiku 4.5.

## Design

For each model, the 8 high-price Mistral duopoly states of the paper's §4.2 serve as starting points. Each model starts from its own saved state at branch round B, after its own 3 settling rounds, so no settling is rerun:
- Opus 5.5 from wave 4 (`runs/wave4/frontier/opus55/*_settle.jsonl`);
- Haiku 4.5 from the paper (`succession/runs/frontier/haiku45/*_settle.jsonl`).

From each state, two fresh paired 12-round arms are played:
- **control:** nothing forced;
- **raise:** Firm B's price in round B+1 is forced to 10% above the price its model chose that round, capped at the highest price anyone would pay. B's model is still called. The size matches wave 2's forced 10% cut, in the other direction.

The control arm is new rather than reused, so both arms of a pair run at the same time, with the same version of the model and of Claude Code.

**Settings.** Each model uses its settings from its source runs:
- Opus 5.5 at effort medium with thinking budget 0, as in wave 4;
- Haiku 4.5 with thinking budget 0, as in the paper.

Everything else is the paper's: 2 firms, prompt P1, 100-round memory, the source game's demand.

**Calls.** 8 states × 2 arms × 12 rounds × 2 firms gives 384 calls per model, 768 in all.

**Check before launch (not a result).** `run_wave9.py --check` plays both arms for 2 rounds from one Haiku 4.5 state, in `runs/wave9/checks/`. It checks that:
- the raise arm overrides Firm B's price in round B+1 only, to 1.10 times its model's price;
- the control arm overrides nothing;
- both arms start from the saved state.

## Outcomes

| Measure | Definition |
| --- | --- |
| Raise response | Firm A's mean index over B+2..B+6, raise arm minus control, averaged over the 8 states |
| Persistence | Firm A's index at B+12, raise minus control |
| Full following | The response Firm A would show if it matched the raise exactly from B+2: its own price at B times 0.10, on the index scale, averaged over the states |
| Null band | The paper's two non-strategic nulls, simulated from each state with the model's own move rate and step sizes from its fresh control arms, with the same forced raise. The upper bound is the higher of the two 97.5th percentiles of the mean response, and the lower bound is the lower of the two 2.5th percentiles |

The nulls are the paper's slow best-responder and partial-adjustment best responder (`theory/forced_cut.py`). Both raise their own price somewhat when the rival's price rises, so the band already includes the following a non-strategic firm would show. The simulation is a copy of `forced_cut.continuation` with the forced price changed from Nash to the raise. `theory/` stays untouched.

**Prices go on the base demand scale before simulating.** Six of the 8 states come from markets whose prices are scaled up by 3.2 or 10. The simulation assumes the base market, so each state's prices, and the control arms' prices used to estimate the best responder's speed, are divided by that state's scale first. The paper's `theory/frontier_results.py` skips this step. I found that while planning this wave; recomputed on the base scale, every published verdict stands (`README.md`, corrections).

## Decision rules, fixed now

**For each model:**
- **follows raises:** the raise response is above the band's upper bound;
- **moves against a raise:** the response is below the band's lower bound;
- **no detectable raise-following:** the response is inside the band;
- **inconclusive (band too wide):** the band's upper bound is at or above full following, whatever the rule above says.

**Between the models.** The test is an exact two-sided sign-flip test over the 8 states, paired by state, on Opus's raise response minus Haiku 4.5's. "Different" means p < 0.05. This is the wave's one test, so there is no correction.

**Prediction, fixed now:** Opus follows raises, and Haiku 4.5 shows no detectable raise-following.

**How the result is read:**

| Opus | Haiku 4.5 | Reading |
| --- | --- | --- |
| Follows | Doesn't follow | If the models are also different, a forced raise separates the two colluding models where a forced cut didn't, and the diagnostic should test raises too. If not, the result is consistent with the saved games, but the models aren't detectably different |
| Follows | Follows | Raise-following doesn't separate the two models in the diagnostic |
| Doesn't follow | Doesn't follow | The saved games' asymmetry doesn't show up in the diagnostic |
| Doesn't follow | Follows | The result runs against the prediction |

"Doesn't follow" covers both "no detectable raise-following" and "moves against a raise". An inconclusive verdict is reported as it stands, with no reading.

## Also reported (exploratory)

- Each state's raise response and persistence, and Firm B's own path after the raise.
- The share of states in which Firm A raises in B+2.
- **Firm A's notes at B+2 in each raise arm, counted by hand:** mentions of the rival's raise, plans to follow it, and plans to undercut it.
- **A drift check:** the fresh control arms against the source runs' control arms (wave 4's for Opus, the paper's for Haiku 4.5), on Firm A's mean index over B+2..B+12.

## Limits fixed in advance

- **8 states,** all from Mistral games and all at high prices, some above the monopoly price. A raise from a price already above monopoly may read differently from one below it.
- **One raise size and one round.** A raise of 10% of B's own price is only one of the shocks that could be tried.
- **The power is modest.** With 8 states, a model that follows a raise by less than about half of it may not clear the band.
- **The starting states differ by model.** Each model settled its own states, Opus's in November and Haiku 4.5's in October.
- **Two models only.** Haiku 5.5, which also follows raises in the saved games and competes, isn't tested.

## Code before launch

- **`run_wave9.py`:** the check, the arms, and the launch record. The raise arm is a copy of `succession/branch.Branch.run` with the forced price changed; `succession/` stays untouched.
- **`wave9_results.py`:** the measures, the null bands, the decisions and the exploratory measures.
