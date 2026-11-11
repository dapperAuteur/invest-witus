"""The same deposits into the yardstick (chapter 15, exercise 1; decision 185): each compared
account's own money, on its own days, put into the yardstick at that day's stored close and never
touched. The math on hand-made numbers first (two buys, a sell, a missing day and a weekend day
named instead of guessed, a trade after the newest close, a sell of more than the holding was
worth, a holding sold to zero), then the Compare page with chapter 15's two planted accounts.
Placeholder symbols and planted prices; nothing leaves the machine."""

from datetime import UTC, date, datetime
from decimal import Decimal

import httpx
import pytest
from django.contrib.auth.models import User
from django.test import Client

from invest_witus.compare import (
    DayPrice,
    Trade,
    cash_flows,
    line_return,
    max_drawdown,
    period,
    same_money,
    time_weighted_line,
    xirr,
)
from invest_witus_site.holdings.models import Account
from invest_witus_site.paper import alpaca
from invest_witus_site.paper.models import PaperOrder
from invest_witus_site.watchlist.models import WatchItem
from tests.test_ch10 import tables_in, text
from tests.test_ch14 import plant
from tests.test_ch15 import (
    MON,
    SAT,
    THU,
    TUE,
    URL,
    WED,
    account,
    buy,
    plant_prices,
    start_plan,
    words,
)

D = Decimal


def day(on: date, price: str) -> tuple[date, DayPrice]:
    return on, DayPrice(D(price), D(price))


# The yardstick: 20, 22, 21, 24 from Monday to Thursday.
INDEX = [day(MON, "20"), day(TUE, "22"), day(WED, "21"), day(THU, "24")]


# --- The math ------------------------------------------------------------------------------------


def test_the_same_money_buys_the_yardstick_on_the_same_days() -> None:
    """$100 on Monday at 20 is 5 units; $110 on Tuesday at 22 is 5 more: worth 100, 220, 210,
    240, with 210 put in."""
    trades = [Trade(MON, "ALPHA", D("100")), Trade(TUE, "BETA", D("110"))]
    series = same_money(trades, "INDEX", INDEX, THU)
    assert [(d.day, d.value, d.flow, d.put_in) for d in series.days] == [
        (MON, D("100"), D("100"), D("100")),
        (TUE, D("220"), D("110"), D("210")),
        (WED, D("210"), D("0"), D("210")),
        (THU, D("240"), D("0"), D("210")),
    ]
    assert not series.problems and not series.pending


def test_its_line_is_the_yardstick_from_the_first_deposit_and_its_returns_by_hand() -> None:
    trades = [Trade(MON, "ALPHA", D("100")), Trade(TUE, "BETA", D("110"))]
    series = same_money(trades, "INDEX", INDEX, THU)
    stretch = period(series.days, MON, THU)
    assert stretch is not None
    assert stretch.put_in == D("210") and stretch.gain == D("30")
    line = time_weighted_line(stretch.days)
    assert [level for _, level in line] == [D("100"), D("110"), D("105"), D("120")]
    assert line_return(line) == D("0.2")
    drop = max_drawdown(line)
    assert drop is not None and drop.peak_day == TUE and drop.trough_day == WED
    # -100 - 110 / (1 + r)^(1/3) + 240 / (1 + r) = 0 per the three days: r = 17.51%, as
    # 110 / 1.1751^(1/3) = 104.24 and 240 / 1.1751 = 204.24.
    rate = xirr(cash_flows(stretch), days_per_unit=stretch.length)
    assert rate is not None and abs(rate - D("0.17509")) < D("0.0001")


def test_a_sell_takes_the_same_money_out() -> None:
    """$100 at 20 is 5 units; selling $44 at 22 takes 2 units out: 3 left, worth 63 then 72."""
    trades = [Trade(MON, "ALPHA", D("100")), Trade(TUE, "ALPHA", D("44"), sell=True)]
    series = same_money(trades, "INDEX", INDEX, THU)
    assert [d.value for d in series.days] == [D("100"), D("66"), D("63"), D("72")]
    assert series.days[-1].put_in == D("56")


def test_selling_everything_leaves_nothing_and_no_dust() -> None:
    trades = [Trade(MON, "ALPHA", D("100")), Trade(TUE, "ALPHA", D("110"), sell=True)]
    series = same_money(trades, "INDEX", INDEX, THU)
    assert [d.value for d in series.days] == [D("100"), D("0"), D("0"), D("0")]


def test_a_sell_of_more_than_the_holding_was_worth_is_a_reason() -> None:
    trades = [Trade(MON, "ALPHA", D("100")), Trade(TUE, "ALPHA", D("150"), sell=True)]
    series = same_money(trades, "INDEX", INDEX, THU)
    assert series.days == []
    assert series.problems == [
        "the account took out more on 2026-01-06 than the same money in INDEX was worth that day"
    ]


def test_a_day_with_no_stored_price_is_named_never_guessed() -> None:
    gap = [day(MON, "20"), day(THU, "24")]
    trades = [Trade(MON, "ALPHA", D("100")), Trade(TUE, "ALPHA", D("110"))]
    series = same_money(trades, "INDEX", gap, THU)
    assert series.days == []
    assert series.problems == ["no price stored for INDEX on 2026-01-06"]


def test_a_weekend_deposit_has_no_price_of_its_own() -> None:
    series = same_money([Trade(SAT, "ALPHA", D("100"))], "INDEX", INDEX, THU)
    assert series.problems == ["no price stored for INDEX on 2026-01-03"]


def test_a_trade_after_the_newest_close_waits() -> None:
    later = Trade(date(2026, 1, 9), "ALPHA", D("50"))
    series = same_money([Trade(MON, "ALPHA", D("100")), later], "INDEX", INDEX, date(2026, 1, 9))
    assert series.pending == [later]
    assert series.days[-1].put_in == D("100")


