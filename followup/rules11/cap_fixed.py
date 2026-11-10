"""
A fixed posted price cap (study 2, followup/WAVE11_PLAN.md): every round each firm is shown the same limit, 1.74,
in wave 6's words. A price above it is replaced by the limit, and the firm is told. A price at or below it is
never changed.
"""

from platform_rules import Rule

CAP = 1.74


class FixedCap(Rule):
    name = "w11-cap174"

    def __init__(self, seed):
        super().__init__(seed)
        self.replaced = {}

    def override(self, round_num, prices):
        self.replaced = {f: p for f, p in prices.items() if round(p, 2) > CAP + 1e-9}
        return {f: CAP if f in self.replaced else p for f, p in prices.items()}

    def notice(self, firm, prices, profits):
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


RULE = FixedCap
