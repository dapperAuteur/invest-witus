# Chapter 15: Compare your methods

**Starts from:** tag `v14a`, plus the reference's work between chapters (step 15.0). **Ends at:** tag `v15`.
**Written against:** Python 3.14.10, uv 0.13.6 and Django 5.2.18.
**Goal:** since decisions 159 and 160 each method can run in its own account, each linked to its own Alpaca paper
account. This chapter puts them side by side. **Compare methods** (`/compare/`) draws two to four of your accounts
on one chart, each line the account's value with the money you put in left out, rebased to 100, beside a
do-nothing line for an S&P 500 index fund from the app's own closes. A table under it says what each account put
in, what it holds now, its gain, its money-weighted and time-weighted returns, its worst drop, how many months the
plan has run and how often it was followed. Every number is rebuilt from the journal and the stored closes; where
one cannot be, the row says why.
**Time:** 3 to 4 hours for the code and tests. The laptop walk-through takes 10 minutes.

## What you will learn

- **Rebuilding a series from events:** a value for every day from a list of trades and a table of prices, with
  each trade counted from the first price day on or after it.
- **Two returns, two questions:** the time-weighted return leaves deposits out and judges the method; the
  money-weighted return (XIRR) counts when the money went in and judges the method and the timing together.
- **Finding a root by halving an interval,** in `Decimal`, with a clear "no answer" instead of a guess.
- **The worst drop** of a line, and why it is measured on the time-weighted line, not on a value that deposits keep
  lifting.
- **Refusing to stretch a short result:** three days are never turned into a yearly rate.
- **A fair test:** same cash, same monthly amount, same list of symbols; only the method differs.
- **A cross-check with a timeout,** read in threads so the page waits for the slowest answer, not the sum.

## Before the code: the arithmetic, and five decisions

**The value.** A buy of money `A` on a day whose price is `P` adds `A / P` units; with the shares `S` known
(Alpaca reports them), it adds `S x close / basis`, where the basis is the adjusted close. A day's value is every
unit held times that day's basis price, carried forward from the symbol's last stored day. The money put in is the
buys less the sells.

**The line.** Write `V(d)` for the value on day `d` and `F(d)` for the money put in that day. The level starts at
100 on the first day with a holding and moves as

```text
L(d) = L(d-1) x (V(d) - F(d)) / V(d-1)
```

so a deposit lifts `V` and `F` together and leaves `L` alone. `L(last) / 100 - 1` is the **time-weighted return**.

**XIRR.** The **money-weighted return** is the rate `r` that makes every flow, moved back to the first day, sum to
zero: each deposit negative, the last value positive,

```text
sum of  flow(i) / (1 + r) ^ (days(i) / unit)  = 0
```

where `unit` is 365 for a yearly rate. There is no formula for `r`; the code halves the interval from -99.9999% to
+100,000% until it is narrower than one ten-billionth.

**Decision 1: a chapter of its own, before the CentenarianOS events.** The page brings ideas a learner can use
anywhere (a value series, two returns, a root finder, a drawdown), so it is chapter 15 with its own checkpoint, and
the proposed CentenarianOS chapter becomes 16. No tag moved. Row 167.

**Decision 2: the yardstick is a symbol of your own.** The app names no real fund anywhere, so the page offers
every symbol you hold, watch or name in a plan, and starts on the first S&P 500 index fund it finds among them
(`SP500_FUNDS`). With no closes for it, the page says so and offers chapter 13's **Get history**, which returns to
the same comparison. Row 168.

**Decision 3: the journal and the closes, no cash ledger.** The app never kept the cash an account holds beside
its holdings, so the value is what the trades bought, and the page says so. A buy placed through Alpaca counts from
its fill's day with Alpaca's shares; an order still open is left out and counted. Alpaca's own equity is shown
beside it as a cross-check. Row 169.

**Decision 4: never stretch a short stretch to a year.** A loss of 14% over three days is a yearly rate of about
-99.99999998%: too close to -100% to find reliably and too large to mean anything. Under a year, XIRR is solved per
the stretch's own length and both returns read "over N days". Row 170.

**Decision 5: say why, never invent.** No trades, a symbol with no price by its trade day, or a sell of more than
was bought: the row prints the reason across its number columns. Row 171.

## Steps

### 15.0 Take the work between chapters

Between `v14a` and this chapter the reference took twelve pieces of work that are not chapters (decisions 155 to
166): a default view saved per person and a Settings page, a plan edited or deleted before anything happens under
it, cancelling a paper order, Alpaca key slots (one Alpaca paper account per Invest account) and their near-miss
names, the plan's amount read as the month's total, striped tables, and the Help bubble keeping its draft. Take them
from the commit this chapter starts from, then migrate:

Listing 15-1, Terminal:

```sh
git fetch reference --tags
git checkout c459ce7 -- src tests .env.example
uv run --env-file .env python manage.py migrate
uv run pytest -q
```

```text
Operations to perform:
  Apply all migrations: accounts, admin, auth, contenttypes, holdings, methods, outbox, pages, paper, prices, reports, sessions, watchlist
Running migrations:
  Applying holdings.0003_account_alpaca_slot_and_number... OK
  Applying methods.0005_view_preference... OK
933 passed
```

Commit that as its own step (`git commit -am "Take the reference's work between chapters 14a and 15"`).

### 15.1 The tests

Start red. The first half of the file checks the math on numbers small enough to work out by hand; the second half
plants closes and journal lines for two accounts and reads the page.

Listing 15-2, Filename: `tests/test_ch15.py`:

```python
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
        ("Linked", "$900.00 on 2026-01-08", "$900.00", "$999,100.00", "$998,200.00")
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
```

Run them: every test fails on the first import, `invest_witus.compare`.

### 15.2 The math, with no Django

One module, plain values in and out. `value_series` walks the price days once, applying each day's trades and
pricing what is held; `period` cuts a stretch and works out what was carried into it; `time_weighted_line`,
`xirr` and `max_drawdown` are the three numbers. Read `xirr` closely: the two early `return None` lines are the
cases with no answer, and the loop stops on a tolerance or after 200 halvings, so it always ends.

Listing 15-3, Filename: `src/invest_witus/compare.py`:

