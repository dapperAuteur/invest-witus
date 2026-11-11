"""Fetching and storing: the ticker maps, one symbol's filings and figures, and the nightly run
over the watched symbols (chapter 16).

A refresh of one company is at most four requests: the two ticker maps when this process has
not read them in the last day, the submissions feed, and companyfacts. Each request waits its
turn in `sec.throttle`. The nightly run asks only for watched symbols whose data is older than
`STALE_HOURS`, so a cron delivered twice does nothing the second time, and it stops at a refusal
or at its time limit; what is left waits for the next night.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from invest_witus import filings as lib
from invest_witus_site.filings import sec
from invest_witus_site.filings.models import COMPANY, FUND, NOT_LISTED, Filing, KeyFact, SecCompany
from invest_witus_site.holdings.models import Holding
from invest_witus_site.watchlist.models import WatchItem

log = logging.getLogger(__name__)

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FUND_TICKERS_URL = "https://www.sec.gov/files/company_tickers_mf.json"
# The ticker maps change when a company lists, renames or delists: once a day is enough.
MAPS_MAX_AGE = timedelta(days=1)
# A symbol's filings are fetched again by the nightly run once this old.
STALE_HOURS = 20
# The nightly run's own ceiling, after the price pull: about 4 requests a second and two per
# symbol, so about 120 symbols fit; a longer list continues the next night.
RUN_TIME_LIMIT_SECONDS = 60.0
# Figures older than this are not stored: the table shows five years.
FACT_YEARS = 7
FUND_KINDS = (Holding.Kind.ETF, Holding.Kind.MUTUAL_FUND)


@dataclass(frozen=True, slots=True)
class TickerMaps:
    companies: dict[str, lib.Listing]
    funds: dict[str, lib.Listing]
    read_at: datetime


_maps: TickerMaps | None = None
_maps_lock = threading.Lock()


def ticker_maps(now: datetime) -> TickerMaps:
    """Both maps, from this process's copy when it is under a day old (two requests otherwise)."""
    global _maps
    with _maps_lock:
        if _maps is not None and now - _maps.read_at < MAPS_MAX_AGE:
            return _maps
    companies = lib.parse_company_tickers(sec.get(TICKERS_URL, now))
    funds = lib.parse_fund_tickers(sec.get(FUND_TICKERS_URL, now))
    fresh = TickerMaps(companies, funds, now)
    with _maps_lock:
        _maps = fresh
    return fresh


def forget_maps() -> None:
    """Drop this process's copy of the maps (the tests start each from nothing)."""
    global _maps
    with _maps_lock:
        _maps = None


def held_as_fund(symbol: str) -> bool:
    """The owner marked the symbol an ETF or a mutual fund on a holding (chapter 05)."""
    return Holding.objects.filter(symbol=symbol, kind__in=FUND_KINDS).exists()


def resolve(symbol: str, now: datetime) -> SecCompany:
    """What EDGAR says the symbol is, from the stored row when it was checked in the last day."""
    stored = SecCompany.objects.filter(symbol=symbol).first()
    if stored is not None and now - stored.checked_at < MAPS_MAX_AGE:
        return stored
    if held_as_fund(symbol):
        kind, listing = SecCompany.Kind.FUND, None
    else:
        maps = ticker_maps(now)
        found, listing = lib.classify(symbol, maps.companies, maps.funds)
        kind = SecCompany.Kind(found)
    company = stored or SecCompany(symbol=symbol)
    company.kind = kind
    company.cik = lib.padded_cik(listing.cik) if listing is not None else ""
    if listing is not None and listing.title:
        company.name = listing.title
    company.checked_at = now
    company.save()
    return company


def store_filings(company: SecCompany, submissions: lib.Submissions, now: datetime) -> int:
    rows = lib.recent_reports(submissions.filings)
    with transaction.atomic():
        Filing.objects.filter(symbol=company.symbol).delete()
        Filing.objects.bulk_create(
            Filing(
                symbol=company.symbol,
                cik=company.cik,
                form=row.form,
                filing_date=row.filed,
                report_date=row.report_date,
                accession=row.accession,
                primary_document=row.primary_document,
                document_url=row.url(company.cik),
                description=row.description[:200],
                fetched_at=now,
            )
            for row in rows
        )
    return len(rows)


def store_facts(symbol: str, facts: list[lib.Fact], now: datetime) -> int:
    with transaction.atomic():
        KeyFact.objects.filter(symbol=symbol).delete()
        KeyFact.objects.bulk_create(
            KeyFact(
                symbol=symbol,
                concept=fact.concept,
                unit=fact.unit,
                period_start=fact.start,
                period_end=fact.end,
                value=fact.value,
                form=fact.form,
                filed=fact.filed,
                accession=fact.accession,
                fiscal_year=fact.fiscal_year,
                fiscal_period=fact.fiscal_period[:4],
                fetched_at=now,
            )
            for fact in facts
        )
    return len(facts)


