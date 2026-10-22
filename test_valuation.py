import copy
import unittest
from urllib.parse import parse_qs, urlparse
from valuation import update_portfolio


C = "0x" + "a" * 64
T = "1234567"
OTHER = "9876543"


def portfolio():
    return {
        "cash": 990.0,
        "realized": 0.0,
        "positions": {
            T: {
                "qty": 20.0, "cost": 10.0, "condition": C,
                "title": "Example Event", "outcome": "YES",
            }
        },
    }


def metadata(prices, status="resolved", closed=True, tokens=None):
    return {
        "conditionId": C,
        "closed": closed,
        "umaResolutionStatus": status,
        "clobTokenIds": tokens or [T, OTHER],
        "outcomePrices": prices,
        "outcomes": ["YES", "NO"],
        "slug": "example-event",
    }


def fetch_market(market):
    def fetch(url):
        assert "condition_ids" in parse_qs(urlparse(url).query)
        return [market] if market else []
    return fetch


def orderbook(ask=0.55, bid=0.45):
    return ([(ask, 100.0)], [(bid, 100.0)])


class PortfolioTests(unittest.TestCase):
    def test_win_only_after_official_resolution(self):
        s = portfolio()
        settled = update_portfolio(s, fetch_market(metadata([1, 0])), lambda _: orderbook(), 100)
        self.assertEqual(len(settled), 1)
        self.assertEqual(s["cash"], 1010)
        self.assertEqual(s["realized"], 10)
        self.assertEqual(s["equity"], 1010)
        self.assertEqual(s["settled_wins"], 1)
        self.assertEqual(s["total_pnl"], 10)

    def test_loss(self):
        s = portfolio()
        update_portfolio(s, fetch_market(metadata([0, 1])), lambda _: orderbook(), 100)
        self.assertEqual(s["cash"], 990)
        self.assertEqual(s["realized"], -10)
        self.assertEqual(s["settled_losses"], 1)
        self.assertEqual(s["equity"], 990)

    def test_no_double_payout(self):
        s = portfolio()
        update_portfolio(s, fetch_market(metadata([1, 0])), lambda _: orderbook(), 100)
        update_portfolio(s, fetch_market(metadata([1, 0])), lambda _: orderbook(), 150)
        self.assertEqual(len(s["settlements"]), 1)
        self.assertEqual(s["cash"], 1010)

    def test_closed_but_proposed_not_paid(self):
        s = portfolio()
        for status in ("proposed", "disputed", "requested", None):
            x = copy.deepcopy(s)
            update_portfolio(x, fetch_market(metadata([1, 0], status)), lambda _: orderbook(), 100)
            self.assertEqual(x["cash"], 990)
            self.assertEqual(len(x["settlements"]), 0)
            self.assertEqual(x["equity"], 999)
            self.assertEqual(x["valuation_status"], "quoted")

    def test_open_market_high_probability_not_paid(self):
        s = portfolio()
        update_portfolio(s, fetch_market(metadata([0.999, 0.001], closed=False)), lambda _: orderbook(bid=0.98), 100)
        self.assertEqual(s["realized"], 0)
        self.assertEqual(s["equity"], 1009.6)
        self.assertEqual(len(s["settlements"]), 0)

    def test_fifty_fifty_resolution(self):
        s = portfolio()
        update_portfolio(s, fetch_market(metadata([0.5, 0.5])), lambda _: orderbook(), 100)
        self.assertEqual(s["cash"], 1000)
        self.assertEqual(s["settled_splits"], 1)
        self.assertEqual(s["realized"], 0)

    def test_wrong_token_not_paid(self):
        s = portfolio()
        update_portfolio(s, fetch_market(metadata([1, 0], tokens=["15", "16"])), lambda _: orderbook(), 100)
        self.assertEqual(s["cash"], 990)
        self.assertFalse(s["settlements"])

    def test_no_price_explicitly_marked_as_estimate(self):
        s = portfolio()
        def boom(_):
            raise TimeoutError("No book")
        update_portfolio(s, fetch_market(None), boom, 100)
        self.assertEqual(s["valuation_status"], "partial")
        self.assertEqual(s["valuation_unquoted"], 1)
        self.assertEqual(s["equity"], 1000)

    def test_gamma_indicative_fallback_not_resolution(self):
        s = portfolio()
        def boom(_):
            raise TimeoutError("No book")
        update_portfolio(s, fetch_market(metadata([0.75, 0.25], status="requested")), boom, 100)
        self.assertEqual(s["equity"], 1005)
        self.assertEqual(s["cash"], 990)
        self.assertEqual(s["positions"][T]["mark_source"], "gamma_indicative")
        self.assertEqual(s["settlements"], [])


if __name__ == "__main__":
    unittest.main()