```python
"""Comparing methods (chapter 15): an account's value day by day, rebuilt from its trades and the
stored prices, and the numbers that say how a method did. No Django, no files: plain values in,
plain values out, every amount a `Decimal`.

**The value.** Each buy adds *units* of its symbol and each sell takes them away. With the shares
known, a unit count is the shares times the day's close over the day's basis price; without them,
the money over the basis price, as if the order filled at that day's close. The basis is the
adjusted close when the caller has one for every day (dividends and splits counted, as if each
dividend bought more of the fund), else the close. A day's value is every unit held times its
symbol's latest basis price on or before that day. The days are the days with a stored price.

**Money put in** is what the buys cost less what the sells brought back. Cash the account keeps
beside its holdings is not counted: the app has no cash ledger, so the value here is the value of
what the trades bought.

**The line** leaves the money put in out, so a deposit never looks like growth: each day's level
is the day before's times `(value - money put in that day) / value the day before`, starting at
100. This is the *time-weighted* return; the **money-weighted** return is the one yearly rate
that makes every deposit, grown to the last day, equal the value then (XIRR). The time-weighted
return judges the method; the money-weighted one judges the method and the timing of the money
together.

**The worst drop** is the largest fall of the line from a high to a later low, as a fraction of
the high.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

ZERO = Decimal(0)
ONE = Decimal(1)
HUNDRED = Decimal(100)
DAYS_A_YEAR = 365
# XIRR is found by halving an interval: from a loss of almost everything to a gain of this many
# times a year. A rate the interval cannot hold is "no rate", never a guess.
LOWEST_RATE = Decimal("-0.999999")
HIGHEST_RATE = Decimal(1000)
RATE_TOLERANCE = Decimal("1e-10")
MAX_HALVINGS = 200


@dataclass(frozen=True, slots=True)
class Trade:
    """One buy or sell: the day the money changed hands, the symbol, the money (always positive),
    and the shares when the fill or the confirmation said."""

    day: date
    symbol: str
    amount: Decimal
    shares: Decimal | None = None
    sell: bool = False

    @property
    def flow(self) -> Decimal:
        """Money put in: positive for a buy, negative for a sell."""
        return -self.amount if self.sell else self.amount


@dataclass(frozen=True, slots=True)
class DayPrice:
    """One stored day of one symbol: the close, and the price the value uses (the adjusted close,
    or the close again when the caller has no adjusted close for every day)."""

    close: Decimal
    basis: Decimal


Prices = Mapping[str, Sequence[tuple[date, DayPrice]]]


def units(trade: Trade, price: DayPrice) -> Decimal:
    """How many units of the basis price the trade moved. With shares: the shares times the
    close over the basis, so a split or a dividend after the trade is counted through the basis
    and never twice. Without shares: the money over the basis price."""
    if trade.shares is not None:
        return trade.shares * price.close / price.basis
    return trade.amount / price.basis


def price_on_or_before(rows: Sequence[tuple[date, DayPrice]], day: date) -> DayPrice | None:
    """The newest stored price on or before `day` (the rows are oldest first), or None."""
    found: DayPrice | None = None
    for stored, price in rows:
        if stored > day:
            break
        found = price
    return found


@dataclass(frozen=True, slots=True)
class Day:
    """One day of an account: its value at the day's prices, the money put in that day, and the
    money put in so far."""

    day: date
    value: Decimal
    flow: Decimal
    put_in: Decimal


@dataclass(frozen=True, slots=True)
class Series:
    """An account day by day, and what could not be counted: trades dated after the newest stored
    price (`pending`), and `problems`, reasons the value cannot be trusted at all."""

    days: list[Day] = field(default_factory=list[Day])
    pending: list[Trade] = field(default_factory=list[Trade])
    problems: list[str] = field(default_factory=list[str])


def value_series(trades: Sequence[Trade], prices: Prices, until: date) -> Series:
    """The account's value on every stored price day from its first trade through `until`.

    A trade counts from the first stored day on or after it (a buy confirmed on a Saturday counts
    from Monday). Its units are worked out at its symbol's price on its own day, or the newest
    one before. A trade after the newest stored day is `pending`, left out of both the value and
    the money put in, so the two always describe the same trades. A symbol with no stored price
    on or before its trade's day, or a sell of more units than were bought, is a problem: the
    series is empty and the reason is kept."""
    ordered = sorted(trades, key=lambda trade: trade.day)
    if not ordered:
        return Series()
    first = ordered[0].day
    calendar = sorted(
        {day for symbol in {t.symbol for t in ordered} for day, _ in prices.get(symbol, ())}
    )
    calendar = [day for day in calendar if first <= day <= until]
    pending = [trade for trade in ordered if not calendar or trade.day > calendar[-1]]
    counted = [trade for trade in ordered if trade not in pending]
    problems: list[str] = []
    moves: dict[date, list[tuple[str, Decimal, Decimal]]] = {}
    for trade in counted:
        applies = next(day for day in calendar if day >= trade.day)
        rows = prices.get(trade.symbol, ())
        price = price_on_or_before(rows, trade.day) or price_on_or_before(rows, applies)
        if price is None:
            problems.append(
                f"no stored price for {trade.symbol} on or before {applies:%Y-%m-%d}, "
                f"the day its {'sell' if trade.sell else 'buy'} of {trade.day:%Y-%m-%d} counts"
            )
            continue
        moved = units(trade, price)
        moves.setdefault(applies, []).append(
            (trade.symbol, -moved if trade.sell else moved, trade.flow)
        )
    if problems:
        return Series(pending=pending, problems=problems)
    held: dict[str, Decimal] = {}
    days: list[Day] = []
    put_in = ZERO
    for day in calendar:
        flow = ZERO
        for symbol, change, money in moves.get(day, []):
            held[symbol] = held.get(symbol, ZERO) + change
            flow += money
        short = [symbol for symbol, count in held.items() if count < 0]
        if short:
            problems.append(
                f"the journal sells more {', '.join(sorted(short))} than it bought "
                f"(by {day:%Y-%m-%d})"
            )
            return Series(pending=pending, problems=problems)
        put_in += flow
        value = ZERO
        for symbol, count in held.items():
            price = price_on_or_before(prices[symbol], day)
            if price is not None and count:
                value += count * price.basis
        days.append(Day(day, value, flow, put_in))
    return Series(days=days, pending=pending)


# --- A stretch of days ----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Period:
    """The days of a series inside a range, and the value carried into it: zero when the range
    starts before the first trade, else the first day's value less that day's money put in."""

    days: list[Day]
    opening: Decimal

    @property
    def first(self) -> Day:
        return self.days[0]

    @property
    def last(self) -> Day:
        return self.days[-1]

    @property
    def put_in(self) -> Decimal:
        """The money put in during the range, the value carried in counted as put in on day one."""
        return self.opening + sum((day.flow for day in self.days), ZERO)

    @property
    def gain(self) -> Decimal:
        return self.last.value - self.put_in

    @property
    def length(self) -> int:
        """Calendar days from the first day to the last."""
        return (self.last.day - self.first.day).days


def period(days: Sequence[Day], start: date, end: date) -> Period | None:
    """The days from `start` through `end`, or None when none falls inside."""
    inside = [day for day in days if start <= day.day <= end]
    if not inside:
        return None
    before = [day for day in days if day.day < start]
    carried = before[-1].value if before else ZERO
    opening = inside[0].value - inside[0].flow if carried > 0 else ZERO
    return Period(inside, opening)


def time_weighted_line(days: Sequence[Day]) -> list[tuple[date, Decimal]]:
    """The account's line with the money put in left out, 100 on its first day with a value. A
    day after a day with nothing held keeps the level: no money was at work."""
    points: list[tuple[date, Decimal]] = []
    level = HUNDRED
    previous: Day | None = None
    for day in days:
        if previous is not None and previous.value > 0:
            level = level * (day.value - day.flow) / previous.value
        if points or day.value > 0:
            points.append((day.day, level))
        previous = day
    return points


def rebase(points: Sequence[tuple[date, Decimal]]) -> list[tuple[date, Decimal]]:
    """Each value times 100 over the first: a price line on the same scale as an account's."""
    if not points or points[0][1] == 0:
        return []
    base = points[0][1]
    return [(day, value * HUNDRED / base) for day, value in points]


def line_return(points: Sequence[tuple[date, Decimal]]) -> Decimal | None:
    """The change from a line's first point to its last, as a fraction: 0.05 is five percent."""
    if len(points) < 2 or points[0][1] == 0:
        return None
    return points[-1][1] / points[0][1] - ONE


@dataclass(frozen=True, slots=True)
class Drawdown:
    """The worst fall of a line: from `peak` on `peak_day` to `trough` on `trough_day`."""

    peak_day: date
    peak: Decimal
    trough_day: date
    trough: Decimal

    @property
    def fraction(self) -> Decimal:
        """Zero or negative: -0.2 is a fall of twenty percent from the high."""
        return self.trough / self.peak - ONE


def max_drawdown(points: Sequence[tuple[date, Decimal]]) -> Drawdown | None:
    """The largest fall from a high to a later low, or None for a line of under two points. A line
    that never fell below its high has a drawdown of zero, on its first day."""
    if len(points) < 2:
        return None
    peak_day, peak = points[0]
    worst = Drawdown(peak_day, peak, peak_day, peak)
    for day, value in points[1:]:
        if value > peak:
            peak_day, peak = day, value
        elif peak > 0 and value / peak - ONE < worst.fraction:
            worst = Drawdown(peak_day, peak, day, value)
    return worst


# --- The money-weighted return --------------------------------------------------------------------


def cash_flows(stretch: Period) -> list[tuple[date, Decimal]]:
    """The investor's side of the account: every deposit negative (money leaving the pocket), the
    value carried in as a deposit on the first day, and the last day's value positive, as if it
    were taken out then."""
    flows: list[tuple[date, Decimal]] = []
    if stretch.opening > 0:
        flows.append((stretch.first.day, -stretch.opening))
    flows += [(day.day, -day.flow) for day in stretch.days if day.flow]
    flows.append((stretch.last.day, stretch.last.value))
    return flows


def present_value(
    rate: Decimal, flows: Sequence[tuple[date, Decimal]], days_per_unit: int = DAYS_A_YEAR
) -> Decimal:
    """Every flow moved back to the first flow's day at `rate` per `days_per_unit` days."""
    first = flows[0][0]
    log = (ONE + rate).ln()
    total = ZERO
    for day, amount in flows:
        units_of_time = Decimal((day - first).days) / days_per_unit
        total += amount * (-units_of_time * log).exp()
    return total


def xirr(flows: Sequence[tuple[date, Decimal]], days_per_unit: int = DAYS_A_YEAR) -> Decimal | None:
    """The rate per `days_per_unit` days (a year unless told otherwise) at which the flows'
    present value is zero, found by halving an interval, or None: no money in or no money out,
    every flow on one day, or no single rate in the interval that fits (possible when deposits
    and withdrawals alternate). A short stretch is solved per its own length, not per year: a
    loss of 14% in three days is a yearly rate of -99.99999998%, too close to -100% to find or to
    mean anything, while "-14% over 3 days" is both."""
    if not any(amount < 0 for _, amount in flows) or not any(amount > 0 for _, amount in flows):
        return None
    ordered = sorted(flows, key=lambda flow: flow[0])
    if ordered[0][0] == ordered[-1][0]:
        return None
    low, high = LOWEST_RATE, HIGHEST_RATE
    try:
        at_low = present_value(low, ordered, days_per_unit)
        at_high = present_value(high, ordered, days_per_unit)
    except InvalidOperation:
        return None
    if at_low == 0:
        return low
    if (at_low > 0) == (at_high > 0):
        return None
    for _ in range(MAX_HALVINGS):
        middle = (low + high) / 2
        at_middle = present_value(middle, ordered, days_per_unit)
        if at_middle == 0 or high - low < RATE_TOLERANCE:
            return middle
        if (at_middle > 0) == (at_low > 0):
            low, at_low = middle, at_middle
        else:
            high = middle
    return (low + high) / 2


def over_days(yearly: Decimal, days: int) -> Decimal:
    """A yearly rate as the change over `days` calendar days: 10% a year over 73 days is about
    1.92%."""
    return ((ONE + yearly).ln() * days / DAYS_A_YEAR).exp() - ONE


def yearly(total: Decimal, days: int) -> Decimal:
    """A change over `days` calendar days as a yearly rate. Only for a year or more: a short
    stretch stretched to a year multiplies its noise."""
    if days < DAYS_A_YEAR:
        raise ValueError(f"{days} days is under a year; show the change over the days instead")
    return ((ONE + total).ln() * DAYS_A_YEAR / days).exp() - ONE


def months_running(start: date, end: date) -> int:
    """Calendar months from `start`'s month to `end`'s, both counted: a plan started on
    2026-11-03 has run 1 month on 2026-11-30 and 2 on 2026-12-01. Zero before it starts."""
    if end < start:
        return 0
    return (end.year - start.year) * 12 + end.month - start.month + 1
```

