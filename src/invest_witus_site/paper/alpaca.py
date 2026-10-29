"""Alpaca's paper Trading API over httpx: the account, the positions, the market clock, one kind
of order (a notional market buy) and reading an order back.

Read from Alpaca's own pages on October 29, 2026 (the decisions log, row 94, has every URL):

- Paper and live are two hosts, `https://paper-api.alpaca.markets` and `https://api.alpaca.markets`,
  with "separate API domains and separate credentials". This client is built for the paper host
  and refuses any other, so a paper key can never be sent to the live host.
- The key pair travels as two headers, `APCA-API-KEY-ID` and `APCA-API-SECRET-KEY`.
- `POST /v2/orders` takes `symbol`, `side`, `type`, `time_in_force`, and either `qty` or
  `notional` ("dollar amount to trade. Cannot work with `qty`. Can only work for market order
  types and day for time in force"), plus `client_order_id` ("A unique identifier for the order",
  at most 128 characters). A duplicate is refused with 422 "client_order_id must be unique".
- A day order "If submitted after the close, it is queued and submitted the following trading
  day."
- `GET /v2/orders/{order_id}` and `GET /v2/orders:by_client_order_id?client_order_id=` read an
  order back; `GET /v2/account` has `cash`, `buying_power`, `equity`; `GET /v2/clock` has
  `timestamp`, `is_open`, `next_open`, `next_close`; `GET /v2/positions` has `qty`,
  `current_price`, `lastday_price`, `market_value`.
- Errors carry a JSON body with a `message` (and usually a numeric `code`): 403 "insufficient
  buying power", 422 "notional must be >= 1.00", 401 "unauthorized".

Numbers arrive as strings ("100000") or JSON numbers; both become `Decimal`, never `float`.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import cast
from urllib.parse import urlsplit

import httpx
from django.conf import settings

# The seam the tests use, as in chapters 07 and 08: a `MockTransport` here and nothing leaves the
# process. It is never set outside a test.
transport: httpx.BaseTransport | None = None

PAPER_HOST = "paper-api.alpaca.markets"
PAPER_BASE_URL = f"https://{PAPER_HOST}"
LIVE_HOST = "api.alpaca.markets"
REQUEST_TIMEOUT_SECONDS = 15.0
# How much of a vendor's message a page or a log line repeats.
MESSAGE_LIMIT = 200


class AlpacaError(Exception):
    """Anything Alpaca or the network refused. `message` is safe to show the owner: it is the
    vendor's own words or a sentence of ours, and never carries a key."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


class AlpacaNotConfigured(AlpacaError):
    """The keys are not set on this server, so no request was made."""


class LiveHostRefused(AlpacaError):
    """Something asked this client to talk to a host other than the paper host."""


class AlpacaUnavailable(AlpacaError):
    """No answer: a timeout, a dropped connection, a 5xx, or a body that is not JSON."""


class AlpacaRateLimited(AlpacaError):
    """429: too many requests; try again later."""


class AlpacaRefused(AlpacaError):
    """A 4xx with Alpaca's reason: a bad key, not enough buying power, a duplicate id."""


class AlpacaNotFound(AlpacaRefused):
    """404: no such order."""


@dataclass(frozen=True, slots=True)
class PaperAccount:
    cash: Decimal
    buying_power: Decimal
    equity: Decimal
    status: str
    trading_blocked: bool


@dataclass(frozen=True, slots=True)
class PaperPosition:
    symbol: str
    qty: Decimal
    avg_entry_price: Decimal | None
    current_price: Decimal | None
    lastday_price: Decimal | None
    market_value: Decimal | None


@dataclass(frozen=True, slots=True)
class MarketClock:
    timestamp: datetime
    is_open: bool
    next_open: datetime
    next_close: datetime


@dataclass(frozen=True, slots=True)
class PaperOrderState:
    """One order as Alpaca reports it. `notional` is set for a dollar order and `qty` for a share
    order, never both; `filled_qty` is "0" until something fills."""

    id: str
    client_order_id: str
    symbol: str
    status: str
    notional: Decimal | None
    qty: Decimal | None
    filled_qty: Decimal
    filled_avg_price: Decimal | None
    submitted_at: datetime | None
    filled_at: datetime | None


