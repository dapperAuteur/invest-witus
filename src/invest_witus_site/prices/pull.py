"""The nightly pull: which symbols, which days, one request per symbol, and the counts.

Written to be run twice without harm, because Vercel's Hobby cron may fire anywhere inside its
hour, does not retry a failed run, and can occasionally deliver a run twice or not at all
(Vercel's cron docs, read October 28, 2026). Asking for the last `DAYS_BACK` days every night
means one missed night is filled in by the next, and `DailyClose.upsert` means a repeated night
writes nothing.

A symbol's first pull asks for `BACKFILL_DAYS` of closes instead (2026-10-29), so a symbol just
added to a watch list has a year of history for its page after one night. It is still one
request: Tiingo's end-of-day endpoint takes a `startDate` and an `endDate` (chapter 08's
reading), so the budget below counts it like any other symbol. `Backfill` remembers which
symbols have had their year.
"""

import logging
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta

from django.utils import timezone

from invest_witus_site.holdings.models import Holding
from invest_witus_site.prices.models import Backfill, DailyClose, UpsertCount
from invest_witus_site.prices.sources import PriceSource, PriceSourceError
from invest_witus_site.watchlist.models import WatchItem

log = logging.getLogger(__name__)

# How many days back a run asks for. A week of closes is seven small rows per symbol, and it
# makes any single missed night harmless.
DAYS_BACK = 7
# The free plan's hourly limit, from Tiingo's pricing page (read October 28, 2026): 50 requests
# an hour, 1,000 a day, 500 unique symbols a month. One request per symbol per run, and a run
# never makes more than this many; what is left is listed as skipped for the next run.
REQUESTS_PER_RUN = 50
# The pause between two symbols. Tiingo's overview (read the same day) counts requests per hour
# and per day and says "We do not rate limit to minute or second", so this is a courtesy to the
# vendor, not a documented requirement; the budget above is the real guard.
PAUSE_SECONDS = 1.0
# How far back a symbol's first pull reaches: a year, the history page's longest range.
BACKFILL_DAYS = 365


def watch_symbols() -> set[str]:
    """Every symbol on any account's watch list (chapter 09). A watched symbol with no close yet
    is exactly what the next run should fetch, so there is no filter here."""
    return set(WatchItem.objects.values_list("symbol", flat=True))


def symbol_universe() -> list[str]:
    """Every symbol an account holds (cash has no price), plus the watch list's, each once."""
    held = Holding.objects.exclude(kind=Holding.Kind.CASH).values_list("symbol", flat=True)
    return sorted(set(held) | watch_symbols())


@dataclass
class PullResult:
    """What one run did, for the command's output and the cron route's JSON."""

    source: str
    since: date
    until: date
    symbols: list[str]
    requests: int = 0
    counts: UpsertCount = UpsertCount()
    failed: dict[str, str] = field(default_factory=dict[str, str])
    skipped: list[str] = field(default_factory=list[str])
    # The symbols whose request this run reached back `BACKFILL_DAYS` for the first time.
    backfilled: list[str] = field(default_factory=list[str])

    def as_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "since": self.since.isoformat(),
            "until": self.until.isoformat(),
            "symbols": self.symbols,
            "requests": self.requests,
            "inserted": self.counts.inserted,
            "updated": self.counts.updated,
            "unchanged": self.counts.unchanged,
            "failed": self.failed,
            "skipped": self.skipped,
            "backfilled": self.backfilled,
        }


def pull(
    source: PriceSource,
    symbols: Iterable[str],
    since: date,
    until: date,
    pause: float | None = None,
    budget: int = REQUESTS_PER_RUN,
) -> PullResult:
    """One request per symbol, in order; a refusal is recorded and the next symbol is tried. A
    rate limit stops the run, and the symbols not reached are listed as skipped. A symbol that
    has not had its backfill asks from `until - BACKFILL_DAYS` instead of `since`, in the same
    single request; a skipped or refused one asks again on the next run."""
    if pause is None:
        pause = PAUSE_SECONDS
    result = PullResult(source.name, since, until, list(symbols))
    backfill_since = until - timedelta(days=BACKFILL_DAYS)
    # A row that reaches back to this run's year counts; one written today still will tomorrow.
    done = set(
        Backfill.objects.filter(symbol__in=result.symbols, since__lte=backfill_since).values_list(
            "symbol", flat=True
        )
    )
    for index, symbol in enumerate(result.symbols):
        if result.requests >= budget:
            result.skipped.append(symbol)
            continue
        if result.requests > 0 and pause > 0:
            time.sleep(pause)
        result.requests += 1
        start = since if symbol in done or since <= backfill_since else backfill_since
        try:
            points = source.closes(symbol, start, until)
        except PriceSourceError as error:
            result.failed[symbol] = error.problem
            log.warning("pull_prices: %s", error)
            if error.retry_later:
                result.skipped.extend(result.symbols[index + 1 :])
                break
            continue
        counts = DailyClose.upsert(symbol, points, source.name)
        result.counts = result.counts + counts
        if symbol not in done and start <= backfill_since:
            Backfill.objects.update_or_create(
                symbol=symbol, defaults={"since": start, "done_at": timezone.now()}
            )
            if start < since:
                result.backfilled.append(symbol)
        log.info("pull_prices: %s, %d day(s) from %s: %s", symbol, len(points), source.name, counts)
    return result
