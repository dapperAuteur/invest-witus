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
