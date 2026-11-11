"""Compare methods on the web (chapter 15): the app's own records turned into the library's plain
values, and the library's numbers turned into what the page prints.

The math is `invest_witus.compare`. This module reads, for each account picked:

- **the trades** from the journal (chapter 10's rows): a buy placed through Alpaca paper counts
  from the day its order filled (`PaperOrder.filled_at`, chapter 11) with the shares Alpaca
  reported; an order still open is left out until it fills; a trade logged by hand counts on its
  own date with its shares if the owner wrote them;
- **the prices** from the stored closes (chapter 08): the adjusted close for a symbol whose every
  stored day in the stretch has one, else the close, and the page says which;
- **the plan** (chapter 10, its versions from chapter 12): its method, its first start, and its
  closed month reviews, which say how often the plan was followed.

Nothing is fetched. The one live read is Alpaca's own equity for a linked account (`alpaca_checks`),
a cross-check with a short timeout that a page asks for and a test replaces.
"""

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.db.models import Exists, OuterRef
from django.utils import timezone

from invest_witus.compare import DAYS_A_YEAR as YEAR_DAYS
from invest_witus.compare import (
    HUNDRED,
    DayPrice,
    Drawdown,
    Period,
    Series,
    Trade,
    cash_flows,
    line_return,
    max_drawdown,
    months_running,
    period,
    same_money,
    time_weighted_line,
    value_series,
    xirr,
    yearly,
)
from invest_witus_site.holdings.models import Account
from invest_witus_site.holdings.templatetags.holdings_extras import money, percent, signed_money
from invest_witus_site.methods.engine import build_review
from invest_witus_site.methods.models import TRADE, JournalEntry, MethodPlan, MonthlyReview
from invest_witus_site.paper.alpaca import AlpacaError, client_for
from invest_witus_site.paper.models import PaperOrder
from invest_witus_site.paper.orders import alpaca_allowed
from invest_witus_site.prices import manual
from invest_witus_site.prices.models import DailyClose

# Two to four accounts on one chart, plus the yardstick: five lines, within the chart's six styles.
MIN_ACCOUNTS = 2
MAX_ACCOUNTS = 4
# S&P 500 index funds by their tickers, from the author's knowledge, not read from a vendor in
# this session: the first one found among the owner's own symbols is the default yardstick. The
# owner can pick any symbol of theirs instead, and the page prints the stored profile's name so
# the owner can check what the fund is (decision 168).
SP500_FUNDS = ("SPY", "VOO", "IVV", "SPLG", "FXAIX", "VFIAX", "SWPPX")
# A trade on a weekend or a holiday reads the newest close before it; two weeks covers any gap.
PRICE_LOOKBACK_DAYS = 14
# Alpaca's equity is a cross-check, not the page: a short wait, then "did not answer".
ALPACA_TIMEOUT_SECONDS = 5.0


# --- Which accounts -------------------------------------------------------------------------------


def plan_of(account: Account) -> MethodPlan | None:
    """The account's plan: the active one, else the newest version of the most recent ended one."""
    active = MethodPlan.active_for(account)
    if active is not None:
        return active
    newest = MethodPlan.objects.filter(account=account).order_by("-started_on", "-pk").first()
    return newest.latest_version() if newest is not None else None


def accounts_with_plans(user: AbstractBaseUser | AnonymousUser) -> list[Account]:
    """The person's accounts that run or ran a plan, by name: the page's default pick."""
    has_plan = Exists(MethodPlan.objects.filter(account=OuterRef("pk")))
    return list(Account.objects.filter(has_plan, owner_id=user.pk).order_by("name"))


@dataclass
class Picked:
    """The accounts asked for, sorted out: the ones compared (in the order asked, at most
    `MAX_ACCOUNTS`), how many ids were not the person's, and the ones over the limit."""

    accounts: list[Account] = field(default_factory=list[Account])
    not_yours: int = 0
    over_limit: list[Account] = field(default_factory=list[Account])
    defaulted: bool = False


