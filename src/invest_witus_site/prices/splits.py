"""Splits between two statements (2026-10-29, decision 124).

A statement records shares as the broker printed them, so a 4-for-1 split between two statements
shows as four times the shares, which reads like a big purchase. The stored `split_factor` (from
Tiingo's `splitFactor`) says when a split happened and its size; this module turns that into a
note beside the symbol on the statements comparison. The statements themselves are never changed.
"""

from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from invest_witus.holdings import Change
from invest_witus_site.holdings.templatetags.holdings_extras import quantity
from invest_witus_site.prices.charts import number_text
from invest_witus_site.prices.models import DailyClose


def ratio_text(factor: Decimal) -> str:
    """4 is `4-for-1`; 0.1 is `1-for-10 reverse`."""
    if factor >= 1:
        return f"{number_text(factor)}-for-1"
    return f"1-for-{number_text(1 / factor)} reverse"


def splits_between(symbol: str, after: date, through: date) -> list[DailyClose]:
    """The stored split days for `symbol` after the earlier statement's date, up to and including
    the later one's: a split on the earlier date is already in that statement's shares."""
    rows = DailyClose.objects.filter(
        symbol=symbol, date__gt=after, date__lte=through, split_factor__isnull=False
    ).exclude(split_factor=1)
    return list(rows.order_by("date"))


def split_note(change: Change, after: date, through: date) -> str:
    """The note for one symbol, or "" when no split is stored between the dates or the symbol
    was not held on the earlier statement (a split cannot explain shares bought from nothing)."""
    if change.shares_before == 0:
        return ""
    splits = splits_between(change.symbol, after, through)
    if not splits:
        return ""
    factor = Decimal(1)
    for row in splits:
        if row.split_factor is not None:
            factor *= row.split_factor
    expected = change.shares_before * factor
    if len(splits) == 1:
        (row,) = splits
        text = (
            f"A {ratio_text(factor)} split on {row.date:%Y-%m-%d} explains a share change of "
            f"this size: {quantity(change.shares_before)} shares before it are "
            f"{quantity(expected)} after it."
        )
    else:
        listed = ", ".join(
            f"{ratio_text(row.split_factor)} on {row.date:%Y-%m-%d}"
            for row in splits
            if row.split_factor is not None
        )
        text = (
            f"Splits between the two statements ({listed}) multiply the shares by "
            f"{number_text(factor)}: {quantity(change.shares_before)} shares before are "
            f"{quantity(expected)} after."
        )
    if expected == change.shares_after:
        return f"{text} That is the whole change."
    rest = change.shares_after - expected
    return (
        f"{text} The statement shows {quantity(change.shares_after)}; the other "
        f"{quantity(rest)} came from buying, selling or reinvesting."
    )


def split_notes(changes: Iterable[Change], after: date, through: date) -> list[tuple[Change, str]]:
    """Each change with its split note ("" for none), in the same order."""
    return [(change, split_note(change, after, through)) for change in changes]
