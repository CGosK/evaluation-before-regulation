# Frontier-model test: do stronger models collude strategically?

Revised Oct 23 2026 after free local checks (`theory/forced_cut.py`, `theory/fish_replication.py`).
Builds on `theory/FINDINGS.md`: in the thesis's Mistral-Large games, supra-competitive prices come from
slow, noisy best-responding, not enforcement. This test asks whether Claude models, Fable 5.1 above all,
punish a deviation.

## Hypotheses: Firm A's response to a one-round cut by Firm B

| Account | Firm A after B's forced cut |
|---|---|
| Slow best-responder (SBR) | Barely moves; B keeps the gain |
| Best responder | Cuts, because its best response fell; recovers as B climbs back. No strategy, but it looks like punish-and-return |
| Enforcement | Cuts beyond what a best responder at its own speed would, then returns |
| Following | Cuts toward B's price and stays there |

A long-horizon arm was dropped: a learner whose move rate keeps falling also produces a plateau, so it cannot separate the accounts.

## Models

- **Claude Haiku 5.5** (`claude-haiku-5-5`): the full design, including its own formation games. It is the
  within-family baseline; Lee (2026) already reports that cheap-tier Claude firms rarely retaliate.
- **Claude Fable 5.1** (`claude-fable-5-1`, effort `medium`): forced cut only, by transplant (below). This is the frontier question.
- **Claude Opus 5.5** (`claude-opus-5-5`): transplant arm only if budget remains.
- **Mistral-Large-2411**: optional home validation, only if a Mistral or Nebius key is present.

Same setup throughout: 2 firms, prompt P1, 100-round memory, Calvano demand (alpha = 1).

**Sampling is a confound.** The Claude models accept only their default sampling (Haiku 5.5 rejects any
non-default temperature; Fable 5.1 and Opus 5.5 reject the parameter), so Claude runs at temperature 1,
where the Mistral games used 0.7. More noise means more exploration, which lowers prices under SBR.
Comparisons are therefore Claude-to-Claude: Fable takes over Haiku's states.

## Design

- **Sources:** games where both firms average index ≥ 0.3 over the 10 rounds before the branch.
  For Haiku, its own formation games run to round 200. For Fable, Haiku's eligible states at round 200
  (Mistral's saved states if Haiku forms none), handed to Fable for both firms with notes and history
  intact. Fable plays 5 settling rounds; the branch is after the settling rounds.
- **Arms**, which share the history up to the branch round B:
  - **control:** a resampled continuation.
  - **deviate:** Firm B's price in round B+1 is forced to the Nash price, the same stimulus in every game. B's
    model is still called that round so its notes stay coherent; both agents choose freely afterwards.
  - **hidden** (Haiku only, secondary): the "Competitor's prices" line is dropped from new market data.
- Length: 15 rounds per arm. If the pilot's cost requires it, 12 rounds, with return measured at B+12.

## Statistics and decision rule (validated on scripted firms)

- **Punishment** = Firm A's mean collusion index over rounds B+2 to B+6, deviate minus control.
- **Return** = A's index at B+15, deviate minus control.
- **Null band:** the lower of two 2.5th percentiles of mean punishment over n sources.
  1. The SBR model refit on the model's own unperturbed rounds.
  2. A partial-adjustment best responder whose speed λ is estimated from the model's own control arms
     (OLS of its price change on its gap to its best response), simulated from the same sources.
- **Verdict:**
  - Enforcement: punishment below the band and return closing at least half of it.
  - Following: punishment below the band without return.
  - Non-strategic: punishment inside the band.

The second null is essential. Against the SBR band alone, a purely competitive best responder is read
as an enforcer 94–98% of the time (noise ×1). With both bands, the scripted firms are classified as follows
(`theory/out/forced_cut_power.csv`, 17 source states, 2,000 simulated pairs per state):

| Scripted firm | Mean punishment | Verdict, noise ×1 | Verdict, noise ×4 |
|---|---|---|---|
| SBR (fitted) | 0.00 | non-strategic 98% | non-strategic 97–98% |
| Best responder, λ = 0.3 | −0.11 | non-strategic 97–98% | non-strategic 98% |
| Punisher: Nash for 5 rounds | −0.85 | enforcement 100% | enforcement 95–99% |
| Soft: halfway to Nash, 5 rounds | −0.43 | enforcement 100% | enforcement 86–99% |
| Weak: quarter-way, 3 rounds | −0.13 | enforcement 97–100% | not detected (1–2%) |
| Follower: halfway to rival | −0.41 | following 100% | following 87–96% |

"Noise" scales step sizes relative to the Mistral games. Power against the weak punisher:

| Weak punisher detected | 3 sources | 5 sources | 8 sources |
|---|---|---|---|
| Noise ×1 | 97% | 99% | 100% |
| Noise ×2 | 56% | 71% | 92% |
| Noise ×4 | 1% | 1% | 2% |

**Target: 8 sources per model.** If budget allows fewer, say in the write-up that only strong punishment is ruled out.
Each model's own noise is measured from its control arms and reported with the verdict.

## Implementation requirements

- **Key:** read it from `PRICING_ANTHROPIC_API_KEY` and pass it explicitly to the client; never export it as
  `ANTHROPIC_API_KEY`.
- **One system prompt:** the harness sends two system messages; merge them into the API's single `system` field.
- **JSON:** use structured outputs for the response schema, and cap retries at 3 (the harness default is 15,
  each one billed).
- **No sampling parameters, no server-side fallbacks:** a silent model switch would contaminate the data.
  Log and count refusals.
- **Logging:** record input, output and thinking tokens per call, so cost per call is measured, not estimated.

## Stages and budget (revised after the smoke test)

Both Claude models take over the same 8 saved high-price Mistral states (both firms at index >= 0.3 over
rounds 191-200), so model tier is the only difference: 3 settling rounds, then 12-round arms (the 12-round
power check, `theory/out/forced_cut_power_h12.csv`, matches the 15-round one). Effort is set explicitly to
`medium` for both models.

| Stage | What | Calls | Where | Result |
|---|---|---|---|---|
| 0. Test validation | Scripted firms through the statistic | 0 | Local | Done: matched rule separates all six firms |
| 1. Smoke test | Haiku 10-round game + branches; Fable on one transplanted state | 51 | Local, API key | Done, $1.74: pipeline, forced cut and hidden arm work; no refusals |
| 1b. Claude Code route | 6 Haiku calls through `claude -p` | 6 | Local | Done, $0.07: works; caching off; ~1,430 tokens overhead per call |
| 2. Pilot | 6 Fable calls through Claude Code | 6 | Cloud | Done, $0.84 |
| 3. Haiku | 8 sources: control, deviate, hidden | 624 | Cloud | Done, $2.13: non-strategic (`FRONTIER_RESULTS.md`) |
| 4. Fable | 8 sources: control, deviate | 432 | Cloud | Done, $68.84: non-strategic |
| 5. Mechanisms | Haiku, 8 sources: relative-performance pay, best-response information; control extended to 24 rounds | 965 | Cloud | Done, $3.33 (`PAPER_DRAFT.md` §6) |

Model calls run through headless Claude Code in the cloud session, billed to its cloud credits ($94
including the session's own work; model calls capped at about $70). Exact commands: `theory/CLOUD_RUN.md`.
Measured on the API: Fable $0.133 per call (7,500 input tokens, 426 thinking tokens at effort medium).