def pick_accounts(asked: list[str], owned: list[Account], with_plans: list[Account]) -> Picked:
    """`?accounts=1&accounts=2` (or `1,2`): each of the person's own accounts once, in the order
    asked. Nothing asked: every account with a plan, the first four by name. An id that is not
    one of the person's accounts is counted and left out, never named."""
    by_pk = {account.pk: account for account in owned}
    picked = Picked()
    seen: set[int] = set()
    for value in asked:
        for token in value.split(","):
            try:
                pk = int(token.strip())
            except ValueError:
                picked.not_yours += 1 if token.strip() else 0
                continue
            if pk in seen:
                continue
            seen.add(pk)
            account = by_pk.get(pk)
            if account is None:
                picked.not_yours += 1
            elif len(picked.accounts) >= MAX_ACCOUNTS:
                picked.over_limit.append(account)
            else:
                picked.accounts.append(account)
    if not picked.accounts and not picked.not_yours and not picked.over_limit:
        picked.accounts = with_plans[:MAX_ACCOUNTS]
        picked.over_limit = with_plans[MAX_ACCOUNTS:]
        picked.defaulted = True
    return picked


# --- The records, as the library's values ---------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Trades:
    """An account's trades through `until`, and the orders still open at Alpaca, left out."""

    trades: list[Trade]
    open_orders: int


def trades_for(account: Account, until: date) -> Trades:
    """The journal's buys and sells, each on the day its money changed hands: a filled Alpaca
    order on its fill's day with Alpaca's shares (chapter 11's sync wrote both onto the entry and
    the order), anything else on the entry's date. An order Alpaca has not finished is left out:
    its entry carries the order's notional, not what was bought."""
    entries = list(
        JournalEntry.objects.filter(account=account, kind=TRADE, date__lte=until)
        .exclude(amount=None)
        .order_by("date", "pk")
    )
    orders = {
        order.journal_entry_id: order
        for order in PaperOrder.objects.filter(journal_entry__in=entries)
    }
    trades: list[Trade] = []
    open_orders = 0
    for entry in entries:
        if entry.amount is None:
            continue
        order = orders.get(entry.pk)
        if order is not None and not order.final:
            open_orders += 1
            continue
        day = entry.date
        if order is not None and order.filled_at is not None:
            day = timezone.localdate(order.filled_at)
        trades.append(
            Trade(day, entry.symbol, entry.amount, entry.shares, sell=entry.action == "sell")
        )
    return Trades(trades, open_orders)


@dataclass(frozen=True, slots=True)
class SymbolPrices:
    """One symbol's stored days, oldest first, and whether the value reads its adjusted close."""

    rows: list[tuple[date, DayPrice]]
    adjusted: bool


def prices_for(symbols: Sequence[str], since: date, until: date) -> dict[str, SymbolPrices]:
    """Each symbol's stored days from `since` through `until`, on the adjusted close when every
    one of those days has it, else on the close (decision 134's rule for a chart line)."""
    stored: dict[str, list[DailyClose]] = {symbol: [] for symbol in symbols}
    rows = DailyClose.objects.filter(symbol__in=list(symbols), date__gte=since, date__lte=until)
    for row in rows.order_by("symbol", "date"):
        stored[row.symbol].append(row)
    found: dict[str, SymbolPrices] = {}
    for symbol, days in stored.items():
        adjusted = bool(days) and all(row.adj_close is not None for row in days)
        found[symbol] = SymbolPrices(
            [
                (
                    row.date,
                    DayPrice(row.close, row.adj_close if adjusted and row.adj_close else row.close),
                )
                for row in days
            ],
            adjusted,
        )
    return found


# --- One account's numbers ------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Followed:
    """How often the plan was followed, from its closed month reviews (chapter 12)."""

    closed: int
    followed: int
    skipped: int

    @property
    def text(self) -> str:
        if not self.closed:
            return "no month closed yet"
        skipped = f" ({self.skipped} skipped with a reason)" if self.skipped else ""
        return f"followed in {self.followed} of {self.closed} closed months{skipped}"


