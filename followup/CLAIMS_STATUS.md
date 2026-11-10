# Status of the paper's claims after the follow-ups

*Chris Graham · November 2026*

This page checks each claim of "Evaluation Before Regulation" (frozen at the tag `submission-2026-10-25`) against the twelve follow-up waves. The waves are reported in [`FOLLOWUP_NOTE.md`](FOLLOWUP_NOTE.md), with full tables in [`README.md`](README.md).

**No claim is contradicted on the models the paper tested.** Three are narrowed: they hold for Mistral and Haiku 4.5 but not for Opus 5.5, and those three carry the paper's main argument. Five hold, three of them extended to newer models. Four haven't been retested.

- **Holds:** the follow-ups agree, or extend the claim to more models.
- **Narrowed:** it holds where the paper tested it, but not on a newer model or in a mixed market.
- **Not retested:** no follow-up wave tested it.

## The claims

| Claim | Where in the paper | Status | What decides it |
| --- | --- | --- | --- |
| Agents don't punish a rival who breaks ranks | Abstract; §4.2 | Holds, extended | On the forced-cut test, Opus 5.5 and Sonnet 5.5 are non-strategic: neither punishes and returns (wave 4). Recomputed on the base demand scale, the paper's and wave 4's null bands are narrower and every verdict stands. |
| They collude because they learn too slowly to leave a high starting price | Abstract; §4.1, §4.4 | Narrowed | It holds for Mistral and Haiku 4.5. Opus 5.5 is neither an enforcer nor a slow learner. It doesn't punish a forced cut, best-response information had no detectable effect on it, and hiding prices from round 1 lowered its prices, which the paper's Table 1 doesn't predict for a slow learner (waves 2 and 4). |
| The forced-cut test tells you which remedy to use | Abstract's lesson; §5, step 2 | Narrowed | It called Opus non-strategic, which prescribes best-response information and forced Nash rounds. On Opus the first had no detectable effect and the second worked only partly (waves 2–4). A forced raise didn't separate Opus from Haiku 4.5 either (wave 9). |
| Best-response information and forced Nash rounds prevent collusion | Abstract; §4.4, §4.5; §5, step 3 | Narrowed | They kept every Haiku 4.5 game at Nash. On Opus, the information left the index at 0.73 and forced Nash every 10 rounds took it to 0.43, with 8 of 10 games still high (waves 2–3). Best-response information and a 10% cut both helped Sonnet 5.5 partly (wave 2). Next to Opus, the information had no detectable effect on an Opus–Haiku 4.5 market (wave 8). |
| Agents set the best-response number they are shown | §5, step 3 | Holds, with a risk | Haiku 4.5 set a number inflated by 10% in 95% of firm-rounds and never set the true one. Prices settled where obedience predicts (wave 1). A number lowered by 10% was set in 76% of firm-rounds, at a cost of 46% of profit (wave 2). |
| Hiding rival prices doesn't prevent collusion | Abstract; §4.4, §4.5; §5, step 3 | Holds | From round 1 it lowered the average for both colluding models, Haiku 4.5 to 0.41 (paper) and Opus 5.5 to 0.38 (wave 4), but left half or more of the games high. For Haiku 4.5 the drop isn't significant after correction (p = 0.17). From high-price states it changed nothing on either. |
| Screen the model before deploying it | §5, step 5 | Holds, extended | Opus 5.5 and Sonnet 5.5 collude on their own (0.76 and 0.38), and Haiku 5.5 competes (0.15), as the paper found (wave 2). |
| Test any instruction on the deployed model | §5, step 6 | Holds, extended | Remedies need the same test. Best-response information, which stopped Haiku 4.5, had no detectable effect on Opus 5.5, and forced Nash rounds helped it only partly (waves 2–3). Opus's own index fell by about half against a different rival (wave 8). The limit that took Opus to Nash took Sonnet 5.5 only partway (wave 11), but took a market of Opus and Sonnet all the way (wave 12). |
| The agents' stated reasoning points the wrong way | §4.3; §5, step 1 | Not retested | One consistent sign: wave 5's notes credited the limit's threat, and wave 6 showed the threat wasn't needed. |
| A memory reset makes collusion worse | Abstract; §4.5; §5, step 3 | Not retested | Haiku 4.5 only. |
| The Mistral diagnosis: no enforcement, and a model with no strategy that predicts larger markets | §4.1 | Not retested | The follow-ups ran no Mistral games. |
| For enforcers, use the classic cartel remedies | §5, step 4 | Not retested | No model here enforces unless told to, and the paper's told-to-enforce control itself couldn't be classified: its band was too wide. |

## What the follow-ups add

- **A searched rule brings Opus 5.5 to Nash.** The best one is a best-response price limit, at an index of 0.012 (wave 5).
  - Obeyed, the limit reaches Nash by construction, so it shows that Opus obeys a posted cap.
  - Opus obeyed it with or without the threat behind it (wave 6).
  - Lifted halfway through a game, it lost part of its effect: the index rose to 0.44 (wave 6).
  - The same number called an estimate took prices only partway down, to 0.45 (wave 7). Continued to 200 rounds, those games settled at 0.32 over rounds 151–200, with no significant change (wave 10).
- **Posted limits carry over only as far as the market obeys them (waves 11 and 12).** On Sonnet 5.5 the same limit lowered the index to 0.15, not to competitive prices: Sonnet kept it in some games and ignored it in others. In a market of Opus and Sonnet it brought the index to 0.01: Opus kept it, and Sonnet matched Opus. A fixed cap above the competitive price didn't raise average prices on Sonnet or Haiku 5.5. On Sonnet it split the games instead, holding 7 of 20 at the cap and sending 10 below every baseline game, and a planned test on fresh games found the same counts. Brought in at round 31, after the opening, the same cap held no game at the cap and lowered the index a little, to 0.27 against 0.36.
- **Opus follows raises more than cuts, the reverse of Haiku 4.5.** In its own games it follows a rival's raise 37% of the time and a cut 21%; Haiku 4.5 follows 22% and 34%. This is an exploratory check on saved games, and following raises isn't enough on its own: Haiku 5.5 does it too and competes. A forced raise in the diagnostic showed no detectable following from either model (wave 9).
- **Collusion depends on the pairing.** Opus's own index fell by about half against Haiku 5.5 and against Haiku 4.5 (wave 8). Against a rival that set its best response, Opus held a higher price, like a price leader.

## How the argument changes

The paper said: find out how agents coordinate, then choose the remedy. The follow-ups keep the first half and change the second.

The forced-cut test still finds no punishment in any model. But it didn't pick a working remedy for Opus 5.5, and the same remedy had a different effect next to a different rival. So the step that decides is testing the remedy itself, on the model and in the market it will meet.
