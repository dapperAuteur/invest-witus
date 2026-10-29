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
