"""Comparing methods (chapter 15): an account's value day by day, rebuilt from its trades and the
stored prices, and the numbers that say how a method did. No Django, no files: plain values in,
plain values out, every amount a `Decimal`.

**The value.** Each buy adds *units* of its symbol and each sell takes them away. With the shares
known, a unit count is the shares times the day's close over the day's basis price; without them,
the money over the basis price, as if the order filled at that day's close. The basis is the
adjusted close when the caller has one for every day (dividends and splits counted, as if each
dividend bought more of the fund), else the close. A day's value is every unit held times its
symbol's latest basis price on or before that day. The days are the days with a stored price.

**Money put in** is what the buys cost less what the sells brought back. Cash the account keeps
beside its holdings is not counted: the app has no cash ledger, so the value here is the value of
what the trades bought.

**The line** leaves the money put in out, so a deposit never looks like growth: each day's level
is the day before's times `(value - money put in that day) / value the day before`, starting at
100. This is the *time-weighted* return; the **money-weighted** return is the one yearly rate
that makes every deposit, grown to the last day, equal the value then (XIRR). The time-weighted
return judges the method; the money-weighted one judges the method and the timing of the money
together.

**The worst drop** is the largest fall of the line from a high to a later low, as a fraction of
the high.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

ZERO = Decimal(0)
ONE = Decimal(1)
HUNDRED = Decimal(100)
DAYS_A_YEAR = 365
# XIRR is found by halving an interval: from a loss of almost everything to a gain of this many
# times a year. A rate the interval cannot hold is "no rate", never a guess.
LOWEST_RATE = Decimal("-0.999999")
HIGHEST_RATE = Decimal(1000)
RATE_TOLERANCE = Decimal("1e-10")
MAX_HALVINGS = 200


@dataclass(frozen=True, slots=True)
class Trade:
    """One buy or sell: the day the money changed hands, the symbol, the money (always positive),
    and the shares when the fill or the confirmation said."""

    day: date
    symbol: str
    amount: Decimal
    shares: Decimal | None = None
    sell: bool = False

    @property
    def flow(self) -> Decimal:
        """Money put in: positive for a buy, negative for a sell."""
        return -self.amount if self.sell else self.amount


@dataclass(frozen=True, slots=True)
class DayPrice:
    """One stored day of one symbol: the close, and the price the value uses (the adjusted close,
    or the close again when the caller has no adjusted close for every day)."""

    close: Decimal
    basis: Decimal


Prices = Mapping[str, Sequence[tuple[date, DayPrice]]]


def units(trade: Trade, price: DayPrice) -> Decimal:
    """How many units of the basis price the trade moved. With shares: the shares times the
    close over the basis, so a split or a dividend after the trade is counted through the basis
    and never twice. Without shares: the money over the basis price."""
    if trade.shares is not None:
        return trade.shares * price.close / price.basis
    return trade.amount / price.basis


def price_on_or_before(rows: Sequence[tuple[date, DayPrice]], day: date) -> DayPrice | None:
    """The newest stored price on or before `day` (the rows are oldest first), or None."""
    found: DayPrice | None = None
    for stored, price in rows:
        if stored > day:
            break
        found = price
    return found


@dataclass(frozen=True, slots=True)
class Day:
    """One day of an account: its value at the day's prices, the money put in that day, and the
    money put in so far."""

    day: date
    value: Decimal
    flow: Decimal
    put_in: Decimal


@dataclass(frozen=True, slots=True)
class Series:
    """An account day by day, and what could not be counted: trades dated after the newest stored
    price (`pending`), and `problems`, reasons the value cannot be trusted at all."""

    days: list[Day] = field(default_factory=list[Day])
    pending: list[Trade] = field(default_factory=list[Trade])
    problems: list[str] = field(default_factory=list[str])


def value_series(trades: Sequence[Trade], prices: Prices, until: date) -> Series:
    """The account's value on every stored price day from its first trade through `until`.

    A trade counts from the first stored day on or after it (a buy confirmed on a Saturday counts
    from Monday). Its units are worked out at its symbol's price on its own day, or the newest
    one before. A trade after the newest stored day is `pending`, left out of both the value and
    the money put in, so the two always describe the same trades. A symbol with no stored price
    on or before its trade's day, or a sell of more units than were bought, is a problem: the
    series is empty and the reason is kept."""
    ordered = sorted(trades, key=lambda trade: trade.day)
    if not ordered:
        return Series()
    first = ordered[0].day
    calendar = sorted(
        {day for symbol in {t.symbol for t in ordered} for day, _ in prices.get(symbol, ())}
    )
    calendar = [day for day in calendar if first <= day <= until]
    pending = [trade for trade in ordered if not calendar or trade.day > calendar[-1]]
    counted = [trade for trade in ordered if trade not in pending]
    problems: list[str] = []
    moves: dict[date, list[tuple[str, Decimal, Decimal]]] = {}
    for trade in counted:
        applies = next(day for day in calendar if day >= trade.day)
        rows = prices.get(trade.symbol, ())
        price = price_on_or_before(rows, trade.day) or price_on_or_before(rows, applies)
        if price is None:
            problems.append(
                f"no stored price for {trade.symbol} on or before {applies:%Y-%m-%d}, "
                f"the day its {'sell' if trade.sell else 'buy'} of {trade.day:%Y-%m-%d} counts"
            )
            continue
        moved = units(trade, price)
        moves.setdefault(applies, []).append(
            (trade.symbol, -moved if trade.sell else moved, trade.flow)
        )
    if problems:
        return Series(pending=pending, problems=problems)
    held: dict[str, Decimal] = {}
    days: list[Day] = []
    put_in = ZERO
    for day in calendar:
        flow = ZERO
        for symbol, change, money in moves.get(day, []):
            held[symbol] = held.get(symbol, ZERO) + change
            flow += money
        short = [symbol for symbol, count in held.items() if count < 0]
        if short:
            problems.append(
                f"the journal sells more {', '.join(sorted(short))} than it bought "
                f"(by {day:%Y-%m-%d})"
            )
            return Series(pending=pending, problems=problems)
        put_in += flow
        value = ZERO
        for symbol, count in held.items():
            price = price_on_or_before(prices[symbol], day)
            if price is not None and count:
                value += count * price.basis
        days.append(Day(day, value, flow, put_in))
    return Series(days=days, pending=pending)


# --- A stretch of days ----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Period:
    """The days of a series inside a range, and the value carried into it: zero when the range
    starts before the first trade, else the first day's value less that day's money put in."""

    days: list[Day]
    opening: Decimal

    @property
    def first(self) -> Day:
        return self.days[0]

    @property
    def last(self) -> Day:
        return self.days[-1]

    @property
    def put_in(self) -> Decimal:
        """The money put in during the range, the value carried in counted as put in on day one."""
        return self.opening + sum((day.flow for day in self.days), ZERO)

    @property
    def gain(self) -> Decimal:
        return self.last.value - self.put_in

    @property
    def length(self) -> int:
        """Calendar days from the first day to the last."""
        return (self.last.day - self.first.day).days


def period(days: Sequence[Day], start: date, end: date) -> Period | None:
    """The days from `start` through `end`, or None when none falls inside."""
    inside = [day for day in days if start <= day.day <= end]
    if not inside:
        return None
    before = [day for day in days if day.day < start]
    carried = before[-1].value if before else ZERO
    opening = inside[0].value - inside[0].flow if carried > 0 else ZERO
    return Period(inside, opening)


def time_weighted_line(days: Sequence[Day]) -> list[tuple[date, Decimal]]:
    """The account's line with the money put in left out, 100 on its first day with a value. A
    day after a day with nothing held keeps the level: no money was at work."""
    points: list[tuple[date, Decimal]] = []
    level = HUNDRED
    previous: Day | None = None
    for day in days:
        if previous is not None and previous.value > 0:
            level = level * (day.value - day.flow) / previous.value
        if points or day.value > 0:
            points.append((day.day, level))
        previous = day
    return points


def rebase(points: Sequence[tuple[date, Decimal]]) -> list[tuple[date, Decimal]]:
    """Each value times 100 over the first: a price line on the same scale as an account's."""
    if not points or points[0][1] == 0:
        return []
    base = points[0][1]
    return [(day, value * HUNDRED / base) for day, value in points]