def followed(plan: MethodPlan, account: Account, today: date) -> Followed:
    """A closed month counts as followed when the review engine marks it done with no finding,
    the same test as the method page's "months followed"; a skip with a reason is counted apart,
    because the plan allowed it but nothing was bought."""
    closed = list(
        MonthlyReview.objects.filter(plan__in=plan.versions(), closed_at__isnull=False)
        .values_list("month", flat=True)
        .distinct()
    )
    if not closed:
        return Followed(0, 0, 0)
    review = build_review(plan, JournalEntry.entries_for(account), today)
    done = skipped = 0
    for label in closed:
        row = review.month(label)
        if row is None:
            continue
        if row.status == "done" and not row.rule_ids:
            done += 1
        elif row.status == "skipped":
            skipped += 1
    return Followed(len(closed), done, skipped)


def method_text(plan: MethodPlan | None) -> str:
    if plan is None:
        return "No plan"
    name = plan.method().name
    if plan.is_momentum and plan.top_n:
        return f"{name}, top {plan.top_n} of {len(plan.symbol_list())}"
    return f"{name}, {len(plan.symbol_list())} symbol{'s' if len(plan.symbol_list()) != 1 else ''}"


def return_text(total: Decimal | None, days: int) -> str:
    """A change over `days` calendar days in words: as it is under a year ("-10.00% over 3
    days"), as a yearly rate from a year on ("+7.20% a year"), never stretched from a few months
    to a year. A stretch of one day has none."""
    if days <= 0 or total is None:
        return ""
    if days < YEAR_DAYS:
        return f"{percent(total * HUNDRED)} over {days} days"
    return f"{percent(yearly(total, days) * HUNDRED)} a year"


def drawdown_text(drop: Drawdown | None) -> str:
    if drop is None:
        return ""
    if drop.fraction == 0:
        return "no drop: the line never fell below a high"
    stretch = f"{drop.peak_day:%Y-%m-%d} to {drop.trough_day:%Y-%m-%d}"
    return f"{percent(drop.fraction * HUNDRED)}, {stretch}"


class Figures:
    """The money put in, the value, the gain, both returns and the worst drop, in words, for
    anything with a stretch and its numbers: an account (chapter 15) or the same money in the
    yardstick (exercise 1, decision 185)."""

    stretch: Period | None
    twr: Decimal | None
    mwr: Decimal | None
    drawdown: Drawdown | None

    @property
    def put_in(self) -> str:
        if self.stretch is None:
            return ""
        carried = (
            f" (incl. {money(self.stretch.opening)} held at the start)"
            if self.stretch.opening
            else ""
        )
        return f"{money(self.stretch.put_in)}{carried}"

    @property
    def value(self) -> str:
        if self.stretch is None:
            return ""
        return f"{money(self.stretch.last.value)} on {self.stretch.last.day:%Y-%m-%d}"

    @property
    def gain(self) -> str:
        if self.stretch is None:
            return ""
        return signed_money(self.stretch.gain)

    @property
    def money_weighted(self) -> str:
        if self.stretch is None or self.stretch.length <= 0:
            return ""
        if self.mwr is None:
            return "not worked out: no single rate fits these deposits"
        if self.stretch.length < YEAR_DAYS:
            return return_text(self.mwr, self.stretch.length)
        return f"{percent(self.mwr * HUNDRED)} a year"

    @property
    def time_weighted(self) -> str:
        if self.stretch is None or self.twr is None:
            return ""
        return return_text(self.twr, self.stretch.length)

    @property
    def worst_drop(self) -> str:
        return drawdown_text(self.drawdown)


@dataclass(frozen=True, slots=True)
class Numbers:
    """A series cut to the dates picked, and its numbers."""

    stretch: Period | None
    line: list[tuple[date, Decimal]]
    twr: Decimal | None = None
    mwr: Decimal | None = None
    drawdown: Drawdown | None = None


