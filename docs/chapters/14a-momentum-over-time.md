# Chapter 14a: Momentum over time: rank changes and the rolling 12-1 line

**Starts from:** tag `v14`, plus the reference's work between chapters (step 14a.0). **Ends at:** tag `v14a`.
**Written against:** Python 3.14.10, uv 0.13.6, Django 5.2.18, and the Kenneth R. French Data Library's page on
the momentum factor as read on November 1, 2026.
**Goal:** chapter 14 showed this month's ranking. This addendum shows how it got there. The method page of a
momentum account gains **Rank changes**: where each candidate ranked this month and last month, how far it moved,
whether it crossed the top-N line, and its place in each of the last twelve months. A watched symbol's history page
gains **12-1 return, month by month**: the number the ranking reads, computed for each of the last 24 months and
drawn as a line with a zero line, a table under it, and "not enough history" wherever a month's window is missing
a close. No new math: both pictures call chapter 14's `score` and `rank` once per month.
**Time:** 2 to 3 hours for the code and tests. The laptop walk-through takes 5 minutes.

This is an addendum to chapter 14, numbered `14a` so that it sorts after the chapter it extends and before chapter
15, which it does not change. The listings are generated from tag `v14a` by `scripts/render_chapter.py`.

## What you will learn

- **Reusing a function instead of writing new math:** a series of results is a loop over months around the
  function that already computes one month, so the page and the ranking can never disagree.
- **A result that can be "not enough history":** a month without both closes keeps its reason all the way to the
  table, and the chart leaves a gap instead of drawing a number nobody computed.
- **Breaking a line at a gap:** grouping consecutive points into runs, one polyline per run.
- **Comparing like with like:** ranking today's candidates in every month, so a column of places means the same
  thing in each month, and saying so on the page.
- **A chart with a zero line and a table:** a shared scale that always includes zero, and the table as the text
  alternative.

## Before the code: the formula, and four decisions

**The formula.** Write `P(m)` for the last stored adjusted close in calendar month `m`. A rebalance in month `M`
reads the 12-1 return

```text
R(M) = P(M-13) to P(M-2):   R(M) = P(M-2) / P(M-13) - 1
```

twelve months back from the start of `M`, less the latest full month, `M-1`, which is left out. This is chapter
14's window, unchanged. It is also the window of the momentum factor in Kenneth French's data library, whose stocks
need "a price for the end of month t-13 and a good return for t-2" (French, n.d.). The idea of buying the stocks
that rose the most over the past months is the one Jegadeesh and Titman (1993) tested: "strategies which buy stocks that have performed well in the past and sell stocks that have performed
poorly" earned significant positive returns over 3- to 12-month holding periods in their sample. That is a
finding about a past sample, not a promise about the next month, and the pages say so.

The **rolling 12-1 line** is `R(M-23), R(M-22), ..., R(M)`: one number per month for the last 24 months, each placed
at the month it is used in. The **rank change** of a candidate is `rank(M-1) - rank(M)`, where `rank` is its place
among the plan's candidates by `R`, 1 the highest: a positive number is a rise.

**Decision 1: today's candidates in every month.** A plan can change its list (chapter 12's versions). Ranking
each past month with the list it had would make the columns of the history table compare different lists. The
history ranks the list the plan names today in every month, and the page says "a month before you changed the list
shows how today's list would have ranked then". Row 153.

**Decision 2: no number where the window is not complete.** A month whose window lacks a close at either end has no
rank and no point. A candidate ranked in only one of the two months has no move in places: it is "new in the
ranking" or "not ranked this month". The line breaks at such a month instead of joining its neighbors. A month
missing *inside* a window changes nothing, because the return reads only its two ends. Rows 153 and 154.

**Decision 3: the point sits at the month it is used in.** The value plotted at November 2026 is the number a
November rebalance reads, from the end of October 2025 to the end of September 2026. The newest point is the same
number as this month's shaded window and badge from chapter 14. Row 154.

**Decision 4: tables first, one small chart.** The rank changes are two tables with arrows and words (`▲ up 2
places`), readable without color or script; a bump chart is left as an exercise. The rolling line is an SVG drawn
on the server in the style of the price chart, with a dashed zero line, one dot per month, and the table of every
month under it. Rows 153 and 154.

## Steps

### 14a.0 Take the work between chapters

Between `v14` and this chapter the reference took four pieces of work that are not chapters: a new symbol's first
fetch asks for two years (decision 149), the symbol profile (150), the Help bubble (151) and the two sign-out
buttons (152), plus a fix to a chapter 08 test whose statement date made it fail after October 30, 2026. Take them
from the commit this chapter starts from, then migrate:

Listing 14a-1, Terminal:

```sh
git fetch reference --tags
git checkout 17335d2 -- src tests .env.example
uv run --env-file .env python manage.py migrate
uv run pytest -q
```

```text
Operations to perform:
  Apply all migrations: accounts, admin, auth, contenttypes, holdings, methods, outbox, pages, paper, prices, reports, sessions, watchlist
Running migrations:
  Applying prices.0005_symbol_profile... OK
778 passed in 21.46s
```

Commit that as its own step (`git commit -am "Take the reference's work between chapters 14 and 14a"`).

### 14a.1 The tests

Listing 14a-2, Filename: `tests/test_ch14a.py`:

```python
"""Chapter 14a checkpoint: 12-1 momentum over time. The rolling 12-1 return month by month from
planted closes with answers worked out by hand (a year boundary, a gap at a window's end, a gap
inside it, too little history, a split read through the adjusted close); the same candidates
ranked in every month with each one's move since last month (up, down, the same, new, dropped out,
never ranked, and crossing the top-N line); the method page's two tables and the history page's
line, on a momentum account only. Placeholder symbols and planted prices only, as in chapter 14."""

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from invest_witus.methods.momentum_12_1 import Month, Score, add_months
from invest_witus.methods.momentum_history import (
    NOT_ENOUGH,
    first_day_needed,
    month_end_series,
    months_ending,
    rank_history,
    rolling,
    segments,
)
from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.models import MethodPlan
from invest_witus_site.methods.momentum_history import (
    LINE_MONTHS,
    RANK_MONTHS,
    rank_changes,
    rolling_line,
)
from invest_witus_site.prices.models import DailyClose
from invest_witus_site.watchlist.models import WatchItem
from tests.test_ch10 import tables_in, text
from tests.test_ch14 import closes, monthly, plant

D = Decimal

# --- Planting prices ------------------------------------------------------------------------------


def linear(first: Month, count: int, day: int = 28) -> list[tuple[date, Decimal]]:
    """One close a month on `day`, 100 in the first month, 101 in the next, and so on, so any
    window's return can be worked out by hand: the close in month i is 100 + i."""
    return [
        (date(year, month, day), D(100 + index))
        for index, (year, month) in enumerate(monthly(first, count))
    ]


def flat(
    first: Month, last: Month, changes: dict[Month, str] | None = None
) -> list[tuple[date, Decimal]]:
    """A close of 100 on the 28th of every month from `first` to `last`, except the months in
    `changes`, which close at the value given."""
    changes = changes or {}
    rows: list[tuple[date, Decimal]] = []
    month = first
    while month <= last:
        rows.append((date(month[0], month[1], 28), D(changes.get(month, "100"))))
        month = add_months(month, 1)
    return rows


def crossing(rebalance: Month) -> dict[str, list[tuple[date, Decimal]]]:
    """Five candidates whose places change between the month before `rebalance` and `rebalance`
    itself. For a rebalance in November 2026 (window October 2025 to September 2026) and the
    month before (September 2025 to August 2026):

    - ALPHA closes at 130 in August 2026 only: +30% for October, 0% for November.
    - BETA closes at 120 in September 2026 only: 0% for October, +20% for November.
    - GAMMA closes at 110 in August and September 2026: +10% in both months.
    - EPSILON starts in October 2025, too late for October's window: unranked, then -10%.
    - ZETA stops in August 2026 at 95, before November's window ends: -5%, then unranked.
    - DELTA starts six months back: never ranked.
    """
    end, before = add_months(rebalance, -2), add_months(rebalance, -3)
    first, last = add_months(rebalance, -22), add_months(rebalance, -1)
    return {
        "ALPHA": flat(first, last, {before: "130"}),
        "BETA": flat(first, last, {end: "120"}),
        "GAMMA": flat(first, last, {before: "110", end: "110"}),
        "EPSILON": flat(add_months(rebalance, -13), last, {end: "90"}),
        "ZETA": flat(first, before, {before: "95"}),
        "DELTA": flat(add_months(rebalance, -6), last),
    }


def plant_all(series: dict[str, list[tuple[date, Decimal]]]) -> None:
    for symbol, rows in series.items():
        plant(symbol, rows)


def this_month() -> Month:
    today = timezone.localdate()
    return today.year, today.month


# --- Fixtures -------------------------------------------------------------------------------------


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_superuser("owner", "owner@example.com", "pw")


@pytest.fixture
def owner_client(client: Client, owner: User) -> Client:
    client.force_login(owner)
    return client


@pytest.fixture
def account(owner: User) -> Account:
    return Account.objects.create(
        name="Practice", broker="Example Broker", kind="paper", owner=owner
    )


def momentum_plan(account: Account, symbols: str, top_n: int = 2) -> MethodPlan:
    start = this_month()
    return MethodPlan.objects.create(
        account=account,
        method_id="momentum-12-1",
        amount=D("100.00"),
        buy_window_days=7,
        symbols=symbols,
        top_n=top_n,
        started_on=date(start[0], start[1], 1),
    )


@pytest.fixture
def crossed(account: Account) -> MethodPlan:
    """A momentum plan over the five crossing candidates, their closes planted for this month."""
    plant_all(crossing(this_month()))
    return momentum_plan(account, "ALPHA BETA GAMMA EPSILON ZETA DELTA")


# --- The months a stretch reads -------------------------------------------------------------------


def test_a_stretch_of_months_ends_at_the_month_given_and_crosses_a_year() -> None:
    assert months_ending((2026, 2), 4) == [(2025, 11), (2025, 12), (2026, 1), (2026, 2)]
    assert months_ending((2026, 2), 1) == [(2026, 2)]
    with pytest.raises(ValueError):
        months_ending((2026, 2), 0)
    # The oldest month, November 2025, reads the end of October 2024: the query starts there.
    assert first_day_needed(months_ending((2026, 2), 4)) == date(2024, 10, 1)


def test_only_each_months_last_close_is_kept() -> None:
    rows = [
        (date(2026, 9, 30), D("101")),
        (date(2026, 9, 2), D("90")),
        (date(2026, 10, 1), D("5")),
    ]
    assert month_end_series(rows) == [(date(2026, 9, 30), D("101")), (date(2026, 10, 1), D("5"))]


# --- The rolling 12-1 line ------------------------------------------------------------------------


def test_each_months_point_is_the_12_1_return_worked_out_by_hand() -> None:
    # 100 in January 2024, 101 in February, ... 123 in December 2025.
    rows = linear((2024, 1), 24)
    points = rolling("ALPHA", rows, months_ending((2026, 1), 3))
    assert [point.label for point in points] == ["2025-11", "2025-12", "2026-01"]
    # A rebalance in December 2025 reads November 2024 (110) to October 2025 (121): 121/110 - 1.
    december = points[1]
    assert isinstance(december.result, Score)
    assert december.change == D("0.1")
    assert (december.result.start_close, december.result.end_close) == (D("110"), D("121"))
    # January 2026 crosses the year: December 2024 (111) to November 2025 (122).
    assert points[2].change == D("122") / D("111") - 1
    # November 2025: October 2024 (109) to September 2025 (120).
    assert points[0].change == D("120") / D("109") - 1
    assert all(isinstance(point.change, Decimal) for point in points)


def test_too_little_history_says_not_enough_instead_of_a_number() -> None:
    # Eleven month-end closes, January to November 2025: no window has both ends.
    eleven = linear((2025, 1), 11)
    points = rolling("NEW", eleven, months_ending((2026, 6), 12))
    assert all(point.score is None for point in points)
    assert all(point.change is None for point in points)
    assert points[-1].reason.startswith("no close stored in")
    assert segments(points) == []
    # Twelve, January to December 2025: exactly one window fits, the rebalance in February 2026
    # (January 2025 to December 2025). Every month before and after it has no number.
    twelve = linear((2025, 1), 12)
    points = rolling("NEW", twelve, months_ending((2026, 6), 12))
    scored = [point.label for point in points if point.score is not None]
    assert scored == ["2026-02"]
    assert points[-1].reason == (
        "no close stored in 2026-04; the window needs a close in 2025-05 and in 2026-04"
    )
    assert NOT_ENOUGH == "not enough history"


def test_a_gap_at_a_windows_end_breaks_the_line_and_a_gap_inside_it_does_not_change_it() -> None:
    rows = [row for row in linear((2024, 1), 30) if (row[0].year, row[0].month) != (2025, 3)]
    points = rolling("ALPHA", rows, months_ending((2026, 6), 6))
    by_label = {point.label: point for point in points}
    # March 2025 is the start of April 2026's window (M-13) and the end of May 2025's (M-2): only
    # April 2026 reads it among these months, so April has no number and the line breaks there.
    assert by_label["2026-04"].score is None
    assert "2025-03" in by_label["2026-04"].reason
    runs = segments(points)
    assert [[point.label for point in run] for run in runs] == [
        ["2026-01", "2026-02", "2026-03"],
        ["2026-05", "2026-06"],
    ]
    # March 2025 sits inside the windows of January to March 2026, which read only their two ends,
    # so their numbers are the ones a full series gives.
    full = rolling("ALPHA", linear((2024, 1), 30), months_ending((2026, 6), 6))
    assert [p.change for p in points[:3]] == [p.change for p in full[:3]]


def test_a_split_read_through_the_adjusted_close_is_not_a_fall() -> None:
    # The plain close halves in June 2025 (a 2-for-1 split); the adjusted close carries on.
    months = monthly((2024, 9), 24)
    adjusted = closes(months, "0.01")
    plain = [(day, value / 2 if day >= date(2025, 6, 1) else value) for day, value in adjusted]
    window = months_ending((2026, 1), 1)
    on_adjusted = rolling("ALPHA", adjusted, window)[0]
    on_plain = rolling("ALPHA", plain, window)[0]
    assert on_adjusted.change is not None and on_adjusted.change > 0
    assert on_plain.change is not None and on_plain.change < D("-0.4"), (
        "why the app reads adj_close"
    )


# --- Rank changes ---------------------------------------------------------------------------------


def test_each_candidate_moves_from_its_place_last_month_to_its_place_this_month() -> None:
    history = rank_history(crossing((2026, 11)), months_ending((2026, 11), 2), top_n=2)
    october, november = history.rankings
    assert [p.symbol for p in october.places] == ["ALPHA", "GAMMA", "BETA", "ZETA"]
    assert [p.symbol for p in november.places] == ["BETA", "GAMMA", "ALPHA", "EPSILON"]
    moves = {move.symbol: move for move in history.moves()}
    assert [move.symbol for move in history.moves()] == [
        "BETA",
        "GAMMA",
        "ALPHA",
        "EPSILON",
        "DELTA",
        "ZETA",
    ], "this month's order, then the unranked A to Z"
    assert (moves["BETA"].rank, moves["BETA"].previous, moves["BETA"].places) == (1, 3, 2)
    assert moves["BETA"].text == "▲ up 2 places" and moves["BETA"].top_change == "joined"
    assert moves["GAMMA"].text == "◆ same place" and moves["GAMMA"].top_change == ""
    assert moves["ALPHA"].text == "▼ down 2 places" and moves["ALPHA"].top_change == "left"
    assert moves["EPSILON"].text == "new in the ranking" and moves["EPSILON"].places is None
    assert moves["ZETA"].text == "not ranked this month" and moves["ZETA"].previous == 4
    assert moves["DELTA"].text == "not ranked" and moves["DELTA"].direction == "none"


def test_a_move_of_one_place_is_singular_and_a_rank_change_needs_two_months() -> None:
    history = rank_history(
        {
            "ALPHA": flat((2025, 1), (2026, 10), {(2026, 8): "105", (2026, 9): "101"}),
            "BETA": flat((2025, 1), (2026, 10), {(2026, 8): "103", (2026, 9): "103"}),
        },
        months_ending((2026, 11), 2),
        top_n=1,
    )
    moves = {move.symbol: move for move in history.moves()}
    assert moves["BETA"].text == "▲ up 1 place"
    assert moves["ALPHA"].text == "▼ down 1 place"
    with pytest.raises(ValueError):
        rank_history({}, [(2026, 11)], top_n=1)


def test_the_rank_history_holds_each_candidates_place_in_every_month() -> None:
    history = rank_history(crossing((2026, 11)), months_ending((2026, 11), 4), top_n=2)
    assert history.row("ALPHA")[-2:] == [1, 3]
    assert history.row("EPSILON")[-2:] == [None, 4]
    assert history.row("DELTA") == [None, None, None, None]
    # July and August 2026 have every flat candidate tied at 0%: ties go A to Z, as on the
    # method page, so the same closes always give the same places.
    assert [p.symbol for p in history.rankings[0].places][:3] == ["ALPHA", "BETA", "GAMMA"]


# --- The method page ------------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_method_page_shows_the_moves_and_twelve_months_of_places(
    owner_client: Client, crossed: MethodPlan
) -> None:
    month = this_month()
    label = f"{month[0]}-{month[1]:02d}"
    before = add_months(month, -1)
    previous = f"{before[0]}-{before[1]:02d}"
    html = text(owner_client.get(f"/accounts/{crossed.account.pk}/method/?view=a"))
    assert f"Rank changes since {previous}" in html
    tables = tables_in(html)
    moves = next(t for t in tables if t[0][:4] == ("Symbol", label, previous, "Move"))
    assert moves[1:] == [
        ("BETA", "1", "3", "▲ up 2 places", "joined the top 2"),
        ("GAMMA", "2", "2", "◆ same place", "in"),
        ("ALPHA", "3", "1", "▼ down 2 places", "left the top 2"),
        ("EPSILON", "4", "not ranked", "new in the ranking", "out"),
        ("DELTA", "not ranked", "not ranked", "not ranked", "out"),
        ("ZETA", "not ranked", "4", "not ranked this month", "out"),
    ]
    places = next(t for t in tables if t[0][0] == "Symbol" and len(t[0]) == RANK_MONTHS + 1)
    assert places[0][-1] == label and places[0][-2] == previous
    beta = next(row for row in places if row[0] == "BETA")
    assert beta[-2:] == ("3", "1 (top 2)"), "a top-N place is bold and says so to a screen reader"
    assert "n/r" in next(row for row in places if row[0] == "DELTA")
    assert "How to read this." in html and "Lesson coming." in html
    assert "Information, not advice." in html
    for view in ("b", "c"):
        page = text(owner_client.get(f"/accounts/{crossed.account.pk}/method/?view={view}"))
        assert "Rank changes since" in page


@pytest.mark.django_db
def test_an_index_plan_has_no_rank_changes(owner_client: Client, account: Account) -> None:
    MethodPlan.objects.create(
        account=account,
        method_id="index-dca",
        amount=D("100.00"),
        buy_window_days=7,
        symbols="INDEX",
        started_on=date(2026, 1, 1),
    )
    assert "Rank changes" not in text(owner_client.get(f"/accounts/{account.pk}/method/"))


@pytest.mark.django_db
def test_rank_changes_with_nothing_ranked_say_so(owner_client: Client, account: Account) -> None:
    plan = momentum_plan(account, "ALPHA BETA GAMMA")
    changes = rank_changes(plan, timezone.localdate())
    assert not changes.any_ranked
    html = text(owner_client.get(f"/accounts/{account.pk}/method/"))
    assert "No candidate can be ranked in any month" in html


# --- The history page's line ----------------------------------------------------------------------


@pytest.mark.django_db
def test_the_history_page_draws_the_rolling_line_with_a_table_of_every_month(
    owner_client: Client, account: Account
) -> None:
    # Thirty months of closes ending last month: the newest points have numbers, the oldest
    # points' windows reach back past the first close and say so.
    last = add_months(this_month(), -1)
    plant("ALPHA", linear(add_months(last, -29), 30))
    momentum_plan(account, "ALPHA BETA GAMMA")
    WatchItem.add_many(account, ["ALPHA"])
    html = text(owner_client.get(f"/accounts/{account.pk}/watch/ALPHA/?days=all"))
    assert "ALPHA's 12-1 return, month by month" in html
    assert 'class="rolling-run"' in html and 'class="rolling-zero"' in html
    table = next(t for t in tables_in(html) if t[0] == ("Month", "12-1 return", "From", "To"))
    assert len(table) == LINE_MONTHS + 1
    month = this_month()
    assert table[1][0] == f"{month[0]}-{month[1]:02d}", "newest first"
    # The closes run from M-30 (100) to M-1 (129). This month reads M-13 (117) to M-2 (128):
    # 128/117 - 1 = 0.0940, printed +9.4%.
    assert table[1][1] == "+9.4%"
    assert table[-1][1] == "not enough history"
    assert "no close stored in" in table[-1][2]
    line = rolling_line("ALPHA", timezone.localdate())
    # A month m has a number when m-13 is on or after M-30, so m runs from M-17 to M: 18 of 24.
    assert line.scored == 18
    # A month label every six months back from this one; on a phone every other one is hidden.
    labels = [tick.label for tick in line.x_ticks]
    assert len(labels) == 4 and labels[-1] == table[1][0]
    assert [tick.label for tick in line.x_ticks if not tick.minor] == [labels[1], labels[3]]
    assert html.count('class="rolling-dot"') == line.scored
    assert "How to read this." in html and "Information, not advice." in html


@pytest.mark.django_db
def test_the_rolling_line_reads_adjusted_closes_from_the_table(account: Account) -> None:
    last = add_months(this_month(), -1)
    rows = closes(monthly(add_months(last, -15), 16), "0.01")
    split = add_months(last, -6)
    for day, value in rows:
        after = (day.year, day.month) >= split
        DailyClose.objects.create(
            symbol="ALPHA",
            date=day,
            close=value / 2 if after else value,
            adj_close=value,
            source="csv",
            fetched_at=timezone.now(),
        )
    newest = rolling_line("ALPHA", timezone.localdate()).points[-1]
    assert newest.text == "+11.6%", "1.01 to the 11th, not the halved plain close"
    assert rolling_line("ALPHA", timezone.localdate()).unadjusted == 0


@pytest.mark.django_db
def test_no_rolling_line_on_an_index_account_and_a_short_history_says_why(
    owner_client: Client, account: Account
) -> None:
    last = add_months(this_month(), -1)
    plant("ALPHA", linear(add_months(last, -5), 6))
    WatchItem.add_many(account, ["ALPHA"])
    assert "month by month" not in text(
        owner_client.get(f"/accounts/{account.pk}/watch/ALPHA/?days=all")
    )
    momentum_plan(account, "ALPHA BETA GAMMA")
    html = text(owner_client.get(f"/accounts/{account.pk}/watch/ALPHA/?days=all"))
    assert "0 of 24 months have enough history" in html
    assert "No month from" in html and 'class="rolling-run"' not in html
```