Try it before any page exists. The numbers are the tests' two buys of a placeholder fund, `INDEX`:

Listing 15-4, Terminal:

```sh
uv run python - <<'EOF'
from datetime import date
from decimal import Decimal as D

from invest_witus.compare import (
    DayPrice, Trade, cash_flows, line_return, max_drawdown, period,
    time_weighted_line, value_series, xirr,
)

days = [date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 7), date(2026, 1, 8)]
index = {"INDEX": [(d, DayPrice(D(p), D(p))) for d, p in zip(days, ["10", "11", "12", "9"])]}
trades = [Trade(days[0], "INDEX", D("100")), Trade(days[1], "INDEX", D("110"))]

series = value_series(trades, index, days[-1])
for day in series.days:
    print(day.day, day.value, day.flow, day.put_in)
line = time_weighted_line(series.days)
print([f"{level:.2f}" for _, level in line])
stretch = period(series.days, date(2026, 1, 1), days[-1])
assert stretch is not None
print("put in", stretch.put_in, "gain", stretch.gain)
print("time-weighted", f"{line_return(line):.4f}")
rate = xirr(cash_flows(stretch), days_per_unit=stretch.length)
print("money-weighted over", stretch.length, "days", f"{rate:.4f}")
drop = max_drawdown(line)
assert drop is not None
print("worst drop", f"{drop.fraction:.4f}", drop.peak_day, drop.trough_day)
EOF
```

```text
2026-01-05 100 100 100
2026-01-06 220 110 210
2026-01-07 240 0 210
2026-01-08 180 0 210
['100.00', '110.00', '120.00', '90.00']
put in 210 gain -30
time-weighted -0.1000
money-weighted over 3 days -0.1708
worst drop -0.2500 2026-01-07 2026-01-08
```

The line moves exactly with the price (10, 11, 12, 9): the $110 deposit on Tuesday did not lift it. The
time-weighted return is the price's -10%; the money-weighted return is worse, -17.08% over the three days, because
more money was in when the price fell.

### 15.3 From the app's records to the library's values

`records.py` reads the journal, the paper orders and the closes, and turns the library's numbers into the words
the table prints. Notice what it leaves out and says: an open order, a symbol on closes only, a trade after the
newest close. `followed` reuses chapter 12's review engine, so "followed" here means what "months followed" means
on the method page.

Listing 15-5, Filename: `src/invest_witus_site/compare/records.py`:

```python
"""Compare methods on the web (chapter 15): the app's own records turned into the library's plain
values, and the library's numbers turned into what the page prints.

The math is `invest_witus.compare`. This module reads, for each account picked:

- **the trades** from the journal (chapter 10's rows): a buy placed through Alpaca paper counts
  from the day its order filled (`PaperOrder.filled_at`, chapter 11) with the shares Alpaca
  reported; an order still open is left out until it fills; a trade logged by hand counts on its
  own date with its shares if the owner wrote them;
- **the prices** from the stored closes (chapter 08): the adjusted close for a symbol whose every
  stored day in the stretch has one, else the close, and the page says which;
- **the plan** (chapter 10, its versions from chapter 12): its method, its first start, and its
  closed month reviews, which say how often the plan was followed.

Nothing is fetched. The one live read is Alpaca's own equity for a linked account (`alpaca_checks`),
a cross-check with a short timeout that a page asks for and a test replaces.
"""

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.db.models import Exists, OuterRef
from django.utils import timezone

from invest_witus.compare import DAYS_A_YEAR as YEAR_DAYS
from invest_witus.compare import (
    HUNDRED,
    DayPrice,
    Drawdown,
    Period,
    Series,
    Trade,
    cash_flows,
    line_return,
    max_drawdown,
    months_running,
    period,
    time_weighted_line,
    value_series,
    xirr,
    yearly,
)
from invest_witus_site.holdings.models import Account
from invest_witus_site.holdings.templatetags.holdings_extras import money, percent, signed_money
from invest_witus_site.methods.engine import build_review
from invest_witus_site.methods.models import TRADE, JournalEntry, MethodPlan, MonthlyReview
from invest_witus_site.paper.alpaca import AlpacaError, client_for
from invest_witus_site.paper.models import PaperOrder
from invest_witus_site.paper.orders import alpaca_allowed
from invest_witus_site.prices import manual
from invest_witus_site.prices.models import DailyClose

# Two to four accounts on one chart, plus the yardstick: five lines, within the chart's six styles.
MIN_ACCOUNTS = 2
MAX_ACCOUNTS = 4
# S&P 500 index funds by their tickers, from the author's knowledge, not read from a vendor in
# this session: the first one found among the owner's own symbols is the default yardstick. The
# owner can pick any symbol of theirs instead, and the page prints the stored profile's name so
# the owner can check what the fund is (decision 168).
SP500_FUNDS = ("SPY", "VOO", "IVV", "SPLG", "FXAIX", "VFIAX", "SWPPX")
# A trade on a weekend or a holiday reads the newest close before it; two weeks covers any gap.
PRICE_LOOKBACK_DAYS = 14
# Alpaca's equity is a cross-check, not the page: a short wait, then "did not answer".
ALPACA_TIMEOUT_SECONDS = 5.0


# --- Which accounts -------------------------------------------------------------------------------


def plan_of(account: Account) -> MethodPlan | None:
    """The account's plan: the active one, else the newest version of the most recent ended one."""
    active = MethodPlan.active_for(account)
    if active is not None:
        return active
    newest = MethodPlan.objects.filter(account=account).order_by("-started_on", "-pk").first()
    return newest.latest_version() if newest is not None else None


def accounts_with_plans(user: AbstractBaseUser | AnonymousUser) -> list[Account]:
    """The person's accounts that run or ran a plan, by name: the page's default pick."""
    has_plan = Exists(MethodPlan.objects.filter(account=OuterRef("pk")))
    return list(Account.objects.filter(has_plan, owner_id=user.pk).order_by("name"))


@dataclass
class Picked:
    """The accounts asked for, sorted out: the ones compared (in the order asked, at most
    `MAX_ACCOUNTS`), how many ids were not the person's, and the ones over the limit."""

    accounts: list[Account] = field(default_factory=list[Account])
    not_yours: int = 0
    over_limit: list[Account] = field(default_factory=list[Account])
    defaulted: bool = False


def pick_accounts(asked: list[str], owned: list[Account], with_plans: list[Account]) -> Picked:
    """`?accounts=1&accounts=2` (or `1,2`): each of the person's own accounts once, in the order
    asked. Nothing asked: every account with a plan, the first four by name. An id that is not
    one of the person's accounts is counted and left out, never named."""
    by_pk = {account.pk: account for account in owned}
    picked = Picked()
    seen: set[int] = set()
    for value in asked:
        for token in value.split(","):
            try:
                pk = int(token.strip())
            except ValueError:
                picked.not_yours += 1 if token.strip() else 0
                continue
            if pk in seen:
                continue
            seen.add(pk)
            account = by_pk.get(pk)
            if account is None:
                picked.not_yours += 1
            elif len(picked.accounts) >= MAX_ACCOUNTS:
                picked.over_limit.append(account)
            else:
                picked.accounts.append(account)
    if not picked.accounts and not picked.not_yours and not picked.over_limit:
        picked.accounts = with_plans[:MAX_ACCOUNTS]
        picked.over_limit = with_plans[MAX_ACCOUNTS:]
        picked.defaulted = True
    return picked


# --- The records, as the library's values ---------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Trades:
    """An account's trades through `until`, and the orders still open at Alpaca, left out."""

    trades: list[Trade]
    open_orders: int


def trades_for(account: Account, until: date) -> Trades:
    """The journal's buys and sells, each on the day its money changed hands: a filled Alpaca
    order on its fill's day with Alpaca's shares (chapter 11's sync wrote both onto the entry and
    the order), anything else on the entry's date. An order Alpaca has not finished is left out:
    its entry carries the order's notional, not what was bought."""
    entries = list(
        JournalEntry.objects.filter(account=account, kind=TRADE, date__lte=until)
        .exclude(amount=None)
        .order_by("date", "pk")
    )
    orders = {
        order.journal_entry_id: order
        for order in PaperOrder.objects.filter(journal_entry__in=entries)
    }
    trades: list[Trade] = []
    open_orders = 0
    for entry in entries:
        if entry.amount is None:
            continue
        order = orders.get(entry.pk)
        if order is not None and not order.final:
            open_orders += 1
            continue
        day = entry.date
        if order is not None and order.filled_at is not None:
            day = timezone.localdate(order.filled_at)
        trades.append(
            Trade(day, entry.symbol, entry.amount, entry.shares, sell=entry.action == "sell")
        )
    return Trades(trades, open_orders)


@dataclass(frozen=True, slots=True)
class SymbolPrices:
    """One symbol's stored days, oldest first, and whether the value reads its adjusted close."""

    rows: list[tuple[date, DayPrice]]
    adjusted: bool


def prices_for(symbols: Sequence[str], since: date, until: date) -> dict[str, SymbolPrices]:
    """Each symbol's stored days from `since` through `until`, on the adjusted close when every
    one of those days has it, else on the close (decision 134's rule for a chart line)."""
    stored: dict[str, list[DailyClose]] = {symbol: [] for symbol in symbols}
    rows = DailyClose.objects.filter(symbol__in=list(symbols), date__gte=since, date__lte=until)
    for row in rows.order_by("symbol", "date"):
        stored[row.symbol].append(row)
    found: dict[str, SymbolPrices] = {}
    for symbol, days in stored.items():
        adjusted = bool(days) and all(row.adj_close is not None for row in days)
        found[symbol] = SymbolPrices(
            [
                (
                    row.date,
                    DayPrice(row.close, row.adj_close if adjusted and row.adj_close else row.close),
                )
                for row in days
            ],
            adjusted,
        )
    return found


# --- One account's numbers ------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Followed:
    """How often the plan was followed, from its closed month reviews (chapter 12)."""

    closed: int
    followed: int
    skipped: int

    @property
    def text(self) -> str:
        if not self.closed:
            return "no month closed yet"
        skipped = f" ({self.skipped} skipped with a reason)" if self.skipped else ""
        return f"followed in {self.followed} of {self.closed} closed months{skipped}"


def followed(plan: MethodPlan, account: Account, today: date) -> Followed:
    """A closed month counts as followed when the review engine marks it done with no finding,
    the same test as the method page's "months followed"; a skip with a reason is counted apart,
    because the plan allowed it but nothing was bought."""
    closed = list(
        MonthlyReview.objects.filter(plan__in=plan.versions(), closed_at__isnull=False)
        .values_list("month", flat=True)
        .distinct()
    )
    if not closed:
        return Followed(0, 0, 0)
    review = build_review(plan, JournalEntry.entries_for(account), today)
    done = skipped = 0
    for label in closed:
        row = review.month(label)
        if row is None:
            continue
        if row.status == "done" and not row.rule_ids:
            done += 1
        elif row.status == "skipped":
            skipped += 1
    return Followed(len(closed), done, skipped)


def method_text(plan: MethodPlan | None) -> str:
    if plan is None:
        return "No plan"
    name = plan.method().name
    if plan.is_momentum and plan.top_n:
        return f"{name}, top {plan.top_n} of {len(plan.symbol_list())}"
    return f"{name}, {len(plan.symbol_list())} symbol{'s' if len(plan.symbol_list()) != 1 else ''}"


def return_text(total: Decimal | None, days: int) -> str:
    """A change over `days` calendar days in words: as it is under a year ("-10.00% over 3
    days"), as a yearly rate from a year on ("+7.20% a year"), never stretched from a few months
    to a year. A stretch of one day has none."""
    if days <= 0 or total is None:
        return ""
    if days < YEAR_DAYS:
        return f"{percent(total * HUNDRED)} over {days} days"
    return f"{percent(yearly(total, days) * HUNDRED)} a year"


def drawdown_text(drop: Drawdown | None) -> str:
    if drop is None:
        return ""
    if drop.fraction == 0:
        return "no drop: the line never fell below a high"
    stretch = f"{drop.peak_day:%Y-%m-%d} to {drop.trough_day:%Y-%m-%d}"
    return f"{percent(drop.fraction * HUNDRED)}, {stretch}"


@dataclass
class AccountResult:
    """One account on the page: its numbers in words, or why a number is missing."""

    account: Account
    plan: MethodPlan | None
    method: str
    series: Series
    stretch: Period | None
    line: list[tuple[date, Decimal]]
    months: str
    followed: str
    notes: list[str] = field(default_factory=list[str])
    reason: str = ""
    twr: Decimal | None = None
    mwr: Decimal | None = None
    drawdown: Drawdown | None = None

    @property
    def put_in(self) -> str:
        if self.stretch is None:
            return ""
        carried = (
            f" (incl. {money(self.stretch.opening)} held at the start)"
            if self.stretch.opening
            else ""
        )
        return f"{money(self.stretch.put_in)}{carried}"

    @property
    def value(self) -> str:
        if self.stretch is None:
            return ""
        return f"{money(self.stretch.last.value)} on {self.stretch.last.day:%Y-%m-%d}"

    @property
    def gain(self) -> str:
        if self.stretch is None:
            return ""
        return signed_money(self.stretch.gain)

    @property
    def money_weighted(self) -> str:
        if self.stretch is None or self.stretch.length <= 0:
            return ""
        if self.mwr is None:
            return "not worked out: no single rate fits these deposits"
        if self.stretch.length < YEAR_DAYS:
            return return_text(self.mwr, self.stretch.length)
        return f"{percent(self.mwr * HUNDRED)} a year"

    @property
    def time_weighted(self) -> str:
        if self.stretch is None or self.twr is None:
            return ""
        return return_text(self.twr, self.stretch.length)

    @property
    def worst_drop(self) -> str:
        return drawdown_text(self.drawdown)


def symbol_list(trades: Sequence[Trade]) -> list[str]:
    return sorted({trade.symbol for trade in trades})


def account_result(account: Account, start: date, end: date, today: date) -> AccountResult:
    """Everything one row and one line need, from the account's own records."""
    plan = plan_of(account)
    found = trades_for(account, end)
    notes: list[str] = []
    if found.open_orders:
        notes.append(
            f"{found.open_orders} order{'s' if found.open_orders != 1 else ''} still open at "
            "Alpaca: left out until filled."
        )
    since = (min((t.day for t in found.trades), default=start)) - timedelta(PRICE_LOOKBACK_DAYS)
    symbols = symbol_list(found.trades)
    prices = prices_for(symbols, since, end)
    closes_only = [
        symbol for symbol in symbols if prices[symbol].rows and not prices[symbol].adjusted
    ]
    if closes_only:
        notes.append(
            f"{', '.join(closes_only)} valued on closes: a stored day has no adjusted close, so "
            "dividends are not counted and a split would read as a fall. Get history with All "
            "available fills them."
        )
    series = value_series(found.trades, {symbol: prices[symbol].rows for symbol in symbols}, end)
    if series.pending:
        newest = max((day for p in prices.values() for day, _ in p.rows), default=None)
        after = f" (the newest is {newest:%Y-%m-%d})" if newest else ""
        count = len(series.pending)
        notes.append(
            f"{count} trade{'s' if count != 1 else ''} dated after the newest stored close{after}: "
            "counted once the nightly pull stores its day."
        )
    stretch = period(series.days, start, end) if not series.problems else None
    reason = ""
    if series.problems:
        reason = "Not worked out: " + "; ".join(series.problems) + "."
    elif not found.trades:
        reason = "No trades in the journal yet, so there is nothing to value."
    elif stretch is None:
        reason = "No trade of this account counts inside the dates picked."
    line = time_weighted_line(stretch.days) if stretch is not None else []
    if plan is None:
        months = ""
        how_often = "no plan"
    else:
        first = plan.chain_start()
        last = plan.ended_on if not plan.active and plan.ended_on else today
        count = months_running(first, last)
        ended = ", ended" if not plan.active else ""
        months = f"{count} (from {first:%Y-%m-%d}{ended})"
        how_often = followed(plan, account, today).text
    result = AccountResult(
        account=account,
        plan=plan,
        method=method_text(plan),
        series=series,
        stretch=stretch,
        line=line,
        months=months,
        followed=how_often,
        notes=notes,
        reason=reason,
    )
    if stretch is not None:
        result.twr = line_return(line)
        # Under a year the rate is solved per the stretch's own length, so it is the change over
        # the days; from a year on, per year (`return_text` says which).
        unit = stretch.length if 0 < stretch.length < YEAR_DAYS else YEAR_DAYS
        result.mwr = xirr(cash_flows(stretch), days_per_unit=unit)
        result.drawdown = max_drawdown(line)
    return result


# --- The yardstick --------------------------------------------------------------------------------


def yardstick_choices(user: AbstractBaseUser | AnonymousUser) -> list[str]:
    """Every symbol of the person's own: held, watched, or named by a plan."""
    named = MethodPlan.objects.filter(account__owner_id=user.pk).values_list("symbols", flat=True)
    in_plans = {symbol for text in named for symbol in text.split()}
    return sorted(set(manual.owner_symbols(user)) | in_plans)


def default_yardstick(choices: Sequence[str]) -> str:
    """The first S&P 500 index fund among the person's symbols, or "" when there is none."""
    return next((symbol for symbol in SP500_FUNDS if symbol in choices), "")


# --- Alpaca's own number --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AlpacaCheck:
    """Alpaca's equity and cash for a linked account, read now, or why they are missing."""

    equity: Decimal | None = None
    cash: Decimal | None = None
    error: str = ""

    @property
    def in_positions(self) -> Decimal | None:
        """Equity less cash: what Alpaca says the holdings are worth now."""
        if self.equity is None or self.cash is None:
            return None
        return self.equity - self.cash


def read_alpaca(account: Account) -> AlpacaCheck:
    try:
        found = client_for(account, timeout=ALPACA_TIMEOUT_SECONDS).account()
    except AlpacaError as error:
        return AlpacaCheck(error=error.message)
    return AlpacaCheck(found.equity, found.cash)


def alpaca_checks(
    user: AbstractBaseUser | AnonymousUser, accounts: Sequence[Account]
) -> dict[int, AlpacaCheck]:
    """Alpaca's numbers for each account the site owner linked to Alpaca paper, read at the same
    time so the page waits for the slowest answer, not the sum of them."""
    linked = [account for account in accounts if alpaca_allowed(user, account)]
    if not linked:
        return {}
    with ThreadPoolExecutor(max_workers=len(linked)) as pool:
        answers = list(pool.map(read_alpaca, linked))
    return {account.pk: answer for account, answer in zip(linked, answers, strict=True)}
```

