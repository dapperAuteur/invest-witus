"""The plan's amount is the month's total (2026-11-03, decisions 161 and 162).

BAM chose $500 expecting $500 of each symbol; the app split $500 between them. Every place the
amount is asked for or shown now says it is the total, split equally, with the plan's own numbers
worked ("about $166.67 each"). The month's buys box says what the month bought against the plan's
amount and why any part is missing, and a month whose ranking changed after its buys were placed
keeps the buys it placed instead of re-splitting money already spent. Placeholder symbols only;
every price is planted, and no Alpaca call leaves the test (FakeAlpaca)."""

from datetime import date
from decimal import Decimal

import httpx
import pytest
from django.contrib.auth.models import User
from django.test import Client
from pytest_django.fixtures import Settings

from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.forms import AMOUNT_HELP, PlanChangeForm, PlanEditForm
from invest_witus_site.methods.models import MethodPlan
from invest_witus_site.paper import alpaca, orders
from invest_witus_site.paper.models import PaperOrder, client_order_id
from tests.test_ch10 import text
from tests.test_ch11 import DAY, KEY_ID, SECRET, FakeAlpaca
from tests.test_ch14 import plant_candidates

D = Decimal
MOMENTUM = "momentum-12-1"
MONTH = "2026-11"


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_superuser("owner", "owner@example.com", "pw")


@pytest.fixture
def account(owner: User) -> Account:
    return Account.objects.create(name="Practice", broker="Paper", kind="paper", owner=owner)


@pytest.fixture
def owner_client(client: Client, owner: User) -> Client:
    client.force_login(owner)
    return client


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> FakeAlpaca:
    fake = FakeAlpaca()
    monkeypatch.setattr(alpaca, "transport", httpx.MockTransport(fake.handle))
    monkeypatch.setattr(orders, "today", lambda: DAY)
    settings.ALPACA_PAPER_KEY_ID = KEY_ID
    settings.ALPACA_PAPER_SECRET_KEY = SECRET
    return fake


def index_plan(account: Account, amount: str, symbols: str) -> MethodPlan:
    return MethodPlan.objects.create(
        account=account,
        method_id="index-dca",
        amount=D(amount),
        buy_window_days=7,
        symbols=symbols,
        started_on=date(2026, 11, 1),
    )


def linked_momentum_plan(account: Account, amount: str = "100.00") -> MethodPlan:
    """Top 2 of four candidates on a linked paper account; with `plant_candidates((2026, 10))`
    November ranks ALPHA then BETA, GAMMA below them and DELTA unranked."""
    account.alpaca = "paper"
    account.save()
    return MethodPlan.objects.create(
        account=account,
        method_id=MOMENTUM,
        amount=D(amount),
        buy_window_days=7,
        symbols="ALPHA BETA GAMMA DELTA",
        top_n=2,
        started_on=date(2026, 11, 1),
        practice_budget=D("1000.00"),
    )


def order(plan: MethodPlan, symbol: str, notional: str, **fields: object) -> PaperOrder:
    return PaperOrder.objects.create(
        account=plan.account,
        plan=plan,
        month=MONTH,
        symbol=symbol,
        notional=D(notional),
        client_order_id=client_order_id(plan.account.pk, plan.pk, MONTH, symbol),
        **fields,
    )


# --- The words ------------------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_split_is_worked_for_the_plans_own_symbols(account: Account) -> None:
    three = index_plan(account, "500", "ALPHA BETA GAMMA")
    assert (three.buys_each_month, three.amount_each) == (3, D("166.67"))
    assert three.amount_text() == (
        "$500.00 a month in all, split equally across ALPHA BETA GAMMA (about $166.67 each)"
    )
    three.delete()
    one = index_plan(account, "100", "INDEX")
    assert one.amount_text() == "$100.00 into INDEX", "one symbol needs no split"
    one.delete()
    momentum = linked_momentum_plan(account, "500")
    assert momentum.amount_text() == (
        "$500.00 a month in all, split equally across the top 2 of ALPHA BETA GAMMA DELTA "
        "(about $250.00 each)"
    )


@pytest.mark.django_db
def test_the_start_form_says_the_amount_is_the_total(
    owner_client: Client, account: Account
) -> None:
    html = text(owner_client.get(f"/accounts/{account.pk}/method/?view=c"))
    assert "Total amount each month" in html
    assert AMOUNT_HELP in html
    assert "$500 across 3 symbols is about $166.67 each" in AMOUNT_HELP
    assert "not an amount for each symbol" in AMOUNT_HELP


@pytest.mark.django_db
def test_the_edit_and_change_forms_work_the_example_for_the_plan(account: Account) -> None:
    plan = index_plan(account, "500", "ALPHA BETA GAMMA")
    for form in (PlanEditForm(plan), PlanChangeForm(plan, DAY)):
        field = form.fields["amount"]
        assert field.label == "Total amount each month"
        assert "(about $166.67 each)" in str(field.help_text)
        assert "not an amount for each symbol" in str(field.help_text)