def numbers_of(series: Series, start: date, end: date) -> Numbers:
    """The stretch, the time-weighted line, both returns and the worst drop of a series. Under a
    year the money-weighted rate is solved per the stretch's own length, so it is the change over
    the days; from a year on, per year (`return_text` says which)."""
    stretch = period(series.days, start, end) if not series.problems else None
    if stretch is None:
        return Numbers(None, [])
    line = time_weighted_line(stretch.days)
    unit = stretch.length if 0 < stretch.length < YEAR_DAYS else YEAR_DAYS
    return Numbers(
        stretch,
        line,
        line_return(line),
        xirr(cash_flows(stretch), days_per_unit=unit),
        max_drawdown(line),
    )


@dataclass
class SameMoney(Figures):
    """The same money into the yardstick for one account: each of its trades' money bought (or a
    sell took out of) the yardstick on the trade's own day."""

    symbol: str
    series: Series
    stretch: Period | None
    line: list[tuple[date, Decimal]]
    adjusted: bool
    reason: str = ""
    twr: Decimal | None = None
    mwr: Decimal | None = None
    drawdown: Drawdown | None = None

    @property
    def label(self) -> str:
        return f"Same money into {self.symbol}"


@dataclass
class AccountResult(Figures):
    """One account on the page: its numbers in words, or why a number is missing."""

    account: Account
    plan: MethodPlan | None
    method: str
    series: Series
    stretch: Period | None
    line: list[tuple[date, Decimal]]
    months: str
    followed: str
    notes: list[str] = field(default_factory=list[str])
    reason: str = ""
    twr: Decimal | None = None
    mwr: Decimal | None = None
    drawdown: Drawdown | None = None
    # Exercise 1 (decision 185): the trades counted, kept for the same money into the yardstick,
    # and that line once the page has picked a yardstick.
    trades: list[Trade] = field(default_factory=list[Trade])
    same: SameMoney | None = None


def symbol_list(trades: Sequence[Trade]) -> list[str]:
    return sorted({trade.symbol for trade in trades})


def account_result(account: Account, start: date, end: date, today: date) -> AccountResult:
    """Everything one row and one line need, from the account's own records."""
    plan = plan_of(account)
    found = trades_for(account, end)
    notes: list[str] = []
    if found.open_orders:
        notes.append(
            f"{found.open_orders} order{'s' if found.open_orders != 1 else ''} still open at "
            "Alpaca: left out until filled."
        )
    since = (min((t.day for t in found.trades), default=start)) - timedelta(PRICE_LOOKBACK_DAYS)
    symbols = symbol_list(found.trades)
    prices = prices_for(symbols, since, end)
    closes_only = [
        symbol for symbol in symbols if prices[symbol].rows and not prices[symbol].adjusted
    ]
    if closes_only:
        notes.append(
            f"{', '.join(closes_only)} valued on closes: a stored day has no adjusted close, so "
            "dividends are not counted and a split would read as a fall. Get history with All "
            "available fills them."
        )
    series = value_series(found.trades, {symbol: prices[symbol].rows for symbol in symbols}, end)
    if series.pending:
        newest = max((day for p in prices.values() for day, _ in p.rows), default=None)
        after = f" (the newest is {newest:%Y-%m-%d})" if newest else ""
        count = len(series.pending)
        notes.append(
            f"{count} trade{'s' if count != 1 else ''} dated after the newest stored close{after}: "
            "counted once the nightly pull stores its day."
        )
    numbers = numbers_of(series, start, end)
    stretch = numbers.stretch
    reason = ""
    if series.problems:
        reason = "Not worked out: " + "; ".join(series.problems) + "."
    elif not found.trades:
        reason = "No trades in the journal yet, so there is nothing to value."
    elif stretch is None:
        reason = "No trade of this account counts inside the dates picked."
    line = numbers.line
    if plan is None:
        months = ""
        how_often = "no plan"
    else:
        first = plan.chain_start()
        last = plan.ended_on if not plan.active and plan.ended_on else today
        count = months_running(first, last)
        ended = ", ended" if not plan.active else ""
        months = f"{count} (from {first:%Y-%m-%d}{ended})"
        how_often = followed(plan, account, today).text
    result = AccountResult(
        account=account,
        plan=plan,
        method=method_text(plan),
        series=series,
        stretch=stretch,
        line=line,
        months=months,
        followed=how_often,
        notes=notes,
        reason=reason,
        twr=numbers.twr,
        mwr=numbers.mwr,
        drawdown=numbers.drawdown,
        trades=found.trades,
    )
    return result


