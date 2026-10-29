# Chapter 11: Alpaca paper trading and the monthly review

**Starts from:** tag `v10`. **Ends at:** tag `v11`.
**Written against:** Python 3.14.10, uv 0.13.6, Django 5.2.18, httpx 0.28.1, and Alpaca's documentation pages as
read on October 29, 2026.
**Goal:** the method page places the month's buys. On an account linked to Alpaca's paper environment, the
method page shows "This month's buys", computed from the plan, with the practice budget the app keeps beside
it, and a Confirm button. One click sends one market order per symbol for the dollar amount to Alpaca paper,
with an order id built from the account, the plan, the month and the symbol, so a second click or a retry never
buys twice, and writes each order into the journal. A closed market is said in words and the order is queued for
the open. A nightly step reads the orders back and fills in the shares. The client talks to the paper host only
and refuses the live one; every Alpaca failure is a message on the page, never a 500; only the site owner sees
any of it.
**Time:** 5 to 6 hours for the code and tests. Your own Alpaca paper keys and a first order take 20 minutes.

The listings in this chapter are not typed in by hand. `scripts/render_chapter.py` pastes the real files from
tag `v11` into the chapter text, so what you read and what the tests run are the same bytes.

## What you will learn

- **A broker client written out:** httpx, two headers, a timeout on every call, and a short list of exceptions
  that say what went wrong in the vendor's own words, so a page can print them and nothing becomes a 500.
- **Refusing a host:** a client that can only be built for one URL, and settings that refuse to start when the
  environment points at another.
- **Idempotency you can test:** an id made from the facts of the order, a unique column, a row lock, and the
  vendor's own duplicate refusal, which together make "click twice" and "retry after a timeout" the same order.
- **A transaction around a network call,** and why the error is raised after the block rather than inside it.
- **Constraints with their own words:** `violation_error_message` on a `CheckConstraint` and on a partial
  `UniqueConstraint`, so the admin says why a row is refused.
- **A fake vendor:** a class that answers the routes the app calls, behind httpx's `MockTransport`, so the whole
  confirm, retry and sync story runs in the test suite with no network and no keys.
- **Reading money at the boundary:** strings and JSON numbers from a vendor turned into `Decimal`, `true`
  refused as a number, timestamps parsed with their offsets.

## Before the code: what the PRD asks, what Alpaca's pages say, and eight decisions

**What the PRD asks.** Section 7.7: paper by default, with the paper host printed beside the environment;
orders the rules produce are staged and placed only when the user confirms; the app keeps its own practice
budget per plan, refuses orders beyond what is left, and ignores Alpaca's balance; Alpaca's paper limits are
stated wherever paper results appear; live trading stays behind a checklist with separate keys. Acceptance: a
paper key can never be sent to the live host, and a test asserts it; keys are read on the server only, never
rendered, logged or committed; the daily job copies orders and fills into the app. Research 05 adds the reason
for the budget: Alpaca's paper account starts at a default balance that cannot be set, so the app keeps the
number.

**What Alpaca's pages say (read October 29, 2026).** The paper and live Trading APIs are two hosts,
`https://paper-api.alpaca.markets` and `https://api.alpaca.markets`, and "Paper and live trading use separate
API domains and separate credentials" (Alpaca, 2026b). The key pair travels as the headers `APCA-API-KEY-ID`
and `APCA-API-SECRET-KEY` (Alpaca, 2026b). An order is `POST /v2/orders`; `notional` is the "dollar amount to
trade. Cannot work with `qty`. Can only work for market order types and day for time in force", and
`client_order_id` is "A unique identifier for the order", at most 128 characters (Alpaca, n.d.-d). A day order
"If submitted after the close, it is queued and submitted the following trading day" (Alpaca, n.d.-e). Alpaca
refuses a repeated id with 422 "client_order_id must be unique", and a short account with 403 "insufficient
buying power" (Alpaca, 2026a). `GET /v2/orders/{order_id}` and `GET /v2/orders:by_client_order_id` read an
order back (Alpaca, n.d.-b, n.d.-c); `GET /v2/account` has `cash`, `buying_power` and `equity` (Alpaca,
n.d.-a); `GET /v2/clock` has `is_open` and `next_open` (Alpaca, n.d.-f). On paper, orders "will receive partial
fills for a random size 10% of the time", and dividends, slippage, market impact and regulatory fees are not
simulated (Alpaca, n.d.-g). Two things no page read that day said: a per-minute limit for the Trading API, and
whether an id may be reused once its order is final. The code assumes neither. Decisions log, row 94, has
every URL with its date.

**Decision 1: a `paper` app, a client written out, no pydantic and no `Protocol`.** The roadmap proposed a
broker client behind a `Protocol` with pydantic models at the boundary. The boundary is five small objects, and
chapter 08's Tiingo parser already showed how to read them: check each field, make every number a `Decimal`,
turn anything missing into one exception. A `Protocol` would have one implementation, and the tests replace the
network, not the class, through the same `transport` seam chapters 07 and 08 used. Decisions log, row 95.

**Decision 2: the host is a constant, and the live host is refused twice.** `check_host` accepts
`https://paper-api.alpaca.markets` and nothing else; for `api.alpaca.markets` the refusal says "live host". There
is no base-URL setting to get wrong. Alpaca's own tools read `APCA_API_BASE_URL`; this app does not, but if that
variable names any other host the settings refuse to start, because someone expected live trading here. Row 95.

**Decision 3: one field links an account, one owner holds the keys.** `Account.alpaca` is "" or `paper`; there
is no live choice. A `CheckConstraint` allows it on a paper account only and a partial `UniqueConstraint` allows
one per owner, because the server holds one pair of keys. On top of chapter 08's ownership query, every Alpaca
route requires a superuser: the keys are the site owner's, and a learner who somehow owned a linked row still
gets a 404. Row 96.

**Decision 4: the practice budget is the plan's, and spent comes from the journal.**
`MethodPlan.practice_budget` is optional, set on the start form or in the admin. Spent is every buy in the
account's journal since the plan started, placed or logged by hand; a pending order counts the moment it is
placed. Alpaca's cash is shown beside it and is not the plan's. Row 97.

**Decision 5: this month's buys, and Confirm for a one-symbol plan.** The amount is split across the plan's
symbols to the cent, with the left-over cents going one each to the first symbols, so the parts always add up.
Chapter 03's rules count one buy of the plan's amount each month, so two split orders would be two findings the
app caused itself; Confirm is offered for a one-symbol plan, and a two-symbol plan shows the split and says why.
Confirm is also refused, in a sentence, before the plan starts, after this month's window, when a buy for the
month is already logged by hand, with no budget, and over the budget, and every check runs again on the server
when the button is pressed. The box sits above the view switch, on all three views, so no view hides it.
Row 98.

**Decision 6: placed once.** The id is `iw-<account>-<plan>-<YYYY-MM>-<symbol>`. The table's column is
unique; the row is created or found and locked inside a transaction; a row that already existed without
Alpaca's id means an earlier try may have reached Alpaca, so Alpaca is asked for that id before anything is
sent; and Alpaca's 422 for a repeated id means the order exists, so it is read back. A refusal is stored on the
row and committed, and the next Confirm retries it. Row 99.