### 15.4 The view, the chart and the page

The chart is chapter 13's. Its layout moved out of `build_plot` into `lay_out` in `prices/charts.py`, so lines that
are not stored closes can use it; a `Line` may carry its own hover text (`readout`), which `chart.js` prints instead
of a close, and a `Plot` its own caption and description. `build_plot` calls `lay_out`, so the history and Compare
symbols pages draw exactly as before.

Listing 15-6, Filename: `src/invest_witus_site/compare/views.py`:

```python
"""The Compare methods page (chapter 15): two to four of the signed-in person's accounts on one
chart, each line its value with the money put in left out, rebased to 100, beside a do-nothing
yardstick, and a table of what each account put in, holds and gained.

Owner pages only (`login_required`), and only the person's own accounts: an id that is not theirs
is counted and left out, never named. No vendor is asked for anything while the page draws,
except Alpaca's own equity for an account the site owner linked to Alpaca paper, read with a short
timeout as a cross-check.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.paginator import Page, Paginator
from django.http import HttpRequest, HttpResponse, QueryDict
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from invest_witus.compare import HUNDRED, line_return, max_drawdown
from invest_witus_site.compare.records import (
    MAX_ACCOUNTS,
    MIN_ACCOUNTS,
    SP500_FUNDS,
    AccountResult,
    AlpacaCheck,
    account_result,
    accounts_with_plans,
    alpaca_checks,
    default_yardstick,
    drawdown_text,
    pick_accounts,
    plan_of,
    return_text,
    yardstick_choices,
)
from invest_witus_site.holdings.models import Account
from invest_witus_site.holdings.templatetags.holdings_extras import money
from invest_witus_site.prices.charts import (
    LINE_STYLES,
    DayRow,
    Line,
    Plot,
    SeriesInput,
    index_text,
    lay_out,
    line_days,
)
from invest_witus_site.prices.history import RangeError, closes_between, parse_day
from invest_witus_site.prices.manual import HISTORY_RANGES
from invest_witus_site.prices.models import SymbolProfile
from invest_witus_site.watchlist.models import WatchItem

ROWS_PER_PAGE = 100
VALUE_BASIS = "value with the money put in left out"


@dataclass(frozen=True, slots=True)
class Dates:
    """The stretch compared, and the words of a refused pair."""

    start: date
    end: date
    error: str = ""
    typed_from: str = ""
    typed_to: str = ""


def chosen_dates(params: QueryDict, default_start: date, today: date) -> Dates:
    """`?from=` and `?to=`, each optional: From defaults to the earliest plan start, To to today.
    A date that does not parse, a To after today or a From after To is refused in words, and the
    defaults are shown instead."""
    typed_from = (params.get("from") or "").strip()
    typed_to = (params.get("to") or "").strip()
    try:
        start = parse_day(typed_from, "From") if typed_from else default_start
        end = parse_day(typed_to, "To") if typed_to else today
        if end > today:
            raise RangeError(f"To ({end:%Y-%m-%d}) is after today ({today:%Y-%m-%d}).")
        if start > end:
            raise RangeError(f"From ({start:%Y-%m-%d}) must be on or before To ({end:%Y-%m-%d}).")
    except RangeError as refused:
        return Dates(min(default_start, today), today, str(refused), typed_from, typed_to)
    return Dates(start, end, "", typed_from, typed_to)


@dataclass
class Yardstick:
    """The do-nothing line: one symbol's stored closes, rebased to 100 on its first day in the
    stretch. `line` is None when no close is stored inside it."""

    symbol: str
    name: str
    line: Line | None
    watched_on: Account | None
    twr: str = ""
    drop: str = ""


def yardstick_for(symbol: str, user_accounts: list[Account], dates: Dates) -> Yardstick:
    profile = SymbolProfile.objects.filter(symbol=symbol).first()
    watched = WatchItem.objects.filter(account__in=user_accounts, symbol=symbol).first()
    rows = closes_between(symbol, dates.start, dates.end)
    found = Yardstick(
        symbol, profile.name if profile else "", None, watched.account if watched else None
    )
    if not rows:
        return found
    basis, missing, days = line_days(SeriesInput(symbol, rows), rebase=True)
    found.line = Line(symbol, basis, missing, "", "", "", days)
    points = [(row.day, row.index or HUNDRED) for row in days]
    total = line_return(points)
    length = (days[-1].day - days[0].day).days
    found.twr = return_text(total, length) if total is not None else ""
    found.drop = drawdown_text(max_drawdown(points))
    return found


def account_line(result: AccountResult) -> Line | None:
    """The account's time-weighted line as a chart line: each day's level, its dollar value in
    the close column (the table under the chart prints it), and the hover text written here."""
    if result.stretch is None or not result.line:
        return None
    values = {day.day: day for day in result.stretch.days}
    rows: list[DayRow] = []
    readout: dict[date, str] = {}
    for day, level in result.line:
        held = values[day]
        rows.append(
            DayRow(
                day=day,
                close=held.value,
                adj_close=None,
                value=level,
                change=None,
                change_pct=None,
                index=level,
                source="journal",
            )
        )
        put_in = f", {money(held.flow)} put in that day" if held.flow else ""
        readout[day] = (
            f"{index_text(level)} (start = 100), value {money(held.value)}, "
            f"{money(held.put_in)} put in so far{put_in}"
        )
    return Line(result.account.name, VALUE_BASIS, 0, "", "", "", rows, readout=readout)


def build_chart(
    results: list[AccountResult], yardstick: Yardstick | None, title: str
) -> Plot | None:
    lines = [line for line in (account_line(result) for result in results) if line is not None]
    if yardstick is not None and yardstick.line is not None:
        lines.append(yardstick.line)
    for position, line in enumerate(lines):
        line.color, line.dash, line.pattern = LINE_STYLES[position]
    plot = lay_out(lines, title, rebase=True, noun="day value")
    if plot is not None:
        words = [
            "Each account's line is its value with the money put in left out, so a deposit never "
            "looks like growth; it starts at 100 on the account's first day with a holding in the "
            "range."
        ]
        if yardstick is not None and yardstick.line is not None:
            words.append(
                f"The yardstick, {yardstick.symbol}, is its stored {yardstick.line.basis}, "
                "rebased to 100 on its first day in the range."
            )
        words.append(
            f"Values from your journal and the app's stored closes, as of {plot.last:%Y-%m-%d}."
        )
        plot.caption = " ".join(words)
        plot.desc = (
            "One line per account, and the yardstick's line if it has closes, oldest day on the "
            "left, each starting at 100."
        )
    return plot


@dataclass(frozen=True, slots=True)
class DailyCell:
    level: str
    amount: str


def daily_rows(plot: Plot) -> list[tuple[date, list[DailyCell | None]]]:
    """Newest first: each date with each line's level and dollar amount (an account's value, the
    yardstick's close), or None where a line has no day."""
    maps = [{row.day: row for row in line.days} for line in plot.lines]
    rows: list[tuple[date, list[DailyCell | None]]] = []
    for day in reversed(plot.all_dates):
        cells: list[DailyCell | None] = []
        for found in maps:
            row = found.get(day)
            cells.append(None if row is None else DailyCell(row.index_label, money(row.close)))
        rows.append((day, cells))
    return rows


def page_of[T](rows: list[T], number: str | None) -> Page[T]:
    return Paginator(rows, ROWS_PER_PAGE).get_page(number)


def query_without_page(params: QueryDict) -> str:
    kept = params.copy()
    kept.pop("page", None)
    return kept.urlencode()


@login_required
@require_GET
def compare_methods(request: HttpRequest) -> HttpResponse:
    today = timezone.localdate()
    owned = list(Account.objects.filter(owner_id=request.user.pk).order_by("name"))
    with_plans = accounts_with_plans(request.user)
    picked = pick_accounts(request.GET.getlist("accounts"), owned, with_plans)
    plans = {account.pk: plan_of(account) for account in owned}
    starts = [
        plan.chain_start()
        for account in picked.accounts
        if (plan := plans.get(account.pk)) is not None
    ]
    dates = chosen_dates(request.GET, min(starts) if starts else today, today)
    results = [
        account_result(account, dates.start, dates.end, today) for account in picked.accounts
    ]
    choices = yardstick_choices(request.user)
    asked = (request.GET.get("yardstick") or "").strip().upper()
    if "yardstick" in request.GET:
        symbol = asked if asked in choices else ""
    else:
        symbol = default_yardstick(choices)
    yardstick = yardstick_for(symbol, owned, dates) if symbol else None
    names = ", ".join(account.name for account in picked.accounts)
    title = f"{names}: {dates.start:%Y-%m-%d} to {dates.end:%Y-%m-%d}"
    plot = build_chart(results, yardstick, title) if picked.accounts else None
    checks: dict[int, AlpacaCheck] = alpaca_checks(request.user, picked.accounts)
    page = request.GET.get("page")
    context = {
        "owned": owned,
        "plans": plans,
        "picked": picked,
        "picked_pks": [account.pk for account in picked.accounts],
        "too_few": 0 < len(picked.accounts) < MIN_ACCOUNTS,
        "min_accounts": MIN_ACCOUNTS,
        "max_accounts": MAX_ACCOUNTS,
        "dates": dates,
        "results": results,
        "rows": [(result, checks.get(result.account.pk)) for result in results],
        "any_check": bool(checks),
        "choices": choices,
        "asked_yardstick": asked if "yardstick" in request.GET else None,
        "yardstick": yardstick,
        "sp500_funds": SP500_FUNDS,
        "plot": plot,
        "daily": page_of(daily_rows(plot) if plot else [], page),
        "daily_open": page is not None,
        "base_query": query_without_page(request.GET),
        "return_query": query_without_page(request.GET),
        "history_ranges": [(value, label) for value, (label, _) in HISTORY_RANGES.items()],
        "rows_per_page": ROWS_PER_PAGE,
        "zero": Decimal(0),
    }
    status = 400 if dates.error else 200
    return render(request, "compare/compare_methods.html", context, status=status)
```

