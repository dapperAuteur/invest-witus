"""Edit a plan before anything happens under it, or delete it to start over (2026-11-02,
decisions 156 to 158).

A plan has history once a paper order of it bought shares, the journal holds an entry it judges
(other than the entry of its own order still open at Alpaca), or one of its reviews was written,
closed or reopened. Without history it can be deleted; it can also be edited in place while it is
version 1 and no month's window has closed under it. Open paper orders are cancelled at Alpaca
first and read back: a cancel Alpaca has not finished, or an order that filled first, stops the
edit or the delete with nothing changed. Every Alpaca answer comes from a fake through httpx's
`MockTransport`; no request leaves the process. Placeholder symbols only."""

from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest
from django.contrib.auth.models import User
from django.test import Client
from pytest_django.fixtures import Settings

from invest_witus_site.holdings.models import Account
from invest_witus_site.methods import views
from invest_witus_site.methods.models import JournalEntry, MethodPlan, MonthlyReview, ReviewEvent
from invest_witus_site.methods.plan_state import PlanHasHistory, delete_plan, plan_state
from invest_witus_site.paper import alpaca, orders
from invest_witus_site.paper.alpaca import AlpacaPaper, AlpacaRefused
from invest_witus_site.paper.models import PaperOrder
from invest_witus_site.watchlist.models import WatchItem
from tests.test_ch10 import text
from tests.test_ch11 import DAY, KEY_ID, SECRET, FakeAlpaca
from tests.test_ch12 import change

D = Decimal
FINAL = {"filled", "canceled", "expired", "rejected"}


class CancellingAlpaca(FakeAlpaca):
    """Chapter 11's fake plus `DELETE /v2/orders/{id}`: 204 for an open order, which moves to
    `cancel_to` (Alpaca may leave it `pending_cancel` for a while), and 422 for a final one."""

    def __init__(self) -> None:
        super().__init__()
        self.cancel_to = "canceled"
        self.cancelled: list[str] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "DELETE" and path.startswith("/v2/orders/"):
            self.requests.append(request)
            found = self.orders.get(path.removeprefix("/v2/orders/"))
            if found is None:
                return httpx.Response(404, json={"code": 40410000, "message": "order not found"})
            if found["status"] in FINAL:
                return httpx.Response(
                    422, json={"code": 42210000, "message": "order is not cancelable"}
                )
            self.cancelled.append(found["id"])
            found["status"] = self.cancel_to
            return httpx.Response(204)
        return super().handle(request)


# --- Fixtures ------------------------------------------------------------------------------------


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> CancellingAlpaca:
    fake = CancellingAlpaca()
    monkeypatch.setattr(alpaca, "transport", httpx.MockTransport(fake.handle))
    monkeypatch.setattr(orders, "today", lambda: DAY)
    settings.ALPACA_PAPER_KEY_ID = KEY_ID
    settings.ALPACA_PAPER_SECRET_KEY = SECRET
    return fake


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    """The method pages' today is DAY, 2026-11-03, inside November's seven-day window, so no
    month's window has closed under the plan whatever day the suite runs."""
    on(monkeypatch, DAY)


def on(monkeypatch: pytest.MonkeyPatch, day: date) -> None:
    monkeypatch.setattr(views, "timezone", SimpleNamespace(localdate=lambda: day))


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
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
    """Started November 1, 2026: 100.00 into INDEX in the first seven days, budget 1,000.00."""
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


def url(account: Account, tail: str = "") -> str:
    return f"/accounts/{account.pk}/method/{tail}"


def edit_form(plan: MethodPlan, **change_to: str) -> dict[str, str]:
    data = {
        "method_id": plan.method_id,
        "amount": str(plan.amount),
        "buy_window_days": str(plan.buy_window_days),
        "symbols": plan.symbols,
        "started_on": plan.started_on.isoformat(),
        "practice_budget": "" if plan.practice_budget is None else str(plan.practice_budget),
        "top_n": "" if plan.top_n is None else str(plan.top_n),
    }
    return {**data, **change_to}


def buy(account: Account, day: date, amount: str = "100.00") -> JournalEntry:
    return JournalEntry.objects.create(
        account=account, date=day, action="buy", symbol="INDEX", amount=D(amount)
    )


