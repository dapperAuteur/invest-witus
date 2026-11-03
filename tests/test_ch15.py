"""Chapter 15 checkpoint: compare your methods. The math on hand-made numbers first (units from
shares or from money, a weekend buy, a trade after the newest close, a sell of more than was
bought, the line with the money put in left out, a stretch that starts after the first trade, the
worst drop, XIRR worked out by hand, a short stretch never stretched to a year, months running);
then the page: the signed-in person's own accounts only, the default pick, the table's numbers
from the journal and planted closes, a filled Alpaca order on its fill's day, an open order left
out, a reason instead of a number, the yardstick and its missing closes, how often the plan was
followed, bad dates, Alpaca's cross-check through a fake, and the links. Placeholder symbols and
planted prices; nothing leaves the machine."""

import re
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal

import httpx
import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone
from pytest_django.fixtures import Settings

from invest_witus.compare import (
    Day,
    DayPrice,
    Trade,
    cash_flows,
    line_return,
    max_drawdown,
    months_running,
    over_days,
    period,
    rebase,
    time_weighted_line,
    units,
    value_series,
    xirr,
    yearly,
)
from invest_witus_site.compare.records import SP500_FUNDS, default_yardstick, pick_accounts
from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.models import JournalEntry, MethodPlan, MonthlyReview
from invest_witus_site.paper import alpaca
from invest_witus_site.paper.models import PaperOrder
from invest_witus_site.prices.models import DailyClose
from invest_witus_site.prices.owner_views import compare_methods_url
from invest_witus_site.watchlist.models import WatchItem
from tests.test_ch10 import tables_in, text
from tests.test_ch14 import plant

D = Decimal
URL = "/compare/"

# --- Hand-made prices -----------------------------------------------------------------------------

MON, TUE, WED, THU = date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 7), date(2026, 1, 8)
FRI, SAT = date(2026, 1, 2), date(2026, 1, 3)


def same(day: date, close: str, basis: str | None = None) -> tuple[date, DayPrice]:
    return day, DayPrice(D(close), D(basis or close))


ALPHA = [same(MON, "10"), same(TUE, "11"), same(WED, "12"), same(THU, "9")]


def two_buys() -> list[Trade]:
    """$100 of ALPHA on Monday at 10 (10 units) and $110 on Tuesday at 11 (10 more)."""
    return [Trade(MON, "ALPHA", D("100")), Trade(TUE, "ALPHA", D("110"))]


# --- Units and the value --------------------------------------------------------------------------


def test_units_come_from_the_shares_when_known_and_from_the_money_when_not() -> None:
    # 10 shares on a day whose close is 50 and adjusted close 40 are 12.5 units of the adjusted
    # price: a later dividend or split moves the adjusted price, never the count twice.
    price = DayPrice(D("50"), D("40"))
    assert units(Trade(MON, "ALPHA", D("500"), shares=D("10")), price) == D("12.5")
    assert units(Trade(MON, "ALPHA", D("100")), price) == D("2.5")


def test_the_value_is_every_unit_held_at_each_days_price_and_the_money_put_in_runs_on() -> None:
    series = value_series(two_buys(), {"ALPHA": ALPHA}, THU)
    assert series.problems == [] and series.pending == []
    assert [(d.day, d.value, d.flow, d.put_in) for d in series.days] == [
        (MON, D("100"), D("100"), D("100")),
        (TUE, D("220"), D("110"), D("210")),
        (WED, D("240"), D("0"), D("210")),
        (THU, D("180"), D("0"), D("210")),
    ]


def test_a_weekend_buy_counts_from_monday_at_fridays_price() -> None:
    prices = {"ALPHA": [same(FRI, "10"), same(MON, "11")]}
    series = value_series([Trade(SAT, "ALPHA", D("100"))], prices, MON)
    # 100 / 10 = 10 units, counted on Monday and valued at Monday's 11.
    assert [(d.day, d.value, d.flow) for d in series.days] == [(MON, D("110"), D("100"))]


def test_a_trade_after_the_newest_close_waits_and_is_in_neither_the_value_nor_the_money() -> None:
    late = Trade(date(2026, 1, 9), "ALPHA", D("50"))
    series = value_series([*two_buys(), late], {"ALPHA": ALPHA}, date(2026, 1, 9))
    assert series.pending == [late]
    assert series.days[-1].put_in == D("210")


