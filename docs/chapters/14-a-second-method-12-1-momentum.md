# Chapter 14: A second method: 12-1 momentum

**Starts from:** tag `v13`, plus the reference's work between chapters (step 14.0). **Ends at:** tag `v14`.
**Written against:** Python 3.14.10, uv 0.13.6, Django 5.2.18, and IRS Publication 550 (2025) as read on October
29, 2026.
**Goal:** the app holds you to a second method. 12-1 momentum ranks a list of candidates you chose by how much each
rose over the past year without its latest month, and puts the month's money into the top few, in equal parts. You
write the method's seven rules into a TOML file next to chapter 03's, compute the ranking in a small module with no
Django in it, check the journal against the new rules with a second rule set, and teach the engine to run whichever
set the plan's method names. A momentum plan starts from the same form with one more number, the top N. The method
page draws the ranking as bars with a table under them, a watched symbol's chart shades the window the return is
measured over, the watch list shows each symbol's number with an arrow, and each picture carries a short "How to read
this". On a paper account, Confirm buys this month's top N.
**Time:** 5 to 6 hours for the code and tests. The laptop walk-through takes 10 minutes.

The listings in this chapter are not typed in by hand. `scripts/render_chapter.py` pastes the real files from
tag `v14` into the chapter text, so what you read and what the tests run are the same bytes.

## What you will learn

- **Windowing by calendar month:** the last stored close of a month, month arithmetic that crosses a year, and a
  window defined by months back from today instead of by days.
- **Ranking with `Decimal`:** a sort key that orders by return and breaks ties the same way every time, and a
  result type that keeps the candidates it could not rank with the reason.
- **A second rule set in the same shape as the first:** a registry from method id to the rules it checks, and a
  test that walks every rules file the package ships.
- **Generalizing without rewriting:** one branch in the engine, optional arguments with the old behavior as the
  default, and an earlier chapter's test that pinned a list.
- **Charts that read without color or script:** bars drawn on the server, a filled or outlined shape, a sign and a
  word beside each number, and a table as the text alternative.

## Before the code: what the PRD asks, and seven decisions

**What the PRD asks.** Section 7.1, method 2: "Rank the user's own universe by return from 12 months ago to 1 month
ago (skipping the most recent month); hold the top N, equal weight; review monthly; trade only at a review." And:
"Method 2 warns before a sell-and-rebuy of the same security within 30 days (wash-sale rule, IRS Publication 550)".
The roadmap's row 14 adds "a second rule block on the same engine". Ranking a list by its past return is the idea
Gray and Vogel (2016) build their momentum system on; their system also screens for the quality of the rise and
rebalances each quarter. This chapter builds the PRD's simpler monthly version. The book's system can come later as
a separately named method, and nothing from the book is copied here.

**Decision 1: seven rules, written before the code.** Each rule is a sentence you can follow without the app, and
each has a check the app can run on your journal (decisions log, row 142):

| Rule id | What it says | What the review flags |
|---|---|---|
| `candidates-only` | Rank and buy only the candidates your plan names | a buy of any other symbol |
| `rank-by-12-1` | Rank by the 12-1 return; a candidate without both closes is not ranked and not bought | a buy of a candidate that was not ranked that month |
| `hold-top-n` | At each rebalance, buy every candidate in the top N and none below | a buy ranked below the top N; a top-N candidate with no buy in a month that had one |
| `equal-weight` | Split the month's amount equally across the symbols you buy, to the cent | a buy more than a cent away from its equal part |
| `sell-what-leaves` | Sell the whole holding once it leaves the top N, and nothing still in it | a holding not sold in a month it ranked outside; a sale of a symbol inside |
| `rebalance-each-month` | Rebalance once in every month of the plan | a month due with no trade (a skip with its reason explains it) |
| `trade-only-at-review` | Trade only within the plan's window at the start of the month | a trade after the window |

Every `lesson` is empty. The lessons will live in the Learn.WitUS preview course "A Method You Can Keep", one per
rule, and none is published yet, so every rule reads "lesson coming". A rule id becomes the second half of its
lesson's address, so choose ids you will not want to rename. The wash-sale warning is not a rule: the method can
require buying back in November what it sold in October, so a rule against that would contradict `hold-top-n`.

**Decision 2: the window, the month-end close and ties.** A rebalance in month M reads the last stored close of
month M-13 and of month M-2. For a rebalance in November 2026 that is the end of October 2025 to the end of
September 2026, and October 2026, the latest full month, is left out. The month-end close is the latest day stored
inside the calendar month, whatever day that is; a month with no close is missing, never filled in from a
neighbor. The return is `end / start - 1`, exact in `Decimal`. Highest first; equal returns are ordered by symbol,
A to Z, and marked tied, so the same prices always give the same order. Row 143.

**Decision 3: adjusted closes.** A split halves the close and leaves the adjusted close alone, so a ranking on
closes would read a split as a fall. The web reads `adj_close` where the row has it and the close where it does not
(a CSV file on a laptop has none), and the page says how many closes had no adjusted value. Row 143.

**Decision 4: one more number on the plan.** `MethodPlan.top_n`, nullable, so the migration is additive. The
candidates are the plan's `symbols`, and `amount` is the month's money, split equally across that month's top N:
method 1's monthly contribution, applied to a ranked list. Equal weight is therefore about each month's new money,
not the value you already hold; rebalancing what you hold back to equal parts needs each position's value and is
left for later. Starting a momentum plan puts every candidate on the watch list, because the nightly pull only
fetches symbols you hold or watch. Row 144.

**Decision 5: a rule set per method.** Chapter 03's `review` and its `CHECKED_RULES` stay exactly as they are. The
new rules get their own module, `adherence/momentum.py`, with its own `CHECKED_RULES` and a `review` that takes the
month's rankings as an argument, and `adherence/rule_sets.py` maps each method id to its set. The engine branches
once on the plan's method. A month where no candidate can be ranked is not judged by rank: a missing price is the
app's gap, not your mistake. Row 145.

**Decision 6: buys only, and a wash-sale warning.** On a paper account, Confirm stages one buy per top-N symbol,
the amount split to the cent in rank order, through chapter 11's ids, budget and sync. A holding that left the top
N is listed as "Sell all of GAMMA" and is not placed by the app. Selling on Alpaca's paper account does not need
the live-trading checklist; the sell path (read the position, close it, book what it brought into the journal and
the sync) is a design of its own, so it waits for a later addendum, and you sell in Alpaca's paper dashboard and
log the sale here. Before a buy of a symbol the journal shows sold in the last 30 days, the page prints a wash-sale
warning. IRS Publication 550 says a wash sale "occurs when you sell or trade stock or securities at a loss and
within 30 days before or after the sale you" buy substantially identical stock or securities, and that the
disallowed loss is added to the cost of the new shares (Internal Revenue Service [IRS], 2026). A paper account has
no tax effect; the warning is there for the day the account is live. Row 146.

**Decision 7: three pictures, each with "How to read this".** Ranked bars on the method page; the window shaded on
a watched symbol's chart, with the excluded month lighter and labelled "excluded"; and a 12-1 column on the watch
list with an arrow, the word up or down, and the number. All three are for the account's owner, on an account that
runs momentum, drawn on the server, with no script. Row 147. Rank changes from month to month and a rolling 12-1
line are chapter 14a.

## Steps

### 14.0 Take the work between chapters

Between `v13` and this chapter the reference took three pieces of work that are not chapters: adjusted closes,
splits and dividends with the price charts and their ranges (decisions 114 to 141), the price buttons, and WitUS
Outbox. This chapter's shaded window draws on those charts, and its ranking on the adjusted closes. Take them from
the reference at the commit this chapter starts from, then migrate:

Listing 14-1, Terminal:

```sh
git fetch reference --tags
git checkout e635e10 -- src tests .env.example
uv run --env-file .env python manage.py migrate
uv run pytest -q
```

```text
Operations to perform:
  Apply all migrations: accounts, admin, auth, contenttypes, holdings, methods, outbox, pages, paper, prices, reports, sessions, watchlist
Running migrations:
  Applying outbox.0001_initial... OK
  Applying prices.0004_daily_close_adjustments... OK
696 passed in 27.36s
```

Commit that as its own step (`git commit -am "Take the reference's work between chapters 13 and 14"`), so this
chapter's diff is only this chapter.

### 14.1 The tests

Listing 14-2, Filename: `tests/test_ch14.py`:

```python
"""Chapter 14 checkpoint: a second method, 12-1 momentum. The 12-1 math in Decimal from planted
prices (the window, the month-end close, the return, the ranking with its ties and its missing
history); a rule set per method, each equal to its rules file; the second rule set's findings, one
rule at a time; a momentum plan started from the same form with its top N, its candidates put on
the watch list; the engine ranking every month from stored adjusted closes; the ranked bars with
their table and "How to read this", the shaded window on a history chart, the watch list's badge;
buys on paper for the top N in equal parts, a refusal when nothing is ranked, and the wash-sale
warning. Placeholder symbols only (ALPHA, BETA, GAMMA, DELTA, INDEX, OTHER); every price is planted
here, and no page that is public shows any of it."""

import random
from collections.abc import Iterable
from datetime import date
from decimal import Decimal

import httpx
import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone
from pytest_django.fixtures import Settings

from invest_witus.adherence import momentum as momentum_rules
from invest_witus.adherence.journal import Action, Entry
from invest_witus.adherence.plan import Plan
from invest_witus.adherence.rule_sets import CHECKED_RULES
from invest_witus.methods.momentum_12_1 import (
    Month,
    Ranking,
    Score,
    Unranked,
    Window,
    add_months,
    month_ends,
    rank,
    score,
)
from invest_witus.methods.rulebook import LESSON_COMING, available_methods, load_method
from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.engine import build_review
from invest_witus_site.methods.forms import PlanChangeForm
from invest_witus_site.methods.models import JournalEntry, MethodPlan
from invest_witus_site.methods.momentum import (
    bar_chart,
    percent_text,
    price_series,
    ranking_for,
    rebalance,
)
from invest_witus_site.paper import alpaca, orders
from invest_witus_site.paper.models import PaperOrder
from invest_witus_site.prices.models import DailyClose
from invest_witus_site.watchlist.models import WatchItem
from tests.test_ch10 import tables_in, text
from tests.test_ch11 import DAY, KEY_ID, SECRET, FakeAlpaca

D = Decimal
MOMENTUM = "momentum-12-1"
CANDIDATES = "ALPHA BETA GAMMA DELTA"
CANDIDATE_LIST: list[str] = ["ALPHA", "BETA", "GAMMA", "DELTA"]
PUBLIC_PATHS = ["/", "/faq/", "/privacy/", "/terms/", "/contact/", "/waitlist/"]


# --- Planting prices ------------------------------------------------------------------------------


def monthly(start: Month, count: int) -> list[Month]:
    return [add_months(start, step) for step in range(count)]


def closes(
    months: Iterable[Month], growth: str, base: str = "100", day: int = 28
) -> list[tuple[date, Decimal]]:
    """One close a month on `day`, starting at `base` and growing by `growth` each month."""
    value = D(base)
    rows: list[tuple[date, Decimal]] = []
    for year, month in months:
        rows.append((date(year, month, day), value.quantize(D("0.0001"))))
        value *= 1 + D(growth)
    return rows


def plant(symbol: str, rows: list[tuple[date, Decimal]], adjusted: bool = True) -> None:
    for day, value in rows:
        DailyClose.objects.create(
            symbol=symbol,
            date=day,
            close=value,
            adj_close=value if adjusted else None,
            source="csv",
            fetched_at=timezone.now(),
        )


def plant_candidates(last: Month) -> None:
    """Twenty months ending at `last`: ALPHA rises 2% a month, BETA 1%, GAMMA falls 1% and has no
    adjusted closes (a CSV file), DELTA has only the last six months, so it cannot be ranked."""
    months = monthly(add_months(last, -19), 20)
    plant("ALPHA", closes(months, "0.02"))
    plant("BETA", closes(months, "0.01"))
    plant("GAMMA", closes(months, "-0.01"), adjusted=False)
    plant("DELTA", closes(months[-6:], "0.05"))


# --- Fixtures -------------------------------------------------------------------------------------


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
    """The site owner, a superuser, as chapter 11 needs for Alpaca paper."""
    return django_user_model.objects.create_superuser("owner", "owner@example.com", "pw")


@pytest.fixture
def someone(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("someone")


@pytest.fixture
def account(owner: User) -> Account:
    return Account.objects.create(
        name="Practice", broker="Example Broker", kind="paper", owner=owner
    )


@pytest.fixture
def owner_client(client: Client, owner: User) -> Client:
    client.force_login(owner)
    return client


def momentum_plan(account: Account, started_on: date, **extra: object) -> MethodPlan:
    return MethodPlan.objects.create(
        account=account,
        method_id=MOMENTUM,
        amount=D("100.00"),
        buy_window_days=7,
        symbols=CANDIDATES,
        top_n=2,
        started_on=started_on,
        **extra,
    )


def this_month() -> Month:
    today = timezone.localdate()
    return today.year, today.month


@pytest.fixture
def running(account: Account) -> MethodPlan:
    """A momentum plan that started last month, with prices through last month."""
    plant_candidates(add_months(this_month(), -1))
    start = add_months(this_month(), -1)
    return momentum_plan(account, date(start[0], start[1], 1))


# --- The 12-1 math --------------------------------------------------------------------------------


def test_the_window_runs_from_13_months_back_to_2_and_leaves_the_latest_month_out() -> None:
    november = Window.for_month(2026, 11)
    assert (november.start, november.end, november.excluded) == ((2025, 10), (2026, 9), (2026, 10))
    january = Window.for_month(2026, 1)
    assert (january.start, january.end, january.excluded) == ((2024, 12), (2025, 11), (2025, 12))
    assert november.needs == "a close in 2025-10 and in 2026-09"


def test_the_month_end_close_is_the_last_stored_day_of_the_month() -> None:
    rows = [
        (date(2026, 9, 2), D("90")),
        (date(2026, 9, 30), D("101")),
        (date(2026, 9, 29), D("150")),
        (date(2026, 10, 1), D("999")),
    ]
    random.Random(14).shuffle(rows)
    ends = month_ends(rows)
    assert ends[(2026, 9)] == (date(2026, 9, 30), D("101"))
    assert ends[(2026, 10)] == (date(2026, 10, 1), D("999"))
    assert (2026, 8) not in ends, "a month without a close is absent, never filled in"


def test_the_12_1_return_is_end_over_start_less_one_and_ignores_the_excluded_month() -> None:
    window = Window.for_month(2026, 11)
    rows = [
        (date(2025, 10, 31), D("80")),
        (date(2026, 9, 30), D("90")),
        (date(2026, 10, 30), D("5000")),  # the excluded month: no effect
        (date(2026, 11, 2), D("1")),  # the rebalance month itself: no effect
    ]
    found = score("ALPHA", rows, window)
    assert isinstance(found, Score)
    assert found.change == D("0.125")
    assert isinstance(found.change, Decimal)
    assert (found.start_day, found.end_day) == (date(2025, 10, 31), date(2026, 9, 30))
    assert percent_text(found.change) == "+12.5%"
    assert percent_text(D("-0.05")) == "-5.0%"


def test_the_ranking_is_highest_first_with_ties_in_symbol_order() -> None:
    window = Window.for_month(2026, 11)

    def two(end: str) -> list[tuple[date, Decimal]]:
        return [(date(2025, 10, 31), D("100")), (date(2026, 9, 30), D(end))]

    ranking = rank({"GAMMA": two("110"), "BETA": two("120"), "ALPHA": two("110")}, window, 2)
    assert [(p.rank, p.symbol, p.top, p.tied) for p in ranking.places] == [
        (1, "BETA", True, False),
        (2, "ALPHA", True, True),
        (3, "GAMMA", False, True),
    ]
    assert ranking.top == ["BETA", "ALPHA"]
    with pytest.raises(ValueError, match="top_n must be at least 1"):
        rank({}, window, 0)


def test_a_candidate_with_missing_history_is_not_ranked_and_says_what_it_needs() -> None:
    window = Window.for_month(2026, 11)
    short = [(date(2026, 3, 31), D("50")), (date(2026, 9, 30), D("60"))]
    zero = [(date(2025, 10, 31), D("0")), (date(2026, 9, 30), D("60"))]
    ranking = rank({"DELTA": short, "OTHER": zero, "ALPHA": []}, window, 2)
    assert not ranking.ranked and ranking.top == []
    reasons = {item.symbol: item.reason for item in ranking.unranked}
    assert reasons["DELTA"] == (
        "no close stored in 2025-10; the window needs a close in 2025-10 and in 2026-09"
    )
    assert reasons["ALPHA"].startswith("no close stored in 2025-10 or 2026-09")
    assert reasons["OTHER"] == "a close of zero or less in the window"
    assert isinstance(score("DELTA", short, window), Unranked)


def test_the_bars_share_one_scale_with_the_zero_line_between_them() -> None:
    window = Window.for_month(2026, 11)

    def two(end: str) -> list[tuple[date, Decimal]]:
        return [(date(2025, 10, 31), D("100")), (date(2026, 9, 30), D(end))]

    chart = bar_chart(rank({"ALPHA": two("120"), "BETA": two("90")}, window, 1))
    assert chart is not None
    assert chart.zero_x == D("33.33")
    up, down = chart.bars
    assert (up.symbol, up.x, up.width, up.direction, up.text) == (
        "ALPHA",
        D("33.33"),
        D("66.67"),
        "up",
        "+20.0%",
    )
    assert (down.symbol, down.x, down.width, down.direction) == (
        "BETA",
        D("0.00"),
        D("33.33"),
        "down",
    )
    assert bar_chart(rank({}, window, 1)) is None


# --- A rule set per method ------------------------------------------------------------------------


def test_every_method_the_package_ships_has_a_rule_set_equal_to_its_rules_file() -> None:
    shipped = [method.id for method in available_methods()]
    assert shipped == ["index-dca", MOMENTUM]
    for method_id in shipped:
        assert {rule.id for rule in load_method(method_id).rules} == CHECKED_RULES[method_id]
    method = load_method(MOMENTUM)
    assert len(method.rules) == 7
    assert all(rule.lesson == "" for rule in method.rules), "no lesson is published yet"
    assert method.lesson_for("rank-by-12-1") == LESSON_COMING


# --- The second rule set, one rule at a time ------------------------------------------------------

PLAN = Plan(
    method=MOMENTUM,
    start=date(2026, 11, 1),
    amount=D("100.00"),
    symbols=frozenset({"ALPHA", "BETA", "GAMMA", "DELTA"}),
    buy_window_days=7,
)


def november_ranking() -> dict[Month, Ranking]:
    """For November 2026: ALPHA first, BETA second, GAMMA third, DELTA unranked."""
    window = Window.for_month(2026, 11)

    def two(end: str) -> list[tuple[date, Decimal]]:
        return [(date(2025, 10, 31), D("100")), (date(2026, 9, 30), D(end))]

    series = {"ALPHA": two("130"), "BETA": two("120"), "GAMMA": two("95"), "DELTA": []}
    return {(2026, 11): rank(series, window, 2)}


def trade(day: date, symbol: str, amount: str = "50.00", action: Action = Action.BUY) -> Entry:
    return Entry(day=day, action=action, symbol=symbol, amount=D(amount))


def found(journal: list[Entry], through: date = date(2026, 11, 30)) -> list[tuple[str, str]]:
    method = load_method(MOMENTUM)
    findings = momentum_rules.review(method, PLAN, 2, journal, through, november_ranking())
    return [(f.rule_id, f.message) for f in findings]


def test_the_top_n_in_equal_parts_inside_the_window_has_no_findings() -> None:
    assert found([trade(date(2026, 11, 3), "ALPHA"), trade(date(2026, 11, 3), "BETA")]) == []
    assert momentum_rules.equal_parts(D("100.00"), ["A", "B", "C"]) == [
        ("A", D("33.34")),
        ("B", D("33.33")),
        ("C", D("33.33")),
    ]


def test_each_momentum_rule_is_flagged_with_its_reason() -> None:
    nov3 = date(2026, 11, 3)
    assert found([trade(nov3, "ALPHA"), trade(nov3, "BETA"), trade(nov3, "OTHER")]) == [
        ("candidates-only", "Bought OTHER, which is not a candidate.")
    ]
    assert ("rank-by-12-1", "Bought DELTA, which was not ranked in 2026-11.") in found(
        [trade(nov3, "ALPHA"), trade(nov3, "BETA"), trade(nov3, "DELTA")]
    )
    gamma = found([trade(nov3, "ALPHA"), trade(nov3, "GAMMA")])
    assert ("hold-top-n", "Bought GAMMA, ranked 3rd in 2026-11; the plan holds the top 2.") in gamma
    assert ("hold-top-n", "No buy of BETA in 2026-11; it ranked 2nd.") in gamma
    assert found([trade(nov3, "ALPHA", "60.00"), trade(nov3, "BETA", "40.00")]) == [
        ("equal-weight", "Bought 40.00 of BETA; an equal part of 100.00 over 2 is 50.00."),
        ("equal-weight", "Bought 60.00 of ALPHA; an equal part of 100.00 over 2 is 50.00."),
    ]
    late = found([trade(date(2026, 11, 12), "ALPHA"), trade(date(2026, 11, 12), "BETA")])
    assert late == [
        ("trade-only-at-review", "Bought ALPHA on day 12; the window is days 1 to 7."),
        ("trade-only-at-review", "Bought BETA on day 12; the window is days 1 to 7."),
    ]
    assert found([]) == [("rebalance-each-month", "No rebalance in 2026-11.")]


def test_a_holding_that_left_the_top_n_must_be_sold_and_one_inside_it_kept() -> None:
    october = [trade(date(2026, 10, 2), "GAMMA"), trade(date(2026, 10, 2), "ALPHA")]
    nov = [trade(date(2026, 11, 3), "ALPHA"), trade(date(2026, 11, 3), "BETA")]
    method = load_method(MOMENTUM)
    rankings = november_ranking()

    def sells(journal: list[Entry]) -> list[str]:
        findings = momentum_rules.review(
            method, PLAN, 2, journal, date(2026, 11, 30), rankings, held_since=date(2026, 10, 1)
        )
        return [f.message for f in findings if f.rule_id == "sell-what-leaves"]

    assert sells(october + nov) == [
        "Held GAMMA into 2026-11, ranked 3rd, outside the top 2, and did not sell it."
    ]
    sold = trade(date(2026, 11, 3), "GAMMA", "40.00", Action.SELL)
    assert sells([*october, *nov, sold]) == []
    sold_alpha = trade(date(2026, 11, 3), "ALPHA", "40.00", Action.SELL)
    assert sells([*october, *nov, sold, sold_alpha]) == [
        "Sold ALPHA, still in the top 2 in 2026-11."
    ]


def test_a_month_with_nothing_ranked_is_not_judged_by_rank() -> None:
    method = load_method(MOMENTUM)
    nothing = {(2026, 11): rank({"ALPHA": [], "BETA": []}, Window.for_month(2026, 11), 2)}
    journal = [trade(date(2026, 11, 3), "GAMMA"), trade(date(2026, 11, 3), "DELTA")]
    findings = momentum_rules.review(method, PLAN, 2, journal, date(2026, 11, 30), nothing)
    assert {f.rule_id for f in findings} == set(), "no rank, so no rank findings"


# --- Plans ----------------------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_start_form_lists_both_methods_and_starts_a_momentum_plan(
    owner_client: Client, account: Account
) -> None:
    page = text(owner_client.get(f"/accounts/{account.pk}/method/"))
    assert '<option value="index-dca"' in page and f'<option value="{MOMENTUM}"' in page
    assert "12-1 momentum, monthly top N in equal parts" in page
    assert "Top N to hold" in page
    form = {
        "method_id": MOMENTUM,
        "amount": "100",
        "buy_window_days": "7",
        "symbols": "alpha, beta gamma delta",
        "started_on": "2026-11-01",
        "top_n": "2",
    }
    done = owner_client.post(f"/accounts/{account.pk}/method/start/", form, follow=True)
    plan = MethodPlan.objects.get(account=account)
    assert (plan.method_id, plan.symbols, plan.top_n) == (MOMENTUM, CANDIDATES, 2)
    html = text(done)
    assert "Started 12-1 momentum, monthly top N in equal parts on Practice." in html
    assert "Added to the watch list, so the nightly pull stores their closes: ALPHA, BETA" in html
    watched = WatchItem.objects.filter(account=account).values_list("symbol", flat=True)
    assert sorted(watched) == ["ALPHA", "BETA", "DELTA", "GAMMA"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "method_id, symbols, top_n, message",
    [
        (MOMENTUM, CANDIDATES, "", "12-1 momentum needs a top N: how many candidates to hold."),
        (
            MOMENTUM,
            "ALPHA BETA",
            "2",
            "Name more candidates than the top N: 2 candidates and a top 2",
        ),
        (MOMENTUM, CANDIDATES, "0", "Ensure this value is greater than or equal to 1."),
        ("index-dca", "INDEX", "2", "Leave this empty: index investing holds every fund it names."),
    ],
)
def test_the_start_form_refuses_a_bad_top_n(
    owner_client: Client, account: Account, method_id: str, symbols: str, top_n: str, message: str
) -> None:
    form = {
        "method_id": method_id,
        "amount": "100",
        "buy_window_days": "7",
        "symbols": symbols,
        "started_on": "2026-11-01",
        "top_n": top_n,
    }
    page = text(owner_client.post(f"/accounts/{account.pk}/method/start/", form))
    assert message in page
    assert not MethodPlan.objects.exists()


@pytest.mark.django_db
def test_the_change_form_carries_the_top_n_for_momentum_only(account: Account) -> None:
    plan = momentum_plan(account, date(2026, 11, 1))
    WatchItem.add_many(account, CANDIDATE_LIST)
    base = {
        "what": "change",
        "amount": "100.00",
        "buy_window_days": "7",
        "symbols": CANDIDATES,
        "effective": "next",
        "reason": "Hold three.",
    }
    same = PlanChangeForm(plan, date(2026, 11, 20), {**base, "top_n": "2"})
    assert not same.is_valid()
    assert "the candidates and the top N match" in str(same.errors)
    form = PlanChangeForm(
        plan, date(2026, 11, 20), {**base, "symbols": f"{CANDIDATES} OTHER", "top_n": "3"}
    )
    assert form.is_valid(), form.errors
    version = form.apply()
    assert (version.version, version.top_n, version.started_on) == (2, 3, date(2026, 12, 1))
    assert form.watched == ["OTHER"]
    index = MethodPlan.objects.create(
        account=Account.objects.create(name="Index", broker="B", kind="paper", owner=account.owner),
        method_id="index-dca",
        amount=D("100"),
        buy_window_days=7,
        symbols="INDEX",
        started_on=date(2026, 11, 1),
    )
    assert "top_n" not in PlanChangeForm(index, date(2026, 11, 20)).fields


# --- The engine -----------------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_engine_ranks_each_month_from_stored_adjusted_closes(account: Account) -> None:
    plant_candidates((2026, 11))
    # BETA splits 2-for-1 in 2026-05: the close halves, the adjusted close does not.
    DailyClose.objects.filter(symbol="BETA", date__gte=date(2026, 5, 1)).update(close=D("1"))
    plan = momentum_plan(account, date(2026, 11, 1))
    for symbol in ("ALPHA", "BETA"):
        JournalEntry.objects.create(
            account=account, date=date(2026, 11, 3), action="buy", symbol=symbol, amount=D("50")
        )
    JournalEntry.objects.create(
        account=account, date=date(2026, 12, 4), kind="skip", reason="Practice: read the lesson."
    )
    review = build_review(plan, JournalEntry.entries_for(account), date(2026, 12, 31))
    assert [(row.label, row.status, row.ranking) for row in review.months] == [
        ("2026-11", "done", "ALPHA, BETA"),
        ("2026-12", "skipped", "ALPHA, BETA"),
    ]
    [finding] = review.findings
    assert (finding.rule.id, finding.message, finding.explained) == (
        "rebalance-each-month",
        "No rebalance in 2026-12.",
        True,
    )
    check = next(c for c in review.checks if c.rule.id == "rebalance-each-month")
    assert check.status == "explained"
    assert review.momentum is not None
    ranking = review.momentum.ranking
    assert [p.symbol for p in ranking.places] == ["ALPHA", "BETA", "GAMMA"]
    assert [u.symbol for u in ranking.unranked] == ["DELTA"]
    # GAMMA's closes from the first window's start (2025-10) on, fourteen months, had none.
    assert review.momentum.unadjusted == 14
    assert review.next_action.symbols == ["ALPHA", "BETA"]


@pytest.mark.django_db
def test_an_index_plan_takes_the_path_it_took_before(account: Account) -> None:
    plan = MethodPlan.objects.create(
        account=account,
        method_id="index-dca",
        amount=D("100"),
        buy_window_days=7,
        symbols="INDEX",
        started_on=date(2026, 1, 1),
    )
    review = build_review(plan, [], date(2026, 2, 28))
    assert review.momentum is None
    assert [row.ranking for row in review.months] == ["", ""]
    assert {f.rule.id for f in review.findings} == {"one-buy-each-month"}


@pytest.mark.django_db
def test_the_rebalance_lists_sells_and_warns_of_a_wash_sale(account: Account) -> None:
    plant_candidates((2026, 11))
    plan = momentum_plan(account, date(2026, 10, 1))
    entry = JournalEntry.objects.create
    entry(account=account, date=date(2026, 10, 2), action="buy", symbol="GAMMA", amount=D("50"))
    entry(account=account, date=date(2026, 10, 2), action="buy", symbol="ALPHA", amount=D("50"))
    entry(account=account, date=date(2026, 10, 20), action="sell", symbol="ALPHA", amount=D("40"))
    ranking = ranking_for(plan, (2026, 11), price_series(CANDIDATES.split()))
    planned = rebalance(plan, ranking, date(2026, 11, 3))
    assert planned.parts == [("ALPHA", D("50.00")), ("BETA", D("50.00"))]
    assert planned.sells == ["GAMMA"]
    [warning] = planned.warnings
    assert warning.startswith("You sold ALPHA on 2026-10-20, 14 days before 2026-11-03.")
    assert "wash sale" in warning and "IRS Publication 550" in warning


# --- The pages ------------------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_method_page_shows_the_ranked_bars_with_a_table_and_how_to_read_them(
    owner_client: Client, running: MethodPlan
) -> None:
    account = running.account
    html = text(owner_client.get(f"/accounts/{account.pk}/method/?view=a"))
    month = this_month()
    assert f"The ranking for {month[0]}-{month[1]:02d}" in html
    assert "on adjusted closes." in html and "the latest full month, is left out" in html
    assert html.count('class="rank-bar"') == 3
    assert html.count("bar-out") == 1, "GAMMA, outside the top 2, is an outline"
    assert "How to read this." in html and "Lesson coming." in html
    tables = tables_in(html)
    ranking = next(t for t in tables if t[0][:3] == ("Rank", "Symbol", "12-1 return"))
    assert [(row[0], row[1], row[5]) for row in ranking[1:]] == [
        ("1", "ALPHA", "yes"),
        ("2", "BETA", "yes"),
        ("3", "GAMMA", "no"),
    ]
    assert ranking[3][2].startswith("-")
    assert "DELTA: no close stored in" in html
    assert "Get 5 years of history for DELTA" in html
    assert "Buy $50.00 of ALPHA" in html and "Buy $50.00 of BETA" in html
    assert "stored closes had no adjusted close" in html
    assert "Information, not advice." in html
    for view in ("b", "c"):
        assert "The ranking for" in text(
            owner_client.get(f"/accounts/{account.pk}/method/?view={view}")
        )
    tables = tables_in(text(owner_client.get(f"/accounts/{account.pk}/method/?view=b")))
    months = next(t for t in tables if t[0][0] == "Month")
    assert months[0][-1] == "Top 2"


@pytest.mark.django_db
def test_the_watch_list_shows_a_12_1_badge_only_on_a_momentum_account(
    owner_client: Client, running: MethodPlan
) -> None:
    account = running.account
    WatchItem.add_many(account, CANDIDATE_LIST)
    html = text(owner_client.get(f"/accounts/{account.pk}/"))
    assert '<th scope="col">12-1 return</th>' in html
    assert "▲ up +" in html and "▼ down -" in html
    assert "not ranked" in html
    assert "How to read this." in html
    other = Account.objects.create(name="Index", broker="B", kind="paper", owner=account.owner)
    WatchItem.add_many(other, ["ALPHA"])
    assert "12-1 return" not in text(owner_client.get(f"/accounts/{other.pk}/"))


@pytest.mark.django_db
def test_a_history_chart_shades_the_window_and_labels_the_excluded_month(
    owner_client: Client, running: MethodPlan
) -> None:
    account = running.account
    WatchItem.add_many(account, ["ALPHA"])
    html = text(owner_client.get(f"/accounts/{account.pk}/watch/ALPHA/?days=all"))
    assert 'class="chart-band-window"' in html and 'class="chart-band-excluded"' in html
    assert ">12-1 window</span>" in html and ">excluded</span>" in html
    assert "The 12-1 window for" in html and "How to read this." in html
    window = Window.for_month(*this_month())
    excluded = f"{window.excluded[0]}-{window.excluded[1]:02d}"
    strip = f"The lighter strip with a dashed edge is {excluded}, the latest full month"
    assert f'{strip}, labelled "excluded"' in html
    assert "Show the whole window" in html


@pytest.mark.django_db
def test_the_momentum_pages_are_the_owners_and_no_public_page_shows_them(
    client: Client, someone: User, running: MethodPlan
) -> None:
    account = running.account
    client.force_login(someone)
    assert client.get(f"/accounts/{account.pk}/method/").status_code == 404
    client.logout()
    for path in PUBLIC_PATHS:
        page = text(client.get(path))
        assert "ALPHA" not in page and "rank-bar" not in page and "<table" not in page


# --- Buys on paper --------------------------------------------------------------------------------


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> FakeAlpaca:
    fake = FakeAlpaca()
    monkeypatch.setattr(alpaca, "transport", httpx.MockTransport(fake.handle))
    monkeypatch.setattr(orders, "today", lambda: DAY)
    settings.ALPACA_PAPER_KEY_ID = KEY_ID
    settings.ALPACA_PAPER_SECRET_KEY = SECRET
    return fake


@pytest.mark.django_db
def test_confirm_buys_the_top_n_in_equal_parts_once(
    fake: FakeAlpaca, owner_client: Client, account: Account
) -> None:
    plant_candidates((2026, 10))
    account.alpaca = "paper"
    account.save()
    plan = momentum_plan(account, date(2026, 11, 1), practice_budget=D("1000.00"))
    stage = orders.month_buys(plan, DAY)
    assert [(b.symbol, b.notional) for b in stage.buys] == [
        ("ALPHA", D("50.00")),
        ("BETA", D("50.00")),
    ]
    assert stage.refusal == "" and stage.can_confirm
    page = text(owner_client.get(f"/accounts/{account.pk}/method/"))
    assert "Buy $50.00 of ALPHA" in page and '<button type="submit">Confirm</button>' in page
    owner_client.post(f"/accounts/{account.pk}/paper/confirm/")
    owner_client.post(f"/accounts/{account.pk}/paper/confirm/")
    assert [sent["client_order_id"] for sent in fake.posted] == [
        f"iw-{account.pk}-{plan.pk}-2026-11-ALPHA",
        f"iw-{account.pk}-{plan.pk}-2026-11-BETA",
    ], "one order per top-N symbol, and a second click sends nothing"
    assert PaperOrder.objects.count() == 2
    buys = JournalEntry.objects.filter(account=account).values_list("symbol", "amount")
    assert sorted(buys) == [("ALPHA", D("50.00")), ("BETA", D("50.00"))]


@pytest.mark.django_db
def test_confirm_is_refused_when_nothing_is_ranked(fake: FakeAlpaca, account: Account) -> None:
    account.alpaca = "paper"
    account.save()
    plan = momentum_plan(account, date(2026, 11, 1), practice_budget=D("1000.00"))
    stage = orders.month_buys(plan, DAY)
    assert stage.buys == []
    assert stage.refusal.startswith("No candidate is ranked for 2026-11")
    with pytest.raises(orders.ConfirmRefused):
        orders.confirm(plan, DAY, alpaca.paper_client())
    assert fake.posted == []
```

