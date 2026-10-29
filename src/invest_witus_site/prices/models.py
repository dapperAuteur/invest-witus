"""One close per symbol per day, in the app's own table, so a page never asks a vendor.

The nightly pull (`pull.py`) writes here through `upsert`, which is idempotent: a day already
stored with the same close is left alone, so a cron that runs twice, or a pull repeated by hand,
changes nothing. The owner's pages read `latest_for`, the newest stored close per symbol, and
show its date beside the value.

Since 2026-10-29 a row also keeps the vendor's adjusted close (`adj_close`), so a chart over a
long range does not draw a split as a crash. An adjusted close is relative to the newest day the
vendor knew when it answered: after a split or a dividend, every earlier day's adjusted close
changes by the same factor. `upsert` keeps the stored ones on one footing by rescaling the days
the answer did not cover (decision 120).
"""

import datetime
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, NamedTuple

from django.db import models
from django.db.models import Max, Q
from django.utils import timezone

from invest_witus.prices.csv_file import PricePoint
from invest_witus.valuation import Quote
from invest_witus_site.prices.points import extras

# Six decimal places, like shares in chapter 05: a vendor's raw close has two to four, and the
# column keeps what it was sent rather than rounding a price to cents before it is multiplied.
PRICE_PLACES = 6
PRICE_STEP = Decimal(1).scaleb(-PRICE_PLACES)


def to_close(value: Decimal) -> Decimal:
    """Round to the column's places, halves away from zero, before the database rounds for us."""
    return value.quantize(PRICE_STEP, rounding=ROUND_HALF_UP)


@dataclass(frozen=True, slots=True)
class UpsertCount:
    """What one `upsert` did. Added together across symbols by the pull."""

    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    # Stored days outside the answer whose adjusted close was rescaled to the answer's footing.
    rescaled: int = 0

    def __add__(self, other: UpsertCount) -> UpsertCount:
        return UpsertCount(
            self.inserted + other.inserted,
            self.updated + other.updated,
            self.unchanged + other.unchanged,
            self.rescaled + other.rescaled,
        )

    def __str__(self) -> str:
        text = f"inserted {self.inserted}, updated {self.updated}, unchanged {self.unchanged}"
        return f"{text}, rescaled {self.rescaled}" if self.rescaled else text


VALUE_FIELDS = ["close", "adj_close", "split_factor", "div_cash"]


class Values(NamedTuple):
    """One day's numbers, rounded to the columns' places, to compare a stored row with an answer.
    Decimal equality ignores trailing zeros, so 4 and 4.000000 are the same."""

    close: Decimal
    adj_close: Decimal | None
    split_factor: Decimal | None
    div_cash: Decimal | None


def rounded(value: Decimal | None) -> Decimal | None:
    return None if value is None else to_close(value)


