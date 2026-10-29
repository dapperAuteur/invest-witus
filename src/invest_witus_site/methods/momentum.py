"""12-1 momentum on the web: the stored closes as series, each month's ranking, the ranked bar
chart, the month's rebalance, and the watch list's badges (chapter 14).

The math is the library's (`invest_witus.methods.momentum_12_1`); this module only reads rows and
arranges what the pages print. Every value is the stored **adjusted close** where the row has one,
because a split or a dividend inside the window would otherwise read as a fall; a row without one
(a CSV file on a laptop) uses its close, and the page counts how many did. Owner pages only: the
vendor's free plan is for the owner's own use, and no public page shows a price or a return.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from invest_witus.adherence.journal import Action
from invest_witus.methods.momentum_12_1 import (
    Month,
    Place,
    Ranking,
    Score,
    Unranked,
    Window,
    month_text,
    rank,
    score,
)
from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.models import JournalEntry, MethodPlan
from invest_witus_site.prices.models import DailyClose
from invest_witus_site.watchlist.models import WatchItem

HUNDRED = Decimal(100)
# The wash-sale rule's span: a loss sale and a purchase of the same security within 30 days
# before or after it (Internal Revenue Service, Publication 550; PRD 7.1, research 03).
WASH_SALE_DAYS = 30
# The note a candidate gets when the plan adds it to the watch list.
WATCH_NOTE = "A 12-1 momentum candidate"


def percent_text(change: Decimal) -> str:
    """0.1234 as `+12.3%`, -0.05 as `-5.0%`: one place, the sign always written, so the number
    says up or down without the color."""
    value = (change * HUNDRED).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    sign = "+" if value > 0 else ("-" if value < 0 else "")
    return f"{sign}{abs(value)}%"


@dataclass(frozen=True, slots=True)
class PriceSeries:
    """Each symbol's (day, value) pairs, oldest first, and how many rows had no adjusted close."""

    values: dict[str, list[tuple[date, Decimal]]]
    unadjusted: int

    def of(self, symbols: Iterable[str]) -> dict[str, list[tuple[date, Decimal]]]:
        return {symbol: self.values.get(symbol, []) for symbol in symbols}


def price_series(symbols: Iterable[str], since: date | None = None) -> PriceSeries:
    """The stored closes of `symbols` from `since` on: the adjusted close, else the close."""
    wanted = sorted(set(symbols))
    rows = DailyClose.objects.filter(symbol__in=wanted).order_by("symbol", "date")
    if since is not None:
        rows = rows.filter(date__gte=since)
    values: dict[str, list[tuple[date, Decimal]]] = {symbol: [] for symbol in wanted}
    unadjusted = 0
    for symbol, day, close, adjusted in rows.values_list("symbol", "date", "close", "adj_close"):
        if adjusted is None:
            unadjusted += 1
        values[symbol].append((day, close if adjusted is None else adjusted))
    return PriceSeries(values, unadjusted)


def series_since(first_month: Month) -> date:
    """The first day a review from `first_month` reads: the start of its window's first month."""
    start = Window.for_month(*first_month).start
    return date(start[0], start[1], 1)


def ranking_for(plan: MethodPlan, month: Month, series: PriceSeries) -> Ranking:
    """The plan version's candidates ranked for a rebalance in `month`."""
    return rank(series.of(plan.symbol_list()), Window.for_month(*month), plan.top_n or 1)


def plan_ranking(plan: MethodPlan, month: Month) -> Ranking:
    """`ranking_for` with its own query, for a page that needs one month only."""
    series = price_series(plan.symbol_list(), series_since(month))
    return ranking_for(plan, month, series)


# --- The ranked bar chart ------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Bar:
    """One candidate's bar: where it starts and how wide it is, in percent of the track, and the
    words beside it. A bar grows right from the zero line for a rise and left for a fall."""

    place: Place
    x: Decimal
    width: Decimal
    text: str

    @property
    def symbol(self) -> str:
        return self.place.symbol

    @property
    def up(self) -> bool:
        return self.place.score.up

    @property
    def direction(self) -> str:
        change = self.place.score.change
        return "up" if change > 0 else ("down" if change < 0 else "flat")


def place_pct(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True, slots=True)
class BarChart:
    """The bars in rank order and the zero line's place on the track."""

    bars: list[Bar]
    zero_x: Decimal


