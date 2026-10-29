"""The owner's two price buttons (2026-10-29): **Fetch prices now** and **Get history**.

BAM asked for a button instead of `manage.py pull_prices --since <date> --symbols <list>`, and for
a way to fetch prices without waiting for the nightly cron. Both buttons run code the pull
already has, for the signed-in owner only, behind a ten-minute guard each:

- **Fetch prices now** is the nightly pull (`pull.pull`), for the symbols the owner's own
  accounts hold or watch, inside the same 50-request budget and one-second pause, plus a time
  limit so it answers inside Vercel's function maximum.
- **Get history** is one request for one symbol over a chosen range (1, 5 or 10 years, or all
  available), written with `DailyClose.upsert`, so a second press adds nothing.
- **Fetch history for selected / for all** (2026-10-29, decision 139) is Get history for several
  watched symbols in one press: one request per symbol, inside the same 50-request budget, pause
  and 240-second limit as Fetch prices now, each symbol behind its own Get history guard.

Tiingo's end-of-day page (https://www.tiingo.com/documentation/end-of-day, read 2026-10-29) shows
historical prices as one request with `startDate` and `endDate` and names no limit on the range a
request may span or on how far back it reaches; its metadata endpoint's `startDate` is "The
earliest date we have price data available for the asset." The pricing page
(https://www.tiingo.com/about/pricing, read the same day) lists "Historical: 30+ Years" for the
free Starter plan. So the history button asks once and reports the earliest close it got back:
the answer itself says how deep the history goes.
"""

import datetime
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.db import IntegrityError, transaction
from django.db.models import Min
from django.utils import timezone

from invest_witus_site.holdings.models import Holding
from invest_witus_site.prices import pull as pull_module
from invest_witus_site.prices.models import Backfill, DailyClose, ManualRun, UpsertCount
from invest_witus_site.prices.pull import BACKFILL_DAYS, REQUESTS_PER_RUN, PullResult
from invest_witus_site.prices.sources import PriceSource, PriceSourceError
from invest_witus_site.watchlist.models import WatchItem

# How long a button waits before it runs again for the same owner (Fetch prices now) or the
# same symbol (Get history). Ten minutes lets the owner retry after fixing a symbol without
# letting a held-down button spend the free plan's 50 requests an hour (decision 70).
GUARD_MINUTES = 10

# The button's own ceiling on a run, in seconds. Vercel's Hobby maximum is 300 s per invocation
# (chapter 06, decision 58). The check happens before each request and a request may wait up to
# `sources.REQUEST_TIMEOUT_SECONDS` (20 s), so the slowest run still answers at about 260 s.
# Fifty requests at about a second each, plus the one-second pause, take well under this.
FETCH_TIME_LIMIT_SECONDS = 240.0

# The history ranges, as the form's values, labels and years back. `None` is "all available":
# Tiingo's page names no earliest date to ask for, so the request starts at `ALL_AVAILABLE_SINCE`,
# a day before any listed market's daily data, and the earliest close that comes back is the
# answer. One request either way.
HISTORY_RANGES: dict[str, tuple[str, int | None]] = {
    "1y": ("1 year", 1),
    "2y": ("2 years", 2),
    "5y": ("5 years", 5),
    "10y": ("10 years", 10),
    "all": ("All available", None),
}
# The add form's automatic first fetch asks for two years, like the nightly backfill
# (decision 149): the 12-1 window needs about 13 months.
DEFAULT_HISTORY_RANGE = "2y"
ALL_AVAILABLE_SINCE = date(1900, 1, 1)

STOP_REASONS = {
    "budget": f"the {REQUESTS_PER_RUN}-request limit for one run",
    "rate limit": "Tiingo's hourly or daily limit",
    "time limit": "the time one press may take",
}


def claim(kind: str, key: str, now: datetime.datetime | None = None) -> datetime.datetime | None:
    """Start a run for this kind and key, or refuse it. `None` means the run may go ahead (the
    start time is already written); a datetime is when the next run may start.

    The update only matches a row older than the guard, and a missing row is created inside its
    own savepoint, so two presses at the same moment cannot both win: the second finds the fresh
    row, or hits the unique constraint, and is refused."""
    now = now or timezone.now()
    guard = timedelta(minutes=GUARD_MINUTES)
    if ManualRun.objects.filter(kind=kind, key=key, ran_at__lte=now - guard).update(ran_at=now):
        return None
    try:
        with transaction.atomic():
            ManualRun.objects.create(kind=kind, key=key, ran_at=now)
    except IntegrityError:
        return ManualRun.objects.get(kind=kind, key=key).ran_at + guard
    return None