def test_a_symbol_with_no_price_or_a_sell_of_more_than_was_bought_is_a_reason_not_a_number() -> (
    None
):
    no_price = value_series(
        [Trade(MON, "ALPHA", D("100")), Trade(TUE, "GAMMA", D("50"))],
        {"ALPHA": ALPHA, "GAMMA": [same(WED, "5")]},
        THU,
    )
    assert no_price.days == []
    assert no_price.problems == [
        "no stored price for GAMMA on or before 2026-01-06, the day its buy of 2026-01-06 counts"
    ]
    oversold = value_series(
        [Trade(MON, "ALPHA", D("100")), Trade(TUE, "ALPHA", D("220"), sell=True)],
        {"ALPHA": ALPHA},
        THU,
    )
    assert oversold.days == []
    assert oversold.problems == ["the journal sells more ALPHA than it bought (by 2026-01-06)"]


def test_with_no_trades_there_is_no_series() -> None:
    assert value_series([], {"ALPHA": ALPHA}, THU).days == []


# --- The line, the stretch and the drop -----------------------------------------------------------


def test_the_line_leaves_the_money_put_in_out_so_it_moves_with_the_price_alone() -> None:
    days = value_series(two_buys(), {"ALPHA": ALPHA}, THU).days
    # Tuesday: (220 - 110) / 100 = 1.1. Wednesday: 240 / 220. Thursday: 180 / 240. The same moves
    # as ALPHA's 10, 11, 12, 9: the $110 deposit is not growth.
    assert time_weighted_line(days) == [
        (MON, D("100")),
        (TUE, D("110")),
        (WED, D("120")),
        (THU, D("90")),
    ]
    assert line_return(time_weighted_line(days)) == D("-0.1")


def test_a_day_after_nothing_was_held_keeps_the_level() -> None:
    days = [
        Day(MON, D("100"), D("100"), D("100")),
        Day(TUE, D("0"), D("-110"), D("-10")),
        Day(WED, D("50"), D("50"), D("40")),
    ]
    assert time_weighted_line(days) == [(MON, D("100")), (TUE, D("110")), (WED, D("110"))]


def test_the_worst_drop_is_from_the_high_to_the_lowest_point_after_it() -> None:
    line = [(MON, D("100")), (TUE, D("120")), (WED, D("90")), (THU, D("130"))]
    drop = max_drawdown(line)
    assert drop is not None
    assert (drop.peak_day, drop.trough_day, drop.fraction) == (TUE, WED, D("-0.25"))
    rising = max_drawdown([(MON, D("100")), (TUE, D("101"))])
    assert rising is not None and rising.fraction == 0
    assert max_drawdown([(MON, D("100"))]) is None


def test_a_stretch_from_the_start_has_nothing_carried_in() -> None:
    days = value_series(two_buys(), {"ALPHA": ALPHA}, THU).days
    stretch = period(days, date(2026, 1, 1), THU)
    assert stretch is not None
    assert (stretch.opening, stretch.put_in, stretch.gain, stretch.length) == (
        D("0"),
        D("210"),
        D("-30"),
        3,
    )
    assert cash_flows(stretch) == [(MON, D("-100")), (TUE, D("-110")), (THU, D("180"))]


def test_a_stretch_after_the_first_trade_carries_the_value_in_as_money_put_in() -> None:
    days = value_series(two_buys(), {"ALPHA": ALPHA}, THU).days
    stretch = period(days, WED, THU)
    assert stretch is not None
    # Wednesday's value less Wednesday's deposits (none): 240 carried in.
    assert (stretch.opening, stretch.put_in, stretch.gain) == (D("240"), D("240"), D("-60"))
    assert cash_flows(stretch) == [(WED, D("-240")), (THU, D("180"))]
    assert period(days, date(2026, 2, 1), date(2026, 2, 28)) is None


def test_rebase_puts_a_price_line_on_the_accounts_scale() -> None:
    assert rebase([(MON, D("400")), (THU, D("420"))]) == [(MON, D("100")), (THU, D("105"))]
    assert rebase([]) == []


# --- XIRR, and never stretching a short stretch ---------------------------------------------------


def close_to(found: Decimal | None, expected: str) -> bool:
    return found is not None and abs(found - D(expected)) < D("0.000001")