def line_return(points: Sequence[tuple[date, Decimal]]) -> Decimal | None:
    """The change from a line's first point to its last, as a fraction: 0.05 is five percent."""
    if len(points) < 2 or points[0][1] == 0:
        return None
    return points[-1][1] / points[0][1] - ONE


@dataclass(frozen=True, slots=True)
class Drawdown:
    """The worst fall of a line: from `peak` on `peak_day` to `trough` on `trough_day`."""

    peak_day: date
    peak: Decimal
    trough_day: date
    trough: Decimal

    @property
    def fraction(self) -> Decimal:
        """Zero or negative: -0.2 is a fall of twenty percent from the high."""
        return self.trough / self.peak - ONE


def max_drawdown(points: Sequence[tuple[date, Decimal]]) -> Drawdown | None:
    """The largest fall from a high to a later low, or None for a line of under two points. A line
    that never fell below its high has a drawdown of zero, on its first day."""
    if len(points) < 2:
        return None
    peak_day, peak = points[0]
    worst = Drawdown(peak_day, peak, peak_day, peak)
    for day, value in points[1:]:
        if value > peak:
            peak_day, peak = day, value
        elif peak > 0 and value / peak - ONE < worst.fraction:
            worst = Drawdown(peak_day, peak, day, value)
    return worst