def when(moment: datetime.datetime) -> str:
    """A time for a message, in the site's time zone with its name."""
    return f"{timezone.localtime(moment):%Y-%m-%d %H:%M %Z}"


def owner_symbols(user: AbstractBaseUser | AnonymousUser) -> list[str]:
    """Every symbol the user's own accounts hold (cash has no price) or watch, each once. A
    signed-out visitor owns no account, so the answer is empty; the views require a sign-in."""
    held = (
        Holding.objects.filter(account__owner=user)
        .exclude(kind=Holding.Kind.CASH)
        .values_list("symbol", flat=True)
    )
    watched = WatchItem.objects.filter(account__owner=user).values_list("symbol", flat=True)
    return sorted(set(held) | set(watched))


def plural(count: int, word: str) -> str:
    return f"{count:,} {word}{'' if count == 1 else 's'}"


def fetch_messages(result: PullResult) -> tuple[str, list[str], list[str]]:
    """What one Fetch prices now run did, as the counts line, the error lines (one per refused
    symbol) and the info lines (the backfilled symbols, and the ones left for tonight)."""
    counts = result.counts
    summary = (
        f"Fetched closes from {result.source} for {plural(len(result.symbols), 'symbol')} in "
        f"{plural(result.requests, 'request')}: {counts.inserted:,} inserted, "
        f"{counts.updated:,} updated, {counts.unchanged:,} unchanged, "
        f"{len(result.failed):,} refused, {len(result.backfilled):,} backfilled, "
        f"{len(result.skipped):,} skipped for budget."
    )
    errors = [f"Refused {symbol}: {problem}" for symbol, problem in result.failed.items()]
    infos: list[str] = []
    if result.backfilled:
        infos.append(f"Two years of closes, first time: {', '.join(result.backfilled)}.")
    if result.skipped:
        reason = STOP_REASONS.get(result.stopped, "the run's limits")
        infos.append(
            f"Stopped by {reason}; not reached: {', '.join(result.skipped)}. "
            "The rest continue tonight."
        )
    return summary, errors, infos


def years_before(day: date, years: int) -> date:
    """The same calendar day `years` earlier; February 29 becomes February 28."""
    try:
        return day.replace(year=day.year - years)
    except ValueError:
        return day.replace(year=day.year - years, day=28)


def history_since(choice: str, today: date) -> date | None:
    """The `startDate` for a range choice, or `None` for a choice the form does not offer."""
    if choice not in HISTORY_RANGES:
        return None
    years = HISTORY_RANGES[choice][1]
    return ALL_AVAILABLE_SINCE if years is None else years_before(today, years)


@dataclass(frozen=True, slots=True)
class HistoryResult:
    """What one Get history request did."""

    symbol: str
    since: date
    returned: int
    first_returned: date | None
    counts: UpsertCount
    earliest_stored: date | None


def fetch_history(source: PriceSource, symbol: str, since: date, until: date) -> HistoryResult:
    """One request for `symbol` from `since` to `until`, written once per day. A source's
    refusal raises `PriceSourceError` for the view to word. A range that reaches back past the
    nightly backfill's window (two years) is recorded in `Backfill`, so the next night does not
    ask again."""
    points = source.closes(symbol, since, until)
    counts = DailyClose.upsert(symbol, points, source.name)
    if points and since <= until - timedelta(days=BACKFILL_DAYS):
        row = Backfill.objects.filter(symbol=symbol).first()
        if row is None or row.since > since:
            Backfill.objects.update_or_create(
                symbol=symbol, defaults={"since": since, "done_at": timezone.now()}
            )
    earliest = DailyClose.objects.filter(symbol=symbol).aggregate(first=Min("date"))["first"]
    first = min((point.day for point in points), default=None)
    return HistoryResult(symbol, since, len(points), first, counts, earliest)