def confirmed(plan: MethodPlan) -> PaperOrder:
    """Press Confirm with the market closed: the order is queued at Alpaca for the next open, and
    its journal entry is written at once, booked at the notional."""
    [order] = orders.confirm(plan, DAY, alpaca.paper_client()).placed
    return order


# --- What counts as history ----------------------------------------------------------------------


@pytest.mark.django_db
def test_a_new_plan_has_no_history_and_may_be_edited_or_deleted(plan: MethodPlan) -> None:
    state = plan_state(plan)
    assert state.history == [] and state.can_edit and state.can_delete
    assert state.versions == [plan] and state.open_orders == []


@pytest.mark.django_db
def test_a_logged_entry_the_plan_judges_is_history_one_before_its_start_is_not(
    account: Account, plan: MethodPlan
) -> None:
    buy(account, date(2026, 10, 15))
    assert plan_state(plan).can_edit, "October is before the plan; it judges nothing there"
    buy(account, date(2026, 11, 2))
    state = plan_state(plan)
    assert not state.can_edit and not state.can_delete
    assert state.history == ["The journal has 1 entry this plan judges, from 2026-11-02."]


@pytest.mark.django_db
def test_a_written_or_closed_review_is_history_an_empty_one_only_stops_the_edit(
    owner: User, plan: MethodPlan
) -> None:
    review = MonthlyReview.objects.create(plan=plan, month="2026-11", opened_on=date(2026, 11, 7))
    state = plan_state(plan)
    assert state.can_delete and not state.can_edit
    assert state.empty_reviews == [review]
    assert "The buy window of 2026-11 closed under these numbers" in state.edit_blockers[0]
    ReviewEvent.objects.create(review=review, action="reopened", text="Typo.", by=owner)
    assert not plan_state(plan).can_delete
    review.delete()
    MonthlyReview.objects.create(
        plan=plan,
        month="2026-11",
        opened_on=date(2026, 11, 7),
        closed_at=datetime(2026, 11, 8, tzinfo=UTC),
    )
    state = plan_state(plan)
    assert state.history == ["The review of 2026-11 was written, closed or reopened, and is kept."]


@pytest.mark.django_db
def test_a_changed_plan_is_not_edited_in_place_but_may_still_be_deleted(
    plan: MethodPlan,
) -> None:
    form = change(plan, DAY, amount="150")
    assert form.is_valid(), form.errors
    version_2 = form.apply()
    state = plan_state(version_2)
    assert state.versions == [plan, version_2]
    assert state.can_delete and not state.can_edit
    assert "it is version 2" in state.edit_blockers[0]
    delete_plan(version_2)
    assert not MethodPlan.objects.exists(), "every version goes, newest first"


@pytest.mark.django_db
def test_an_open_order_is_not_history_until_it_fills(
    fake: CancellingAlpaca, plan: MethodPlan
) -> None:
    fake.is_open = False
    order = confirmed(plan)
    assert JournalEntry.objects.count() == 1, "booked at the notional while it waits"
    state = plan_state(plan)
    assert state.open_orders == [order] and state.entries == [] and state.can_edit
    order.filled_qty = D("0.5")
    order.status = "partially_filled"
    order.save()
    state = plan_state(plan)
    assert state.filled == [order] and not state.can_delete
    assert state.history[0].startswith("1 paper order bought shares (INDEX).")


# --- The Alpaca client's cancel ------------------------------------------------------------------


def test_cancel_order_sends_one_delete_and_reads_nothing_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/gone"):
            return httpx.Response(
                422, json={"code": 42210000, "message": "order is not cancelable"}
            )
        return httpx.Response(204)

    monkeypatch.setattr(alpaca, "transport", httpx.MockTransport(answer))
    client = AlpacaPaper(KEY_ID, SECRET)
    assert client.cancel_order("order-1") is None
    [request] = seen
    assert (request.method, str(request.url)) == (
        "DELETE",
        "https://paper-api.alpaca.markets/v2/orders/order-1",
    )
    assert request.headers["APCA-API-KEY-ID"] == KEY_ID
    with pytest.raises(AlpacaRefused, match="not cancelable") as refused:
        client.cancel_order("gone")
    assert refused.value.status == 422


