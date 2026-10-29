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
