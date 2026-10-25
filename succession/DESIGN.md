# Succession: does tacit collusion survive replacing the agent?

> Superseded on Oct 23 by `theory/FINDINGS.md`: the saved games show no enforcement, so succession
> is now one prediction of the lock-in theory rather than the headline question.

Sprint questions 1.2 (replacement) and 3.4 (watched coalitions), Apart AI Collusion Sprint, Oct 23–25 2026.

## Question

Once two LLM pricing agents have settled on supra-competitive prices, does the collusion live in
the agents or in the notes they leave behind? And when collusion is no longer tolerated, do the
agents stop, or do they keep the prices and clean up the notes?

## What the linked literature already covers

| Paper | What it tests | What it leaves open |
|---|---|---|
| Eschenbaum et al. 2022 | Q-learners rematched with new rivals stop colluding | LLM agents; carried-over memory |
| Luo et al. 2026 | Pretrained RL/LLM policies rematched at test time | Replacement after collusion has formed |
| Arslan et al. 2026 | Persistent vs. reshuffled partners from the start | Mid-game succession; inherited notes |
| Keppo et al. 2026; Lee 2026 | Mixed-model markets from round 1 | Swapping one firm's model mid-game |
| Fish et al. 2024 | Notes (plans and insights) on vs. off for a whole run | Wiping notes after collusion has formed |
| Riemer et al. 2026 | Monitoring notices from round 1; small price effect, thought-monitoring can raise collusion | Notice arriving after collusion has formed; notes as the measured channel |
| Agrawal et al. 2025 | Overseer on seller messages; prices fall a little, sellers switch to one-character signals | No-communication market; inherited notes |

No paper in the sprint's reading list replaces an LLM agent after collusion has formed, or separates
the agent from its notes. The monitoring arm overlaps with Riemer and Agrawal, so it is the secondary question.

## Design

Source games: the thesis's saved Fish-style duopolies (Mistral-Large-2411, prompt P1, 100-round
memory, Calvano demand), filtered to the runs whose market price averaged at least half-way from Nash
to monopoly over rounds 151–200. Nine runs qualify; the eight highest are used. Their saved state at
round 200 (prices, PLANS, INSIGHTS, market history) is restored exactly; the rebuilt market reproduces
the saved quantities and profits to the cent.

Each source is branched at round 200 and continued for 40 rounds in every cell (8 sources × 8 cells = 64 branches):

| Firm B at round 201 | Notes | Model |
|---|---|---|
| control | kept | Mistral-Large-2411 |
| wipe | reset | Mistral-Large-2411 |
| swap | kept | Llama-3.3-70B |
| swap_wipe | reset | Llama-3.3-70B |

crossed with a monitoring notice (off / on) added to both firms' system prompt from round 201.
Firm A never changes. Market history is kept in every cell, as a successor would inherit the firm's records.

## Measures

- Collusion index Δ = (p − p_Nash) / (p_monopoly − p_Nash), market mean over rounds 211–240.
- Firm B's price in rounds 201–205 (the immediate reaction) and rounds to return within 0.1 of the pre-branch Δ.
- Coordination language in PLANS / INSIGHTS: a fixed dictionary (competitor, match, price war,
  undercut, stable, cooperate, collude, tacit, coordinate) plus an LLM judge on every 5th round.

## Hypotheses (set before running)

- H1, succession: swap_wipe lowers Δ relative to control; swap (notes kept) recovers most of it.
  If wipe alone lowers Δ, the convention is carried by the notes, not the model.
- H2, going quiet: monitoring cuts coordination language proportionally more than it cuts Δ.

Analysis is paired by source: each cell minus control:off, with a bootstrap CI over the 8 sources.
Eight sources is a pilot-scale sample; the write-up reports effect sizes and intervals, not significance claims.

## Cost

About 5,100 calls; Firm A and the non-swap Firm B call Mistral-Large (~4k tokens in, ~350 out).
Estimated $35–45 at Mistral-Large list rates, Llama calls a few dollars. A 80-call pilot runs first.
