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
    is always labelled; a label near an edge is aligned to it."""
    count = len(months)
    ticks: list[Tick] = []
    for index, month in enumerate(months):
        if (count - 1 - index) % LINE_LABEL_EVERY:
            continue
        at = x_at(index, count)
        edge = "start" if at < EDGE_PERCENT else "end" if at > HUNDRED - EDGE_PERCENT else ""
        ticks.append(Tick(at, month_text(month), edge))
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