Things to notice:

- **Every price is planted.** `closes` writes one close a month that grows by a fixed rate, so the ranking is
  known before the test runs: ALPHA rises 2% a month, BETA 1%, GAMMA falls 1%, and DELTA has six months, too few
  to rank. The symbols are placeholders, and so are the prices.
- **The math tests need no database.** The window, the month-end close, the return, the ranking and the bars take
  plain lists, the way chapter 01's tests took plain numbers.
- **The month-end test shuffles its input.** A month-end close that depended on the order the rows arrived would
  pass with sorted rows and fail on a real query someday.
- **One rule at a time.** `found` runs the second rule set on a hand-made ranking, and each test plants exactly one
  mistake.
- **Dates relative to today, where the page reads today.** The method page and the watch list read the clock, so
  `running` plants prices through last month, whatever month you run it in.
- **The paper fake is chapter 11's,** imported, with the day fixed on November 3, 2026.

Run the tests:

Listing 14-3, Terminal:

```sh
uv run pytest tests/test_ch14.py
```

```text
tests/test_ch14.py:23: in <module>
    from invest_witus.adherence import momentum as momentum_rules
E   ImportError: cannot import name 'momentum' from 'invest_witus.adherence' (.../src/invest_witus/adherence/__init__.py)
=========================== short test summary info ============================
ERROR tests/test_ch14.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.88s ===============================
```

Red at import. No package is added this chapter.

### 14.2 The rules file

Listing 14-4, Filename: `src/invest_witus/methods/momentum_12_1.toml`:

```toml
# 12-1 momentum, monthly top N in equal parts, written as rules the app checks (chapter 14).
# The Learn.WitUS lesson and the code read this same file. A rule's `lesson` is the URL of the
# lesson that teaches it; leave it empty until that lesson is published. Never guess a URL.
# The ideas behind the method are cited in chapter 14 (Gray & Vogel, 2016); nothing here is copied.

id = "momentum-12-1"
name = "12-1 momentum, monthly top N in equal parts"
version = 1
summary = "Each month, rank your own candidates by their return over the past year without its latest month, put the month's amount into the top N in equal parts, and sell a holding once it leaves the top N."
lesson = ""

[[rules]]
id = "candidates-only"
text = "Rank and buy only the candidates your plan names: the list is chosen before the ranking, never after it."
lesson = ""

[[rules]]
id = "rank-by-12-1"
text = "Rank the candidates by their 12-1 return: the change in adjusted close from the end of the month 13 months back to the end of the month 2 months back, so the latest full month is left out. A candidate without a close in both of those months (12 months of history or more) is not ranked and not bought."
lesson = ""

[[rules]]
id = "hold-top-n"
text = "Hold the top N: at each rebalance, buy every candidate ranked in the top N and none ranked below. With fewer than N ranked, hold those."
lesson = ""

[[rules]]
id = "equal-weight"
text = "Split the month's amount equally across the symbols you buy, to the cent: the amount divided by N, or by the number ranked when fewer than N are."
lesson = ""

[[rules]]
id = "sell-what-leaves"
text = "Sell the whole holding of a symbol at the first rebalance after it leaves the top N, and sell nothing that is still in it."
lesson = ""

[[rules]]
id = "rebalance-each-month"
text = "Rebalance once in every month of the plan."
lesson = ""

[[rules]]
id = "trade-only-at-review"
text = "Trade only at the monthly rebalance, within the plan's window at the start of the month, not when the news makes you feel ready."
lesson = ""
```

Chapter 10's `available_methods()` lists every `.toml` file in the package, so this file is the second option in
the start form with no other change. It also breaks one earlier test, on purpose:
`test_the_package_lists_its_methods_and_the_rules_file_still_matches_the_checks` in `tests/test_ch10.py` asserted
the whole list, `["index-dca"]`. That was true at `v10` and is not now. Change its first line to assert membership:

Listing 14-5, Filename: `tests/test_ch10.py` (one line changed):

```python
    # Chapter 14 ships a second method, so this asserts membership, not the whole list.
    assert "index-dca" in [method.id for method in available_methods()]
```

A test that pins a whole list breaks when the list grows by design. Chapter 14's own test pins the list instead,
because this chapter decides what it holds.

### 14.3 The 12-1 math

Listing 14-6, Filename: `src/invest_witus/methods/momentum_12_1.py`:

```python
"""12-1 momentum: the math only. Month-end closes, the 12-1 window, each candidate's return, and
the ranking, all in `Decimal`, from price series the caller supplies. No Django, no files.

A rebalance happens in a month, `M`. Its window runs from the last close of the month 13 months
back (`M-13`) to the last close of the month 2 months back (`M-2`): twelve months measured from
the start of `M`, less the latest full month (`M-1`), which is left out. For a rebalance in
November 2026 that is the end of October 2025 to the end of September 2026, and October 2026 is
the month left out. The series are the caller's choice of value: the app passes adjusted closes,
so a split or a dividend inside the window does not read as a fall.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

type Month = tuple[int, int]

# The window, in months back from the rebalance month: its start, its end, and the month left out.
START_BACK = 13
END_BACK = 2
EXCLUDED_BACK = 1


def add_months(month: Month, count: int) -> Month:
    """`(2026, 1)` plus `-2` is `(2025, 11)`."""
    index = month[0] * 12 + (month[1] - 1) + count
    return index // 12, index % 12 + 1


def month_text(month: Month) -> str:
    return f"{month[0]}-{month[1]:02d}"


def month_ends(closes: Iterable[tuple[date, Decimal]]) -> dict[Month, tuple[date, Decimal]]:
    """The last stored close of every month that has one: `{(2026, 9): (date(2026, 9, 30), 101)}`.
    The month-end close is the latest day in the series inside the calendar month, whatever day
    of the month that is; a month with no close is absent, never filled from a neighbor."""
    ends: dict[Month, tuple[date, Decimal]] = {}
    for day, close in closes:
        month = (day.year, day.month)
        if month not in ends or day > ends[month][0]:
            ends[month] = (day, close)
    return ends


@dataclass(frozen=True, slots=True)
class Window:
    """The months a rebalance in `rebalance` reads: the close at the end of `start`, the close at
    the end of `end`, and `excluded`, the latest full month, which is left out."""

    rebalance: Month
    start: Month
    end: Month
    excluded: Month

    @classmethod
    def for_month(cls, year: int, month: int) -> Window:
        rebalance = (year, month)
        return cls(
            rebalance=rebalance,
            start=add_months(rebalance, -START_BACK),
            end=add_months(rebalance, -END_BACK),
            excluded=add_months(rebalance, -EXCLUDED_BACK),
        )

    @property
    def needs(self) -> str:
        """The two months a candidate must have a close in, in words."""
        return f"a close in {month_text(self.start)} and in {month_text(self.end)}"


@dataclass(frozen=True, slots=True)
class Score:
    """One candidate's 12-1 return: `end_close / start_close - 1`, exact to `Decimal`'s precision.
    0.125 is a 12.5 percent rise over the window."""

    symbol: str
    start_day: date
    start_close: Decimal
    end_day: date
    end_close: Decimal

    @property
    def change(self) -> Decimal:
        return self.end_close / self.start_close - 1

    @property
    def up(self) -> bool:
        return self.change > 0


@dataclass(frozen=True, slots=True)
class Unranked:
    """A candidate the window cannot score, and why, in a sentence."""

    symbol: str
    reason: str


def score(symbol: str, closes: Iterable[tuple[date, Decimal]], window: Window) -> Score | Unranked:
    """The candidate's 12-1 return over `window`, or the reason there is none: a month without a
    close, or a close of zero or less (which no return can be divided by)."""
    ends = month_ends(closes)
    missing = [month_text(m) for m in (window.start, window.end) if m not in ends]
    if missing:
        return Unranked(
            symbol, f"no close stored in {' or '.join(missing)}; the window needs {window.needs}"
        )
    start_day, start_close = ends[window.start]
    end_day, end_close = ends[window.end]
    if start_close <= 0 or end_close <= 0:
        return Unranked(symbol, "a close of zero or less in the window")
    return Score(symbol, start_day, start_close, end_day, end_close)


@dataclass(frozen=True, slots=True)
class Place:
    """One ranked candidate: its place (1 is the highest return), its score, whether it is in the
    top N, and whether another candidate has exactly the same return."""

    rank: int
    score: Score
    top: bool
    tied: bool

    @property
    def symbol(self) -> str:
        return self.score.symbol


@dataclass(frozen=True, slots=True)
class Ranking:
    """Every candidate for one rebalance: the ranked ones in order, then the unscored ones."""

    window: Window
    top_n: int
    places: tuple[Place, ...]
    unranked: tuple[Unranked, ...]

    @property
    def ranked(self) -> bool:
        """At least one candidate has a return. With none, the month cannot be judged by rank."""
        return bool(self.places)

    @property
    def top(self) -> list[str]:
        """The symbols to hold, in rank order: the top N, or every ranked one when fewer."""
        return [place.symbol for place in self.places if place.top]

    def place_of(self, symbol: str) -> Place | None:
        return next((place for place in self.places if place.symbol == symbol), None)

    def is_unranked(self, symbol: str) -> bool:
        return any(item.symbol == symbol for item in self.unranked)


def rank(
    series: Mapping[str, Iterable[tuple[date, Decimal]]], window: Window, top_n: int
) -> Ranking:
    """Score every candidate and rank the scored ones, highest return first. Equal returns are
    ordered by symbol, A to Z, so the same prices always give the same order, and each is marked
    `tied`; the top N is the first N places, so a tie across the line is settled by the symbol."""
    if top_n < 1:
        raise ValueError(f"top_n must be at least 1, got {top_n}")
    scores: list[Score] = []
    unranked: list[Unranked] = []
    for symbol in sorted(series):
        result = score(symbol, series[symbol], window)
        if isinstance(result, Score):
            scores.append(result)
        else:
            unranked.append(result)
    scores.sort(key=lambda s: (-s.change, s.symbol))
    changes = [s.change for s in scores]
    places = tuple(
        Place(rank=index + 1, score=s, top=index < top_n, tied=changes.count(s.change) > 1)
        for index, s in enumerate(scores)
    )
    return Ranking(window, top_n, places, tuple(unranked))
```

Things to notice:

- **Months as `(year, month)` tuples.** `add_months` turns a month into a count of months since year zero, adds,
  and turns it back, so January minus two is November of the year before without a special case.
- **`month_ends` keeps the latest day per month,** comparing days, so the order of the input does not matter.
- **`score` returns a `Score` or an `Unranked`,** never `None`: a candidate that cannot be ranked carries its
  reason to the page.
- **The sort key is `(-change, symbol)`.** Negating a `Decimal` sorts highest first; the symbol settles a tie the
  same way every time. `tied` is computed after, so the page can say so.
- **`change` is a property, not a stored field,** so the ranking and the page divide the same two numbers.

### 14.4 The second rule set

Listing 14-7, Filename: `src/invest_witus/adherence/momentum.py`:

```python
"""The monthly review for 12-1 momentum: every place the journal breaks that method's rules.

Chapter 03's `review` checks index investing and stays as it was. This is the second rule set, in
the same shape: a set of the rule ids it checks (a test keeps it equal to the TOML file's), and a
function from the method, the plan, the journal and the review date to a sorted list of
`Finding`s. The one thing it needs that chapter 03 did not is the ranking of each month, which
the caller computes from prices with `invest_witus.methods.momentum_12_1.rank` and passes in.

A month whose ranking is missing, or ranks nothing (no candidate has both closes stored), is not
judged by rank: the checks that need a rank are skipped for it, and the page says why. The app
never flags a buy because the app lacks the prices.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from invest_witus.adherence.journal import Action, Entry
from invest_witus.adherence.plan import Plan
from invest_witus.adherence.review import Finding, months_due
from invest_witus.methods.momentum_12_1 import Month, Ranking, month_text
from invest_witus.methods.rulebook import Method
from invest_witus.money import CENT, to_money

# The rule ids this module checks. A test keeps this set and the method's TOML file in step.
CHECKED_RULES = frozenset(
    {
        "candidates-only",
        "rank-by-12-1",
        "hold-top-n",
        "equal-weight",
        "sell-what-leaves",
        "rebalance-each-month",
        "trade-only-at-review",
    }
)
# The rule a skip with its reason can explain: a month with no trade (chapter 12's idea).
MISSED_MONTH = "rebalance-each-month"

# `flag` inside `review`: a day, a rule id and a message.
type FlagFunction = Callable[[date, str, str], None]


def equal_part(amount: Decimal, count: int) -> Decimal:
    """The amount over `count` symbols, unrounded: 100.00 over 3 is 33.333... A buy within a cent
    of it follows the rule, so 33.34 and 33.33 both do."""
    return amount / count


def equal_parts(amount: Decimal, symbols: list[str]) -> list[tuple[str, Decimal]]:
    """The amount in equal parts to the cent, one per symbol in rank order; the cents that do not
    divide go one each to the first symbols, so the parts add up exactly: 100.00 over three is
    33.34, 33.33 and 33.33 (chapter 11's split, which the paper orders use)."""
    if not symbols:
        return []
    cents = int(to_money(amount) / CENT)
    each, left_over = divmod(cents, len(symbols))
    return [(s, (each + (1 if i < left_over else 0)) * CENT) for i, s in enumerate(symbols)]


def ordinal(number: int) -> str:
    endings = {1: "st", 2: "nd", 3: "rd"}
    suffix = "th" if 10 <= number % 100 <= 20 else endings.get(number % 10, "th")
    return f"{number}{suffix}"


@dataclass(frozen=True, slots=True)
class Holdings:
    """What the journal says was held at the start of a month: every symbol whose latest trade
    before the month was a buy. A sale ends a holding, because the method sells it whole."""

    symbols: frozenset[str]

    @classmethod
    def before(cls, journal: list[Entry], month: Month, since: date) -> Holdings:
        first = date(month[0], month[1], 1)
        last_action: dict[str, Action] = {}
        for entry in sorted(journal, key=lambda e: e.day):
            if since <= entry.day < first:
                last_action[entry.symbol] = entry.action
        return cls(frozenset(s for s, action in last_action.items() if action is Action.BUY))


def review(
    method: Method,
    plan: Plan,
    top_n: int,
    journal: list[Entry],
    through: date,
    rankings: Mapping[Month, Ranking],
    held_since: date | None = None,
) -> list[Finding]:
    """Every finding from the plan's start through `through`. `rankings` holds the ranking of each
    month by its rebalance month; `held_since` is where holdings start counting (the first
    version's start, so a holding bought under version 1 is still held under version 2)."""
    findings: list[Finding] = []

    def flag(day: date, rule_id: str, message: str) -> None:
        findings.append(Finding(day, rule_id, message, method.lesson_for(rule_id)))

    entries = [e for e in journal if plan.start <= e.day <= through]
    for entry in entries:
        if entry.day.day > plan.buy_window_days:
            what = "Bought" if entry.action is Action.BUY else "Sold"
            flag(
                entry.day,
                "trade-only-at-review",
                f"{what} {entry.symbol} on day {entry.day.day}; the window is days 1 to "
                f"{plan.buy_window_days}.",
            )
        if entry.action is Action.BUY and entry.symbol not in plan.symbols:
            flag(entry.day, "candidates-only", f"Bought {entry.symbol}, which is not a candidate.")

    for month in months_due(plan, through):
        first = date(month[0], month[1], 1)
        in_month = [e for e in entries if (e.day.year, e.day.month) == month]
        if not in_month:
            flag(first, MISSED_MONTH, f"No rebalance in {month_text(month)}.")
            continue
        ranking = rankings.get(month)
        buys = [e for e in in_month if e.action is Action.BUY]
        divisor = top_n
        if ranking is not None and ranking.ranked:
            check_ranks(flag, plan, ranking, buys, month, top_n)
            divisor = len(ranking.top)
            held = Holdings.before(journal, month, held_since or plan.start).symbols
            check_sells(flag, ranking, in_month, held, month, top_n)
        part = equal_part(plan.amount, divisor)
        for buy in buys:
            if buy.symbol in plan.symbols and abs(buy.amount - part) >= CENT:
                flag(
                    buy.day,
                    "equal-weight",
                    f"Bought {buy.amount:.2f} of {buy.symbol}; an equal part of "
                    f"{plan.amount:.2f} over {divisor} is {to_money(part):.2f}.",
                )

    return sorted(findings, key=lambda f: (f.day, f.rule_id, f.message))


def check_ranks(
    flag: FlagFunction,
    plan: Plan,
    ranking: Ranking,
    buys: list[Entry],
    month: Month,
    top_n: int,
) -> None:
    """A buy of a candidate the window could not score, a buy ranked below the top N, and, in a
    month that had a buy, a top-N candidate that got none."""
    label = month_text(month)
    for buy in buys:
        if buy.symbol not in plan.symbols:
            continue
        if ranking.is_unranked(buy.symbol):
            flag(buy.day, "rank-by-12-1", f"Bought {buy.symbol}, which was not ranked in {label}.")
            continue
        place = ranking.place_of(buy.symbol)
        if place is not None and not place.top:
            flag(
                buy.day,
                "hold-top-n",
                f"Bought {buy.symbol}, ranked {ordinal(place.rank)} in {label}; the plan holds "
                f"the top {top_n}.",
            )
    if not buys:
        return
    bought = {buy.symbol for buy in buys}
    first = date(month[0], month[1], 1)
    for symbol in ranking.top:
        if symbol not in bought:
            place = ranking.place_of(symbol)
            rank = ordinal(place.rank) if place is not None else "top"
            flag(first, "hold-top-n", f"No buy of {symbol} in {label}; it ranked {rank}.")


def check_sells(
    flag: FlagFunction,
    ranking: Ranking,
    in_month: list[Entry],
    held: frozenset[str],
    month: Month,
    top_n: int,
) -> None:
    """A holding that left the top N and was not sold this month, and a sale of a top-N symbol."""
    label = month_text(month)
    sold = {e.symbol for e in in_month if e.action is Action.SELL}
    top = set(ranking.top)
    first = date(month[0], month[1], 1)
    for symbol in sorted(held - top - sold):
        place = ranking.place_of(symbol)
        where = f"ranked {ordinal(place.rank)}" if place is not None else "not ranked"
        flag(
            first,
            "sell-what-leaves",
            f"Held {symbol} into {label}, {where}, outside the top {top_n}, and did not sell it.",
        )
    for entry in in_month:
        if entry.action is Action.SELL and entry.symbol in top:
            flag(
                entry.day,
                "sell-what-leaves",
                f"Sold {entry.symbol}, still in the top {top_n} in {label}.",
            )
```

Listing 14-8, Filename: `src/invest_witus/adherence/rule_sets.py`:

```python
"""Which module checks which method: one set of checked rule ids per method id.

Chapter 03 wrote one rule set (`review.CHECKED_RULES`, index investing). Chapter 14 adds the
second (`momentum.CHECKED_RULES`). A test walks every method the package ships and asserts its
TOML file's rule ids equal its set here, so a rules file without checks, or a check without a
rule, fails the suite.
"""

from invest_witus.adherence import momentum, review

CHECKED_RULES: dict[str, frozenset[str]] = {
    "index-dca": review.CHECKED_RULES,
    "momentum-12-1": momentum.CHECKED_RULES,
}
```

Things to notice:

- **The same shape as chapter 03.** A frozen set of ids, a `Finding` per break with its lesson, sorted by day.
  Chapter 03's module is imported for `Finding` and `months_due`, and not changed.
- **The rankings are an argument.** The rule set never reads a price. Whoever calls it decides where the prices
  come from: planted lists in the tests, stored closes on the web.
- **A month with nothing ranked skips the rank checks.** Without that guard, a candidate whose prices were never
  fetched would turn every buy into a finding.
- **`Holdings.before` reads the journal,** not the broker: a symbol whose latest trade before the month was a buy.
  The method sells a holding whole, so one sale ends it.
- **`equal_parts` is chapter 11's split,** written once more here so the library needs nothing from the web app.

### 14.5 The plan's top N

Listing 14-9, Filename: `src/invest_witus_site/methods/models.py`:

```python
"""The method an account runs, and the journal the review reads: two tables, both thin.

A `MethodPlan` is chapter 03's `Plan` as a row: the method's id, the amount, the buy window, the
symbols and the start date, for one account. The method's rules are NOT in the row. They come from
the TOML file that ships in `invest_witus.methods` through `load_method(method_id)` at request
time, so a rule's text or lesson link changes with the package and no row goes stale, and a rule
without a published lesson reads "lesson coming" because the file says so, never because a column
was left empty. A `JournalEntry` is chapter 03's `Entry` as a row: one buy or sell, with the
shares if known and a note. Both convert to the chapter 03 values (`to_plan`, `to_entry`), so
`adherence.review.review` runs on the web exactly as it ran on the command line.

Chapter 12 turns the journal into a logbook and the plan into a history. An entry has a kind: a
trade (buy or sell, as before), a hold or a skip, each of the last two with a required reason; any
entry may carry a reason, a state of mind from a short fixed list, and tags. A plan changes by
becoming a new row, a *version*, that points at the one it replaced, so every month is judged by
the numbers in force that month. And each month whose window has closed gets a `MonthlyReview`,
closed by the owner with a short written review; a closed month's entries are read-only until the
review is reopened with a reason, and every close and reopen is kept as a `ReviewEvent`.

Chapter 14 adds a second method, 12-1 momentum, with one more number on the plan: `top_n`, how
many of the ranked candidates to hold. The candidates are the plan's `symbols`, and `amount` is the
month's money, split equally across the top N. An index plan leaves `top_n` empty.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from invest_witus.adherence.journal import Action, Entry
from invest_witus.adherence.plan import Plan
from invest_witus.methods.rulebook import Method, UnknownMethodError, load_method
from invest_witus.money import to_money, to_shares
from invest_witus_site.holdings.models import MONEY_PLACES, SHARE_PLACES, Account
from invest_witus_site.holdings.templatetags import holdings_extras
from invest_witus_site.watchlist.models import normalize_symbol, parse_symbols, validate_symbol

# Chapter 03's rule for a plan file, kept here for the form and `full_clean`: a buy window is a
# day of the month that every month has.
MIN_WINDOW_DAYS = 1
MAX_WINDOW_DAYS = 28
# The smallest amount a plan or an entry can carry: one cent. The form says so beside the box.
ONE_CENT = Decimal("0.01")
# Chapter 14: the method whose plan carries a top N. The id is the TOML file's.
MOMENTUM = "momentum-12-1"


def validate_method_id(value: str) -> None:
    """The id must name a rules file the package ships. Never a free text: a plan for a method
    that has no rules could not be reviewed."""
    try:
        load_method(value)
    except UnknownMethodError:
        raise ValidationError(f"unknown method {value!r}") from None


def validate_symbol_list(value: str) -> None:
    """The stored list is symbols separated by spaces, each inside chapter 09's rule."""
    parsed = parse_symbols(value)
    if parsed.refused:
        reasons = "; ".join(f"{token} ({reason})" for token, reason in parsed.refused)
        raise ValidationError(f"Not a symbol: {reasons}.")
    if not parsed.symbols:
        raise ValidationError("Name at least one symbol.")


def join_symbols(text: str) -> str:
    """The list as it is stored: each symbol normalized, once, in the order typed, joined by
    single spaces. A refused token raises, as `normalize_symbol` does, so no caller stores one."""
    parsed = parse_symbols(text)
    if parsed.refused:
        token, reason = parsed.refused[0]
        raise ValueError(f"{token}: {reason}")
    if not parsed.symbols:
        raise ValueError("empty")
    return " ".join(parsed.symbols)


class MethodPlan(models.Model):
    """One account running one method with the person's own numbers. At most one is active per
    account (a partial unique constraint); an ended plan stays as history with `active` off.

    Chapter 12: a row is one *version* of a plan. Changing the amount, the window or the symbols
    makes a new row that points at the old one through `previous`, starts on the first day of a
    month, and becomes the active row; the old row keeps its numbers, gets `ended_on`, and goes
    on judging the months it was in force. Ending a plan sets `ended_on` and `end_reason`."""

    account: models.ForeignKey[Account, Account] = models.ForeignKey(
        Account, on_delete=models.CASCADE
    )
    method_id: models.CharField[str, str] = models.CharField(
        max_length=40,
        validators=[validate_method_id],
        help_text="The id of a rules file the package ships, such as index-dca.",
    )
    amount: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=14,
        decimal_places=MONEY_PLACES,
        validators=[MinValueValidator(ONE_CENT)],
        help_text="What the method buys each time.",
    )
    buy_window_days: models.PositiveSmallIntegerField[int, int] = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(MIN_WINDOW_DAYS)],
        help_text="Buy within the first N days of each month, 1 to 28.",
    )
    symbols: models.CharField[str, str] = models.CharField(
        max_length=200,
        validators=[validate_symbol_list],
        help_text="The fund or funds the plan names, separated by spaces.",
    )
    started_on: models.DateField[date, date] = models.DateField(
        help_text="The plan's first month; earlier trades are not reviewed."
    )
    active: models.BooleanField[bool, bool] = models.BooleanField(default=True)
    created_at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now_add=True)
    # Chapter 11: the practice money the plan may spend, kept by the app. Alpaca's paper balance
    # cannot be set (research 05), so the plan's budget is this number, not Alpaca's cash.
    practice_budget: models.DecimalField[Decimal | None, Decimal | None] = models.DecimalField(
        max_digits=14,
        decimal_places=MONEY_PLACES,
        null=True,
        blank=True,
        validators=[MinValueValidator(ONE_CENT)],
        help_text="Practice money this plan may spend on a paper account. Empty: not set.",
    )
    # Chapter 12: the plan's history. Every new column has a database default (`db_default`) as
    # well as Django's, so a row written by the previous release's code, which does not know the
    # column, is still valid while the migration workflow runs.
    version: models.PositiveSmallIntegerField[int, int] = models.PositiveSmallIntegerField(
        default=1, db_default=1, help_text="1 for the plan as started; one more for each change."
    )
    previous: models.OneToOneField[MethodPlan | None, MethodPlan | None] = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="next_version",
        help_text="The version this one replaced.",
    )
    change_reason: models.TextField[str, str] = models.TextField(
        blank=True, default="", db_default="", help_text="Why this version replaced the last."
    )
    ended_on: models.DateField[date | None, date | None] = models.DateField(
        null=True, blank=True, help_text="The last day this version was in force."
    )
    end_reason: models.TextField[str, str] = models.TextField(
        blank=True, default="", db_default="", help_text="Why the plan was ended."
    )
    # Chapter 14: how many of the ranked candidates a 12-1 momentum plan holds. Nullable, so the
    # column is additive (old rows and the previous release's inserts are NULL), and an index
    # plan, which holds every fund it names, leaves it empty.
    top_n: models.PositiveSmallIntegerField[int | None, int | None] = (
        models.PositiveSmallIntegerField(
            null=True,
            blank=True,
            validators=[MinValueValidator(1)],
            help_text="12-1 momentum only: how many of the ranked candidates to hold.",
        )
    )

    class Meta:
        ordering = ["account", "-started_on", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["account"],
                condition=Q(active=True),
                name="one_active_plan_per_account",
            ),
            models.CheckConstraint(
                condition=Q(buy_window_days__gte=MIN_WINDOW_DAYS)
                & Q(buy_window_days__lte=MAX_WINDOW_DAYS),
                name="buy_window_between_1_and_28",
            ),
        ]
        verbose_name = "method plan"
        verbose_name_plural = "method plans"

    def __str__(self) -> str:
        return f"{self.method_id} on {self.account}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Normalize before the row is written, as every table in this app does: the amount to
        cents, the symbols through chapter 09's rule, a float refused, an unknown method refused."""
        for field in ("amount", "practice_budget"):
            if isinstance(getattr(self, field), float):
                raise TypeError(f"{field} must be a Decimal, not a float")
        validate_method_id(self.method_id)
        self.amount = to_money(self.amount)
        if self.practice_budget is not None:
            self.practice_budget = to_money(self.practice_budget)
        self.symbols = join_symbols(self.symbols)
        super().save(*args, **kwargs)

    @classmethod
    def active_for(cls, account: Account) -> MethodPlan | None:
        return cls.objects.filter(account=account, active=True).first()

    def method(self) -> Method:
        """The rules, read from the package now, never copied into the row."""
        return load_method(self.method_id)

    def symbol_list(self) -> list[str]:
        return self.symbols.split()

    @property
    def is_momentum(self) -> bool:
        return self.method_id == MOMENTUM

    def to_plan(self) -> Plan:
        """Chapter 03's `Plan`, so `review` runs unchanged."""
        return Plan(
            method=self.method_id,
            start=self.started_on,
            amount=self.amount,
            symbols=frozenset(self.symbol_list()),
            buy_window_days=self.buy_window_days,
        )

    def versions(self) -> list[MethodPlan]:
        """Every version up to this one, oldest first, by following `previous` back."""
        chain: list[MethodPlan] = [self]
        while chain[-1].previous is not None:
            chain.append(chain[-1].previous)
        return chain[::-1]

    def latest_version(self) -> MethodPlan:
        """The newest version of the plan this row belongs to, by following the chain forward."""
        latest = self
        while (following := MethodPlan.objects.filter(previous=latest).first()) is not None:
            latest = following
        return latest

    def chain_start(self) -> date:
        """The first day of the first version: where the plan's practice budget began."""
        return self.versions()[0].started_on

    def in_force(self, day: date) -> MethodPlan:
        """The version that judges `day`: the newest whose span has begun, else the first one
        (the plan has not started yet)."""
        spans = version_spans(self.versions())
        begun = [span.plan for span in spans if span.first <= day]
        return begun[-1] if begun else (spans[0].plan if spans else self)


@dataclass(frozen=True, slots=True)
class Span:
    """One version and the days it judges: from its start through `last`, or open-ended."""

    plan: MethodPlan
    first: date
    last: date | None


def version_spans(versions: list[MethodPlan]) -> list[Span]:
    """Each version runs from its start to the day before the next version starts; the newest
    runs to its `ended_on`, or on. A version replaced before it started (a change scheduled for
    next month, then changed again) has no days, and is left out."""
    spans: list[Span] = []
    for index, version in enumerate(versions):
        if index + 1 < len(versions):
            last: date | None = versions[index + 1].started_on - timedelta(days=1)
        else:
            last = version.ended_on
        if last is None or last >= version.started_on:
            spans.append(Span(version, version.started_on, last))
    return spans


# The choices for an entry's action come from chapter 03's enum, so the two cannot drift: a value
# the review does not know cannot be stored.
ACTION_CHOICES = [(action.value, action.value.capitalize()) for action in Action]

# Chapter 12: what an entry is. A trade is chapter 10's row (a buy or a sell); a hold and a skip
# are decisions not to trade, and each needs a reason. Plain strings, not `TextChoices`, so the
# constants read as strings everywhere (chapter 11's note on pyright and choices).
TRADE = "trade"
HOLD = "hold"
SKIP = "skip"
KIND_CHOICES = [(TRADE, "Trade (a buy or a sell)"), (HOLD, "Hold"), (SKIP, "Skip")]
DECISIONS = frozenset({HOLD, SKIP})
# The state of mind an entry may record: a short fixed list, chosen in decisions row 104. Empty
# means not recorded. Each word describes the person at the moment of the entry, never the market.
STATE_CHOICES = [
    ("", "Not recorded"),
    ("calm", "Calm"),
    ("focused", "Focused"),
    ("confident", "Confident"),
    ("unsure", "Unsure"),
    ("stressed", "Stressed"),
    ("rushed", "Rushed"),
]
# Tags: up to five short words of the owner's own, lower case, letters, digits and hyphens.
MAX_TAGS = 5
TAG = re.compile(r"[a-z0-9][a-z0-9-]{0,23}")
REASON_MAX_LENGTH = 1000


def parse_tags(text: str) -> list[str]:
    """`"Late, news  late"` becomes `["late", "news"]`, or a `ValueError` naming the problem."""
    tags: list[str] = []
    for token in text.replace(",", " ").lower().split():
        if TAG.fullmatch(token) is None:
            raise ValueError(
                f"{token!r} is not a tag: letters, digits and hyphens, 24 characters at most"
            )
        if token not in tags:
            tags.append(token)
    if len(tags) > MAX_TAGS:
        raise ValueError(f"{len(tags)} tags; the most is {MAX_TAGS}")
    return tags


def validate_tags(value: str) -> None:
    try:
        parse_tags(value)
    except ValueError as error:
        raise ValidationError(str(error)) from None


def month_of(day: date) -> str:
    return f"{day.year}-{day.month:02d}"


class JournalEntry(models.Model):
    """One line of the logbook. Chapter 10's row was a trade the person logged by hand: the day,
    buy or sell, the symbol, the money, and the shares if the confirmation showed them. Chapter 12
    adds the kind (a hold or a skip is a decision with a reason, and has no amount), the reason,
    the state of mind and the tags."""

    account: models.ForeignKey[Account, Account] = models.ForeignKey(
        Account, on_delete=models.CASCADE
    )
    date: models.DateField[date, date] = models.DateField(help_text="The day it happened.")
    kind: models.CharField[str, str] = models.CharField(
        max_length=5, choices=KIND_CHOICES, default=TRADE, db_default=TRADE
    )
    action: models.CharField[str, str] = models.CharField(
        max_length=4,
        choices=ACTION_CHOICES,
        blank=True,
        help_text="Trades only: buy or sell. Leave empty for a hold or a skip.",
    )
    symbol: models.CharField[str, str] = models.CharField(
        max_length=20,
        validators=[validate_symbol],
        blank=True,
        help_text="Trades name one. Optional for a hold or a skip.",
    )
    amount: models.DecimalField[Decimal | None, Decimal | None] = models.DecimalField(
        max_digits=14,
        decimal_places=MONEY_PLACES,
        null=True,
        blank=True,
        validators=[MinValueValidator(ONE_CENT)],
        help_text="Trades only: the money that changed hands.",
    )
    shares: models.DecimalField[Decimal | None, Decimal | None] = models.DecimalField(
        max_digits=18,
        decimal_places=SHARE_PLACES,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="From the confirmation, if shown. Optional.",
    )
    reason: models.TextField[str, str] = models.TextField(
        blank=True,
        default="",
        db_default="",
        max_length=REASON_MAX_LENGTH,
        help_text="Why. Required for a hold or a skip.",
    )
    state: models.CharField[str, str] = models.CharField(
        max_length=10,
        choices=STATE_CHOICES,
        blank=True,
        default="",
        db_default="",
        help_text="How you were when you decided. Optional.",
    )
    tags: models.CharField[str, str] = models.CharField(
        max_length=200,
        blank=True,
        default="",
        db_default="",
        validators=[validate_tags],
        help_text="Up to five words of your own, separated by spaces or commas. Optional.",
    )
    note: models.CharField[str, str] = models.CharField(max_length=200, blank=True, default="")
    created_at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now_add=True)
    # The foreign key's own column, which Django adds; declared so pyright can read it.
    account_id: int | None

    class Meta:
        ordering = ["account", "date", "pk"]
        verbose_name = "journal entry"
        verbose_name_plural = "journal entries"

    def __str__(self) -> str:
        if self.kind == TRADE:
            # The text a "Logged:" or "Saved:" message shows: money as the pages show it (row 113).
            amount = holdings_extras.money(self.amount)
            return f"{self.date:%Y-%m-%d} {self.action} {amount} of {self.symbol}"
        return f"{self.date:%Y-%m-%d} {self.kind}{f' {self.symbol}' if self.symbol else ''}"

    @property
    def is_trade(self) -> bool:
        return self.kind == TRADE

    @property
    def what(self) -> str:
        """The word a table prints: Buy, Sell, Hold or Skip."""
        return (self.action if self.kind == TRADE else self.kind).capitalize()

    @property
    def money(self) -> Decimal:
        """The amount, or zero for a decision with none, for sums."""
        return self.amount if self.amount is not None else Decimal("0")

    def tag_list(self) -> list[str]:
        return self.tags.split()

    def clean(self) -> None:
        """The rules of a line beyond each field's own: a trade is a buy or a sell of a symbol for
        an amount; a hold or a skip has a reason and no money; and nothing is written into a
        month whose review is closed. A `ModelForm` and the admin run this before `save()`."""
        errors: dict[str, str] = {}
        if self.kind == TRADE:
            if self.action not in {action.value for action in Action}:
                errors["action"] = "A trade is a buy or a sell."
            if not self.symbol:
                errors["symbol"] = "A trade names its symbol."
            if self.amount is None:
                errors["amount"] = "A trade has an amount."
        elif self.kind in DECISIONS:
            if not self.reason.strip():
                errors["reason"] = f"A {self.kind} needs a reason: write why, in a sentence."
            if self.action:
                errors["action"] = f"A {self.kind} is not a trade: leave Action empty."
            if self.amount is not None or self.shares is not None:
                errors["amount"] = f"A {self.kind} moves no money: leave Amount and Shares empty."
        if errors:
            raise ValidationError(errors)
        self.refuse_closed_month()

    def refuse_closed_month(self) -> None:
        """A closed month is read-only: a new line dated in it, or a change to a line that was
        dated in it, is refused until its review is reopened with a reason."""
        # An invalid date in a form leaves the field empty, whatever its annotation says.
        day: date | None = getattr(self, "date", None)
        if self.account_id is None or day is None:
            return
        days = {day}
        if self.pk is not None:
            stored = JournalEntry.objects.filter(pk=self.pk).values_list("date", flat=True).first()
            if stored is not None:
                days.add(stored)
        for each in sorted(days):
            if MonthlyReview.is_closed(self.account_id, each):
                raise ValidationError(
                    f"{month_of(each)} is closed. Reopen its review, with a reason, to change it."
                )

    def save(self, *args: Any, **kwargs: Any) -> None:
        """The same guards as a statement line: no float, the symbol's rule, the rounding. A hold
        or a skip without a reason is refused here too, whatever path wrote it."""
        for field in ("amount", "shares"):
            if isinstance(getattr(self, field), float):
                raise TypeError(f"{field} must be a Decimal, not a float")
        if self.kind in DECISIONS and not self.reason.strip():
            raise ValueError(f"a {self.kind} needs a reason")
        if self.symbol:
            self.symbol = normalize_symbol(self.symbol)
        if self.amount is not None:
            self.amount = to_money(self.amount)
        if self.shares is not None:
            self.shares = to_shares(self.shares)
        self.tags = " ".join(parse_tags(self.tags))
        super().save(*args, **kwargs)

    def to_entry(self) -> Entry:
        """Chapter 03's `Entry`, for a trade. `Action(self.action)` raises on a value the enum
        lacks, which the choices and the form make impossible to store. A hold or a skip is not a
        trade, and the review never sees one."""
        if self.kind != TRADE or self.amount is None:
            raise ValueError(f"a {self.kind} is not a trade")
        return Entry(
            day=self.date, action=Action(self.action), symbol=self.symbol, amount=self.amount
        )

    @classmethod
    def entries_for(cls, account: Account) -> list[JournalEntry]:
        """The account's rows in date order, the order `review` and the pages want."""
        return list(cls.objects.filter(account=account))


class MonthlyReview(models.Model):
    """One month of one plan version, opened when the month's buy window closes and closed by the
    owner with three short answers: what I did, what the rules said, what I'll do next month."""

    plan: models.ForeignKey[MethodPlan, MethodPlan] = models.ForeignKey(
        MethodPlan, on_delete=models.PROTECT, related_name="reviews"
    )
    month: models.CharField[str, str] = models.CharField(max_length=7, help_text="YYYY-MM")
    opened_on: models.DateField[date, date] = models.DateField(
        help_text="The day the month's buy window closed."
    )
    did: models.TextField[str, str] = models.TextField(blank=True, default="")
    rules_said: models.TextField[str, str] = models.TextField(blank=True, default="")
    next_month: models.TextField[str, str] = models.TextField(blank=True, default="")
    closed_at: models.DateTimeField[datetime | None, datetime | None] = models.DateTimeField(
        null=True, blank=True
    )
    created_at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["month", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["plan", "month"], name="one_review_per_plan_month")
        ]
        verbose_name = "monthly review"
        verbose_name_plural = "monthly reviews"

    def __str__(self) -> str:
        return f"{self.month} {'closed' if self.closed else 'open'} ({self.plan})"

    @property
    def closed(self) -> bool:
        return self.closed_at is not None

    @classmethod
    def is_closed(cls, account_id: int, day: date) -> bool:
        return cls.objects.filter(
            plan__account_id=account_id, month=month_of(day), closed_at__isnull=False
        ).exists()


class ReviewEvent(models.Model):
    """The audit trail of a review: every close, with what was written, and every reopen, with
    its reason, who did it and when. Rows are only ever added."""

    CLOSED = "closed"
    REOPENED = "reopened"
    ACTIONS = [(CLOSED, "Closed"), (REOPENED, "Reopened")]

    review: models.ForeignKey[MonthlyReview, MonthlyReview] = models.ForeignKey(
        MonthlyReview, on_delete=models.CASCADE, related_name="events"
    )
    action: models.CharField[str, str] = models.CharField(max_length=8, choices=ACTIONS)
    text: models.TextField[str, str] = models.TextField()
    by: models.ForeignKey[Any, Any] = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["at", "pk"]
        verbose_name = "review event"
        verbose_name_plural = "review events"

    def __str__(self) -> str:
        return f"{self.review.month} {self.action} {self.at:%Y-%m-%d %H:%M}"
```

The new column is nullable, which is the additive form of a new column: an old row and an insert from the release
before this one both leave it `NULL`. Make the migration and tidy it:

Listing 14-10, Terminal:

```sh
uv run --env-file .env python manage.py makemigrations methods --name methodplan_top_n
uv run ruff format src/invest_witus_site/methods/migrations/
uv run ruff check --fix src/invest_witus_site/methods/migrations/
```

```text
Migrations for 'methods':
  src/invest_witus_site/methods/migrations/0004_methodplan_top_n.py
    + Add field top_n to methodplan
```

Listing 14-11, Filename: `src/invest_witus_site/methods/migrations/0004_methodplan_top_n.py`:

```python
# Generated by Django 5.2.18 on 2026-10-29 19:20

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("methods", "0003_journal_kinds_plan_versions_and_reviews"),
    ]

    operations = [
        migrations.AddField(
            model_name="methodplan",
            name="top_n",
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text="12-1 momentum only: how many of the ranked candidates to hold.",
                null=True,
                validators=[django.core.validators.MinValueValidator(1)],
            ),
        ),
    ]
```

### 14.6 Prices, rankings and pictures for the web

Listing 14-12, Filename: `src/invest_witus_site/methods/momentum.py`:

```python
"""12-1 momentum on the web: the stored closes as series, each month's ranking, the ranked bar
chart, the month's rebalance, and the watch list's badges (chapter 14).

The math is the library's (`invest_witus.methods.momentum_12_1`); this module only reads rows and
arranges what the pages print. Every value is the stored **adjusted close** where the row has one,
because a split or a dividend inside the window would otherwise read as a fall; a row without one
(a CSV file on a laptop) uses its close, and the page counts how many did. Owner pages only: the
vendor's free plan is for the owner's own use, and no public page shows a price or a return.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from invest_witus.adherence.journal import Action
from invest_witus.adherence.momentum import equal_parts
from invest_witus.methods.momentum_12_1 import (
    Month,
    Place,
    Ranking,
    Score,
    Unranked,
    Window,
    month_text,
    rank,
    score,
)
from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.models import JournalEntry, MethodPlan
from invest_witus_site.prices.models import DailyClose
from invest_witus_site.watchlist.models import WatchItem

HUNDRED = Decimal(100)
# The wash-sale rule's span: a loss sale and a purchase of the same security within 30 days
# before or after it (Internal Revenue Service, Publication 550; PRD 7.1, research 03).
WASH_SALE_DAYS = 30
# The note a candidate gets when the plan adds it to the watch list.
WATCH_NOTE = "A 12-1 momentum candidate"


def percent_text(change: Decimal) -> str:
    """0.1234 as `+12.3%`, -0.05 as `-5.0%`: one place, the sign always written, so the number
    says up or down without the color."""
    value = (change * HUNDRED).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    sign = "+" if value > 0 else ("-" if value < 0 else "")
    return f"{sign}{abs(value)}%"


@dataclass(frozen=True, slots=True)
class PriceSeries:
    """Each symbol's (day, value) pairs, oldest first, and how many rows had no adjusted close."""

    values: dict[str, list[tuple[date, Decimal]]]
    unadjusted: int

    def of(self, symbols: Iterable[str]) -> dict[str, list[tuple[date, Decimal]]]:
        return {symbol: self.values.get(symbol, []) for symbol in symbols}


def price_series(symbols: Iterable[str], since: date | None = None) -> PriceSeries:
    """The stored closes of `symbols` from `since` on: the adjusted close, else the close."""
    wanted = sorted(set(symbols))
    rows = DailyClose.objects.filter(symbol__in=wanted).order_by("symbol", "date")
    if since is not None:
        rows = rows.filter(date__gte=since)
    values: dict[str, list[tuple[date, Decimal]]] = {symbol: [] for symbol in wanted}
    unadjusted = 0
    for symbol, day, close, adjusted in rows.values_list("symbol", "date", "close", "adj_close"):
        if adjusted is None:
            unadjusted += 1
        values[symbol].append((day, close if adjusted is None else adjusted))
    return PriceSeries(values, unadjusted)


def series_since(first_month: Month) -> date:
    """The first day a review from `first_month` reads: the start of its window's first month."""
    start = Window.for_month(*first_month).start
    return date(start[0], start[1], 1)


def ranking_for(plan: MethodPlan, month: Month, series: PriceSeries) -> Ranking:
    """The plan version's candidates ranked for a rebalance in `month`."""
    return rank(series.of(plan.symbol_list()), Window.for_month(*month), plan.top_n or 1)


def plan_ranking(plan: MethodPlan, month: Month) -> Ranking:
    """`ranking_for` with its own query, for a page that needs one month only."""
    series = price_series(plan.symbol_list(), series_since(month))
    return ranking_for(plan, month, series)


# --- The ranked bar chart ------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Bar:
    """One candidate's bar: where it starts and how wide it is, in percent of the track, and the
    words beside it. A bar grows right from the zero line for a rise and left for a fall."""

    place: Place
    x: Decimal
    width: Decimal
    text: str

    @property
    def symbol(self) -> str:
        return self.place.symbol

    @property
    def up(self) -> bool:
        return self.place.score.up

    @property
    def direction(self) -> str:
        change = self.place.score.change
        return "up" if change > 0 else ("down" if change < 0 else "flat")


def place_pct(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True, slots=True)
class BarChart:
    """The bars in rank order and the zero line's place on the track."""

    bars: list[Bar]
    zero_x: Decimal


def bar_chart(ranking: Ranking) -> BarChart | None:
    """A shared scale for every bar: from the lowest return (or 0) to the highest (or 0), so the
    zero line is where the bars meet and the lengths compare. None when nothing is ranked."""
    if not ranking.places:
        return None
    changes = [place.score.change for place in ranking.places]
    low, high = min(min(changes), Decimal(0)), max(max(changes), Decimal(0))
    span = high - low or Decimal(1)
    zero = (0 - low) * HUNDRED / span
    bars: list[Bar] = []
    for place in ranking.places:
        end = (place.score.change - low) * HUNDRED / span
        bars.append(
            Bar(
                place=place,
                x=place_pct(min(zero, end)),
                width=place_pct(max(abs(end - zero), Decimal("0.5"))),
                text=percent_text(place.score.change),
            )
        )
    return BarChart(bars, place_pct(zero))


# --- The month's rebalance ------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Rebalance:
    """What the rules ask for in one month: buy the top N in equal parts, sell the holdings that
    left it, and the wash-sale warnings for buying back something sold within 30 days."""

    month: Month
    buys: list[str]
    sells: list[str]
    warnings: list[str]
    parts: list[tuple[str, Decimal]] = field(default_factory=list[tuple[str, Decimal]])


def held_symbols(account: Account, since: date, before: date) -> set[str]:
    """Symbols whose latest trade in the journal between `since` and `before` was a buy."""
    last: dict[str, str] = {}
    trades = JournalEntry.objects.filter(
        account=account, kind="trade", date__gte=since, date__lt=before
    ).order_by("date", "pk")
    for symbol, action in trades.values_list("symbol", "action"):
        last[symbol] = action
    return {symbol for symbol, action in last.items() if action == Action.BUY.value}


def wash_sale_warnings(account: Account, symbols: list[str], day: date) -> list[str]:
    """One sentence per symbol to buy that the journal shows sold in the 30 days before `day`."""
    since = day - timedelta(days=WASH_SALE_DAYS)
    sales = JournalEntry.objects.filter(
        account=account,
        kind="trade",
        action=Action.SELL.value,
        symbol__in=symbols,
        date__gte=since,
        date__lte=day,
    ).order_by("-date")
    warnings: list[str] = []
    seen: set[str] = set()
    for sale in sales:
        if sale.symbol in seen:
            continue
        seen.add(sale.symbol)
        days = (day - sale.date).days
        warnings.append(
            f"You sold {sale.symbol} on {sale.date:%Y-%m-%d}, {days} day{'' if days == 1 else 's'} "
            f"before {day:%Y-%m-%d}. If that sale was at a loss, buying {sale.symbol} again within "
            f"{WASH_SALE_DAYS} days of it is a wash sale: the loss cannot be deducted then, and is "
            "added to the cost of the new shares instead (IRS Publication 550). A paper account "
            "has no tax effect; a live one would."
        )
    return warnings


def rebalance(plan: MethodPlan, ranking: Ranking, day: date) -> Rebalance:
    month = ranking.window.rebalance
    first = date(month[0], month[1], 1)
    held = held_symbols(plan.account, plan.chain_start(), first)
    top = ranking.top
    sells = sorted(held - set(top)) if ranking.ranked else []
    warnings = wash_sale_warnings(plan.account, top, day)
    return Rebalance(month, top, sells, warnings, equal_parts(plan.amount, top))


# --- What the method page shows -------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MomentumView:
    """The momentum section of the method page: this month's ranking, its bars, the rebalance,
    and how many closes had no adjusted value."""

    ranking: Ranking
    chart: BarChart | None
    rebalance: Rebalance
    unadjusted: int
    top_n: int
    candidates: list[str] = field(default_factory=list[str])

    @property
    def month(self) -> str:
        return month_text(self.ranking.window.rebalance)

    @property
    def window(self) -> Window:
        return self.ranking.window

    @property
    def start(self) -> str:
        return month_text(self.window.start)

    @property
    def end(self) -> str:
        return month_text(self.window.end)

    @property
    def excluded(self) -> str:
        return month_text(self.window.excluded)

    @property
    def unranked_symbols(self) -> list[str]:
        return [item.symbol for item in self.ranking.unranked]


def momentum_view(plan: MethodPlan, today: date, series: PriceSeries) -> MomentumView:
    ranking = ranking_for(plan, (today.year, today.month), series)
    return MomentumView(
        ranking=ranking,
        chart=bar_chart(ranking),
        rebalance=rebalance(plan, ranking, today),
        unadjusted=series.unadjusted,
        top_n=plan.top_n or 1,
        candidates=plan.symbol_list(),
    )


# --- The watch list and the plan's candidates -----------------------------------------------------


def scores_for(symbols: list[str], today: date) -> dict[str, Score | Unranked]:
    """Each symbol's 12-1 return for this month's rebalance, or why there is none: the watch
    list's badges."""
    window = Window.for_month(today.year, today.month)
    series = price_series(symbols, series_since(window.rebalance))
    return {symbol: score(symbol, series.values.get(symbol, []), window) for symbol in symbols}


def ensure_watched(account: Account, symbols: list[str]) -> list[str]:
    """Put each candidate on the account's watch list, so the nightly pull stores its closes,
    and return the symbols that were added (the ones already watched are left as they were)."""
    return WatchItem.add_many(account, symbols, note=WATCH_NOTE).added


@dataclass(frozen=True, slots=True)
class Badge:
    """A watched symbol's 12-1 return as the watch list prints it: an arrow, a word and the
    number, so up and down never rest on color alone; or the words "not ranked" and why."""

    symbol: str
    direction: str
    text: str
    reason: str = ""


def badges_for(symbols: list[str], today: date) -> dict[str, Badge]:
    badges: dict[str, Badge] = {}
    for symbol, result in scores_for(symbols, today).items():
        if isinstance(result, Unranked):
            badges[symbol] = Badge(symbol, "none", "not ranked", result.reason)
            continue
        change = result.change
        direction = "up" if change > 0 else ("down" if change < 0 else "flat")
        arrow = {"up": "▲", "down": "▼", "flat": "◆"}[direction]
        badges[symbol] = Badge(symbol, direction, f"{arrow} {direction} {percent_text(change)}")
    return badges


@dataclass(frozen=True, slots=True)
class HistoryWindow:
    """This month's 12-1 window for one symbol, as dates a chart can shade, with its score."""

    window: Window
    result: Score | Unranked
    first: date
    last: date
    excluded_first: date
    excluded_last: date

    @property
    def start(self) -> str:
        return month_text(self.window.start)

    @property
    def end(self) -> str:
        return month_text(self.window.end)

    @property
    def excluded(self) -> str:
        return month_text(self.window.excluded)

    @property
    def month(self) -> str:
        return month_text(self.window.rebalance)

    @property
    def score(self) -> Score | None:
        return self.result if isinstance(self.result, Score) else None

    @property
    def change_text(self) -> str:
        return percent_text(self.result.change) if isinstance(self.result, Score) else ""


def last_day(month: Month) -> date:
    following = (month[0] + 1, 1) if month[1] == 12 else (month[0], month[1] + 1)
    return date(following[0], following[1], 1) - timedelta(days=1)


def history_window(symbol: str, today: date) -> HistoryWindow:
    """The window for a rebalance this month: shaded from the start close's day (or the end of
    the start month, without one) to the end close's day, and the excluded month in full."""
    window = Window.for_month(today.year, today.month)
    result = scores_for([symbol], today)[symbol]
    if isinstance(result, Score):
        first, last = result.start_day, result.end_day
    else:
        first, last = last_day(window.start), last_day(window.end)
    excluded_first = date(window.excluded[0], window.excluded[1], 1)
    return HistoryWindow(window, result, first, last, excluded_first, last_day(window.excluded))
```

