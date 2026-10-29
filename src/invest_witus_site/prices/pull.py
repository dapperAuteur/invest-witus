"""The nightly pull: which symbols, which days, one request per symbol, and the counts.

Written to be run twice without harm, because Vercel's Hobby cron may fire anywhere inside its
hour, does not retry a failed run, and can occasionally deliver a run twice or not at all
(Vercel's cron docs, read October 28, 2026). Asking for the last `DAYS_BACK` days every night
means one missed night is filled in by the next, and `DailyClose.upsert` means a repeated night
writes nothing.
"""

import logging
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

from invest_witus_site.holdings.models import Holding
from invest_witus_site.prices.models import DailyClose, UpsertCount
from invest_witus_site.prices.sources import PriceSource, PriceSourceError

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


def watch_symbols() -> set[str]:
    """Reserved for chapter 09: the symbols on the owner's watch lists. Nothing yet."""
    return set()


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
    rate limit stops the run, and the symbols not reached are listed as skipped."""
    if pause is None:
        pause = PAUSE_SECONDS
    result = PullResult(source.name, since, until, list(symbols))
    for index, symbol in enumerate(result.symbols):
        if result.requests >= budget:
            result.skipped.append(symbol)
            continue
        if result.requests > 0 and pause > 0:
            time.sleep(pause)
        result.requests += 1
        try:
            points = source.closes(symbol, since, until)
        except PriceSourceError as error:
            result.failed[symbol] = error.problem
            log.warning("pull_prices: %s", error)
            if error.retry_later:
                result.skipped.extend(result.symbols[index + 1 :])
                break
            continue
        counts = DailyClose.upsert(symbol, points, source.name)
        result.counts = result.counts + counts
        log.info("pull_prices: %s, %d day(s) from %s: %s", symbol, len(points), source.name, counts)
    return result