Things to notice:

- **The answers are worked out by hand.** `linear` closes month `i` at `100 + i`, so the December 2025 point is
  121 over 110, exactly `0.1`, and the comment says which two closes those are.
- **Eleven and twelve.** Eleven month-ends score nothing; twelve score exactly one month. A window spans eleven
  monthly returns and needs twelve month-end closes, the first one 13 months before the rebalance month. The test
  pins that boundary so nobody "fixes" it to thirteen.
- **The crossing candidates** are flat at 100 except for one or two months, so each one's return in each month is
  a number you can read off the docstring, and every kind of move appears once.
- **The split test runs twice:** once in the library, on two lists, and once through the stored rows, with a
  plain close that halves and an adjusted close that does not.
- **Dates relative to today, where the page reads today,** as in chapter 14.

Run them:

Listing 14a-3, Terminal:

```sh
uv run pytest tests/test_ch14a.py
```

```text
tests/test_ch14a.py:17: in <module>
    from invest_witus.methods.momentum_history import (
E   ModuleNotFoundError: No module named 'invest_witus.methods.momentum_history'
```

Red at import.

### 14a.2 The months, the line and the moves

Listing 14a-4, Filename: `src/invest_witus/methods/momentum_history.py`:

```python
"""12-1 momentum over time (chapter 14a): the same 12-1 return, computed once for every month in a
stretch, and the ranking of the same candidates in every month, with how each one's place moved.
No Django, no files, no new math: every number here comes from chapter 14's `score` and `rank`.

**The rolling 12-1 line.** For each month `M` in the stretch, the 12-1 return a rebalance in `M`
would read: the last stored close of `M-13` to the last stored close of `M-2`, `M-1` left out.
The point is placed at `M`, the month the number is used in. A month whose window lacks either
close has no point: it says "not enough history" and why, and the line breaks there instead of
joining its neighbors across the gap.

**Rank changes.** The candidates are ranked in each month of the stretch with chapter 14's
`rank`, and each candidate's place this month is compared with its place the month before. A
candidate that was not ranked in one of the two months has no move in places; it is "new in the
ranking" or "not ranked this month", never a made-up number.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from invest_witus.methods.momentum_12_1 import (
    Month,
    Ranking,
    Score,
    Unranked,
    Window,
    add_months,
    month_ends,
    month_text,
    rank,
    score,
)

NOT_ENOUGH = "not enough history"


def months_ending(last: Month, count: int) -> list[Month]:
    """`count` months, oldest first, the last one `last`: `months_ending((2026, 2), 3)` is
    November 2025 to February 2026."""
    if count < 1:
        raise ValueError(f"count must be at least 1, got {count}")
    return [add_months(last, step - count + 1) for step in range(count)]


def first_day_needed(months: Sequence[Month]) -> date:
    """The first day the oldest month's window reads: the start of its `M-13`. A query for closes
    from this day on has everything every month in `months` needs."""
    start = Window.for_month(*months[0]).start
    return date(start[0], start[1], 1)


def month_end_series(closes: Iterable[tuple[date, Decimal]]) -> list[tuple[date, Decimal]]:
    """Only the last stored close of each month, oldest first. `score` reads nothing else, so a
    stretch of 24 months scores a dozen numbers per month instead of every daily close."""
    return sorted(month_ends(closes).values())


# --- The rolling 12-1 line ------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Point:
    """The 12-1 return a rebalance in `month` reads, or why there is none."""

    month: Month
    result: Score | Unranked

    @property
    def label(self) -> str:
        return month_text(self.month)

    @property
    def window(self) -> Window:
        return Window.for_month(*self.month)

    @property
    def score(self) -> Score | None:
        return self.result if isinstance(self.result, Score) else None

    @property
    def change(self) -> Decimal | None:
        return self.result.change if isinstance(self.result, Score) else None

    @property
    def reason(self) -> str:
        return self.result.reason if isinstance(self.result, Unranked) else ""


def rolling(
    symbol: str, closes: Iterable[tuple[date, Decimal]], months: Sequence[Month]
) -> list[Point]:
    """One point per month in `months`, in their order: the symbol's 12-1 return for a rebalance
    in that month, or the reason the window cannot be read."""
    ends = month_end_series(closes)
    return [Point(month, score(symbol, ends, Window.for_month(*month))) for month in months]


def segments(points: Sequence[Point]) -> list[list[Point]]:
    """The runs of consecutive months that have a number, so a line can be drawn through each run
    and broken at every month without one. A run of one month is a lone point."""
    runs: list[list[Point]] = []
    current: list[Point] = []
    for point in points:
        if point.score is None:
            if current:
                runs.append(current)
            current = []
        else:
            current.append(point)
    if current:
        runs.append(current)
    return runs


# --- Rank changes ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Move:
    """One candidate's place this month and the month before: 1 is the highest 12-1 return, None
    is not ranked. `places` is how many places it rose (negative: fell), or None when either
    month has no place to compare."""

    symbol: str
    rank: int | None
    previous: int | None
    top: bool
    was_top: bool

    @property
    def places(self) -> int | None:
        if self.rank is None or self.previous is None:
            return None
        return self.previous - self.rank

    @property
    def direction(self) -> str:
        """`up`, `down`, `same`, `new` (ranked now, not last month), `out` (ranked last month,
        not now) or `none` (ranked in neither)."""
        if self.places is not None:
            return "up" if self.places > 0 else ("down" if self.places < 0 else "same")
        if self.rank is not None:
            return "new"
        return "out" if self.previous is not None else "none"

    @property
    def text(self) -> str:
        """The move in words with an arrow, so it never rests on color: `▲ up 2 places`."""
        places = self.places
        if places is not None and places != 0:
            count = abs(places)
            word = "up" if places > 0 else "down"
            arrow = "▲" if places > 0 else "▼"
            return f"{arrow} {word} {count} place{'' if count == 1 else 's'}"
        return {
            "same": "◆ same place",
            "new": "new in the ranking",
            "out": "not ranked this month",
            "none": "not ranked",
        }[self.direction]

    @property
    def top_change(self) -> str:
        """`joined` or `left` when the move crossed the top-N line, else ""."""
        if self.top and not self.was_top:
            return "joined"
        if self.was_top and not self.top:
            return "left"
        return ""


@dataclass(frozen=True, slots=True)
class RankHistory:
    """The same candidates ranked in each month of a stretch, oldest first, and the moves from
    the month before the last to the last."""

    months: list[Month]
    rankings: list[Ranking]
    top_n: int

    @property
    def month(self) -> Month:
        return self.months[-1]

    @property
    def previous_month(self) -> Month:
        return add_months(self.month, -1)

    @property
    def symbols(self) -> list[str]:
        """Every candidate, in this month's rank order, then the unranked ones A to Z."""
        latest = self.rankings[-1]
        ranked = [place.symbol for place in latest.places]
        return ranked + sorted(item.symbol for item in latest.unranked)

    def place(self, symbol: str, index: int) -> int | None:
        """The candidate's place in the ranking at `index`, or None when it was not ranked."""
        found = self.rankings[index].place_of(symbol)
        return found.rank if found is not None else None

    def row(self, symbol: str) -> list[int | None]:
        """The candidate's place in each month, oldest first."""
        return [self.place(symbol, index) for index in range(len(self.rankings))]

    def moves(self) -> list[Move]:
        """Each candidate's move from last month to this month, in this month's order."""
        latest, before = self.rankings[-1], self.rankings[-2]
        found: list[Move] = []
        for symbol in self.symbols:
            now, then = latest.place_of(symbol), before.place_of(symbol)
            found.append(
                Move(
                    symbol=symbol,
                    rank=now.rank if now else None,
                    previous=then.rank if then else None,
                    top=bool(now and now.top),
                    was_top=bool(then and then.top),
                )
            )
        return found


def rank_history(
    series: Mapping[str, Iterable[tuple[date, Decimal]]], months: Sequence[Month], top_n: int
) -> RankHistory:
    """Rank the same candidates in every month of `months` (at least two, oldest first) with
    chapter 14's `rank`, so each month's order and its ties are exactly the method page's."""
    if len(months) < 2:
        raise ValueError("a rank change needs at least two months")
    ends = {symbol: month_end_series(closes) for symbol, closes in series.items()}
    rankings = [rank(ends, Window.for_month(*month), top_n) for month in months]
    return RankHistory(list(months), rankings, top_n)
```