Things to notice:

- **One query per page.** `price_series` reads every candidate's rows from the first window's start, oldest
  first, and the engine ranks every month from that one result.
- **`adj_close` if stored, else `close`,** counted in `unadjusted`, so the page can say so instead of hiding it.
- **`bar_chart` puts every bar on one scale,** from the lowest return or zero to the highest or zero. The zero line
  sits where they meet, and a bar never shrinks below half a percent of the track, so a return of 0.1% still shows.
- **`wash_sale_warnings` reads only the journal,** and words the rule as the IRS states it, without a tax figure.
- **`ensure_watched` reuses chapter 09's `WatchItem.add_many`,** so the symbol rule and the one-row-per-symbol
  constraint apply.

### 14.7 The engine's second path

Listing 14-13, Filename: `src/invest_witus_site/methods/engine.py`:

```python
"""What the method page shows, built once: the plan, its rules with their lessons, the review's
findings, every month of the plan with its status, and the next action.

Chapter 03's `review` is called here exactly as the command line called it, on the values the
two converters in `models.py` produce. Everything else in this module is arrangement: the same
findings grouped by rule for a table, by month for another, and the one sentence that says what
to do next. The three views (A, B and C) render this one `MethodReview`; none of them queries
anything the others do not get.

Chapter 12 adds three things, all arrangement, none a new rule:

- **Versions.** A plan that changed is several rows; each judges only its own months (its span),
  so `review` runs once per version with that version's numbers and the results are joined.
- **Explained misses.** Chapter 03's "No buy in 2026-03" is still a finding of the rule "buy once
  in every month". When the journal has a skip for that month, the skip's reason is attached to
  the finding, the month reads "skipped" instead of "missed", and the rule's status reads
  "explained" when every finding it has is. The rule and `CHECKED_RULES` are unchanged.
- **The count of months followed:** the months due that were done with no finding.

Chapter 14 adds the second method, 12-1 momentum. Its rules are checked by its own rule set,
`invest_witus.adherence.momentum.review`, which needs each month's ranking: this module reads the
candidates' stored closes once (`methods/momentum.py`), ranks every month the review covers, and
passes the rankings in. Everything else is the same arrangement: the spans, the month rows (a
month with any trade is done, since a rebalance may be only a sale), a skip explaining a month
with no trade, and the next action, whose symbols are that month's top N. An index plan takes
exactly the path it took before.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal

from invest_witus.adherence import momentum as momentum_rules
from invest_witus.adherence.journal import Action, Entry
from invest_witus.adherence.plan import Plan
from invest_witus.adherence.review import Finding, months_due, review
from invest_witus.methods.momentum_12_1 import Month, Ranking
from invest_witus.methods.rulebook import LESSON_COMING, Method
from invest_witus_site.methods.models import SKIP, JournalEntry, MethodPlan, Span, version_spans
from invest_witus_site.methods.momentum import (
    MomentumView,
    PriceSeries,
    momentum_view,
    price_series,
    ranking_for,
    series_since,
)

ZERO = Decimal("0")
# The one rule a skip can explain: a month with no buy. The id is the TOML file's.
ONE_BUY = "one-buy-each-month"


@dataclass(frozen=True, slots=True)
class RuleLine:
    """One rule as a page prints it: its id, its text, and the lesson's URL or `None`, which the
    template renders as the words "lesson coming". The URL is the TOML file's, through
    `Method.lesson_for`; nothing here invents one."""

    id: str
    text: str
    lesson_url: str | None


@dataclass(frozen=True, slots=True)
class FindingLine:
    """One finding with the rule it broke and the month it concerns. `explanation` is the reason
    of the skip that explains it, or "" when nothing does."""

    day: date
    month: str
    rule: RuleLine
    message: str
    explanation: str = ""

    @property
    def explained(self) -> bool:
        return bool(self.explanation)


@dataclass(frozen=True, slots=True)
class RuleCheck:
    """One rule's result through the review date: pass with no findings, fail with the list."""

    rule: RuleLine
    findings: list[FindingLine]

    @property
    def status(self) -> str:
        """pass with no findings; explained when every finding has a skip's reason; else fail."""
        if not self.findings:
            return "pass"
        return "explained" if all(f.explained for f in self.findings) else "fail"

    @property
    def months(self) -> str:
        """The months the findings fall in, each once, in order."""
        return ", ".join(sorted({finding.month for finding in self.findings}))

    @property
    def evidence(self) -> str:
        """The fact that decided it, in words: how many findings, and in which months."""
        if not self.findings:
            return "no findings"
        count = len(self.findings)
        explained = sum(1 for finding in self.findings if finding.explained)
        note = f" ({explained} explained)" if explained else ""
        return f"{count} finding{'' if count == 1 else 's'}: {self.months}{note}"


@dataclass(frozen=True, slots=True)
class MonthRow:
    """One month of the plan: the window, what was bought, and whether the month is done,
    missed, skipped (no buy, and a skip with its reason), or still open on the review date.
    `version` is the plan version that judged it."""

    label: str
    window_closes: date
    status: str
    buys: int
    amount: Decimal
    shares: Decimal | None
    rule_ids: list[str]
    version: int = 1
    skip_reason: str = ""
    # Chapter 14: the month's top N in rank order, or why there is none (12-1 momentum only).
    ranking: str = ""


@dataclass(frozen=True, slots=True)
class NextAction:
    """The one thing the method asks for next: a buy in a window, and whether that window is
    open now ("due"), or ahead ("upcoming") because this month's buy is done or missed."""

    label: str
    opens: date
    closes: date
    amount: Decimal
    symbols: list[str]
    status: str


@dataclass(frozen=True, slots=True)
class MethodReview:
    """Everything the three views render, from one plan and one journal."""

    plan: MethodPlan
    method: Method
    rules: list[RuleLine]
    through: date
    entries: list[JournalEntry]
    findings: list[FindingLine]
    checks: list[RuleCheck]
    months: list[MonthRow]
    next_action: NextAction
    spans: list[Span] = field(default_factory=list[Span])
    # Chapter 14: the ranking, the bars and the rebalance; None for an index plan.
    momentum: MomentumView | None = None

    @property
    def on_plan(self) -> bool:
        return not self.findings

    @property
    def unexplained(self) -> list[FindingLine]:
        return [finding for finding in self.findings if not finding.explained]

    @property
    def explained_count(self) -> int:
        return len(self.findings) - len(self.unexplained)

    @property
    def months_followed(self) -> int:
        """Months due that were done as the rules said: a buy, and no finding in the month."""
        return sum(1 for row in self.months if row.status == "done" and not row.rule_ids)

    def month(self, label: str) -> MonthRow | None:
        return next((row for row in self.months if row.label == label), None)

    @property
    def months_done(self) -> int:
        return sum(1 for row in self.months if row.status == "done")

    @property
    def months_due(self) -> int:
        return sum(1 for row in self.months if row.status != "open")


def month_label(year: int, month: int) -> str:
    return f"{year}-{month:02d}"


def rule_lines(method: Method) -> list[RuleLine]:
    """Each rule with its lesson resolved: the rule's own, else the method's, else nothing."""
    lines: list[RuleLine] = []
    for rule in method.rules:
        lesson = method.lesson_for(rule.id)
        lines.append(RuleLine(rule.id, rule.text, None if lesson == LESSON_COMING else lesson))
    return lines


def finding_lines(findings: list[Finding], rules: dict[str, RuleLine]) -> list[FindingLine]:
    return [
        FindingLine(f.day, month_label(f.day.year, f.day.month), rules[f.rule_id], f.message)
        for f in findings
    ]


def rule_checks(rules: list[RuleLine], findings: list[FindingLine]) -> list[RuleCheck]:
    return [RuleCheck(rule, [f for f in findings if f.rule.id == rule.id]) for rule in rules]


def next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def month_rows(
    plan: Plan,
    entries: list[JournalEntry],
    findings: list[FindingLine],
    through: date,
    version: int = 1,
    any_trade: bool = False,
    rankings: Mapping[Month, str] | None = None,
) -> list[MonthRow]:
    """Every month from the plan's start through `through`: the months whose window has closed
    (chapter 03's `months_due`) and, if the review date falls inside a window that is still open,
    that month too, marked open. The rows are the journal's own, not chapter 03's values, because
    the shares column exists only here; the shares total is `None` when any buy in the month
    left shares blank, so a partial total is never printed as a whole. A month with no buy and a
    skip in the journal reads "skipped", with the skip's reason.
    Chapter 14: with `any_trade`, a month with a sale and no buy is done too (a momentum
    rebalance can be a sale alone), and `rankings` gives each month's top N in words."""
    due = months_due(plan, through)
    months = list(due)
    if through >= plan.start:
        current = (through.year, through.month)
        if current not in months and current >= (plan.start.year, plan.start.month):
            months.append(current)
    buys = [e for e in entries if e.action == Action.BUY.value and plan.start <= e.date <= through]
    skips = [e for e in entries if e.kind == SKIP and plan.start <= e.date <= through]
    traded = [e for e in entries if e.is_trade and plan.start <= e.date <= through]
    rows: list[MonthRow] = []
    for year, month in months:
        label = month_label(year, month)
        in_month = [b for b in buys if (b.date.year, b.date.month) == (year, month)]
        skipped = [s for s in skips if (s.date.year, s.date.month) == (year, month)]
        done = bool(in_month) or (
            any_trade and any((t.date.year, t.date.month) == (year, month) for t in traded)
        )
        if done:
            status = "done"
        elif skipped:
            status = "skipped"
        elif (year, month) in due:
            status = "missed"
        else:
            status = "open"
        shares: Decimal | None = None
        if in_month and all(b.shares is not None for b in in_month):
            shares = sum((b.shares for b in in_month if b.shares is not None), ZERO)
        rows.append(
            MonthRow(
                label=label,
                window_closes=date(year, month, plan.buy_window_days),
                status=status,
                buys=len(in_month),
                amount=sum((b.money for b in in_month), ZERO),
                shares=shares,
                rule_ids=sorted({f.rule.id for f in findings if f.month == label}),
                version=version,
                skip_reason=skipped[0].reason if skipped and not done else "",
                ranking=(rankings or {}).get((year, month), ""),
            )
        )
    return rows


def next_action(
    plan: Plan,
    entries: list[Entry],
    today: date,
    skipped: frozenset[tuple[int, int]] = frozenset(),
) -> NextAction:
    """The next buy. Before the start: the start month's window. In a month with no buy yet and
    the window open: that window, due now. Otherwise, the month after: this month's buy is done,
    or its window has closed (the review says "No buy" for it; the next action is still the
    next window, because the method has no catching up). Chapter 12: a month in `skipped` (a
    skip with its reason in the journal) counts as decided, like a month with a buy."""
    bought = {(e.day.year, e.day.month) for e in entries if e.action is Action.BUY} | skipped
    if today < plan.start:
        year, month, status = plan.start.year, plan.start.month, "upcoming"
    elif (today.year, today.month) in bought or today.day > plan.buy_window_days:
        (year, month), status = next_month(today.year, today.month), "upcoming"
    else:
        year, month, status = today.year, today.month, "due"
    return NextAction(
        label=month_label(year, month),
        opens=date(year, month, 1),
        closes=date(year, month, plan.buy_window_days),
        amount=plan.amount,
        symbols=sorted(plan.symbols),
        status=status,
    )


def explain(
    findings: list[FindingLine], months: list[MonthRow], rule_id: str = ONE_BUY
) -> list[FindingLine]:
    """Attach a skip's reason to the "No buy" finding of a month the journal says was skipped.
    Only that rule, and only a month with no buy: a skip does not excuse two buys. Chapter 14:
    `rule_id` names the method's missed-month rule ("No rebalance" for 12-1 momentum)."""
    skipped = {row.label: row.skip_reason for row in months if row.status == "skipped"}
    return [
        replace(finding, explanation=skipped[finding.month])
        if finding.rule.id == rule_id and finding.month in skipped
        else finding
        for finding in findings
    ]


def span_through(span: Span, through: date) -> date:
    return through if span.last is None else min(through, span.last)


def version_on(spans: list[Span], day: date) -> MethodPlan:
    begun = [span.plan for span in spans if span.first <= day]
    return begun[-1] if begun else spans[0].plan


def build_review(plan: MethodPlan, entries: list[JournalEntry], through: date) -> MethodReview:
    """The whole context for the method page, from the row, the rows and the date. `plan` is the
    newest version; each version in its history is reviewed over its own span, with its own
    numbers, and the findings and months are joined in order."""
    method = plan.method()
    spans = version_spans(plan.versions() if plan.pk is not None else [plan])
    if not spans:
        spans = [Span(plan, plan.started_on, plan.ended_on)]
    trades = [entry.to_entry() for entry in entries if entry.is_trade]
    rules = rule_lines(method)
    by_id = {rule.id: rule for rule in rules}
    findings: list[FindingLine] = []
    months: list[MonthRow] = []
    series = momentum_prices(spans) if plan.is_momentum else None
    for span in spans:
        upto = span_through(span, through)
        version = span.plan.to_plan()
        if series is None:
            found = finding_lines(review(span.plan.method(), version, trades, upto), by_id)
            months_found = month_rows(version, entries, found, upto, span.plan.version)
        else:
            rankings = span_rankings(span.plan, version, upto, series)
            checked = momentum_rules.review(
                span.plan.method(),
                version,
                span.plan.top_n or 1,
                trades,
                upto,
                rankings,
                held_since=spans[0].first,
            )
            found = finding_lines(checked, by_id)
            words = {month: ranking_words(ranking) for month, ranking in rankings.items()}
            months_found = month_rows(
                version, entries, found, upto, span.plan.version, any_trade=True, rankings=words
            )
        findings += found
        months += months_found
    findings = explain(
        findings, months, momentum_rules.MISSED_MONTH if series is not None else ONE_BUY
    )
    skipped = frozenset(
        (e.date.year, e.date.month) for e in entries if e.kind == SKIP and e.date >= spans[0].first
    )
    now = version_on(spans, through)
    action = next_action(now.to_plan(), trades, through, skipped)
    if now is not plan and action.opens >= plan.started_on:
        now = plan
        action = next_action(plan.to_plan(), trades, through, skipped)
    if series is not None:
        top = ranking_for(now, (action.opens.year, action.opens.month), series).top
        action = replace(action, symbols=top)
    return MethodReview(
        plan=plan,
        method=method,
        rules=rules,
        through=through,
        entries=entries,
        findings=findings,
        checks=rule_checks(rules, findings),
        months=months,
        next_action=action,
        spans=spans,
        momentum=momentum_view(plan, through, series) if series is not None else None,
    )


# --- Chapter 14: the rankings a momentum review reads ---------------------------------------------


def momentum_prices(spans: list[Span]) -> PriceSeries:
    """One query for every candidate any version names, from the first window's start on."""
    symbols = {symbol for span in spans for symbol in span.plan.symbol_list()}
    first = spans[0].first
    return price_series(symbols, series_since((first.year, first.month)))


def span_rankings(
    version: MethodPlan, plan: Plan, through: date, series: PriceSeries
) -> dict[Month, Ranking]:
    """The ranking of every month the span's review covers: the months due, and the month of
    `through` while its window is still open, so its row can say what the top N is."""
    months: list[Month] = list(months_due(plan, through))
    current = (through.year, through.month)
    if through >= plan.start and current not in months:
        months.append(current)
    return {month: ranking_for(version, month, series) for month in months}


def ranking_words(ranking: Ranking) -> str:
    """`ALPHA, BETA` for the top N in rank order, or `not ranked` when no candidate has both
    closes stored."""
    return ", ".join(ranking.top) if ranking.ranked else "not ranked"
```

The change is one branch in `build_review`. An index plan takes the path it took in chapter 12, line for line;
`test_ch10.py` and `test_ch12.py` prove it. A momentum plan reads its prices once, ranks the months each version
covers, runs the momentum rule set per version, and adds the ranking to each month row. `month_rows` and `explain`
gain one argument each with the old behavior as its default: a month with only a sale is a rebalance, and the skip
explains "No rebalance" the way it explains "No buy".

### 14.8 The forms and the views

Listing 14-14, Filename: `src/invest_witus_site/methods/forms.py`:

```python
"""The method page's forms: start a method for an account, and log one journal entry. Chapter 12
adds three: change or end the plan with a reason, close a month's review, and reopen it. Chapter
14 adds the top N a 12-1 momentum plan holds, to the start form and the change form, and puts a
momentum plan's candidates on the account's watch list so the nightly pull stores their closes."""

from collections.abc import Mapping
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction

from invest_witus.methods.rulebook import available_methods
from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.models import (
    MAX_WINDOW_DAYS,
    MIN_WINDOW_DAYS,
    MOMENTUM,
    ONE_CENT,
    REASON_MAX_LENGTH,
    TRADE,
    JournalEntry,
    MethodPlan,
    MonthlyReview,
    join_symbols,
    month_of,
    parse_tags,
    validate_symbol_list,
)
from invest_witus_site.methods.momentum import ensure_watched

SYMBOL_BOX = {"autocomplete": "off", "autocapitalize": "characters", "spellcheck": "false"}


def method_choices() -> list[tuple[str, str]]:
    """The methods the package ships, read when the form is built, never typed into the form.
    Chapter 14's second rules file became the second option with no change here."""
    return [(method.id, method.name) for method in available_methods()]


class StartMethodForm(forms.Form):
    """The plan's numbers. The method is a choice from the package; the symbols go through
    chapter 09's rule; the account is the view's, not a field. Valid only while the account
    runs no method, which `clean()` checks and the database's partial unique constraint backs."""

    method_id = forms.ChoiceField(label="Method", choices=method_choices)
    amount = forms.DecimalField(
        label="Amount each month",
        min_value=ONE_CENT,
        max_digits=14,
        decimal_places=2,
        help_text="In dollars, to the cent.",
    )
    buy_window_days = forms.IntegerField(
        label="Buy window, in days",
        min_value=MIN_WINDOW_DAYS,
        max_value=MAX_WINDOW_DAYS,
        initial=7,
        help_text="Buy within the first N days of each month; 1 to 28.",
    )
    symbols = forms.CharField(
        label="Symbols",
        max_length=200,
        widget=forms.TextInput(attrs=SYMBOL_BOX),
        help_text="The fund or funds the plan names, separated by commas or spaces.",
    )
    started_on = forms.DateField(
        label="Start", widget=forms.DateInput(attrs={"type": "date"}), initial=date.today
    )
    # Chapter 11: optional, and used only on an account linked to Alpaca paper, where Confirm
    # refuses buys beyond what is left of it.
    practice_budget = forms.DecimalField(
        label="Practice budget",
        required=False,
        min_value=ONE_CENT,
        max_digits=14,
        decimal_places=2,
        help_text="Paper accounts only: the practice money this plan may spend. Optional.",
    )
    # Chapter 14: 12-1 momentum's one more number. Optional in the form, required by `clean()`
    # for momentum and refused for index investing, which holds every fund it names.
    top_n = forms.IntegerField(
        label="Top N to hold",
        required=False,
        min_value=1,
        help_text=(
            "12-1 momentum only: how many of the ranked candidates to hold, fewer than the "
            "candidates you name. Leave it empty for index investing."
        ),
    )

    def __init__(self, account: Account, data: Mapping[str, Any] | None = None) -> None:
        super().__init__(data)
        self.account = account
        # The symbols the start put on the watch list (momentum only), for the view's message.
        self.watched: list[str] = []

    def clean_symbols(self) -> str:
        """The box as the stored list: each symbol normalized, once, joined by spaces. A refused
        token is a form error naming it; a plan with a typo in its universe would flag every buy."""
        text: str = self.cleaned_data["symbols"]
        validate_symbol_list(text)
        return join_symbols(text)

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean() or {}
        if MethodPlan.active_for(self.account) is not None:
            raise ValidationError(
                "This account already runs a method. End it from the method page before "
                "starting another."
            )
        check_top_n(self, cleaned.get("method_id"), cleaned.get("top_n"), cleaned.get("symbols"))
        return cleaned

    def start(self) -> MethodPlan:
        """The row. Called after `is_valid()`; the model's `save()` normalizes once more."""
        amount: Decimal = self.cleaned_data["amount"]
        plan = MethodPlan.objects.create(
            account=self.account,
            method_id=self.cleaned_data["method_id"],
            amount=amount,
            buy_window_days=self.cleaned_data["buy_window_days"],
            symbols=self.cleaned_data["symbols"],
            started_on=self.cleaned_data["started_on"],
            practice_budget=self.cleaned_data["practice_budget"],
            top_n=self.cleaned_data.get("top_n"),
        )
        if plan.is_momentum:
            self.watched = ensure_watched(self.account, plan.symbol_list())
        return plan


def check_top_n(
    form: forms.Form, method_id: str | None, top_n: int | None, symbols: str | None
) -> None:
    """Chapter 14: a momentum plan names a top N smaller than its candidates (with N equal to the
    list, the ranking would leave nothing out); an index plan names none."""
    if "top_n" in form.errors:
        return
    if method_id != MOMENTUM:
        if top_n is not None:
            form.add_error("top_n", "Leave this empty: index investing holds every fund it names.")
        return
    if top_n is None:
        form.add_error("top_n", "12-1 momentum needs a top N: how many candidates to hold.")
        return
    count = len((symbols or "").split())
    if symbols and top_n >= count:
        form.add_error(
            "top_n",
            f"Name more candidates than the top N: {count} candidate{'' if count == 1 else 's'} "
            f"and a top {top_n} leaves nothing to rank out.",
        )


class JournalEntryForm(forms.ModelForm[JournalEntry]):
    """One row of the journal, as a `ModelForm`: the fields, their labels, help and validators
    come from the model, so the symbol rule and the one-cent minimum run here before `save()`
    runs them again. The view passes `instance=JournalEntry(account=account)`, so the model's
    `clean()` knows the account and can refuse a closed month.

    Chapter 12: the kind, the reason, the state and the tags. A form posted without a kind (the
    chapter 10 form, a script) is a trade, as every entry was before this chapter."""

    class Meta:
        model = JournalEntry
        fields = [
            "date",
            "kind",
            "action",
            "symbol",
            "amount",
            "shares",
            "reason",
            "state",
            "tags",
            "note",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "symbol": forms.TextInput(attrs=SYMBOL_BOX),
            "reason": forms.Textarea(attrs={"rows": 2}),
            "tags": forms.TextInput(attrs={"autocomplete": "off", "spellcheck": "false"}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["kind"].required = False

    def clean_kind(self) -> str:
        kind: str = self.cleaned_data.get("kind") or ""
        return kind or TRADE

    def clean_tags(self) -> str:
        try:
            return " ".join(parse_tags(self.cleaned_data.get("tags") or ""))
        except ValueError as error:
            raise ValidationError(str(error)) from None


def first_of_month(day: date) -> date:
    return day.replace(day=1)


def first_of_next_month(day: date) -> date:
    return (day.replace(day=28) + timedelta(days=4)).replace(day=1)


THIS_MONTH = "this"
NEXT_MONTH = "next"
CHANGE = "change"
END = "end"


class PlanChangeForm(forms.Form):
    """Change the plan's amount, window or symbols, or end it, always with a reason. A change
    makes a new version that starts on the first day of this month or next month; the old version
    keeps judging the months before it (PRD 7.1: "old reviews keep pointing at the version they
    judged"). The method itself does not change here: a different method is a new plan."""

    what = forms.ChoiceField(
        label="What to do",
        choices=[(CHANGE, "Change the numbers"), (END, "End the plan")],
        widget=forms.RadioSelect,
        initial=CHANGE,
    )
    amount = forms.DecimalField(
        label="Amount each month",
        required=False,
        min_value=ONE_CENT,
        max_digits=14,
        decimal_places=2,
    )
    buy_window_days = forms.IntegerField(
        label="Buy window, in days",
        required=False,
        min_value=MIN_WINDOW_DAYS,
        max_value=MAX_WINDOW_DAYS,
    )
    symbols = forms.CharField(
        label="Symbols", required=False, max_length=200, widget=forms.TextInput(attrs=SYMBOL_BOX)
    )
    # Chapter 14: shown for a 12-1 momentum plan only; removed in `__init__` for an index plan.
    top_n = forms.IntegerField(label="Top N to hold", required=False, min_value=1)
    effective = forms.ChoiceField(label="Starting", required=False)
    reason = forms.CharField(
        label="Why",
        max_length=REASON_MAX_LENGTH,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Required. It is kept with the version, dated, for every later review.",
    )

    def __init__(
        self, plan: MethodPlan, today: date, data: Mapping[str, Any] | None = None
    ) -> None:
        initial = {
            "amount": plan.amount,
            "buy_window_days": plan.buy_window_days,
            "symbols": plan.symbols,
            "top_n": plan.top_n,
            "effective": NEXT_MONTH,
        }
        super().__init__(data, initial=initial)
        self.plan = plan
        self.today = today
        self.watched: list[str] = []
        if not plan.is_momentum:
            del self.fields["top_n"]
        this, following = first_of_month(today), first_of_next_month(today)
        effective = self.fields["effective"]
        assert isinstance(effective, forms.ChoiceField)
        effective.choices = [
            (NEXT_MONTH, f"Next month, from {following:%Y-%m-%d}"),
            (THIS_MONTH, f"This month, from {this:%Y-%m-%d}"),
        ]

    def clean_symbols(self) -> str:
        text: str = self.cleaned_data.get("symbols") or ""
        if not text.strip():
            return ""
        validate_symbol_list(text)
        return join_symbols(text)

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean() or {}
        if cleaned.get("what") != CHANGE:
            return cleaned
        for name in ("amount", "buy_window_days", "symbols"):
            if name not in self.errors and cleaned.get(name) in (None, ""):
                self.add_error(name, "A change keeps every number: fill this in.")
        if self.errors:
            return cleaned
        plan = self.plan
        if plan.is_momentum:
            check_top_n(self, plan.method_id, cleaned.get("top_n"), cleaned["symbols"])
            if self.errors:
                return cleaned
        new = (cleaned["amount"], cleaned["buy_window_days"], cleaned["symbols"])
        top_n = cleaned.get("top_n") if plan.is_momentum else plan.top_n
        if new == (plan.amount, plan.buy_window_days, plan.symbols) and top_n == plan.top_n:
            if plan.is_momentum:
                raise ValidationError(
                    "Nothing changed: the amount, the window, the candidates and the top N match."
                )
            raise ValidationError("Nothing changed: the amount, the window and the symbols match.")
        if cleaned.get("effective") == THIS_MONTH:
            self.check_this_month()
        return cleaned

    def check_this_month(self) -> None:
        """This month may take the new numbers only while nothing in it is settled: the window is
        still open, no trade is logged in it, and the version in force has started. Otherwise
        the month already belongs to the old numbers, and the change starts next month."""
        plan, today = self.plan, self.today
        if plan.started_on > today:
            raise ValidationError(
                f"Version {plan.version} starts on {plan.started_on:%Y-%m-%d} and has not begun; "
                "a change to it starts next month."
            )
        if today.day > plan.buy_window_days:
            raise ValidationError(
                f"This month's window closed on day {plan.buy_window_days}; the month is judged "
                "by the numbers in force then. Choose next month."
            )
        traded = JournalEntry.objects.filter(
            account=plan.account,
            kind=TRADE,
            date__year=today.year,
            date__month=today.month,
            date__gte=plan.started_on,
        ).exists()
        if traded:
            raise ValidationError(
                f"{month_of(today)} already has a trade in the journal; it stays on version "
                f"{plan.version}. Choose next month."
            )
        if MonthlyReview.is_closed(plan.account.pk, today):
            raise ValidationError(f"{month_of(today)} is closed. Choose next month.")

    def apply(self) -> MethodPlan:
        """Write the change, after `is_valid()`. Ending: the row stays, inactive, with the day and
        the reason. Changing: the old row ends the day before the new version starts, and the
        new row points back at it. One transaction, the old row first, so the partial unique
        constraint (one active plan per account) never sees two."""
        plan, data = self.plan, self.cleaned_data
        reason: str = data["reason"].strip()
        with transaction.atomic():
            if data["what"] == END:
                plan.active = False
                plan.ended_on = self.today
                plan.end_reason = reason
                plan.save()
                return plan
            effective = (
                first_of_month(self.today)
                if data.get("effective") == THIS_MONTH
                else first_of_next_month(self.today)
            )
            starts = max(effective, plan.started_on)
            plan.active = False
            plan.ended_on = starts - timedelta(days=1)
            plan.save()
            version = MethodPlan.objects.create(
                account=plan.account,
                method_id=plan.method_id,
                amount=data["amount"],
                buy_window_days=data["buy_window_days"],
                symbols=data["symbols"],
                started_on=starts,
                practice_budget=plan.practice_budget,
                previous=plan,
                version=plan.version + 1,
                change_reason=reason,
                top_n=data.get("top_n") if plan.is_momentum else plan.top_n,
            )
            if version.is_momentum:
                self.watched = ensure_watched(version.account, version.symbol_list())
            return version


TEXT_BOX = {"rows": 3}


class CloseReviewForm(forms.Form):
    """The month's written review: three short answers, each required."""

    did = forms.CharField(
        label="What I did",
        max_length=REASON_MAX_LENGTH,
        widget=forms.Textarea(attrs=TEXT_BOX),
    )
    rules_said = forms.CharField(
        label="What the rules said",
        max_length=REASON_MAX_LENGTH,
        widget=forms.Textarea(attrs=TEXT_BOX),
        help_text="Started for you from the review's findings. Edit it to say it your way.",
    )
    next_month = forms.CharField(
        label="What I'll do next month",
        max_length=REASON_MAX_LENGTH,
        widget=forms.Textarea(attrs=TEXT_BOX),
    )


class ReopenReviewForm(forms.Form):
    reason = forms.CharField(
        label="Why reopen it",
        max_length=REASON_MAX_LENGTH,
        widget=forms.Textarea(attrs=TEXT_BOX),
        help_text="Required, and kept: the month's history shows every close and reopen.",
    )
```

Listing 14-15, Filename: `src/invest_witus_site/methods/views.py`:

```python
"""The method page for one account, in three views, and its two POST actions.

`method_page` renders the same context through one of three templates, A, B or C, named as the
research named them (`docs/research/01-ux-benchmarks-and-three-directions.md`, section 5). The
choice comes from `?view=a|b|c`, is remembered in the session, and defaults to A when the
account runs a method and to C when it does not (PRD 7.2: C to start a method, A as the home).
Every view sits behind `login_required` and the same ownership query as chapter 08's pages, so
another owner's account is a 404; nothing here is public.

Chapter 12 adds the plan's change form (`change_plan`) and the month's review page with its two
actions (`review_month`, `close_month`, `reopen_month`). The method page opens the review of every
month whose window has closed, and view A offers to close the oldest one still open.
"""

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from invest_witus.methods.rulebook import available_methods
from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.engine import MethodReview, build_review, rule_lines
from invest_witus_site.methods.forms import (
    CloseReviewForm,
    JournalEntryForm,
    PlanChangeForm,
    ReopenReviewForm,
    StartMethodForm,
)
from invest_witus_site.methods.models import (
    JournalEntry,
    MethodPlan,
    MonthlyReview,
    ReviewEvent,
)
from invest_witus_site.methods.reviews import (
    ReviewRefused,
    close_review,
    open_due_reviews,
    reopen_review,
)
from invest_witus_site.paper.orders import alpaca_allowed, paper_section

# The three views, by letter, as the research and the PRD name them. The order is the switch's.
VIEWS = {
    "a": ("A: The Plan and the Logbook", "methods/_view_a.html"),
    "b": ("B: Method Console", "methods/_view_b.html"),
    "c": ("C: The Lesson Lab", "methods/_view_c.html"),
}
SESSION_KEY = "method_view"


def chosen_view(request: HttpRequest, has_plan: bool) -> str:
    """`?view=` when it names a view (and remember it); else the session's; else the default."""
    asked = request.GET.get("view", "").lower()
    if asked in VIEWS:
        request.session[SESSION_KEY] = asked
        return asked
    saved = request.session.get(SESSION_KEY)
    if isinstance(saved, str) and saved in VIEWS:
        return saved
    return "a" if has_plan else "c"


def through_date(request: HttpRequest, today: date) -> date:
    """`?through=YYYY-MM-DD` reviews up to that day, as chapter 03's command did; anything else
    is today. The page says which day it was reviewed through."""
    try:
        return date.fromisoformat(request.GET.get("through", ""))
    except ValueError:
        return today


@login_required
def method_page(request: HttpRequest, pk: int) -> HttpResponse:
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    return render_method_page(request, account)


def render_method_page(
    request: HttpRequest,
    account: Account,
    start_form: StartMethodForm | None = None,
    entry_form: JournalEntryForm | None = None,
    force_view: str | None = None,
) -> HttpResponse:
    """One context, three templates. The ownership check is the caller's. The two POST views
    render the page again through this function, with a bound form, when a submission fails."""
    today = timezone.localdate()
    through = through_date(request, today)
    plan = MethodPlan.active_for(account)
    entries = JournalEntry.entries_for(account)
    view = force_view or chosen_view(request, plan is not None)
    # Chapter 12: every month whose window closed by today has a review; the oldest still open
    # is the one view A offers to close. Opened against today, never `?through=`.
    month_reviews = open_due_reviews(plan, today) if plan is not None else []
    still_open = [review for review in month_reviews if not review.closed]
    context = {
        "account": account,
        "plan": plan,
        "review": build_review(plan, entries, through) if plan is not None else None,
        "entries": entries,
        "catalog": [(method, rule_lines(method)) for method in available_methods()],
        "start_form": start_form or StartMethodForm(account),
        "entry_form": entry_form or JournalEntryForm(initial={"date": today}),
        "month_reviews": month_reviews,
        "review_to_close": still_open[0] if still_open else None,
        "open_reviews": len(still_open),
        "view": view,
        "view_label": VIEWS[view][0],
        "view_template": VIEWS[view][1],
        "views": [(key, label) for key, (label, _) in VIEWS.items()],
        "through": through,
        "through_query": f"&through={through.isoformat()}" if through != today else "",
        # Chapter 11: this month's buys and the Confirm button, on an account linked to Alpaca
        # paper only. One request to Alpaca (the clock); `None` everywhere else.
        "paper": (
            paper_section(plan)
            if plan is not None and alpaca_allowed(request.user, account)
            else None
        ),
    }
    return render(request, "methods/method_page.html", context)


@login_required
@require_POST
def start_method(request: HttpRequest, pk: int) -> HttpResponse:
    """Create the plan. A refused form draws view C again with the reasons beside the boxes;
    a started method goes to view A, the everyday home, and the session remembers it."""
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    form = StartMethodForm(account, request.POST)
    if not form.is_valid():
        return render_method_page(request, account, start_form=form, force_view="c")
    plan = form.start()
    messages.success(request, f"Started {plan.method().name} on {account.name}.")
    watched_message(request, form.watched)
    request.session[SESSION_KEY] = "a"
    return redirect("method-page", pk=account.pk)


@login_required
@require_POST
def log_entry(request: HttpRequest, pk: int) -> HttpResponse:
    """Add one journal row to the account and come back to the same view."""
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    form = JournalEntryForm(request.POST, instance=JournalEntry(account=account))
    if not form.is_valid():
        return render_method_page(request, account, entry_form=form)
    entry = form.save()
    messages.success(request, f"Logged: {entry}.")
    return redirect("method-page", pk=account.pk)


def watched_message(request: HttpRequest, added: list[str]) -> None:
    """Chapter 14: say which candidates a momentum plan put on the watch list, and why."""
    if added:
        messages.info(
            request,
            "Added to the watch list, so the nightly pull stores their closes: "
            f"{', '.join(added)}. A candidate needs a year of closes or more to be ranked; "
            "Get history fetches them now.",
        )


# --- Chapter 12: change or end the plan -----------------------------------------------------------


@login_required
def change_plan(request: HttpRequest, pk: int) -> HttpResponse:
    """GET draws the form with the plan's numbers; POST writes a new version or ends the plan."""
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    plan = MethodPlan.active_for(account)
    if plan is None:
        messages.info(request, "No method runs on this account, so there is no plan to change.")
        return redirect("method-page", pk=account.pk)
    today = timezone.localdate()
    form = PlanChangeForm(plan, today, request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        written = form.apply()
        watched_message(request, form.watched)
        if written.active:
            messages.success(
                request,
                f"Version {written.version} of the plan starts on {written.started_on:%Y-%m-%d}. "
                f"Version {plan.version} keeps its months, judged by its own numbers.",
            )
        else:
            messages.success(
                request,
                f"Ended {plan.method().name} on {account.name}. Its months and reviews stay; "
                "start a new method when you are ready.",
            )
            # With no plan, the method page is the Lesson Lab, where a new one starts.
            request.session[SESSION_KEY] = "c"
        return redirect("method-page", pk=account.pk)
    context = {"account": account, "plan": plan, "form": form, "versions": plan.versions()}
    return render(request, "methods/plan_change.html", context)


# --- Chapter 12: the month's review ---------------------------------------------------------------


def review_or_404(account: Account, month: str) -> MonthlyReview:
    """The account's review for the month: the newest plan's, if two plans share the month. The
    running plan's due reviews are opened first, so a link to a month works before the method
    page has been drawn that day."""
    plan = MethodPlan.active_for(account)
    if plan is not None:
        open_due_reviews(plan, timezone.localdate())
    review = (
        MonthlyReview.objects.filter(plan__account=account, month=month)
        .select_related("plan")
        .order_by("-plan__pk")
        .first()
    )
    if review is None:
        raise Http404("No review for that month.")
    return review


def month_context(review: MonthlyReview) -> MethodReview:
    """The plan's whole review through today, from the newest version of the review's plan."""
    plan = review.plan.latest_version()
    entries = JournalEntry.entries_for(plan.account)
    return build_review(plan, entries, timezone.localdate())


def rules_said_draft(context: MethodReview, month: str) -> str:
    """The second answer's starting text: the month's findings, or the sentence that none."""
    found = [f for f in context.findings if f.month == month]
    if not found:
        return "Every rule passed this month."
    lines: list[str] = []
    for finding in found:
        line = finding.message
        if finding.explained:
            line += f" (skipped: {finding.explanation})"
        lines.append(line)
    return " ".join(lines)


def render_review_page(
    request: HttpRequest,
    account: Account,
    review: MonthlyReview,
    close_form: CloseReviewForm | None = None,
    reopen_form: ReopenReviewForm | None = None,
) -> HttpResponse:
    context = month_context(review)
    row = context.month(review.month)
    entries = [entry for entry in context.entries if f"{entry.date:%Y-%m}" == review.month]
    page = {
        "account": account,
        "review": review,
        "version": review.plan,
        "row": row,
        "findings": [f for f in context.findings if f.month == review.month],
        "entries": entries,
        "events": list(ReviewEvent.objects.filter(review=review).select_related("by")),
        "close_form": close_form
        or CloseReviewForm(initial={"rules_said": rules_said_draft(context, review.month)}),
        "reopen_form": reopen_form or ReopenReviewForm(),
    }
    return render(request, "methods/review_month.html", page)


@login_required
def review_month(request: HttpRequest, pk: int, month: str) -> HttpResponse:
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    return render_review_page(request, account, review_or_404(account, month))


@login_required
@require_POST
def close_month(request: HttpRequest, pk: int, month: str) -> HttpResponse:
    """Close the month with the three answers. Refused, with the page drawn again, when a field
    is empty or the month has a missed buy that no skip explains."""
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    review = review_or_404(account, month)
    if review.closed:
        messages.error(request, f"{review.month} is already closed.")
        return redirect("method-review", pk=account.pk, month=review.month)
    form = CloseReviewForm(request.POST)
    if not form.is_valid():
        return render_review_page(request, account, review, close_form=form)
    try:
        close_review(review, month_context(review), by=request.user, **form.cleaned_data)
    except ReviewRefused as refused:
        form.add_error(None, str(refused))
        return render_review_page(request, account, review, close_form=form)
    messages.success(request, f"Closed {review.month}. Its entries are read-only now.")
    return redirect("method-page", pk=account.pk)


@login_required
@require_POST
def reopen_month(request: HttpRequest, pk: int, month: str) -> HttpResponse:
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    review = review_or_404(account, month)
    form = ReopenReviewForm(request.POST)
    if not form.is_valid():
        return render_review_page(request, account, review, reopen_form=form)
    try:
        reopen_review(review, reason=form.cleaned_data["reason"], by=request.user)
    except ReviewRefused as refused:
        messages.error(request, str(refused))
    else:
        messages.success(request, f"Reopened {review.month}. Its entries can change again.")
    return redirect("method-review", pk=account.pk, month=review.month)
```

Things to notice:

- **`check_top_n` is one function for two forms.** It reads the method from the form's data, so the start form,
  where the method is a field, and the change form, where it is the plan's, share every message.
- **The change form removes its field for an index plan.** `del self.fields["top_n"]` keeps chapter 12's form and
  its tests exactly as they were.
- **The form returns the plan, as before.** The symbols it added to the watch list go in `form.watched`, so
  `start()` keeps the signature chapter 10's tests call.

### 14.9 The pages

The momentum section is one partial, included above the view, so views A, B and C each show it without three
copies:

Listing 14-16, Filename: `src/invest_witus_site/methods/templates/methods/_momentum.html`:

```html
{% load holdings_extras %}
{# 12-1 momentum (chapter 14), on the method page of an account that runs it, above the view. Included by #}
{# methods/method_page.html with `account` and `momentum` (a MomentumView). The ranked bars are drawn on the server #}
{# and the table under them is their text alternative; no script. Owner only, as the whole page is. #}
<section class="card" aria-labelledby="ranking-heading">
  <h2 id="ranking-heading">The ranking for {{ momentum.month }}</h2>
  <p>The 12-1 return of each candidate: from the last close of {{ momentum.start }} to the last close of {{ momentum.end }}, on adjusted closes. {{ momentum.excluded }}, the latest full month, is left out. Your plan holds the top {{ momentum.top_n }}.</p>
  {% if momentum.unadjusted %}<p class="small">{{ momentum.unadjusted }} stored close{{ momentum.unadjusted|pluralize }} had no adjusted close, so the plain close was used for {{ momentum.unadjusted|pluralize:"it,them" }}; a split inside the window would then read as a fall. Get history with 5 years fills the adjusted closes.</p>{% endif %}
  {% if momentum.chart %}
  <figure class="rank-chart" aria-labelledby="rank-title">
    <figcaption>
      <p class="chart-title" id="rank-title">12-1 return by candidate, highest first, for the {{ momentum.month }} rebalance</p>
      <p class="small muted">A filled bar is in the top {{ momentum.top_n }}; an outlined bar is not. Bars right of the line rose over the window, bars left of it fell.</p>
    </figcaption>
    <ol class="rank-bars">
      {% for bar in momentum.chart.bars %}
      <li class="rank-bar">
        <span class="rank-label">{{ bar.place.rank }}. {{ bar.symbol }}{% if bar.place.top %}<span class="top-mark">top {{ momentum.top_n }}</span>{% endif %}</span>
        <svg class="rank-track" viewBox="0 0 100 10" preserveAspectRatio="none" aria-hidden="true" focusable="false"><title>{{ bar.symbol }}: {{ bar.text }}, ranked {{ bar.place.rank }}</title><rect class="bar-{{ bar.direction }}{% if not bar.place.top %} bar-out{% endif %}" x="{{ bar.x }}" y="1.5" width="{{ bar.width }}" height="7" vector-effect="non-scaling-stroke"/><line class="zero" x1="{{ momentum.chart.zero_x }}" x2="{{ momentum.chart.zero_x }}" y1="0" y2="10" vector-effect="non-scaling-stroke"/></svg>
        <span class="rank-value">{{ bar.text }} {{ bar.direction }}{% if bar.place.tied %}, tied{% endif %}</span>
      </li>
      {% endfor %}
    </ol>
  </figure>
  <p class="how-to-read"><strong>How to read this.</strong> Each bar is one candidate's change in price over the eleven months of its window, with dividends and splits counted through the adjusted close. The longest bar to the right ranked first. The method holds the filled bars, in equal parts, until a later ranking pushes one out. A high rank is a fact about the past year, not a forecast. <span class="muted">Lesson coming.</span></p>
  <div class="table-scroll" role="region" aria-labelledby="ranking-caption" tabindex="0">
  <table class="holdings">
    <caption id="ranking-caption">The same ranking as a table, with the two closes each return is computed from</caption>
    <thead>
      <tr>
        <th scope="col">Rank</th>
        <th scope="col">Symbol</th>
        <th scope="col" class="num">12-1 return</th>
        <th scope="col">From</th>
        <th scope="col">To</th>
        <th scope="col">Top {{ momentum.top_n }}</th>
      </tr>
    </thead>
    <tbody>
      {% for bar in momentum.chart.bars %}
      <tr>
        <th scope="row">{{ bar.place.rank }}</th>
        <td>{{ bar.symbol }}</td>
        <td class="num">{{ bar.text }}{% if bar.place.tied %} (tied){% endif %}</td>
        <td>{{ bar.place.score.start_day|date:"Y-m-d" }}, {{ bar.place.score.start_close|money }}</td>
        <td>{{ bar.place.score.end_day|date:"Y-m-d" }}, {{ bar.place.score.end_close|money }}</td>
        <td>{% if bar.place.top %}yes{% else %}no{% endif %}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  </div>
  {% else %}
  <p>No candidate can be ranked yet: none has a close stored in both months of the window.</p>
  {% endif %}
  {% if momentum.ranking.unranked %}
  <h3>Not ranked</h3>
  <ul>
    {% for item in momentum.ranking.unranked %}<li>{{ item.symbol }}: {{ item.reason }}.</li>{% endfor %}
  </ul>
  <form method="post" action="{% url 'watch-fetch-history-many' account.pk %}" class="history-form">
    {% csrf_token %}
    <input type="hidden" name="typed" value="{{ momentum.unranked_symbols|join:' ' }}">
    <input type="hidden" name="range" value="5y">
    <button type="submit" name="which" value="selected">Get 5 years of history for {{ momentum.unranked_symbols|join:", " }}</button>
  </form>
  <p class="small muted">A candidate needs a close in both months of the window, about 13 months of history; the nightly pull's first fetch of a new symbol stores one year. The button asks the price source once per symbol and goes back to the account page.</p>
  {% endif %}
  <h3>This month's rebalance</h3>
  {% if momentum.rebalance.buys %}
  <ul>
    {% for symbol, part in momentum.rebalance.parts %}<li>Buy {{ part|money }} of {{ symbol }}</li>{% endfor %}
    {% for symbol in momentum.rebalance.sells %}<li>Sell all of {{ symbol }}: it left the top {{ momentum.top_n }}</li>{% endfor %}
  </ul>
  {% if momentum.rebalance.sells %}<p class="small">The app does not place sells yet. On a paper account, sell in Alpaca's paper dashboard; anywhere else, at your broker. Then log the sale here with its amount, inside the window.</p>{% endif %}
  {% for warning in momentum.rebalance.warnings %}<p class="error" role="note">Wash-sale warning. {{ warning }}</p>{% endfor %}
  {% else %}
  <p>Nothing to buy until a candidate is ranked.</p>
  {% endif %}
  <p class="small muted">The ranking is arithmetic on your own candidates, the list you wrote before it was computed. It is not a recommendation. Information, not advice.</p>
</section>
```

Listing 14-17, Filename: `src/invest_witus_site/methods/templates/methods/method_page.html`:

```html
{% extends "pages/base.html" %}
{% load holdings_extras %}
{% block title %}{% if plan %}{{ review.method.name }}{% else %}Start a method{% endif %}: {{ account.name }}: Invest.WitUS{% endblock %}
{% block content %}
<section class="container" aria-labelledby="method-heading">
  <p class="eyebrow">{{ account.name }} <span class="muted">({{ account.broker }})</span></p>
  <h1 id="method-heading">{% if plan %}{{ review.method.name }}{% else %}Start a method{% endif %}</h1>
  {# The environment, as text, on every signed-in page (PRD 7.2). The account's kind is what chapter 05 stored. #}
  <p class="band">{{ account.get_kind_display }} account. {% if account.kind == "paper" %}Simulated money: nothing here is a real trade.{% else %}Entered by hand from statements: the app places no order.{% endif %} Information, not advice.</p>
  {% include "methods/_switch.html" %}
  {# Chapter 12: the logbook and the plan's change form, the same two links in every view. #}
  <p class="small"><a href="{% url 'logbook' account.pk %}">Open the logbook</a>: every entry, with filters and a CSV export.{% if plan %} <a href="{% url 'method-change' account.pk %}">Change or end this plan</a>, with a reason.{% endif %}</p>
  {# Chapter 11: on an account linked to Alpaca paper, this month's buys and the Confirm button. #}
  {% if paper %}{% include "paper/_month_buys.html" %}{% endif %}
  {# Chapter 14: a 12-1 momentum plan's ranking, its bars and this month's rebalance, in every view. #}
  {% if review.momentum %}{% include "methods/_momentum.html" with momentum=review.momentum %}{% endif %}
  {# The same context, one of three arrangements (chapter 10). The view's letter is the research's. #}
  {% include view_template %}
  <p><a href="{% url 'account-detail' account.pk %}">Back to the account</a></p>
</section>
{% endblock %}
```

Things to notice:

- **The bars are an ordered list.** Each item is the rank, the symbol, a small SVG and the number with its sign and
  the word up or down. A screen reader reads the list; the SVG is `aria-hidden` and carries a `<title>` for a mouse
  pointer.
- **Filled or outlined.** A bar in the top N is filled and one below it is an outline, so the line between them
  does not depend on telling two colors apart. The fill colors are the chart palette's blue and orange, each at
  least 3:1 against the page.
- **The table under the bars** holds the same ranking with the two closes and their days: the text alternative,
  and the place to check the arithmetic by hand.
- **"Get 5 years of history"** posts to the watch list's Fetch history for selected, with the unranked symbols
  typed in. No new view.

The views print the plan in momentum's words, in the same `if` everywhere. View A, for example:

Listing 14-18, Filename: `src/invest_witus_site/methods/templates/methods/_view_a.html`:

```html
{% load holdings_extras %}
{# View A, "The Plan and the Logbook" (research 01, direction A): the everyday home. One next action, #}
{# the on-plan status with its fixes, the plan's rules each with its lesson, and the logbook. #}
{% if plan %}
<section class="card" aria-labelledby="next-heading">
  <h2 id="next-heading">Next</h2>
  {% if review.momentum %}
  <p>{% if not review.next_action.symbols %}No candidate is ranked for {{ review.next_action.label }} yet, so there is nothing to buy; see the ranking above.{% elif review.next_action.status == "due" %}Due now: rebalance by {{ review.next_action.closes|date:"Y-m-d" }}, the end of this month's window. Put {{ review.next_action.amount|money }} in equal parts into {{ review.next_action.symbols|join:", " }}, and sell what left the top {{ plan.top_n }}.{% else %}Rebalance between {{ review.next_action.opens|date:"Y-m-d" }} and {{ review.next_action.closes|date:"Y-m-d" }}: {{ review.next_action.amount|money }} in equal parts into that month's top {{ plan.top_n }}, {{ review.next_action.symbols|join:", " }} on today's closes. Nothing to do before then.{% endif %}</p>
  {% else %}
  <p>{% if review.next_action.status == "due" %}Due now: buy {{ review.next_action.amount|money }} of {{ review.next_action.symbols|join:", " }} by {{ review.next_action.closes|date:"Y-m-d" }}, the end of this month's window.{% else %}Buy {{ review.next_action.amount|money }} of {{ review.next_action.symbols|join:", " }} between {{ review.next_action.opens|date:"Y-m-d" }} and {{ review.next_action.closes|date:"Y-m-d" }}. Nothing to do before then.{% endif %}</p>
  {% endif %}
</section>

{% if review_to_close %}{% include "methods/_close_month.html" %}{% endif %}

<section aria-labelledby="status-heading">
  <h2 id="status-heading">{% if review.on_plan %}You are on plan{% else %}Off plan: {{ review.findings|length }} thing{{ review.findings|length|pluralize }} to look at{% endif %}</h2>
  <p>{{ review.months_done }} of {{ review.months_due }} scheduled buy{{ review.months_due|pluralize }} made through {{ review.through|date:"Y-m-d" }}. A finding is a place the journal left the method; the lesson beside it says why the rule exists.</p>
  {% include "methods/_findings.html" %}
</section>

<section aria-labelledby="plan-heading">
  <h2 id="plan-heading">My plan</h2>
  <p>{{ review.method.summary }}</p>
  <p>{% if plan.is_momentum %}{{ plan.amount|money }} a month, in equal parts, into the top {{ plan.top_n }} of {{ plan.symbols }}{% else %}{{ plan.amount|money }} into {{ plan.symbols }}{% endif %} within the first {{ plan.buy_window_days }} day{{ plan.buy_window_days|pluralize }} of each month, since {{ plan.started_on|date:"Y-m-d" }}.</p>
  {% include "methods/_versions.html" %}
  <h3>The rules</h3>
  {% include "methods/_rules.html" with rules=review.rules %}
</section>

<section aria-labelledby="logbook-heading">
  <h2 id="logbook-heading">Logbook</h2>
  {% include "methods/_entries.html" with caption="Every trade logged for this account, in date order" %}
  <h3>Write a log entry</h3>
  {% include "methods/_log_form.html" %}
</section>
{% else %}
<p>No method yet on this account. <a href="?view=c">Read the rules and start one in the Lesson Lab</a>.</p>
{% endif %}
```

`_view_b.html` adds a **Top N** column to the Months table for a momentum plan, and `_view_c.html`,
`_versions.html` and `plan_change.html` change the plan's sentence the same way. Each `else` branch is the chapter
12 text, byte for byte, because chapter 10's tests compare it.

### 14.10 The shaded window and the badge

The chart gains bands: a stretch of days, clipped to the range on screen.

Listing 14-19, Filename: `src/invest_witus_site/prices/charts.py`:

```python
"""Line charts of stored closes: one symbol on its history page, or up to six rebased to 100 on the
compare page (2026-10-29, decisions 133 to 136).

Everything is computed here, in Decimal, and drawn by the template `prices/_chart.html`:

- **The plot** is an SVG whose viewBox is 0 to 100 both ways, stretched to its box
  (`preserveAspectRatio="none"`, strokes kept thin with `vector-effect`), so a point's x and y
  are percentages of the plot's width and height.
- **The axes** are HTML beside the SVG, placed by the same percentages, so their text stays a
  readable size at 320 pixels wide instead of shrinking with the drawing.
- **The values** a line uses are the adjusted close when every day in the range has one, else the
  close, and the legend says which (decision 134). A compare line is that value times 100 over
  its first value in the range.
- **The hover data** is the same numbers already formatted with `money`, so the owner pages'
  small script only picks a day and shows text the server wrote; the table carries the same text
  without the script.
- **Long ranges are thinned for drawing** (decision 140): over `MAX_POINTS` stored dates, the
  chart draws an even spread of them plus the first, the last, each line's lowest and highest
  day and every split or dividend day; the hover data follows the drawn dates; the tables under
  the chart keep every day.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal

from invest_witus_site.holdings.templatetags.holdings_extras import (
    money,
    percent,
    plain_number,
    signed_money,
)
from invest_witus_site.prices.models import DailyClose

# Up to six lines on one chart: four colors from Okabe and Ito's palette for color vision
# deficiency, plus two more, each also drawn with its own dash pattern so no line is told apart
# by color alone. Every color is at least 3:1 against the page's background (#020617), the
# contrast WCAG 2.2's 1.4.11 asks of graphics (checked in the tests).
LINE_STYLES: tuple[tuple[str, str, str], ...] = (
    ("#56b4e9", "", "solid"),
    ("#e69f00", "8 4", "dashed"),
    ("#009e73", "2 3", "dotted"),
    ("#f0e442", "10 3 2 3", "dash-dot"),
    ("#cc79a7", "4 4", "short dashes"),
    ("#ff8c69", "12 3 2 3 2 3", "dash-dot-dot"),
)
MAX_LINES = len(LINE_STYLES)

PLACE = Decimal("0.01")
HUNDRED = Decimal(100)
MAX_X_TICKS = 6
Y_TICKS = 4
# A tick label this close to an edge is aligned to it instead of centered, so it never hangs past
# the plot (and never makes the page scroll sideways on a phone).
EDGE_PERCENT = Decimal(12)
# Above this many dates a chart draws a thinned set (decision 140): 27 years of closes is about
# 6,800 days, which a phone draws slowly and the hover data would carry for nothing.
MAX_POINTS = 1000

SOURCE_NAMES = {"tiingo": "Tiingo", "csv": "CSV files"}

ADJUSTED = "adjusted close"
CLOSE = "close"


def place(value: Decimal) -> Decimal:
    return value.quantize(PLACE, rounding=ROUND_HALF_UP)


def rebased(value: Decimal, base: Decimal) -> Decimal:
    """`value` on a scale where `base` is 100: 110 is ten percent above the start."""
    return value * HUNDRED / base


def change_percent(start: Decimal, end: Decimal) -> Decimal:
    return (end - start) * HUNDRED / start


def number_text(value: Decimal) -> str:
    """A factor without trailing zeros: 4.000000 is `4`, 1.500000 is `1.5`."""
    return f"{value.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP).normalize():f}"


def split_text(factor: Decimal) -> str:
    """Tiingo's splitFactor in words: 4 is `Split 4-for-1`, 0.1 is `Reverse split 1-for-10`."""
    if factor >= 1:
        return f"Split {number_text(factor)}-for-1"
    return f"Reverse split 1-for-{number_text(1 / factor)}"


def dividend_text(amount: Decimal) -> str:
    """Tiingo's divCash: `Dividend $0.57`; a sub-cent amount keeps its places, `$0.5734`."""
    exact = amount == amount.quantize(Decimal("0.01"))
    return f"Dividend {money(amount) if exact else '$' + plain_number(amount)}"


def day_events(row: DailyClose) -> list[tuple[str, str]]:
    """The day's corporate actions as (kind, text) pairs, kind "split" or "dividend"."""
    found: list[tuple[str, str]] = []
    if row.is_split and row.split_factor is not None:
        found.append(("split", split_text(row.split_factor)))
    if row.is_dividend and row.div_cash is not None:
        found.append(("dividend", dividend_text(row.div_cash)))
    return found


def index_text(value: Decimal) -> str:
    """A rebased value to two places: `112.34`."""
    return f"{place(value):.2f}"


# --- Axes ----------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Tick:
    """One axis label: where it sits (percent along the axis), its text, how it aligns at an
    edge ("start", "end" or ""), and whether a narrow screen hides it."""

    at: Decimal
    label: str
    edge: str = ""
    minor: bool = False


def nice_step(raw: Decimal) -> Decimal:
    """The smallest of 1, 2, 2.5 and 5 times a power of ten that is at least `raw`."""
    if raw <= 0:
        return Decimal(1)
    magnitude = Decimal(1).scaleb(raw.adjusted())
    for multiple in (Decimal(1), Decimal(2), Decimal("2.5"), Decimal(5), Decimal(10)):
        if multiple * magnitude >= raw:
            return (multiple * magnitude).normalize()
    return (Decimal(10) * magnitude).normalize()  # not reached: 10 times the magnitude is >= raw


def y_scale(low: Decimal, high: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """The axis's bottom, top and step: round numbers just outside the lowest and highest value.
    A flat line gets room above and below."""
    if high == low:
        pad = nice_step(abs(low) / 10) if low else Decimal(1)
        low, high = low - pad, high + pad
    step = nice_step((high - low) / Y_TICKS)
    bottom = (low / step).to_integral_value(rounding=ROUND_FLOOR) * step
    top = (high / step).to_integral_value(rounding=ROUND_CEILING) * step
    return bottom, top, step


def y_label(value: Decimal, step: Decimal, as_money: bool) -> str:
    exponent = step.normalize().as_tuple().exponent
    places = max(0, -exponent) if isinstance(exponent, int) else 0
    if as_money:
        text = money(value)
        return text.removesuffix(".00") if places == 0 else text
    return f"{value.quantize(Decimal(1).scaleb(-places)):.{places}f}"


def y_ticks(bottom: Decimal, top: Decimal, step: Decimal, as_money: bool) -> list[Tick]:
    ticks: list[Tick] = []
    value = bottom
    while value <= top:
        at = place((top - value) * HUNDRED / (top - bottom))
        ticks.append(Tick(at, y_label(value, step, as_money)))
        value += step
    return ticks


def month_starts(first: date, last: date, every: int) -> list[date]:
    year, month = (first.year, first.month) if first.day == 1 else _next_month(first)
    days: list[date] = []
    while date(year, month, 1) <= last:
        if (month - 1) % every == 0:
            days.append(date(year, month, 1))
        year, month = _next_month(date(year, month, 1))
    return days


def _next_month(day: date) -> tuple[int, int]:
    return (day.year + 1, 1) if day.month == 12 else (day.year, day.month + 1)


def year_starts(first: date, last: date, every: int) -> list[date]:
    year = first.year if (first.month, first.day) == (1, 1) else first.year + 1
    return [date(y, 1, 1) for y in range(year, last.year + 1) if y % every == 0]


def mondays(first: date, last: date) -> list[date]:
    day = first + timedelta(days=(7 - first.weekday()) % 7)
    days: list[date] = []
    while day <= last:
        days.append(day)
        day += timedelta(days=7)
    return days


# The x axis's choices, finest first: the first one with at most `MAX_X_TICKS` labels wins.
X_INTERVALS: tuple[tuple[str, int], ...] = (
    ("week", 1),
    ("month", 1),
    ("month", 2),
    ("month", 3),
    ("month", 6),
    ("year", 1),
    ("year", 2),
    ("year", 5),
    ("year", 10),
    ("year", 25),
)


def tick_label(kind: str, day: date, first: bool = False) -> str:
    """A tick's words. A month carries its year on the first tick and on January only, so the
    labels stay short enough not to touch at 320 pixels wide."""
    if kind == "week":
        return f"{day:%b} {day.day}"
    if kind == "month":
        return f"{day:%b %Y}" if first or day.month == 1 else f"{day:%b}"
    if kind == "year":
        return f"{day.year}"
    return f"{day:%Y-%m-%d}"


def tick_days(kind: str, every: int, first: date, last: date) -> list[date]:
    if kind == "week":
        return mondays(first, last)
    if kind == "month":
        return month_starts(first, last, every)
    return year_starts(first, last, every)


def x_ticks(first: date, last: date) -> list[Tick]:
    """Dates along the bottom: Mondays over a month ("Oct 5"), month starts over a few months
    ("Nov 2025", "Jan 2026", "Mar"), years over a long range ("2020"). Over three labels, every
    other one is hidden on a narrow screen. A range too short for any of them gets its first and
    last day."""
    span = (last - first).days
    if span == 0:
        return [Tick(Decimal(50), tick_label("day", first))]
    kind, days = "day", [first, last]
    for interval, every in X_INTERVALS:
        found = tick_days(interval, every, first, last)
        if len(found) <= MAX_X_TICKS:
            if found:
                kind, days = interval, found
            break
    ticks: list[Tick] = []
    for index, day in enumerate(days):
        at = x_position(day, first, span)
        edge = "start" if at < EDGE_PERCENT else "end" if at > HUNDRED - EDGE_PERCENT else ""
        label = tick_label(kind, day, first=index == 0)
        ticks.append(Tick(at, label, edge, minor=len(days) > 3 and index % 2 == 1))
    return ticks


def x_position(day: date, first: date, span: int) -> Decimal:
    if span == 0:
        return Decimal(50)
    return place(Decimal((day - first).days) * HUNDRED / span)


# --- Lines ---------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SeriesInput:
    """One symbol's stored days in the range, oldest first, and the stored day just before the
    range (for the first day's change), if any."""

    symbol: str
    rows: Sequence[DailyClose]
    previous: DailyClose | None = None


@dataclass(frozen=True, slots=True)
class DayRow:
    """One day of one line, as the table and the hover readout show it."""

    day: date
    close: Decimal
    adj_close: Decimal | None
    value: Decimal  # what the line charts: the adjusted close or the close
    change: Decimal | None  # from the day before, in dollars, on the line's basis
    change_pct: Decimal | None
    index: Decimal | None  # the rebased value, on the compare page
    source: str
    events: tuple[tuple[str, str], ...] = ()  # ("split", "Split 4-for-1"), ("dividend", ...)

    @property
    def index_label(self) -> str:
        return "" if self.index is None else index_text(self.index)

    @property
    def events_text(self) -> str:
        return "; ".join(text for _, text in self.events)


@dataclass(frozen=True, slots=True)
class Marker:
    """A split or a dividend drawn on a line: where, which kind, and its words."""

    symbol: str
    day: date
    kind: str
    text: str
    x: Decimal
    y: Decimal
    color: str

    @property
    def letter(self) -> str:
        return "S" if self.kind == "split" else "D"


@dataclass
class Line:
    symbol: str
    basis: str  # ADJUSTED or CLOSE
    missing_adjusted: int  # days in the range stored without an adjusted close
    color: str
    dash: str
    pattern: str
    days: list[DayRow]
    points: str = ""
    ys: dict[date, Decimal] = field(default_factory=dict[date, Decimal])
    end_x: Decimal = Decimal(0)

    @property
    def first(self) -> DayRow:
        return self.days[0]

    @property
    def last(self) -> DayRow:
        return self.days[-1]

    @property
    def change_pct(self) -> Decimal:
        return change_percent(self.first.value, self.last.value)

    @property
    def end_y(self) -> Decimal:
        return self.ys[self.last.day]

    @property
    def newest_first(self) -> list[DayRow]:
        return list(reversed(self.days))


def line_days(series: SeriesInput, rebase: bool) -> tuple[str, int, list[DayRow]]:
    """The basis, the count of days without an adjusted close, and each day's numbers."""
    missing = sum(1 for row in series.rows if row.adj_close is None)
    basis = ADJUSTED if series.rows and missing == 0 else CLOSE
    pick: Callable[[DailyClose], Decimal] = (
        (lambda row: row.charted) if basis == ADJUSTED else (lambda row: row.close)
    )
    days: list[DayRow] = []
    previous = series.previous
    if previous is not None and basis == ADJUSTED and previous.adj_close is None:
        previous = None  # a change across two bases would be a made-up number
    base = pick(series.rows[0]) if series.rows else Decimal(1)
    for row in series.rows:
        value = pick(row)
        change = change_pct = None
        if previous is not None:
            before = pick(previous)
            change = value - before
            change_pct = change_percent(before, value)
        days.append(
            DayRow(
                day=row.date,
                close=row.close,
                adj_close=row.adj_close,
                value=value,
                change=change,
                change_pct=change_pct,
                index=rebased(value, base) if rebase else None,
                source=row.source,
                events=tuple(day_events(row)),
            )
        )
        previous = row
    return basis, missing, days


@dataclass(frozen=True, slots=True)
class Band:
    """A shaded stretch of the chart (chapter 14): `kind` "window" or "excluded", its words, its
    days, and where it sits, in percent of the plot's width."""

    kind: str
    label: str
    first: date
    last: date
    x: Decimal
    width: Decimal

    @property
    def end_x(self) -> Decimal:
        """The band's right edge: the excluded month's label ends here, so it never runs past
        the plot on the right."""
        return self.x + self.width


@dataclass
class Plot:
    """Everything the chart partial draws, and the data the hover script reads."""

    title: str
    svg_title: str
    y_title: str
    rebase: bool
    lines: list[Line]
    dates: list[date]
    xs: list[Decimal]
    x_ticks: list[Tick]
    y_ticks: list[Tick]
    low: Decimal
    high: Decimal
    sources: str
    markers: list[Marker] = field(default_factory=list[Marker])
    # Every stored date in the range; `dates` is the drawn ones, the same list unless thinned.
    all_dates: list[date] = field(default_factory=list[date])
    # Chapter 14: shaded stretches, such as a 12-1 window; none unless a page adds them.
    bands: list[Band] = field(default_factory=list[Band])

    @property
    def thinned(self) -> bool:
        return len(self.dates) < len(self.all_dates)

    @property
    def total_days(self) -> int:
        return len(self.all_dates)

    @property
    def first(self) -> date:
        return self.dates[0]

    @property
    def last(self) -> date:
        return self.dates[-1]

    @property
    def count(self) -> int:
        """The points drawn, over every line."""
        drawn = set(self.dates)
        return sum(1 for line in self.lines for row in line.days if row.day in drawn)

    @property
    def y_width(self) -> int:
        """The y labels' column, in characters of the axis font."""
        return max((len(tick.label) for tick in self.y_ticks), default=4) + 1

    @property
    def low_text(self) -> str:
        return index_text(self.low) if self.rebase else money(self.low)

    @property
    def high_text(self) -> str:
        return index_text(self.high) if self.rebase else money(self.high)

    @property
    def bases(self) -> str:
        """`adjusted closes`, `closes`, or both when the lines differ."""
        found = sorted({line.basis for line in self.lines})
        return " and ".join(f"{basis}s" for basis in found)

    def hover(self) -> dict[str, object]:
        """The hover script's data: for each date, its place and, per line, the text to show.
        Everything is text the server formatted, so the script never rounds a price."""
        series: list[dict[str, object]] = []
        for line in self.lines:
            by_day = {row.day: row for row in line.days}
            rows = [by_day.get(day) for day in self.dates]
            series.append(
                {
                    "symbol": line.symbol,
                    "basis": line.basis,
                    "color": line.color,
                    "y": [float(line.ys[day]) if day in line.ys else None for day in self.dates],
                    "close": [money(row.close) if row else None for row in rows],
                    "adj": [
                        money(row.adj_close) if row and row.adj_close is not None else None
                        for row in rows
                    ],
                    "change": [
                        signed_money(row.change) if row and row.change is not None else None
                        for row in rows
                    ],
                    "changePct": [
                        percent(row.change_pct) if row and row.change_pct is not None else None
                        for row in rows
                    ],
                    "index": [
                        index_text(row.index) if row and row.index is not None else None
                        for row in rows
                    ],
                    "events": [row.events_text if row and row.events else None for row in rows],
                }
            )
        return {
            "rebased": self.rebase,
            "dates": [f"{day:%Y-%m-%d}" for day in self.dates],
            "x": [float(x) for x in self.xs],
            "series": series,
        }

    @property
    def marker_kinds(self) -> list[tuple[str, str, str]]:
        """The legend's marker entries present on this chart: (kind, letter, words)."""
        kinds = {marker.kind for marker in self.markers}
        legend = [("split", "S", "Split"), ("dividend", "D", "Dividend (ex-date)")]
        return [entry for entry in legend if entry[0] in kinds]

    def daily_rows(self) -> list[tuple[date, list[DayRow | None]]]:
        """Newest first: each date with each line's day, or None where a line has no close."""
        maps = [{row.day: row for row in line.days} for line in self.lines]
        return [(day, [found.get(day) for found in maps]) for day in reversed(self.all_dates)]


def charted_value(row: DayRow, rebase: bool) -> Decimal:
    return row.index if rebase and row.index is not None else row.value


def source_names(lines: Sequence[Line]) -> str:
    names = sorted(
        {SOURCE_NAMES.get(row.source, row.source) for line in lines for row in line.days}
    )
    return " and ".join(names)


def thin(dates: list[date], keep: set[date], limit: int) -> list[date]:
    """At most about `limit` of `dates` (sorted) for drawing: an even spread, plus the first, the
    last and every day in `keep`. Within the limit, all of them."""
    if len(dates) <= limit:
        return dates
    step = len(dates) / (limit - 1)
    spread = {dates[min(len(dates) - 1, round(index * step))] for index in range(limit)}
    return sorted(spread | {dates[0], dates[-1]} | (keep & set(dates)))


def build_plot(
    series: Sequence[SeriesInput], title: str, rebase: bool, max_points: int = MAX_POINTS
) -> Plot | None:
    """One line per series that has a stored day, in the given order, styled by position. No
    days at all, no plot. Over `max_points` dates the drawing is thinned (`thin`)."""
    lines: list[Line] = []
    for series_input in series:
        if not series_input.rows:
            continue
        color, dash, pattern = LINE_STYLES[len(lines) % MAX_LINES]
        basis, missing, days = line_days(series_input, rebase)
        lines.append(Line(series_input.symbol, basis, missing, color, dash, pattern, days))
    if not lines:
        return None
    all_dates = sorted({row.day for line in lines for row in line.days})
    first, last = all_dates[0], all_dates[-1]
    span = (last - first).days
    keep: set[date] = {row.day for line in lines for row in line.days if row.events}
    for line in lines:
        keep.add(min(line.days, key=lambda row: charted_value(row, rebase)).day)
        keep.add(max(line.days, key=lambda row: charted_value(row, rebase)).day)
    dates = thin(all_dates, keep, max_points)
    drawn = set(dates)
    xs = [x_position(day, first, span) for day in dates]
    x_of = {day: x_position(day, first, span) for day in all_dates}
    values = [charted_value(row, rebase) for line in lines for row in line.days]
    low, high = min(values), max(values)
    bottom, top, step = y_scale(low, high)
    for line in lines:
        for row in line.days:
            value = charted_value(row, rebase)
            line.ys[row.day] = place((top - value) * HUNDRED / (top - bottom))
        line.points = " ".join(
            f"{x_of[row.day]},{line.ys[row.day]}" for row in line.days if row.day in drawn
        )
        line.end_x = x_of[line.last.day]
    markers = sorted(
        (
            Marker(line.symbol, row.day, kind, text, x_of[row.day], line.ys[row.day], line.color)
            for line in lines
            for row in line.days
            for kind, text in row.events
        ),
        key=lambda marker: (marker.day, marker.symbol, marker.kind),
    )
    if rebase:
        y_title = "Value, with each line's first day in the range at 100"
    else:
        y_title = f"{'Adjusted close' if lines[0].basis == ADJUSTED else 'Close'}, US dollars"
    count = sum(len(line.days) for line in lines)
    svg_title = (
        f"{title}: {count} close{'' if count == 1 else 's'} from {first:%Y-%m-%d} to "
        f"{last:%Y-%m-%d}, low {index_text(low) if rebase else money(low)}, "
        f"high {index_text(high) if rebase else money(high)}"
    )
    return Plot(
        title=title,
        svg_title=svg_title,
        y_title=y_title,
        rebase=rebase,
        lines=lines,
        dates=dates,
        xs=xs,
        x_ticks=x_ticks(first, last),
        y_ticks=y_ticks(bottom, top, step, as_money=not rebase),
        low=low,
        high=high,
        sources=source_names(lines),
        markers=markers,
        all_dates=all_dates,
    )


def band(plot: Plot, kind: str, label: str, first: date, last: date) -> Band | None:
    """A shaded stretch from `first` to `last`, clipped to the plot's stored days; None when the
    stretch falls wholly outside them, so a chart of 30 days never shades a year it cannot show."""
    start, end = plot.all_dates[0], plot.all_dates[-1]
    first, last = max(first, start), min(last, end)
    if first > last:
        return None
    span = (end - start).days
    x = x_position(first, start, span)
    width = max(x_position(last, start, span) - x, Decimal("0.5"))
    return Band(kind, label, first, last, min(x, HUNDRED - width), width)
```

Listing 14-20, Filename: `src/invest_witus_site/prices/templates/prices/_chart.html`:

```html
{% load static %}
{# The owner's price chart (2026-10-29, decisions 133 to 138), from `prices/charts.py`'s `Plot`. Included with `plot`. #}
{# The plot is an SVG whose viewBox runs 0 to 100 both ways, stretched to its box; the axes are HTML placed by #}
{# the same percentages, so their text stays readable on a phone. The table the page puts under the chart is the #}
{# text alternative. The hover script is served here, so only an owner chart page carries it. #}
<figure class="chart" aria-labelledby="chart-heading">
  <figcaption class="chart-caption">
    <p class="chart-title" id="chart-heading">{{ plot.title }}</p>
    <p class="small muted">{% if plot.rebase %}Each line is its symbol's {{ plot.bases }}, rebased so its first day in the range is 100: 110 means ten percent above where it started, whatever the price.{% else %}{{ plot.y_title }}.{% endif %} Daily closes from {{ plot.sources }}, as of {{ plot.last|date:"Y-m-d" }}.</p>
  </figcaption>
  <ul class="legend" aria-label="Key">
    {% for line in plot.lines %}
    <li><svg class="swatch" viewBox="0 0 36 10" width="36" height="10" aria-hidden="true" focusable="false"><line x1="1" y1="5" x2="35" y2="5" stroke="{{ line.color }}" stroke-width="3"{% if line.dash %} stroke-dasharray="{{ line.dash }}"{% endif %}/></svg>{{ line.symbol }} <span class="muted">({{ line.basis }}, {{ line.pattern }} line)</span></li>
    {% endfor %}
    {% for shaded in plot.bands %}
    <li><span class="band-key band-key-{{ shaded.kind }}" aria-hidden="true"></span>{{ shaded.label }}, {{ shaded.first|date:"Y-m-d" }} to {{ shaded.last|date:"Y-m-d" }}</li>
    {% endfor %}
    {% for kind, letter, words in plot.marker_kinds %}
    <li><span class="marker-key marker-{{ kind }}" aria-hidden="true">{{ letter }}</span>{{ words }}</li>
    {% endfor %}
  </ul>
  <div class="chart-frame" style="--y-width: {{ plot.y_width }}ch">
    <p class="axis-title axis-y">{{ plot.y_title }}</p>
    <div class="chart-y" aria-hidden="true">
      {% for tick in plot.y_ticks %}<span style="top: {{ tick.at }}%">{{ tick.label }}</span>{% endfor %}
    </div>
    <div class="chart-plot" data-chart="chart-data" data-readout="chart-readout">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-labelledby="chart-title chart-desc" data-points="{{ plot.count }}">
        <title id="chart-title">{{ plot.svg_title }}</title>
        <desc id="chart-desc">{% if plot.rebase %}One line per symbol, oldest day on the left, each rebased to 100 on its first day in the range.{% else %}A line of the stored {{ plot.bases }}, oldest on the left.{% endif %}{% if plot.markers %} Letters on the line mark splits (S) and dividends (D).{% endif %}{% for shaded in plot.bands %} Shaded: {{ shaded.label }}, {{ shaded.first|date:"Y-m-d" }} to {{ shaded.last|date:"Y-m-d" }}.{% endfor %} The tables below list every value in the chart.</desc>
        {% for shaded in plot.bands %}<rect class="chart-band-{{ shaded.kind }}" x="{{ shaded.x }}" y="0" width="{{ shaded.width }}" height="100" vector-effect="non-scaling-stroke"/>{% endfor %}
        {% for tick in plot.y_ticks %}<line class="grid" x1="0" x2="100" y1="{{ tick.at }}" y2="{{ tick.at }}" vector-effect="non-scaling-stroke"/>{% endfor %}
        {% for tick in plot.x_ticks %}<line class="grid" x1="{{ tick.at }}" x2="{{ tick.at }}" y1="0" y2="100" vector-effect="non-scaling-stroke"/>{% endfor %}
        {% for line in plot.lines %}
        <polyline points="{{ line.points }}" fill="none" stroke="{{ line.color }}" stroke-width="2"{% if line.dash %} stroke-dasharray="{{ line.dash }}"{% endif %} stroke-linejoin="round" vector-effect="non-scaling-stroke" data-symbol="{{ line.symbol }}"/>
        {% endfor %}
      </svg>
      {% for shaded in plot.bands %}<span class="chart-band-label chart-band-label-{{ shaded.kind }}" style="left: {% if shaded.kind == "excluded" %}{{ shaded.end_x }}{% else %}{{ shaded.x }}{% endif %}%" aria-hidden="true">{{ shaded.label }}</span>{% endfor %}
      {% for line in plot.lines %}<span class="chart-end" style="left: {{ line.end_x }}%; top: {{ line.end_y }}%; background: {{ line.color }}" aria-hidden="true"></span>{% endfor %}
      {% for marker in plot.markers %}<span class="chart-marker marker-{{ marker.kind }}" style="left: {{ marker.x }}%; top: {{ marker.y }}%; border-color: {{ marker.color }}" title="{{ marker.symbol }} {{ marker.day|date:'Y-m-d' }}: {{ marker.text }}" aria-hidden="true">{{ marker.letter }}</span>{% endfor %}
    </div>
    <div class="chart-x" aria-hidden="true">
      {% for tick in plot.x_ticks %}<span class="{{ tick.edge }}{% if tick.minor %} minor{% endif %}" style="left: {{ tick.at }}%">{{ tick.label }}</span>{% endfor %}
    </div>
    <p class="axis-title axis-x">Date</p>
  </div>
  <div class="chart-readout" id="chart-readout" aria-live="polite" hidden></div>
</figure>
{% if plot.markers %}
<table class="holdings events">
  <caption>Splits and dividends from {{ plot.first|date:"Y-m-d" }} to {{ plot.last|date:"Y-m-d" }}</caption>
  <thead>
    <tr>
      <th scope="col">Date</th>
      <th scope="col">Symbol</th>
      <th scope="col">Event</th>
    </tr>
  </thead>
  <tbody>
    {% for marker in plot.markers %}
    <tr>
      <th scope="row">{{ marker.day|date:"Y-m-d" }}</th>
      <td>{{ marker.symbol }}</td>
      <td>{{ marker.text }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
<p class="small muted">From the price source's split factor and cash dividend for each day; a dividend is listed on its ex-date. The adjusted close already accounts for both.</p>
{% endif %}
{{ plot.hover|json_script:"chart-data" }}
<script src="{% static 'prices/chart.js' %}" defer></script>
```