**Decision 7: the journal entry is written at Confirm and corrected by the sync.** One entry per order,
dated the day you confirmed (the window rule is about what you did; the fill's day goes in the note), for the
notional, shares empty until the order is final. A full fill keeps the notional and gets the shares; an order
that ended part filled is booked at shares times the average price; an order that ended with nothing filled was
never a trade, so its entry is removed and the order row keeps the history. When the market is closed the box
says so, the button reads "Confirm: queue for the open", and the order is the same day order Alpaca queues.
Row 100.

**Decision 8: the sync runs three ways, and chapter 08's cron keeps its shape.** `manage.py
sync_paper_orders`, a "Check orders now" button on the paper page, and a step in chapter 08's cron route after
the pull. The cron step runs only when both keys are set and adds an `orders` object to the JSON; without keys
the body is chapter 08's exactly, and `vercel.json` keeps its one cron. A 429 stops the run; any other refusal
is recorded for that order and the rest go on. Row 101.

## Steps

### 11.1 The tests

Listing 11-1, Filename: `tests/test_ch11.py`:

```python
"""Chapter 11 checkpoint: Alpaca paper trading and the monthly review's buys. A client fixed to the
paper host that refuses the live one, sends the keys as headers and turns every vendor failure
into a typed error with Alpaca's words; this month's buys staged from the plan, the practice
budget, and a Confirm that places each buy once (a deterministic `client_order_id`, a second
click, a retry, a duplicate refused by Alpaca); the closed market and its queue for the open; the
nightly sync that fills in the journal; the owner's paper page; and public pages that still show
no table and no account link. Every Alpaca answer comes from `FakeAlpaca` through httpx's
`MockTransport`: no request leaves the process, and the keys are made up."""

import importlib
import json
import os
import sys
from datetime import date
from decimal import Decimal
from html import unescape
from io import StringIO
from pathlib import Path
from types import ModuleType
from typing import Any, Protocol

import httpx
import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client
from pytest_django.fixtures import Settings

from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.models import JournalEntry, MethodPlan
from invest_witus_site.paper import alpaca, orders
from invest_witus_site.paper.alpaca import (
    PAPER_HOST,
    AlpacaNotConfigured,
    AlpacaNotFound,
    AlpacaPaper,
    AlpacaRateLimited,
    AlpacaRefused,
    AlpacaUnavailable,
    LiveHostRefused,
)
from invest_witus_site.paper.models import PaperOrder, client_order_id
from invest_witus_site.paper.orders import split_amount

D = Decimal
BASE_DIR = Path(__file__).resolve().parent.parent
# Made up, and shaped like nothing real. A test asserts neither ever reaches a page.
KEY_ID = "TESTKEYID0000"
SECRET = "test-secret-not-a-real-key"
# Placeholder symbols only, as every chapter: INDEX and OTHER from chapter 02.
DAY = date(2026, 11, 3)  # a Tuesday, inside a seven-day window that opened on November 1
PUBLIC_PATHS = [
    "/",
    "/faq/",
    "/privacy/",
    "/terms/",
    "/contact/",
    "/waitlist/",
    "/waitlist/thanks/",
    "/auth/witus/login/",
]
LIVE_LINE = "Paper money. Live trading needs the checklist in a later chapter and separate keys."


class FakeAlpaca:
    """The paper Trading API's routes this app calls, in memory. Orders are kept by id; a second
    order with a `client_order_id` it already has is refused with 422, as Alpaca does."""

    def __init__(self) -> None:
        self.is_open = True
        self.next_open = "2026-11-04T09:30:00-05:00"
        self.orders: dict[str, dict[str, Any]] = {}
        self.posted: list[dict[str, Any]] = []
        self.requests: list[httpx.Request] = []
        # "METHOD /path" -> (status, body): answered instead of the route, every time.
        self.fail: dict[str, tuple[int, object]] = {}

    def by_client_id(self, client_id: str) -> dict[str, Any] | None:
        return next((o for o in self.orders.values() if o["client_order_id"] == client_id), None)

    def add_order(self, client_id: str, symbol: str = "INDEX", notional: str = "100") -> str:
        order_id = f"order-{len(self.orders) + 1}"
        self.orders[order_id] = {
            "id": order_id,
            "client_order_id": client_id,
            "symbol": symbol,
            "status": "accepted",
            "notional": notional,
            "qty": None,
            "filled_qty": "0",
            "filled_avg_price": None,
            "submitted_at": "2026-11-03T15:00:00Z",
            "filled_at": None,
        }
        return order_id

    def fill(self, order_id: str, qty: str, price: str, status: str = "filled") -> None:
        self.orders[order_id].update(
            status=status,
            filled_qty=qty,
            filled_avg_price=price,
            filled_at="2026-11-04T14:30:01.123456789Z",
        )

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        failed = self.fail.get(f"{request.method} {path}")
        if failed is not None:
            status, body = failed
            if isinstance(body, str):
                return httpx.Response(status, text=body)
            return httpx.Response(status, json=body)
        if path == "/v2/clock":
            return httpx.Response(
                200,
                json={
                    "timestamp": "2026-11-03T10:15:00-05:00",
                    "is_open": self.is_open,
                    "next_open": self.next_open,
                    "next_close": "2026-11-03T16:00:00-05:00",
                },
            )
        if path == "/v2/account":
            return httpx.Response(
                200,
                json={
                    "cash": "1234.56",
                    "buying_power": "2469.12",
                    "equity": "1334.56",
                    "status": "ACTIVE",
                    "trading_blocked": False,
                },
            )
        if path == "/v2/positions":
            position = {
                "symbol": "INDEX",
                "qty": "0.5",
                "avg_entry_price": "200",
                "current_price": "201.5",
                "lastday_price": "199.25",
                "market_value": "100.75",
            }
            return httpx.Response(200, json=[position])
        if request.method == "POST" and path == "/v2/orders":
            sent: dict[str, Any] = json.loads(request.content)
            self.posted.append(sent)
            if self.by_client_id(sent["client_order_id"]) is not None:
                return httpx.Response(
                    422, json={"code": 40010001, "message": "client_order_id must be unique"}
                )
            order_id = self.add_order(sent["client_order_id"], sent["symbol"], sent["notional"])
            return httpx.Response(200, json=self.orders[order_id])
        if path == "/v2/orders:by_client_order_id":
            found = self.by_client_id(request.url.params["client_order_id"])
            if found is None:
                return httpx.Response(404, json={"code": 40410000, "message": "order not found"})
            return httpx.Response(200, json=found)
        if path.startswith("/v2/orders/"):
            found = self.orders.get(path.removeprefix("/v2/orders/"))
            if found is None:
                return httpx.Response(404, json={"code": 40410000, "message": "order not found"})
            return httpx.Response(200, json=found)
        return httpx.Response(404, json={"message": "no such route"})


# --- Fixtures ------------------------------------------------------------------------------------


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> FakeAlpaca:
    """Alpaca in memory, made-up keys in the settings, and the app's today fixed on DAY."""
    fake = FakeAlpaca()
    monkeypatch.setattr(alpaca, "transport", httpx.MockTransport(fake.handle))
    monkeypatch.setattr(orders, "today", lambda: DAY)
    settings.ALPACA_PAPER_KEY_ID = KEY_ID
    settings.ALPACA_PAPER_SECRET_KEY = SECRET
    return fake


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
    """The site owner: a superuser, as chapter 05 made one."""
    return django_user_model.objects.create_superuser("owner", "owner@example.com", "pw")


@pytest.fixture
def someone(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("someone")


@pytest.fixture
def account(owner: User) -> Account:
    return Account.objects.create(
        name="Practice", broker="Alpaca", kind="paper", alpaca="paper", owner=owner
    )


@pytest.fixture
def plan(account: Account) -> MethodPlan:
    """index-dca from November 1, 2026: 100.00 into INDEX within the first seven days, with a
    practice budget of 1,000.00."""
    return MethodPlan.objects.create(
        account=account,
        method_id="index-dca",
        amount=D("100.00"),
        buy_window_days=7,
        symbols="INDEX",
        started_on=date(2026, 11, 1),
        practice_budget=D("1000.00"),
    )


@pytest.fixture
def owner_client(client: Client, owner: User) -> Client:
    client.force_login(owner)
    return client


class Page(Protocol):
    content: bytes


def text(response: Page) -> str:
    return unescape(response.content.decode())


def method_url(account: Account) -> str:
    return f"/accounts/{account.pk}/method/"


def paper_url(account: Account, action: str = "") -> str:
    return f"/accounts/{account.pk}/paper/{action}"


def posted_orders(fake: FakeAlpaca) -> int:
    return len(fake.posted)


# --- The client ---------------------------------------------------------------------------------


def test_the_client_refuses_the_live_host_and_any_other() -> None:
    with pytest.raises(LiveHostRefused, match="live host"):
        AlpacaPaper(KEY_ID, SECRET, base_url="https://api.alpaca.markets")
    for other in ("http://paper-api.alpaca.markets", "https://example.com"):
        with pytest.raises(LiveHostRefused, match="the only host this app calls"):
            AlpacaPaper(KEY_ID, SECRET, base_url=other)
    assert AlpacaPaper(KEY_ID, SECRET).base_url == "https://paper-api.alpaca.markets"


def fresh_settings(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> ModuleType:
    """Chapter 06's helper: the settings imported again with exactly these variables."""
    for name in list(os.environ):
        if name.startswith(("DJANGO_", "VERCEL", "DATABASE_URL", "APCA_", "ALPACA_")):
            monkeypatch.delenv(name)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    # `raising=False`: after a refused import the module is not in `sys.modules` at all.
    monkeypatch.delitem(sys.modules, "invest_witus_site.settings", raising=False)
    return importlib.import_module("invest_witus_site.settings")


def test_the_settings_refuse_to_start_when_anything_points_at_the_live_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ImproperlyConfigured, match="paper only"):
        fresh_settings(
            monkeypatch, {"DJANGO_DEBUG": "1", "APCA_API_BASE_URL": "https://api.alpaca.markets"}
        )
    paper = fresh_settings(
        monkeypatch,
        {"DJANGO_DEBUG": "1", "APCA_API_BASE_URL": "https://paper-api.alpaca.markets"},
    )
    assert (paper.ALPACA_PAPER_KEY_ID, paper.ALPACA_PAPER_SECRET_KEY) == ("", "")


def test_the_client_needs_both_keys_and_never_shows_them(settings: Settings) -> None:
    settings.ALPACA_PAPER_KEY_ID = KEY_ID
    settings.ALPACA_PAPER_SECRET_KEY = ""
    with pytest.raises(AlpacaNotConfigured, match="ALPACA_PAPER_SECRET_KEY"):
        alpaca.paper_client()
    assert alpaca.keys_configured() is False
    client = AlpacaPaper(KEY_ID, SECRET)
    assert SECRET not in repr(client) and KEY_ID not in repr(client)


def test_the_client_sends_the_keys_as_headers_and_reads_numbers_as_decimals(
    fake: FakeAlpaca,
) -> None:
    client = alpaca.paper_client()
    account = client.account()
    assert (account.cash, account.buying_power, account.equity) == (
        D("1234.56"),
        D("2469.12"),
        D("1334.56"),
    )
    [position] = client.positions()
    assert (position.symbol, position.qty, position.market_value) == (
        "INDEX",
        D("0.5"),
        D("100.75"),
    )
    assert isinstance(position.current_price, Decimal)
    clock = client.clock()
    assert clock.is_open is True and clock.next_open.isoformat() == "2026-11-04T09:30:00-05:00"
    for request in fake.requests:
        assert request.url.host == PAPER_HOST
        assert request.headers["APCA-API-KEY-ID"] == KEY_ID
        assert request.headers["APCA-API-SECRET-KEY"] == SECRET
        assert SECRET not in str(request.url)


def test_a_buy_is_a_notional_market_order_good_for_the_day(fake: FakeAlpaca) -> None:
    state = alpaca.paper_client().buy_notional("INDEX", D("100.00"), "iw-1-1-2026-11-INDEX")
    assert fake.posted == [
        {
            "symbol": "INDEX",
            "side": "buy",
            "type": "market",
            "time_in_force": "day",
            "notional": "100.00",
            "client_order_id": "iw-1-1-2026-11-INDEX",
        }
    ]
    assert (state.status, state.notional, state.qty, state.filled_qty) == (
        "accepted",
        D("100"),
        None,
        D("0"),
    )


@pytest.mark.parametrize(
    ("status", "body", "error", "words"),
    [
        (401, {"message": "unauthorized"}, AlpacaRefused, "Alpaca answered 401: unauthorized"),
        (
            403,
            {"code": 40310000, "message": "insufficient buying power"},
            AlpacaRefused,
            "insufficient buying power",
        ),
        (404, {"message": "order not found"}, AlpacaNotFound, "order not found"),
        (422, {"message": "notional must be >= 1.00"}, AlpacaRefused, "notional must be >= 1.00"),
        (429, {"message": "too many requests"}, AlpacaRateLimited, "too many requests"),
        (500, "<html>oops</html>", AlpacaUnavailable, "Alpaca answered 500"),
    ],
)
def test_vendor_errors_become_typed_exceptions_with_alpacas_words(
    fake: FakeAlpaca, status: int, body: object, error: type[Exception], words: str
) -> None:
    fake.fail["GET /v2/account"] = (status, body)
    with pytest.raises(error, match=words) as raised:
        alpaca.paper_client().account()
    assert SECRET not in str(raised.value)


def test_no_answer_and_a_bad_body_are_unavailable(
    fake: FakeAlpaca, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake.fail["GET /v2/clock"] = (200, "not json")
    with pytest.raises(AlpacaUnavailable, match="not JSON"):
        alpaca.paper_client().clock()
    fake.fail["GET /v2/account"] = (200, {"cash": True})
    with pytest.raises(AlpacaUnavailable, match="cash is not a number"):
        alpaca.paper_client().account()

    def time_out(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    monkeypatch.setattr(alpaca, "transport", httpx.MockTransport(time_out))
    with pytest.raises(AlpacaUnavailable, match="did not answer in time"):
        alpaca.paper_client().positions()
    assert alpaca.REQUEST_TIMEOUT_SECONDS > 0


# --- Staging this month's buys -------------------------------------------------------------------


def test_the_client_order_id_is_the_same_for_the_same_buy_and_short() -> None:
    first = client_order_id(12, 3, "2026-11", "INDEX")
    assert first == client_order_id(12, 3, "2026-11", "INDEX") == "iw-12-3-2026-11-INDEX"
    others = {
        client_order_id(13, 3, "2026-11", "INDEX"),
        client_order_id(12, 4, "2026-11", "INDEX"),
        client_order_id(12, 3, "2026-12", "INDEX"),
        client_order_id(12, 3, "2026-11", "OTHER"),
    }
    assert first not in others and len(others) == 4
    assert len(client_order_id(10**9, 10**9, "2026-11", "A" * 12)) <= 128


def test_the_amount_splits_across_symbols_to_the_cent() -> None:
    assert split_amount(D("100"), ["INDEX"]) == [("INDEX", D("100.00"))]
    assert split_amount(D("100.00"), ["INDEX", "OTHER", "THIRD"]) == [
        ("INDEX", D("33.34")),
        ("OTHER", D("33.33")),
        ("THIRD", D("33.33")),
    ]
    parts = split_amount(D("250.01"), ["INDEX", "OTHER"])
    assert sum(amount for _, amount in parts) == D("250.01")
    with pytest.raises(ValueError, match="no symbols"):
        split_amount(D("1"), [])


@pytest.mark.django_db
def test_this_months_buys_come_from_the_plan_with_the_budget(plan: MethodPlan) -> None:
    stage = orders.month_buys(plan, DAY)
    assert (stage.month, stage.window_closes, stage.total) == (
        "2026-11",
        date(2026, 11, 7),
        D("100.00"),
    )
    [buy] = stage.buys
    assert (buy.symbol, buy.notional, buy.placed) == ("INDEX", D("100.00"), False)
    assert buy.client_order_id == f"iw-{plan.account.pk}-{plan.pk}-2026-11-INDEX"
    assert (stage.budget, stage.spent, stage.left) == (D("1000.00"), D("0"), D("1000.00"))
    assert stage.refusal == "" and stage.can_confirm


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("change", "day", "words"),
    [
        ({}, date(2026, 11, 10), "This month's window closed on 2026-11-07"),
        ({}, date(2026, 10, 30), "The plan starts on 2026-11-01"),
        ({"practice_budget": None}, DAY, "Set a practice budget"),
        ({"practice_budget": D("50.00")}, DAY, "more than the practice budget left, 50.00"),
        ({"symbols": "INDEX OTHER"}, DAY, "The plan names 2 symbols"),
    ],
)
def test_confirm_is_refused_in_words_outside_the_rules(
    plan: MethodPlan, change: dict[str, Any], day: date, words: str
) -> None:
    for name, value in change.items():
        setattr(plan, name, value)
    plan.save()
    stage = orders.month_buys(plan, day)
    assert words in stage.refusal and not stage.can_confirm


@pytest.mark.django_db
def test_a_buy_logged_by_hand_this_month_stops_confirm(plan: MethodPlan) -> None:
    JournalEntry.objects.create(
        account=plan.account, date=date(2026, 11, 2), action="buy", symbol="INDEX", amount=D("100")
    )
    stage = orders.month_buys(plan, DAY)
    assert stage.refusal == "A buy for 2026-11 is already in the journal, logged by hand."
    assert stage.spent == D("100.00")


@pytest.mark.django_db
def test_a_two_symbol_plan_shows_the_split_without_a_confirm_button(
    fake: FakeAlpaca, owner_client: Client, plan: MethodPlan
) -> None:
    plan.symbols = "INDEX OTHER"
    plan.save()
    html = text(owner_client.get(method_url(plan.account)))
    assert "Buy 50.00 of INDEX" in html and "Buy 50.00 of OTHER" in html
    assert "The plan names 2 symbols" in html
    assert "Confirm" not in html


# --- Confirm ------------------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_method_page_shows_this_months_buys_and_confirm(
    fake: FakeAlpaca, owner_client: Client, plan: MethodPlan
) -> None:
    html = text(owner_client.get(method_url(plan.account)))
    assert "This month's buys" in html
    assert "Buy 100.00 of INDEX" in html
    assert "Practice budget, the app's own number: 1000.00, spent 0.00, left 1000.00." in html
    assert f"Alpaca paper ({PAPER_HOST}). {LIVE_LINE}" in html
    assert '<button type="submit">Confirm</button>' in html
    assert SECRET not in html and KEY_ID not in html


@pytest.mark.django_db
def test_confirm_places_each_buy_once_and_writes_one_journal_entry(
    fake: FakeAlpaca, owner_client: Client, plan: MethodPlan
) -> None:
    account = plan.account
    first = owner_client.post(paper_url(account, "confirm/"), follow=True)
    assert first.redirect_chain == [(method_url(account), 302)]
    assert "Placed: buy 100.00 of INDEX, accepted." in text(first)
    again = owner_client.post(paper_url(account, "confirm/"), follow=True)
    assert posted_orders(fake) == 1, "a second click sends nothing"
    assert "This month's buys are placed." in text(again)
    [order] = PaperOrder.objects.all()
    assert (order.client_order_id, order.alpaca_id, order.status) == (
        f"iw-{account.pk}-{plan.pk}-2026-11-INDEX",
        "order-1",
        "accepted",
    )
    [entry] = JournalEntry.objects.filter(account=account)
    assert order.journal_entry == entry
    assert (entry.date, entry.action, entry.symbol, entry.amount, entry.shares) == (
        DAY,
        "buy",
        "INDEX",
        D("100.00"),
        None,
    )
    assert entry.note == "Alpaca paper order order-1: accepted"
    assert orders.month_buys(plan, DAY).spent == D("100.00")


@pytest.mark.django_db
def test_a_retry_finds_the_order_alpaca_already_has(fake: FakeAlpaca, plan: MethodPlan) -> None:
    """An earlier try reached Alpaca and then failed before saving its answer: the row exists with
    no Alpaca id. Confirm asks Alpaca for the id first and adopts the order; nothing is sent."""
    cid = client_order_id(plan.account.pk, plan.pk, "2026-11", "INDEX")
    PaperOrder.objects.create(
        account=plan.account,
        plan=plan,
        month="2026-11",
        symbol="INDEX",
        notional=D("100"),
        client_order_id=cid,
    )
    fake.add_order(cid)
    result = orders.confirm(plan, DAY, alpaca.paper_client())
    assert posted_orders(fake) == 0
    assert [order.alpaca_id for order in result.placed] == ["order-1"]
    assert JournalEntry.objects.count() == 1


@pytest.mark.django_db
def test_alpacas_duplicate_refusal_reads_the_order_back(fake: FakeAlpaca, plan: MethodPlan) -> None:
    """Two requests at once: Alpaca took the other one's order. The 422 means "it exists"."""
    fake.add_order(client_order_id(plan.account.pk, plan.pk, "2026-11", "INDEX"))
    result = orders.confirm(plan, DAY, alpaca.paper_client())
    assert posted_orders(fake) == 1 and len(fake.orders) == 1
    assert [order.alpaca_id for order in result.placed] == ["order-1"]
    assert result.failed == []


@pytest.mark.django_db
def test_a_closed_market_is_said_and_the_order_queues_for_the_open(
    fake: FakeAlpaca, owner_client: Client, plan: MethodPlan
) -> None:
    fake.is_open = False
    html = text(owner_client.get(method_url(plan.account)))
    assert (
        "The market is closed. Alpaca queues a day order placed now for the next open, "
        "2026-11-04 14:30 UTC." in html
    )
    assert "Confirm: queue for the open" in html
    assert "after this month's window closes" not in html
    response = owner_client.post(paper_url(plan.account, "confirm/"), follow=True)
    assert fake.posted[0]["time_in_force"] == "day"
    assert "queues a day order for the next open, 2026-11-04 14:30 UTC." in text(response)


@pytest.mark.django_db
def test_a_queue_past_the_window_is_said(
    fake: FakeAlpaca, owner_client: Client, plan: MethodPlan, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(orders, "today", lambda: date(2026, 11, 7))
    fake.is_open = False
    fake.next_open = "2026-11-09T09:30:00-05:00"
    html = text(owner_client.get(method_url(plan.account)))
    assert "That open is after this month's window closes on 2026-11-07" in html


@pytest.mark.django_db
def test_a_vendor_refusal_is_a_message_and_buys_nothing(
    fake: FakeAlpaca, owner_client: Client, plan: MethodPlan
) -> None:
    fake.fail["POST /v2/orders"] = (403, {"code": 40310000, "message": "insufficient buying power"})
    response = owner_client.post(paper_url(plan.account, "confirm/"), follow=True)
    assert response.status_code == 200
    html = text(response)
    assert "Not placed: INDEX. Alpaca answered 403: insufficient buying power" in html
    assert JournalEntry.objects.count() == 0
    [order] = PaperOrder.objects.all()
    assert (order.status, order.placed) == ("staged", False)
    assert "Buy 100.00 of INDEX: not placed. Alpaca answered 403" in html
    del fake.fail["POST /v2/orders"]
    owner_client.post(paper_url(plan.account, "confirm/"))
    assert PaperOrder.objects.get().placed and JournalEntry.objects.count() == 1


@pytest.mark.django_db
def test_no_clock_means_no_confirm_button_and_nothing_placed(
    fake: FakeAlpaca, owner_client: Client, plan: MethodPlan
) -> None:
    fake.fail["GET /v2/clock"] = (503, {"message": "service unavailable"})
    html = text(owner_client.get(method_url(plan.account)))
    assert "Alpaca did not answer, so nothing can be placed now." in html
    assert "Confirm" not in html
    response = owner_client.post(paper_url(plan.account, "confirm/"), follow=True)
    assert "Nothing was placed. Alpaca answered 503: service unavailable" in text(response)
    assert posted_orders(fake) == 0 and PaperOrder.objects.count() == 0


@pytest.mark.django_db
def test_confirm_checks_the_rules_again_on_the_server(
    fake: FakeAlpaca, owner_client: Client, plan: MethodPlan, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(orders, "today", lambda: date(2026, 11, 20))
    response = owner_client.post(paper_url(plan.account, "confirm/"), follow=True)
    assert "This month's window closed on 2026-11-07" in text(response)
    assert fake.requests == [] or all(r.url.path == "/v2/clock" for r in fake.requests)
    assert posted_orders(fake) == 0


# --- The sync -----------------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_sync_fills_a_pending_order_and_fixes_its_journal_entry(
    fake: FakeAlpaca, plan: MethodPlan
) -> None:
    orders.confirm(plan, DAY, alpaca.paper_client())
    fake.fill("order-1", qty="0.496277915", price="201.5")
    out = StringIO()
    call_command("sync_paper_orders", stdout=out)
    assert out.getvalue().strip() == (
        "Checked 1, changed 1: 1 filled, 0 ended part filled, 0 ended unfilled, 0 still open."
    )
    order = PaperOrder.objects.get()
    assert (order.status, order.filled_qty, order.filled_avg_price) == (
        "filled",
        D("0.496277915"),
        D("201.5"),
    )
    entry = JournalEntry.objects.get()
    assert (entry.amount, entry.shares, entry.date) == (D("100.00"), D("0.496277"), DAY)
    assert (
        entry.note == "Alpaca paper order order-1: filled, 0.496277 shares at 201.5 on 2026-11-04"
    )
    again = StringIO()
    call_command("sync_paper_orders", stdout=again)
    assert again.getvalue().startswith("Checked 0, changed 0")


@pytest.mark.django_db
def test_an_order_that_ends_unfilled_leaves_no_journal_entry(
    fake: FakeAlpaca, plan: MethodPlan
) -> None:
    orders.confirm(plan, DAY, alpaca.paper_client())
    fake.orders["order-1"]["status"] = "canceled"
    result = orders.sync_orders(alpaca.paper_client())
    assert (result.changed, result.ended_unfilled) == (1, 1)
    assert JournalEntry.objects.count() == 0
    assert PaperOrder.objects.get().status == "canceled", "the row keeps the history"


@pytest.mark.django_db
def test_an_order_that_ends_part_filled_books_what_was_bought(
    fake: FakeAlpaca, plan: MethodPlan
) -> None:
    orders.confirm(plan, DAY, alpaca.paper_client())
    fake.fill("order-1", qty="0.25", price="200", status="partially_filled")
    first = orders.sync_orders(alpaca.paper_client())
    assert (first.still_open, JournalEntry.objects.get().shares) == (1, None)
    fake.orders["order-1"]["status"] = "expired"
    second = orders.sync_orders(alpaca.paper_client())
    assert second.ended_part_filled == 1
    entry = JournalEntry.objects.get()
    assert (entry.amount, entry.shares) == (D("50.00"), D("0.25"))


@pytest.mark.django_db
def test_the_sync_records_a_refusal_and_goes_on(fake: FakeAlpaca, plan: MethodPlan) -> None:
    orders.confirm(plan, DAY, alpaca.paper_client())
    fake.fail["GET /v2/orders/order-1"] = (404, {"message": "order not found"})
    result = orders.sync_orders(alpaca.paper_client())
    cid = PaperOrder.objects.get().client_order_id
    assert result.failed == {cid: "Alpaca answered 404: order not found"}
    assert PaperOrder.objects.get().status == "accepted"


@pytest.mark.django_db
def test_the_command_without_keys_says_so(settings: Settings) -> None:
    settings.ALPACA_PAPER_KEY_ID = ""
    settings.ALPACA_PAPER_SECRET_KEY = ""
    out = StringIO()
    call_command("sync_paper_orders", stdout=out)
    assert out.getvalue().strip() == "Alpaca paper keys are not set; nothing to sync."


@pytest.mark.django_db
def test_the_nightly_cron_syncs_orders_once_the_keys_are_set(
    fake: FakeAlpaca, client: Client, settings: Settings, plan: MethodPlan, tmp_path: Path
) -> None:
    settings.CRON_SECRET = "cron-secret-for-tests-only"
    settings.TIINGO_API_KEY = ""
    settings.PRICES_CSV_DIR = tmp_path
    orders.confirm(plan, DAY, alpaca.paper_client())
    fake.fill("order-1", qty="0.5", price="200")
    headers = {"Authorization": "Bearer cron-secret-for-tests-only"}
    body = client.get("/api/cron/pull-prices/", headers=headers).json()
    assert body["orders"] == {
        "checked": 1,
        "changed": 1,
        "filled": 1,
        "ended_part_filled": 0,
        "ended_unfilled": 0,
        "still_open": 0,
        "failed": {},
    }
    settings.ALPACA_PAPER_KEY_ID = ""
    assert "orders" not in client.get("/api/cron/pull-prices/", headers=headers).json()


# --- The paper page, and who may see it ----------------------------------------------------------


@pytest.mark.django_db
def test_the_paper_page_shows_alpacas_positions_and_cash_beside_the_practice_budget(
    fake: FakeAlpaca, owner_client: Client, plan: MethodPlan
) -> None:
    orders.confirm(plan, DAY, alpaca.paper_client())
    html = text(owner_client.get(paper_url(plan.account)))
    assert f"Alpaca paper ({PAPER_HOST}). {LIVE_LINE}" in html
    assert "<dt>Budget</dt><dd>1000.00</dd>" in html and "<dt>Spent</dt><dd>100.00</dd>" in html
    assert "<dt>Cash</dt><dd>1234.56</dd>" in html
    assert '<th scope="row">INDEX</th>' in html and "100.75" in html
    assert "order-1" in html
    assert "does not simulate dividends" in html
    assert SECRET not in html and KEY_ID not in html


@pytest.mark.django_db
def test_the_paper_page_shows_an_alpaca_failure_as_a_message(
    fake: FakeAlpaca, owner_client: Client, plan: MethodPlan
) -> None:
    fake.fail["GET /v2/account"] = (401, {"message": "unauthorized"})
    response = owner_client.get(paper_url(plan.account))
    assert response.status_code == 200
    assert "Alpaca did not answer. Alpaca answered 401: unauthorized" in text(response)


@pytest.mark.django_db
def test_check_orders_now_syncs_this_account(
    fake: FakeAlpaca, owner_client: Client, plan: MethodPlan
) -> None:
    orders.confirm(plan, DAY, alpaca.paper_client())
    fake.fill("order-1", qty="0.5", price="200")
    response = owner_client.post(paper_url(plan.account, "sync/"), follow=True)
    assert "Checked 1 open order: 1 filled, 0 still open." in text(response)
    assert JournalEntry.objects.get().shares == D("0.5")


@pytest.mark.django_db
def test_the_account_page_links_the_paper_page_for_the_owner(
    fake: FakeAlpaca, owner_client: Client, account: Account
) -> None:
    html = text(owner_client.get(f"/accounts/{account.pk}/"))
    assert f'href="{paper_url(account)}"' in html and LIVE_LINE in html


@pytest.mark.django_db
def test_every_paper_route_is_the_owners_alone(
    fake: FakeAlpaca,
    client: Client,
    owner: User,
    someone: User,
    plan: MethodPlan,
    django_user_model: type[User],
) -> None:
    account = plan.account
    routes = [
        ("get", paper_url(account)),
        ("post", paper_url(account, "confirm/")),
        ("post", paper_url(account, "sync/")),
    ]
    for method, url in routes:
        assert getattr(client, method)(url).status_code == 302, "signed out: to the sign-in"
    client.force_login(someone)
    for method, url in routes:
        assert getattr(client, method)(url).status_code == 404, "another owner's account"
    # The owner of a linked account who is not a superuser: the keys are the site owner's.
    plain = django_user_model.objects.create_user("plain")
    theirs = Account.objects.create(
        name="Theirs", broker="Alpaca", kind="paper", alpaca="paper", owner=plain
    )
    client.force_login(plain)
    assert client.get(paper_url(theirs)).status_code == 404
    # The site owner's account that is not linked.
    unlinked = Account.objects.create(name="Unlinked", broker="Example", kind="paper", owner=owner)
    client.force_login(owner)
    assert client.get(paper_url(unlinked)).status_code == 404
    assert "This month's buys" not in text(client.get(method_url(unlinked)))
    assert client.get(paper_url(account, "confirm/")).status_code == 405
    assert posted_orders(fake) == 0


@pytest.mark.django_db
def test_a_post_without_a_csrf_token_is_refused(
    fake: FakeAlpaca, owner: User, plan: MethodPlan
) -> None:
    strict = Client(enforce_csrf_checks=True)
    strict.force_login(owner)
    assert strict.post(paper_url(plan.account, "confirm/")).status_code == 403
    assert posted_orders(fake) == 0


@pytest.mark.django_db
def test_an_alpaca_link_is_for_one_paper_account_per_owner(owner: User, account: Account) -> None:
    brokerage = Account(
        name="Taxable", broker="Example", kind="brokerage", alpaca="paper", owner=owner
    )
    with pytest.raises(ValidationError, match="Only a paper account can be linked"):
        brokerage.full_clean()
    second = Account(name="Second", broker="Alpaca", kind="paper", alpaca="paper", owner=owner)
    with pytest.raises(ValidationError, match="already has an account linked"):
        second.full_clean()
    with transaction.atomic(), pytest.raises(IntegrityError):
        second.save()


@pytest.mark.django_db
def test_the_admin_lists_paper_orders_read_only(
    fake: FakeAlpaca, admin_client: Client, plan: MethodPlan
) -> None:
    orders.confirm(plan, DAY, alpaca.paper_client())
    assert admin_client.get("/admin/paper/paperorder/").status_code == 200
    assert admin_client.get("/admin/paper/paperorder/add/").status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_public_pages_show_no_table_and_no_account_link(
    fake: FakeAlpaca, client: Client, plan: MethodPlan, path: str
) -> None:
    orders.confirm(plan, DAY, alpaca.paper_client())
    html = text(client.get(path))
    assert "<table" not in html.lower()
    assert "/accounts/" not in html and "/paper/" not in html
    assert "This month's buys" not in html and "Alpaca paper (" not in html


def test_env_example_names_the_two_paper_keys() -> None:
    names = (BASE_DIR / ".env.example").read_text(encoding="utf-8")
    assert "\nALPACA_PAPER_KEY_ID=\n" in names and "\nALPACA_PAPER_SECRET_KEY=\n" in names
```

Things to notice:

- **`FakeAlpaca` is the vendor.** It answers the six routes the app calls, keeps orders by id, and refuses a
  second order with an id it already has, with Alpaca's 422 and Alpaca's words. `fail` makes any route answer
  with a status and a body of your choice, which is how the refusal, timeout and 5xx tests are written.
- **The keys are made up and checked for.** `KEY_ID` and `SECRET` look like nothing real. Several tests assert
  that neither appears in a page, a URL or an error message.
- **The day is fixed.** `orders.today` is a function so the `fake` fixture can pin it to November 3, 2026,
  inside a seven-day window that opened on the 1st. A test that ran on the 20th would otherwise see "window
  closed".
- **Placeholder symbols only.** `INDEX` and `OTHER`, as in every chapter. The fake fills at made-up prices.
- **The owner is a superuser.** `create_superuser`, because Alpaca is the site owner's. The ownership test makes
  a plain user who owns a linked account and expects a 404.
- **The retry and the duplicate are separate tests.** One plants a row with no Alpaca id and an order Alpaca
  already has, and expects no POST at all; the other plants only Alpaca's order and expects one POST, Alpaca's
  422, and the order read back.
- **`fresh_settings` is chapter 06's helper** with the Alpaca names added to the ones it clears, and
  `raising=False`, because after a refused import the settings module is not in `sys.modules` to delete.

Run the tests:

Listing 11-2, Terminal:

```sh
uv run pytest tests/test_ch11.py
```

```text
tests/test_ch11.py:33: in <module>
    from invest_witus_site.paper import alpaca, orders
E   ModuleNotFoundError: No module named 'invest_witus_site.paper'
=========================== short test summary info ============================
ERROR tests/test_ch11.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.51s ===============================
```

Red at import. No package is added this chapter: httpx has been a dependency since chapter 07.

### 11.2 The settings, the app and its URLs

Two names join the settings, read from the environment like every other value, and one check refuses a live
host before Django finishes starting:

Listing 11-3, Filename: `src/invest_witus_site/settings.py`:

```python
"""Django settings for Invest.WitUS.

Anything that differs between your laptop and a server comes from an environment variable, with a
safe default for the laptop. The names are listed in `.env.example`; values never go in git.
Chapter 06 added the server's side: the database from `DATABASE_URL`, a secret key the server
must set, the HTTPS cookie and proxy settings, the folder `collectstatic` fills, and logging a
server can show. Chapter 07 added the four names of Sign in with WitUS; chapter 08 the price
source and the cron secret, at the end. Chapters 09 and 10 add one app each and no names.
"""

import contextlib
import os
from pathlib import Path

import django_stubs_ext
from django.core.exceptions import ImproperlyConfigured

from invest_witus_site.database import database_from_url

# django-stubs describes Django's classes as generics (`ModelAdmin[WaitlistEntry]`) so pyright can
# check them, but Django itself does not accept `[...]` on those classes at runtime. This one call
# teaches them to, so the admin code can be written the way the type checker reads it.
django_stubs_ext.monkeypatch()

# The repository root. This file is src/invest_witus_site/settings.py, three levels down.
BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env_list(name: str) -> list[str]:
    """A comma-separated variable as a list, blanks dropped: "a, b," becomes ["a", "b"]."""
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


# Off unless DJANGO_DEBUG=1. Debug pages show settings and source code; never on a server.
DEBUG = os.environ.get("DJANGO_DEBUG") == "1"

# Vercel sets VERCEL=1 on its build machine and inside the function (its system environment
# variables). It is read for one question only: does a proxy that ends HTTPS sit in front?
ON_VERCEL = os.environ.get("VERCEL") == "1"
if DEBUG and ON_VERCEL:
    raise ImproperlyConfigured(
        "DJANGO_DEBUG=1 on Vercel: debug pages would show settings and code to anyone. Unset it."
    )


def secret_key(debug: bool) -> str:
    """DJANGO_SECRET_KEY, which a server must set. With debug off and no key, Django refuses to
    start here, with a message that says what to do, rather than sign sessions with a key anyone
    can read in git."""
    key = os.environ.get("DJANGO_SECRET_KEY", "")
    if key:
        return key
    if not debug:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY is not set and DJANGO_DEBUG is not 1. A server needs a secret key. "
            "Make one with: uv run python -c "
            '"from django.core.management.utils import get_random_secret_key as k; print(k())"'
        )
    # DEV-ONLY FALLBACK, reachable only with DJANGO_DEBUG=1 on a laptop. `check --deploy` warns
    # about the `django-insecure-` prefix, which is the point.
    return "django-insecure-dev-only-set-DJANGO_SECRET_KEY"


SECRET_KEY = secret_key(DEBUG)

# Host names the site answers to. The default answers a laptop and nothing else; production sets
# DJANGO_ALLOWED_HOSTS=invest.witus.online. The host names Vercel gives a deployment (its
# *.vercel.app URLs, and the production domain once one is added) come from Vercel's own
# variables, so a preview deployment answers without anyone listing its URL by hand.
VERCEL_HOSTS = [
    host
    for name in ("VERCEL_URL", "VERCEL_BRANCH_URL", "VERCEL_PROJECT_PRODUCTION_URL")
    if (host := os.environ.get(name))
]
# (dict.fromkeys keeps the order and drops a name listed twice.)
ALLOWED_HOSTS = list(
    dict.fromkeys((env_list("DJANGO_ALLOWED_HOSTS") or ["localhost", "127.0.0.1"]) + VERCEL_HOSTS)
)

# Origins (scheme and host) a form may be posted from. Django compares a POST's Origin header with
# the request's own origin; listing the site's HTTPS origin keeps that check passing even if the
# proxy header below were ever missing. Production sets https://invest.witus.online.
CSRF_TRUSTED_ORIGINS = list(
    dict.fromkeys(
        env_list("DJANGO_CSRF_TRUSTED_ORIGINS") + [f"https://{host}" for host in VERCEL_HOSTS]
    )
)

# Chapter 04 installed only staticfiles and the pages app. The admin (chapter 05) needs the four
# contrib apps it is built on: auth (users and permissions), contenttypes (the table of tables that
# permissions point at), sessions (how a login is remembered) and messages (the "2 entries approved"
# notes after an action). They arrive together because the admin does not start without them.
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "invest_witus_site.pages",
    "invest_witus_site.holdings",
    "invest_witus_site.accounts",
    "invest_witus_site.prices",
    # The watch list (chapter 09): symbols the owner follows, kept per account, pulled nightly.
    "invest_witus_site.watchlist",
    # The method engine (chapter 10): the plan an account runs, its journal, the review, the views.
    "invest_witus_site.methods",
    # Alpaca paper trading (chapter 11): the paper client, the orders, the confirm step, the sync.
    "invest_witus_site.paper",
]

# Order matters: a middleware sees the request top to bottom and the response bottom to top.
# Sessions must load before authentication can read the session, and messages after that.
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "invest_witus_site.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Templates live in each app's templates/ folder; nothing outside an app.
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "invest_witus_site.pages.context_processors.site",
                "invest_witus_site.accounts.context_processors.identity",
            ],
        },
    },
]