class DailyClose(models.Model):
    """The closing price of one symbol on one day, and where and when the app got it."""

    symbol: models.CharField[str, str] = models.CharField(max_length=20)
    date: models.DateField[datetime.date, datetime.date] = models.DateField(
        help_text="The trading day the close is for."
    )
    close: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=18, decimal_places=PRICE_PLACES
    )
    # Nullable with a database default of NULL (decision 111): the previous release keeps
    # inserting rows while the migration runs, and a CSV source has no adjusted close at all.
    adj_close: models.DecimalField[Decimal | None, Decimal | None] = models.DecimalField(
        max_digits=18,
        decimal_places=PRICE_PLACES,
        null=True,
        blank=True,
        default=None,
        db_default=None,
        help_text="The close adjusted for splits and dividends (Tiingo's adjClose); empty when "
        "the source sent none.",
    )
    # The day's corporate actions as the vendor reports them (decision 123): 1 and 0 on an
    # ordinary day, None when the source sent nothing (a CSV file, or a row stored before).
    split_factor: models.DecimalField[Decimal | None, Decimal | None] = models.DecimalField(
        max_digits=18,
        decimal_places=PRICE_PLACES,
        null=True,
        blank=True,
        default=None,
        db_default=None,
        help_text="Tiingo's splitFactor: 4 on the day of a 4-for-1 split, 1 on other days.",
    )
    div_cash: models.DecimalField[Decimal | None, Decimal | None] = models.DecimalField(
        max_digits=18,
        decimal_places=PRICE_PLACES,
        null=True,
        blank=True,
        default=None,
        db_default=None,
        help_text="Tiingo's divCash: the cash dividend whose ex-date is this day, 0 on others.",
    )
    source: models.CharField[str, str] = models.CharField(
        max_length=40, help_text="Which source answered: tiingo, or csv on a laptop."
    )
    fetched_at: models.DateTimeField[datetime.datetime, datetime.datetime] = models.DateTimeField(
        help_text="When the pull wrote or last changed this row."
    )

    class Meta:
        ordering = ["symbol", "-date"]
        constraints = [
            models.UniqueConstraint(
                fields=["symbol", "date"], name="close_once_per_symbol_and_day"
            ),
        ]
        verbose_name = "daily close"
        verbose_name_plural = "daily closes"

    def __str__(self) -> str:
        return f"{self.symbol} {self.date:%Y-%m-%d} {self.close}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """The same guards as a statement line: the symbol's case, the rounding, and no float."""
        if isinstance(self.close, float):
            raise TypeError(f"close must be a Decimal, not a float ({self.close!r})")
        if isinstance(self.adj_close, float):
            raise TypeError(f"adj_close must be a Decimal, not a float ({self.adj_close!r})")
        self.symbol = self.symbol.strip().upper()
        self.close = to_close(self.close)
        if self.adj_close is not None:
            self.adj_close = to_close(self.adj_close)
        if self.split_factor is not None:
            self.split_factor = to_close(self.split_factor)
        if self.div_cash is not None:
            self.div_cash = to_close(self.div_cash)
        super().save(*args, **kwargs)

    @property
    def is_split(self) -> bool:
        return self.split_factor is not None and self.split_factor != 1

    @property
    def is_dividend(self) -> bool:
        return self.div_cash is not None and self.div_cash > 0

    @property
    def charted(self) -> Decimal:
        """The adjusted close when stored, else the close: what a chart of one day uses."""
        return self.close if self.adj_close is None else self.adj_close

    def values(self) -> Values:
        return Values(self.close, self.adj_close, self.split_factor, self.div_cash)

    def quote(self) -> Quote:
        return Quote(close=self.close, as_of=self.date, source=self.source)

    @classmethod
    def upsert(
        cls,
        symbol: str,
        points: Iterable[PricePoint],
        source: str,
        now: datetime.datetime | None = None,
    ) -> UpsertCount:
        """Write each day once. A day already stored with the same close, adjusted close, split
        factor, dividend and source is left alone, `fetched_at` included, so a re-run changes
        nothing. A different value (a vendor's correction, a second source, or an adjusted close
        arriving for a day stored without one) replaces the row and counts as an update.

        Then the footing: when the answer's oldest day that was already stored with an adjusted
        close now has a different one, a split or a dividend has happened since that row was
        written, and every stored day the answer did not cover moves by the same ratio. That is
        what the vendor does to its own history (an adjustment multiplies every earlier day by
        one factor), so the nightly week keeps a long history consistent without asking for it
        again."""
        symbol = symbol.strip().upper()
        wanted: dict[datetime.date, Values] = {}
        for point in points:
            adjusted, split, dividend = extras(point)
            wanted[point.day] = Values(
                to_close(point.close), rounded(adjusted), rounded(split), rounded(dividend)
            )
        existing = {row.date: row for row in cls.objects.filter(symbol=symbol, date__in=wanted)}
        ratio = footing_ratio(existing, wanted)
        stamp = now or timezone.now()
        inserted = updated = unchanged = 0
        new_rows: list[DailyClose] = []
        for day, values in sorted(wanted.items()):
            row = existing.get(day)
            if row is None:
                new_rows.append(
                    cls(
                        symbol=symbol,
                        date=day,
                        close=values.close,
                        adj_close=values.adj_close,
                        split_factor=values.split_factor,
                        div_cash=values.div_cash,
                        source=source,
                        fetched_at=stamp,
                    )
                )
                inserted += 1
            elif row.values() != values or row.source != source:
                row.close, row.adj_close = values.close, values.adj_close
                row.split_factor, row.div_cash = values.split_factor, values.div_cash
                row.source, row.fetched_at = source, stamp
                row.save(update_fields=[*VALUE_FIELDS, "source", "fetched_at"])
                updated += 1
            else:
                unchanged += 1
        cls.objects.bulk_create(new_rows)
        rescaled = 0
        if ratio is not None:
            others = list(
                cls.objects.filter(symbol=symbol, adj_close__isnull=False).exclude(date__in=wanted)
            )
            for row in others:
                if row.adj_close is not None:
                    row.adj_close = to_close(row.adj_close * ratio)
            cls.objects.bulk_update(others, ["adj_close"], batch_size=500)
            rescaled = len(others)
        return UpsertCount(inserted, updated, unchanged, rescaled)

    @classmethod
    def latest_for(cls, symbols: Iterable[str]) -> dict[str, Quote]:
        """The newest stored close per symbol, as a `Quote`. A symbol with no rows is absent."""
        wanted = {symbol.strip().upper() for symbol in symbols}
        if not wanted:
            return {}
        # One query for the newest date per symbol, one for those rows. `values().annotate()`
        # groups by the listed field, like SQL's GROUP BY.
        newest = list(
            cls.objects.filter(symbol__in=wanted).values("symbol").annotate(latest=Max("date"))
        )
        if not newest:
            return {}
        picks = Q()
        for row in newest:
            picks |= Q(symbol=row["symbol"], date=row["latest"])
        return {row.symbol: row.quote() for row in cls.objects.filter(picks)}