# --- Edit ----------------------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_owner_edits_a_new_plan_in_place(
    owner_client: Client, account: Account, plan: MethodPlan
) -> None:
    page = text(owner_client.get(url(account)))
    assert "its numbers can still be edited" in page
    assert f'href="{url(account, "edit/")}">Edit the plan</a>' in page
    form_page = text(owner_client.get(url(account, "edit/")))
    assert 'value="100.00"' in form_page and 'value="INDEX"' in form_page
    assert '<button type="submit">Save the plan</button>' in form_page
    response = owner_client.post(
        url(account, "edit/"), edit_form(plan, amount="250", buy_window_days="5", symbols="other")
    )
    assert response.status_code == 302 and response["Location"] == url(account)
    edited = MethodPlan.objects.get()
    assert (edited.pk, edited.version, edited.previous) == (plan.pk, 1, None)
    assert (edited.amount, edited.buy_window_days, edited.symbols) == (D("250.00"), 5, "OTHER")
    messages = text(owner_client.get(url(account)))
    assert "this is still version 1, not a new one" in messages
    same = owner_client.post(url(account, "edit/"), edit_form(edited), follow=True)
    assert "Nothing changed: these are the plan's numbers already." in text(same)


@pytest.mark.django_db
def test_an_edit_can_switch_method_and_puts_momentum_candidates_on_the_watch_list(
    owner_client: Client, account: Account, plan: MethodPlan
) -> None:
    refused = owner_client.post(
        url(account, "edit/"), edit_form(plan, method_id="momentum-12-1", symbols="ALPHA BETA")
    )
    assert "12-1 momentum needs a top N" in text(refused)
    owner_client.post(
        url(account, "edit/"),
        edit_form(plan, method_id="momentum-12-1", symbols="ALPHA BETA GAMMA", top_n="2"),
    )
    edited = MethodPlan.objects.get()
    assert (edited.method_id, edited.top_n, edited.pk) == ("momentum-12-1", 2, plan.pk)
    watched = set(WatchItem.objects.filter(account=account).values_list("symbol", flat=True))
    assert watched == {"ALPHA", "BETA", "GAMMA"}


@pytest.mark.django_db
def test_a_plan_with_history_is_not_edited_and_the_page_says_why(
    owner_client: Client, account: Account, plan: MethodPlan
) -> None:
    buy(account, date(2026, 11, 2))
    assert "Edit the plan</a>" not in text(owner_client.get(url(account)))
    page = text(owner_client.get(url(account, "edit/")))
    assert "can no longer be edited in place" in page
    assert "The journal has 1 entry this plan judges, from 2026-11-02." in page
    assert "Save the plan" not in page
    owner_client.post(url(account, "edit/"), edit_form(plan, amount="250"))
    assert MethodPlan.objects.get().amount == D("100.00")
    change_page = text(owner_client.get(url(account, "change/")))
    assert "This plan cannot be edited in place or deleted, because it has history" in change_page


@pytest.mark.django_db
def test_an_edit_waits_until_no_window_has_closed_under_the_plan(
    monkeypatch: pytest.MonkeyPatch, owner_client: Client, account: Account, plan: MethodPlan
) -> None:
    on(monkeypatch, date(2026, 11, 9))
    page = text(owner_client.get(url(account, "edit/")))
    assert "The buy window of 2026-11 closed under these numbers" in page
    assert f'href="{url(account, "delete/")}">delete it</a>' in page
    owner_client.post(url(account, "edit/"), edit_form(plan, amount="250"))
    assert MethodPlan.objects.get().amount == D("100.00")


@pytest.mark.django_db
def test_editing_cancels_the_queued_order_first_then_the_new_buy_is_offered(
    fake: CancellingAlpaca, owner_client: Client, account: Account, plan: MethodPlan
) -> None:
    fake.is_open = False
    owner_client.post(f"/accounts/{account.pk}/paper/confirm/")
    [order] = PaperOrder.objects.all()
    assert JournalEntry.objects.count() == 1
    page = text(owner_client.get(url(account, "edit/")))
    assert "Saving cancels this order at Alpaca paper first" in page
    assert "Buy $100.00 of INDEX, accepted (queued at Alpaca)" in page
    response = owner_client.post(url(account, "edit/"), edit_form(plan, amount="150"), follow=True)
    html = text(response)
    assert "Cancelled at Alpaca: buy $100.00 of INDEX (canceled, nothing filled)." in html
    assert fake.cancelled == [order.alpaca_id]
    order.refresh_from_db()
    assert (order.status, order.filled_qty, order.journal_entry) == ("canceled", 0, None)
    assert JournalEntry.objects.count() == 0, "the cancelled order's entry is gone"
    assert MethodPlan.objects.get().amount == D("150.00")
    # The month is staged again with the new amount, as chapter 12's Place again, never twice.
    stage = orders.month_buys(MethodPlan.objects.get(), DAY)
    [again] = stage.buys
    assert (again.notional, again.attempt, stage.placing_again) == (D("150.00"), 2, True)
    assert [p["client_order_id"] for p in fake.posted] == [order.client_order_id]


