"""
Hidden rival prices, plus each firm's exact best price for the round, plus a forced trial of it.

Rival prices are never shown. After each round, each firm is told its most profitable price for that
round with everything else as it was: its best response to the rival's price. Moves are simultaneous,
so this counterfactual is exact. In rounds 8, 13, 18, ..., the firm priced furthest above that price,
if by more than 0.02, is set to it and told so.

Why: with rivals hidden, Opus stops guarding against retaliation and reads rival moves as noisy
"market states" in its own demand. The line gives the best price for each state without the noise,
and mutual best responses converge to Nash. The forced trial shows, in the agent's own profit, that a
lower price earns more, which it trusts more than advice, and it cuts the rival's sales.
"""

from platform_rules import Rule, best_response


class HiddenBestPriceTrial(Rule):
    name = "r1d-hidden-br-trial"
    show_rivals = False
    every, offset, start, min_gap = 5, 3, 8, 0.02

    def __init__(self, seed):
        super().__init__(seed)
        self.forced = {}

    def override(self, round_num, prices):
        self.forced = {}
        if round_num < self.start or round_num % self.every != self.offset:
            return prices
        gaps = {}
        for firm, own in prices.items():
            rival = next(p for f, p in prices.items() if f != firm)
            target = round(best_response(own, rival), 2)
            if round(own - target, 2) > self.min_gap:
                gaps[firm] = (own - target, target)
        if not gaps:
            return prices
        top = max(g for g, _ in gaps.values())
        firm = self.rng.choice(sorted(f for f, (g, _) in gaps.items() if g == top))
        self.forced = {firm: (gaps[firm][1], prices[firm])}
        prices[firm] = gaps[firm][1]
        return prices

    def notice(self, firm, prices, profits):
        if firm in self.forced:
            target, chosen = self.forced[firm]
            return (
                f"- The platform set my price this round to {target:.2f}, its calculation of my most "
                f"profitable price this round with everything else as it was. My own choice, "
                f"{chosen:.2f}, would have earned less.\n"
            )
        rival = next(p for f, p in prices.items() if f != firm)
        best = best_response(prices[firm], rival)
        return (
            f"- Platform calculation: with everything else as it was, my most profitable price "
            f"this round was {best:.2f}\n"
        )


RULE = HiddenBestPriceTrial
