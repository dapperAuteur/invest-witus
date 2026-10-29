"""A statement valued at the latest stored closes: the join between holdings and prices."""

from datetime import date
from decimal import Decimal

from invest_witus.valuation import Quote, Valuation, value_positions
from invest_witus_site.holdings.models import Holding, Snapshot
from invest_witus_site.prices.models import DailyClose

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