def test_xirr_finds_the_yearly_rate_worked_out_by_hand() -> None:
    # 1,000 in, 1,100 out a year later: 10% a year.
    assert close_to(xirr([(date(2025, 1, 1), D("-1000")), (date(2026, 1, 1), D("1100"))]), "0.1")
    # 1,000 in, 1,000 more a year later, 2,310 out a year after that: 1,000 x 1.1^2 + 1,000 x 1.1.
    flows = [
        (date(2024, 1, 1), D("-1000")),
        (date(2024, 12, 31), D("-1000")),
        (date(2025, 12, 31), D("2310")),
    ]
    assert close_to(xirr(flows), "0.1")


def test_xirr_has_no_answer_without_money_both_ways_or_with_every_flow_on_one_day() -> None:
    assert xirr([(MON, D("-100")), (TUE, D("-100"))]) is None
    assert xirr([(MON, D("-100")), (MON, D("110"))]) is None


def test_a_yearly_rate_becomes_the_change_over_the_days_and_back() -> None:
    assert close_to(over_days(D("0.1"), 365), "0.1")
    assert close_to(over_days(D("0.21"), 730), "0.4641")
    assert close_to(yearly(D("0.21"), 730), "0.1")
    with pytest.raises(ValueError, match="under a year"):
        yearly(D("0.05"), 90)


def test_months_running_count_the_first_month_and_this_one() -> None:
    start = date(2026, 11, 3)
    assert months_running(start, date(2026, 11, 30)) == 1
    assert months_running(start, date(2026, 12, 1)) == 2
    assert months_running(start, date(2027, 2, 1)) == 4
    assert months_running(start, date(2026, 11, 2)) == 0


# --- The page ------------------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def no_real_alpaca(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every request this file could make to Alpaca fails here instead of leaving the machine;
    the cross-check test puts its own fake in."""

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


def account(owner: User, name: str, **extra: str) -> Account:
    return Account.objects.create(
        name=name, broker="Example Broker", kind="paper", owner=owner, **extra
    )


def start_plan(
    where: Account, method_id: str, top_n: int | None = None, symbols: str = "ALPHA BETA"
) -> MethodPlan:
    return MethodPlan.objects.create(
        account=where,
        method_id=method_id,
        amount=D("1000"),
        buy_window_days=5,
        symbols=symbols,
        started_on=date(2026, 1, 1),
        top_n=top_n,
    )


def buy(
    where: Account, day: date, symbol: str, amount: str, shares: str | None = None
) -> JournalEntry:
    return JournalEntry.objects.create(
        account=where,
        date=day,
        action="buy",
        symbol=symbol,
        amount=D(amount),
        shares=D(shares) if shares else None,
    )


def plant_prices() -> None:
    plant("ALPHA", [(MON, D("100")), (TUE, D("110")), (WED, D("120")), (THU, D("90"))])
    plant("BETA", [(MON, D("50")), (TUE, D("50")), (WED, D("55")), (THU, D("55"))])


@pytest.fixture
def two_accounts(owner: User) -> Iterator[tuple[Account, Account]]:
    """MOMENTUM buys $1,000 of ALPHA on Monday through Alpaca (filled Monday, 10 shares at 100)
    and $1,100 more on Tuesday by hand (10 units at 110): worth 1,000, 2,200, 2,400 and 1,800.
    INDEX buys $500 of each on Monday: 5 ALPHA and 10 BETA, worth 1,000, 1,050, 1,150, 1,000."""
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
    yield momentum, index


def words(page: str) -> str:
    """The page's text without its tags, spaces collapsed: what a reader sees in one line."""
    return " ".join(re.sub(r"<[^>]+>", " ", page).split()).replace(" )", ")").replace("( ", "(")


def row_for(page: str, name: str) -> tuple[str, ...]:
    table = next(t for t in tables_in(page) if t and t[0][:2] == ("Account", "Method"))
    return next(row for row in table if row[0].startswith(name))


def test_the_page_needs_a_sign_in(client: Client) -> None:
    response = client.get(URL)
    assert response.status_code == 302 and "login" in response["Location"]