Things to notice:

- **`rolling` calls chapter 14's `score` once per month.** The window, the month-end close and the "no close
  stored in" reason are chapter 14's. `month_end_series` only shrinks the input to one close per month first, so
  24 months read about 36 numbers instead of every daily close 24 times.
- **`segments` splits the points into runs** at every month without a number. A run of one is a lone dot, with no
  line to draw.
- **`Move.places` is `None`, not 0,** when either month has no place: zero would claim "same place", which is a
  fact nobody computed. `text` turns each case into words with an arrow.
- **`rank_history` calls chapter 14's `rank` once per month,** so the ties are placed A to Z, as on the method
  page, and the top N is the first N places.

### 14a.3 What the pages print

Listing 14a-5, Filename: `src/invest_witus_site/methods/momentum_history.py`:

```python
"""12-1 momentum over time on the web (chapter 14a): the method page's rank changes, and the rolling
12-1 line on a watched symbol's history page.

The math is the library's (`invest_witus.methods.momentum_history`, built on chapter 14's
`score` and `rank`); this module reads the stored closes once per page, through chapter 14's
`price_series` (the adjusted close where the row has one), and lays out what the templates draw.
Owner pages only, on an account that runs 12-1 momentum, as in chapter 14.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from invest_witus.methods.momentum_12_1 import Month, month_text
from invest_witus.methods.momentum_history import (
    NOT_ENOUGH,
    Move,
    Point,
    RankHistory,
    first_day_needed,
    months_ending,
    rank_history,
    rolling,
    segments,
)
from invest_witus_site.methods.models import MethodPlan
from invest_witus_site.methods.momentum import HUNDRED, percent_text, place_pct, price_series
from invest_witus_site.prices.charts import EDGE_PERCENT, Tick, y_scale, y_ticks

# How far back each picture reaches, in months, the current month included. Twelve months of
# ranks read 24 months of closes; 24 points on the line read 36, so a symbol fetched with the
# first two years shows "not enough history" for its oldest points until more is fetched.
RANK_MONTHS = 12
LINE_MONTHS = 24
# A label on the line's month axis every this many months, counted back from the newest.
LINE_LABEL_EVERY = 6


# --- Rank changes on the method page --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HistoryRow:
    """One candidate's line in the rank-history table: its place in each month, oldest first,
    each with whether it was in the top N that month."""

    symbol: str
    cells: list[tuple[int | None, bool]]


@dataclass(frozen=True, slots=True)
class RankChanges:
    """What the method page's "Rank changes" section prints."""

    history: RankHistory
    moves: list[Move]
    rows: list[HistoryRow]
    unadjusted: int

    @property
    def month(self) -> str:
        return month_text(self.history.month)

    @property
    def previous(self) -> str:
        return month_text(self.history.previous_month)

    @property
    def first(self) -> str:
        return month_text(self.history.months[0])

    @property
    def labels(self) -> list[str]:
        return [month_text(month) for month in self.history.months]

    @property
    def top_n(self) -> int:
        return self.history.top_n

    @property
    def any_ranked(self) -> bool:
        return any(ranking.ranked for ranking in self.history.rankings)


def rank_changes(plan: MethodPlan, today: date, months: int = RANK_MONTHS) -> RankChanges:
    """The plan's current candidates ranked in each of the last `months` months, today's month
    last. The earlier months rank today's list, not the list a past version of the plan named, so
    every row compares the same candidates; the page says so."""
    stretch = months_ending((today.year, today.month), months)
    symbols = plan.symbol_list()
    series = price_series(symbols, first_day_needed(stretch))
    history = rank_history(series.of(symbols), stretch, plan.top_n or 1)
    rows = [
        HistoryRow(
            symbol,
            [
                (found.rank, found.top) if found is not None else (None, False)
                for found in (ranking.place_of(symbol) for ranking in history.rankings)
            ],
        )
        for symbol in history.symbols
    ]
    return RankChanges(history, history.moves(), rows, series.unadjusted)


# --- The rolling 12-1 line on a history page ------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LinePoint:
    """One month on the line: the library's point, and where it sits on the plot (percent)."""

    point: Point
    x: Decimal
    y: Decimal | None

    @property
    def label(self) -> str:
        return self.point.label

    @property
    def text(self) -> str:
        change = self.point.change
        return percent_text(change) if change is not None else NOT_ENOUGH


@dataclass(frozen=True, slots=True)
class RollingLine:
    """The rolling 12-1 line for one symbol: every month's point (newest last), the drawn runs,
    the axes, and the zero line's height. `scored` counts the months with a number."""

    symbol: str
    points: list[LinePoint]
    runs: list[str]
    x_ticks: list[Tick]
    y_ticks: list[Tick]
    zero_y: Decimal | None
    unadjusted: int

    @property
    def scored(self) -> int:
        return sum(1 for each in self.points if each.y is not None)

    @property
    def first(self) -> str:
        return self.points[0].label

    @property
    def last(self) -> str:
        return self.points[-1].label

    @property
    def drawn(self) -> list[LinePoint]:
        return [each for each in self.points if each.y is not None]

    @property
    def newest_first(self) -> list[LinePoint]:
        return list(reversed(self.points))

    @property
    def y_width(self) -> int:
        return max((len(tick.label) for tick in self.y_ticks), default=4) + 1

    @property
    def svg_title(self) -> str:
        scored = [each for each in self.points if each.point.change is not None]
        if not scored:
            return f"{self.symbol}: no month from {self.first} to {self.last} has a 12-1 return"
        low = min(scored, key=lambda each: each.point.change or 0)
        high = max(scored, key=lambda each: each.point.change or 0)
        return (
            f"{self.symbol}: rolling 12-1 return, {len(scored)} of {len(self.points)} months from "
            f"{self.first} to {self.last}, lowest {low.text} in {low.label}, highest {high.text} "
            f"in {high.label}"
        )


def x_at(index: int, count: int) -> Decimal:
    if count == 1:
        return Decimal(50)
    return place_pct(Decimal(index) * HUNDRED / (count - 1))


def month_ticks(months: list[Month]) -> list[Tick]:
    """A label every `LINE_LABEL_EVERY` months counted back from the newest, so the newest month
    is always labelled; a label near an edge is aligned to it. Over two labels, every other one
    counted back from the newest is hidden on a narrow screen, as on the price chart."""
    count = len(months)
    ticks: list[Tick] = []
    for index, month in enumerate(months):
        back = count - 1 - index
        if back % LINE_LABEL_EVERY:
            continue
        at = x_at(index, count)
        edge = "start" if at < EDGE_PERCENT else "end" if at > HUNDRED - EDGE_PERCENT else ""
        minor = count > 2 * LINE_LABEL_EVERY and (back // LINE_LABEL_EVERY) % 2 == 1
        ticks.append(Tick(at, month_text(month), edge, minor=minor))
    return ticks


def rolling_line(symbol: str, today: date, months: int = LINE_MONTHS) -> RollingLine:
    """The symbol's 12-1 return for a rebalance in each of the last `months` months, today's last,
    on one scale that always includes zero, so the zero line shows where up turns to down."""
    stretch = months_ending((today.year, today.month), months)
    series = price_series([symbol], first_day_needed(stretch))
    points = rolling(symbol, series.values.get(symbol, []), stretch)
    percents = [point.change * HUNDRED for point in points if point.change is not None]
    count = len(points)
    if not percents:
        placed = [LinePoint(point, x_at(index, count), None) for index, point in enumerate(points)]
        return RollingLine(symbol, placed, [], month_ticks(stretch), [], None, series.unadjusted)
    bottom, top, step = y_scale(min(min(percents), Decimal(0)), max(max(percents), Decimal(0)))

    def y_of(value: Decimal) -> Decimal:
        return place_pct((top - value) * HUNDRED / (top - bottom))

    placed = [
        LinePoint(
            point,
            x_at(index, count),
            y_of(point.change * HUNDRED) if point.change is not None else None,
        )
        for index, point in enumerate(points)
    ]
    by_month = {each.point.month: each for each in placed}
    runs = [
        " ".join(f"{by_month[p.month].x},{by_month[p.month].y}" for p in run)
        for run in segments(points)
        if len(run) > 1
    ]
    ticks = [
        Tick(tick.at, f"{tick.label}%", tick.edge)
        for tick in y_ticks(bottom, top, step, as_money=False)
    ]
    return RollingLine(
        symbol, placed, runs, month_ticks(stretch), ticks, y_of(Decimal(0)), series.unadjusted
    )
```