def check_host(base_url: str) -> str:
    """The base URL, if it is the paper host over https; otherwise a refusal. The live host gets
    its own words: live trading needs the checklist and separate keys, and is not built."""
    parts = urlsplit(base_url)
    if parts.hostname == LIVE_HOST:
        raise LiveHostRefused(
            f"{base_url} is Alpaca's live host. This app trades on paper only; live trading "
            "needs the checklist in a later chapter and separate keys."
        )
    if parts.scheme != "https" or parts.hostname != PAPER_HOST:
        raise LiveHostRefused(f"{base_url} is not {PAPER_BASE_URL}, the only host this app calls.")
    return PAPER_BASE_URL


class AlpacaPaper:
    """The paper Trading API with one key pair. Every call has a timeout, and every failure is one
    of the exceptions above, never an `httpx` error or a `KeyError` that would become a 500."""

    def __init__(self, key_id: str, secret_key: str, base_url: str = PAPER_BASE_URL) -> None:
        self.base_url = check_host(base_url)
        if not key_id or not secret_key:
            raise AlpacaNotConfigured(
                "Alpaca paper keys are not set (ALPACA_PAPER_KEY_ID, ALPACA_PAPER_SECRET_KEY)."
            )
        self._headers = {"APCA-API-KEY-ID": key_id, "APCA-API-SECRET-KEY": secret_key}

    def __repr__(self) -> str:
        # The default repr would print the headers, keys included, into any traceback.
        return f"AlpacaPaper({self.base_url!r})"

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
        body: dict[str, str] | None = None,
    ) -> object:
        try:
            with httpx.Client(
                base_url=self.base_url, transport=transport, timeout=REQUEST_TIMEOUT_SECONDS
            ) as http:
                response = http.request(
                    method, path, params=params, json=body, headers=self._headers
                )
        except httpx.TimeoutException as error:
            raise AlpacaUnavailable(
                f"Alpaca did not answer in time ({type(error).__name__})."
            ) from None
        except httpx.HTTPError as error:
            raise AlpacaUnavailable(f"Could not reach Alpaca ({type(error).__name__}).") from None
        if response.status_code >= 400:
            raise refusal(response)
        try:
            return cast(object, json.loads(response.text, parse_float=Decimal))
        except json.JSONDecodeError:
            raise AlpacaUnavailable(
                f"Alpaca answered {response.status_code} with a body that is not JSON."
            ) from None

    def account(self) -> PaperAccount:
        data = as_object(self._request("GET", "/v2/account"), "account")
        return PaperAccount(
            cash=number(data, "cash"),
            buying_power=number(data, "buying_power"),
            equity=number(data, "equity"),
            status=text(data, "status"),
            trading_blocked=data.get("trading_blocked") is True,
        )

    def positions(self) -> list[PaperPosition]:
        body = self._request("GET", "/v2/positions")
        if not isinstance(body, list):
            raise AlpacaUnavailable("Alpaca's positions were not a list.")
        positions: list[PaperPosition] = []
        for item in cast(list[object], body):
            data = as_object(item, "position")
            positions.append(
                PaperPosition(
                    symbol=text(data, "symbol"),
                    qty=number(data, "qty"),
                    avg_entry_price=optional_number(data, "avg_entry_price"),
                    current_price=optional_number(data, "current_price"),
                    lastday_price=optional_number(data, "lastday_price"),
                    market_value=optional_number(data, "market_value"),
                )
            )
        return sorted(positions, key=lambda position: position.symbol)

    def clock(self) -> MarketClock:
        data = as_object(self._request("GET", "/v2/clock"), "clock")
        is_open = data.get("is_open")
        if not isinstance(is_open, bool):
            raise AlpacaUnavailable("Alpaca's clock had no is_open.")
        return MarketClock(
            timestamp=moment(data, "timestamp"),
            is_open=is_open,
            next_open=moment(data, "next_open"),
            next_close=moment(data, "next_close"),
        )

    def buy_notional(self, symbol: str, notional: Decimal, client_order_id: str) -> PaperOrderState:
        """A market buy for a dollar amount, good for the day: the only order this chapter
        places. Alpaca allows notional only with `market` and `day`, so neither is a choice."""
        body = {
            "symbol": symbol,
            "side": "buy",
            "type": "market",
            "time_in_force": "day",
            "notional": f"{notional:.2f}",
            "client_order_id": client_order_id,
        }
        return order_state(self._request("POST", "/v2/orders", body=body))

    def order(self, order_id: str) -> PaperOrderState:
        return order_state(self._request("GET", f"/v2/orders/{order_id}"))

    def order_by_client_id(self, client_order_id: str) -> PaperOrderState:
        params = {"client_order_id": client_order_id}
        return order_state(self._request("GET", "/v2/orders:by_client_order_id", params=params))


