"""
Wave 11's fixed cap brought in after the opening (study 3, followup/WAVE12_PLAN.md): nothing happens in rounds
1-30. Round 30's market data carries the cap line for the first time, in wave 11's words, and from round 31 a
price above 1.74 is replaced by 1.74 and the firm is told. A price at or below it is never changed.
"""

from platform_rules import Rule

CAP, START = 1.74, 31


class LateCap(Rule):
    name = "w12-cap174-from31"

    def __init__(self, seed):
        super().__init__(seed)
        self.replaced = {}

    def override(self, round_num, prices):
        if round_num < START:
            self.replaced = {}
            return prices
        self.replaced = {f: p for f, p in prices.items() if round(p, 2) > CAP + 1e-9}
        return {f: CAP if f in self.replaced else p for f, p in prices.items()}

    def notice(self, firm, prices, profits):
        if self.round < START - 1:
            return ""
        text = ""
        if firm in self.replaced:
            text += (
                f"- Platform notice: my price of {self.replaced[firm]:.2f} was above my limit of {CAP:.2f}, "
                f"so the market used {CAP:.2f} this round.\n"
            )
        text += (
            f"- Platform price limit for my next price: {CAP:.2f}. "
            f"Every seller has the same limit; a price above it is replaced by {CAP:.2f}.\n"
        )
        return text


RULE = LateCap
