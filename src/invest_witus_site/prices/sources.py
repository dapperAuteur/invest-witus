"""Where closes come from: a Protocol, Tiingo's end-of-day endpoint over httpx, and a folder of
CSV files for a laptop and the tests.

Every source answers the same question (this symbol, these days) with chapter 02's `PricePoint`s,
and refuses one symbol with `PriceSourceError` rather than a crash, so the pull can record the
refusal and go on to the next symbol.

Tiingo, as read on October 28, 2026 (https://www.tiingo.com/documentation/end-of-day and
/documentation/general/connecting): prices for one ticker come from
`https://api.tiingo.com/tiingo/daily/<ticker>/prices` with `startDate` and `endDate`; the token
goes in the `Authorization` header as `Token <value>`; each day is an object with `date`, `open`,
`high`, `low`, `close`, `volume` and the adjusted and dividend fields. The docs describe `date`
only as "the date this data pertains to", so the parser reads its first ten characters, which
covers a bare date and a timestamp alike.
"""

import json
import logging
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Protocol, cast

import httpx
from django.conf import settings

from invest_witus.prices.csv_file import PriceFileError, PricePoint, load_prices

log = logging.getLogger(__name__)

# The seam the tests use, as in chapter 07: a `MockTransport` here and nothing leaves the process.
transport: httpx.BaseTransport | None = None

TIINGO_BASE_URL = "https://api.tiingo.com"
REQUEST_TIMEOUT_SECONDS = 20.0


class PriceSourceError(Exception):
    """One symbol the source could not answer. `retry_later` is True when asking for the next
    symbol now would fail the same way (a rate limit), so the pull should stop for this run."""

    def __init__(self, symbol: str, problem: str, retry_later: bool = False) -> None:
        super().__init__(f"{symbol}: {problem}")
        self.symbol = symbol
        self.problem = problem
        self.retry_later = retry_later


class PriceSource(Protocol):
    """What the pull needs from a source: a name for the `source` column, and closes by day."""

    name: str

    def closes(self, symbol: str, since: date, until: date) -> list[PricePoint]: ...


class CsvPrices:
    """A folder of `<SYMBOL>.csv` files in chapter 02's format (`date,close`)."""

    name = "csv"

    def __init__(self, folder: Path) -> None:
        self.folder = folder

    def closes(self, symbol: str, since: date, until: date) -> list[PricePoint]:
        path = self.folder / f"{symbol}.csv"
        if not path.is_file():
            raise PriceSourceError(symbol, f"no file {path.name} in {self.folder}")
        try:
            points = load_prices(path)
        except PriceFileError as error:
            raise PriceSourceError(symbol, str(error)) from error
        return [point for point in points if since <= point.day <= until]


class TiingoEod:
    """Tiingo's end-of-day prices, one request per symbol, with the owner's own token."""

    name = "tiingo"

    def __init__(self, api_key: str, base_url: str = TIINGO_BASE_URL) -> None:
        if not api_key:
            raise ValueError("TiingoEod needs an API key (TIINGO_API_KEY)")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def closes(self, symbol: str, since: date, until: date) -> list[PricePoint]:
        url = f"{self.base_url}/tiingo/daily/{symbol}/prices"
        params = {"startDate": since.isoformat(), "endDate": until.isoformat(), "format": "json"}
        # The token travels in the header, never in the URL, so no log that keeps URLs has it.
        headers = {"Authorization": f"Token {self.api_key}", "Content-Type": "application/json"}
        try:
            with httpx.Client(transport=transport, timeout=REQUEST_TIMEOUT_SECONDS) as http:
                response = http.get(url, params=params, headers=headers)
        except httpx.HTTPError as error:
            raise PriceSourceError(symbol, f"request failed: {type(error).__name__}") from error
        if response.status_code == 429:
            raise PriceSourceError(
                symbol,
                "Tiingo answered 429: the hourly or daily request limit is reached",
                retry_later=True,
            )
        if response.status_code != 200:
            # The first 200 characters of the body name the reason (an unknown ticker, a bad
            # token). The body is the vendor's; the key is never in it.
            raise PriceSourceError(
                symbol, f"Tiingo answered {response.status_code}: {response.text[:200]}"
            )
        return parse_tiingo(symbol, response.text)


def parse_tiingo(symbol: str, text: str) -> list[PricePoint]:
    """A JSON list of days to `PricePoint`s, decoded with `parse_float=Decimal` so that a close
    written as 101.23 becomes the Decimal 101.23 and never the float 101.23000000000000398."""
    try:
        body: object = json.loads(text, parse_float=Decimal)
    except json.JSONDecodeError as error:
        raise PriceSourceError(symbol, f"not JSON: {error.msg}") from error
    if not isinstance(body, list):
        raise PriceSourceError(symbol, "expected a list of days")
    points: list[PricePoint] = []
    for item in cast(list[object], body):
        if not isinstance(item, dict):
            raise PriceSourceError(symbol, "expected an object per day")
        day_field = cast(dict[str, object], item)
        raw_day, raw_close = day_field.get("date"), day_field.get("close")
        if not isinstance(raw_day, str) or len(raw_day) < 10:
            raise PriceSourceError(symbol, f"not a date: {raw_day!r}")
        try:
            day = date.fromisoformat(raw_day[:10])
        except ValueError:
            raise PriceSourceError(symbol, f"not a date: {raw_day!r}") from None
        # `bool` is an `int` in Python; `true` is not a price.
        if isinstance(raw_close, bool) or not isinstance(raw_close, Decimal | int):
            raise PriceSourceError(symbol, f"close is not a number: {raw_close!r}")
        close = Decimal(raw_close)
        if close <= 0:
            raise PriceSourceError(symbol, f"close must be positive, got {close}")
        points.append(PricePoint(day=day, close=close))
    return sorted(points, key=lambda point: point.day)


def source_from_settings() -> PriceSource:
    """Tiingo when the owner set a key; otherwise the CSV folder, which is what a laptop and a
    learner's copy have."""
    if settings.TIINGO_API_KEY:
        return TiingoEod(settings.TIINGO_API_KEY)
    return CsvPrices(Path(settings.PRICES_CSV_DIR))
