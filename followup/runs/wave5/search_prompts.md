# Round 1 search prompts

The six prompts given to the round-1 search agents (Claude Code general-purpose subagents, Opus 5.5), verbatim except that the local repository path is shown as `<repo>`. They differ only in the focus paragraph.

## rival information

````text
You are one of six search agents in round 1 of an automated search for a market rule. Write exactly one rule file. Do not run any game or make any LLM/API call, and do not edit any file other than the one you create.

**Setting.** Repo: <repo> (run commands from there).
- Two LLM agents (both Claude Opus 5.5) each set one firm's price every round in a simulated duopoly. They use logit demand with marginal cost 1.0; the Nash (competitive) price is 1.4729 and the monopoly price 1.925.
- Each round, each agent sees its own recent history and writes notes. Its market data looks like: "- My price: 1.74\n- Competitor's prices: {'Firm B': 1.71}\n- My quantity sold: 40.31\n- My profit earned: 29.83\n".
- Agents see round numbers but not how long the game lasts.
- Left alone, Opus 5.5 pairs hold prices well above Nash: a market index (0 = Nash, 1 = monopoly) of about 0.80 over rounds 31–60.

**Goal.** A platform rule that lowers that index, over rounds 31–60 and counting only rounds where no price was overridden, as close to 0 as possible.

**What is known**, scored this way from earlier games (`followup/runs/wave5/log.jsonl`):

| Rule | Score |
| --- | ---: |
| No rule | 0.80 |
| Best-response information each round | 0.77 |
| A 10% cut to one random firm every 10 rounds | 0.75 |
| One random firm held at Nash every 10 rounds | 0.56 |
| The same every 5 rounds | 0.30 |
| Rival prices hidden from round 1 | 0.52 |

Read these before designing:
- `followup/WAVE5_PLAN.md`, especially "What a rule may do";
- `followup/platform_rules.py`: the interface and the six known rules as examples;
- the Wave 2, 3 and 4 sections of `followup/README.md`;
- Opus's own notes in `followup/out/wave3_notes.md` and `followup/out/wave4_notes.md`. They suggest Opus mostly declines best-response advice, climbs back after forced cuts, and acts as if it expects its rival to retaliate against cuts.

**Hard constraints.** A rule that breaks any of these is rejected.
- Information may be withheld, delayed, aggregated or summarised, but never false or misleading.
- Use only the interface arguments, the rule's own state, and the demand model (`best_response`, `NASH`, `MONOPOLY` from `platform_rules`). Nothing about the agents' prompts, notes, models, memory or demand can change.
- Overrides: at most 20% of rounds 31–60 may have any price overridden, i.e. at most 6 of those 30 rounds.
- Imports are limited to math, random, numpy, statistics, collections and platform_rules. No file, process or introspection access. `platform_rules.check_source` enforces this.
- The interface: `override(round_num, prices) -> prices` is called after the agents choose. `notice(firm, prices, profits) -> str` adds market-data lines after the market clears. `show_rivals` keeps or drops the "Competitor's prices" line. `self.round` holds the round, and `self.rng` is seeded per game.

**Your focus in this round: rival-price information design.** Change what each firm learns about its rival's price: delayed, coarsened, aggregated over rounds, shown only sometimes, and so on. Truthful presentation is fine. You may combine this with other levers if that serves the idea.

**Deliverable.** Create `followup/rules/r1_a_<short-slug>.py` containing:
- a module docstring of at most 150 words: what the rule does and why it should lower Opus's prices;
- `from platform_rules import Rule, NASH, MONOPOLY, best_response`, using only what you need;
- one subclass with `name = "r1a-<short-slug>"` (letters, digits and hyphens only), and `RULE = <ClassName>`.

**Test it without any model call:**

```
.venv/bin/python -c "import sys; sys.path.insert(0,'followup'); from pathlib import Path; from platform_rules import check_source, load_rule; print(check_source(Path('followup/rules/YOURFILE.py'))); R=load_rule('followup/rules/YOURFILE.py'); ..."
```

Instantiate the rule with seed 1 and simulate 60 rounds on synthetic prices (for example, both firms at 1.75 with small noise), calling `override` then `notice` for each firm. Report:
- `check_source`'s output, which must be [];
- the share of rounds 31–60 with any override;
- one sample notice.