Listing 15-7, Filename: `src/invest_witus_site/compare/templates/compare/compare_methods.html`:

```html
{% extends "pages/base.html" %}
{% load holdings_extras %}
{% block title %}Compare methods: Invest.WitUS{% endblock %}
{% block content %}
{# Compare methods (chapter 15, decisions 167 to 171): two to four of the signed-in person's own accounts on one #}
{# chart, each line its value with the money put in left out, beside a do-nothing yardstick, and a table. #}
<section class="container" aria-labelledby="compare-methods-heading">
  <p class="eyebrow">Signed in</p>
  <h1 id="compare-methods-heading">Compare methods</h1>
  <p>Each account runs one method. Pick {{ min_accounts }} to {{ max_accounts }} of your accounts and a stretch of days: the chart puts them side by side, and the table says what each one put in, holds and gained.</p>
  {% if owned %}
  <form method="get" class="compare-form">
    <fieldset class="field">
      <legend>Accounts, {{ min_accounts }} to {{ max_accounts }}</legend>
      <ul class="plain choice-list">
        {% for account in owned %}
        {% with plan=plans|item:account.pk %}
        <li><label><input type="checkbox" name="accounts" value="{{ account.pk }}"{% if account.pk in picked_pks %} checked{% endif %}> <span>{{ account.name }} <span class="muted small">({% if plan %}{{ plan.method.name }}{% if not plan.active %}, ended{% endif %}{% else %}no plan{% endif %})</span></span></label></li>
        {% endwith %}
        {% endfor %}
      </ul>
      <p class="small muted">Left empty, the page picks every account that runs or ran a plan, up to {{ max_accounts }}.</p>
    </fieldset>
    <fieldset class="field range-dates">
      <legend>Dates</legend>
      <div class="range-dates-row">
        <div><label for="compare-from">From</label>
        <input type="date" id="compare-from" name="from" value="{% if dates.typed_from %}{{ dates.typed_from }}{% else %}{{ dates.start|date:'Y-m-d' }}{% endif %}"{% if dates.error %} aria-describedby="range-error"{% endif %}></div>
        <div><label for="compare-to">To</label>
        <input type="date" id="compare-to" name="to" value="{% if dates.typed_to %}{{ dates.typed_to }}{% else %}{{ dates.end|date:'Y-m-d' }}{% endif %}"{% if dates.error %} aria-describedby="range-error"{% endif %}></div>
      </div>
      <p class="small muted">From starts at the earliest plan start of the accounts picked, To at today.</p>
    </fieldset>
    <div class="field">
      <label for="compare-yardstick">Yardstick</label>
      <select id="compare-yardstick" name="yardstick">
        <option value=""{% if not yardstick %} selected{% endif %}>None</option>
        {% for symbol in choices %}<option value="{{ symbol }}"{% if yardstick and yardstick.symbol == symbol %} selected{% endif %}>{{ symbol }}</option>{% endfor %}
      </select>
      <p class="small muted">A do-nothing line: what an S&amp;P 500 index fund did over the same days. The page starts on the first of {{ sp500_funds|join:", " }} that you hold, watch or name in a plan; any symbol of yours can stand in.</p>
    </div>
    <button type="submit">Compare</button>
  </form>
  {% else %}
  <p>No accounts yet, so there is nothing to compare.</p>
  {% endif %}

  {% if dates.error %}<p class="message error" id="range-error">{{ dates.error }} Showing {{ dates.start|date:"Y-m-d" }} to {{ dates.end|date:"Y-m-d" }} instead.</p>{% endif %}
  {% if picked.not_yours %}<p class="message error">Left out {{ picked.not_yours }} account{{ picked.not_yours|pluralize }} that {{ picked.not_yours|pluralize:"is,are" }} not yours.</p>{% endif %}
  {% if picked.over_limit %}<p class="message{% if not picked.defaulted %} error{% endif %}">Up to {{ max_accounts }} accounts at once; left out: {% for account in picked.over_limit %}{{ account.name }}{% if not forloop.last %}, {% endif %}{% endfor %}.</p>{% endif %}
  {% if owned and not picked.accounts %}<p class="message">None of your accounts runs a plan yet. Start one on an account's method page, or tick accounts above.</p>{% endif %}
  {% if too_few %}<p class="message">Pick at least {{ min_accounts }} accounts to compare; the one picked is shown on its own.</p>{% endif %}

  {% if yardstick and not yardstick.line %}
  <div class="message" id="yardstick-missing">
    <p>No closes stored for {{ yardstick.symbol }} from {{ dates.start|date:"Y-m-d" }} to {{ dates.end|date:"Y-m-d" }}, so the chart has no yardstick.</p>
    {% if yardstick.watched_on %}
    {% include "prices/_history_form.html" with account=yardstick.watched_on symbol=yardstick.symbol return_to="compare-methods" %}
    {% else %}
    <p>Add {{ yardstick.symbol }} to a watch list on an account page, then press <strong>Get history</strong> there.</p>
    {% endif %}
  </div>
  {% elif not yardstick and asked_yardstick is None %}
  <p class="message">No yardstick: none of {{ sp500_funds|join:", " }} is held, watched or named in a plan of yours. Add one to a watch list and press <strong>Get history</strong>, or pick any of your symbols above.</p>
  {% endif %}

  {% if plot %}
  {% include "prices/_chart.html" %}
  {% include "prices/_thinned.html" %}
  {% endif %}

  {% if results %}
  <div class="table-scroll" role="region" aria-label="The accounts compared, scrolls sideways on a narrow screen" tabindex="0">
  <table class="holdings">
    <caption>Each account from {{ dates.start|date:"Y-m-d" }} to {{ dates.end|date:"Y-m-d" }}</caption>
    <thead>
      <tr>
        <th scope="col">Account</th>
        <th scope="col">Method</th>
        <th scope="col" class="num">Money put in</th>
        <th scope="col" class="num">Value now</th>
        <th scope="col" class="num">Gain</th>
        <th scope="col" class="num">Money-weighted return</th>
        <th scope="col" class="num">Time-weighted return</th>
        <th scope="col" class="num">Worst drop</th>
        <th scope="col">Months running</th>
        <th scope="col">Plan followed</th>
      </tr>
    </thead>
    <tbody>
      {% for result, check in rows %}
      <tr>
        <th scope="row"><a href="{% url 'account-detail' result.account.pk %}">{{ result.account.name }}</a></th>
        <td>{% if result.plan %}<a href="{% url 'method-page' result.account.pk %}">{{ result.method }}</a>{% else %}{{ result.method }}{% endif %}</td>
        {% if result.stretch %}
        <td class="num">{{ result.put_in }}</td>
        <td class="num">{{ result.value }}</td>
        <td class="num">{{ result.gain }}</td>
        <td class="num">{{ result.money_weighted|default:"one day only: no return yet" }}</td>
        <td class="num">{{ result.time_weighted|default:"one day only: no return yet" }}</td>
        <td class="num">{{ result.worst_drop|default:"needs two days" }}</td>
        {% else %}
        <td colspan="6">{{ result.reason }}</td>
        {% endif %}
        <td>{{ result.months|default:"no plan" }}</td>
        <td>{{ result.followed }}</td>
      </tr>
      {% endfor %}
      {% if yardstick and yardstick.line %}
      <tr>
        <th scope="row">{{ yardstick.symbol }}{% if yardstick.name %} <span class="muted small">({{ yardstick.name }})</span>{% endif %}</th>
        <td>Yardstick: bought once, never touched</td>
        <td colspan="3">No money put in: a price line, rebased to 100.</td>
        <td class="num">no deposits</td>
        <td class="num">{{ yardstick.twr|default:"one day only: no return yet" }}</td>
        <td class="num">{{ yardstick.drop|default:"needs two days" }}</td>
        <td colspan="2">Uses the {{ yardstick.line.basis }}.</td>
      </tr>
      {% endif %}
    </tbody>
  </table>
  </div>
  <p class="small"><strong>Money-weighted or time-weighted?</strong> The money-weighted return counts when your money went in, so it judges the method and the timing of your deposits together; the time-weighted return leaves the deposits out, so it judges the method alone, and it is what the chart draws. Under a year, both are the change over the days shown; from a year on, both are a yearly rate.</p>
  {% for result in results %}{% if result.notes %}
  <p class="small muted">{{ result.account.name }}: {{ result.notes|join:" " }}</p>
  {% endif %}{% endfor %}
  <p class="small muted">The value is what each account's trades bought, at the newest stored close on or before each day; the adjusted close counts dividends as if they bought more. Cash an account keeps beside its holdings is not in it: the app keeps no cash ledger, so the money put in is what the buys cost less what any sells brought back. A buy placed through Alpaca counts from the day it filled, with the shares Alpaca reported.</p>
  {% endif %}

  {% if any_check %}
  <div class="table-scroll" role="region" aria-label="Alpaca's own numbers, scrolls sideways on a narrow screen" tabindex="0">
  <table class="holdings" id="alpaca-check">
    <caption>Cross-check: Alpaca's own numbers, read now</caption>
    <thead>
      <tr>
        <th scope="col">Account</th>
        <th scope="col" class="num">Value here</th>
        <th scope="col" class="num">Alpaca: holdings now</th>
        <th scope="col" class="num">Alpaca: equity</th>
        <th scope="col" class="num">Alpaca: cash</th>
      </tr>
    </thead>
    <tbody>
      {% for result, check in rows %}{% if check %}
      <tr>
        <th scope="row">{{ result.account.name }}</th>
        <td class="num">{{ result.value|default:"not worked out" }}</td>
        {% if check.error %}
        <td colspan="3">{{ check.error }}</td>
        {% else %}
        <td class="num">{{ check.in_positions|money }}</td>
        <td class="num">{{ check.equity|money }}</td>
        <td class="num">{{ check.cash|money }}</td>
        {% endif %}
      </tr>
      {% endif %}{% endfor %}
    </tbody>
  </table>
  </div>
  <p class="small muted">Alpaca's holdings are its equity less its cash, at its own latest prices; the value here uses the app's newest stored close. They should be close, not equal: a difference of more than a few percent means a trade is missing from the journal or a close is missing from the app.</p>
  {% endif %}

  <aside class="how-to-read" aria-labelledby="how-to-read-heading">
    <p id="how-to-read-heading"><strong>How to read this.</strong></p>
    <ul>
      <li><strong>A few months prove nothing.</strong> Over months, luck moves these lines more than any method does. Judge a method over years, and by whether you kept to it.</li>
      <li><strong>The methods buy differently.</strong> 12-1 momentum buys only its top N of your list each month; index investing buys all of it. Holding fewer symbols makes the line swing more, up and down.</li>
      <li><strong>Same cash, same amount, same list: a fair test.</strong> When the accounts start with the same money, put in the same amount each month and draw from the same symbols, the method is the one thing that differs.</li>
      <li><strong>Past results do not predict future results.</strong> This page describes what happened; it is not a forecast and not advice. <span class="muted">Lesson coming.</span></li>
    </ul>
  </aside>

  {% if plot %}
  <details class="daily" id="daily"{% if daily_open %} open{% endif %}>
    <summary>Every day's values</summary>
    <div class="table-scroll" role="region" aria-labelledby="daily-caption" tabindex="0">
    <table class="holdings">
      <caption id="daily-caption">Each line's level (start = 100) and dollars per stored day, newest first{% if daily.paginator.num_pages > 1 %}, {{ rows_per_page }} a page{% endif %}</caption>
      <thead>
        <tr>
          <th scope="col">Date</th>
          {% for line in plot.lines %}
          <th scope="col" class="num">{{ line.symbol }} (start = 100)</th>
          <th scope="col" class="num">{{ line.symbol }} {% if line.basis == "adjusted close" or line.basis == "close" %}close{% else %}value{% endif %}</th>
          {% endfor %}
        </tr>
      </thead>
      <tbody>
        {% for day, cells in daily %}
        <tr>
          <th scope="row">{{ day|date:"Y-m-d" }}</th>
          {% for cell in cells %}
          {% if cell %}
          <td class="num">{{ cell.level }}</td>
          <td class="num">{{ cell.amount }}</td>
          {% else %}
          <td class="num muted" colspan="2">no value</td>
          {% endif %}
          {% endfor %}
        </tr>
        {% endfor %}
      </tbody>
    </table>
    </div>
    {% include "prices/_pager.html" with page=daily base_query=base_query label="Every day's values" anchor="#daily" %}
  </details>
  {% endif %}
  <p class="small muted">Your own accounts only, from your journal and the app's stored closes. The closes vendor's free plan is for the owner's own use, so this page is never public. A comparison of the past, not a forecast. Information, not advice.</p>
</section>
{% endblock %}
```