@pytest.mark.django_db
def test_a_cancel_alpaca_has_not_finished_saves_nothing(
    fake: CancellingAlpaca, owner_client: Client, account: Account, plan: MethodPlan
) -> None:
    fake.is_open = False
    fake.cancel_to = "pending_cancel"
    order = confirmed(plan)
    html = text(
        owner_client.post(url(account, "edit/"), edit_form(plan, amount="150"), follow=True)
    )
    assert "Alpaca took the cancel of INDEX but has not finished it (pending_cancel)." in html
    assert MethodPlan.objects.get().amount == D("100.00")
    assert JournalEntry.objects.count() == 1
    # Later the cancel lands; the nightly sync removes the entry, and the edit goes through.
    fake.orders[order.alpaca_id]["status"] = "canceled"
    orders.sync_orders(alpaca.paper_client())
    owner_client.post(url(account, "edit/"), edit_form(plan, amount="150"))
    assert MethodPlan.objects.get().amount == D("150.00")
    assert fake.cancelled == [order.alpaca_id], "a final order is not cancelled again"


@pytest.mark.django_db
def test_an_order_that_filled_before_the_cancel_stops_the_edit(
    fake: CancellingAlpaca, owner_client: Client, account: Account, plan: MethodPlan
) -> None:
    order = confirmed(plan)
    fake.fill(order.alpaca_id, "0.5", "200")
    html = text(
        owner_client.post(url(account, "edit/"), edit_form(plan, amount="150"), follow=True)
    )
    assert "INDEX filled 0.5 shares before the cancel" in html
    assert MethodPlan.objects.get().amount == D("100.00")
    entry = JournalEntry.objects.get()
    assert entry.shares == D("0.5"), "the fill is in the journal, as the sync would put it"
    assert not plan_state(plan).can_delete


# --- Delete --------------------------------------------------------------------------------------


@pytest.mark.django_db
def test_delete_asks_first_then_deletes_the_plan_and_its_empty_reviews(
    monkeypatch: pytest.MonkeyPatch, owner_client: Client, account: Account, plan: MethodPlan
) -> None:
    before = buy(account, date(2026, 10, 15))
    on(monkeypatch, date(2026, 11, 9))
    page = text(owner_client.get(url(account, "delete/")))
    assert "Deleting cannot be undone. These go with it:" in page
    assert "1 month review the app opened and nobody wrote in: 2026-11." in page
    assert '<button type="submit" name="confirm" value="delete">Delete this plan</button>' in page
    unconfirmed = owner_client.post(url(account, "delete/"), follow=True)
    assert "Press Delete this plan to delete it. Nothing changed." in text(unconfirmed)
    assert MethodPlan.objects.exists()
    response = owner_client.post(url(account, "delete/"), {"confirm": "delete"})
    assert response.status_code == 302 and response["Location"] == url(account)
    assert not MethodPlan.objects.exists() and not MonthlyReview.objects.exists()
    assert list(JournalEntry.objects.all()) == [before], "the journal is not touched"
    after = text(owner_client.get(url(account)))
    assert (
        "Deleted Index investing with a fixed monthly contribution on Practice: 1 version" in after
    )
    assert "Start a method on this account" in after, "back in the Lesson Lab"