def same_money_for(result: AccountResult, symbol: str, start: date, end: date) -> SameMoney:
    """Exercise 1 (decision 185): the account's own trades, the same money on the same days, into
    `symbol` at its stored adjusted close (else its close, said on the page). No trades, or a day
    the yardstick has no price for, is a reason, never a guess."""
    if not result.trades:
        return SameMoney(symbol, Series(), None, [], False, "No trades, so no money to put in.")
    since = min(trade.day for trade in result.trades) - timedelta(PRICE_LOOKBACK_DAYS)
    stored = prices_for([symbol], since, end)[symbol]
    series = same_money(result.trades, symbol, stored.rows, end)
    numbers = numbers_of(series, start, end)
    reason = ""
    if series.problems:
        reason = "Not worked out: " + "; ".join(series.problems) + "."
    elif numbers.stretch is None:
        reason = "None of this account's money went in inside the dates picked."
    return SameMoney(
        symbol=symbol,
        series=series,
        stretch=numbers.stretch,
        line=numbers.line,
        adjusted=stored.adjusted,
        reason=reason,
        twr=numbers.twr,
        mwr=numbers.mwr,
        drawdown=numbers.drawdown,
    )


# --- The yardstick --------------------------------------------------------------------------------


def yardstick_choices(user: AbstractBaseUser | AnonymousUser) -> list[str]:
    """Every symbol of the person's own: held, watched, or named by a plan."""
    named = MethodPlan.objects.filter(account__owner_id=user.pk).values_list("symbols", flat=True)
    in_plans = {symbol for text in named for symbol in text.split()}
    return sorted(set(manual.owner_symbols(user)) | in_plans)


def default_yardstick(choices: Sequence[str]) -> str:
    """The first S&P 500 index fund among the person's symbols, or "" when there is none."""
    return next((symbol for symbol in SP500_FUNDS if symbol in choices), "")


# --- Alpaca's own number --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AlpacaCheck:
    """Alpaca's equity and cash for a linked account, read now, or why they are missing."""

    equity: Decimal | None = None
    cash: Decimal | None = None
    error: str = ""

    @property
    def in_positions(self) -> Decimal | None:
        """Equity less cash: what Alpaca says the holdings are worth now."""
        if self.equity is None or self.cash is None:
            return None
        return self.equity - self.cash


def read_alpaca(account: Account) -> AlpacaCheck:
    try:
        found = client_for(account, timeout=ALPACA_TIMEOUT_SECONDS).account()
    except AlpacaError as error:
        return AlpacaCheck(error=error.message)
    return AlpacaCheck(found.equity, found.cash)


def alpaca_checks(
    user: AbstractBaseUser | AnonymousUser, accounts: Sequence[Account]
) -> dict[int, AlpacaCheck]:
    """Alpaca's numbers for each account the site owner linked to Alpaca paper, read at the same
    time so the page waits for the slowest answer, not the sum of them."""
    linked = [account for account in accounts if alpaca_allowed(user, account)]
    if not linked:
        return {}
    with ThreadPoolExecutor(max_workers=len(linked)) as pool:
        answers = list(pool.map(read_alpaca, linked))
    return {account.pk: answer for account, answer in zip(linked, answers, strict=True)}