Things to notice:

- **One query per picture,** through chapter 14's `price_series`, from `first_day_needed`: the start of the oldest
  month's `M-13`. The adjusted close where the row has one, and the count of rows without.
- **The y scale includes zero** whatever the numbers are, so the dashed zero line is always on the chart. It reuses
  the price chart's `y_scale` and `y_ticks`, with a `%` added to each label.
- **The month labels count back from the newest month,** so this month is always labelled, and every other label
  is hidden on a narrow screen, the price chart's rule.

The method page passes one more value, on a momentum plan only. In `methods/views.py`, add the import and one entry
to the context of `render_method_page`:

Listing 14a-6, Filename: `src/invest_witus_site/methods/views.py` (two additions):

```python
from invest_witus_site.methods.momentum_history import rank_changes
```

```python
        # Chapter 14a: how each candidate's rank moved since last month, and its last twelve
        # places, on a 12-1 momentum plan only. One more query, for the closes those months read.
        "rank_changes": (
            rank_changes(plan, through) if plan is not None and plan.is_momentum else None
        ),
```

and include the partial in `method_page.html`, under chapter 14's:

```html
  {% if rank_changes %}{% include "methods/_rank_changes.html" with changes=rank_changes %}{% endif %}
```

Listing 14a-7, Filename: `src/invest_witus_site/methods/templates/methods/_rank_changes.html`:

```html
{# Rank changes (chapter 14a), on the method page of an account that runs 12-1 momentum, under the ranking. #}
{# Included by methods/method_page.html with `changes` (a RankChanges). Two tables, no script: each candidate's #}
{# move since last month with an arrow and words, then its place in each of the last twelve months. #}
<section class="card" aria-labelledby="rank-changes-heading">
  <h2 id="rank-changes-heading">Rank changes since {{ changes.previous }}</h2>
  {% if changes.any_ranked %}
  <p>Where each candidate ranked for the {{ changes.month }} rebalance, where it ranked for {{ changes.previous }}, and how far it moved. Place 1 is the highest 12-1 return; the plan holds the top {{ changes.top_n }}.</p>
  <div class="table-scroll" role="region" aria-labelledby="moves-caption" tabindex="0">
  <table class="holdings rank-moves">
    <caption id="moves-caption">Each candidate's place for {{ changes.month }} and for {{ changes.previous }}, in this month's order</caption>
    <thead>
      <tr>
        <th scope="col">Symbol</th>
        <th scope="col" class="num">{{ changes.month }}</th>
        <th scope="col" class="num">{{ changes.previous }}</th>
        <th scope="col">Move</th>
        <th scope="col">Top {{ changes.top_n }}</th>
      </tr>
    </thead>
    <tbody>
      {% for move in changes.moves %}
      <tr>
        <th scope="row">{{ move.symbol }}</th>
        <td class="num">{% if move.rank %}{{ move.rank }}{% else %}not ranked{% endif %}</td>
        <td class="num">{% if move.previous %}{{ move.previous }}{% else %}not ranked{% endif %}</td>
        <td><span class="rank-move rank-move-{{ move.direction }}">{{ move.text }}</span></td>
        <td>{% if move.top_change == "joined" %}joined the top {{ changes.top_n }}{% elif move.top_change == "left" %}left the top {{ changes.top_n }}{% elif move.top %}in{% else %}out{% endif %}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  </div>
  <div class="table-scroll" role="region" aria-labelledby="rank-history-caption" tabindex="0">
  <table class="holdings rank-history">
    <caption id="rank-history-caption">Each candidate's place for every rebalance from {{ changes.first }} to {{ changes.month }}, oldest on the left. A place in bold was in the top {{ changes.top_n }}; "n/r" means not ranked that month; equal returns take places A to Z, as in the ranking above.</caption>
    <thead>
      <tr>
        <th scope="col">Symbol</th>
        {% for label in changes.labels %}<th scope="col" class="num">{{ label }}</th>{% endfor %}
      </tr>
    </thead>
    <tbody>
      {% for row in changes.rows %}
      <tr>
        <th scope="row">{{ row.symbol }}</th>
        {% for rank, top in row.cells %}<td class="num">{% if rank is None %}<abbr title="not ranked">n/r</abbr>{% elif top %}<strong>{{ rank }}</strong><span class="sr-only"> (top {{ changes.top_n }})</span>{% else %}{{ rank }}{% endif %}</td>{% endfor %}
      </tr>
      {% endfor %}
    </tbody>
  </table>
  </div>
  {% if changes.unadjusted %}<p class="small">{{ changes.unadjusted }} stored close{{ changes.unadjusted|pluralize }} in these months had no adjusted close, so the plain close was used; a split would then read as a fall.</p>{% endif %}
  {% else %}
  <p>No candidate can be ranked in any month from {{ changes.first }} to {{ changes.month }} yet: none has a close stored in both months of a window. The ranking above says which history is missing.</p>
  {% endif %}
  <p class="how-to-read"><strong>How to read this.</strong> The method acts on rank, not on the return itself: at each rebalance it holds whatever sits in the top {{ changes.top_n }}. An arrow up means the candidate's 12-1 return now ranks higher among your candidates than it did last month; "joined" or "left" means the move crossed the top {{ changes.top_n }} line, which is when the method buys or sells. Every month is ranked with your candidates as they are today, so a month before you changed the list shows how today's list would have ranked then. "not ranked" means a close is missing at one end of that month's window; the app never fills it in. <span class="muted">Lesson coming.</span></p>
  <p class="small muted">Arithmetic on stored closes of the candidates you chose. A past rank is not a forecast. Information, not advice.</p>
</section>
```