@pytest.mark.django_db
def test_delete_cancels_open_orders_and_drops_unfilled_rows(
    fake: CancellingAlpaca, owner_client: Client, account: Account, plan: MethodPlan
) -> None:
    fake.is_open = False
    order = confirmed(plan)
    never_sent = PaperOrder.objects.create(
        account=account,
        plan=plan,
        month="2026-11",
        symbol="OTHER",
        notional=D("1.00"),
        client_order_id="iw-test-never-sent",
    )
    page = text(owner_client.get(url(account, "delete/")))
    assert "First, these orders are cancelled at Alpaca paper" in page
    assert "Buy $1.00 of OTHER, staged (not confirmed at Alpaca)" in page
    html = text(owner_client.post(url(account, "delete/"), {"confirm": "delete"}, follow=True))
    assert "iw-test-never-sent never reached Alpaca; the app's row for it is removed." in html
    assert "Cancelled at Alpaca: buy $100.00 of INDEX" in html
    assert fake.cancelled == [order.alpaca_id]
    assert not PaperOrder.objects.filter(pk__in=[order.pk, never_sent.pk]).exists()
    assert not MethodPlan.objects.exists() and not JournalEntry.objects.exists()
    assert len(fake.posted) == 1, "nothing new was ever sent to Alpaca"


@pytest.mark.django_db
def test_a_plan_with_history_is_not_deleted_and_end_is_offered(
    fake: CancellingAlpaca, owner_client: Client, account: Account, plan: MethodPlan
) -> None:
    order = confirmed(plan)
    fake.fill(order.alpaca_id, "0.5", "200")
    orders.sync_orders(alpaca.paper_client())
    assert "delete it</a>" not in text(owner_client.get(url(account)))
    page = text(owner_client.get(url(account, "delete/")))
    assert "This plan cannot be deleted, because it has history" in page
    assert "1 paper order bought shares (INDEX)." in page
    assert f'<a href="{url(account, "change/")}">End the plan instead</a>' in page
    assert "Delete this plan</button>" not in page
    owner_client.post(url(account, "delete/"), {"confirm": "delete"})
    assert MethodPlan.objects.filter(pk=plan.pk).exists()
    with pytest.raises(PlanHasHistory, match="bought shares"):
        delete_plan(plan)
    assert fake.cancelled == []


@pytest.mark.django_db
def test_an_open_order_only_the_site_owner_can_cancel_stops_the_delete(
    fake: CancellingAlpaca, someone: User
) -> None:
    theirs = Account.objects.create(
        name="Theirs", broker="Alpaca", kind="paper", alpaca="paper", owner=someone
    )
    plan = MethodPlan.objects.create(
        account=theirs,
        method_id="index-dca",
        amount=D("100.00"),
        buy_window_days=7,
        symbols="INDEX",
        started_on=date(2026, 11, 1),
    )
    PaperOrder.objects.create(
        account=theirs,
        plan=plan,
        month="2026-11",
        symbol="INDEX",
        notional=D("100.00"),
        client_order_id="iw-theirs",
        alpaca_id="order-77",
        status="accepted",
    )
    client = Client()
    client.force_login(someone)
    html = text(client.post(url(theirs, "delete/"), {"confirm": "delete"}, follow=True))
    assert "only the site owner, on an account linked to Alpaca paper, can cancel them" in html
    assert MethodPlan.objects.filter(pk=plan.pk).exists() and fake.requests == []


# --- Who may do it -------------------------------------------------------------------------------


@pytest.mark.django_db
def test_edit_and_delete_are_the_owners_alone_and_need_csrf(
    client: Client, owner: User, someone: User, account: Account, plan: MethodPlan
) -> None:
    pages = [url(account, "edit/"), url(account, "delete/")]
    for page in pages:
        for response in (client.get(page), client.post(page, {"confirm": "delete"})):
            assert response.status_code == 302
            assert response["Location"].startswith("/auth/witus/login/")
    client.force_login(someone)
    for page in pages:
        assert client.get(page).status_code == 404
        assert client.post(page, {"confirm": "delete"}).status_code == 404
    strict = Client(enforce_csrf_checks=True)
    strict.force_login(owner)
    assert strict.post(url(account, "edit/"), edit_form(plan, amount="1")).status_code == 403
    assert strict.post(url(account, "delete/"), {"confirm": "delete"}).status_code == 403
    assert MethodPlan.objects.get().amount == D("100.00")
    for page in pages:
        html = text(strict.get(page))
        form = html.split(f'action="{page}"', 1)[1].split("</form>")[0]
        assert 'name="csrfmiddlewaretoken"' in form


@pytest.mark.django_db
def test_the_one_active_plan_rule_is_unchanged() -> None:
    names = {constraint.name for constraint in MethodPlan._meta.constraints}
    assert "one_active_plan_per_account" in names