# The WSGI application `runserver` loads. It names the bridge file at the repository root, not
# `invest_witus_site.wsgi`, because Vercel turns this value into a file path beside `manage.py`,
# and the bridge is what puts `src/` on the import path there (chapter 06).
WSGI_APPLICATION = "wsgi.application"


# The database. With no DATABASE_URL: SQLite in the folder git ignores, as in chapter 04. On
# Vercel the Neon integration sets DATABASE_URL (the pooled connection, for the app) and
# DATABASE_URL_UNPOOLED (the direct one, for migrations). `database_from_url` reads either shape.
# Vercel's connect dialog can put a prefix on every name the integration writes; the production
# project was connected with the prefix STORAGE (read from its variable list, 2026-10-28), so the
# prefixed names are accepted as well. An unprefixed name wins when both exist.
def first_env(*names: str) -> str | None:
    """The first of `names` that is set and not empty, or None."""
    for name in names:
        if value := os.environ.get(name):
            return value
    return None


DATA_DIR = BASE_DIR / "data" / "private"
POOLED_URL = first_env("DATABASE_URL", "STORAGE_DATABASE_URL")
DATABASE_URL = POOLED_URL or "sqlite:///data/private/invest-witus.sqlite3"
if not POOLED_URL:
    # A server's filesystem may be read-only; then /healthz/ reports the database as missing.
    with contextlib.suppress(OSError):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASES = {"default": database_from_url(DATABASE_URL, BASE_DIR)}
if unpooled := first_env("DATABASE_URL_UNPOOLED", "STORAGE_DATABASE_URL_UNPOOLED"):
    # Neon: schema changes take the direct connection, not the pooler. The owner runs
    # `manage.py migrate --database direct` and `createsuperuser --database direct` against it.
    DATABASES["direct"] = database_from_url(unpooled, BASE_DIR)

# The only password in this app is the owner's admin login (chapter 05). Sign in with WitUS
# (chapter 07) adds no passwords. `createsuperuser` refuses a password these validators reject.
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
# Where `collectstatic` copies every app's static files into one folder (gitignored). Vercel sees
# STATIC_ROOT, runs collectstatic itself during the build, and serves that folder from its CDN at
# STATIC_URL; the function never serves a static file.
STATIC_ROOT = BASE_DIR / "staticfiles"

# HTTPS. Vercel ends TLS at its CDN and calls the function over plain HTTP with the header
# X-Forwarded-Proto: https. Django is told to trust that header only on Vercel, where the proxy
# sets it on every request (Django's warning: never where a client could send it to Django
# directly). Vercel also answers every plain-HTTP request with a 308 to HTTPS before Django sees
# it, and sends Strict-Transport-Security on custom domains, so the redirect below is a second
# line and the HSTS check (security.W004) is silenced on purpose.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if ON_VERCEL else None
SECURE_SSL_REDIRECT = ON_VERCEL
SILENCED_SYSTEM_CHECKS = ["security.W004"]
# Cookies marked Secure travel only over HTTPS. On whenever debug is off, so a server never sends
# the admin's session over plain HTTP. It is also why `runserver` with debug off cannot sign you
# in at http://127.0.0.1:8000/admin/: the browser keeps a Secure cookie off a plain connection.
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# Django's default logging prints to the console only while debug is on, so a server would show
# nothing. This sends warnings and errors (a 500's traceback, a refused host) to stderr, which
# Vercel collects as the function's logs. Nothing here logs a request body or a setting.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"stderr": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["stderr"], "level": "WARNING"},
}

# The FAQ, privacy and terms pages are Markdown files in the repo, so a wording change is a normal
# commit with a diff anyone can read.
SITE_PAGES_DIR = BASE_DIR / "docs" / "site"

# Vercel Web Analytics (chapter 06a): two script tags in the base template, rendered only when
# both hold: the app runs on Vercel, and the owner set VERCEL_ANALYTICS=1 on that environment. So
# production and preview can differ, and `runserver` never emits the tags (debug on Vercel is
# refused above, so a debug server never does either). The script's path belongs to the project:
# once Analytics is enabled, the project's Analytics page shows it, and that value goes in
# VERCEL_ANALYTICS_SCRIPT_PATH. FALLBACK, not a value read from any dashboard: the shared
# `/_vercel/insights/` route the quickstart names, with the file name from its snippet.
VERCEL_ANALYTICS_ENABLED = ON_VERCEL and os.environ.get("VERCEL_ANALYTICS") == "1"
VERCEL_ANALYTICS_SCRIPT_PATH = (
    os.environ.get("VERCEL_ANALYTICS_SCRIPT_PATH") or "/_vercel/insights/script.js"
)
if not VERCEL_ANALYTICS_SCRIPT_PATH.startswith("/"):
    raise ImproperlyConfigured(
        "VERCEL_ANALYTICS_SCRIPT_PATH must be a path on this site, starting with /, such as "
        "/<unique-path>/script.js from the Analytics page of the Vercel project."
    )

# Sign in with WitUS (chapter 07): OpenID Connect against the ecosystem's identity provider. The
# client is ON only when the secret is set; without it the sign-in route shows chapter 04's stub
# page and the site deploys as before. The issuer is what the provider asserts in its discovery
# document; the default is the ecosystem's accounts host as read on October 28, 2026, copied from
# that document, and the client refuses a document whose issuer differs. The client id follows the
# registry's `witus-<slug>` form. The secret is minted in the witus repo (task 07) and never
# written anywhere but the two Vercel projects' Environment Variables pages.
WITUS_OIDC_ISSUER = (os.environ.get("WITUS_OIDC_ISSUER") or "https://accounts.witus.online").rstrip(
    "/"
)
WITUS_OIDC_CLIENT_ID = os.environ.get("WITUS_OIDC_CLIENT_ID") or "witus-invest"
WITUS_OIDC_CLIENT_SECRET = os.environ.get("WITUS_OIDC_CLIENT_SECRET", "")
WITUS_OIDC_SCOPES = os.environ.get("WITUS_OIDC_SCOPES") or "openid email profile"
if not WITUS_OIDC_ISSUER.startswith("https://"):
    raise ImproperlyConfigured(
        "WITUS_OIDC_ISSUER must be the provider's https:// issuer, as its discovery document "
        "states it, such as https://accounts.witus.online"
    )
if "openid" not in WITUS_OIDC_SCOPES.split():
    raise ImproperlyConfigured(
        "WITUS_OIDC_SCOPES must include openid, such as: openid email profile"
    )

# Where `login_required` sends a visitor who is not signed in: the WitUS sign-in route, by name.
LOGIN_URL = "sign-in"

# Prices (chapter 08). The nightly pull writes one close per symbol per day into the app's own
# table. With TIINGO_API_KEY set, the closes come from Tiingo's end-of-day endpoint with the
# owner's own key; the free plan's license is "Internal Use Only" (its pricing page, read October
# 28, 2026), and the values are shown to the signed-in owner and to no one else. Without a key the
# pull reads `<SYMBOL>.csv` files from PRICES_CSV_DIR, chapter 02's format, which is what a laptop
# and a learner's copy use.
TIINGO_API_KEY = os.environ.get("TIINGO_API_KEY", "")
PRICES_CSV_DIR = Path(os.environ.get("PRICES_CSV_DIR") or DATA_DIR / "prices")
# What Vercel sends as `Authorization: Bearer <value>` when it calls the cron route (its docs,
# read October 28, 2026; at least 16 random characters). Empty means the route answers 503 and
# runs nothing: a deploy that forgot the variable fails closed.
CRON_SECRET = os.environ.get("CRON_SECRET", "")

# Alpaca paper trading (chapter 11). The owner's paper keys, from the paper dashboard's API Keys
# module; empty means every Alpaca feature says "not set" and nothing is called. The client's host
# is fixed in `paper/alpaca.py` to paper-api.alpaca.markets, never read from here. Live trading is
# not built: it needs the checklist in a later chapter and separate keys under other names.
ALPACA_PAPER_KEY_ID = os.environ.get("ALPACA_PAPER_KEY_ID", "")
ALPACA_PAPER_SECRET_KEY = os.environ.get("ALPACA_PAPER_SECRET_KEY", "")
# Alpaca's own tools read the host from APCA_API_BASE_URL (its paper trading page, read October
# 29, 2026). This app does not, but a value pointing anywhere except the paper host means someone
# expects live trading here, so the settings refuse to start rather than run beside that belief.
_alpaca_base_url = os.environ.get("APCA_API_BASE_URL", "")
if _alpaca_base_url and _alpaca_base_url.rstrip("/") != "https://paper-api.alpaca.markets":
    raise ImproperlyConfigured(
        "APCA_API_BASE_URL points somewhere other than https://paper-api.alpaca.markets. "
        "This app trades on paper only; unset it or set it to the paper host."
    )
```

The new lines are the last block and one entry in `INSTALLED_APPS`. The check compares the whole URL with the
paper host, so a trailing slash is fine and `https://api.alpaca.markets` is not.

Make the folder `src/invest_witus_site/paper/` with an empty `__init__.py`, an empty `migrations/__init__.py`,
`management/__init__.py` and `management/commands/__init__.py`, then the app's config:

Listing 11-4, Filename: `src/invest_witus_site/paper/apps.py`:

```python
from django.apps import AppConfig


class PaperConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "invest_witus_site.paper"
    verbose_name = "Paper trading"
```

Listing 11-5, Filename: `src/invest_witus_site/urls.py`:

```python
"""Where every URL of the site starts. Each app lists its own paths; this file includes them."""

from django.contrib import admin
from django.urls import include, path

from invest_witus_site import health

urlpatterns = [
    # The owner's back office. Every page under it requires a staff login (chapter 05).
    path("admin/", admin.site.urls),
    # Up, version, database: what a monitor asks after a deploy (chapter 06).
    path("healthz/", health.healthz, name="healthz"),
    # Sign in with WitUS: login, callback and logout (chapter 07).
    path("auth/witus/", include("invest_witus_site.accounts.urls")),
    # The signed-in owner's accounts, valued at the latest stored closes (chapter 08).
    path("accounts/", include("invest_witus_site.holdings.urls")),
    # The watch list's add and remove actions on an account page (chapter 09). The `pk` captured
    # here is passed on to the included views.
    path("accounts/<int:pk>/watch/", include("invest_witus_site.watchlist.urls")),
    # The method an account runs, its journal and the review, in three views (chapter 10).
    path("accounts/<int:pk>/method/", include("invest_witus_site.methods.urls")),
    # The account linked to Alpaca paper: its positions, cash and orders, the Confirm step and
    # the order check (chapter 11). Owner, superuser and a linked account only.
    path("accounts/<int:pk>/paper/", include("invest_witus_site.paper.urls")),
    # The nightly price pull, called by Vercel's cron with the bearer secret (chapter 08).
    path("api/cron/", include("invest_witus_site.prices.urls")),
    path("", include("invest_witus_site.pages.urls")),
]
```