def footing_ratio(
    existing: dict[datetime.date, DailyClose], wanted: dict[datetime.date, Values]
) -> Decimal | None:
    """New adjusted close over stored adjusted close, on the oldest day of the answer where both
    exist; None when there is no such day or the two agree. A day stored before a split or a
    dividend lies before it, so its ratio is the event's factor; a day stored after it already
    has the new footing, and its ratio is one."""
    for day in sorted(wanted):
        row = existing.get(day)
        adjusted = wanted[day].adj_close
        if row is None or row.adj_close is None or adjusted is None:
            continue
        return None if adjusted == row.adj_close else adjusted / row.adj_close
    return None


class Backfill(models.Model):
    """A symbol whose history the pull has already asked for, and how far back (2026-10-29).

    The first pull of a symbol asks for a year of closes in its one request instead of the
    nightly week, then writes a row here. A symbol without a row, or with one that does not
    reach back far enough, gets the year on its next pull: one held or watched before this
    table existed included. A refused or skipped request writes no row, so the next night tries
    again. Deleting a row in the admin asks for the year again.
    """

    symbol: models.CharField[str, str] = models.CharField(max_length=20, unique=True)
    since: models.DateField[datetime.date, datetime.date] = models.DateField(
        help_text="The first day the backfill request asked for."
    )
    done_at: models.DateTimeField[datetime.datetime, datetime.datetime] = models.DateTimeField(
        help_text="When the source answered it."
    )

    class Meta:
        ordering = ["symbol"]
        verbose_name = "price backfill"
        verbose_name_plural = "price backfills"

    def __str__(self) -> str:
        return f"{self.symbol} since {self.since:%Y-%m-%d}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.symbol = self.symbol.strip().upper()
        super().save(*args, **kwargs)


class ManualRun(models.Model):
    """When an owner's button last asked the price source for closes (2026-10-29), so a second
    press inside the guard's ten minutes is refused instead of spending Tiingo's hourly
    requests again.

    One row per kind and key: **Fetch prices now** keys on the owner's user id, **Get history**
    on the symbol. The row is the guard's memory because the site runs as Vercel functions that
    share no memory between invocations; the database is the one thing every invocation sees.
    The time is written when a run starts, not when it ends, so two presses at the same moment
    cannot both run. Deleting a row in the admin lifts the guard for that key.
    """

    class Kind(models.TextChoices):
        FETCH_NOW = "fetch-now", "Fetch prices now"
        HISTORY = "history", "Get history"

    kind: models.CharField[str, str] = models.CharField(max_length=20, choices=Kind.choices)
    key: models.CharField[str, str] = models.CharField(
        max_length=40,
        help_text="The owner's id (Fetch prices now) or the symbol (Get history).",
    )
    ran_at: models.DateTimeField[datetime.datetime, datetime.datetime] = models.DateTimeField(
        help_text="When the last run started."
    )

    class Meta:
        ordering = ["-ran_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["kind", "key"], name="manual_run_once_per_kind_and_key"
            ),
        ]
        verbose_name = "manual price run"
        verbose_name_plural = "manual price runs"

    def __str__(self) -> str:
        return f"{self.Kind(self.kind).label} {self.key} at {self.ran_at:%Y-%m-%d %H:%M}"
