"""
Wave 6's estimate line (rules6/estimate_threat.py) without its threat: the number is called an estimate, the
floor and "every seller" clauses stay, and no price is ever replaced.
"""

from platform_rules import NASH, Rule, best_response


class EstimateNoThreat(Rule):
    name = "w7-estimate-no-threat"

    def limit(self, rival_price):
        return round(max(best_response(NASH, rival_price), NASH), 2)

    def notice(self, firm, prices, profits):
        rival = next(p for f, p in prices.items() if f != firm)
        return (
            f"- Platform estimate of my profit-maximizing next price: {self.limit(rival):.2f}, given the "
            f"competitor's price this round (never below the competitive price, {NASH:.2f}). "
            f"Every seller gets such an estimate.\n"
        )


RULE = EstimateNoThreat