@pytest.mark.django_db
def test_every_view_shows_the_plan_as_a_total(owner_client: Client, account: Account) -> None:
    index_plan(account, "500", "ALPHA BETA GAMMA")
    for view in "abc":
        html = text(owner_client.get(f"/accounts/{account.pk}/method/?view={view}"))
        assert "$500.00 a month in all, split equally across ALPHA BETA GAMMA" in html, view
        assert "(about $166.67 each)" in html, view
    detail = text(owner_client.get(f"/accounts/{account.pk}/"))
    assert "$500.00 a month in all, split equally across ALPHA BETA GAMMA" in detail


# --- The month's buys box ------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_box_says_the_month_total_is_the_plans_amount(
    fake: FakeAlpaca, owner_client: Client, account: Account
) -> None:
    plant_candidates((2026, 10))
    linked_momentum_plan(account)
    html = text(owner_client.get(f"/accounts/{account.pk}/method/"))
    assert "Buy $50.00 of ALPHA" in html and "Buy $50.00 of BETA" in html
    assert "$100.00 in all this month, split across 2 symbols" in html
    assert "not an amount for each symbol" in html
    assert "Bought or queued this month" not in html, "nothing sent yet"


@pytest.mark.django_db
def test_a_refused_buy_shows_beside_the_total_with_alpacas_reason(
    fake: FakeAlpaca, owner_client: Client, account: Account
) -> None:
    plant_candidates((2026, 10))
    plan = linked_momentum_plan(account)
    order(plan, "ALPHA", "50.00", alpaca_id="order-1", status="filled", filled_qty=D("0.5"))
    order(plan, "BETA", "50.00", message="asset BETA is not tradable")
    stage = orders.month_buys(plan, DAY)
    assert stage.bought == D("50.00") and stage.plan_amount == D("100.00")
    assert stage.shortfalls == [
        "BETA: $50.00 not placed. Alpaca's answer: asset BETA is not tradable"
    ]
    html = text(owner_client.get(f"/accounts/{account.pk}/method/"))
    assert "Bought or queued this month: $50.00 of $100.00." in html
    assert "BETA: $50.00 not placed. Alpaca's answer: asset BETA is not tradable" in html


@pytest.mark.django_db
def test_a_part_fill_and_an_unfilled_order_are_named(fake: FakeAlpaca, account: Account) -> None:
    plant_candidates((2026, 10))
    plan = linked_momentum_plan(account)
    order(
        plan,
        "ALPHA",
        "50.00",
        alpaca_id="order-1",
        status="expired",
        filled_qty=D("0.1"),
        filled_avg_price=D("300"),
    )
    order(plan, "BETA", "50.00", alpaca_id="order-2", status="canceled")
    stage = orders.month_buys(plan, DAY)
    assert stage.bought == D("30.00")
    assert stage.shortfalls[0].startswith("ALPHA: $30.00 of $50.00. The order ended part filled")
    assert stage.shortfalls[1] == (
        "BETA: $50.00 not bought. The order ended with nothing filled (canceled)."
    )


@pytest.mark.django_db
def test_a_ranking_that_changes_after_the_buys_never_re_splits_or_buys_past_the_amount(
    fake: FakeAlpaca, account: Account
) -> None:
    """Decision 162's bug: ALPHA was the only candidate ranked when the owner confirmed, so it got
    the whole $100. BETA's history arrived later and ranked it in. Before the fix the box showed
    ALPHA's placed order as $50.00 and staged $50.00 of BETA with Confirm offered: $150 for a $100
    month. Now the month keeps what it placed and names BETA."""
    plant_candidates((2026, 10))
    plan = linked_momentum_plan(account)
    order(plan, "ALPHA", "100.00", alpaca_id="order-1", status="accepted")
    stage = orders.month_buys(plan, DAY)
    assert [(buy.symbol, buy.notional) for buy in stage.buys] == [("ALPHA", D("100.00"))]
    assert stage.ranked_in_later == ["BETA"]
    assert not stage.can_confirm and stage.bought == D("100.00") and stage.shortfalls == []
    orders.confirm(plan, DAY, alpaca.paper_client())
    assert fake.posted == [], "nothing beyond the plan's amount is sent"


@pytest.mark.django_db
def test_a_month_whose_orders_all_ended_unfilled_is_split_again_from_the_plan(
    fake: FakeAlpaca, account: Account
) -> None:
    plant_candidates((2026, 10))
    plan = linked_momentum_plan(account)
    order(plan, "ALPHA", "100.00", alpaca_id="order-1", status="expired")
    stage = orders.month_buys(plan, DAY)
    assert [(buy.symbol, buy.notional, buy.attempt) for buy in stage.buys] == [
        ("ALPHA", D("50.00"), 2),
        ("BETA", D("50.00"), 1),
    ]
    assert stage.can_confirm and stage.ranked_in_later == []