@dataclass
class Refreshed:
    """What one symbol's refresh did."""

    symbol: str
    kind: str
    filings: int = 0
    facts: int = 0
    note: str = ""


def refresh_symbol(symbol: str, now: datetime | None = None) -> Refreshed:
    """Resolve the symbol, then for a company store its recent filings and its figures. A fund
    or an unlisted symbol stops after the maps, with its stored filings removed. Raises
    `sec.SecError` (the row keeps the problem) or `lib.FilingsDataError`."""
    now = now or timezone.now()
    symbol = symbol.strip().upper()
    company: SecCompany | None = None
    try:
        company = resolve(symbol, now)
        if company.kind != COMPANY:
            Filing.objects.filter(symbol=symbol).delete()
            KeyFact.objects.filter(symbol=symbol).delete()
            mark_good(company, filings=False, facts=False, now=now)
            return Refreshed(symbol, company.kind)
        submissions = lib.parse_submissions(sec.get(lib.submissions_url(company.cik), now))
        if lib.is_fund_filer(submissions):
            company.kind = SecCompany.Kind.FUND
            company.save(update_fields=["kind"])
            Filing.objects.filter(symbol=symbol).delete()
            KeyFact.objects.filter(symbol=symbol).delete()
            mark_good(company, filings=False, facts=False, now=now)
            return Refreshed(symbol, company.kind)
        if submissions.name:
            company.name = submissions.name[:200]
        result = Refreshed(symbol, company.kind)
        result.filings = store_filings(company, submissions, now)
        try:
            text = sec.get(lib.companyfacts_url(company.cik), now)
        except sec.SecError as error:
            if error.status != 404:
                raise
            text = '{"facts": {}}'
            result.note = "SEC EDGAR has no XBRL figures for this company"
        since = date(now.year - FACT_YEARS, 1, 1)
        result.facts = store_facts(symbol, lib.parse_companyfacts(text, since=since), now)
        mark_good(company, filings=True, facts=True, now=now)
        return result
    except (sec.SecError, lib.FilingsDataError) as error:
        problem = error.problem if isinstance(error, sec.SecError) else f"unexpected data: {error}"
        target = company or SecCompany.objects.filter(symbol=symbol).first()
        if target is not None:
            target.problem = problem[:300]
            target.problem_at = now
            target.save(update_fields=["problem", "problem_at"])
        raise


def mark_good(company: SecCompany, filings: bool, facts: bool, now: datetime) -> None:
    company.problem = ""
    company.problem_at = None
    if filings:
        company.filings_fetched_at = now
    if facts:
        company.facts_fetched_at = now
    company.save()


@dataclass
class FilingsRun:
    """What the nightly run did, for the cron's JSON."""

    refreshed: list[str] = field(default_factory=list[str])
    funds: list[str] = field(default_factory=list[str])
    not_listed: list[str] = field(default_factory=list[str])
    failed: dict[str, str] = field(default_factory=dict[str, str])
    skipped: list[str] = field(default_factory=list[str])
    stopped: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "refreshed": self.refreshed,
            "funds": self.funds,
            "not_listed": self.not_listed,
            "failed": self.failed,
            "skipped": self.skipped,
            "stopped": self.stopped,
        }


def due_symbols(now: datetime) -> list[str]:
    """Every watched symbol with no data, or data older than `STALE_HOURS`, in order."""
    watched = sorted(set(WatchItem.objects.values_list("symbol", flat=True)))
    cutoff = now - timedelta(hours=STALE_HOURS)
    company = Q(kind=SecCompany.Kind.COMPANY, filings_fetched_at__gt=cutoff)
    other = ~Q(kind=SecCompany.Kind.COMPANY) & Q(checked_at__gt=cutoff)
    fresh = set(
        SecCompany.objects.filter(symbol__in=watched, problem="")
        .filter(company | other)
        .values_list("symbol", flat=True)
    )
    return [symbol for symbol in watched if symbol not in fresh]


def refresh_watched(
    now: datetime | None = None, time_limit: float = RUN_TIME_LIMIT_SECONDS
) -> FilingsRun:
    """The nightly step: each due watched symbol once, stopping at a refusal or the time limit."""
    now = now or timezone.now()
    run = FilingsRun()
    pending = due_symbols(now)
    started = time.monotonic()
    for index, symbol in enumerate(pending):
        if time.monotonic() - started > time_limit:
            run.skipped.extend(pending[index:])
            run.stopped = "time limit"
            break
        try:
            done = refresh_symbol(symbol, now)
        except sec.SecError as error:
            run.failed[symbol] = error.problem
            if error.retry_later:
                run.skipped.extend(pending[index + 1 :])
                run.stopped = "refused"
                break
            continue
        except lib.FilingsDataError as error:
            run.failed[symbol] = f"unexpected data: {error}"
            continue
        if done.kind == FUND:
            run.funds.append(symbol)
        elif done.kind == NOT_LISTED:
            run.not_listed.append(symbol)
        else:
            run.refreshed.append(symbol)
    log.info("filings: %s", run.as_dict())
    return run
