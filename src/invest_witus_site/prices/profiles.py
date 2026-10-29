"""What a symbol is: its name, exchange and a short description, from the price vendor
(2026-10-30, decision 150, backlog item 3).

Tiingo, as read on October 30, 2026 (https://www.tiingo.com/documentation/end-of-day, section
2.1.3 "Meta Endpoint"): `GET https://api.tiingo.com/tiingo/daily/<ticker>` answers one object
whose fields are `ticker` ("Ticker related to the asset."), `name` ("Full-length name of the
asset."), `exchangeCode` ("An identifier that maps which Exchange this asset is listed on."),
`description` ("Long-form descripton of the asset."), `startDate` ("The earliest date we have
price data available for the asset.") and `endDate` ("The latest date we have price data
available for the asset."); for both dates "When null it means no price data available for the
given asset." The page names no website field and says nothing about whether this endpoint
counts toward the request limits, so each request is counted like a price request.

So the page links to an issuer's own site only when the metadata carries one, which today it
does not, and never to a guessed Wikipedia article: only to Wikipedia's search page for the name,
labelled "Search Wikipedia" (authoritative-values rule).

A profile is refreshed at most once every `REFRESH_DAYS`: by the nightly pull, after the closes
and inside what is left of the run's request budget, capped at `PROFILES_PER_RUN`; or by the
owner's **Get description** on the symbol page. The CSV source has no metadata, so a laptop
without a Tiingo key has no profiles and the page says so.
"""

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Protocol, cast
from urllib.parse import quote_plus

from django.conf import settings
from django.utils import timezone

from invest_witus_site.prices.models import EXCHANGE_CODE_MAX, PROFILE_NAME_MAX, SymbolProfile
from invest_witus_site.prices.sources import PriceSourceError, TiingoEod

# At most once a week per symbol: a fund's name and description change rarely.
REFRESH_DAYS = 7
# The nightly pull's ceiling on profile requests, inside what the closes left of its budget.
PROFILES_PER_RUN = 10
# The page shows this many words of the description, with the rest behind "Full description".
SHORT_WORDS = 60
WIKIPEDIA_SEARCH = "https://en.wikipedia.org/w/index.php?search="


@dataclass(frozen=True, slots=True)
class ProfileData:
    """One metadata answer, checked."""

    symbol: str
    name: str
    exchange_code: str
    description: str
    start_date: date | None
    end_date: date | None


class MetadataSource(Protocol):
    """What a profile needs from a source: a name for the `source` column and the raw answer."""

    name: str

    def metadata(self, symbol: str) -> str: ...


def profile_source_from_settings() -> MetadataSource | None:
    """Tiingo when the owner set a key; `None` on a laptop with only the CSV folder."""
    if settings.TIINGO_API_KEY:
        return TiingoEod(settings.TIINGO_API_KEY)
    return None


def text_field(symbol: str, body: dict[str, object], key: str, limit: int | None) -> str:
    raw = body.get(key)
    if raw is None:
        return ""
    if not isinstance(raw, str):
        raise PriceSourceError(symbol, f"{key} is not text: {raw!r}")
    value = " ".join(raw.split())
    return value[:limit] if limit else value


def date_field(symbol: str, body: dict[str, object], key: str) -> date | None:
    raw = body.get(key)
    if raw is None or raw == "":
        return None
    if not isinstance(raw, str) or len(raw) < 10:
        raise PriceSourceError(symbol, f"{key} is not a date: {raw!r}")
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        raise PriceSourceError(symbol, f"{key} is not a date: {raw!r}") from None