def paper_client() -> AlpacaPaper:
    """The client with the owner's keys from settings. The host is never a setting."""
    return AlpacaPaper(settings.ALPACA_PAPER_KEY_ID, settings.ALPACA_PAPER_SECRET_KEY)


def keys_configured() -> bool:
    return bool(settings.ALPACA_PAPER_KEY_ID and settings.ALPACA_PAPER_SECRET_KEY)


def refusal(response: httpx.Response) -> AlpacaError:
    """A 4xx or 5xx as one of our exceptions, with Alpaca's `message` when the body has one."""
    reason = ""
    try:
        body: object = json.loads(response.text)
    except json.JSONDecodeError:
        body = None
    if isinstance(body, dict):
        found = cast(dict[str, object], body).get("message")
        if isinstance(found, str):
            reason = found
    reason = (reason or response.reason_phrase or "no reason given")[:MESSAGE_LIMIT]
    status = response.status_code
    message = f"Alpaca answered {status}: {reason}"
    if status == 404:
        return AlpacaNotFound(message, status)
    if status == 429:
        return AlpacaRateLimited(message, status)
    if status >= 500:
        return AlpacaUnavailable(message, status)
    return AlpacaRefused(message, status)


# --- Reading Alpaca's JSON at the boundary: every field checked, every number a Decimal ---------


def as_object(body: object, what: str) -> dict[str, object]:
    if not isinstance(body, dict):
        raise AlpacaUnavailable(f"Alpaca's {what} was not an object.")
    return cast(dict[str, object], body)


def text(data: dict[str, object], name: str) -> str:
    value = data.get(name)
    if not isinstance(value, str):
        raise AlpacaUnavailable(f"Alpaca's answer had no {name}.")
    return value


def optional_number(data: dict[str, object], name: str) -> Decimal | None:
    """A string such as "101.5" or a JSON number, as a Decimal; `None` when absent or null.
    `bool` is refused: `true` is an `int` in Python, and not a price."""
    value = data.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, str | int | Decimal):
        raise AlpacaUnavailable(f"Alpaca's {name} is not a number: {value!r}")
    try:
        return Decimal(value)
    except InvalidOperation:
        raise AlpacaUnavailable(f"Alpaca's {name} is not a number: {value!r}") from None


def number(data: dict[str, object], name: str) -> Decimal:
    value = optional_number(data, name)
    if value is None:
        raise AlpacaUnavailable(f"Alpaca's answer had no {name}.")
    return value


def optional_moment(data: dict[str, object], name: str) -> datetime | None:
    """An RFC 3339 timestamp such as "2026-11-03T09:30:00-05:00" or "...Z", or `None`."""
    value = data.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise AlpacaUnavailable(f"Alpaca's {name} is not a timestamp: {value!r}")
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise AlpacaUnavailable(f"Alpaca's {name} is not a timestamp: {value!r}") from None


def moment(data: dict[str, object], name: str) -> datetime:
    value = optional_moment(data, name)
    if value is None:
        raise AlpacaUnavailable(f"Alpaca's answer had no {name}.")
    return value


def order_state(body: object) -> PaperOrderState:
    data = as_object(body, "order")
    return PaperOrderState(
        id=text(data, "id"),
        client_order_id=text(data, "client_order_id"),
        symbol=text(data, "symbol"),
        status=text(data, "status"),
        notional=optional_number(data, "notional"),
        qty=optional_number(data, "qty"),
        filled_qty=optional_number(data, "filled_qty") or Decimal("0"),
        filled_avg_price=optional_number(data, "filled_avg_price"),
        submitted_at=optional_moment(data, "submitted_at"),
        filled_at=optional_moment(data, "filled_at"),
    )