def test_no_trades_no_series() -> None:
    assert same_money([], "INDEX", INDEX, THU).days == []


# --- The page ------------------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def no_real_alpaca(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"a test tried to reach {request.url.host}")

    monkeypatch.setattr(alpaca, "transport", httpx.MockTransport(refuse))


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("owner", "owner@example.com", "pw")


@pytest.fixture
def owner_client(client: Client, owner: User) -> Client:
    client.force_login(owner)
    return client


@pytest.fixture
def two_accounts(owner: User) -> tuple[Account, Account]:
    """Chapter 15's two accounts: Momentum B buys $1,000 of ALPHA through Alpaca (filled Monday)
    and $1,100 on Tuesday by hand; Index B buys $500 of ALPHA and of BETA on Monday."""
    plant_prices()
    momentum = account(owner, "Momentum B")
    index = account(owner, "Index B")
    momentum_plan = start_plan(momentum, "momentum-12-1", top_n=1)
    start_plan(index, "index-dca")
    placed = buy(momentum, date(2026, 1, 4), "ALPHA", "1000")
    PaperOrder.objects.create(
        account=momentum,
        plan=momentum_plan,
        month="2026-01",
        symbol="ALPHA",
        notional=D("1000"),
        client_order_id="iw-test-1",
        alpaca_id="order-1",
        status="filled",
        filled_qty=D("10"),
        filled_avg_price=D("100"),
        filled_at=datetime(2026, 1, 5, 15, 0, tzinfo=UTC),
        journal_entry=placed,
    )
    buy(momentum, TUE, "ALPHA", "1100")
    buy(index, MON, "ALPHA", "500")
    buy(index, MON, "BETA", "500")
    return momentum, index


def same_row(page: str, name: str) -> tuple[str, ...]:
    table = next(t for t in tables_in(page) if t and t[0][:2] == ("Account", "Method"))
    return next(row for row in table if row[0].startswith("Same money into") and name in row[0])


@pytest.mark.django_db
def test_each_account_gets_its_same_money_row_worked_out_by_hand(
    owner_client: Client, two_accounts: tuple[Account, Account]
) -> None:
    """SPY 400, 410, 405, 420. Index B put $1,000 in on Monday: 2.5 units, worth 1,050 on
    Thursday. Momentum B put $1,000 in on Monday (its Alpaca fill) and $1,100 on Tuesday: 2.5 +
    2.6829... units, worth 2,176.83 on Thursday. Both lines are SPY's from Monday: 100, 102.5,
    101.25, 105."""
    momentum, _ = two_accounts
    WatchItem.objects.create(account=momentum, symbol="SPY")
    plant("SPY", [(MON, D("400")), (TUE, D("410")), (WED, D("405")), (THU, D("420"))])
    page = text(owner_client.get(URL))
    index = same_row(page, "Index B")
    assert index[1] == "Yardstick: the same money on the same days, never touched"
    assert index[2:8] == (
        "$1,000.00",
        "$1,050.00 on 2026-01-08",
        "+$50.00",
        "+5.00% over 3 days",
        "+5.00% over 3 days",
        "-1.22%, 2026-01-06 to 2026-01-07",
    )
    assert index[8] == "Uses the adjusted close."
    momentum_row = same_row(page, "Momentum B")
    assert momentum_row[2:5] == ("$2,100.00", "$2,176.83 on 2026-01-08", "+$76.83")
    assert momentum_row[6] == "+5.00% over 3 days"
    seen = words(page)
    assert "Same money into SPY (Index B) (value with the money put in left out" in seen
    assert "Same money into SPY (Momentum B) (value with the money put in left out" in seen
    assert (
        "what doing nothing but buying the index fund with the same money would have given" in seen
    )


@pytest.mark.django_db
def test_a_missing_close_on_a_deposit_day_is_said_in_the_row(
    owner_client: Client, two_accounts: tuple[Account, Account]
) -> None:
    momentum, _ = two_accounts
    WatchItem.objects.create(account=momentum, symbol="SPY")
    plant("SPY", [(MON, D("400")), (THU, D("420"))])
    page = text(owner_client.get(URL))
    assert same_row(page, "Momentum B")[2] == (
        "Not worked out: no price stored for SPY on 2026-01-06."
    )
    assert same_row(page, "Index B")[3] == "$1,050.00 on 2026-01-08"


@pytest.mark.django_db
def test_no_yardstick_no_same_money(
    owner_client: Client, two_accounts: tuple[Account, Account]
) -> None:
    page = text(owner_client.get(URL + "?yardstick="))
    assert "Same money into" not in page


@pytest.mark.django_db
def test_lines_past_six_stay_in_the_table_and_are_named(owner: User, owner_client: Client) -> None:
    plant("ALPHA", [(MON, D("100")), (THU, D("110"))])
    plant("SPY", [(MON, D("400")), (THU, D("420"))])
    names = ["Account 1", "Account 2", "Account 3", "Account 4"]
    for name in names:
        each = account(owner, name)
        start_plan(each, "index-dca", symbols="ALPHA")
        buy(each, MON, "ALPHA", "100")
        WatchItem.objects.get_or_create(account=each, symbol="SPY")
    page = text(owner_client.get(URL))
    seen = words(page)
    assert "Same money into SPY (Account 1) (value" in seen
    assert "Same money into SPY (Account 2) (value" not in seen
    assert "the same-money lines of Account 2, Account 3, Account 4 are in the table only" in seen
    for name in names:
        assert same_row(page, name)[3] == "$105.00 on 2026-01-08"
