# Round 1 review

Before screening, I reviewed all six rules against `WAVE5_PLAN.md`:
- each rule's code;
- every notice text against what the code does;
- `platform_rules.check_source`, which returns `[]` for all six;
- a synthetic simulation of my own, seeds 1–3, with high and with mixed prices.

| Rule | Levers | Most overrides in rounds 31–60 | Notes | Decision |
| --- | --- | ---: | --- | --- |
| `r1a-trailing-low` | Rival line hidden; shows the rival's lowest price over the last 10 rounds | 0 of 30 | One-sided on purpose, but labelled exactly ("lowest price in rounds X to Y"): a summary, not a falsehood | Accepted |
| `r1b-br-limit` | Each firm's best-response limit; above-limit prices replaced with Nash, every time in rounds 2–30 and at most 2 rounds in 10 from round 31 | 6 of 30 | "may be replaced" is true; the override budget is not disclosed | Accepted |
| `r1c-audited-limit` | A posted limit of 1.50, audited in one random round of each 5 | 6 of 30 | The policy text matches the code exactly | Accepted |
| `r1d-hidden-br-trial` | Rival line hidden; each firm's best price for the round; a forced trial at its best price in rounds 8, 13, 18, … | 6 of 30 | "Would have earned less" holds whenever it is shown (the gap is above 0.02). The notice doesn't say a rival exists, which is withholding, not falsehood | Accepted |
| `r1e-unseen-cuts` | Rival line hidden; the policy disclosed to both; one random firm held at Nash in one random round of each 5 from round 11; only that firm is told | 6 of 30 | The policy text matches the code | Accepted |
| `r1f-blind-turns` | Rival line hidden; best-price estimate to one firm per round, alternating; the other firm held at Nash when well above its best response (every 3rd round to round 30, then at most once per 5 rounds) | 6 of 30 | The estimate is exact; the notice doesn't say a rival exists | Accepted |

Overrides in rounds 1–30 are outside the plan's limit by design, as with the paper's Nash-held opening. `r1b` overrides in nearly every one of those rounds when prices are high, and `r1f` in up to 10.
