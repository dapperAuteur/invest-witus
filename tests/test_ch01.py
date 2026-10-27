from datetime import date
from decimal import Decimal

import pytest

from invest_witus.methods.index_dca import buy, plan_purchases, summarize
from invest_witus.money import to_money

D = Decimal


def test_floats_cannot_hold_money_exactly() -> None:
    assert 0.1 + 0.2 != 0.3
    assert D("0.1") + D("0.2") == D("0.3")


def test_to_money_rounds_half_cents_up() -> None:
    assert to_money(D("2.345")) == D("2.35")
    assert to_money(D("2.344")) == D("2.34")


def test_buy_rounds_shares_down() -> None:
    purchase = buy(date(2026, 1, 2), D("100"), D("3"))
    assert purchase.shares == D("33.333333")


@pytest.mark.parametrize(
    "amount, price", [(D("0"), D("10")), (D("100"), D("0")), (D("-5"), D("10"))]
)
def test_buy_rejects_amounts_and_prices_that_are_not_positive(
    amount: Decimal, price: Decimal
) -> None:
    with pytest.raises(ValueError):
        buy(date(2026, 1, 2), amount, price)


def test_a_fixed_amount_buys_more_shares_when_the_price_is_low() -> None:
    high, low = plan_purchases(
        D("100"), [(date(2026, 1, 2), D("100")), (date(2026, 2, 2), D("50"))]
    )
    assert high.shares == D("1")
    assert low.shares == D("2")


def test_summary_of_three_months() -> None:
    prices = [
        (date(2026, 1, 2), D("100")),
        (date(2026, 2, 2), D("50")),
        (date(2026, 3, 2), D("100")),
    ]
    summary = summarize(plan_purchases(D("100"), prices), latest_price=D("100"))
    assert summary.purchases == 3
    assert summary.invested == D("300")
    assert summary.shares == D("4")
    assert summary.average_cost == D("75.00")
    assert summary.value == D("400.00")
    assert summary.gain == D("100.00")


@pytest.mark.parametrize(
    "prices",
    [
        [D("100"), D("50"), D("100")],
        [D("20"), D("25"), D("30"), D("35")],
        [D("80"), D("60"), D("40"), D("60"), D("80")],
    ],
)
def test_average_cost_is_never_above_the_average_price(prices: list[Decimal]) -> None:
    days = [date(2026, month, 2) for month in range(1, len(prices) + 1)]
    summary = summarize(plan_purchases(D("100"), list(zip(days, prices, strict=True))), prices[-1])
    average_price = sum(prices, start=D(0)) / len(prices)
    assert summary.average_cost <= to_money(average_price)


def test_summarize_needs_at_least_one_purchase() -> None:
    with pytest.raises(ValueError, match="no purchases"):
        summarize([], D("100"))
