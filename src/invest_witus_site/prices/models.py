"""One close per symbol per day, in the app's own table, so a page never asks a vendor.

The nightly pull (`pull.py`) writes here through `upsert`, which is idempotent: a day already
stored with the same close is left alone, so a cron that runs twice, or a pull repeated by hand,
changes nothing. The owner's pages read `latest_for`, the newest stored close per symbol, and
show its date beside the value.
"""

import datetime
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db import models
from django.db.models import Max, Q
from django.utils import timezone

from invest_witus.prices.csv_file import PricePoint
from invest_witus.valuation import Quote

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

    def __add__(self, other: UpsertCount) -> UpsertCount:
        return UpsertCount(
            self.inserted + other.inserted,
            self.updated + other.updated,
            self.unchanged + other.unchanged,
        )

    def __str__(self) -> str:
        return f"inserted {self.inserted}, updated {self.updated}, unchanged {self.unchanged}"


class DailyClose(models.Model):
    """The closing price of one symbol on one day, and where and when the app got it."""

    symbol: models.CharField[str, str] = models.CharField(max_length=20)
    date: models.DateField[datetime.date, datetime.date] = models.DateField(
        help_text="The trading day the close is for."
    )
    close: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=18, decimal_places=PRICE_PLACES
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
        self.symbol = self.symbol.strip().upper()
        self.close = to_close(self.close)
        super().save(*args, **kwargs)

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
        """Write each day once. A day already stored with the same close and source is left
        alone, `fetched_at` included, so a re-run changes nothing. A different close (a vendor's
        correction, or a second source) replaces the row and counts as an update."""
        symbol = symbol.strip().upper()
        wanted = {point.day: to_close(point.close) for point in points}
        existing = {row.date: row for row in cls.objects.filter(symbol=symbol, date__in=wanted)}
        stamp = now or timezone.now()
        inserted = updated = unchanged = 0
        new_rows: list[DailyClose] = []
        for day, close in sorted(wanted.items()):
            row = existing.get(day)
            if row is None:
                new_rows.append(
                    cls(symbol=symbol, date=day, close=close, source=source, fetched_at=stamp)
                )
                inserted += 1
            elif row.close != close or row.source != source:
                row.close, row.source, row.fetched_at = close, source, stamp
                row.save(update_fields=["close", "source", "fetched_at"])
                updated += 1
            else:
                unchanged += 1
        cls.objects.bulk_create(new_rows)
        return UpsertCount(inserted, updated, unchanged)

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