@pytest.mark.django_db
def test_the_default_pick_is_every_account_with_a_plan_and_the_numbers_are_worked_out_by_hand(
    owner_client: Client, two_accounts: tuple[Account, Account]
) -> None:
    page = text(owner_client.get(URL))
    momentum = row_for(page, "Momentum B")
    assert momentum[1] == "12-1 momentum, top 1 of 2" or momentum[1].endswith("top 1 of 2")
    # Put in 1,000 + 1,100; worth 20 units x 90 on Thursday; the line 100, 110, 120, 90.
    assert momentum[2:5] == ("$2,100.00", "$1,800.00 on 2026-01-08", "-$300.00")
    # -1,000 - 1,100 / (1 + r)^(1/3) + 1,800 / (1 + r) = 0, r per the three days: -17.08%, as
    # 1,100 x 0.8292^(-1/3) = 1,170.86 and 1,800 / 0.8292 = 2,170.77.
    assert momentum[5] == "-17.08% over 3 days"
    assert momentum[6] == "-10.00% over 3 days"
    assert momentum[7] == "-25.00%, 2026-01-07 to 2026-01-08"
    index = row_for(page, "Index B")
    # 5 x 90 + 10 x 55 = 1,000: no gain, no return, and a drop from 1,150 to 1,000.
    assert index[2:8] == (
        "$1,000.00",
        "$1,000.00 on 2026-01-08",
        "$0.00",
        "0.00% over 3 days",
        "0.00% over 3 days",
        "-13.04%, 2026-01-07 to 2026-01-08",
    )
    running = months_running(date(2026, 1, 1), timezone.localdate())
    assert index[8] == f"{running} (from 2026-01-01)"
    # The chart: one line per account in the key, and the page's own caption.
    # Picked by default, so in name order: Index B first.
    assert "Index B (value with the money put in left out, solid line)" in words(page)
    assert "Momentum B (value with the money put in left out, dashed line)" in words(page)
    assert "so a deposit never looks like growth" in page
    assert "How to read this." in page and "A few months prove nothing." in page


@pytest.mark.django_db
def test_a_filled_alpaca_order_counts_from_its_fill_with_alpacas_shares(
    owner_client: Client, two_accounts: tuple[Account, Account]
) -> None:
    # The entry is dated Sunday (the day of the click); the order filled Monday. Nothing counted
    # before Monday, so the first day's value is Monday's 10 shares x 100.
    page = text(owner_client.get(URL))
    daily = next(t for t in tables_in(page) if t and t[0][0] == "Date")
    monday = next(row for row in daily if row[0] == "2026-01-05")
    assert monday[1:3] == ("100.00", "$1,000.00")


@pytest.mark.django_db
def test_an_open_order_is_left_out_and_said(
    owner_client: Client, owner: User, two_accounts: tuple[Account, Account]
) -> None:
    momentum, _ = two_accounts
    waiting = buy(momentum, WED, "BETA", "500")
    PaperOrder.objects.create(
        account=momentum,
        plan=MethodPlan.active_for(momentum),
        month="2026-01",
        symbol="BETA",
        notional=D("500"),
        client_order_id="iw-test-2",
        alpaca_id="order-2",
        status="accepted",
        journal_entry=waiting,
    )
    page = text(owner_client.get(URL))
    assert row_for(page, "Momentum B")[2] == "$2,100.00"
    assert "Momentum B: 1 order still open at Alpaca: left out until filled." in page


@pytest.mark.django_db
def test_an_account_without_trades_says_why_instead_of_a_number(
    owner_client: Client, owner: User, two_accounts: tuple[Account, Account]
) -> None:
    empty = account(owner, "Another try")
    start_plan(empty, "index-dca")
    momentum, index = two_accounts
    query = f"?accounts={momentum.pk}&accounts={empty.pk}"
    page = text(owner_client.get(URL + query))
    assert (
        row_for(page, "Another try")[2]
        == "No trades in the journal yet, so there is nothing to value."
    )
    assert index.name not in [row[0] for row in tables_in(page)[0]]


@pytest.mark.django_db
def test_another_persons_account_is_left_out_and_never_named(
    owner_client: Client,
    django_user_model: type[User],
    two_accounts: tuple[Account, Account],
) -> None:
    stranger = django_user_model.objects.create_user("stranger", "s@example.com", "pw")
    theirs = account(stranger, "Their secret account")
    start_plan(theirs, "index-dca")
    momentum, index = two_accounts
    response = owner_client.get(URL + f"?accounts={momentum.pk},{theirs.pk},{index.pk}")
    page = text(response)
    assert response.status_code == 200
    assert "Their secret account" not in page
    assert "Left out 1 account that is not yours." in page
    # Their account is not offered in the picker either, and the default never includes it.
    assert "Their secret account" not in text(owner_client.get(URL))


