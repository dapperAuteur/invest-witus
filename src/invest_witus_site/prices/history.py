"""A symbol's stored closes over a range, and the small line chart the history page draws from them.

The chart is server-rendered SVG: the view computes each point's place here, in Decimal, and the
template writes the `<polyline>`. No JavaScript and no charting library; the table under the chart
holds the same closes as text, so the picture is never the only way to read them.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from invest_witus_site.prices.models import DailyClose

# The ranges the page offers, in calendar days, and the one it opens on.
RANGES = (30, 90, 365)
DEFAULT_RANGE = 90

# The drawing's own units: the SVG's viewBox. It scales to the column's width on the page.
WIDTH = 600
HEIGHT = 200
PADDING = 12
COORDINATE_STEP = Decimal("0.1")


def range_days(text: str | None) -> int:
    """`?days=` as one of `RANGES`; anything else is the default, never an error."""
    try:
        days = int(text or "")
    except ValueError:
        return DEFAULT_RANGE
    return days if days in RANGES else DEFAULT_RANGE


def closes_since(symbol: str, since: date) -> list[DailyClose]:
    """The stored closes from `since` on, oldest first."""
    return list(DailyClose.objects.filter(symbol=symbol, date__gte=since).order_by("date"))


@dataclass(frozen=True, slots=True)
class ChartPoint:
    x: Decimal
    y: Decimal


@dataclass(frozen=True, slots=True)
class Chart:
    """What the template draws: the points in order, the lowest and highest close, the first and
    last day. `points` is the `<polyline>`'s attribute, `x,y` pairs separated by spaces."""

    width: int
    height: int
    plotted: list[ChartPoint]
    low: Decimal
    high: Decimal
    first: date
    last: date

    @property
    def count(self) -> int:
        return len(self.plotted)

    @property
    def points(self) -> str:
        return " ".join(f"{point.x},{point.y}" for point in self.plotted)

    @property
    def latest(self) -> ChartPoint:
        return self.plotted[-1]


def place(value: Decimal) -> Decimal:
    return value.quantize(COORDINATE_STEP, rounding=ROUND_HALF_UP)


def line_chart(closes: list[DailyClose]) -> Chart | None:
    """Days along x by calendar distance (a weekend is a gap, not a squeeze), closes along y from
    the range's lowest at the bottom to its highest at the top. One close, or a flat range, sits
    in the middle. No closes, no chart."""
    if not closes:
        return None
    first, last = closes[0].date, closes[-1].date
    low = min(row.close for row in closes)
    high = max(row.close for row in closes)
    span_days = (last - first).days
    inner_width = Decimal(WIDTH - 2 * PADDING)
    inner_height = Decimal(HEIGHT - 2 * PADDING)
    plotted: list[ChartPoint] = []
    for row in closes:
        if span_days == 0:
            x = Decimal(WIDTH) / 2
        else:
            x = PADDING + inner_width * (row.date - first).days / span_days
        if high == low:
            y = Decimal(HEIGHT) / 2
        else:
            y = PADDING + inner_height * (high - row.close) / (high - low)
        plotted.append(ChartPoint(place(x), place(y)))
    return Chart(WIDTH, HEIGHT, plotted, low, high, first, last)
