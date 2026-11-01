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