def history_message(result: HistoryResult, label: str) -> str:
    asked = f"{result.symbol}, {label.lower()} asked (from {result.since:%Y-%m-%d})"
    if not result.returned:
        stored = (
            f" Earliest close stored: {result.earliest_stored:%Y-%m-%d}."
            if result.earliest_stored
            else ""
        )
        return f"{asked}: the source returned no closes.{stored}"
    counts = result.counts
    first = f"{result.first_returned:%Y-%m-%d}" if result.first_returned else "none"
    earliest = f"{result.earliest_stored:%Y-%m-%d}" if result.earliest_stored else "none"
    return (
        f"{asked}: {plural(counts.inserted, 'day')} added, {counts.updated:,} updated, "
        f"{counts.unchanged:,} unchanged. Earliest close returned: {first}; earliest close "
        f"now stored: {earliest}."
    )


# How long to wait before pressing again for the symbols a stopped run did not reach: Tiingo
# counts the free plan's 50 requests per hour (decision 70), so a budget or a 429 stop waits the
# hour; a time stop spent no extra requests and can go again in a minute.
RETRY_MINUTES = {"budget": 60, "rate limit": 60, "time limit": 1}


@dataclass
class ManyResult:
    """What one Fetch history for selected (or for all) press did, symbol by symbol."""

    since: date
    fetched: list[HistoryResult] = field(default_factory=list[HistoryResult])
    failed: dict[str, str] = field(default_factory=dict[str, str])
    # Symbols inside their ten-minute Get history guard, with when each may run again.
    guarded: dict[str, datetime.datetime] = field(default_factory=dict[str, datetime.datetime])
    not_reached: list[str] = field(default_factory=list[str])
    stopped: str = ""
    requests: int = 0


def fetch_history_many(
    source: PriceSource,
    symbols: list[str],
    since: date,
    until: date,
    budget: int = REQUESTS_PER_RUN,
    time_limit: float = FETCH_TIME_LIMIT_SECONDS,
    clock: Callable[[], float] = time.monotonic,
) -> ManyResult:
    """Get history for each symbol in turn. Before each request: the budget, then the time
    limit (either stops the run, and the rest are `not_reached`), then the symbol's own guard (a
    guarded symbol is skipped and named; it spends no request). A refusal is recorded and the
    next symbol tried; a 429 stops the run like the budget."""
    started = clock()
    result = ManyResult(since)
    for index, symbol in enumerate(symbols):
        if result.requests >= budget:
            result.stopped = "budget"
        elif clock() - started >= time_limit:
            result.stopped = "time limit"
        if result.stopped:
            result.not_reached = symbols[index:]
            break
        refused_until = claim(ManualRun.Kind.HISTORY, symbol)
        if refused_until is not None:
            result.guarded[symbol] = refused_until
            continue
        if result.requests > 0 and pull_module.PAUSE_SECONDS > 0:
            time.sleep(pull_module.PAUSE_SECONDS)
        result.requests += 1
        try:
            result.fetched.append(fetch_history(source, symbol, since, until))
        except PriceSourceError as error:
            result.failed[symbol] = error.problem
            if error.retry_later:
                result.stopped = "rate limit"
                result.not_reached = symbols[index + 1 :]
                break
    return result


def many_messages(result: ManyResult, label: str) -> tuple[list[str], list[str], list[str]]:
    """The success, error and info lines for one press: one line per symbol fetched, one per
    refusal, then the guarded symbols and the ones not reached."""
    successes: list[str] = []
    for item in result.fetched:
        earliest = f"{item.earliest_stored:%Y-%m-%d}" if item.earliest_stored else "none"
        successes.append(
            f"{item.symbol}, {label.lower()}: {plural(item.counts.inserted, 'day')} added, "
            f"{item.counts.updated:,} updated; earliest close stored {earliest}."
        )
    errors = [
        f"{symbol}: {problem}. Nothing was stored." for symbol, problem in result.failed.items()
    ]
    infos: list[str] = []
    if result.guarded:
        listed = ", ".join(f"{symbol} (at {when(at)})" for symbol, at in result.guarded.items())
        infos.append(
            f"Skipped, fetched less than {GUARD_MINUTES} minutes ago; each can run again at the "
            f"time shown: {listed}."
        )
    if result.not_reached:
        reason = STOP_REASONS.get(result.stopped, "the run's limits")
        minutes = RETRY_MINUTES.get(result.stopped, 60)
        infos.append(
            f"Stopped by {reason}. The rest: press again in {plural(minutes, 'minute')}: "
            f"{', '.join(result.not_reached)}."
        )
    return successes, errors, infos
