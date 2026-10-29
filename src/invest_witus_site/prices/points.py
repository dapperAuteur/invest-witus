"""A day's close with the vendor's adjusted close, split factor and dividend beside it (2026-10-29).

Chapter 02's `PricePoint` is a date and a close, and chapter 02's file stays as it was published.
A source that also knows them (Tiingo's `adjClose`, `splitFactor` and `divCash`) answers with
this subclass; a source that does not (the CSV folder) keeps answering with plain `PricePoint`s,
and `extras` reads both.
"""

from dataclasses import dataclass
from decimal import Decimal

from invest_witus.prices.csv_file import PricePoint


@dataclass(frozen=True, slots=True)
class AdjustedPoint(PricePoint):
    """`adj_close` is the close adjusted for later splits and dividends; `split_factor` the
    day's split factor (1 on an ordinary day, 4 on the day of a 4-for-1 split); `div_cash` the
    cash dividend whose ex-date is this day (0 on an ordinary day). Each is None when the source
    sent nothing for it."""

    adj_close: Decimal | None = None
    split_factor: Decimal | None = None
    div_cash: Decimal | None = None


def extras(point: PricePoint) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    """The point's adjusted close, split factor and dividend; all None for a plain point."""
    if isinstance(point, AdjustedPoint):
        return point.adj_close, point.split_factor, point.div_cash
    return None, None, None
