"""Index investing with a fixed monthly contribution (dollar-cost averaging).

The math only: what a fixed amount buys at each price, and where the plan stands at a later price.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from invest_witus.money import to_money, to_shares


@dataclass(frozen=True, slots=True)
class Purchase:
    day: date
    price: Decimal
    amount: Decimal
    shares: Decimal


@dataclass(frozen=True, slots=True)
class Summary:
    purchases: int
    invested: Decimal
    shares: Decimal
    average_cost: Decimal
    value: Decimal
    gain: Decimal


def buy(day: date, amount: Decimal, price: Decimal) -> Purchase:
    """Spend `amount` at `price` and record the shares it buys."""
    if amount <= 0:
        raise ValueError(f"amount must be positive, got {amount}")
    if price <= 0:
        raise ValueError(f"price must be positive, got {price}")
    return Purchase(day=day, price=price, amount=amount, shares=to_shares(amount / price))


def plan_purchases(amount: Decimal, prices: list[tuple[date, Decimal]]) -> list[Purchase]:
    """Buy the same amount at every (day, price) in the list."""
    return [buy(day, amount, price) for day, price in prices]


def summarize(purchases: list[Purchase], latest_price: Decimal) -> Summary:
    """Total up the purchases and value the shares at `latest_price`."""
    if not purchases:
        raise ValueError("no purchases to summarize")
    invested = sum((p.amount for p in purchases), start=Decimal(0))
    shares = sum((p.shares for p in purchases), start=Decimal(0))
    value = to_money(shares * latest_price)
    return Summary(
        purchases=len(purchases),
        invested=invested,
        shares=shares,
        average_cost=to_money(invested / shares),
        value=value,
        gain=value - invested,
    )