@pytest.mark.django_db
def test_at_most_four_accounts_and_at_least_two_are_asked_for(owner: User) -> None:
    owned = [account(owner, f"A{n}") for n in range(6)]
    picked = pick_accounts([",".join(str(a.pk) for a in owned)], owned, [])
    assert [a.name for a in picked.accounts] == ["A0", "A1", "A2", "A3"]
    assert [a.name for a in picked.over_limit] == ["A4", "A5"]
    default = pick_accounts([], owned, owned)
    assert default.defaulted and len(default.accounts) == 4
    assert pick_accounts(["x"], owned, owned).not_yours == 1


@pytest.mark.django_db
def test_one_account_picked_is_shown_with_a_note(
    owner_client: Client, two_accounts: tuple[Account, Account]
) -> None:
    momentum, _ = two_accounts
    page = text(owner_client.get(URL + f"?accounts={momentum.pk}"))
    assert "Pick at least 2 accounts to compare" in page
    assert row_for(page, "Momentum B")[2] == "$2,100.00"


# --- The yardstick --------------------------------------------------------------------------------


def test_the_default_yardstick_is_the_first_sp500_fund_among_the_persons_symbols() -> None:
    assert default_yardstick(["ALPHA", "IVV", "VOO"]) == "VOO"
    assert default_yardstick(["ALPHA"]) == ""
    assert SP500_FUNDS[0] == "SPY"


@pytest.mark.django_db
def test_a_watched_index_fund_is_the_yardstick_line_rebased_to_100(
    owner_client: Client, two_accounts: tuple[Account, Account]
) -> None:
    momentum, _ = two_accounts
    WatchItem.objects.create(account=momentum, symbol="SPY")
    plant("SPY", [(MON, D("400")), (THU, D("420"))])
    page = text(owner_client.get(URL))
    spy = row_for(page, "SPY")
    assert spy[1] == "Yardstick: bought once, never touched"
    assert "+5.00% over 3 days" in spy
    assert "SPY (adjusted close, dotted line)" in words(page)


@pytest.mark.django_db
def test_a_yardstick_with_no_closes_says_so_and_offers_get_history(
    owner_client: Client, two_accounts: tuple[Account, Account]
) -> None:
    momentum, _ = two_accounts
    WatchItem.objects.create(account=momentum, symbol="VOO")
    page = text(owner_client.get(URL))
    assert "No closes stored for VOO from 2026-01-01" in page
    assert f'action="/accounts/{momentum.pk}/watch/VOO/fetch-history/"' in page
    assert 'name="return_to" value="compare-methods"' in page


@pytest.mark.django_db
def test_with_no_index_fund_the_page_says_how_to_add_one(
    owner_client: Client, two_accounts: tuple[Account, Account]
) -> None:
    page = text(owner_client.get(URL))
    assert "No yardstick: none of SPY, VOO" in page
    assert not DailyClose.objects.filter(symbol__in=SP500_FUNDS).exists()


def test_get_history_returns_to_the_compare_page_with_only_its_own_parameters() -> None:
    url = compare_methods_url("accounts=1&accounts=2&from=2026-01-01&next=https://evil.example")
    assert url == "/compare/?accounts=1&accounts=2&from=2026-01-01"
    assert compare_methods_url("") == "/compare/"


# --- Followed, dates, links -----------------------------------------------------------------------


@pytest.mark.django_db
def test_how_often_the_plan_was_followed_comes_from_closed_month_reviews(
    owner_client: Client, owner: User, two_accounts: tuple[Account, Account]
) -> None:
    # One symbol: chapter 03's index rules expect one buy of the plan's amount a month.
    single = account(owner, "Single fund")
    plan = start_plan(single, "index-dca", symbols="ALPHA")
    buy(single, MON, "ALPHA", "1000")
    assert row_for(text(owner_client.get(URL)), "Single fund")[9] == "no month closed yet"
    MonthlyReview.objects.create(
        plan=plan,
        month="2026-01",
        opened_on=date(2026, 1, 5),
        did="Bought both.",
        rules_said="Buy both.",
        next_month="Same.",
        closed_at=datetime(2026, 2, 1, tzinfo=UTC),
    )
    assert row_for(text(owner_client.get(URL)), "Single fund")[9] == (
        "followed in 1 of 1 closed months"
    )


@pytest.mark.django_db
def test_bad_dates_are_refused_in_words_and_the_defaults_are_shown(
    owner_client: Client, two_accounts: tuple[Account, Account]
) -> None:
    response = owner_client.get(URL + "?from=2026-01-08&to=2026-01-05")
    assert response.status_code == 400
    assert "From (2026-01-08) must be on or before To (2026-01-05)." in text(response)
    future = owner_client.get(URL + "?to=2999-01-01")
    assert future.status_code == 400 and "is after today" in text(future)
    assert owner_client.get(URL + "?from=yesterday").status_code == 400