# --- The money-weighted return --------------------------------------------------------------------


def cash_flows(stretch: Period) -> list[tuple[date, Decimal]]:
    """The investor's side of the account: every deposit negative (money leaving the pocket), the
    value carried in as a deposit on the first day, and the last day's value positive, as if it
    were taken out then."""
    flows: list[tuple[date, Decimal]] = []
    if stretch.opening > 0:
        flows.append((stretch.first.day, -stretch.opening))
    flows += [(day.day, -day.flow) for day in stretch.days if day.flow]
    flows.append((stretch.last.day, stretch.last.value))
    return flows


def present_value(rate: Decimal, flows: Sequence[tuple[date, Decimal]]) -> Decimal:
    """Every flow moved back to the first flow's day at `rate` a year."""
    first = flows[0][0]
    log = (ONE + rate).ln()
    total = ZERO
    for day, amount in flows:
        years = Decimal((day - first).days) / DAYS_A_YEAR
        total += amount * (-years * log).exp()
    return total


def xirr(flows: Sequence[tuple[date, Decimal]]) -> Decimal | None:
    """The yearly rate at which the flows' present value is zero, found by halving an interval,
    or None: no money in or no money out, every flow on one day, or no single rate in the
    interval that fits (possible when deposits and withdrawals alternate)."""
    if not any(amount < 0 for _, amount in flows) or not any(amount > 0 for _, amount in flows):
        return None
    ordered = sorted(flows, key=lambda flow: flow[0])
    if ordered[0][0] == ordered[-1][0]:
        return None
    low, high = LOWEST_RATE, HIGHEST_RATE
    try:
        at_low, at_high = present_value(low, ordered), present_value(high, ordered)
    except InvalidOperation:
        return None
    if at_low == 0:
        return low
    if (at_low > 0) == (at_high > 0):
        return None
    for _ in range(MAX_HALVINGS):
        middle = (low + high) / 2
        at_middle = present_value(middle, ordered)
        if at_middle == 0 or high - low < RATE_TOLERANCE:
            return middle
        if (at_middle > 0) == (at_low > 0):
            low, at_low = middle, at_middle
        else:
            high = middle
    return (low + high) / 2


def over_days(yearly: Decimal, days: int) -> Decimal:
    """A yearly rate as the change over `days` calendar days: 10% a year over 73 days is about
    1.92%."""
    return ((ONE + yearly).ln() * days / DAYS_A_YEAR).exp() - ONE


def yearly(total: Decimal, days: int) -> Decimal:
    """A change over `days` calendar days as a yearly rate. Only for a year or more: a short
    stretch stretched to a year multiplies its noise."""
    if days < DAYS_A_YEAR:
        raise ValueError(f"{days} days is under a year; show the change over the days instead")
    return ((ONE + total).ln() * DAYS_A_YEAR / days).exp() - ONE


def months_running(start: date, end: date) -> int:
    """Calendar months from `start`'s month to `end`'s, both counted: a plan started on
    2026-11-03 has run 1 month on 2026-11-30 and 2 on 2026-12-01. Zero before it starts."""
    if end < start:
        return 0
    return (end.year - start.year) * 12 + end.month - start.month + 1