The history page does the same on the account chapter 14 shades the window for. In `watchlist/views.py`, import
`rolling_line` and add to the context of `history`:

Listing 14a-8, Filename: `src/invest_witus_site/watchlist/views.py` (one addition):

```python
        "rolling": rolling_line(item.symbol, today) if window is not None else None,
```

and include the partial in `history.html`, under the window's:

```html
  {% if rolling %}{% include "watchlist/_rolling_12_1.html" %}{% endif %}
```

Listing 14a-9, Filename: `src/invest_witus_site/watchlist/templates/watchlist/_rolling_12_1.html`:

```html
{% load holdings_extras %}
{# The rolling 12-1 line (chapter 14a), on a watched symbol's history page, on an account running 12-1 momentum. #}
{# Included by watchlist/history.html with `rolling` (a RollingLine) and `item`. The plot is an SVG stretched to #}
{# its box like the price chart, its axes HTML beside it; the dots are HTML so they stay round. The table under it #}
{# is the text alternative and lists every month, the ones without a number too. No script. #}
<section aria-labelledby="rolling-heading">
  <h2 id="rolling-heading">{{ item.symbol }}'s 12-1 return, month by month</h2>
  <p>For each month from {{ rolling.first }} to {{ rolling.last }}: the 12-1 return a rebalance in that month reads, from the last close 13 months back to the last close 2 months back, on adjusted closes. {{ rolling.scored }} of {{ rolling.points|length }} months have enough history for a number. This line does not follow the range picked above.</p>
  {% if rolling.scored %}
  <figure class="chart rolling-chart" aria-labelledby="rolling-title">
    <figcaption class="chart-caption">
      <p class="chart-title" id="rolling-title">Rolling 12-1 return of {{ item.symbol }}, {{ rolling.first }} to {{ rolling.last }}</p>
      <p class="small muted">One dot per month with a number; the line breaks at a month without one. The dashed line is zero: above it the window rose, below it the window fell.</p>
    </figcaption>
    <div class="chart-frame" style="--y-width: {{ rolling.y_width }}ch">
      <p class="axis-title axis-y">12-1 return, percent</p>
      <div class="chart-y" aria-hidden="true">
        {% for tick in rolling.y_ticks %}<span style="top: {{ tick.at }}%">{{ tick.label }}</span>{% endfor %}
      </div>
      <div class="chart-plot">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-labelledby="rolling-svg-title rolling-svg-desc" data-points="{{ rolling.scored }}">
          <title id="rolling-svg-title">{{ rolling.svg_title }}</title>
          <desc id="rolling-svg-desc">One point per month, oldest on the left, with a dashed zero line. The table below lists every month's number or why it has none.</desc>
          {% for tick in rolling.y_ticks %}<line class="grid" x1="0" x2="100" y1="{{ tick.at }}" y2="{{ tick.at }}" vector-effect="non-scaling-stroke"/>{% endfor %}
          <line class="rolling-zero" x1="0" x2="100" y1="{{ rolling.zero_y }}" y2="{{ rolling.zero_y }}" vector-effect="non-scaling-stroke"/>
          {% for run in rolling.runs %}<polyline class="rolling-run" points="{{ run }}" fill="none" vector-effect="non-scaling-stroke"/>{% endfor %}
        </svg>
        {% for each in rolling.drawn %}<span class="rolling-dot" style="left: {{ each.x }}%; top: {{ each.y }}%" title="{{ each.label }}: {{ each.text }}" aria-hidden="true"></span>{% endfor %}
      </div>
      <div class="chart-x" aria-hidden="true">
        {% for tick in rolling.x_ticks %}<span class="{{ tick.edge }}{% if tick.minor %} minor{% endif %}" style="left: {{ tick.at }}%">{{ tick.label }}</span>{% endfor %}
      </div>
      <p class="axis-title axis-x">Rebalance month</p>
    </div>
  </figure>
  {% else %}
  <p>No month from {{ rolling.first }} to {{ rolling.last }} has enough history for a 12-1 return yet. <strong>Get history</strong> below with 5 years fetches the closes the windows need.</p>
  {% endif %}
  <p class="how-to-read"><strong>How to read this.</strong> Each dot is the number the method's ranking reads, or would have read, for a rebalance in that month. A line climbing means the past eleven months kept looking better from one month to the next; a line crossing zero means the window turned from a rise to a fall. The newest dot is this month's 12-1 return, the same as the window above. A month with no dot is missing a close at one end of its window, and says "not enough history" in the table; the app never fills it in from a neighbor. <span class="muted">Lesson coming.</span></p>
  {% if rolling.unadjusted %}<p class="small">{{ rolling.unadjusted }} stored close{{ rolling.unadjusted|pluralize }} in these months had no adjusted close, so the plain close was used; a split would then read as a fall.</p>{% endif %}
  <div class="table-scroll" role="region" aria-labelledby="rolling-caption" tabindex="0">
  <table class="holdings">
    <caption id="rolling-caption">{{ item.symbol }}'s 12-1 return for each rebalance month, newest first, with the two closes it is computed from</caption>
    <thead>
      <tr>
        <th scope="col">Month</th>
        <th scope="col" class="num">12-1 return</th>
        <th scope="col">From</th>
        <th scope="col">To</th>
      </tr>
    </thead>
    <tbody>
      {% for each in rolling.newest_first %}
      <tr>
        <th scope="row">{{ each.label }}</th>
        {% if each.point.score %}
        <td class="num">{{ each.text }}</td>
        <td>{{ each.point.score.start_day|date:"Y-m-d" }}, {{ each.point.score.start_close|money }}</td>
        <td>{{ each.point.score.end_day|date:"Y-m-d" }}, {{ each.point.score.end_close|money }}</td>
        {% else %}
        <td class="num">not enough history</td>
        <td colspan="2">{{ each.point.reason }}</td>
        {% endif %}
      </tr>
      {% endfor %}
    </tbody>
  </table>
  </div>
  <p class="small muted">Arithmetic on the stored closes. A past return is not a forecast. Information, not advice.</p>
</section>
```

Things to notice:

- **The dots are HTML, the line is SVG.** The SVG is stretched to its box, so a circle in it would draw as an
  ellipse; a `span` placed by the same percentages stays round.
- **`n/r` is an `abbr`,** and a bold place carries " (top 2)" in a `sr-only` span, so a screen reader hears what
  sighted readers see in bold.
- **The table lists every month,** with "not enough history" and the months a window needs, newest first.

`site.css` gets a short block: the move colors, the rank tables kept on one line, the zero line, the run and the dot.

### 14a.4 Green, and both pictures on your laptop

Listing 14a-10, Terminal:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run --env-file .env python manage.py makemigrations --check --dry-run
```

```text
793 passed in 26.32s
All checks passed!
240 files already formatted
0 errors, 0 warnings, 0 informations
No changes detected
```

Fifteen new tests, and no migration: nothing is stored that was not stored before. Start a momentum plan on a new
account with the six crossing candidates, plant their closes with the test's own helper, and read the moves:

Listing 14a-11, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -v 0 -c "
import re
from django.contrib.auth.models import User
from django.test import Client
from invest_witus_site.holdings.models import Account
from tests.test_ch10 import tables_in, text
from tests.test_ch14a import crossing, plant_all, this_month
u = User.objects.get(is_superuser=True); c = Client(); c.force_login(u)
a, _ = Account.objects.get_or_create(owner=u, name='Crossing practice', defaults={'broker': 'Example Brokerage', 'kind': 'paper'})
m = this_month()
c.post(f'/accounts/{a.pk}/method/start/', {'method_id': 'momentum-12-1', 'amount': '100', 'buy_window_days': '7', 'symbols': 'ALPHA BETA GAMMA EPSILON ZETA DELTA', 'started_on': f'{m[0]}-{m[1]:02d}-01', 'top_n': '2'})
plant_all(crossing(m))
page = text(c.get(f'/accounts/{a.pk}/method/?view=a'))
print(re.search(r'<h2 id=\"rank-changes-heading\">([^<]+)<', page).group(1))
tables = tables_in(page)
for row in next(t for t in tables if 'Move' in t[0]): print(row)
places = next(t for t in tables if t[0][0] == 'Symbol' and len(t[0]) == 13)
for row in places: print(row[0], *row[-4:], sep=' | ')
"
```

