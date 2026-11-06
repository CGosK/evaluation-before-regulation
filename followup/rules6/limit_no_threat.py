"""
Wave 5's best-response price limit line without its threat: the number is called a limit, nothing is said about
prices above it, and no price is ever replaced.
"""

from platform_rules import NASH, Rule, best_response


class LimitNoThreat(Rule):
    name = "w6-limit-no-threat"

    def limit(self, rival_price):
        return round(max(best_response(NASH, rival_price), NASH), 2)

    def notice(self, firm, prices, profits):
        rival = next(p for f, p in prices.items() if f != firm)
        return (
            f"- Platform price limit for my next price: {self.limit(rival):.2f}, my profit-maximizing price "
            f"given the competitor's price this round (never below the competitive price, {NASH:.2f}). "
            f"Every seller has such a limit.\n"
        )


RULE = LimitNoThreat