Listing 11-6, Filename: `src/invest_witus_site/paper/urls.py`:

```python
"""The paper account page and its two actions. `invest_witus_site/urls.py` mounts this file under
`accounts/<int:pk>/paper/`, and the `pk` captured there reaches all three views."""

from django.urls import path

from invest_witus_site.paper import views

urlpatterns = [
    path("", views.paper_account, name="paper-account"),
    path("confirm/", views.confirm_buys, name="paper-confirm"),
    path("sync/", views.sync_now, name="paper-sync"),
]
```

The paper routes hang under the account, as the method page's do, so the `pk` captured in the root file reaches
every view.

### 11.3 The client

Listing 11-7, Filename: `src/invest_witus_site/paper/alpaca.py`:

```python
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
```

Things to notice:

- **The host is checked in `__init__`, before the keys.** `AlpacaPaper(key, secret, base_url=...)` with the live
  host raises `LiveHostRefused` whether or not keys are present, so no code path builds a client that could
  send a paper key to the live host.
- **`__repr__` is written by hand.** The headers hold the keys; a default `repr` in a traceback would print
  them.
- **One `_request` does all the talking.** A timeout becomes `AlpacaUnavailable`, any other httpx error too,
  each with `from None` so the chained exception (which can carry the request) is not printed; a 4xx or 5xx goes
  through `refusal`, which reads Alpaca's `message` and picks the exception by status.
- **The parsers are chapter 08's idea.** `json.loads(parse_float=Decimal)` so a JSON number is never a float;
  `optional_number` takes a string, an int or a Decimal and refuses `bool`, because `True` is an `int` in Python;
  `moment` uses `datetime.fromisoformat`, which reads Alpaca's `Z` and offsets and drops digits past the
  microsecond.
- **`buy_notional` takes no time in force.** Alpaca allows a dollar amount only on a market day order, so the
  client sends `market` and `day` and nothing else is possible.

### 11.4 The rows

Two fields join chapter 05's and chapter 10's tables, and one table is new. The account first:

Listing 11-8, Filename: `src/invest_witus_site/holdings/models.py`:

```python
"""Accounts, what they hold, and the dated statements that say so.

Four tables. An `Account` belongs to the owner. A `Snapshot` is one statement for one account on
one date; its `SnapshotLine`s are the numbers on it, one per symbol. A `Holding` is one row per
account and symbol: the symbol's kind and name, which do not change from statement to statement.
The numbers live on the lines, never on the holding, so history is kept and nothing is overwritten.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q

from invest_witus.holdings import Change, Position, compare
from invest_witus.money import to_money, to_shares

# Six decimal places for shares (the share step from chapter 01), two for money. `max_digits`
# counts both sides of the point: 18 and 6 allow up to 999,999,999,999 shares.
SHARE_PLACES = 6
MONEY_PLACES = 2


class Account(models.Model):
    """One account at one broker, entered by hand from its statements.

    `owner` is the Django user who manages the account in the admin: the owner's own login until
    Sign in with WitUS (chapter 07). `witus_user_id` is the WitUS user id (the `sub` claim) the
    account will be matched by after that chapter; it stays empty until then.
    """

    class Kind(models.TextChoices):
        BROKERAGE = "brokerage", "Brokerage (taxable)"
        RETIREMENT = "retirement", "Retirement"
        PAPER = "paper", "Paper (practice)"

    owner: models.ForeignKey[User, User] = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="accounts"
    )
    witus_user_id: models.CharField[str | None, str | None] = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text="Filled by Sign in with WitUS (chapter 07). Leave empty.",
    )
    name: models.CharField[str, str] = models.CharField(max_length=80)
    broker: models.CharField[str, str] = models.CharField(
        max_length=80, help_text="The broker's name as it appears on the statement."
    )
    kind: models.CharField[str, str] = models.CharField(max_length=10, choices=Kind.choices)
    currency: models.CharField[str, str] = models.CharField(
        max_length=3, default="USD", choices=[("USD", "US dollar")]
    )
    created_at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now_add=True)

    class Alpaca(models.TextChoices):
        """Which Alpaca environment the account mirrors (chapter 11). Paper is the only choice:
        live trading needs the checklist in a later chapter and separate keys, and is not here."""

        NONE = "", "Not linked"
        PAPER = "paper", "Alpaca paper"

    alpaca: models.CharField[str, str] = models.CharField(
        max_length=5,
        choices=Alpaca.choices,
        blank=True,
        default="",
        help_text="Chapter 11. Paper accounts only, one per owner.",
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "name"], name="account_name_once_per_owner"),
            # Chapter 11: a link to Alpaca's paper environment only on a paper account, and one per
            # owner, because the server holds one pair of paper keys and two linked rows would
            # count the same orders twice.
            models.CheckConstraint(
                condition=Q(alpaca="") | Q(kind="paper"),
                name="alpaca_link_on_paper_accounts_only",
                violation_error_message="Only a paper account can be linked to Alpaca paper.",
            ),
            models.UniqueConstraint(
                fields=["owner"],
                condition=Q(alpaca="paper"),
                name="one_alpaca_paper_account_per_owner",
                violation_error_message="This owner already has an account linked to Alpaca paper.",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.broker})"

    def snapshots(self) -> models.QuerySet[Snapshot]:
        """Newest first. Written as a query, not `self.snapshot_set`, so pyright can read it."""
        return Snapshot.objects.filter(account=self).order_by("-as_of")

    def latest_snapshot(self) -> Snapshot | None:
        return self.snapshots().first()

    @property
    def is_alpaca_paper(self) -> bool:
        return self.alpaca == "paper"


class Holding(models.Model):
    """One symbol in one account: the parts of a holding that do not change between statements."""

    class Kind(models.TextChoices):
        STOCK = "stock", "Stock"
        ETF = "etf", "ETF"
        MUTUAL_FUND = "mutual_fund", "Mutual fund"
        CASH = "cash", "Cash"

    account: models.ForeignKey[Account, Account] = models.ForeignKey(
        Account, on_delete=models.CASCADE
    )
    symbol: models.CharField[str, str] = models.CharField(max_length=20)
    # Blank until the owner sets it in the admin. The app never guesses a security's kind.
    kind: models.CharField[str, str] = models.CharField(
        max_length=12, choices=Kind.choices, blank=True, default=""
    )
    name: models.CharField[str, str] = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        ordering = ["account", "symbol"]
        constraints = [
            models.UniqueConstraint(fields=["account", "symbol"], name="holding_symbol_once"),
        ]

    def __str__(self) -> str:
        return f"{self.symbol} in {self.account}"


class Snapshot(models.Model):
    """One statement: an account on an as-of date. Its lines are the numbers on it."""

    account: models.ForeignKey[Account, Account] = models.ForeignKey(
        Account, on_delete=models.CASCADE
    )
    as_of: models.DateField[date, date] = models.DateField(
        help_text="The statement's as-of date, not the day you typed it in."
    )
    source: models.CharField[str, str] = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="For example: October statement PDF.",
    )
    created_at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-as_of"]
        constraints = [
            models.UniqueConstraint(fields=["account", "as_of"], name="snapshot_date_once"),
        ]

    def __str__(self) -> str:
        return f"{self.account.name} as of {self.as_of:%Y-%m-%d}"

    def lines(self) -> models.QuerySet[SnapshotLine]:
        return SnapshotLine.objects.filter(snapshot=self).order_by("symbol")

    def positions(self) -> list[Position]:
        """The lines as the library's plain values, ready for `compare`."""
        return [Position(line.symbol, line.shares, line.cost_basis) for line in self.lines()]

    def changes_since(self, earlier: Snapshot) -> list[Change]:
        """Per symbol: shares and cost basis on `earlier`, on this snapshot, and the difference."""
        return compare(earlier.positions(), self.positions())


class SnapshotLine(models.Model):
    """One symbol on one statement. Shares and money are Decimals, rounded with the library's
    rules before the database applies its own."""

    snapshot: models.ForeignKey[Snapshot, Snapshot] = models.ForeignKey(
        Snapshot, on_delete=models.CASCADE
    )
    symbol: models.CharField[str, str] = models.CharField(max_length=20)
    shares: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=18, decimal_places=SHARE_PLACES
    )
    cost_basis: models.DecimalField[Decimal | None, Decimal | None] = models.DecimalField(
        max_digits=14,
        decimal_places=MONEY_PLACES,
        null=True,
        blank=True,
        help_text="Total cost as the statement prints it; empty if not shown.",
    )
    market_value: models.DecimalField[Decimal | None, Decimal | None] = models.DecimalField(
        max_digits=14,
        decimal_places=MONEY_PLACES,
        null=True,
        blank=True,
        help_text="Value as the statement prints it, if any. No prices yet.",
    )
    notes: models.CharField[str, str] = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["symbol"]
        constraints = [
            models.UniqueConstraint(fields=["snapshot", "symbol"], name="line_symbol_once"),
        ]

    def __str__(self) -> str:
        return f"{self.symbol}: {self.shares} shares"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Normalize before the row is written: the symbol's case and spacing, the decimals'
        rounding, and the rule that a float never reaches a money field."""
        for field in ("shares", "cost_basis", "market_value"):
            value = getattr(self, field)
            if isinstance(value, float):
                raise TypeError(f"{field} must be a Decimal, not a float ({value!r})")
        self.symbol = self.symbol.strip().upper()
        self.shares = to_shares(self.shares)
        if self.cost_basis is not None:
            self.cost_basis = to_money(self.cost_basis)
        if self.market_value is not None:
            self.market_value = to_money(self.market_value)
        super().save(*args, **kwargs)
        # The account's catalog of symbols. The kind stays blank until the owner sets it.
        Holding.objects.get_or_create(account=self.snapshot.account, symbol=self.symbol)
```

`Alpaca` is a `TextChoices` with no live member. The two new constraints carry `violation_error_message`, so
when the admin's form validates them it prints "Only a paper account can be linked to Alpaca paper." instead of
the default, "Constraint “%(name)s” is violated." (Django Software Foundation, n.d.). `is_alpaca_paper` compares with the string
`"paper"`: pyright reads `Account.Alpaca.PAPER` as the `(value, label)` pair it is declared with.

The plan's budget:

Listing 11-9, Filename: `src/invest_witus_site/methods/models.py`:

```python
"""The method an account runs, and the journal the review reads: two tables, both thin.

A `MethodPlan` is chapter 03's `Plan` as a row: the method's id, the amount, the buy window, the
symbols and the start date, for one account. The method's rules are NOT in the row. They come from
the TOML file that ships in `invest_witus.methods` through `load_method(method_id)` at request
time, so a rule's text or lesson link changes with the package and no row goes stale, and a rule
without a published lesson reads "lesson coming" because the file says so, never because a column
was left empty. A `JournalEntry` is chapter 03's `Entry` as a row: one buy or sell, with the
shares if known and a note. Both convert to the chapter 03 values (`to_plan`, `to_entry`), so
`adherence.review.review` runs on the web exactly as it ran on the command line.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from invest_witus.adherence.journal import Action, Entry
from invest_witus.adherence.plan import Plan
from invest_witus.methods.rulebook import Method, UnknownMethodError, load_method
from invest_witus.money import to_money, to_shares
from invest_witus_site.holdings.models import MONEY_PLACES, SHARE_PLACES, Account
from invest_witus_site.watchlist.models import normalize_symbol, parse_symbols, validate_symbol

# Chapter 03's rule for a plan file, kept here for the form and `full_clean`: a buy window is a
# day of the month that every month has.
MIN_WINDOW_DAYS = 1
MAX_WINDOW_DAYS = 28
# The smallest amount a plan or an entry can carry: one cent. The form says so beside the box.
ONE_CENT = Decimal("0.01")


def validate_method_id(value: str) -> None:
    """The id must name a rules file the package ships. Never a free text: a plan for a method
    that has no rules could not be reviewed."""
    try:
        load_method(value)
    except UnknownMethodError:
        raise ValidationError(f"unknown method {value!r}") from None


def validate_symbol_list(value: str) -> None:
    """The stored list is symbols separated by spaces, each inside chapter 09's rule."""
    parsed = parse_symbols(value)
    if parsed.refused:
        reasons = "; ".join(f"{token} ({reason})" for token, reason in parsed.refused)
        raise ValidationError(f"Not a symbol: {reasons}.")
    if not parsed.symbols:
        raise ValidationError("Name at least one symbol.")


def join_symbols(text: str) -> str:
    """The list as it is stored: each symbol normalized, once, in the order typed, joined by
    single spaces. A refused token raises, as `normalize_symbol` does, so no caller stores one."""
    parsed = parse_symbols(text)
    if parsed.refused:
        token, reason = parsed.refused[0]
        raise ValueError(f"{token}: {reason}")
    if not parsed.symbols:
        raise ValueError("empty")
    return " ".join(parsed.symbols)


class MethodPlan(models.Model):
    """One account running one method with the person's own numbers. At most one is active per
    account (a partial unique constraint); an ended plan stays as history with `active` off."""

    account: models.ForeignKey[Account, Account] = models.ForeignKey(
        Account, on_delete=models.CASCADE
    )
    method_id: models.CharField[str, str] = models.CharField(
        max_length=40,
        validators=[validate_method_id],
        help_text="The id of a rules file the package ships, such as index-dca.",
    )
    amount: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=14,
        decimal_places=MONEY_PLACES,
        validators=[MinValueValidator(ONE_CENT)],
        help_text="What the method buys each time.",
    )
    buy_window_days: models.PositiveSmallIntegerField[int, int] = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(MIN_WINDOW_DAYS)],
        help_text="Buy within the first N days of each month, 1 to 28.",
    )
    symbols: models.CharField[str, str] = models.CharField(
        max_length=200,
        validators=[validate_symbol_list],
        help_text="The fund or funds the plan names, separated by spaces.",
    )
    started_on: models.DateField[date, date] = models.DateField(
        help_text="The plan's first month; earlier trades are not reviewed."
    )
    active: models.BooleanField[bool, bool] = models.BooleanField(default=True)
    created_at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now_add=True)
    # Chapter 11: the practice money the plan may spend, kept by the app. Alpaca's paper balance
    # cannot be set (research 05), so the plan's budget is this number, not Alpaca's cash.
    practice_budget: models.DecimalField[Decimal | None, Decimal | None] = models.DecimalField(
        max_digits=14,
        decimal_places=MONEY_PLACES,
        null=True,
        blank=True,
        validators=[MinValueValidator(ONE_CENT)],
        help_text="Practice money this plan may spend on a paper account. Empty: not set.",
    )

    class Meta:
        ordering = ["account", "-started_on", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["account"],
                condition=Q(active=True),
                name="one_active_plan_per_account",
            ),
            models.CheckConstraint(
                condition=Q(buy_window_days__gte=MIN_WINDOW_DAYS)
                & Q(buy_window_days__lte=MAX_WINDOW_DAYS),
                name="buy_window_between_1_and_28",
            ),
        ]
        verbose_name = "method plan"
        verbose_name_plural = "method plans"

    def __str__(self) -> str:
        return f"{self.method_id} on {self.account}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Normalize before the row is written, as every table in this app does: the amount to
        cents, the symbols through chapter 09's rule, a float refused, an unknown method refused."""
        for field in ("amount", "practice_budget"):
            if isinstance(getattr(self, field), float):
                raise TypeError(f"{field} must be a Decimal, not a float")
        validate_method_id(self.method_id)
        self.amount = to_money(self.amount)
        if self.practice_budget is not None:
            self.practice_budget = to_money(self.practice_budget)
        self.symbols = join_symbols(self.symbols)
        super().save(*args, **kwargs)

    @classmethod
    def active_for(cls, account: Account) -> MethodPlan | None:
        return cls.objects.filter(account=account, active=True).first()

    def method(self) -> Method:
        """The rules, read from the package now, never copied into the row."""
        return load_method(self.method_id)

    def symbol_list(self) -> list[str]:
        return self.symbols.split()

    def to_plan(self) -> Plan:
        """Chapter 03's `Plan`, so `review` runs unchanged."""
        return Plan(
            method=self.method_id,
            start=self.started_on,
            amount=self.amount,
            symbols=frozenset(self.symbol_list()),
            buy_window_days=self.buy_window_days,
        )


# The choices for an entry's action come from chapter 03's enum, so the two cannot drift: a value
# the review does not know cannot be stored.
ACTION_CHOICES = [(action.value, action.value.capitalize()) for action in Action]


class JournalEntry(models.Model):
    """One trade the person logged by hand: the day, buy or sell, the symbol, the money, and the
    shares if the confirmation showed them. Chapter 12 builds the full logbook on this table."""

    account: models.ForeignKey[Account, Account] = models.ForeignKey(
        Account, on_delete=models.CASCADE
    )
    date: models.DateField[date, date] = models.DateField(help_text="The day the trade happened.")
    action: models.CharField[str, str] = models.CharField(max_length=4, choices=ACTION_CHOICES)
    symbol: models.CharField[str, str] = models.CharField(
        max_length=20, validators=[validate_symbol]
    )
    amount: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=14,
        decimal_places=MONEY_PLACES,
        validators=[MinValueValidator(ONE_CENT)],
        help_text="The money that changed hands.",
    )
    shares: models.DecimalField[Decimal | None, Decimal | None] = models.DecimalField(
        max_digits=18,
        decimal_places=SHARE_PLACES,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="From the confirmation, if shown. Optional.",
    )
    note: models.CharField[str, str] = models.CharField(max_length=200, blank=True, default="")
    created_at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["account", "date", "pk"]
        verbose_name = "journal entry"
        verbose_name_plural = "journal entries"

    def __str__(self) -> str:
        return f"{self.date:%Y-%m-%d} {self.action} {self.amount} of {self.symbol}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """The same guards as a statement line: no float, the symbol's rule, the rounding."""
        for field in ("amount", "shares"):
            if isinstance(getattr(self, field), float):
                raise TypeError(f"{field} must be a Decimal, not a float")
        self.symbol = normalize_symbol(self.symbol)
        self.amount = to_money(self.amount)
        if self.shares is not None:
            self.shares = to_shares(self.shares)
        super().save(*args, **kwargs)

    def to_entry(self) -> Entry:
        """Chapter 03's `Entry`. `Action(self.action)` raises on a value the enum lacks, which the
        choices and the form make impossible to store."""
        return Entry(
            day=self.date, action=Action(self.action), symbol=self.symbol, amount=self.amount
        )

    @classmethod
    def entries_for(cls, account: Account) -> list[JournalEntry]:
        """The account's rows in date order, the order `review` and the pages want."""
        return list(cls.objects.filter(account=account))
```

`practice_budget` gets the same float guard and rounding as `amount`. It is nullable, so every plan from
chapter 10 stays valid.

The orders:

Listing 11-10, Filename: `src/invest_witus_site/paper/models.py`:

```python
"""The app's own copy of every paper order it placed: one row per account, plan, month and symbol.

Alpaca executes; this table remembers. A paper account deleted on Alpaca's dashboard takes its
history with it (research 05), so every order the app places is written here first, with the
deterministic `client_order_id` that makes a second click or a retry the same order, and the
nightly sync copies Alpaca's status and fill back into the row and into the journal entry it
made.
"""

from datetime import datetime
from decimal import Decimal

from django.db import models

from invest_witus_site.holdings.models import MONEY_PLACES, Account
from invest_witus_site.methods.models import JournalEntry, MethodPlan

# Alpaca reports quantities "up to 9 decimal points" (its order reference, read October 29, 2026).
# The row keeps all nine; the journal keeps six, rounded down, as every share count in the app.
ALPACA_QTY_PLACES = 9
# Statuses after which "no further updates will occur for the order" (Alpaca's order lifecycle
# page). `replaced` is final for the old order; this app never replaces one.
FINAL_STATUSES = frozenset({"filled", "canceled", "expired", "rejected", "replaced"})
# Not yet sent, or sent and refused before Alpaca made an order: the row's own status.
STAGED = "staged"


def client_order_id(account_pk: int, plan_pk: int, month: str, symbol: str) -> str:
    """The same four facts always give the same id, so Alpaca and this table both see a repeat
    as the order they already have. `iw-12-3-2026-11-INDEX`: well under Alpaca's 128 characters
    (a symbol is at most 12)."""
    return f"iw-{account_pk}-{plan_pk}-{month}-{symbol}"


class PaperOrder(models.Model):
    account: models.ForeignKey[Account, Account] = models.ForeignKey(
        Account, on_delete=models.CASCADE
    )
    plan: models.ForeignKey[MethodPlan, MethodPlan] = models.ForeignKey(
        MethodPlan, on_delete=models.PROTECT
    )
    month: models.CharField[str, str] = models.CharField(max_length=7, help_text="YYYY-MM")
    symbol: models.CharField[str, str] = models.CharField(max_length=20)
    notional: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=14, decimal_places=MONEY_PLACES, help_text="The dollars the order asked for."
    )
    client_order_id: models.CharField[str, str] = models.CharField(max_length=128, unique=True)
    alpaca_id: models.CharField[str, str] = models.CharField(
        max_length=64, blank=True, default="", help_text="Alpaca's order id, once it has one."
    )
    status: models.CharField[str, str] = models.CharField(max_length=24, default=STAGED)
    filled_qty: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=20, decimal_places=ALPACA_QTY_PLACES, default=Decimal("0")
    )
    filled_avg_price: models.DecimalField[Decimal | None, Decimal | None] = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True
    )
    submitted_at: models.DateTimeField[datetime | None, datetime | None] = models.DateTimeField(
        null=True, blank=True
    )
    filled_at: models.DateTimeField[datetime | None, datetime | None] = models.DateTimeField(
        null=True, blank=True
    )
    # The last refusal, in Alpaca's words, for a row still `staged`. Never a key.
    message: models.CharField[str, str] = models.CharField(max_length=240, blank=True, default="")
    journal_entry: models.OneToOneField[JournalEntry | None, JournalEntry | None] = (
        models.OneToOneField(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True)
    )
    created_at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-month", "symbol"]
        verbose_name = "paper order"
        verbose_name_plural = "paper orders"

    def __str__(self) -> str:
        return f"{self.month} {self.symbol} {self.notional} ({self.status})"

    @property
    def placed(self) -> bool:
        return bool(self.alpaca_id)

    @property
    def final(self) -> bool:
        return self.status in FINAL_STATUSES

    @classmethod
    def for_month(cls, plan: MethodPlan, month: str) -> list[PaperOrder]:
        return list(cls.objects.filter(plan=plan, month=month))

    @classmethod
    def open_orders(cls, account: Account | None = None) -> models.QuerySet[PaperOrder]:
        """Orders Alpaca has and that can still change: the sync's work list."""
        orders = cls.objects.exclude(alpaca_id="").exclude(status__in=FINAL_STATUSES)
        return orders.filter(account=account) if account is not None else orders
```

- **`client_order_id` is unique in the table,** which is the app's half of the idempotency; Alpaca's 422 is the
  other half.
- **`filled_qty` keeps nine places,** Alpaca's precision; the journal keeps six, rounded down, as every share
  count in the app since chapter 01.
- **`plan` is `PROTECT`.** An order the app placed under a plan is history; deleting the plan should fail
  rather than lose it.
- **`journal_entry` is `SET_NULL`.** An order that ended unfilled loses its entry and keeps its row.

Make the three migrations, in this order (the paper table depends on the other two), then let ruff tidy them:

Listing 11-11, Terminal:

```sh
uv run --env-file .env python manage.py makemigrations holdings --name account_alpaca
uv run --env-file .env python manage.py makemigrations methods
uv run --env-file .env python manage.py makemigrations paper
uv run ruff format src/invest_witus_site/*/migrations/
uv run ruff check --fix src/invest_witus_site/*/migrations/
```

```text
Migrations for 'holdings':
  src/invest_witus_site/holdings/migrations/0002_account_alpaca.py
    + Add field alpaca to account
    + Create constraint alpaca_link_on_paper_accounts_only on model account
    + Create constraint one_alpaca_paper_account_per_owner on model account
Migrations for 'methods':
  src/invest_witus_site/methods/migrations/0002_methodplan_practice_budget.py
    + Add field practice_budget to methodplan
Migrations for 'paper':
  src/invest_witus_site/paper/migrations/0001_initial.py
    + Create model PaperOrder
3 files reformatted, 14 files left unchanged
Found 2 errors (2 fixed, 0 remaining).
```

Listing 11-12, Filename: `src/invest_witus_site/holdings/migrations/0002_account_alpaca.py`:

```python
# Generated by Django 5.2.18 on 2026-10-29 14:52

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("holdings", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="account",
            name="alpaca",
            field=models.CharField(
                blank=True,
                choices=[("", "Not linked"), ("paper", "Alpaca paper")],
                default="",
                help_text="Chapter 11. Paper accounts only, one per owner.",
                max_length=5,
            ),
        ),
        migrations.AddConstraint(
            model_name="account",
            constraint=models.CheckConstraint(
                condition=models.Q(("alpaca", ""), ("kind", "paper"), _connector="OR"),
                name="alpaca_link_on_paper_accounts_only",
                violation_error_message="Only a paper account can be linked to Alpaca paper.",
            ),
        ),
        migrations.AddConstraint(
            model_name="account",
            constraint=models.UniqueConstraint(
                condition=models.Q(("alpaca", "paper")),
                fields=("owner",),
                name="one_alpaca_paper_account_per_owner",
                violation_error_message="This owner already has an account linked to Alpaca paper.",
            ),
        ),
    ]
```

Listing 11-13, Filename: `src/invest_witus_site/methods/migrations/0002_methodplan_practice_budget.py`:

```python
# Generated by Django 5.2.18 on 2026-10-29 14:51

from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("methods", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="methodplan",
            name="practice_budget",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Practice money this plan may spend on a paper account. Empty: not set.",
                max_digits=14,
                null=True,
                validators=[django.core.validators.MinValueValidator(Decimal("0.01"))],
            ),
        ),
    ]
```

Listing 11-14, Filename: `src/invest_witus_site/paper/migrations/0001_initial.py`:

```python
# Generated by Django 5.2.18 on 2026-10-29 14:52

from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("holdings", "0002_account_alpaca"),
        ("methods", "0002_methodplan_practice_budget"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaperOrder",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("month", models.CharField(help_text="YYYY-MM", max_length=7)),
                ("symbol", models.CharField(max_length=20)),
                (
                    "notional",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="The dollars the order asked for.",
                        max_digits=14,
                    ),
                ),
                ("client_order_id", models.CharField(max_length=128, unique=True)),
                (
                    "alpaca_id",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Alpaca's order id, once it has one.",
                        max_length=64,
                    ),
                ),
                ("status", models.CharField(default="staged", max_length=24)),
                (
                    "filled_qty",
                    models.DecimalField(decimal_places=9, default=Decimal("0"), max_digits=20),
                ),
                (
                    "filled_avg_price",
                    models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
                ),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("filled_at", models.DateTimeField(blank=True, null=True)),
                ("message", models.CharField(blank=True, default="", max_length=240)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="holdings.account"
                    ),
                ),
                (
                    "journal_entry",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="methods.journalentry",
                    ),
                ),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to="methods.methodplan"
                    ),
                ),
            ],
            options={
                "verbose_name": "paper order",
                "verbose_name_plural": "paper orders",
                "ordering": ["-month", "symbol"],
            },
        ),
    ]
```

All three only add: a column with a default, a nullable column, a new table. The production workflow from the
last chapter applies them after the merge, and the old code keeps working on the new schema while it runs.

### 11.5 Stage, confirm, sync

Listing 11-15, Filename: `src/invest_witus_site/paper/orders.py`:

```python
"""The monthly review's buys on a paper account: stage them from the plan, place them when the owner
confirms, and copy Alpaca's answers back into the journal.

Three jobs, in the order they happen:

1. `month_buys` stages this month's buys from the active plan: the plan's amount split across its
   symbols to the cent, each with its deterministic `client_order_id`, and the one reason, if any,
   that Confirm is not offered (outside the window, no practice budget, over the budget, a buy
   already logged by hand, more than one symbol).
2. `confirm` places what is staged and not yet placed, one order per symbol, and writes one
   journal entry per order. A second click, a retry after a timeout, or two clicks at once find
   the same row (unique `client_order_id`) and the same Alpaca order, so nothing is bought twice.
3. `sync_orders` reads every open order back from Alpaca and fixes its row and its journal entry:
   the shares filled, the amount, and no entry at all for an order that ended with nothing filled.

Nothing here runs without the owner's click except the sync, which only reads.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.db import transaction
from django.utils import timezone

from invest_witus.money import CENT, to_money, to_shares
from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.models import JournalEntry, MethodPlan
from invest_witus_site.paper.alpaca import (
    PAPER_HOST,
    AlpacaError,
    AlpacaNotFound,
    AlpacaPaper,
    AlpacaRateLimited,
    AlpacaRefused,
    MarketClock,
    PaperOrderState,
    paper_client,
)
from invest_witus_site.paper.models import PaperOrder, client_order_id

ZERO = Decimal("0")
NOTE_LIMIT = 200


def today() -> date:
    """The app's today. A function, so a test can fix the day the way chapter 03's `--through`
    fixed the review's."""
    return timezone.localdate()


def month_of(day: date) -> str:
    return f"{day.year}-{day.month:02d}"


def alpaca_allowed(user: AbstractBaseUser | AnonymousUser, account: Account) -> bool:
    """Alpaca is the site owner's: the server holds one pair of paper keys, so only a superuser,
    on an account linked to Alpaca paper, may read it or place orders through it. The caller has
    already fetched the account with `owner=request.user`."""
    return account.is_alpaca_paper and getattr(user, "is_superuser", False) is True


# --- 1. Stage -----------------------------------------------------------------------------------


def split_amount(amount: Decimal, symbols: list[str]) -> list[tuple[str, Decimal]]:
    """The amount in equal parts to the cent, one per symbol, in the plan's order. The cents that
    do not divide go one each to the first symbols, so the parts add up to the amount exactly:
    100.00 over three symbols is 33.34, 33.33 and 33.33."""
    if not symbols:
        raise ValueError("no symbols to split across")
    cents = int(to_money(amount) / CENT)
    each, left_over = divmod(cents, len(symbols))
    return [
        (symbol, (each + (1 if index < left_over else 0)) * CENT)
        for index, symbol in enumerate(symbols)
    ]


def practice_spent(plan: MethodPlan) -> Decimal:
    """What the plan has spent of its practice budget: every buy in the account's journal since
    the plan started, placed through Alpaca or logged by hand. A pending order has its entry
    already, so its money is spent the moment it is placed."""
    buys = JournalEntry.objects.filter(
        account=plan.account, action="buy", date__gte=plan.started_on
    ).values_list("amount", flat=True)
    return sum(buys, ZERO)


@dataclass(frozen=True, slots=True)
class StagedBuy:
    symbol: str
    notional: Decimal
    client_order_id: str
    order: PaperOrder | None

    @property
    def placed(self) -> bool:
        return self.order is not None and self.order.placed


@dataclass(frozen=True, slots=True)
class MonthBuys:
    """This month's buys for one plan, and why Confirm is not offered, in words, when it is not."""

    month: str
    window_closes: date
    buys: list[StagedBuy]
    total: Decimal
    budget: Decimal | None
    spent: Decimal
    refusal: str

    @property
    def left(self) -> Decimal | None:
        return None if self.budget is None else self.budget - self.spent

    @property
    def to_place(self) -> list[StagedBuy]:
        return [buy for buy in self.buys if not buy.placed]

    @property
    def can_confirm(self) -> bool:
        return not self.refusal and bool(self.to_place)


def month_buys(plan: MethodPlan, day: date) -> MonthBuys:
    month = month_of(day)
    parts = split_amount(plan.amount, plan.symbol_list())
    existing = {order.symbol: order for order in PaperOrder.for_month(plan, month)}
    buys = [
        StagedBuy(
            symbol,
            notional,
            client_order_id(plan.account.pk, plan.pk, month, symbol),
            existing.get(symbol),
        )
        for symbol, notional in parts
    ]
    window_closes = date(day.year, day.month, plan.buy_window_days)
    spent = practice_spent(plan)
    unplaced = sum((buy.notional for buy in buys if not buy.placed), ZERO)
    budget = plan.practice_budget
    return MonthBuys(
        month=month,
        window_closes=window_closes,
        buys=buys,
        total=sum((notional for _, notional in parts), ZERO),
        budget=budget,
        spent=spent,
        refusal=refusal_for(plan, day, window_closes, buys, unplaced, budget, spent),
    )


def refusal_for(
    plan: MethodPlan,
    day: date,
    window_closes: date,
    buys: list[StagedBuy],
    unplaced: Decimal,
    budget: Decimal | None,
    spent: Decimal,
) -> str:
    """The first reason Confirm cannot be pressed, or "" when it can. Each is a sentence the page
    prints as it is."""
    if day < plan.started_on:
        return f"The plan starts on {plan.started_on:%Y-%m-%d}; nothing is due before then."
    if day > window_closes:
        return (
            f"This month's window closed on {window_closes:%Y-%m-%d}. The method has no catching "
            "up: the next window opens on the 1st."
        )
    if len(buys) > 1:
        return (
            f"The plan names {len(buys)} symbols. This method's rules count one buy of the plan's "
            "amount each month, so split orders would show as findings; the app places a month's "
            "buys for a plan with one symbol."
        )
    if hand_logged_buys(plan, day):
        return f"A buy for {month_of(day)} is already in the journal, logged by hand."
    if not any(not buy.placed for buy in buys):
        return ""
    if budget is None:
        return (
            "Set a practice budget for this plan first, the app's own number: in the admin, "
            "Method plans, this plan, Practice budget."
        )
    if unplaced > budget - spent:
        return (
            f"This month's buys, {unplaced:.2f}, are more than the practice budget left, "
            f"{budget - spent:.2f}."
        )
    return ""


def hand_logged_buys(plan: MethodPlan, day: date) -> bool:
    """A buy this month in the journal that no paper order wrote: the owner already bought."""
    from_orders = PaperOrder.objects.filter(account=plan.account).exclude(journal_entry=None)
    return (
        JournalEntry.objects.filter(
            account=plan.account, action="buy", date__year=day.year, date__month=day.month
        )
        .exclude(pk__in=from_orders.values("journal_entry"))
        .exists()
    )


@dataclass(frozen=True, slots=True)
class PaperSection:
    """What the method page's "This month's buys" box needs: the staged buys, the clock, and the
    one error to show instead when Alpaca did not answer."""

    stage: MonthBuys
    clock: MarketClock | None
    error: str

    @property
    def host(self) -> str:
        return PAPER_HOST

    @property
    def queues_past_window(self) -> bool:
        """Closed now, and the next open is after the window: the fill will land outside it."""
        return (
            self.clock is not None
            and not self.clock.is_open
            and self.clock.next_open.date() > self.stage.window_closes
        )


def paper_section(plan: MethodPlan) -> PaperSection:
    """Built by the method page for a linked account. One request to Alpaca, the clock."""
    stage = month_buys(plan, today())
    try:
        clock = paper_client().clock()
    except AlpacaError as error:
        return PaperSection(stage, None, error.message)
    return PaperSection(stage, clock, "")


# --- 2. Confirm ---------------------------------------------------------------------------------


class ConfirmRefused(Exception):
    """The staged buys may not be placed; the message is `MonthBuys.refusal`."""


@dataclass(slots=True)
class ConfirmResult:
    clock: MarketClock
    placed: list[PaperOrder] = field(default_factory=list[PaperOrder])
    already: list[PaperOrder] = field(default_factory=list[PaperOrder])
    failed: list[tuple[str, str]] = field(default_factory=list[tuple[str, str]])


def confirm(plan: MethodPlan, day: date, client: AlpacaPaper) -> ConfirmResult:
    """Place this month's staged buys that are not placed yet. The checks run again here, on the
    server, whatever the page showed: a stale tab cannot buy outside the window or the budget."""
    stage = month_buys(plan, day)
    if stage.refusal:
        raise ConfirmRefused(stage.refusal)
    # Asked first, so a closed market is known before anything is sent; an error here stops the
    # whole confirm with nothing placed.
    result = ConfirmResult(clock=client.clock())
    for buy in stage.buys:
        if buy.placed and buy.order is not None:
            result.already.append(buy.order)
            continue
        try:
            order, new = place_one(plan, buy, day, client)
        except AlpacaError as error:
            result.failed.append((buy.symbol, error.message))
            continue
        (result.placed if new else result.already).append(order)
    return result


def place_one(
    plan: MethodPlan, buy: StagedBuy, day: date, client: AlpacaPaper
) -> tuple[PaperOrder, bool]:
    """One buy, at most once. The row is created or found by its `client_order_id` and locked for
    the length of the call (Postgres; SQLite has one writer anyway), so a second request for the
    same buy waits, then finds the order placed and returns it. A row that already existed
    without an Alpaca id means an earlier try may have reached Alpaca before failing here, so
    Alpaca is asked for that id before anything is sent."""
    failure: AlpacaError | None = None
    with transaction.atomic():
        order, created = PaperOrder.objects.select_for_update().get_or_create(
            client_order_id=buy.client_order_id,
            defaults={
                "account": plan.account,
                "plan": plan,
                "month": month_of(day),
                "symbol": buy.symbol,
                "notional": buy.notional,
            },
        )
        if order.placed:
            return order, False
        try:
            state = submit(client, order, look_first=not created)
        except AlpacaError as error:
            # Kept on the row, so the page can say why, and committed with it: the exception is
            # raised after the block, not inside it, which would roll the message back.
            order.message = error.message[:240]
            order.save(update_fields=["message", "updated_at"])
            failure = error
        else:
            apply_state(order, state)
            order.message = ""
            order.save()
            reconcile_journal(order, day)
            return order, True
    raise failure


def submit(client: AlpacaPaper, order: PaperOrder, look_first: bool) -> PaperOrderState:
    """Send the order, unless Alpaca already has one with this id. Alpaca refuses a repeated
    `client_order_id` with 422 "client_order_id must be unique"; that answer means the order
    exists, so it is read back rather than reported as a failure."""
    if look_first:
        try:
            return client.order_by_client_id(order.client_order_id)
        except AlpacaNotFound:
            pass
    try:
        return client.buy_notional(order.symbol, order.notional, order.client_order_id)
    except AlpacaRefused as error:
        if error.status == 422 and "client_order_id" in error.message:
            return client.order_by_client_id(order.client_order_id)
        raise


def apply_state(order: PaperOrder, state: PaperOrderState) -> None:
    order.alpaca_id = state.id
    order.status = state.status
    order.filled_qty = state.filled_qty
    order.filled_avg_price = state.filled_avg_price
    order.submitted_at = state.submitted_at
    order.filled_at = state.filled_at


# --- The journal entry an order writes ----------------------------------------------------------


def journal_amount(order: PaperOrder) -> Decimal:
    """The money that changed hands. A full fill spent the notional; an order that ended part
    filled spent shares times the average price; an order still open is booked at its notional,
    so the practice budget counts it now."""
    partly_done = order.final and order.status != "filled" and order.filled_qty > 0
    if partly_done and order.filled_avg_price is not None:
        return to_money(order.filled_qty * order.filled_avg_price)
    return order.notional


def journal_note(order: PaperOrder) -> str:
    note = f"Alpaca paper order {order.alpaca_id}: {order.status}"
    if order.final and order.filled_qty > 0 and order.filled_avg_price is not None:
        when = f" on {order.filled_at:%Y-%m-%d}" if order.filled_at else ""
        note += f", {to_shares(order.filled_qty)} shares at {order.filled_avg_price}{when}"
    return note[:NOTE_LIMIT]


def reconcile_journal(order: PaperOrder, day: date | None = None) -> None:
    """Make the order's journal entry say what Alpaca says. Shares are recorded once the order is
    final; an order that ended with nothing filled was never a trade, so its entry is removed and
    the row keeps the history. The entry's date is the day the owner confirmed, which is the act
    the method's window rule is about; the fill's date is in the note."""
    entry = order.journal_entry
    if order.final and order.filled_qty == 0:
        if entry is not None:
            order.journal_entry = None
            order.save(update_fields=["journal_entry", "updated_at"])
            entry.delete()
        return
    shares = to_shares(order.filled_qty) if order.final and order.filled_qty > 0 else None
    if entry is None:
        entry = JournalEntry.objects.create(
            account=order.account,
            date=day or today(),
            action="buy",
            symbol=order.symbol,
            amount=journal_amount(order),
            shares=shares,
            note=journal_note(order),
        )
        order.journal_entry = entry
        order.save(update_fields=["journal_entry", "updated_at"])
        return
    entry.amount = journal_amount(order)
    entry.shares = shares
    entry.note = journal_note(order)
    entry.save()


# --- 3. Sync ------------------------------------------------------------------------------------


@dataclass(slots=True)
class SyncResult:
    checked: int = 0
    changed: int = 0
    filled: int = 0
    ended_part_filled: int = 0
    ended_unfilled: int = 0
    still_open: int = 0
    failed: dict[str, str] = field(default_factory=dict[str, str])

    def as_dict(self) -> dict[str, object]:
        return {
            "checked": self.checked,
            "changed": self.changed,
            "filled": self.filled,
            "ended_part_filled": self.ended_part_filled,
            "ended_unfilled": self.ended_unfilled,
            "still_open": self.still_open,
            "failed": self.failed,
        }


def sync_orders(client: AlpacaPaper, account: Account | None = None) -> SyncResult:
    """Read every open order back and fix its row and its journal entry. Idempotent: an order that
    did not change writes nothing new, and a final order is never asked about again. One order
    Alpaca refuses is recorded and the rest go on; a 429 stops the run for the next one."""
    result = SyncResult()
    for order in PaperOrder.open_orders(account):
        result.checked += 1
        try:
            state = client.order(order.alpaca_id)
        except AlpacaRateLimited as error:
            result.failed[order.client_order_id] = error.message
            break
        except AlpacaError as error:
            result.failed[order.client_order_id] = error.message
            continue
        before = (order.status, order.filled_qty)
        apply_state(order, state)
        if (order.status, order.filled_qty) != before:
            result.changed += 1
            with transaction.atomic():
                order.save()
                reconcile_journal(order)
        if order.status == "filled":
            result.filled += 1
        elif not order.final:
            result.still_open += 1
        elif order.filled_qty > 0:
            result.ended_part_filled += 1
        else:
            result.ended_unfilled += 1
    return result
```