```text
Rank changes since 2026-10
('Symbol', '2026-11', '2026-10', 'Move', 'Top 2')
('BETA', '1', '3', '▲ up 2 places', 'joined the top 2')
('GAMMA', '2', '2', '◆ same place', 'in')
('ALPHA', '3', '1', '▼ down 2 places', 'left the top 2')
('EPSILON', '4', 'not ranked', 'new in the ranking', 'out')
('DELTA', 'not ranked', 'not ranked', 'not ranked', 'out')
('ZETA', 'not ranked', '4', 'not ranked this month', 'out')
Symbol | 2026-08 | 2026-09 | 2026-10 | 2026-11
BETA | 2 (top 2) | 2 (top 2) | 3 | 1 (top 2)
GAMMA | 3 | 3 | 2 (top 2) | 2 (top 2)
ALPHA | 1 (top 2) | 1 (top 2) | 1 (top 2) | 3
EPSILON | n/r | n/r | n/r | 4
DELTA | n/r | n/r | n/r | n/r
ZETA | 4 | 4 | 4 | n/r
```

Your months are the month you run it in and the ones before. Check BETA by hand: last month its window ended at
100 (0%, third), this month it ends at 120 (+20%, first): up two places, into the top 2. In August and September
every flat candidate returned 0%, so the places there are the A to Z tie order. Now read ALPHA's line:

Listing 14a-12, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -v 0 -c "
import re
from django.contrib.auth.models import User
from django.test import Client
from invest_witus_site.holdings.models import Account
from tests.test_ch10 import tables_in, text
u = User.objects.get(is_superuser=True); a = Account.objects.get(owner=u, name='Crossing practice'); c = Client(); c.force_login(u)
page = text(c.get(f'/accounts/{a.pk}/watch/ALPHA/?days=all'))
print(re.search(r'(\d+ of \d+ months have enough history)', page).group(1))
table = next(t for t in tables_in(page) if t[0] == ('Month', '12-1 return', 'From', 'To'))
for row in table[:5]: print(row)
print(table[-1])
"
```

```text
10 of 24 months have enough history
('Month', '12-1 return', 'From', 'To')
('2026-11', '0.0%', '2025-10-28, $100.00', '2026-09-28, $100.00')
('2026-10', '+30.0%', '2025-09-28, $100.00', '2026-08-28, $130.00')
('2026-09', '0.0%', '2025-08-28, $100.00', '2026-07-28, $100.00')
('2026-08', '0.0%', '2025-07-28, $100.00', '2026-06-28, $100.00')
('2024-12', 'not enough history', 'no close stored in 2023-11 or 2024-10; the window needs a close in 2023-11 and in 2024-10')
```

ALPHA's planted closes start 22 months back, so only the newest ten months have both ends. In a browser, sign in,
open **Crossing practice**: the method page shows **Rank changes** under the ranking; click ALPHA on the account
page's watch list to see the line, its spike in the month whose window ended on the 130 close, and the gap where
the history runs out.

### 14a.5 What the owner does outside the editor

Nothing new to set up: no variable, no package, no migration. Merge the chapter, open a momentum account's method
page and a candidate's history page, and press **Get history** with 5 years for any candidate whose older months
say "not enough history".

## Checkpoint

- `uv run pytest` prints `793 passed`; ruff, pyright and `makemigrations --check` pass.
- Listing 14a-11 prints six moves, one of each kind, and twelve months of places with the top 2 marked.
- Listing 14a-12 prints ten months with a number and "not enough history" with the months it needs.
- An index plan's pages are as they were: no Rank changes, no rolling line.
- Commit and push: `git add -A && git commit -m "Chapter 14a: rank changes and the rolling 12-1 line"`.

## Exercises

1. **A bump chart.** Draw the rank history as lines, one per candidate, place 1 at the top, with a gap at each
   "n/r". Keep the table as its text alternative.
2. **The list each version named.** Rank each past month with the candidates the plan version active in that month
   named, and mark the month where the list changed. Write the decision first: what does a move mean across a
   change of list?
3. **Every candidate on one line chart.** On the method page, draw each candidate's rolling 12-1 line on one chart
   with the price chart's dash patterns, so no line is told apart by color alone.
4. **Quintiles.** Split the candidates into five groups by this month's 12-1 return and show which group the top N
   comes from (the momentum views backlog, item 5).

## If you get stuck

- Browse: https://github.com/dapperAuteur/invest-witus/tree/v14a
- Diff for this chapter: https://github.com/dapperAuteur/invest-witus/compare/17335d2...v14a (the diff from `v14`
  also holds the work between chapters that step 14a.0 takes)
- Zip: https://github.com/dapperAuteur/invest-witus/archive/v14a.zip
- Take the reference's files. Chapter 14a added `src/invest_witus/methods/momentum_history.py`,
  `src/invest_witus_site/methods/momentum_history.py`, the templates `methods/_rank_changes.html` and
  `watchlist/_rolling_12_1.html`, and `tests/test_ch14a.py`; and changed `methods/views.py`,
  `methods/templates/methods/method_page.html`, `watchlist/views.py`, `watchlist/templates/watchlist/history.html`
  and `pages/static/pages/site.css`. Nothing moved: `git fetch reference --tags && git checkout v14a -- src tests`.
- `test_too_little_history_says_not_enough_instead_of_a_number` finds no scored month with twelve closes: your
  window asks for thirteen month-ends. The start is `M-13` and the end `M-2`: twelve month-ends apart, not thirteen.
- `test_each_candidate_moves_from_its_place_last_month_to_its_place_this_month` finds EPSILON "◆ same place":
  `places` returned 0 where a month had no rank. Return `None`.
- `test_a_gap_at_a_windows_end_breaks_the_line_and_a_gap_inside_it_does_not_change_it` finds one run: `segments`
  skipped the months without a number instead of closing the run there.
- The rolling line's dots are ovals: they are drawn inside the stretched SVG. Draw them as HTML, as Listing 14a-9
  does.

## What we learned

- A series of a computed number is the same function in a loop; call it, do not copy its arithmetic.
- "Not enough history" is an answer. Keep the reason, show it in the table, and leave the gap in the chart.
- A move needs two places. When one is missing, say what happened in words instead of printing a zero.
- A history table means something only if every column compares the same thing; when the app chooses what that
  is, the page has to say so.
- A zero line turns a line chart of returns into a picture of rises and falls.

## Next

Chapter 15 compares your methods: two to four accounts on one chart beside an index fund, with what each put in,
holds and gained (decision 167 placed it before the CentenarianOS events, now chapter 16).

## References

French, K. R. (n.d.). *Detail for monthly momentum factor (Mom)*. Kenneth R. French Data Library, Tuck School of
Business at Dartmouth. Retrieved November 1, 2026, from
https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/det_mom_factor.html

Jegadeesh, N., & Titman, S. (1993). Returns to buying winners and selling losers: Implications for stock market
efficiency. *The Journal of Finance, 48*(1), 65-91. https://doi.org/10.1111/j.1540-6261.1993.tb04702.x