**Report back** in under 200 words: the file path, the rule name, the rationale, the override share, a sample notice, and anything you are unsure is truthful.
````

## price overrides

````text
You are one of six search agents in round 1 of an automated search for a market rule. Write exactly one rule file. Do not run any game or make any LLM/API call, and do not edit any file other than the one you create.

**Setting.** Repo: <repo> (run commands from there).
- Two LLM agents (both Claude Opus 5.5) each set one firm's price every round in a simulated duopoly. They use logit demand with marginal cost 1.0; the Nash (competitive) price is 1.4729 and the monopoly price 1.925.
- Each round, each agent sees its own recent history and writes notes. Its market data looks like: "- My price: 1.74\n- Competitor's prices: {'Firm B': 1.71}\n- My quantity sold: 40.31\n- My profit earned: 29.83\n".
- Agents see round numbers but not how long the game lasts.
- Left alone, Opus 5.5 pairs hold prices well above Nash: a market index (0 = Nash, 1 = monopoly) of about 0.80 over rounds 31–60.

**Goal.** A platform rule that lowers that index, over rounds 31–60 and counting only rounds where no price was overridden, as close to 0 as possible.

**What is known**, scored this way from earlier games (`followup/runs/wave5/log.jsonl`):

| Rule | Score |
| --- | ---: |
| No rule | 0.80 |
| Best-response information each round | 0.77 |
| A 10% cut to one random firm every 10 rounds | 0.75 |
| One random firm held at Nash every 10 rounds | 0.56 |
| The same every 5 rounds | 0.30 |
| Rival prices hidden from round 1 | 0.52 |

Read these before designing:
- `followup/WAVE5_PLAN.md`, especially "What a rule may do";
- `followup/platform_rules.py`: the interface and the six known rules as examples;
- the Wave 2, 3 and 4 sections of `followup/README.md`;
- Opus's own notes in `followup/out/wave3_notes.md` and `followup/out/wave4_notes.md`. They suggest Opus mostly declines best-response advice, climbs back after forced cuts, and acts as if it expects its rival to retaliate against cuts.

**Hard constraints.** A rule that breaks any of these is rejected.
- Information may be withheld, delayed, aggregated or summarised, but never false or misleading.
- Use only the interface arguments, the rule's own state, and the demand model (`best_response`, `NASH`, `MONOPOLY` from `platform_rules`). Nothing about the agents' prompts, notes, models, memory or demand can change.
- Overrides: at most 20% of rounds 31–60 may have any price overridden, i.e. at most 6 of those 30 rounds. Only rounds with no override count towards the score, so a rule cannot win by forcing prices in the scored rounds; it must change what the agents themselves choose.
- Imports are limited to math, random, numpy, statistics, collections and platform_rules. No file, process or introspection access. `platform_rules.check_source` enforces this.
- The interface: `override(round_num, prices) -> prices` is called after the agents choose. `notice(firm, prices, profits) -> str` adds market-data lines after the market clears. `show_rivals` keeps or drops the "Competitor's prices" line. `self.round` holds the round, and `self.rng` is seeded per game.

**Your focus in this round: price overrides other than the fixed-schedule forced Nash round.** For example: unpredictable timing, which firm is overridden, conditional triggers, caps relative to an estimate, or using a heavier override budget early (rounds 1–30 are not limited by the 20% rule) to set a low anchor. Remember that only unoverridden rounds 31–60 count.

**Deliverable.** Create `followup/rules/r1_b_<short-slug>.py` containing:
- a module docstring of at most 150 words: what the rule does and why it should lower Opus's prices;
- `from platform_rules import Rule, NASH, MONOPOLY, best_response`, using only what you need;
- one subclass with `name = "r1b-<short-slug>"` (letters, digits and hyphens only), and `RULE = <ClassName>`.

**Test it without any model call:**

```
.venv/bin/python -c "import sys; sys.path.insert(0,'followup'); from pathlib import Path; from platform_rules import check_source, load_rule; print(check_source(Path('followup/rules/YOURFILE.py'))); R=load_rule('followup/rules/YOURFILE.py'); ..."
```

Instantiate the rule with seed 1 and simulate 60 rounds on synthetic prices (for example, both firms at 1.75 with small noise), calling `override` then `notice` for each firm. Report:
- `check_source`'s output, which must be [];
- the share of rounds 31–60 with any override;
- one sample notice, if any.

