"""What a statement's lines are worth at the latest stored close, and when a close is too old.

Pure functions over plain values, like `holdings.py`: no database and no vendor. The Django view
(chapter 08) hands in the lines as `Position`s and one `Quote` per symbol, and prints what comes
back. A symbol with no quote is not valued and is listed, never shown as zero.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from invest_witus.holdings import Position
from invest_witus.money import to_money

# A close older than this many calendar days is marked stale. Five covers a weekend, a market
# holiday and one missed nightly run; anything older deserves a look at the cron's log.
STALE_AFTER_DAYS = 5
ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class Quote:
    """One close for one symbol: the number, the day it is for, and where it came from."""

    close: Decimal
    as_of: date
    source: str


@dataclass(frozen=True, slots=True)
class ValuedLine:
    """One statement line with the quote used, or `None` and no value when there is no close."""

    symbol: str
    shares: Decimal
    quote: Quote | None
    value: Decimal | None
    stale: bool


@dataclass(frozen=True, slots=True)
class Valuation:
    """Every line, the total of the priced ones, and the symbols that have no close yet."""

    lines: list[ValuedLine]
    total: Decimal
    unpriced: list[str]


def is_stale(quote: Quote, today: date) -> bool:
    """A calendar test: more than `STALE_AFTER_DAYS` days between the close and today. Shared by
    the valued statement line and, from chapter 09, the watch list."""
    return (today - quote.as_of).days > STALE_AFTER_DAYS


def value_line(position: Position, quote: Quote | None, today: date) -> ValuedLine:
    """Shares times close, rounded to cents half up (chapter 01's `to_money`). Both factors are
    Decimals; a float in either place fails here with a TypeError instead of a wrong number."""
    if quote is None:
        return ValuedLine(position.symbol, position.shares, None, None, False)
    value = to_money(position.shares * quote.close)
    return ValuedLine(position.symbol, position.shares, quote, value, is_stale(quote, today))


def value_positions(
    positions: Iterable[Position], quotes: Mapping[str, Quote], today: date
) -> Valuation:
    """Value each position with its symbol's quote. The total adds the priced lines only."""
    lines = [value_line(position, quotes.get(position.symbol), today) for position in positions]
    total = to_money(sum((line.value for line in lines if line.value is not None), ZERO))
    unpriced = [line.symbol for line in lines if line.quote is None]
    return Valuation(lines, total, unpriced)