def parse_profile(symbol: str, text: str) -> ProfileData:
    """The metadata object to a `ProfileData`. A missing or `null` field is empty (or `None` for
    a date); a field of the wrong type is refused like a bad close. Whitespace inside the name
    and description is collapsed, and the name and exchange are cut to their columns."""
    try:
        body: object = json.loads(text)
    except json.JSONDecodeError as error:
        raise PriceSourceError(symbol, f"not JSON: {error.msg}") from error
    if not isinstance(body, dict):
        raise PriceSourceError(symbol, "expected one object of metadata")
    fields = cast(dict[str, object], body)
    return ProfileData(
        symbol=symbol,
        name=text_field(symbol, fields, "name", PROFILE_NAME_MAX),
        exchange_code=text_field(symbol, fields, "exchangeCode", EXCHANGE_CODE_MAX),
        description=text_field(symbol, fields, "description", None),
        start_date=date_field(symbol, fields, "startDate"),
        end_date=date_field(symbol, fields, "endDate"),
    )


def is_fresh(profile: SymbolProfile | None, now: datetime) -> bool:
    return profile is not None and profile.fetched_at > now - timedelta(days=REFRESH_DAYS)


def next_refresh(profile: SymbolProfile) -> datetime:
    return profile.fetched_at + timedelta(days=REFRESH_DAYS)


def fetch_profile(
    source: MetadataSource, symbol: str, now: datetime | None = None
) -> SymbolProfile:
    """One request for `symbol`'s metadata, stored over any older row. A refusal raises
    `PriceSourceError` and stores nothing."""
    data = parse_profile(symbol, source.metadata(symbol))
    profile, _ = SymbolProfile.objects.update_or_create(
        symbol=symbol,
        defaults={
            "name": data.name,
            "exchange_code": data.exchange_code,
            "description": data.description,
            "start_date": data.start_date,
            "end_date": data.end_date,
            "source": source.name,
            "fetched_at": now or timezone.now(),
        },
    )
    return profile


@dataclass
class ProfileRun:
    """What the nightly refresh did, for the cron's JSON."""

    requests: int = 0
    fetched: list[str] = field(default_factory=list[str])
    failed: dict[str, str] = field(default_factory=dict[str, str])
    skipped: list[str] = field(default_factory=list[str])

    def as_dict(self) -> dict[str, object]:
        return {
            "requests": self.requests,
            "fetched": self.fetched,
            "failed": self.failed,
            "skipped": self.skipped,
        }


def due(symbols: list[str], now: datetime) -> list[str]:
    """The symbols with no profile or one older than `REFRESH_DAYS`, in the order given."""
    fresh = set(
        SymbolProfile.objects.filter(
            symbol__in=symbols, fetched_at__gt=now - timedelta(days=REFRESH_DAYS)
        ).values_list("symbol", flat=True)
    )
    return [symbol for symbol in symbols if symbol not in fresh]


def refresh_profiles(
    source: MetadataSource, symbols: list[str], budget: int, now: datetime | None = None
) -> ProfileRun:
    """Fetch the due profiles, one request each, at most `budget` (never more than
    `PROFILES_PER_RUN`). A rate limit stops the run; the rest are skipped for the next night."""
    now = now or timezone.now()
    run = ProfileRun()
    limit = max(0, min(budget, PROFILES_PER_RUN))
    pending = due(symbols, now)
    for index, symbol in enumerate(pending):
        if run.requests >= limit:
            run.skipped.extend(pending[index:])
            break
        run.requests += 1
        try:
            fetch_profile(source, symbol, now)
        except PriceSourceError as error:
            run.failed[symbol] = error.problem
            if error.retry_later:
                run.skipped.extend(pending[index + 1 :])
                break
            continue
        run.fetched.append(symbol)
    return run


def wikipedia_search_url(name: str) -> str:
    """Wikipedia's search page for the name: Wikipedia picks the article, never this app."""
    return WIKIPEDIA_SEARCH + quote_plus(name)


def short_description(text: str, words: int = SHORT_WORDS) -> tuple[str, bool]:
    """The first `words` words, and whether anything was cut."""
    parts = text.split()
    if len(parts) <= words:
        return text, False
    return " ".join(parts[:words]) + " ...", True