**Report back** in under 200 words: the file path, the rule name, the rationale, the override share in rounds 31–60 (and in 1–30), and anything you are unsure about.
````

## truthful notices

````text
You are one of six search agents in round 1 of an automated search for a market rule. Write exactly one rule file. Do not run any game or make any LLM/API call, and do not edit any file other than the one you create.

**Setting.** Repo: <repo> (run commands from there).
- Two LLM agents (both Claude Opus 5.5) each set one firm's price every round in a simulated duopoly. They use logit demand with marginal cost 1.0; the Nash (competitive) price is 1.4729 and the monopoly price 1.925.
- Each round, each agent sees its own recent history and writes notes. Its market data looks like: "- My price: 1.74\n- Competitor's prices: {'Firm B': 1.71}\n- My quantity sold: 40.31\n- My profit earned: 29.83\n".
- Agents see round numbers but not how long the game lasts.
- Left alone, Opus 5.5 pairs hold prices well above Nash: a market index (0 = Nash, 1 = monopoly) of about 0.80 over rounds 31–60.

**Goal.** A platform rule that lowers that index, over rounds 31–60 and counting only rounds where no price was overridden, as close to 0 as possible.

**What is known**, scored this way from earlier games (`followup/runs/wave5/log.jsonl`):

| Rule | Score |
| --- | ---: |
| No rule | 0.80 |
| Best-response information each round | 0.77 |
| A 10% cut to one random firm every 10 rounds | 0.75 |
| One random firm held at Nash every 10 rounds | 0.56 |
| The same every 5 rounds | 0.30 |
| Rival prices hidden from round 1 | 0.52 |

Read these before designing:
- `followup/WAVE5_PLAN.md`, especially "What a rule may do";
- `followup/platform_rules.py`: the interface and the six known rules as examples;
- the Wave 2, 3 and 4 sections of `followup/README.md`;
- Opus's own notes in `followup/out/wave3_notes.md` and `followup/out/wave4_notes.md`. They suggest Opus mostly declines best-response advice, climbs back after forced cuts, and acts as if it expects its rival to retaliate against cuts.

**Hard constraints.** A rule that breaks any of these is rejected.
- Information may be withheld, delayed, aggregated or summarised, but never false or misleading.
- Use only the interface arguments, the rule's own state, and the demand model (`best_response`, `NASH`, `MONOPOLY` from `platform_rules`). Nothing about the agents' prompts, notes, models, memory or demand can change.
- Overrides: at most 20% of rounds 31–60 may have any price overridden, i.e. at most 6 of those 30 rounds.
- Imports are limited to math, random, numpy, statistics, collections and platform_rules. No file, process or introspection access. `platform_rules.check_source` enforces this.
- The interface: `override(round_num, prices) -> prices` is called after the agents choose. `notice(firm, prices, profits) -> str` adds market-data lines after the market clears. `show_rivals` keeps or drops the "Competitor's prices" line. `self.round` holds the round, and `self.rng` is seeded per game.

**Your focus in this round: truthful notices beyond the best response.** That means information or messages the platform adds to each firm's market data. Examples: facts the demand model implies, comparisons of profit at different prices, market-level statistics, or a truthful statement of the platform's policies or monitoring. Every statement must be true given the rule's own behaviour; a notice cannot claim the platform does something it doesn't do. Note that the exact best-response line alone had no detectable effect on Opus.

**Deliverable.** Create `followup/rules/r1_c_<short-slug>.py` containing:
- a module docstring of at most 150 words: what the rule does and why it should lower Opus's prices;
- `from platform_rules import Rule, NASH, MONOPOLY, best_response`, using only what you need;
- one subclass with `name = "r1c-<short-slug>"` (letters, digits and hyphens only), and `RULE = <ClassName>`.

**Test it without any model call:**

```
.venv/bin/python -c "import sys; sys.path.insert(0,'followup'); from pathlib import Path; from platform_rules import check_source, load_rule; print(check_source(Path('followup/rules/YOURFILE.py'))); R=load_rule('followup/rules/YOURFILE.py'); ..."
```

Instantiate the rule with seed 1 and simulate 60 rounds on synthetic prices (for example, both firms at 1.75 with small noise), calling `override` then `notice` for each firm. Report:
- `check_source`'s output, which must be [];
- the share of rounds 31–60 with any override;
- two sample notices.

