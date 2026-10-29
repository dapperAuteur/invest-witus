"""A symbol's stored closes over a range: the ranges the chart pages offer and the queries.

The chart itself is built in `charts.py` (2026-10-29): server-rendered SVG with its axes, key and
hover data, and the closes as a table under it, so the picture is never the only way to read
them.

Since 2026-10-29 (decision 140) the pages offer longer presets (5 years, 10 years, All) beside
the 30, 90 and 365 days they open on, and a From and To date pair (`?from=YYYY-MM-DD&to=...`)
that sets the chart and the table together. `chosen_range` reads them; a bad pair is a
`RangeError` whose words the page prints, never a 500.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from django.db.models import Max, Min
from django.http import QueryDict

from invest_witus_site.prices.manual import years_before
from invest_witus_site.prices.models import DailyClose

# The ranges the page offers, in calendar days, and the one it opens on.
RANGES = (30, 90, 365)
DEFAULT_RANGE = 90


# The compare page opens on a year: comparing is about the longer run.
COMPARE_DEFAULT_RANGE = 365

# The longer presets (2026-10-29): `?days=5y`, `?days=10y` and `?days=all`, each with its label.
# A number of years is the same calendar day that many years back; All has no lower bound.
LONG_RANGES: dict[str, tuple[str, int | None]] = {
    "5y": ("5 years", 5),
    "10y": ("10 years", 10),
    "all": ("All", None),
}


def range_days(text: str | None, default: int = DEFAULT_RANGE) -> int:
    """`?days=` as one of `RANGES`; anything else is the default, never an error."""
    try:
        days = int(text or "")
    except ValueError:
        return default
    return days if days in RANGES else default


@dataclass(frozen=True, slots=True)
class Preset:
    """One link or option in the range picker: its `?days=` value and its words."""

    key: str
    label: str


PRESETS: tuple[Preset, ...] = (
    *(Preset(str(days), f"{days} days") for days in RANGES),
    *(Preset(key, label) for key, (label, _) in LONG_RANGES.items()),
)


@dataclass(frozen=True, slots=True)
class ChosenRange:
    """The range a chart page shows. `since` and `until` bound the stored days (None is open),
    `key` is the preset's `?days=` value or "custom", `title` goes in the chart's title ("last 30
    days", "2020-01-02 to 2024-12-31"), `within` after "every stored day" or "No closes stored",
    and `query` is the part of a link that keeps the range."""

    key: str
    since: date | None
    until: date | None
    title: str
    within: str
    query: str

    @property
    def custom(self) -> bool:
        return self.key == "custom"


class RangeError(ValueError):
    """A From and To pair the page cannot show; the message is for the owner."""


def preset_range(key: str, today: date) -> ChosenRange:
    """A preset by its `?days=` value; the caller has checked it is one."""
    if key in LONG_RANGES:
        label, years = LONG_RANGES[key]
        if years is None:
            return ChosenRange(key, None, None, "all stored days", "in all stored days", "days=all")
        since = years_before(today, years)
        return ChosenRange(key, since, None, f"last {label}", f"in the last {label}", f"days={key}")
    days = int(key)
    return ChosenRange(
        key,
        today - timedelta(days=days),
        None,
        f"last {days} days",
        f"in the last {days} days",
        f"days={days}",
    )


def preset_key(text: str | None, default: int) -> str:
    """`?days=` as a preset key; an unknown value is the default, never an error."""
    if text in LONG_RANGES:
        return text
    return str(range_days(text, default=default))


def parse_day(text: str, name: str) -> date:
    try:
        if len(text) != 10:
            raise ValueError(text)
        return date.fromisoformat(text)
    except ValueError:
        raise RangeError(f"{name} is not a date in the form YYYY-MM-DD: {text!r}.") from None


@dataclass(frozen=True, slots=True)
class StoredSpan:
    """The oldest and newest stored day for a set of symbols, or None for each when none is."""

    first: date | None
    last: date | None


def stored_span(symbols: list[str]) -> StoredSpan:
    found = DailyClose.objects.filter(symbol__in=symbols).aggregate(
        first=Min("date"), last=Max("date")
    )
    return StoredSpan(found["first"], found["last"])


def chosen_range(
    params: QueryDict, today: date, span: StoredSpan, default: int = DEFAULT_RANGE
) -> ChosenRange:
    """`?from=` and `?to=` when either is given, else the `?days=` preset. Raises `RangeError`
    when the pair is incomplete, not two dates, not in order (From before To), or outside the
    stored closes (`span`)."""
    start = (params.get("from") or "").strip()
    end = (params.get("to") or "").strip()
    if not start and not end:
        return preset_range(preset_key(params.get("days"), default), today)
    if not start or not end:
        raise RangeError("Pick both a From date and a To date, or one of the ranges above.")
    since, until = parse_day(start, "From"), parse_day(end, "To")
    if since >= until:
        raise RangeError(f"From ({since:%Y-%m-%d}) must be before To ({until:%Y-%m-%d}).")
    if span.first is None or span.last is None:
        raise RangeError("No closes are stored yet, so there is no range to pick from.")
    if since < span.first or until > span.last:
        raise RangeError(
            f"Pick dates within the stored closes, {span.first:%Y-%m-%d} to {span.last:%Y-%m-%d}; "
            f"{since:%Y-%m-%d} to {until:%Y-%m-%d} is not."
        )
    text = f"{since:%Y-%m-%d} to {until:%Y-%m-%d}"
    return ChosenRange(
        "custom",
        since,
        until,
        text,
        f"from {text}",
        f"from={since:%Y-%m-%d}&to={until:%Y-%m-%d}",
    )


def closes_since(symbol: str, since: date) -> list[DailyClose]:
    """The stored closes from `since` on, oldest first."""
    return closes_between(symbol, since, None)


def closes_between(symbol: str, since: date | None, until: date | None) -> list[DailyClose]:
    """The stored closes from `since` through `until`, oldest first; None leaves that end open."""
    rows = DailyClose.objects.filter(symbol=symbol)
    if since is not None:
        rows = rows.filter(date__gte=since)
    if until is not None:
        rows = rows.filter(date__lte=until)
    return list(rows.order_by("date"))


def close_before(symbol: str, day: date | None) -> DailyClose | None:
    """The newest stored close before `day`: the first day's "change from the day before". With
    no lower bound (All) there is none."""
    if day is None:
        return None
    return DailyClose.objects.filter(symbol=symbol, date__lt=day).order_by("-date").first()