Things to notice:

- **`split_amount` works in whole cents.** `int(to_money(amount) / CENT)` is the amount in cents, `divmod`
  gives each part and the remainder, and the remainder goes one cent at a time to the first symbols. 100.00
  over three symbols is 33.34, 33.33 and 33.33, which add up to 100.00; a split in `Decimal` division would not.
- **`refusal_for` is a list of sentences in order.** The first that applies is the one the page prints. "All
  placed" is not a refusal: it is the state after a successful Confirm, and the page says so in its own words.
- **`place_one` raises after the `with` block.** An exception raised inside `transaction.atomic()` rolls the
  block back, and with it the message the row should keep. So the error is caught, the message saved, and the
  exception raised once the block has committed.
- **`select_for_update()` locks the row on Postgres** until the transaction ends, so a second request for the
  same buy waits for the first and then finds the order placed. SQLite ignores it, and has only one writer.
- **`submit` looks first only for an old row.** A row created by this request cannot have been sent before, so
  it is sent directly; Alpaca's 422 still catches two requests that raced past each other.
- **`reconcile_journal` is the one place the journal is written.** Confirm calls it with the day; the sync calls
  it with no day, so a new entry (rare: an order that had none) uses today.
- **`sync_orders` writes only what changed.** A status and fill that match the row skip the save, so a second
  run is quiet.
- **`PaperSection` is what the method page needs:** the staged buys, the clock, and one error string. It lives
  here, not in the views, so the method app imports the paper app's service module and never its views.

### 11.6 The pages

The paper app's views:

Listing 11-16, Filename: `src/invest_witus_site/paper/views.py`:

```python
"""The paper account page and its two actions: Confirm this month's buys, and check orders now.

Every view here needs a sign-in, the account's owner, an account linked to Alpaca paper and a
superuser (`alpaca_allowed`); anything else is a 404, which does not say whether the account
exists. Every Alpaca failure becomes a message on the page, never a 500. The keys never reach a
template: the page gets numbers and Alpaca's messages, nothing else.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.models import MethodPlan
from invest_witus_site.paper import orders
from invest_witus_site.paper.alpaca import (
    PAPER_HOST,
    AlpacaError,
    PaperAccount,
    PaperPosition,
    paper_client,
)
from invest_witus_site.paper.models import PaperOrder

# The paper limits Alpaca's paper trading page lists (read October 29, 2026). PRD 7.7: stated
# wherever paper results appear.
PAPER_LIMITS = (
    "Alpaca's paper trading does not simulate dividends, price slippage, market impact or "
    "regulatory fees, and fills part of an order at random about one time in ten."
)


def linked_account_or_404(request: HttpRequest, pk: int) -> Account:
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    if not orders.alpaca_allowed(request.user, account):
        raise Http404("No paper account here.")
    return account


@login_required
def paper_account(request: HttpRequest, pk: int) -> HttpResponse:
    account = linked_account_or_404(request, pk)
    plan = MethodPlan.active_for(account)
    alpaca_account: PaperAccount | None = None
    positions: list[PaperPosition] = []
    error = ""
    try:
        client = paper_client()
        alpaca_account = client.account()
        positions = client.positions()
    except AlpacaError as failure:
        error = failure.message
    context = {
        "account": account,
        "plan": plan,
        "spent": orders.practice_spent(plan) if plan is not None else None,
        "alpaca_account": alpaca_account,
        "positions": positions,
        "orders": PaperOrder.objects.filter(account=account),
        "error": error,
        "host": PAPER_HOST,
        "paper_limits": PAPER_LIMITS,
    }
    return render(request, "paper/paper_account.html", context)


@login_required
@require_POST
def confirm_buys(request: HttpRequest, pk: int) -> HttpResponse:
    """The owner's click. Places this month's staged buys once, then back to the method page."""
    account = linked_account_or_404(request, pk)
    plan = MethodPlan.active_for(account)
    if plan is None:
        messages.error(request, "No method runs on this account, so there is nothing to buy.")
        return redirect("method-page", pk=account.pk)
    try:
        result = orders.confirm(plan, orders.today(), paper_client())
    except orders.ConfirmRefused as refused:
        messages.error(request, str(refused))
    except AlpacaError as error:
        messages.error(request, f"Nothing was placed. {error.message}")
    else:
        report(request, result)
    return redirect("method-page", pk=account.pk)


def report(request: HttpRequest, result: orders.ConfirmResult) -> None:
    for order in result.placed:
        messages.success(
            request, f"Placed: buy {order.notional:.2f} of {order.symbol}, {order.status}."
        )
    for order in result.already:
        messages.info(request, f"Already placed: {order.symbol}, {order.status}. Nothing new sent.")
    for symbol, message in result.failed:
        messages.error(request, f"Not placed: {symbol}. {message}")
    if result.placed and not result.clock.is_open:
        messages.info(
            request,
            "The market is closed. Alpaca queues a day order for the next open, "
            f"{timezone.localtime(result.clock.next_open):%Y-%m-%d %H:%M %Z}.",
        )


@login_required
@require_POST
def sync_now(request: HttpRequest, pk: int) -> HttpResponse:
    """The nightly sync for this account's orders, now."""
    account = linked_account_or_404(request, pk)
    try:
        result = orders.sync_orders(paper_client(), account)
    except AlpacaError as error:
        messages.error(request, error.message)
    else:
        messages.info(
            request,
            f"Checked {result.checked} open order{'' if result.checked == 1 else 's'}: "
            f"{result.filled} filled, {result.still_open} still open.",
        )
        for client_order_id, message in result.failed.items():
            messages.error(request, f"{client_order_id}: {message}")
    return redirect("paper-account", pk=account.pk)
```

`linked_account_or_404` is chapter 08's ownership query plus `alpaca_allowed`. Confirm and the sync are POST
only, behind `login_required` on top so a visitor is sent to the sign-in rather than told the method is not
allowed. Every `AlpacaError` becomes a message through Django's messages framework, as chapter 09's watch list
reported its refusals.

The paper account page:

Listing 11-17, Filename: `src/invest_witus_site/paper/templates/paper/paper_account.html`:

```html
{% extends "pages/base.html" %}
{% load holdings_extras %}
{% block title %}Alpaca paper: {{ account.name }}: Invest.WitUS{% endblock %}
{% block content %}
<section class="container" aria-labelledby="paper-heading">
  <p class="eyebrow">{{ account.name }} <span class="muted">({{ account.broker }})</span></p>
  <h1 id="paper-heading">Alpaca paper</h1>
  {# The environment as text (PRD 7.2 and 7.7): the host beside it, and the line about live trading. #}
  <p class="band">Alpaca paper ({{ host }}). Paper money. Live trading needs the checklist in a later chapter and separate keys.</p>
  {% if error %}
  <p class="error">Alpaca did not answer. {{ error }}</p>
  {% endif %}

  <h2>Practice budget</h2>
  {% if plan %}
  <dl class="status" aria-label="Practice budget">
    <dt>Budget</dt><dd>{% if plan.practice_budget is not None %}{{ plan.practice_budget|plain_number }}{% else %}not set{% endif %}</dd>
    <dt>Spent</dt><dd>{{ spent|plain_number }}</dd>
    <dt>Plan</dt><dd>{{ plan.amount|plain_number }} into {{ plan.symbols }} within the first {{ plan.buy_window_days }} days of each month</dd>
  </dl>
  <p>The budget is the app's own number. Alpaca's paper balance cannot be set, so the plan spends from this budget and Alpaca's cash below is not the plan's.</p>
  {% else %}
  <p>No method runs on this account. <a href="{% url 'method-page' account.pk %}?view=c">Start one</a>, with a practice budget.</p>
  {% endif %}

  {% if alpaca_account %}
  <h2>Alpaca's account</h2>
  <dl class="status" aria-label="Alpaca's paper account">
    <dt>Cash</dt><dd>{{ alpaca_account.cash|plain_number }}</dd>
    <dt>Buying power</dt><dd>{{ alpaca_account.buying_power|plain_number }}</dd>
    <dt>Equity</dt><dd>{{ alpaca_account.equity|plain_number }}</dd>
    <dt>Status</dt><dd>{{ alpaca_account.status }}{% if alpaca_account.trading_blocked %}, trading blocked{% endif %}</dd>
  </dl>

  <h2>Positions</h2>
  {% if positions %}
  <table class="holdings">
    <caption class="sr-only">Positions on Alpaca's paper account, as Alpaca reports them</caption>
    <thead>
      <tr>
        <th scope="col">Symbol</th>
        <th scope="col" class="num">Shares</th>
        <th scope="col" class="num">Price</th>
        <th scope="col" class="num">Last close</th>
        <th scope="col" class="num">Value</th>
      </tr>
    </thead>
    <tbody>
      {% for position in positions %}
      <tr>
        <th scope="row">{{ position.symbol }}</th>
        <td class="num">{{ position.qty|plain_number }}</td>
        <td class="num">{{ position.current_price|plain_number }}</td>
        <td class="num">{{ position.lastday_price|plain_number }}</td>
        <td class="num">{{ position.market_value|plain_number }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p>No positions yet.</p>
  {% endif %}
  {% endif %}

  <h2>Orders the app placed</h2>
  {% if orders %}
  <table class="holdings">
    <caption class="sr-only">Every paper order this app placed for the account, newest month first</caption>
    <thead>
      <tr>
        <th scope="col">Month</th>
        <th scope="col">Symbol</th>
        <th scope="col" class="num">Amount</th>
        <th scope="col">Status</th>
        <th scope="col" class="num">Shares filled</th>
        <th scope="col">Order id</th>
      </tr>
    </thead>
    <tbody>
      {% for order in orders %}
      <tr>
        <th scope="row">{{ order.month }}</th>
        <td>{{ order.symbol }}</td>
        <td class="num">{{ order.notional|plain_number }}</td>
        <td>{{ order.status }}{% if order.message %}: {{ order.message }}{% endif %}</td>
        <td class="num">{{ order.filled_qty|plain_number }}</td>
        <td>{{ order.alpaca_id|default:"none yet" }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p>No orders yet. The method page's Confirm button places this month's buys.</p>
  {% endif %}
  <form method="post" action="{% url 'paper-sync' account.pk %}">
    {% csrf_token %}
    <button type="submit">Check orders now</button>
  </form>
  <p class="small muted">{{ paper_limits }} Information, not advice.</p>
  <p><a href="{% url 'method-page' account.pk %}">The method page</a> · <a href="{% url 'account-detail' account.pk %}">Back to the account</a></p>
</section>
{% endblock %}
```

The band at the top is the line the PRD asks for, with the host printed beside the environment: "Paper money.
Live trading needs the checklist in a later chapter and separate keys." The practice budget comes before
Alpaca's account, and the paragraph between them says which number is the plan's.

The box on the method page:

Listing 11-18, Filename: `src/invest_witus_site/paper/templates/paper/_month_buys.html`:

```html
{% load holdings_extras %}
{# This month's buys (chapter 11), on the method page of an account linked to Alpaca paper. Included by #}
{# methods/method_page.html with `account` and `paper` (a PaperSection: the staged buys, the clock, an error). #}
<section class="card" aria-labelledby="buys-heading">
  <h2 id="buys-heading">This month's buys</h2>
  <p class="band">Alpaca paper ({{ paper.host }}). Paper money. Live trading needs the checklist in a later chapter and separate keys.</p>
  <ul>
    {% for buy in paper.stage.buys %}
    <li>Buy {{ buy.notional|plain_number }} of {{ buy.symbol }}{% if buy.placed %}: placed, {{ buy.order.status }}{% elif buy.order.message %}: not placed. {{ buy.order.message }}{% endif %}</li>
    {% endfor %}
  </ul>
  <p>Practice budget, the app's own number: {% if paper.stage.budget is not None %}{{ paper.stage.budget|plain_number }}, spent {{ paper.stage.spent|plain_number }}, left {{ paper.stage.left|plain_number }}{% else %}not set{% endif %}.</p>
  {% if paper.error %}
  <p class="error">Alpaca did not answer, so nothing can be placed now. {{ paper.error }}</p>
  {% elif paper.stage.refusal %}
  <p>{{ paper.stage.refusal }}</p>
  {% elif paper.stage.can_confirm %}
  {% if not paper.clock.is_open %}
  <p>The market is closed. Alpaca queues a day order placed now for the next open, {{ paper.clock.next_open|date:"Y-m-d H:i e" }}.{% if paper.queues_past_window %} That open is after this month's window closes on {{ paper.stage.window_closes|date:"Y-m-d" }}; the journal records the day you confirm, and the fill's day goes in its note.{% endif %}</p>
  {% endif %}
  <form method="post" action="{% url 'paper-confirm' account.pk %}">
    {% csrf_token %}
    <button type="submit">{% if paper.clock.is_open %}Confirm{% else %}Confirm: queue for the open{% endif %}</button>
  </form>
  <p class="small muted">One market order per symbol for the dollar amount, good for the day, on Alpaca's paper account. Each order goes in the journal at once; the nightly check fills in the shares.</p>
  {% else %}
  <p>This month's buys are placed. The nightly check copies the fills into the journal. <a href="{% url 'paper-account' account.pk %}">See the orders</a>.</p>
  {% endif %}
</section>
```

The button's label is the market's state. `|date:"Y-m-d H:i e"` prints the next open in the site's time zone,
UTC, with its name, so "2026-11-04 14:30 UTC" is the 09:30 Eastern open Alpaca sent as `-05:00`.

Three files from chapter 10 change by a few lines each. The method page's view builds the box when the account
is linked:

Listing 11-19, Filename: `src/invest_witus_site/methods/views.py`:

```python
"""The method page for one account, in three views, and its two POST actions.

`method_page` renders the same context through one of three templates, A, B or C, named as the
research named them (`docs/research/01-ux-benchmarks-and-three-directions.md`, section 5). The
choice comes from `?view=a|b|c`, is remembered in the session, and defaults to A when the
account runs a method and to C when it does not (PRD 7.2: C to start a method, A as the home).
Every view sits behind `login_required` and the same ownership query as chapter 08's pages, so
another owner's account is a 404; nothing here is public.
"""

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from invest_witus.methods.rulebook import available_methods
from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.engine import build_review, rule_lines
from invest_witus_site.methods.forms import JournalEntryForm, StartMethodForm
from invest_witus_site.methods.models import JournalEntry, MethodPlan
from invest_witus_site.paper.orders import alpaca_allowed, paper_section

# The three views, by letter, as the research and the PRD name them. The order is the switch's.
VIEWS = {
    "a": ("A: The Plan and the Logbook", "methods/_view_a.html"),
    "b": ("B: Method Console", "methods/_view_b.html"),
    "c": ("C: The Lesson Lab", "methods/_view_c.html"),
}
SESSION_KEY = "method_view"


def chosen_view(request: HttpRequest, has_plan: bool) -> str:
    """`?view=` when it names a view (and remember it); else the session's; else the default."""
    asked = request.GET.get("view", "").lower()
    if asked in VIEWS:
        request.session[SESSION_KEY] = asked
        return asked
    saved = request.session.get(SESSION_KEY)
    if isinstance(saved, str) and saved in VIEWS:
        return saved
    return "a" if has_plan else "c"


def through_date(request: HttpRequest, today: date) -> date:
    """`?through=YYYY-MM-DD` reviews up to that day, as chapter 03's command did; anything else
    is today. The page says which day it was reviewed through."""
    try:
        return date.fromisoformat(request.GET.get("through", ""))
    except ValueError:
        return today


@login_required
def method_page(request: HttpRequest, pk: int) -> HttpResponse:
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    return render_method_page(request, account)


def render_method_page(
    request: HttpRequest,
    account: Account,
    start_form: StartMethodForm | None = None,
    entry_form: JournalEntryForm | None = None,
    force_view: str | None = None,
) -> HttpResponse:
    """One context, three templates. The ownership check is the caller's. The two POST views
    render the page again through this function, with a bound form, when a submission fails."""
    today = timezone.localdate()
    through = through_date(request, today)
    plan = MethodPlan.active_for(account)
    entries = JournalEntry.entries_for(account)
    view = force_view or chosen_view(request, plan is not None)
    context = {
        "account": account,
        "plan": plan,
        "review": build_review(plan, entries, through) if plan is not None else None,
        "entries": entries,
        "catalog": [(method, rule_lines(method)) for method in available_methods()],
        "start_form": start_form or StartMethodForm(account),
        "entry_form": entry_form or JournalEntryForm(initial={"date": today}),
        "view": view,
        "view_label": VIEWS[view][0],
        "view_template": VIEWS[view][1],
        "views": [(key, label) for key, (label, _) in VIEWS.items()],
        "through": through,
        "through_query": f"&through={through.isoformat()}" if through != today else "",
        # Chapter 11: this month's buys and the Confirm button, on an account linked to Alpaca
        # paper only. One request to Alpaca (the clock); `None` everywhere else.
        "paper": (
            paper_section(plan)
            if plan is not None and alpaca_allowed(request.user, account)
            else None
        ),
    }
    return render(request, "methods/method_page.html", context)


@login_required
@require_POST
def start_method(request: HttpRequest, pk: int) -> HttpResponse:
    """Create the plan. A refused form draws view C again with the reasons beside the boxes;
    a started method goes to view A, the everyday home, and the session remembers it."""
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    form = StartMethodForm(account, request.POST)
    if not form.is_valid():
        return render_method_page(request, account, start_form=form, force_view="c")
    plan = form.start()
    messages.success(request, f"Started {plan.method().name} on {account.name}.")
    request.session[SESSION_KEY] = "a"
    return redirect("method-page", pk=account.pk)


@login_required
@require_POST
def log_entry(request: HttpRequest, pk: int) -> HttpResponse:
    """Add one journal row to the account and come back to the same view."""
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    form = JournalEntryForm(request.POST)
    if not form.is_valid():
        return render_method_page(request, account, entry_form=form)
    entry = form.save(commit=False)
    entry.account = account
    entry.save()
    messages.success(request, f"Logged: {entry}.")
    return redirect("method-page", pk=account.pk)
```

