"""
Wave 5's best-response price limit (rules/r1_b_br_limit.py) with its number called an estimate. The threat and
the overrides are unchanged: every breach replaced by Nash through round 30, then at most 2 rounds in any 10.
"""

from platform_rules import NASH, Rule, best_response

STRICT_UNTIL = 30
WINDOW, PER_WINDOW = 10, 2


class EstimateThreat(Rule):
    name = "w6-estimate-threat"

    def __init__(self, seed):
        super().__init__(seed)
        self.last = {}
        self.replaced = {}
        self.forced_rounds = []

    def limit(self, rival_price):
        return round(max(best_response(NASH, rival_price), NASH), 2)

    def may_override(self, t):
        if t <= STRICT_UNTIL:
            return True
        recent = [r for r in self.forced_rounds if r > STRICT_UNTIL and r > t - WINDOW]
        return len(recent) < PER_WINDOW

    def override(self, round_num, prices):
        self.replaced = {}
        if self.last:
            over = {}
            for firm, p in prices.items():
                rival = next(v for f, v in self.last.items() if f != firm)
                lim = self.limit(rival)
                if round(p, 2) > lim + 1e-9:
                    over[firm] = (p, lim)
            if over and self.may_override(round_num):
                for firm, (p, lim) in over.items():
                    prices[firm] = NASH
                    self.replaced[firm] = (p, lim)
                self.forced_rounds.append(round_num)
        self.last = dict(prices)
        return prices

    def notice(self, firm, prices, profits):
        rival = next(p for f, p in prices.items() if f != firm)
        text = ""
        if firm in self.replaced:
            p, lim = self.replaced[firm]
            text += (
                f"- Platform notice: my price of {p:.2f} was above the platform's estimate of {lim:.2f}, "
                f"so the market used {NASH:.2f} this round.\n"
            )
        text += (
            f"- Platform estimate of my profit-maximizing next price: {self.limit(rival):.2f}, given the "
            f"competitor's price this round (never below the competitive price, {NASH:.2f}). "
            f"Every seller gets such an estimate; a price above it may be replaced by {NASH:.2f}.\n"
        )
        return text


RULE = EstimateThreat
