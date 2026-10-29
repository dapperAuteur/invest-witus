"""A symbol's stored closes over a range: the ranges the chart pages offer and the queries.

The chart itself is built in `charts.py` (2026-10-29): server-rendered SVG with its axes, key and
hover data, and the closes as a table under it, so the picture is never the only way to read
them.
"""

from datetime import date

from invest_witus_site.prices.models import DailyClose

# The ranges the page offers, in calendar days, and the one it opens on.
RANGES = (30, 90, 365)
DEFAULT_RANGE = 90


# The compare page opens on a year: comparing is about the longer run.
COMPARE_DEFAULT_RANGE = 365


def range_days(text: str | None, default: int = DEFAULT_RANGE) -> int:
    """`?days=` as one of `RANGES`; anything else is the default, never an error."""
    try:
        days = int(text or "")
    except ValueError:
        return default
    return days if days in RANGES else default


def closes_since(symbol: str, since: date) -> list[DailyClose]:
    """The stored closes from `since` on, oldest first."""
    return list(DailyClose.objects.filter(symbol=symbol, date__gte=since).order_by("date"))


def close_before(symbol: str, day: date) -> DailyClose | None:
    """The newest stored close before `day`: the first day's "change from the day before"."""
    return DailyClose.objects.filter(symbol=symbol, date__lt=day).order_by("-date").first()