Listing 11-20, Filename: `src/invest_witus_site/methods/templates/methods/method_page.html`:

```html
{% extends "pages/base.html" %}
{% load holdings_extras %}
{% block title %}{% if plan %}{{ review.method.name }}{% else %}Start a method{% endif %}: {{ account.name }}: Invest.WitUS{% endblock %}
{% block content %}
<section class="container" aria-labelledby="method-heading">
  <p class="eyebrow">{{ account.name }} <span class="muted">({{ account.broker }})</span></p>
  <h1 id="method-heading">{% if plan %}{{ review.method.name }}{% else %}Start a method{% endif %}</h1>
  {# The environment, as text, on every signed-in page (PRD 7.2). The account's kind is what chapter 05 stored. #}
  <p class="band">{{ account.get_kind_display }} account. {% if account.kind == "paper" %}Simulated money: nothing here is a real trade.{% else %}Entered by hand from statements: the app places no order.{% endif %} Information, not advice.</p>
  {% include "methods/_switch.html" %}
  {# Chapter 11: on an account linked to Alpaca paper, this month's buys and the Confirm button. #}
  {% if paper %}{% include "paper/_month_buys.html" %}{% endif %}
  {# The same context, one of three arrangements (chapter 10). The view's letter is the research's. #}
  {% include view_template %}
  <p><a href="{% url 'account-detail' account.pk %}">Back to the account</a></p>
</section>
{% endblock %}
```

Listing 11-21, Filename: `src/invest_witus_site/methods/forms.py`:

```python
"""Two forms on the method page: start a method for an account, and log one journal entry."""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any

from django import forms
from django.core.exceptions import ValidationError

from invest_witus.methods.rulebook import available_methods
from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.models import (
    MAX_WINDOW_DAYS,
    MIN_WINDOW_DAYS,
    ONE_CENT,
    JournalEntry,
    MethodPlan,
    join_symbols,
    validate_symbol_list,
)

SYMBOL_BOX = {"autocomplete": "off", "autocapitalize": "characters", "spellcheck": "false"}


def method_choices() -> list[tuple[str, str]]:
    """The methods the package ships, read when the form is built, never typed into the form.
    Today that is one; a second rules file is a second option with no change here."""
    return [(method.id, method.name) for method in available_methods()]


class StartMethodForm(forms.Form):
    """The plan's numbers. The method is a choice from the package; the symbols go through
    chapter 09's rule; the account is the view's, not a field. Valid only while the account
    runs no method, which `clean()` checks and the database's partial unique constraint backs."""

    method_id = forms.ChoiceField(label="Method", choices=method_choices)
    amount = forms.DecimalField(
        label="Amount each month",
        min_value=ONE_CENT,
        max_digits=14,
        decimal_places=2,
        help_text="In dollars, to the cent.",
    )
    buy_window_days = forms.IntegerField(
        label="Buy window, in days",
        min_value=MIN_WINDOW_DAYS,
        max_value=MAX_WINDOW_DAYS,
        initial=7,
        help_text="Buy within the first N days of each month; 1 to 28.",
    )
    symbols = forms.CharField(
        label="Symbols",
        max_length=200,
        widget=forms.TextInput(attrs=SYMBOL_BOX),
        help_text="The fund or funds the plan names, separated by commas or spaces.",
    )
    started_on = forms.DateField(
        label="Start", widget=forms.DateInput(attrs={"type": "date"}), initial=date.today
    )
    # Chapter 11: optional, and used only on an account linked to Alpaca paper, where Confirm
    # refuses buys beyond what is left of it.
    practice_budget = forms.DecimalField(
        label="Practice budget",
        required=False,
        min_value=ONE_CENT,
        max_digits=14,
        decimal_places=2,
        help_text="Paper accounts only: the practice money this plan may spend. Optional.",
    )

    def __init__(self, account: Account, data: Mapping[str, Any] | None = None) -> None:
        super().__init__(data)
        self.account = account

    def clean_symbols(self) -> str:
        """The box as the stored list: each symbol normalized, once, joined by spaces. A refused
        token is a form error naming it; a plan with a typo in its universe would flag every buy."""
        text: str = self.cleaned_data["symbols"]
        validate_symbol_list(text)
        return join_symbols(text)

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean() or {}
        if MethodPlan.active_for(self.account) is not None:
            raise ValidationError(
                "This account already runs a method. End it in the admin before starting another."
            )
        return cleaned

    def start(self) -> MethodPlan:
        """The row. Called after `is_valid()`; the model's `save()` normalizes once more."""
        amount: Decimal = self.cleaned_data["amount"]
        return MethodPlan.objects.create(
            account=self.account,
            method_id=self.cleaned_data["method_id"],
            amount=amount,
            buy_window_days=self.cleaned_data["buy_window_days"],
            symbols=self.cleaned_data["symbols"],
            started_on=self.cleaned_data["started_on"],
            practice_budget=self.cleaned_data["practice_budget"],
        )


class JournalEntryForm(forms.ModelForm[JournalEntry]):
    """One row of the journal, as a `ModelForm`: the fields, their labels, help and validators
    come from the model, so the symbol rule and the one-cent minimum run here before `save()`
    runs them again. The account is set by the view."""

    class Meta:
        model = JournalEntry
        fields = ["date", "action", "symbol", "amount", "shares", "note"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "symbol": forms.TextInput(attrs=SYMBOL_BOX),
        }
```

The start form gains one optional field, the practice budget; chapter 10's tests post the form without it and
still pass. The account page links the paper page for the site owner:

Listing 11-22, Filename: `src/invest_witus_site/holdings/templates/holdings/account_detail.html`:

```html
{% extends "pages/base.html" %}
{% load holdings_extras %}
{% block title %}{{ account.name }}: Invest.WitUS{% endblock %}
{% block content %}
<section class="container" aria-labelledby="account-heading">
  <p class="eyebrow">Your account</p>
  <h1 id="account-heading">{{ account.name }} <span class="muted">({{ account.broker }})</span></h1>
  {% if snapshot %}
  <p>Statement as of {{ snapshot.as_of|date:"Y-m-d" }}{% if snapshot.source %} ({{ snapshot.source }}){% endif %}. Each line is valued at the latest close the app has stored for its symbol, with that close's date and source beside it; a close older than five days is marked stale. Information, not advice.</p>
  <table class="holdings">
    <caption class="sr-only">Holdings on the latest statement, valued at the latest stored close</caption>
    <thead>
      <tr>
        <th scope="col">Symbol</th>
        <th scope="col" class="num">Shares</th>
        <th scope="col" class="num">Close</th>
        <th scope="col">As of</th>
        <th scope="col">Source</th>
        <th scope="col" class="num">Value</th>
      </tr>
    </thead>
    <tbody>
      {% for line in valuation.lines %}
      <tr>
        <th scope="row">{{ line.symbol }}</th>
        <td class="num">{{ line.shares|plain_number }}</td>
        {% if line.quote %}
        <td class="num">{{ line.quote.close|plain_number }}</td>
        <td>{{ line.quote.as_of|date:"Y-m-d" }}{% if line.stale %} <span class="stale">stale</span>{% endif %}</td>
        <td>{{ line.quote.source }}</td>
        <td class="num">{{ line.value|plain_number }}</td>
        {% else %}
        <td class="muted" colspan="4">no price yet</td>
        {% endif %}
      </tr>
      {% endfor %}
    </tbody>
    <tfoot>
      <tr>
        <th scope="row" colspan="5">Total of the priced lines</th>
        <td class="num">{{ valuation.total|plain_number }}</td>
      </tr>
    </tfoot>
  </table>
  {% if valuation.unpriced %}
  <p class="muted">No price yet for {{ valuation.unpriced|join:", " }}: the nightly pull has not stored a close for {{ valuation.unpriced|length|pluralize:"it,them" }}. A symbol the price source does not know stays unpriced; the pull's log names it.</p>
  {% endif %}
  {% else %}
  <p>No statement yet.{% if user.is_staff %} <a href="{% url 'admin:holdings_snapshot_add' %}?account={{ account.pk }}">Enter the first one in the admin.</a>{% endif %}</p>
  {% endif %}
  {# The method (chapter 10): one line naming it, or the invitation to start one; the method page has the rest. #}
  <section class="method-line" aria-labelledby="method-line-heading">
    <h2 id="method-line-heading">Method</h2>
    {% if method_plan %}
    <p><a href="{% url 'method-page' account.pk %}">{{ method_plan.method.name }}</a>: {{ method_plan.amount|plain_number }} into {{ method_plan.symbols }} within the first {{ method_plan.buy_window_days }} day{{ method_plan.buy_window_days|pluralize }} of each month, since {{ method_plan.started_on|date:"Y-m-d" }}. The rules, the review and the journal are on the method page.</p>
    {% else %}
    <p>No method yet on this account. <a href="{% url 'method-page' account.pk %}?view=c">Read the rules and start one.</a></p>
    {% endif %}
  </section>
  {# Alpaca paper (chapter 11): the link to Alpaca's positions, cash and orders, for the site owner. #}
  {% if account.is_alpaca_paper and user.is_superuser %}
  <section aria-labelledby="paper-line-heading">
    <h2 id="paper-line-heading">Alpaca paper</h2>
    <p><a href="{% url 'paper-account' account.pk %}">Positions, cash and orders on Alpaca paper</a>. Paper money. Live trading needs the checklist in a later chapter and separate keys.</p>
  </section>
  {% endif %}
  {# The watch list (chapter 09): the symbols followed here, the latest close beside each, the add form. #}
  {% include "watchlist/_section.html" %}
  <p><a href="{% url 'account-list' %}">All accounts</a></p>
</section>
{% endblock %}
```

And the admin: the orders read-only, the new columns in two lists.

Listing 11-23, Filename: `src/invest_witus_site/paper/admin.py`:

```python
"""The paper orders in the admin, read-only: Alpaca's answers are copied in by the app, never
typed, so a hand edit could only make the row disagree with Alpaca."""

from django.contrib import admin
from django.http import HttpRequest

from invest_witus_site.paper.models import PaperOrder


@admin.register(PaperOrder)
class PaperOrderAdmin(admin.ModelAdmin[PaperOrder]):
    list_display = ("month", "symbol", "notional", "status", "filled_qty", "account", "alpaca_id")
    list_filter = ("account", "status")
    search_fields = ("client_order_id", "alpaca_id", "symbol")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: PaperOrder | None = None) -> bool:
        return False
```

Listing 11-24, Filename: `src/invest_witus_site/methods/admin.py`:

```python
"""The plans and the journal in the admin. The owner's page is where both are kept; the admin is
where a plan is ended (`active` off) until chapter 12 gives a change of plan its own form."""

from django.contrib import admin

from invest_witus_site.methods.models import JournalEntry, MethodPlan


@admin.register(MethodPlan)
class MethodPlanAdmin(admin.ModelAdmin[MethodPlan]):
    list_display = (
        "method_id",
        "account",
        "amount",
        "symbols",
        "buy_window_days",
        "started_on",
        "practice_budget",
        "active",
    )
    list_editable = ("active",)
    list_filter = ("account", "active")
    readonly_fields = ("created_at",)


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin[JournalEntry]):
    list_display = ("date", "account", "action", "symbol", "amount", "shares", "note")
    list_filter = ("account", "action")
    date_hierarchy = "date"
    search_fields = ("symbol", "note")
    readonly_fields = ("created_at",)
```

In `src/invest_witus_site/holdings/admin.py`, chapter 05's `AccountAdmin.list_display` gains `"alpaca"` after
`"kind"`; nothing else in that file changes.

### 11.7 The nightly step and the command

Listing 11-25, Filename: `src/invest_witus_site/prices/views.py`:

```python
"""`GET /api/cron/pull-prices/`: the nightly pull, called by Vercel's cron, and since chapter 11
the paper order check after it.

Vercel sends the project's `CRON_SECRET` as `Authorization: Bearer <value>` with every cron
request (its docs, read October 28, 2026). The route compares that header with the setting in
constant time and answers 403 to anything else. With no secret configured it answers 503 and runs
nothing: a deploy that forgot the variable fails closed instead of pulling for anyone who asks.
"""

import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from invest_witus_site.paper.alpaca import AlpacaError, keys_configured, paper_client
from invest_witus_site.paper.orders import sync_orders
from invest_witus_site.prices.pull import DAYS_BACK, pull, symbol_universe
from invest_witus_site.prices.sources import source_from_settings

log = logging.getLogger(__name__)


def bearer_matches(header: str, secret: str) -> bool:
    """`compare_digest` takes the same time whether the first or the last byte differs."""
    return secrets.compare_digest(header.encode("utf-8"), f"Bearer {secret}".encode())


@never_cache
@require_GET
def pull_prices_cron(request: HttpRequest) -> JsonResponse:
    secret = settings.CRON_SECRET
    if not secret:
        log.error("cron: CRON_SECRET is not set; the pull did not run")
        return JsonResponse({"error": "CRON_SECRET is not set"}, status=503)
    if not bearer_matches(request.headers.get("Authorization", ""), secret):
        return JsonResponse({"error": "forbidden"}, status=403)
    today = timezone.localdate()
    result = pull(
        source_from_settings(), symbol_universe(), today - timedelta(days=DAYS_BACK), today
    )
    body = result.as_dict()
    # Chapter 11: then the paper orders, once the owner's Alpaca paper keys are set. Without them
    # the body is chapter 08's, unchanged. A failure is reported in the body; the prices stand.
    if keys_configured():
        try:
            body["orders"] = sync_orders(paper_client()).as_dict()
        except AlpacaError as error:
            body["orders"] = {"error": error.message}
    # Which schedule fired, when more than one cron shares a path; empty for a call by hand.
    body["schedule"] = request.headers.get("x-vercel-cron-schedule", "")
    log.info("cron: pull-prices %s", body)
    return JsonResponse(body)
```

Listing 11-26, Filename: `src/invest_witus_site/paper/management/commands/sync_paper_orders.py`:

```python
"""`manage.py sync_paper_orders`: read every open paper order back from Alpaca and fix the rows
and their journal entries. The nightly cron runs the same function after the price pull."""

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from invest_witus_site.paper.alpaca import AlpacaError, keys_configured, paper_client
from invest_witus_site.paper.orders import sync_orders


class Command(BaseCommand):
    help = "Update open Alpaca paper orders to filled or cancelled, and their journal entries."

    def handle(self, *args: Any, **options: Any) -> None:
        if not keys_configured():
            self.stdout.write("Alpaca paper keys are not set; nothing to sync.")
            return
        try:
            result = sync_orders(paper_client())
        except AlpacaError as error:
            raise CommandError(error.message) from None
        self.stdout.write(
            f"Checked {result.checked}, changed {result.changed}: {result.filled} filled, "
            f"{result.ended_part_filled} ended part filled, {result.ended_unfilled} ended "
            f"unfilled, {result.still_open} still open."
        )
        for client_order_id, message in result.failed.items():
            self.stderr.write(f"Failed {client_order_id}: {message}")
```

The cron step sits after the pull and inside `if keys_configured()`, so chapter 08's test of the exact JSON body
still passes on a copy with no keys. A failure reading orders goes into the body as `{"error": ...}` and the
prices stay stored.

### 11.8 The two names in `.env.example`

Listing 11-27, Filename: `.env.example`:

```sh
# Copy to .env (git ignores it) and run with: uv run --env-file .env python manage.py runserver
# Names only; values never go in git. On Vercel the same names are set in the project's
# Environment Variables page (chapter 06); the laptop and the server share one settings file.

# "1" shows Django's debug pages and serves static files from runserver. Never "1" on a server:
# settings.py refuses to start on Vercel with it set.
DJANGO_DEBUG=1

# Required whenever DJANGO_DEBUG is not 1, which is every server. Make one with:
#   uv run python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
# Leave empty on your laptop: with DJANGO_DEBUG=1 a labeled dev-only key is used instead.
DJANGO_SECRET_KEY=

# Comma-separated host names the site answers to. Default: localhost,127.0.0.1
# Production: invest.witus.online (Vercel's own *.vercel.app host names are added on their own).
DJANGO_ALLOWED_HOSTS=

# Comma-separated origins, scheme and host, that may post the site's forms.
# Production: https://invest.witus.online
DJANGO_CSRF_TRUSTED_ORIGINS=

# The database. Empty: SQLite at data/private/invest-witus.sqlite3. On Vercel the Neon integration
# sets both names: DATABASE_URL is the pooled connection the app uses, DATABASE_URL_UNPOOLED the
# direct one that migrations use (`manage.py migrate --database direct`).
# Shape: postgresql://user:password@host/name?sslmode=require
# If the Vercel connect dialog added a prefix (the production project has STORAGE_), the
# prefixed names STORAGE_DATABASE_URL and STORAGE_DATABASE_URL_UNPOOLED work too.
DATABASE_URL=
DATABASE_URL_UNPOOLED=

# The owner's one-time, non-interactive superuser on a new database (chapter 06). These three are
# set in the shell for that one command, never written to a file:
#   DJANGO_SUPERUSER_USERNAME  DJANGO_SUPERUSER_EMAIL  DJANGO_SUPERUSER_PASSWORD
#   ... vercel env run -e production -- uv run python manage.py createsuperuser --noinput --database direct

# Vercel Web Analytics (chapter 06a). Both are set on Vercel, per environment, never on a laptop: the
# two script tags render only with VERCEL=1 (Vercel's own variable) and VERCEL_ANALYTICS=1, so
# Production can be on while Preview stays off. VERCEL_ANALYTICS_SCRIPT_PATH is the script path the
# project's Analytics page shows once Analytics is enabled (the quickstart writes it as
# /<unique-path>/script.js): copy it from there. Left empty, the FALLBACK /_vercel/insights/script.js
# is used, the shared route the quickstart names, not a value read from your dashboard. If the
# dashboard shows no page views after a deploy, set the path to what the page shows.
VERCEL_ANALYTICS=
VERCEL_ANALYTICS_SCRIPT_PATH=

# Sign in with WitUS (chapter 07): OpenID Connect against the ecosystem's identity provider. The
# client is OFF until WITUS_OIDC_CLIENT_SECRET is set; until then the sign-in route shows the stub
# page from chapter 04 and the site deploys as before. The owner mints the secret in the witus repo
# (`node scripts/gen-oidc-client.mjs invest`), which prints one value for the provider
# (WITUS_OIDC_SECRET__INVEST, on witus-online) and the same value for this app. Mark it Secret on
# Vercel. A learner's copy of the app is not registered with the provider and leaves it empty.
WITUS_OIDC_CLIENT_SECRET=
# The issuer the provider asserts in its discovery document. Default: https://accounts.witus.online,
# the ecosystem's accounts host as read on October 28, 2026. The discovery document is read from
# under it, and its own `issuer` field must match.
WITUS_OIDC_ISSUER=
# This app's client id at the provider. Default: witus-invest (the registry's `witus-<slug>`).
WITUS_OIDC_CLIENT_ID=
# The scopes asked for. Default: openid email profile. `openid` is required.
WITUS_OIDC_SCOPES=

# Prices (chapter 08). The nightly pull stores one close per symbol per day. With TIINGO_API_KEY
# set it asks Tiingo's end-of-day endpoint with your own token (https://www.tiingo.com/signup,
# then https://www.tiingo.com/account/api/token; the free plan allows 50 requests an hour, 1,000 a
# day and 500 unique symbols a month, "Internal Use Only", as read on October 28, 2026). Left
# empty, the pull reads <SYMBOL>.csv files in chapter 02's format from data/private/prices/
# (PRICES_CSV_DIR changes the folder), which is what a laptop uses.
TIINGO_API_KEY=
PRICES_CSV_DIR=
# What Vercel sends as "Authorization: Bearer <value>" to /api/cron/pull-prices/ once a day
# (vercel.json). Set it on Vercel only, Production, marked Sensitive; at least 16 random
# characters, for example: openssl rand -hex 24
# Unset, the route answers 503 and runs nothing, so a deploy without it fails closed.
CRON_SECRET=

# Alpaca paper trading (chapter 11). Your own PAPER keys: log in at https://app.alpaca.markets,
# switch the environment to paper in the top bar, then API Keys on the right of the dashboard,
# Generate New Key (Alpaca's "API key security" article, read October 29, 2026). The secret is
# shown once. Set both on Vercel as Sensitive, Production only. Empty: every Alpaca feature says
# the keys are not set and nothing is called. The host is fixed to paper-api.alpaca.markets in the
# code and is not a variable; APCA_API_BASE_URL, if set at all, must be that host or the settings
# refuse to start. Live keys never go here: live trading is not built.
ALPACA_PAPER_KEY_ID=
ALPACA_PAPER_SECRET_KEY=
```

The comment gives the dashboard path from Alpaca's own article, says the secret is shown once, and says what an
empty value does.

### 11.9 Green, and a confirm on your laptop against the fake

Listing 11-28, Terminal:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

```text
366 passed in 8.82s
All checks passed!
166 files already formatted
0 errors, 0 warnings, 0 informations
```

Fifty-four new tests. Migrate the laptop database:

Listing 11-29, Terminal:

```sh
uv run --env-file .env python manage.py migrate
```

```text
Operations to perform:
  Apply all migrations: accounts, admin, auth, contenttypes, holdings, methods, pages, paper, prices, sessions, watchlist
Running migrations:
  Applying holdings.0002_account_alpaca... OK
  Applying methods.0002_methodplan_practice_budget... OK
  Applying paper.0001_initial... OK
```

Link the account from chapter 10 and give its plan a budget. In the admin that is the account's **Kind**, set to
Paper (practice) if it is not already, its new **Alpaca** field, set to Alpaca paper, and the plan's **Practice
budget**. The same through the shell, for an account named `Practice` (use yours):

Listing 11-30, Terminal:

```sh
DJANGO_DEBUG=1 DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -v 0 -c "from decimal import Decimal; from invest_witus_site.holdings.models import Account; from invest_witus_site.methods.models import MethodPlan; a = Account.objects.get(name='Practice'); a.kind = 'paper'; a.alpaca = 'paper'; a.full_clean(); a.save(); p = MethodPlan.active_for(a); p.practice_budget = Decimal('1200'); p.full_clean(); p.save(); print(a.get_kind_display(), '/', a.get_alpaca_display(), '/', p.practice_budget)"
```

```text
Paper (practice) / Alpaca paper / 1200.00
```

`-v 0` keeps Django 5.2's shell from printing the list of names it imports for you. Now the whole confirm,
against the test file's fake Alpaca and with made-up keys, so nothing leaves your machine. The day is pinned to
November 3, 2026, inside the window of chapter 10's plan (days 1 to 7):

Listing 11-31, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
ALPACA_PAPER_KEY_ID=made-up-id ALPACA_PAPER_SECRET_KEY=made-up-secret \
uv run python manage.py shell -v 0 -c "
import re
from datetime import date
import httpx
from django.contrib.auth.models import User
from django.test import Client
from invest_witus_site.holdings.models import Account
from invest_witus_site.paper import alpaca, orders
from tests.test_ch11 import FakeAlpaca, text
fake = FakeAlpaca(); alpaca.transport = httpx.MockTransport(fake.handle); orders.today = lambda: date(2026, 11, 3)
u = User.objects.get(is_superuser=True); a = Account.objects.get(owner=u, alpaca='paper'); c = Client(); c.force_login(u)
box = text(c.get(f'/accounts/{a.pk}/method/')).split('<h2 id=\"buys-heading\">')[1].split('</section>')[0]
print('\n'.join(re.sub(r'<[^>]+>', '', line).strip() for line in box.splitlines() if re.sub(r'<[^>]+>', '', line).strip()))
for click in (1, 2):
    page = text(c.post(f'/accounts/{a.pk}/paper/confirm/', follow=True))
    print(click, re.findall(r'class=\"message \w+\">([^<]+)<', page))
print(len(fake.posted), 'order sent:', fake.posted[0])
"
```

```text
This month's buys
Alpaca paper (paper-api.alpaca.markets). Paper money. Live trading needs the checklist in a later chapter and separate keys.
Buy 100.00 of INDEX
Practice budget, the app's own number: 1200.00, spent 200.00, left 1000.00.
Confirm
One market order per symbol for the dollar amount, good for the day, on Alpaca's paper account. Each order goes in the journal at once; the nightly check fills in the shares.
1 ['Placed: buy 100.00 of INDEX, accepted.']
2 ['Already placed: INDEX, accepted. Nothing new sent.']
1 order sent: {'symbol': 'INDEX', 'side': 'buy', 'type': 'market', 'time_in_force': 'day', 'notional': '100.00', 'client_order_id': 'iw-1-1-2026-11-INDEX'}
```

Spent is 200.00 because chapter 10's two logged buys count against the plan's budget. Two clicks, one order
sent, and its id is made of the account, the plan, the month and the symbol (your ids may differ). Then the
sync, against a fresh fake that has the order and has filled it:

Listing 11-32, Terminal:

```sh
DJANGO_DEBUG=1 DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
ALPACA_PAPER_KEY_ID=made-up-id ALPACA_PAPER_SECRET_KEY=made-up-secret \
uv run python manage.py shell -v 0 -c "
import httpx
from django.core.management import call_command
from invest_witus_site.paper import alpaca
from invest_witus_site.paper.models import PaperOrder
from tests.test_ch11 import FakeAlpaca
order = PaperOrder.objects.get()
fake = FakeAlpaca(); alpaca.transport = httpx.MockTransport(fake.handle)
fake.fill(fake.add_order(order.client_order_id), qty='0.496277915', price='201.5')
print(order.client_order_id, order.status, order.journal_entry)
call_command('sync_paper_orders')
call_command('sync_paper_orders')
order.refresh_from_db(); entry = order.journal_entry
print(order.status, order.filled_qty, '|', entry, '|', entry.shares, '|', entry.note)
"
```

```text
iw-1-1-2026-11-INDEX accepted 2026-11-03 buy 100.00 of INDEX
Checked 1, changed 1: 1 filled, 0 ended part filled, 0 ended unfilled, 0 still open.
Checked 0, changed 0: 0 filled, 0 ended part filled, 0 ended unfilled, 0 still open.
filled 0.496277915 | 2026-11-03 buy 100.00 of INDEX | 0.496277 | Alpaca paper order order-1: filled, 0.496277 shares at 201.5 on 2026-11-04
```

The first run fills the row and the entry; the second finds nothing open. Nine places on the order, six on the
journal, rounded down. Open view B of the method page under `runserver` and November reads done, with shares.

### 11.10 Your own Alpaca paper keys

This step talks to Alpaca for real, with your keys, on paper.

1. Sign in at https://app.alpaca.markets. In the top bar, make sure the environment is **paper**.
2. On the dashboard, the **API Keys** module is on the right. Press **Generate New Key** (Alpaca, 2026b). The
   modal shows the key id and the secret; the secret is shown once, so copy both now.
3. Put them in your `.env` as `ALPACA_PAPER_KEY_ID=` and `ALPACA_PAPER_SECRET_KEY=`. Never in a chat, a
   commit or a screenshot. If one leaks, generate a new pair, which replaces the old one.
4. Run `uv run --env-file .env python manage.py runserver`, sign in, and open the paper page from the account
   page's "Alpaca paper" section. It shows Alpaca's cash, buying power and equity, and no positions yet.
5. On the method page, inside your plan's window, press Confirm. `INDEX` is a placeholder, not a symbol you
   chose; if Alpaca refuses it, the box says "not placed" with Alpaca's reason in its own words, which is the
   vendor-error path, live. To place an order that fills, start a plan on this account with the fund your
   lesson names; this repository never names one.
6. Check the order in Alpaca's paper dashboard, then press **Check orders now** on the paper page, or run `uv
   run --env-file .env python manage.py sync_paper_orders`, after it fills.

Outside market hours the button reads "Confirm: queue for the open" and the order waits for the next open, as
Alpaca's day order does.

### 11.11 What the owner does outside the editor

The reference app's steps are task 16 in the owner's queue. A learner with a Vercel project of their own does
the same:

1. **Set the two keys on Vercel** (Settings, Environment Variables, Production, Sensitive) if they are not there
   yet, and redeploy once.
2. **Merge the chapter.** The migrate workflow from `docs/05-operations.md` applies the three migrations after the
   push to `main`; until it finishes, about a minute, pages that read accounts or plans answer 500.
3. **Link the paper account** in the admin: Kind, Paper (practice); Alpaca, Alpaca paper.
4. **Give the plan a budget,** or start one on that account with it: the method page's start form has the field.
5. **Press Confirm** in the next buy window, then check the order in Alpaca's paper dashboard and on the paper
   page. The nightly cron fills in the shares; "Check orders now" does it at once.

## Checkpoint

- `uv run pytest` prints `366 passed`; ruff and pyright pass.
- Listing 11-30 prints the paper kind, the Alpaca link and the budget.
- Listing 11-31 prints the box, one "Placed" message, one "Already placed" message and one order sent with
  `time_in_force` `day`.
- Listing 11-32 fills the order once and prints the shares on the journal entry.
- `AlpacaPaper("id", "secret", base_url="https://api.alpaca.markets")` raises `LiveHostRefused`.
- Signed out, every public page has no `<table`, no link to `/accounts/` or `/paper/`, and no "This month's
  buys"; signed in as anyone but the site owner, every paper route is a 404.
- Commit and push: `git add -A && git commit -m "Chapter 11: Alpaca paper trading and the monthly review"`.

## Exercises

1. Hold with a reason. Add a POST route `paper-hold` with a required reason that writes a journal note for the
   month instead of an order, and make `refusal_for` treat a held month as done. Write the test first.
2. Plan value from the app's own fills. On the paper page, add a line that values the plan's journal shares at
   chapter 08's latest stored close, with the close's date, and compare it with Alpaca's `market_value`. Decide,
   and write down, which number the page calls the plan's.
3. Cancel an order from the app. Alpaca documents `DELETE /v2/orders/{order_id}`; read its page, add
   `cancel(order_id)` to the client, a button on the paper page for an order that is not final, and a test with
   the fake. What should the journal entry do?
4. A second linked account. The partial unique constraint allows one per owner. Lift it, add an
   `alpaca_account_number` column checked against `GET /v2/account`'s `account_number`, and refuse an order when
   they differ. What does a second pair of keys need?

## If you get stuck

- Browse: https://github.com/dapperAuteur/invest-witus/tree/v11
- Diff for this chapter: https://github.com/dapperAuteur/invest-witus/compare/v10...v11
- Zip: https://github.com/dapperAuteur/invest-witus/archive/v11.zip
- Take the reference's files. Chapter 11 changed `src/invest_witus_site/settings.py`,
  `src/invest_witus_site/urls.py`, `holdings/models.py`, `holdings/admin.py`, the template
  `holdings/account_detail.html`, `methods/models.py`, `methods/forms.py`, `methods/views.py`, `methods/admin.py`,
  the template `methods/method_page.html`, `prices/views.py`, `.env.example` and `docs/site/privacy.md`, and
  added `src/invest_witus_site/paper/` (the whole app), `holdings/migrations/0002_account_alpaca.py`,
  `methods/migrations/0002_methodplan_practice_budget.py` and `tests/test_ch11.py`. No package changed, two
  environment variables were added, nothing moved:
  `git fetch reference --tags && git checkout v11 -- src tests .env.example docs/site/privacy.md`.
- `ModuleNotFoundError: No module named 'invest_witus_site.paper'` after 11.2: the folder is missing its
  `__init__.py`, or it was made inside another app.
- `test_the_settings_refuse_to_start_when_anything_points_at_the_live_host` raises `KeyError:
  'invest_witus_site.settings'`: the helper's `delitem` lacks `raising=False`.
- `test_the_client_refuses_the_live_host_and_any_other` builds a client for `http://paper-api...`: `check_host`
  compares the host and forgets the scheme.
- A test finds the secret in `repr(client)`: `__repr__` is missing, and the default prints the attributes.
- `test_vendor_errors_become_typed_exceptions_with_alpacas_words` gets `AlpacaRefused` for the 500: `refusal`
  checks `>= 400` before `>= 500`. The order is 404, 429, 5xx, then the rest.
- `test_no_answer_and_a_bad_body_are_unavailable` sees `cash` accepted as `True`: `optional_number` tests
  `isinstance(value, int)` before refusing `bool`.
- `test_every_paper_route_is_the_owners_alone` raises `IntegrityError` while creating the unlinked account: the
  partial unique constraint lacks its `condition`, so it is a plain unique on `owner`.
- `test_confirm_places_each_buy_once_and_writes_one_journal_entry` sends two orders: `month_buys` builds
  `existing` from another month, or `StagedBuy.placed` checks the row instead of its Alpaca id.
- `test_a_retry_finds_the_order_alpaca_already_has` sends a POST: `submit` was called with `look_first=created`
  instead of `not created`.
- `test_a_vendor_refusal_is_a_message_and_buys_nothing` finds no row: the message is saved inside the
  `with` block and the exception raised there too, which rolls the save back.
- `test_the_sync_fills_a_pending_order_and_fixes_its_journal_entry` prints `0.496278` shares: the journal used
  `to_money` or `round`; shares round down through `to_shares`.
- `test_an_order_that_ends_unfilled_leaves_no_journal_entry` raises on `entry.delete()`: the order still points
  at the entry. Clear `order.journal_entry` and save the order first.
- `test_the_cron_route_pulls_the_last_seven_days_and_answers_counts` (chapter 08) fails with an extra `orders`
  key: the cron step runs without checking `keys_configured()`.
- `test_every_paper_route_is_the_owners_alone` gets 200 for the plain user: `alpaca_allowed` does not check
  `is_superuser`.
- `test_a_two_symbol_plan_shows_the_split_without_a_confirm_button` finds "Confirm": `refusal_for` has no
  symbol-count check, so a two-symbol plan with a budget is offered the button.
- A circular import at startup naming `methods.views` and `paper.views`: `methods/views.py` imports from
  `paper/views.py`. `paper_section` lives in `paper/orders.py`.
- On Vercel after the merge, the method page answers 500 with `no such column: practice_budget` or `relation
  "paper_paperorder" does not exist` for about a minute: the migrate workflow is still running. Longer than
  that, open GitHub Actions and read the run.

## What we learned

- A broker client is a few dozen lines of httpx when every call has a timeout, every failure is one of a short
  list of exceptions with the vendor's words, and every number is read into `Decimal` at the boundary.
- A safety rule is strongest as a constructor that cannot build the unsafe thing: no setting chooses the host,
  and the settings refuse a variable that suggests otherwise.
- "Click twice" and "retry after a timeout" are the same problem. An id made from the order's facts, a unique
  column, a row lock and the vendor's own duplicate refusal turn both into "the order you already have".
- A transaction rolls back what an exception passes through, so a failure that must be remembered is saved,
  committed, and raised afterwards.
- A constraint can carry its own message, and the admin prints it.
- A fake vendor behind the transport tests the whole story, including the parts that are hard to make happen
  for real: a race, a timeout, a 422, a partial fill.
- The app keeps its own budget and its own copy of every order, because the broker's balance cannot be set and
  its history can be deleted.

## Next

Chapter 12 is the journal: the logbook with automatic entries (this chapter's orders are the first), tags,
skips and holds with reasons, the rule-following rate, and a CSV export. The monthly review gains a close: a
journal entry that says the month is done.

## References

Alpaca. (n.d.-a). *Get account* [API reference]. Retrieved October 29, 2026, from
https://docs.alpaca.markets/reference/getaccount-1

Alpaca. (n.d.-b). *Get order by client order ID* [API reference]. Retrieved October 29, 2026, from
https://docs.alpaca.markets/reference/getorderbyclientorderid

Alpaca. (n.d.-c). *Get order by ID* [API reference]. Retrieved October 29, 2026, from
https://docs.alpaca.markets/reference/getorderbyorderid-1

Alpaca. (n.d.-d). *Create an order* [API reference]. Retrieved October 29, 2026, from
https://docs.alpaca.markets/reference/postorder

Alpaca. (n.d.-e). *Orders at Alpaca*. Retrieved October 29, 2026, from
https://docs.alpaca.markets/docs/orders-at-alpaca

Alpaca. (n.d.-f). *Get US market clock* [API reference]. Retrieved October 29, 2026, from
https://docs.alpaca.markets/us/reference/legacyclock

Alpaca. (n.d.-g). *Paper trading*. Retrieved October 29, 2026, from
https://docs.alpaca.markets/docs/paper-trading

Alpaca. (2026a, March 4). *How to fix common trading API errors at Alpaca*. Alpaca Learn.
https://alpaca.markets/learn/how-to-fix-common-trading-api-errors-at-alpaca

Alpaca. (2026b, September 14). *API key security best practices for Alpaca builders*. Alpaca Learn.
https://alpaca.markets/learn/api-key-security-best-practices-for-alpaca-builders

Django Software Foundation. (n.d.). *Constraints reference*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/ref/models/constraints/ (retrieved October 29, 2026)
