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