def bar_chart(ranking: Ranking) -> BarChart | None:
    """A shared scale for every bar: from the lowest return (or 0) to the highest (or 0), so the
    zero line is where the bars meet and the lengths compare. None when nothing is ranked."""
    if not ranking.places:
        return None
    changes = [place.score.change for place in ranking.places]
    low, high = min(min(changes), Decimal(0)), max(max(changes), Decimal(0))
    span = high - low or Decimal(1)
    zero = (0 - low) * HUNDRED / span
    bars: list[Bar] = []
    for place in ranking.places:
        end = (place.score.change - low) * HUNDRED / span
        bars.append(
            Bar(
                place=place,
                x=place_pct(min(zero, end)),
                width=place_pct(max(abs(end - zero), Decimal("0.5"))),
                text=percent_text(place.score.change),
            )
        )
    return BarChart(bars, place_pct(zero))


# --- The month's rebalance ------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Rebalance:
    """What the rules ask for in one month: buy the top N in equal parts, sell the holdings that
    left it, and the wash-sale warnings for buying back something sold within 30 days."""

    month: Month
    buys: list[str]
    sells: list[str]
    warnings: list[str]


def held_symbols(account: Account, since: date, before: date) -> set[str]:
    """Symbols whose latest trade in the journal between `since` and `before` was a buy."""
    last: dict[str, str] = {}
    trades = JournalEntry.objects.filter(
        account=account, kind="trade", date__gte=since, date__lt=before
    ).order_by("date", "pk")
    for symbol, action in trades.values_list("symbol", "action"):
        last[symbol] = action
    return {symbol for symbol, action in last.items() if action == Action.BUY.value}


def wash_sale_warnings(account: Account, symbols: list[str], day: date) -> list[str]:
    """One sentence per symbol to buy that the journal shows sold in the 30 days before `day`."""
    since = day - timedelta(days=WASH_SALE_DAYS)
    sales = JournalEntry.objects.filter(
        account=account,
        kind="trade",
        action=Action.SELL.value,
        symbol__in=symbols,
        date__gte=since,
        date__lte=day,
    ).order_by("-date")
    warnings: list[str] = []
    seen: set[str] = set()
    for sale in sales:
        if sale.symbol in seen:
            continue
        seen.add(sale.symbol)
        days = (day - sale.date).days
        warnings.append(
            f"You sold {sale.symbol} on {sale.date:%Y-%m-%d}, {days} day{'' if days == 1 else 's'} "
            f"before {day:%Y-%m-%d}. If that sale was at a loss, buying {sale.symbol} again within "
            f"{WASH_SALE_DAYS} days of it is a wash sale, and the loss cannot be deducted then "
            "(IRS Publication 550). A paper account has no tax effect; a live one would."
        )
    return warnings


def rebalance(plan: MethodPlan, ranking: Ranking, day: date) -> Rebalance:
    month = ranking.window.rebalance
    first = date(month[0], month[1], 1)
    held = held_symbols(plan.account, plan.chain_start(), first)
    top = ranking.top
    sells = sorted(held - set(top)) if ranking.ranked else []
    return Rebalance(month, top, sells, wash_sale_warnings(plan.account, top, day))


# --- What the method page shows -------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MomentumView:
    """The momentum section of the method page: this month's ranking, its bars, the rebalance,
    and how many closes had no adjusted value."""

    ranking: Ranking
    chart: BarChart | None
    rebalance: Rebalance
    unadjusted: int
    top_n: int
    candidates: list[str] = field(default_factory=list[str])

    @property
    def month(self) -> str:
        return month_text(self.ranking.window.rebalance)

    @property
    def window(self) -> Window:
        return self.ranking.window

    @property
    def unranked_symbols(self) -> list[str]:
        return [item.symbol for item in self.ranking.unranked]


def momentum_view(plan: MethodPlan, today: date, series: PriceSeries) -> MomentumView:
    ranking = ranking_for(plan, (today.year, today.month), series)
    return MomentumView(
        ranking=ranking,
        chart=bar_chart(ranking),
        rebalance=rebalance(plan, ranking, today),
        unadjusted=series.unadjusted,
        top_n=plan.top_n or 1,
        candidates=plan.symbol_list(),
    )


# --- The watch list and the plan's candidates -----------------------------------------------------


def scores_for(symbols: list[str], today: date) -> dict[str, Score | Unranked]:
    """Each symbol's 12-1 return for this month's rebalance, or why there is none: the watch
    list's badges."""
    window = Window.for_month(today.year, today.month)
    series = price_series(symbols, series_since(window.rebalance))
    return {symbol: score(symbol, series.values.get(symbol, []), window) for symbol in symbols}


def ensure_watched(account: Account, symbols: list[str]) -> list[str]:
    """Put each candidate on the account's watch list, so the nightly pull stores its closes,
    and return the symbols that were added (the ones already watched are left as they were)."""
    return WatchItem.add_many(account, symbols, note=WATCH_NOTE).added