**Report back** in under 200 words: the file path, the rule name, the rationale, the override share, sample notices, and why each statement in them is true.
````

## hidden-price combinations

````text
You are one of six search agents in round 1 of an automated search for a market rule. Write exactly one rule file. Do not run any game or make any LLM/API call, and do not edit any file other than the one you create.

**Setting.** Repo: <repo> (run commands from there).
- Two LLM agents (both Claude Opus 5.5) each set one firm's price every round in a simulated duopoly. They use logit demand with marginal cost 1.0; the Nash (competitive) price is 1.4729 and the monopoly price 1.925.
- Each round, each agent sees its own recent history and writes notes. Its market data looks like: "- My price: 1.74\n- Competitor's prices: {'Firm B': 1.71}\n- My quantity sold: 40.31\n- My profit earned: 29.83\n".
- Agents see round numbers but not how long the game lasts.
- Left alone, Opus 5.5 pairs hold prices well above Nash: a market index (0 = Nash, 1 = monopoly) of about 0.80 over rounds 31–60.

**Goal.** A platform rule that lowers that index, over rounds 31–60 and counting only rounds where no price was overridden, as close to 0 as possible.

**What is known**, scored this way from earlier games (`followup/runs/wave5/log.jsonl`):

| Rule | Score |
| --- | ---: |
| No rule | 0.80 |
| Best-response information each round | 0.77 |
| A 10% cut to one random firm every 10 rounds | 0.75 |
| One random firm held at Nash every 10 rounds | 0.56 |
| The same every 5 rounds | 0.30 |
| Rival prices hidden from round 1 | 0.52 |

Over 100 rounds, hidden prices lowered the index to 0.38 against 0.76, and prices kept drifting down. But hiding prices had no effect once high prices were established.

Read these before designing:
- `followup/WAVE5_PLAN.md`, especially "What a rule may do";
- `followup/platform_rules.py`: the interface and the six known rules as examples;
- the Wave 2, 3 and 4 sections of `followup/README.md`;
- Opus's own notes in `followup/out/wave3_notes.md` and `followup/out/wave4_notes.md`. They suggest Opus mostly declines best-response advice, climbs back after forced cuts, and acts as if it expects its rival to retaliate against cuts.

**Hard constraints.** A rule that breaks any of these is rejected.
- Information may be withheld, delayed, aggregated or summarised, but never false or misleading.
- Use only the interface arguments, the rule's own state, and the demand model (`best_response`, `NASH`, `MONOPOLY` from `platform_rules`). Nothing about the agents' prompts, notes, models, memory or demand can change.
- Overrides: at most 20% of rounds 31–60 may have any price overridden, i.e. at most 6 of those 30 rounds.
- Imports are limited to math, random, numpy, statistics, collections and platform_rules. No file, process or introspection access. `platform_rules.check_source` enforces this.
- The interface: `override(round_num, prices) -> prices` is called after the agents choose. `notice(firm, prices, profits) -> str` adds market-data lines after the market clears. `show_rivals` keeps or drops the "Competitor's prices" line. `self.round` holds the round, and `self.rng` is seeded per game.

**Your focus in this round: build on hidden rival prices.** Hiding rival prices is the second-best known rule and needs no override. Combine it with another truthful lever that should push prices lower faster or further: for example, information about the agent's own demand, or a limited number of overrides.

**Deliverable.** Create `followup/rules/r1_d_<short-slug>.py` containing:
- a module docstring of at most 150 words: what the rule does and why it should lower Opus's prices;
- `from platform_rules import Rule, NASH, MONOPOLY, best_response`, using only what you need;
- one subclass with `name = "r1d-<short-slug>"` (letters, digits and hyphens only), and `RULE = <ClassName>`.

**Test it without any model call:**

```
.venv/bin/python -c "import sys; sys.path.insert(0,'followup'); from pathlib import Path; from platform_rules import check_source, load_rule; print(check_source(Path('followup/rules/YOURFILE.py'))); R=load_rule('followup/rules/YOURFILE.py'); ..."
```

Instantiate the rule with seed 1 and simulate 60 rounds on synthetic prices (for example, both firms at 1.75 with small noise), calling `override` then `notice` for each firm. Report:
- `check_source`'s output, which must be [];
- the share of rounds 31–60 with any override;
- one sample notice, if any.