The history page adds the bands when the account runs momentum, and a section with the symbol's number and its
note:

Listing 14-21, Filename: `src/invest_witus_site/watchlist/views.py`:

```python
"""Two POST views on the signed-in owner's account page: add one or many symbols, remove one.
Since 2026-10-29, two GET views too: a watched symbol's stored closes, and the compare page, up to
six of the account's symbols on one chart rebased to 100. Both open on 30, 90 or 365 days and
offer 5 years, 10 years, All and a From and To pair (decision 140); a bad pair is a 400 with the
reason on the page and the default range under it. Their day-by-day tables show 100 rows a page.

Both check ownership the way chapter 08's pages do: the account comes from
`get_object_or_404(Account, pk=pk, owner=request.user)`, so another owner's account is a 404.
Both finish with a redirect to the account page (Post/Redirect/Get, as chapter 04's waitlist),
carrying their report in Django's messages, which the base template prints once.
"""

from dataclasses import dataclass, field
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Page, Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from invest_witus.valuation import STALE_AFTER_DAYS, is_stale
from invest_witus_site.holdings.models import Account, Holding
from invest_witus_site.holdings.views import account_page
from invest_witus_site.methods.models import MethodPlan
from invest_witus_site.methods.momentum import HistoryWindow, history_window
from invest_witus_site.prices.charts import MAX_LINES, MAX_POINTS, SeriesInput, band, build_plot
from invest_witus_site.prices.history import (
    COMPARE_DEFAULT_RANGE,
    DEFAULT_RANGE,
    PRESETS,
    ChosenRange,
    RangeError,
    StoredSpan,
    chosen_range,
    close_before,
    closes_between,
    preset_key,
    preset_range,
    stored_span,
)
from invest_witus_site.prices.manual import DEFAULT_HISTORY_RANGE, HISTORY_RANGES
from invest_witus_site.prices.models import DailyClose
from invest_witus_site.prices.owner_views import run_history_many
from invest_witus_site.watchlist.forms import WatchForm
from invest_witus_site.watchlist.models import WatchItem


@login_required
@require_POST
def add(request: HttpRequest, pk: int) -> HttpResponse:
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    form = WatchForm(request.POST)
    if not form.is_valid():
        # Nothing could be added: the account page again, with the reason beside the box.
        return account_page(request, account, form)
    parsed = form.cleaned_data["symbols"]
    report = WatchItem.add_many(account, parsed.symbols, form.cleaned_data["note"])
    if report.added:
        messages.success(request, f"Added to the watch list: {', '.join(report.added)}.")
    if report.existing:
        messages.info(request, f"Already on the watch list: {', '.join(report.existing)}.")
    if parsed.refused:
        reasons = "; ".join(f"{token} ({reason})" for token, reason in parsed.refused)
        messages.error(request, f"Refused: {reasons}.")
    if form.cleaned_data["fetch_history"] and report.added:
        # The symbols this submission added, through Get history for several symbols (2026-10-29):
        # one request each within the run's budget and time limit, each symbol's guard kept.
        choice = form.cleaned_data["history_range"] or DEFAULT_HISTORY_RANGE
        run_history_many(request, report.added, choice)
    return redirect("account-detail", pk=account.pk)


@login_required
@require_POST
def remove(request: HttpRequest, pk: int, item_pk: int) -> HttpResponse:
    """The row is looked up inside the account named in the URL, so an id from another
    account, the owner's own or anyone else's, is a 404. Stored closes are not touched: the
    table of prices is the pull's, and a symbol may be watched again or held tomorrow."""
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    item = get_object_or_404(WatchItem, pk=item_pk, account=account)
    item.delete()
    messages.success(request, f"Removed {item.symbol} from the watch list.")
    return redirect("account-detail", pk=account.pk)


# The day-by-day tables under a chart show this many rows a page (`?page=`).
ROWS_PER_PAGE = 100


@dataclass(frozen=True, slots=True)
class RangeChoice:
    """The range a chart page shows, and what the picker needs: an error to print (the page then
    shows the default range and answers 400), the From and To typed, and the stored span that
    bounds the date inputs."""

    chosen: ChosenRange
    error: str
    typed_from: str
    typed_to: str
    span: StoredSpan


def read_range(request: HttpRequest, symbols: list[str], default: int) -> RangeChoice:
    today = timezone.localdate()
    span = stored_span(symbols)
    typed_from = (request.GET.get("from") or "").strip()
    typed_to = (request.GET.get("to") or "").strip()
    try:
        chosen = chosen_range(request.GET, today, span, default=default)
        error = ""
    except RangeError as refused:
        chosen = preset_range(preset_key(None, default), today)
        error = str(refused)
    return RangeChoice(chosen, error, typed_from, typed_to, span)


def range_context(choice: RangeChoice, plot_dates: int, thinned: bool) -> dict[str, object]:
    return {
        "chosen": choice.chosen,
        "range_error": choice.error,
        # The date inputs keep what was typed, so a refused pair can be corrected in place.
        "typed_from": choice.typed_from,
        "typed_to": choice.typed_to,
        "span": choice.span,
        "presets": PRESETS,
        "plot_dates": plot_dates,
        "thinned": thinned,
        "max_points": MAX_POINTS,
        "rows_per_page": ROWS_PER_PAGE,
    }


def page_of[T](rows: list[T], number: str | None) -> Page[T]:
    """One page of a table's rows; a page number out of range is the nearest page."""
    return Paginator(rows, ROWS_PER_PAGE).get_page(number)


@login_required
@require_GET
def history(request: HttpRequest, pk: int, symbol: str) -> HttpResponse:
    """A watched symbol's closes: a labelled line chart with a key and a hover readout, and the
    same days as a table (100 rows a page), over the range from `?days=` (30, 90, 365, 5y, 10y or
    all) or `?from=` and `?to=`. The symbol must be on this account's watch list, and the account
    the signed-in owner's; anything else is a 404. The "as of" line is the newest stored close,
    with chapter 08's stale rule, even when it falls before the range."""
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    item = get_object_or_404(WatchItem, account=account, symbol=symbol.strip().upper())
    choice = read_range(request, [item.symbol], DEFAULT_RANGE)
    chosen = choice.chosen
    closes = closes_between(item.symbol, chosen.since, chosen.until)
    series = SeriesInput(item.symbol, closes, close_before(item.symbol, chosen.since))
    plot = build_plot([series], f"{item.symbol}, {chosen.title}", rebase=False)
    line = plot.lines[0] if plot else None
    window = momentum_window(account, item.symbol, timezone.localdate())
    if plot is not None and window is not None:
        shaded = (
            band(plot, "window", "12-1 window", window.first, window.last),
            band(plot, "excluded", "excluded", window.excluded_first, window.excluded_last),
        )
        plot.bands = [each for each in shaded if each is not None]
    latest = DailyClose.latest_for([item.symbol]).get(item.symbol)
    today = timezone.localdate()
    context = {
        "account": account,
        "item": item,
        "plot": plot,
        "line": line,
        "rows": page_of(line.newest_first if line else [], request.GET.get("page")),
        "latest": latest,
        "stale": latest is not None and is_stale(latest, today),
        "stale_after_days": STALE_AFTER_DAYS,
        "history_ranges": [(value, label) for value, (label, _) in HISTORY_RANGES.items()],
        **range_context(choice, plot.total_days if plot else 0, bool(plot and plot.thinned)),
        # Chapter 14: this month's 12-1 window, on an account running 12-1 momentum only, and
        # the From and To that show all of it when the stored closes reach back that far.
        "momentum_window": window,
        "window_query": window_query(window, choice.span) if window is not None else "",
    }
    status = 400 if choice.error else 200
    return render(request, "watchlist/history.html", context, status=status)


def momentum_window(account: Account, symbol: str, today: date) -> HistoryWindow | None:
    plan = MethodPlan.active_for(account)
    if plan is None or not plan.is_momentum:
        return None
    return history_window(symbol, today)


def window_query(window: HistoryWindow, span: StoredSpan) -> str:
    """`from=...&to=...` covering the window and the excluded month, or "" when the stored closes
    do not reach the window's start (the range would be refused)."""
    if span.first is None or span.last is None or span.first > window.first:
        return ""
    until = span.last
    if until <= window.first:
        return ""
    return f"from={window.first:%Y-%m-%d}&to={until:%Y-%m-%d}"


def compare_choices(account: Account) -> list[str]:
    """The symbols the compare page offers for this account: its watch list and its holdings
    (cash has no price), each once, sorted."""
    watched = WatchItem.objects.filter(account=account).values_list("symbol", flat=True)
    held = (
        Holding.objects.filter(account=account)
        .exclude(kind=Holding.Kind.CASH)
        .values_list("symbol", flat=True)
    )
    return sorted(set(watched) | set(held))


@dataclass
class Picked:
    """The symbols asked for, sorted out: the ones charted (in the order asked, at most
    `MAX_LINES`), the ones this account does not watch or hold, and the ones over the limit."""

    symbols: list[str] = field(default_factory=list[str])
    not_allowed: list[str] = field(default_factory=list[str])
    over_limit: list[str] = field(default_factory=list[str])


def pick_symbols(asked: list[str], allowed: list[str]) -> Picked:
    """`?symbols=A,B,C`, or the form's `?symbols=A&symbols=B`, or both: split on commas, upper
    case, each once in the order asked."""
    picked = Picked()
    seen: set[str] = set()
    for value in asked:
        for token in value.split(","):
            symbol = token.strip().upper()
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            if symbol not in allowed:
                picked.not_allowed.append(symbol)
            elif len(picked.symbols) >= MAX_LINES:
                picked.over_limit.append(symbol)
            else:
                picked.symbols.append(symbol)
    return picked


@login_required
@require_GET
def compare(request: HttpRequest, pk: int) -> HttpResponse:
    """Up to six of this account's watched or held symbols on one chart, each rebased to 100 on
    its first stored day in the range, with a table of start, end and change per symbol. The
    account must be the signed-in owner's (404 otherwise); a symbol it neither watches nor holds
    is named and left out, never charted. The range works as on the history page, bounded by the
    stored closes of the symbols picked; each line is rebased on its first stored day in it."""
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    allowed = compare_choices(account)
    picked = pick_symbols(request.GET.getlist("symbols"), allowed)
    choice = read_range(request, picked.symbols or allowed, COMPARE_DEFAULT_RANGE)
    chosen = choice.chosen
    series = [
        SeriesInput(
            symbol,
            closes_between(symbol, chosen.since, chosen.until),
            close_before(symbol, chosen.since),
        )
        for symbol in picked.symbols
    ]
    plot = build_plot(series, f"{', '.join(picked.symbols)}: {chosen.title}", rebase=True)
    charted = {line.symbol for line in plot.lines} if plot else set[str]()
    page = request.GET.get("page")
    context = {
        "account": account,
        "allowed": allowed,
        "picked": picked,
        "symbols_query": ",".join(picked.symbols),
        "empty": [symbol for symbol in picked.symbols if symbol not in charted],
        "max_lines": MAX_LINES,
        "plot": plot,
        "daily": page_of(plot.daily_rows() if plot else [], page),
        "daily_open": page is not None,
        "starts_differ": plot is not None and len({line.first.day for line in plot.lines}) > 1,
        **range_context(choice, plot.total_days if plot else 0, bool(plot and plot.thinned)),
    }
    status = 400 if choice.error else 200
    return render(request, "watchlist/compare.html", context, status=status)
```

Listing 14-22, Filename: `src/invest_witus_site/watchlist/templates/watchlist/_momentum_window.html`:

```html
{% load holdings_extras %}
{# This month's 12-1 window on a watched symbol's chart (chapter 14), on an account running 12-1 momentum. #}
{# Included by watchlist/history.html with `window` (a HistoryWindow), `item`, `account` and `window_query`. #}
<section aria-labelledby="window-heading">
  <h2 id="window-heading">The 12-1 window for {{ window.month }}</h2>
  {% if window.score %}
  <p>{{ item.symbol }}'s 12-1 return for {{ window.month }}: <strong>{{ window.change_text }}</strong>, from {{ window.score.start_close|money }} on {{ window.score.start_day|date:"Y-m-d" }} to {{ window.score.end_close|money }} on {{ window.score.end_day|date:"Y-m-d" }}.</p>
  {% else %}
  <p>{{ item.symbol }} is not ranked for {{ window.month }}: {{ window.result.reason }}.</p>
  {% endif %}
  <p class="how-to-read"><strong>How to read this.</strong> The darker shading is the 12-1 window, from the last close of {{ window.start }} to the last close of {{ window.end }}; the return is the change between its two ends, read on the adjusted close. The lighter strip with a dashed edge is {{ window.excluded }}, the latest full month, labelled "excluded": the method leaves it out, so what happened in it does not move the rank. A range shorter than the window shows only the part inside it. <span class="muted">Lesson coming.</span></p>
  {% if window_query %}<p><a href="?{{ window_query }}">Show the whole window</a></p>{% else %}<p class="small">The stored closes do not reach back to {{ window.first|date:"Y-m-d" }}. <strong>Get history</strong> below with 5 years fetches them.</p>{% endif %}
</section>
```

The watch list's column needs a dictionary lookup by a variable, which Django's templates do not do, so
`holdings_extras` gains one small filter:

Listing 14-23, Filename: `src/invest_witus_site/holdings/templatetags/holdings_extras.py`:

```python
"""Template filters for the holdings pages. `{% load holdings_extras %}` makes them available."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django import template

register = template.Library()

CENT = Decimal("0.01")
# Shares are stored to six places (chapter 05's share step), so a count shows at most six.
SHARE_STEP = Decimal("0.000001")


def as_decimal(value: Decimal | int | str) -> Decimal | None:
    """A Decimal as it is; an int or a numeric string through `Decimal(str(...))`, never through
    a float. Anything else is None, so a filter shows the empty text instead of an error page."""
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


@register.filter
def signed(value: Decimal | None) -> str:
    """A change with its sign: `+1.500000`, `-500.00`, or plain `0.00`. None: the statement
    did not show the number, so there is nothing to compare."""
    if value is None:
        return "not shown"
    if value == 0:
        return str(value)
    return f"{value:+}"


@register.filter
def plain_number(value: Decimal | None) -> str:
    """A Decimal without the column's trailing zeros, with at least two places: `2.500000`
    becomes `2.50`, `101.230000` becomes `101.23`, `12.3456` stays, `1` becomes `1.00`."""
    if value is None:
        return ""
    text = f"{value:f}"
    whole, point, fraction = text.partition(".")
    fraction = fraction.rstrip("0") if point else ""
    return f"{whole}.{fraction.ljust(2, '0')}"


@register.filter
def money(value: Decimal | int | str | None) -> str:
    """US dollars to the cent, halves rounded up and away from zero, with thousands commas:
    `1234.5` is `$1,234.50`, `-1234.565` is `-$1,234.57`, `0.004` is `$0.00`. None is empty,
    as `plain_number` leaves it, so a template's own "not set" text stays in charge."""
    if value is None:
        return ""
    number = as_decimal(value)
    if number is None:
        return ""
    cents = number.quantize(CENT, rounding=ROUND_HALF_UP)
    # A value that rounds to zero is $0.00, never -$0.00.
    sign = "-" if cents < 0 else ""
    return f"{sign}${abs(cents):,.2f}"


@register.filter
def quantity(value: Decimal | int | str | None) -> str:
    """A share count with thousands commas and up to six places, trailing zeros dropped:
    `1234.500000` is `1,234.5`, `0.123456` stays, `10.000000` is `10`. None is empty."""
    if value is None:
        return ""
    number = as_decimal(value)
    if number is None:
        return ""
    shares = number.quantize(SHARE_STEP, rounding=ROUND_HALF_UP)
    sign = "-" if shares < 0 else ""
    text = f"{abs(shares):,f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return f"{sign}{text}"


@register.filter
def signed_money(value: Decimal | None) -> str:
    """A change in dollars with its sign (2026-10-29): `+$34.50`, `-$1,234.57`, `$0.00`. None
    is empty."""
    if value is None:
        return ""
    text = money(value)
    return text if text.startswith("-") or text == "$0.00" else f"+{text}"


@register.filter
def percent(value: Decimal | None) -> str:
    """A change in percent to two places with its sign (2026-10-29): `+2.88%`, `-0.50%`,
    `0.00%`. None is empty."""
    if value is None:
        return ""
    rounded = value.quantize(CENT, rounding=ROUND_HALF_UP)
    return "0.00%" if rounded == 0 else f"{rounded:+.2f}%"


@register.filter
def item(mapping: object, key: object) -> object:
    """`{{ badges|item:row.item.symbol }}`: a dictionary's value for a key the template holds in
    a variable, or None (chapter 14, the watch list's 12-1 badges)."""
    return mapping.get(key) if isinstance(mapping, dict) else None  # type: ignore[union-attr]
```

Listing 14-24, Filename: `src/invest_witus_site/watchlist/templates/watchlist/_section.html`:

```html
{% load holdings_extras %}
{# The watch list section of the account page (chapter 09). Included by holdings/account_detail.html #}
{# with `account`, `watch` (the rows with their quotes), `watch_form` and `history_ranges` (2026-10-29). #}
{# Since 2026-10-29 each row's History cell starts with a checkbox for Fetch history for selected; the boxes #}
{# belong to the `bulk-history` form under the table through their `form` attribute, since a form cannot hold #}
{# the row forms. #}
<section class="watch" aria-labelledby="watch-heading">
  <h2 id="watch-heading">Watch list</h2>
  {% if watch.rows %}
  <div class="table-scroll" role="region" aria-label="Watch list table, scrolls sideways on a narrow screen" tabindex="0">
  <table class="holdings">
    <caption class="sr-only">Symbols you follow in this account, with the latest stored close</caption>
    <thead>
      <tr>
        <th scope="col">Symbol</th>
        <th scope="col">Note</th>
        <th scope="col" class="num">Close</th>
        <th scope="col">As of</th>
        <th scope="col">Source</th>
        {% if momentum_badges is not None %}<th scope="col">12-1 return</th>{% endif %}
        <th scope="col">History</th>
        <th scope="col"><span class="sr-only">Remove</span></th>
      </tr>
    </thead>
    <tbody>
      {% for row in watch.rows %}
      <tr>
        <th scope="row"><a href="{% url 'watch-history' account.pk row.item.symbol %}">{{ row.item.symbol }}</a></th>
        <td>{{ row.item.note }}</td>
        {% if row.quote %}
        <td class="num">{{ row.quote.close|money }}</td>
        <td>{{ row.quote.as_of|date:"Y-m-d" }}{% if row.stale %} <span class="stale">stale</span>{% endif %}</td>
        <td>{{ row.quote.source }}</td>
        {% else %}
        <td class="muted" colspan="3">no price yet</td>
        {% endif %}
        {% if momentum_badges is not None %}{% with badge=momentum_badges|item:row.item.symbol %}<td>{% if badge.direction == "none" %}<span class="muted" title="{{ badge.reason }}">not ranked</span>{% else %}<span class="momentum-badge momentum-{{ badge.direction }}">{{ badge.text }}</span>{% endif %}</td>{% endwith %}{% endif %}
        <td class="history-cell"><label class="pick-label"><input type="checkbox" name="symbols" value="{{ row.item.symbol }}" form="bulk-history" class="pick"><span class="sr-only">Select {{ row.item.symbol }} for Fetch history for selected</span></label>{% include "prices/_history_form.html" with symbol=row.item.symbol return_to="account" %}</td>
        <td>
          <form method="post" action="{% url 'watch-remove' account.pk row.item.pk %}">
            {% csrf_token %}
            <button type="submit" class="link-button">Remove <span class="sr-only">{{ row.item.symbol }}</span></button>
          </form>
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  </div>
  <form method="post" action="{% url 'watch-fetch-history-many' account.pk %}" id="bulk-history" class="history-form bulk-history">
    {% csrf_token %}
    <label for="bulk-history-range">History range</label>
    <select name="range" id="bulk-history-range">
      {% for value, label in history_ranges %}<option value="{{ value }}">{{ label }}</option>{% endfor %}
    </select>
    <label for="bulk-history-typed">Or type symbols</label>
    <input type="text" name="typed" id="bulk-history-typed" class="typed-symbols" autocomplete="off" autocapitalize="characters" spellcheck="false" aria-describedby="bulk-history-help">
    <button type="submit" name="which" value="selected">Fetch history for selected</button>
    <button type="submit" name="which" value="all">Fetch history for all</button>
  </form>
  <p class="small muted" id="bulk-history-help">Get history for several symbols in one press: tick symbols in the History column or type them, separated by commas or spaces (only symbols on this list), or press for all. One request per symbol, at most 50, within four minutes; a symbol fetched in the last 10 minutes is skipped and named.</p>
  {% if momentum_badges is not None %}<p class="how-to-read"><strong>How to read this.</strong> The 12-1 return is each symbol's change in adjusted close over this month's 12-1 window: from the end of the month 13 months back to the end of the month 2 months back, leaving out the latest full month. The arrow and the word say which way it went; the number says how far. "Not ranked" means a close is missing at one end of the window. The method page ranks your plan's candidates by this number. <span class="muted">Lesson coming.</span></p>{% endif %}
  <p><a href="{% url 'compare' account.pk %}?symbols={% for row in watch.rows|slice:":6" %}{{ row.item.symbol }}{% if not forloop.last %},{% endif %}{% endfor %}">Compare these symbols on one chart</a></p>
  {% if watch.unpriced %}
  <p class="muted">Prices arrive after the nightly pull: no close is stored yet for {{ watch.unpriced|join:", " }}. Press <strong>Fetch prices now</strong> to ask for them without waiting. A symbol the price source does not know stays unpriced; the pull's log names it.</p>
  {% endif %}
  {% else %}
  <p>Nothing on the watch list yet.</p>
  {% endif %}
  {% url 'account-fetch-prices' account.pk as fetch_action %}
  {% include "prices/_fetch_now.html" with action=fetch_action %}
  <form method="post" action="{% url 'watch-add' account.pk %}" class="watch-form" novalidate>
    {% csrf_token %}
    <div class="field">
      <label for="{{ watch_form.symbols.id_for_label }}">Symbols</label>
      {{ watch_form.symbols }}
      {{ watch_form.symbols.errors }}
      <p class="small muted">One or more, separated by commas or spaces. Letters, digits, a dot and a hyphen; up to twelve characters each.</p>
    </div>
    <div class="field">
      <label for="{{ watch_form.note.id_for_label }}">Note (optional)</label>
      {{ watch_form.note }}
      {{ watch_form.note.errors }}
    </div>
    <div class="field add-history">
      <label class="check-label" for="{{ watch_form.fetch_history.id_for_label }}">{{ watch_form.fetch_history }} Fetch their history now</label>
      <label for="{{ watch_form.history_range.id_for_label }}">History range</label>
      {{ watch_form.history_range }}
      <p class="small muted">Ticked, the symbols this adds are fetched right away, one request each, like Fetch history for selected. Unticked, their prices arrive with the nightly pull or Fetch prices now.</p>
    </div>
    <button type="submit">Add to the watch list</button>
  </form>
  <p class="small muted">Watching a symbol places no order and recommends nothing. A symbol reaches a plan only when you add it to the plan's universe. Information, not advice.</p>
</section>
```

`holdings/views.py` passes `momentum_badges` (or `None` for an account without momentum), `history.html` includes
the window partial under the chart, and `site.css` gets the bar, band and badge styles. The home page's line about
methods now names both.

### 14.11 Buys on paper

Listing 14-25, Filename: `src/invest_witus_site/paper/orders.py`:

```python
"""The monthly review's buys on a paper account: stage them from the plan, place them when the owner
confirms, and copy Alpaca's answers back into the journal.

Three jobs, in the order they happen:

1. `month_buys` stages this month's buys from the active plan: the plan's amount split across its
   symbols to the cent, each with its deterministic `client_order_id`, and the one reason, if any,
   that Confirm is not offered (outside the window, no practice budget, over the budget, a buy
   already logged by hand, a skip logged for the month, more than one symbol). Chapter 12: when
   the month's order ended with nothing filled, the buy is staged again as a new attempt with its
   own id, and the button reads "Place again".
2. `confirm` places what is staged and not yet placed, one order per symbol, and writes one
   journal entry per order. A second click, a retry after a timeout, or two clicks at once find
   the same row (unique `client_order_id`) and the same Alpaca order, so nothing is bought twice.
3. `sync_orders` reads every open order back from Alpaca and fixes its row and its journal entry:
   the shares filled, the amount, and no entry at all for an order that ended with nothing filled.

Nothing here runs without the owner's click except the sync, which only reads.

Chapter 14: a 12-1 momentum plan stages a buy for each of this month's top N, the plan's amount in
equal parts in rank order, through the same ids, Confirm and sync. Only buys: a holding that left
the top N is listed on the method page to be sold by hand (decision 146).
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.db import transaction
from django.utils import timezone

from invest_witus.money import CENT, to_money, to_shares
from invest_witus_site.holdings.models import Account
from invest_witus_site.holdings.templatetags.holdings_extras import money
from invest_witus_site.methods.models import SKIP, JournalEntry, MethodPlan
from invest_witus_site.methods.momentum import plan_ranking
from invest_witus_site.paper.alpaca import (
    PAPER_HOST,
    AlpacaError,
    AlpacaNotFound,
    AlpacaPaper,
    AlpacaRateLimited,
    AlpacaRefused,
    MarketClock,
    PaperOrderState,
    paper_client,
)
from invest_witus_site.paper.models import PaperOrder, client_order_id

ZERO = Decimal("0")
NOTE_LIMIT = 200


def today() -> date:
    """The app's today. A function, so a test can fix the day the way chapter 03's `--through`
    fixed the review's."""
    return timezone.localdate()


def month_of(day: date) -> str:
    return f"{day.year}-{day.month:02d}"


def alpaca_allowed(user: AbstractBaseUser | AnonymousUser, account: Account) -> bool:
    """Alpaca is the site owner's: the server holds one pair of paper keys, so only a superuser,
    on an account linked to Alpaca paper, may read it or place orders through it. The caller has
    already fetched the account with `owner=request.user`."""
    return account.is_alpaca_paper and getattr(user, "is_superuser", False) is True


# --- 1. Stage -----------------------------------------------------------------------------------


def split_amount(amount: Decimal, symbols: list[str]) -> list[tuple[str, Decimal]]:
    """The amount in equal parts to the cent, one per symbol, in the plan's order. The cents that
    do not divide go one each to the first symbols, so the parts add up to the amount exactly:
    100.00 over three symbols is 33.34, 33.33 and 33.33."""
    if not symbols:
        raise ValueError("no symbols to split across")
    cents = int(to_money(amount) / CENT)
    each, left_over = divmod(cents, len(symbols))
    return [
        (symbol, (each + (1 if index < left_over else 0)) * CENT)
        for index, symbol in enumerate(symbols)
    ]


def practice_spent(plan: MethodPlan) -> Decimal:
    """What the plan has spent of its practice budget: every buy in the account's journal since
    the plan started, placed through Alpaca or logged by hand. A pending order has its entry
    already, so its money is spent the moment it is placed. Chapter 12: since the plan's first
    version started, so a change of amount does not reset what was spent."""
    buys = JournalEntry.objects.filter(
        account=plan.account, action="buy", date__gte=plan.chain_start()
    ).values_list("amount", flat=True)
    return sum((amount for amount in buys if amount is not None), ZERO)


@dataclass(frozen=True, slots=True)
class StagedBuy:
    """One symbol's buy this month. `order` is the row for this `client_order_id`, if any;
    `previous` is the attempt before it, set only when that one ended with nothing filled."""

    symbol: str
    notional: Decimal
    client_order_id: str
    order: PaperOrder | None
    attempt: int = 1
    previous: PaperOrder | None = None

    @property
    def placed(self) -> bool:
        return self.order is not None and self.order.placed


@dataclass(frozen=True, slots=True)
class MonthBuys:
    """This month's buys for one plan, and why Confirm is not offered, in words, when it is not."""

    month: str
    window_closes: date
    buys: list[StagedBuy]
    total: Decimal
    budget: Decimal | None
    spent: Decimal
    refusal: str

    @property
    def left(self) -> Decimal | None:
        return None if self.budget is None else self.budget - self.spent

    @property
    def to_place(self) -> list[StagedBuy]:
        return [buy for buy in self.buys if not buy.placed]

    @property
    def can_confirm(self) -> bool:
        return not self.refusal and bool(self.to_place)

    @property
    def placing_again(self) -> bool:
        """The button says "Place again" when what it places replaces an unfilled order."""
        return any(buy.previous is not None for buy in self.to_place)


def staged(plan: MethodPlan, month: str, symbol: str, notional: Decimal) -> StagedBuy:
    """The buy for one symbol: the newest attempt's row, or, when that attempt ended with nothing
    filled, the next attempt with its own id. The attempt number comes from the rows, so two
    clicks on "Place again" compute the same id and the unique column keeps it to one order."""
    attempts = [order for order in PaperOrder.for_month(plan, month) if order.symbol == symbol]
    latest = attempts[-1] if attempts else None
    account_pk = plan.account.pk
    if latest is not None and latest.ended_unfilled:
        attempt = latest.attempt + 1
        cid = client_order_id(account_pk, plan.pk, month, symbol, attempt)
        return StagedBuy(symbol, notional, cid, None, attempt, previous=latest)
    attempt = latest.attempt if latest is not None else 1
    cid = client_order_id(account_pk, plan.pk, month, symbol, attempt)
    return StagedBuy(symbol, notional, cid, latest, attempt)


def month_symbols(plan: MethodPlan, day: date) -> list[str]:
    """What the month buys: every symbol an index plan names; a momentum plan's top N for the
    month's ranking, in rank order (chapter 14), which is empty while nothing is ranked."""
    if plan.is_momentum:
        return plan_ranking(plan, (day.year, day.month)).top
    return plan.symbol_list()


def month_buys(plan: MethodPlan, day: date) -> MonthBuys:
    month = month_of(day)
    symbols = month_symbols(plan, day)
    parts = split_amount(plan.amount, symbols) if symbols else []
    buys = [staged(plan, month, symbol, notional) for symbol, notional in parts]
    window_closes = date(day.year, day.month, plan.buy_window_days)
    spent = practice_spent(plan)
    unplaced = sum((buy.notional for buy in buys if not buy.placed), ZERO)
    budget = plan.practice_budget
    return MonthBuys(
        month=month,
        window_closes=window_closes,
        buys=buys,
        total=sum((notional for _, notional in parts), ZERO),
        budget=budget,
        spent=spent,
        refusal=refusal_for(plan, day, window_closes, buys, unplaced, budget, spent),
    )


def refusal_for(
    plan: MethodPlan,
    day: date,
    window_closes: date,
    buys: list[StagedBuy],
    unplaced: Decimal,
    budget: Decimal | None,
    spent: Decimal,
) -> str:
    """The first reason Confirm cannot be pressed, or "" when it can. Each is a sentence the page
    prints as it is."""
    if day < plan.started_on:
        return f"The plan starts on {plan.started_on:%Y-%m-%d}; nothing is due before then."
    if day > window_closes:
        return (
            f"This month's window closed on {window_closes:%Y-%m-%d}. The method has no catching "
            "up: the next window opens on the 1st."
        )
    if plan.is_momentum and not buys:
        return (
            f"No candidate is ranked for {month_of(day)}: none has a close stored in both months "
            "of its 12-1 window, so there is nothing to buy."
        )
    if not plan.is_momentum and len(buys) > 1:
        return (
            f"The plan names {len(buys)} symbols. This method's rules count one buy of the plan's "
            "amount each month, so split orders would show as findings; the app places a month's "
            "buys for a plan with one symbol."
        )
    if hand_logged_buys(plan, day):
        return f"A buy for {month_of(day)} is already in the journal, logged by hand."
    if skip_logged(plan, day):
        return f"You logged a skip for {month_of(day)}, with its reason: nothing is placed."
    if not any(not buy.placed for buy in buys):
        return ""
    if budget is None:
        return (
            "Set a practice budget for this plan first, the app's own number: in the admin, "
            "Method plans, this plan, Practice budget."
        )
    if unplaced > budget - spent:
        return (
            f"This month's buys, {money(unplaced)}, are more than the practice budget left, "
            f"{money(budget - spent)}."
        )
    return ""


def hand_logged_buys(plan: MethodPlan, day: date) -> bool:
    """A buy this month in the journal that no paper order wrote: the owner already bought."""
    from_orders = PaperOrder.objects.filter(account=plan.account).exclude(journal_entry=None)
    return (
        JournalEntry.objects.filter(
            account=plan.account, action="buy", date__year=day.year, date__month=day.month
        )
        .exclude(pk__in=from_orders.values("journal_entry"))
        .exists()
    )


def skip_logged(plan: MethodPlan, day: date) -> bool:
    """A skip this month in the journal: the owner decided not to buy, and said why."""
    return JournalEntry.objects.filter(
        account=plan.account, kind=SKIP, date__year=day.year, date__month=day.month
    ).exists()


@dataclass(frozen=True, slots=True)
class PaperSection:
    """What the method page's "This month's buys" box needs: the staged buys, the clock, and the
    one error to show instead when Alpaca did not answer."""

    stage: MonthBuys
    clock: MarketClock | None
    error: str

    @property
    def host(self) -> str:
        return PAPER_HOST

    @property
    def queues_past_window(self) -> bool:
        """Closed now, and the next open is after the window: the fill will land outside it."""
        return (
            self.clock is not None
            and not self.clock.is_open
            and self.clock.next_open.date() > self.stage.window_closes
        )


def paper_section(plan: MethodPlan) -> PaperSection:
    """Built by the method page for a linked account. One request to Alpaca, the clock. The
    buys come from the plan version in force today (chapter 12), which is not the active row
    while a change is scheduled for next month."""
    day = today()
    stage = month_buys(plan.in_force(day), day)
    try:
        clock = paper_client().clock()
    except AlpacaError as error:
        return PaperSection(stage, None, error.message)
    return PaperSection(stage, clock, "")


# --- 2. Confirm ---------------------------------------------------------------------------------


class ConfirmRefused(Exception):
    """The staged buys may not be placed; the message is `MonthBuys.refusal`."""


@dataclass(slots=True)
class ConfirmResult:
    clock: MarketClock
    placed: list[PaperOrder] = field(default_factory=list[PaperOrder])
    already: list[PaperOrder] = field(default_factory=list[PaperOrder])
    failed: list[tuple[str, str]] = field(default_factory=list[tuple[str, str]])


def confirm(plan: MethodPlan, day: date, client: AlpacaPaper) -> ConfirmResult:
    """Place this month's staged buys that are not placed yet. The checks run again here, on the
    server, whatever the page showed: a stale tab cannot buy outside the window or the budget.
    The plan is the version in force on `day`."""
    plan = plan.in_force(day)
    stage = month_buys(plan, day)
    if stage.refusal:
        raise ConfirmRefused(stage.refusal)
    # Asked first, so a closed market is known before anything is sent; an error here stops the
    # whole confirm with nothing placed.
    result = ConfirmResult(clock=client.clock())
    for buy in stage.buys:
        if buy.placed and buy.order is not None:
            result.already.append(buy.order)
            continue
        try:
            order, new = place_one(plan, buy, day, client)
        except AlpacaError as error:
            result.failed.append((buy.symbol, error.message))
            continue
        (result.placed if new else result.already).append(order)
    return result


def place_one(
    plan: MethodPlan, buy: StagedBuy, day: date, client: AlpacaPaper
) -> tuple[PaperOrder, bool]:
    """One buy, at most once. The row is created or found by its `client_order_id` and locked for
    the length of the call (Postgres; SQLite has one writer anyway), so a second request for the
    same buy waits, then finds the order placed and returns it. A row that already existed
    without an Alpaca id means an earlier try may have reached Alpaca before failing here, so
    Alpaca is asked for that id before anything is sent."""
    failure: AlpacaError | None = None
    with transaction.atomic():
        order, created = PaperOrder.objects.select_for_update().get_or_create(
            client_order_id=buy.client_order_id,
            defaults={
                "account": plan.account,
                "plan": plan,
                "month": month_of(day),
                "symbol": buy.symbol,
                "notional": buy.notional,
                "attempt": buy.attempt,
            },
        )
        if order.placed:
            return order, False
        try:
            state = submit(client, order, look_first=not created)
        except AlpacaError as error:
            # Kept on the row, so the page can say why, and committed with it: the exception is
            # raised after the block, not inside it, which would roll the message back.
            order.message = error.message[:240]
            order.save(update_fields=["message", "updated_at"])
            failure = error
        else:
            apply_state(order, state)
            order.message = ""
            order.save()
            reconcile_journal(order, day)
            return order, True
    raise failure


def submit(client: AlpacaPaper, order: PaperOrder, look_first: bool) -> PaperOrderState:
    """Send the order, unless Alpaca already has one with this id. Alpaca refuses a repeated
    `client_order_id` with 422 "client_order_id must be unique"; that answer means the order
    exists, so it is read back rather than reported as a failure."""
    if look_first:
        try:
            return client.order_by_client_id(order.client_order_id)
        except AlpacaNotFound:
            pass
    try:
        return client.buy_notional(order.symbol, order.notional, order.client_order_id)
    except AlpacaRefused as error:
        if error.status == 422 and "client_order_id" in error.message:
            return client.order_by_client_id(order.client_order_id)
        raise


def apply_state(order: PaperOrder, state: PaperOrderState) -> None:
    order.alpaca_id = state.id
    order.status = state.status
    order.filled_qty = state.filled_qty
    order.filled_avg_price = state.filled_avg_price
    order.submitted_at = state.submitted_at
    order.filled_at = state.filled_at


# --- The journal entry an order writes ----------------------------------------------------------


def journal_amount(order: PaperOrder) -> Decimal:
    """The money that changed hands. A full fill spent the notional; an order that ended part
    filled spent shares times the average price; an order still open is booked at its notional,
    so the practice budget counts it now."""
    partly_done = order.final and order.status != "filled" and order.filled_qty > 0
    if partly_done and order.filled_avg_price is not None:
        return to_money(order.filled_qty * order.filled_avg_price)
    return order.notional


def journal_note(order: PaperOrder) -> str:
    note = f"Alpaca paper order {order.alpaca_id}: {order.status}"
    if order.final and order.filled_qty > 0 and order.filled_avg_price is not None:
        when = f" on {order.filled_at:%Y-%m-%d}" if order.filled_at else ""
        note += f", {to_shares(order.filled_qty)} shares at {order.filled_avg_price}{when}"
    return note[:NOTE_LIMIT]


def reconcile_journal(order: PaperOrder, day: date | None = None) -> None:
    """Make the order's journal entry say what Alpaca says. Shares are recorded once the order is
    final; an order that ended with nothing filled was never a trade, so its entry is removed and
    the row keeps the history. The entry's date is the day the owner confirmed, which is the act
    the method's window rule is about; the fill's date is in the note."""
    entry = order.journal_entry
    if order.final and order.filled_qty == 0:
        if entry is not None:
            order.journal_entry = None
            order.save(update_fields=["journal_entry", "updated_at"])
            entry.delete()
        return
    shares = to_shares(order.filled_qty) if order.final and order.filled_qty > 0 else None
    if entry is None:
        entry = JournalEntry.objects.create(
            account=order.account,
            date=day or today(),
            action="buy",
            symbol=order.symbol,
            amount=journal_amount(order),
            shares=shares,
            note=journal_note(order),
        )
        order.journal_entry = entry
        order.save(update_fields=["journal_entry", "updated_at"])
        return
    entry.amount = journal_amount(order)
    entry.shares = shares
    entry.note = journal_note(order)
    entry.save()


# --- 3. Sync ------------------------------------------------------------------------------------


@dataclass(slots=True)
class SyncResult:
    checked: int = 0
    changed: int = 0
    filled: int = 0
    ended_part_filled: int = 0
    ended_unfilled: int = 0
    still_open: int = 0
    failed: dict[str, str] = field(default_factory=dict[str, str])

    def as_dict(self) -> dict[str, object]:
        return {
            "checked": self.checked,
            "changed": self.changed,
            "filled": self.filled,
            "ended_part_filled": self.ended_part_filled,
            "ended_unfilled": self.ended_unfilled,
            "still_open": self.still_open,
            "failed": self.failed,
        }


def sync_orders(client: AlpacaPaper, account: Account | None = None) -> SyncResult:
    """Read every open order back and fix its row and its journal entry. Idempotent: an order that
    did not change writes nothing new, and a final order is never asked about again. One order
    Alpaca refuses is recorded and the rest go on; a 429 stops the run for the next one."""
    result = SyncResult()
    for order in PaperOrder.open_orders(account):
        result.checked += 1
        try:
            state = client.order(order.alpaca_id)
        except AlpacaRateLimited as error:
            result.failed[order.client_order_id] = error.message
            break
        except AlpacaError as error:
            result.failed[order.client_order_id] = error.message
            continue
        before = (order.status, order.filled_qty)
        apply_state(order, state)
        if (order.status, order.filled_qty) != before:
            result.changed += 1
            with transaction.atomic():
                order.save()
                reconcile_journal(order)
        if order.status == "filled":
            result.filled += 1
        elif not order.final:
            result.still_open += 1
        elif order.filled_qty > 0:
            result.ended_part_filled += 1
        else:
            result.ended_unfilled += 1
    return result
```

`month_symbols` is the one new idea: an index plan buys every symbol it names, a momentum plan its top N for the
day's month. Everything after it, the ids, the split, the budget, Confirm, Place again and the sync, is chapter 11
and 12's. Chapter 11's one-symbol refusal still applies to index plans; a momentum plan with nothing ranked is
refused in words.

### 14.12 Green, and a momentum plan on your laptop

Listing 14-26, Terminal:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run --env-file .env python manage.py migrate
```

```text
722 passed in 26.87s
All checks passed!
231 files already formatted
0 errors, 0 warnings, 0 informations
Operations to perform:
  Apply all migrations: accounts, admin, auth, contenttypes, holdings, methods, outbox, pages, paper, prices, reports, sessions, watchlist
Running migrations:
  Applying methods.0004_methodplan_top_n... OK
```

Twenty-six new tests. Your laptop's `Practice` account runs index investing from chapter 10, and an account runs
one method at a time, so start momentum on a second account. The first two tries are refused on purpose:

Listing 14-27, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -v 0 -c "
import re
from django.contrib.auth.models import User
from django.test import Client
from invest_witus_site.holdings.models import Account
u = User.objects.get(is_superuser=True); c = Client(); c.force_login(u)
a, _ = Account.objects.get_or_create(owner=u, name='Momentum practice', defaults={'broker': 'Example Brokerage', 'kind': 'paper'})
said = lambda page: re.findall(r'class=\"message \w+\">([^<]+)<', page) or re.findall(r'class=\"errorlist[^\"]*\"[^>]*><li>([^<]+)<', page)
form = {'method_id': 'momentum-12-1', 'amount': '100', 'buy_window_days': '7', 'symbols': 'ALPHA BETA GAMMA DELTA', 'started_on': '2026-10-01'}
for top_n in ('', '4', '2'):
    for line in said(c.post(f'/accounts/{a.pk}/method/start/', {**form, 'top_n': top_n}, follow=True).content.decode()):
        print(line)
"
```

```text
12-1 momentum needs a top N: how many candidates to hold.
Name more candidates than the top N: 4 candidates and a top 4 leaves nothing to rank out.
Started 12-1 momentum, monthly top N in equal parts on Momentum practice.
Added to the watch list, so the nightly pull stores their closes: ALPHA, BETA, GAMMA, DELTA. A candidate needs a year of closes or more to be ranked; Get history fetches them now.
```

Use the first day of your current month for `started_on`. The four symbols are placeholders, so no price source
knows them; plant twenty months of made-up closes with the test's own helper, and read the ranking:

Listing 14-28, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -v 0 -c "
import re
from django.contrib.auth.models import User
from django.test import Client
from invest_witus_site.holdings.models import Account
from tests.test_ch10 import tables_in, text
from tests.test_ch14 import add_months, plant_candidates, this_month
u = User.objects.get(is_superuser=True); a = Account.objects.get(owner=u, name='Momentum practice'); c = Client(); c.force_login(u)
plant_candidates(add_months(this_month(), -1))
page = text(c.get(f'/accounts/{a.pk}/method/?view=b'))
print(re.search(r'<h2 id=\"ranking-heading\">([^<]+)<', page).group(1))
for row in next(t for t in tables_in(page) if t[0][0] == 'Rank'): print(row)
print(re.findall(r'<li>(DELTA: [^<]+)</li>', page))
print(re.findall(r'<li>(Buy [^<]+|Sell [^<]+)</li>', page))
"
```

```text
The ranking for 2026-10
('Rank', 'Symbol', '12-1 return', 'From', 'To', 'Top 2')
('1', 'ALPHA', '+24.3%', '2025-09-28, $114.87', '2026-08-28, $142.82', 'yes')
('2', 'BETA', '+11.6%', '2025-09-28, $107.21', '2026-08-28, $119.61', 'yes')
('3', 'GAMMA', '-10.5%', '2025-09-28, $93.21', '2026-08-28, $83.45', 'no')
['DELTA: no close stored in 2025-09; the window needs a close in 2025-09 and in 2026-08.']
['Buy $50.00 of ALPHA', 'Buy $50.00 of BETA']
```

Your months are the ones before the month you run it in. Check one return by hand: 142.82 over 114.87 is 1.2433,
or +24.3%. September 2026 is in neither column: it is the excluded month. Now break a rule on purpose, buying GAMMA
instead of BETA, and read view B:

Listing 14-29, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -v 0 -c "
from django.contrib.auth.models import User
from django.test import Client
from invest_witus_site.holdings.models import Account
from tests.test_ch10 import tables_in, text
u = User.objects.get(is_superuser=True); a = Account.objects.get(owner=u, name='Momentum practice'); c = Client(); c.force_login(u)
for symbol, amount in (('ALPHA', '50'), ('GAMMA', '50')):
    c.post(f'/accounts/{a.pk}/method/log/', {'date': '2026-10-02', 'action': 'buy', 'symbol': symbol, 'amount': amount})
tables = tables_in(text(c.get(f'/accounts/{a.pk}/method/?view=b')))
checks = next(t for t in tables if t[0][0] == 'Rule')
for row in checks: print(row[0][:44], row[1], row[2], sep=' | ')
months = next(t for t in tables if t[0][0] == 'Month')
for row in months: print(row[0], row[2], row[6], row[7], sep=' | ')
findings = next(t for t in tables if t[0][:2] == ('Day', 'Rule'))
for row in findings[1:]: print(row[0], row[2], sep=' | ')
"
```

```text
Rule | Status | Evidence
Rank and buy only the candidates your plan n | pass | no findings
Rank the candidates by their 12-1 return: th | pass | no findings
Hold the top N: at each rebalance, buy every | fail | 2 findings: 2026-10
Split the month's amount equally across the  | pass | no findings
Sell the whole holding of a symbol at the fi | pass | no findings
Rebalance once in every month of the plan. | pass | no findings
Trade only at the monthly rebalance, within  | pass | no findings
Month | Status | Rules flagged | Top 2
2026-10 | done | hold-top-n | ALPHA, BETA
2026-10-01 | No buy of BETA in 2026-10; it ranked 2nd.
2026-10-02 | Bought GAMMA, ranked 3rd in 2026-10; the plan holds the top 2.
```

One trade, two findings of one rule: GAMMA was bought from below the line, and BETA, above it, was not. In a
browser, sign in, open **Momentum practice**, and the method page shows the bars above the view; the account page's
watch list shows the 12-1 column; click ALPHA and pick **All** to see the window shaded.

### 14.13 What the owner does outside the editor

The reference app's steps are task 25 in the owner's queue. A learner with a Vercel project of their own does the
same:

1. **Merge the chapter.** The push to `main` runs the migrate workflow in `docs/05-operations.md`; its summary
   lists `methods.0004_methodplan_top_n`. The new column is nullable, so the release before keeps working while
   it runs.
2. **Start a momentum plan** on a test account with a few candidates you already watch, a top N smaller than the
   list, and the first of this month as the start.
3. **Fetch the history** the window needs: the method page's **Get 5 years of history** for any candidate it lists
   as not ranked. Then read the ranking, the table and the review.

## Checkpoint

- `uv run pytest` prints `722 passed`; ruff and pyright pass.
- Listing 14-27 refuses a missing top N and a top N as large as the list, then starts the plan and names the
  symbols it put on the watch list.
- Listing 14-28 ranks ALPHA, BETA and GAMMA, lists DELTA as not ranked with the months it needs, and stages two
  buys of $50.00.
- Listing 14-29 fails `hold-top-n` with two findings and passes the other six rules.
- An index plan's pages are as they were: no ranking, no Top N column, no 12-1 column, no shading.
- Signed out, no page has a ranking, a symbol or a table; signed in as anyone but the owner, the method page is a
  404.
- Commit and push: `git add -A && git commit -m "Chapter 14: a second method, 12-1 momentum"`.

## Exercises

1. **Sell on paper.** Add a sell path for a holding that left the top N: read the position from Alpaca, close it
   with a deterministic id, book what it brought into the journal, and let the sync fix it. Show the wash-sale
   warning before Confirm when a buy follows a sale within 30 days. Write the decision first.
2. **Equal weight on the value held.** Today each month's new money is split equally. Add an option that also
   trims and tops up what you hold so each position is the same share of the total, using the stored closes, and
   a rule for how far off is too far.
3. **Rank changes.** Add a column to the ranking table with each candidate's place last month and an arrow for the
   move, from the same `rank` function run one month earlier (chapter 14a builds this).
4. **The rolling line.** On a candidate's history page, draw its 12-1 return for each of the last 24 months as a
   line, with the zero line marked.

## If you get stuck

- Browse: https://github.com/dapperAuteur/invest-witus/tree/v14
- Diff for this chapter: https://github.com/dapperAuteur/invest-witus/compare/e635e10...v14 (the diff from `v13`
  also holds the work between chapters that step 14.0 takes)
- Zip: https://github.com/dapperAuteur/invest-witus/archive/v14.zip
- Take the reference's files. Chapter 14 added `src/invest_witus/methods/momentum_12_1.toml`,
  `src/invest_witus/methods/momentum_12_1.py`, `src/invest_witus/adherence/momentum.py`,
  `src/invest_witus/adherence/rule_sets.py`, `src/invest_witus_site/methods/momentum.py`,
  `methods/migrations/0004_methodplan_top_n.py`, the templates `methods/_momentum.html` and
  `watchlist/_momentum_window.html`, and `tests/test_ch14.py`; and changed `methods/models.py`, `methods/engine.py`,
  `methods/forms.py`, `methods/views.py`, the method templates `method_page.html`, `_view_a.html`, `_view_b.html`,
  `_view_c.html`, `_versions.html` and `plan_change.html`, `paper/orders.py`, `prices/charts.py`, the template
  `prices/_chart.html`, `watchlist/views.py`, the templates `watchlist/_section.html` and `watchlist/history.html`,
  `holdings/views.py`, `holdings/templatetags/holdings_extras.py`, `pages/static/pages/site.css`,
  `pages/templates/pages/home.html` and one line of `tests/test_ch10.py`. No package changed, no environment
  variable was added, nothing moved:
  `git fetch reference --tags && git checkout v14 -- src tests`.
- `test_the_package_lists_its_methods_and_the_rules_file_still_matches_the_checks` (chapter 10) fails with
  `['index-dca', 'momentum-12-1'] == ['index-dca']`: change its first assertion as Listing 14-5 shows.
- `test_the_month_end_close_is_the_last_stored_day_of_the_month` gets 150: `month_ends` kept the first or the
  highest close of the month instead of the latest day.
- `test_the_ranking_is_highest_first_with_ties_in_symbol_order` puts GAMMA before ALPHA: the sort key is
  `-change` alone, so a tie keeps the input order.
- `test_a_month_with_nothing_ranked_is_not_judged_by_rank` finds rank findings: `review` checks ranks whenever a
  ranking exists, without `ranking.ranked`.
- `test_the_engine_ranks_each_month_from_stored_adjusted_closes` ranks BETA last: `price_series` reads `close`
  where `adj_close` is stored, so BETA's planted split reads as a fall.
- Chapter 10's view tests fail on the plan's sentence: an `else` branch in a view template is not byte for byte
  the old text (a space or a line break around `{% endif %}`).
- `test_the_change_form_carries_the_top_n_for_momentum_only` finds `top_n` in an index plan's form: the field is
  declared on the class and `__init__` did not delete it.
- `test_confirm_buys_the_top_n_in_equal_parts_once` finds "The plan names 2 symbols": chapter 11's refusal ran for
  a momentum plan; guard it with `not plan.is_momentum`.
- On Vercel after the merge, a page answers 500 with `no such column: top_n` or `column ... top_n does not
  exist` for about a minute: the migrate workflow is still running. Longer than that, open GitHub Actions and read
  the run.

## What we learned

- A window defined in calendar months needs month arithmetic and a rule for which day stands for the month; write
  both down before the code.
- A ranking should give the same order for the same inputs. Break ties on purpose.
- A result type that can say "not ranked, and here is why" is worth more on the page than a `None`.
- A second rule set in the first one's shape lets the engine branch once, and a registry with a test keeps every
  rules file matched to its checks.
- When an earlier test pinned a whole list, the honest fix is to say in the chapter what changed and why.
- A chart is readable when the shape, the sign and the words carry the meaning, and a table under it carries the
  numbers.

## Next

Chapter 14a adds two more pictures of momentum: how each candidate's rank moved since last month, and the 12-1
return as a line over time on each symbol's history page.

## References

Gray, W. R., & Vogel, J. R. (2016). *Quantitative momentum: A practitioner's guide to building a momentum-based
stock selection system*. Wiley.

Internal Revenue Service. (2026). *Publication 550 (2025): Investment income and expenses (including capital gains
and losses)*. Retrieved October 29, 2026, from https://www.irs.gov/publications/p550
