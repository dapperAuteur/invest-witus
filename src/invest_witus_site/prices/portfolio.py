"""What the account page shows, priced: a statement valued at the latest stored closes, and
(chapter 09) the watch list with the latest close beside each symbol. The joins between the
account's symbols and the prices table live here, so the holdings views stay thin."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from invest_witus.valuation import Quote, Valuation, is_stale, value_positions
from invest_witus_site.holdings.models import Account, Holding, Snapshot
from invest_witus_site.prices.models import DailyClose
from invest_witus_site.watchlist.models import WatchItem

# A cash line is worth its amount. It is never pulled: no vendor has a close for "CASH".
CASH_CLOSE = Decimal("1")


def value_snapshot(snapshot: Snapshot, today: date) -> Valuation:
    """Each line of the statement at its symbol's newest close; cash at face, dated by the
    statement; a symbol with no close yet is listed, not valued."""
    positions = snapshot.positions()
    kinds: dict[str, str] = dict(
        Holding.objects.filter(account=snapshot.account).values_list("symbol", "kind")
    )
    cash = {position.symbol for position in positions if kinds.get(position.symbol) == "cash"}
    quotes = DailyClose.latest_for(
        position.symbol for position in positions if position.symbol not in cash
    )
    for symbol in cash:
        quotes[symbol] = Quote(close=CASH_CLOSE, as_of=snapshot.as_of, source="statement")
    return value_positions(positions, quotes, today)


@dataclass(frozen=True, slots=True)
class WatchedSymbol:
    """One watch list row with its newest close, or `None` while the pull has not stored one."""

    item: WatchItem
    quote: Quote | None
    stale: bool


@dataclass(frozen=True, slots=True)
class WatchList:
    """The account's rows, by symbol, and the symbols that have no close yet."""

    rows: list[WatchedSymbol]
    unpriced: list[str]


def watch_list(account: Account, today: date) -> WatchList:
    """Each watched symbol with the newest close the app has stored for it. A watched symbol is
    never valued: there are no shares to multiply, so the close and its date are the whole row."""
    items = list(WatchItem.objects.filter(account=account))
    quotes = DailyClose.latest_for(item.symbol for item in items)
    rows: list[WatchedSymbol] = []
    for item in items:
        quote = quotes.get(item.symbol)
        rows.append(WatchedSymbol(item, quote, quote is not None and is_stale(quote, today)))
    return WatchList(rows, [row.item.symbol for row in rows if row.quote is None])