Then the small changes: the app in `INSTALLED_APPS` and `path("compare/", ...)` in `urls.py`; **Compare methods**
in the header, the account list and under an account's method line; an optional `timeout` on `AlpacaPaper`,
`client_for_slot` and `client_for`; `return_to=compare-methods` in `owner_views.fetch_history` with
`compare_methods_url`, and the hidden `return_query` in `prices/_history_form.html`; and in `site.css`, a checkbox
in a `.choice-list` keeping its own size. Take them from the tag if you prefer:
`git checkout v15 -- src/invest_witus_site/prices src/invest_witus_site/paper/alpaca.py`.

### 15.5 Green, and the page on your laptop

Listing 15-8, Terminal:

```sh
uv run pytest -q
uv run ruff check . && uv run ruff format --check . && uv run pyright
uv run --env-file .env python manage.py makemigrations --check --dry-run
```

```text
969 passed
All checks passed!
262 files already formatted
0 errors, 0 warnings, 0 informations
No changes detected
```

On your laptop: give two paper accounts a plan each (the method page's start form), log a few buys in each
account's logbook over a month of stored closes (CSV files from chapter 02 work), put an index fund's placeholder
on a watch list with its closes, and open **Compare methods**. Point at the chart: each account's line shows its
level, its value and the money put in so far. Change **From** to a day after the first buy: the table's "Money put
in" now starts with "held at the start".

### 15.6 What the owner does outside the editor

Nothing to set up: no variable, no package, no migration. Merge the chapter and open **Compare methods**. If the
yardstick says it has no closes, press its **Get history**. On accounts linked to Alpaca paper, compare "Alpaca:
holdings now" with "Value here".

## Checkpoint

- `uv run pytest` prints `969 passed`; ruff, pyright and `makemigrations --check` pass.
- Listing 15-4 prints the four days, the line 100, 110, 120, 90, a gain of -30, -10% time-weighted, -17.08%
  money-weighted over 3 days, and a worst drop of 25%.
- Another person's account never appears on your page, even by its id.
- The history and Compare symbols pages draw as they did in chapter 13.
- Commit and push: `git add -A && git commit -m "Chapter 15: compare your methods"`.

## Exercises

1. **The same money in the yardstick.** Add a row: the yardstick bought with each account's own deposits on the
   same days, with its value and money-weighted return. Which question does it answer that the rebased line does
   not?
   *(The reference built this after the tag, on 2026-11-10, decision 185: `same_money` in `compare.py` buys the
   yardstick with each trade's money on the trade's own day at that day's stored adjusted close and names a day
   with no stored price instead of guessing; the page adds a "Same money into SPY" row under each account and its
   line on the chart while there is room for it. Try it yourself before you read `git diff v15 main -- src/invest_witus/compare.py`.)*
2. **A cash ledger.** Store each account's starting cash and every fill's cost, and show the whole account's value
   (holdings plus cash). Write the decision first: what does "money put in" mean once the cash was there from day
   one?
3. **Monthly returns.** Under the table, a grid of each account's time-weighted return per calendar month, with
   the best and worst month marked. Keep the reason where a month has no value.
4. **The worst drop's recovery.** Add how many days the line took to get back above its old high, or "not yet".

## If you get stuck

- Browse: https://github.com/dapperAuteur/invest-witus/tree/v15
- Diff for this chapter: https://github.com/dapperAuteur/invest-witus/compare/c459ce7...v15 (the diff from `v14a`
  also holds the work between chapters that step 15.0 takes)