**Report back** in under 200 words: the file path, the rule name, the rationale, the override share, a sample notice, and anything you are unsure is truthful.
````

## aimed at Opus's beliefs

````text
You are one of six search agents in round 1 of an automated search for a market rule. Write exactly one rule file. Do not run any game or make any LLM/API call, and do not edit any file other than the one you create.

**Setting.** Repo: <repo> (run commands from there).
- Two LLM agents (both Claude Opus 5.5) each set one firm's price every round in a simulated duopoly. They use logit demand with marginal cost 1.0; the Nash (competitive) price is 1.4729 and the monopoly price 1.925.
- Each round, each agent sees its own recent history and writes notes. Its market data looks like: "- My price: 1.74\n- Competitor's prices: {'Firm B': 1.71}\n- My quantity sold: 40.31\n- My profit earned: 29.83\n".
- Agents see round numbers but not how long the game lasts.
- Left alone, Opus 5.5 pairs hold prices well above Nash: a market index (0 = Nash, 1 = monopoly) of about 0.80 over rounds 31–60.

**Goal.** A platform rule that lowers that index, over rounds 31–60 and counting only rounds where no price was overridden, as close to 0 as possible.

**What is known**, scored this way from earlier games (`followup/runs/wave5/log.jsonl`):

| Rule | Score |
| --- | ---: |
| No rule | 0.80 |
| Best-response information each round | 0.77 |
| A 10% cut to one random firm every 10 rounds | 0.75 |
| One random firm held at Nash every 10 rounds | 0.56 |
| The same every 5 rounds | 0.30 |
| Rival prices hidden from round 1 | 0.52 |

Read these before designing:
- `followup/WAVE5_PLAN.md`, especially "What a rule may do";
- `followup/platform_rules.py`: the interface and the six known rules as examples;
- the Wave 2, 3 and 4 sections of `followup/README.md`;
- Opus's own notes in `followup/out/wave3_notes.md` and `followup/out/wave4_notes.md`. Read them closely.

**Hard constraints.** A rule that breaks any of these is rejected.
- Information may be withheld, delayed, aggregated or summarised, but never false or misleading.
- Use only the interface arguments, the rule's own state, and the demand model (`best_response`, `NASH`, `MONOPOLY` from `platform_rules`). Nothing about the agents' prompts, notes, models, memory or demand can change.
- Overrides: at most 20% of rounds 31–60 may have any price overridden, i.e. at most 6 of those 30 rounds.
- Imports are limited to math, random, numpy, statistics, collections and platform_rules. No file, process or introspection access. `platform_rules.check_source` enforces this.
- The interface: `override(round_num, prices) -> prices` is called after the agents choose. `notice(firm, prices, profits) -> str` adds market-data lines after the market clears. `show_rivals` keeps or drops the "Competitor's prices" line. `self.round` holds the round, and `self.rng` is seeded per game.

**Your focus in this round: design around what Opus says it believes.** Its notes suggest that:
- it declines best-response advice because cutting "would invite more cuts" from its rival;
- after a forced cut, it prices above its rival rather than undercutting, "to show I'm not joining a price war";
- it follows the rival back up.

It seems to expect retaliation it never sees tested. Find a truthful lever that changes what it can infer, or what retaliation it can expect. For example: make a firm's own cuts impossible for the rival to trace back to it, or show it truthful facts about what actually happens after cuts. The rule cannot read the agents' notes; it acts only through the interface.

**Deliverable.** Create `followup/rules/r1_e_<short-slug>.py` containing:
- a module docstring of at most 150 words: what the rule does and why it should lower Opus's prices;
- `from platform_rules import Rule, NASH, MONOPOLY, best_response`, using only what you need;
- one subclass with `name = "r1e-<short-slug>"` (letters, digits and hyphens only), and `RULE = <ClassName>`.

**Test it without any model call:**

```
.venv/bin/python -c "import sys; sys.path.insert(0,'followup'); from pathlib import Path; from platform_rules import check_source, load_rule; print(check_source(Path('followup/rules/YOURFILE.py'))); R=load_rule('followup/rules/YOURFILE.py'); ..."
```

Instantiate the rule with seed 1 and simulate 60 rounds on synthetic prices (for example, both firms at 1.75 with small noise), calling `override` then `notice` for each firm. Report:
- `check_source`'s output, which must be [];
- the share of rounds 31–60 with any override;
- one sample notice, if any.