@pytest.mark.django_db
def test_a_later_from_date_carries_the_value_in(
    owner_client: Client, two_accounts: tuple[Account, Account]
) -> None:
    page = text(owner_client.get(URL + "?from=2026-01-07&to=2026-01-08"))
    # Wednesday's 2,400 carried in, worth 1,800 on Thursday.
    momentum = row_for(page, "Momentum B")
    assert momentum[2:5] == (
        "$2,400.00 (incl. $2,400.00 held at the start)",
        "$1,800.00 on 2026-01-08",
        "-$600.00",
    )


@pytest.mark.django_db
def test_the_header_the_account_list_and_the_account_page_link_the_page(
    owner_client: Client, two_accounts: tuple[Account, Account]
) -> None:
    momentum, _ = two_accounts
    for path in ("/accounts/", f"/accounts/{momentum.pk}/", URL):
        assert 'href="/compare/"' in owner_client.get(path).content.decode()
    assert 'href="/compare/"' not in Client().get("/").content.decode()


@pytest.mark.django_db
def test_the_chart_has_a_text_title_and_a_table_of_every_day(
    owner_client: Client, two_accounts: tuple[Account, Account]
) -> None:
    page = owner_client.get(URL).content.decode()
    assert 'role="img"' in page and '<title id="chart-title">' in page
    assert "8 day values from 2026-01-05 to 2026-01-08" in page
    assert "Every day&#x27;s values" in page or "Every day's values" in page
    assert '"text": ["100.00 (start = 100), value $1,000.00' in page


# --- Alpaca's cross-check, through a fake ---------------------------------------------------------


@pytest.mark.django_db
def test_alpacas_equity_is_read_for_a_linked_account_of_the_site_owner(
    client: Client,
    django_user_model: type[User],
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    boss = django_user_model.objects.create_superuser("boss", "boss@example.com", "pw")
    plant_prices()
    linked = account(
        boss, "Linked", alpaca="paper", alpaca_slot="B_INDEX", alpaca_account_number="PA1"
    )
    other = account(boss, "Not linked")
    for each in (linked, other):
        start_plan(each, "index-dca")
        buy(each, MON, "ALPHA", "1000")
    settings.ALPACA_PAPER_KEY_SLOTS = {"B_INDEX": ("KEY-B-INDEX", "SECRET-B-INDEX")}
    seen: list[str] = []

    def fake(request: httpx.Request) -> httpx.Response:
        seen.append(f"{request.method} {request.url.path} {request.headers['APCA-API-KEY-ID']}")
        body = {"cash": "998200", "buying_power": "1", "equity": "999100", "status": "ACTIVE"}
        return httpx.Response(200, json=body)

    monkeypatch.setattr(alpaca, "transport", httpx.MockTransport(fake))
    client.force_login(boss)
    page = text(client.get(URL))
    assert seen == ["GET /v2/account KEY-B-INDEX"]
    check = next(
        t for t in tables_in(page) if t and t[0][1:3] == ("Value here", "Alpaca: holdings now")
    )
    assert check[1:] == [
        ("Linked 🧪 Practice", "$900.00 on 2026-01-08", "$900.00", "$999,100.00", "$998,200.00")
    ]
    assert "SECRET-B-INDEX" not in page and "KEY-B-INDEX" not in page


@pytest.mark.django_db
def test_alpaca_not_answering_is_a_sentence_and_the_page_still_draws(
    client: Client,
    django_user_model: type[User],
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    boss = django_user_model.objects.create_superuser("boss", "boss@example.com", "pw")
    plant_prices()
    linked = account(
        boss, "Linked", alpaca="paper", alpaca_slot="B_INDEX", alpaca_account_number="PA1"
    )
    start_plan(linked, "index-dca")
    settings.ALPACA_PAPER_KEY_SLOTS = {"B_INDEX": ("KEY-B-INDEX", "SECRET-B-INDEX")}

    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    monkeypatch.setattr(alpaca, "transport", httpx.MockTransport(slow))
    client.force_login(boss)
    response = client.get(URL)
    assert response.status_code == 200
    assert "Alpaca did not answer in time (ReadTimeout)." in text(response)