- Zip: https://github.com/dapperAuteur/invest-witus/archive/v15.zip
- Take the reference's files. Chapter 15 added `src/invest_witus/compare.py`, the `src/invest_witus_site/compare/`
  app (`__init__.py`, `apps.py`, `records.py`, `views.py` and `templates/compare/compare_methods.html`) and
  `tests/test_ch15.py`; and changed `settings.py`, `urls.py`, `prices/charts.py`, `prices/owner_views.py`,
  `prices/static/prices/chart.js`, `prices/templates/prices/_chart.html` and `_history_form.html`,
  `paper/alpaca.py`, `pages/templates/pages/_header.html`, `holdings/templates/holdings/account_list.html` and
  `account_detail.html`, and `pages/static/pages/site.css`. Nothing moved:
  `git fetch reference --tags && git checkout v15 -- src tests`.
- `test_xirr_finds_the_yearly_rate_worked_out_by_hand` returns `None`: your present value used `days / 365` with
  integer division, or started the clock at the last flow instead of the first.
- `test_a_stretch_from_the_start_has_nothing_carried_in` finds an opening of 0 on day one but a gain off by the
  first day's move: you set the opening to the first day's value less its deposit when nothing was held before. Only
  carry a value in when the day before the range held something.
- The money-weighted return reads "not worked out" for a short losing stretch: you solved per year. Solve per the
  stretch's own length under a year (`days_per_unit`).
- Every account line is flat at 100: `time_weighted_line` divided by today's value instead of yesterday's.

## What we learned

- A value over time is a fold over days: apply the day's events, then price what is held.
- Leave the deposits out to judge a method; put them in to judge what happened to your money. Both are true; they
  answer different questions, and the page says which is which.
- A number found by search needs a stated interval, a tolerance, a step limit and an honest "no answer".
- Three days are three days. A yearly rate from them is noise multiplied.
- A comparison is fair only when everything but the method is the same, and even then a few months prove nothing.

## Next

Chapter 16 reads what a company reports to the SEC: its recent filings and its key numbers from SEC EDGAR. The
CentenarianOS events are chapter 17 (decision 184).