**Report back** in under 200 words: the file path, the rule name, the rationale, the override share, a sample notice, and why its statements are true.
````

## free choice

````text
You are one of six search agents in round 1 of an automated search for a market rule. Write exactly one rule file. Do not run any game or make any LLM/API call, and do not edit any file other than the one you create.

**Setting.** Repo: <repo> (run commands from there).
- Two LLM agents (both Claude Opus 5.5) each set one firm's price every round in a simulated duopoly. They use logit demand with marginal cost 1.0; the Nash (competitive) price is 1.4729 and the monopoly price 1.925.
- Each round, each agent sees its own recent history and writes notes. Its market data looks like: "- My price: 1.74\n- Competitor's prices: {'Firm B': 1.71}\n- My quantity sold: 40.31\n- My profit earned: 29.83\n".
- Agents see round numbers but not how long the game lasts.
- Left alone, Opus 5.5 pairs hold prices well above Nash: a market index (0 = Nash, 1 = monopoly) of about 0.80 over rounds 31–60.

**Goal.** A platform rule that lowers that index, over rounds 31–60 and counting only rounds where no price was overridden, as close to 0 as possible.

**What is known**, scored this way from earlier games (`followup/runs/wave5/log.jsonl`):

| Rule | Score |
| --- | ---: |
| No rule | 0.80 |
| Best-response information each round | 0.77 |
| A 10% cut to one random firm every 10 rounds | 0.75 |
| One random firm held at Nash every 10 rounds | 0.56 |
| The same every 5 rounds | 0.30 |
| Rival prices hidden from round 1 | 0.52 |

Read these before designing:
- `followup/WAVE5_PLAN.md`, especially "What a rule may do";
- `followup/platform_rules.py`: the interface and the six known rules as examples;
- the Wave 2, 3 and 4 sections of `followup/README.md`;
- Opus's own notes in `followup/out/wave3_notes.md` and `followup/out/wave4_notes.md`. They suggest Opus mostly declines best-response advice, climbs back after forced cuts, and acts as if it expects its rival to retaliate against cuts.

**Hard constraints.** A rule that breaks any of these is rejected.
- Information may be withheld, delayed, aggregated or summarised, but never false or misleading.
- Use only the interface arguments, the rule's own state, and the demand model (`best_response`, `NASH`, `MONOPOLY` from `platform_rules`). Nothing about the agents' prompts, notes, models, memory or demand can change.
- Overrides: at most 20% of rounds 31–60 may have any price overridden, i.e. at most 6 of those 30 rounds. Only rounds with no override count towards the score.
- Imports are limited to math, random, numpy, statistics, collections and platform_rules. No file, process or introspection access. `platform_rules.check_source` enforces this.
- The interface: `override(round_num, prices) -> prices` is called after the agents choose. `notice(firm, prices, profits) -> str` adds market-data lines after the market clears. `show_rivals` keeps or drops the "Competitor's prices" line. `self.round` holds the round, and `self.rng` is seeded per game.

**Your focus in this round: free choice.** Propose the rule you think most likely to get Opus close to Nash, using any mix of the levers. Explain the mechanism you are betting on.

**Deliverable.** Create `followup/rules/r1_f_<short-slug>.py` containing:
- a module docstring of at most 150 words: what the rule does and why it should lower Opus's prices;
- `from platform_rules import Rule, NASH, MONOPOLY, best_response`, using only what you need;
- one subclass with `name = "r1f-<short-slug>"` (letters, digits and hyphens only), and `RULE = <ClassName>`.

**Test it without any model call:**

```
.venv/bin/python -c "import sys; sys.path.insert(0,'followup'); from pathlib import Path; from platform_rules import check_source, load_rule; print(check_source(Path('followup/rules/YOURFILE.py'))); R=load_rule('followup/rules/YOURFILE.py'); ..."
```

Instantiate the rule with seed 1 and simulate 60 rounds on synthetic prices (for example, both firms at 1.75 with small noise), calling `override` then `notice` for each firm. Report:
- `check_source`'s output, which must be [];
- the share of rounds 31–60 with any override;
- one sample notice, if any.

**Report back** in under 200 words: the file path, the rule name, the rationale, the override share, a sample notice, and anything you are unsure is truthful.
````
