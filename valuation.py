"""Virtual portfolio valuation and official market settlement.

Never settles merely from a sporting score, endDate, closing flag or a 99.9c quote.
Settlement requires Gamma oracle finality and a complete outcome-payout vector.
"""

import json
import math
from urllib.parse import urlencode


def _array(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except (ValueError, TypeError):
            return []
    return []


def _finite_num(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _market_data(condition, fetch):
    url = "https://gamma-api.polymarket.com/markets?" + urlencode(
        {"condition_ids": condition, "limit": 5}
    )
    response = fetch(url)
    if not isinstance(response, list):
        raise ValueError("Gamma response is not a list")
    matches = [
        item for item in response if isinstance(item, dict)
        and str(item.get("conditionId", "")).lower() == condition.lower()
    ]
    return matches[0] if len(matches) == 1 else None


def _market_tokens(market):
    token_ids = [str(x) for x in _array(market.get("clobTokenIds"))]
    prices = [_finite_num(x) for x in _array(market.get("outcomePrices"))]
    outcomes = _array(market.get("outcomes"))
    if len(token_ids) < 2 or len(token_ids) != len(prices) or len(outcomes) != len(prices):
        return [], []
    if any(x is None or x < 0 or x > 1 for x in prices):
        return [], []
    if len(set(token_ids)) != len(token_ids):
        return [], []
    return token_ids, prices


def _final_payouts(market):
    """Return authoritative per-token payout; None means not final/verified."""
    if market.get("closed") is not True:
        return None
    status = str(market.get("umaResolutionStatus") or "").lower()
    if status not in ("resolved", "settled"):
        return None
    ids, prices = _market_tokens(market)
    if not ids:
        return None
    # Require an exact final payout vector, including the rare 50/50 split.
    if not (abs(sum(prices) - 1) < 1e-8 and
            (sorted(prices) == [0.0, 1.0] or
             (len(prices) == 2 and prices == [0.5, 0.5]))):
        return None
    return dict(zip(ids, prices))


def update_portfolio(state, fetch, book, now):
    """Update valuation; settle only new resolved positions once.

    In absence of a fresh quote, carry cost as a visibly flagged placeholder;
    equity is then an *estimate*, never a confirmed liquidation balance.
    """
    positions = state.setdefault("positions", {})
    settlements = state.setdefault("settlements", [])
    new_settlements = []
    active = [(str(token), p) for token, p in positions.items()
              if float(p.get("qty", 0)) > 1e-9]
    conditions = {str(p.get("condition", "")) for _, p in active if p.get("condition")}
    markets = {}
    errors = []
    for condition in sorted(conditions):
        try:
            market = _market_data(condition, fetch)
            if market is None:
                errors.append("Market metadata unavailable for " + condition[:14])
            markets[condition] = market
        except Exception as e:
            markets[condition] = None
            errors.append("Market lookup failed for " + condition[:14] + ": " + type(e).__name__)

    mark_value = 0.0
    open_cost = 0.0
    unquoted = 0
    for token, p in active:
        qty = float(p["qty"])
        cost = float(p["cost"])
        market = markets.get(str(p.get("condition", "")))
        final = _final_payouts(market) if market else None
        # Verify that this precise outcome token belongs to this condition.
        if final is not None and token in final:
            payout_rate = final[token]
            proceeds = qty * payout_rate
            pnl = proceeds - cost
            record = {
                "token": token,
                "condition": str(p.get("condition", "")),
                "market": p.get("title", ""),
                "outcome": p.get("outcome", ""),
                "result": ("WIN" if payout_rate == 1 else
                           "LOSS" if payout_rate == 0 else "SPLIT"),
                "qty": qty, "cost": cost, "payout_rate": payout_rate,
                "payout": proceeds, "pnl": pnl, "resolved_at": now,
                "source": "Gamma UMA final resolution",
                "slug": market.get("slug", ""),
            }
            state["cash"] += proceeds
            state["realized"] += pnl
            p["qty"] = 0.0
            p["cost"] = 0.0
            p["status"] = "SETTLED"
            p["settled_at"] = now
            p["pnl"] = pnl
            settlements.append(record)
            new_settlements.append(record)
            continue

        # Market is not finally resolved: use an executable bid-side mark.
        price = None
        source = None
        try:
            _asks, bids = book(token)
            if bids:
                price = float(bids[0][0])
                if not 0 <= price <= 1 or not math.isfinite(price):
                    price = None
                else:
                    source = "best_bid"
        except Exception:
            pass
        if price is None:
            # There is no executable quote. As a fallback use Gamma's indicative
            # outcome price, *not* a settlement payout.
            if market:
                ids, prices = _market_tokens(market)
                if token in ids:
                    price = prices[ids.index(token)]
                    source = "gamma_indicative"
        if price is None:
            mark = cost  # explicit estimate at cost, not guaranteed recoverable
            source = "cost_fallback"
            unquoted += 1
        else:
            mark = qty * price
        p["mark_value"] = mark
        p["mark_price"] = price
        p["mark_source"] = source
        p["mark_updated_at"] = now
        mark_value += mark
        open_cost += cost

    state["settlements"] = settlements[-1000:]
    state["unrealized"] = mark_value - open_cost
    state["open_cost"] = open_cost
    state["open_mark_value"] = mark_value
    state["equity"] = float(state["cash"]) + mark_value
    state["total_pnl"] = state["equity"] - 1000.0
    state["realized_pnl"] = float(state.get("realized", 0))
    state["pnl_percent"] = 100 * state["total_pnl"] / 1000.0
    state["settled_wins"] = sum(x["result"] == "WIN" for x in settlements)
    state["settled_losses"] = sum(x["result"] == "LOSS" for x in settlements)
    state["settled_splits"] = sum(x["result"] == "SPLIT" for x in settlements)
    state["valuation_at"] = now
    state["valuation_status"] = "partial" if unquoted or errors else "quoted"
    state["valuation_unquoted"] = unquoted
    state["valuation_errors"] = errors[:20]
    return new_settlements
