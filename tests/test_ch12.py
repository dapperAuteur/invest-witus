"""Chapter 12 checkpoint: the journal becomes a logbook, and the month gets a close. A hold and a
skip each need a reason and move no money; a skip with its reason explains a month with no buy,
and the review says so without changing a rule; each month whose window has closed gets a review,
closed with three written answers and reopened only with a reason, every step kept; a closed
month's entries are read-only; a plan changes by a new version and each month is judged by the
version in force; a paper month whose order ended unfilled is placed again with a new id, once;
the logbook filters and exports CSV for its owner only; and the public pages are as they were.
Placeholder symbols only, and every Alpaca answer from chapter 11's fake."""

import csv
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

import httpx
import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import Client
from django.utils import timezone
from pytest_django.fixtures import Settings

from invest_witus.adherence.review import CHECKED_RULES
from invest_witus.methods.rulebook import load_method
from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.engine import build_review, next_action
from invest_witus_site.methods.forms import PlanChangeForm, first_of_next_month
from invest_witus_site.methods.logbook import CSV_COLUMNS, cell
from invest_witus_site.methods.models import (
    JournalEntry,
    MethodPlan,
    MonthlyReview,
    ReviewEvent,
    version_spans,
)
from invest_witus_site.methods.reviews import (
    ReviewRefused,
    close_review,
    open_due_reviews,
    reopen_review,
)
from invest_witus_site.paper import alpaca, orders
from invest_witus_site.paper.models import PaperOrder, client_order_id
from tests.test_ch10 import tables_in, text
from tests.test_ch11 import DAY, KEY_ID, SECRET, FakeAlpaca

D = Decimal
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
SKIP_REASON = "Practice month: I read the lesson again instead."
ANSWERS = {
    "did": "Bought once, on day 2.",
    "rules_said": "Every rule passed this month.",
    "next_month": "The same, in the first week.",
}


# --- Fixtures: an owner, an account, a plan from January 2026 -------------------------------------


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
    """The site owner, a superuser as chapter 11 needs for the paper tests."""
    return django_user_model.objects.create_superuser("owner", "owner@example.com", "pw")


@pytest.fixture
def someone(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("someone")


@pytest.fixture
def account(owner: User) -> Account:
    return Account.objects.create(name="Practice", broker="Example", kind="paper", owner=owner)


@pytest.fixture
def plan(account: Account) -> MethodPlan:
    """index-dca from January 1, 2026: 100.00 into INDEX within the first seven days."""
    return MethodPlan.objects.create(
        account=account,
        method_id="index-dca",
        amount=D("100.00"),
        buy_window_days=7,
        symbols="INDEX",
        started_on=date(2026, 1, 1),
    )


@pytest.fixture
def owner_client(client: Client, owner: User) -> Client:
    client.force_login(owner)
    return client


def buy(account: Account, day: date, amount: str = "100.00", **extra: object) -> JournalEntry:
    return JournalEntry.objects.create(
        account=account, date=day, action="buy", symbol="INDEX", amount=D(amount), **extra
    )


def skip(account: Account, day: date, reason: str = SKIP_REASON, **extra: object) -> JournalEntry:
    return JournalEntry.objects.create(
        account=account, date=day, kind="skip", reason=reason, **extra
    )


def method_url(account: Account, query: str = "") -> str:
    return f"/accounts/{account.pk}/method/{query}"


def review_url(account: Account, month: str, action: str = "") -> str:
    return f"/accounts/{account.pk}/method/review/{month}/{action}"


def logbook_url(account: Account, tail: str = "") -> str:
    return f"/accounts/{account.pk}/logbook/{tail}"


def entry_form(**change: str) -> dict[str, str]:
    """The log form as a browser posts it, with chapter 12's fields."""
    data = {
        "date": "2026-02-03",
        "kind": "trade",
        "action": "buy",
        "symbol": "INDEX",
        "amount": "100",
        "shares": "",
        "reason": "",
        "state": "",
        "tags": "",
        "note": "",
    }
    return {**data, **change}


# --- Hold and skip --------------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_hold_or_a_skip_needs_a_reason_and_moves_no_money(account: Account) -> None:
    day = date(2026, 3, 2)
    for kind in ("hold", "skip"):
        with pytest.raises(ValidationError) as refused:
            JournalEntry(account=account, date=day, kind=kind).full_clean()
        assert refused.value.message_dict == {
            "reason": [f"A {kind} needs a reason: write why, in a sentence."]
        }
        with pytest.raises(ValidationError) as refused:
            JournalEntry(
                account=account, date=day, kind=kind, reason="why", action="buy", amount=D("1")
            ).full_clean()
        assert set(refused.value.message_dict) == {"action", "amount"}
        with pytest.raises(ValueError, match=f"a {kind} needs a reason"):
            JournalEntry(account=account, date=day, kind=kind, reason="  ").save()
    with pytest.raises(ValidationError) as refused:
        JournalEntry(account=account, date=day, symbol="INDEX", amount=D("1")).full_clean()
    assert refused.value.message_dict == {"action": ["A trade is a buy or a sell."]}
    row = skip(account, day)
    assert (row.symbol, row.amount, row.action, row.what) == ("", None, "", "Skip")
    assert str(row) == "2026-03-02 skip" and not row.is_trade
    with pytest.raises(ValueError, match="not a trade"):
        row.to_entry()


@pytest.mark.django_db
def test_the_log_form_takes_a_skip_with_its_reason_state_and_tags(
    owner_client: Client, account: Account, plan: MethodPlan
) -> None:
    url = method_url(account, "log/")
    skip_form = entry_form(kind="skip", action="", symbol="", amount="")
    for change, message in [
        ({}, "A skip needs a reason: write why, in a sentence."),
        ({"reason": "why", "amount": "5"}, "A skip moves no money"),
        ({"reason": "why", "state": "euphoric"}, "Select a valid choice."),
        ({"reason": "why", "tags": "bad tag!"}, "'tag!' is not a tag"),
        ({"reason": "why", "tags": "a b c d e f"}, "6 tags; the most is 5"),
    ]:
        refused = owner_client.post(url, {**skip_form, **change})
        assert refused.status_code == 200 and message in text(refused), change
    assert JournalEntry.objects.count() == 0
    data = {**skip_form, "reason": SKIP_REASON, "state": "unsure", "tags": "Late, news  late"}
    response = owner_client.post(url, data, follow=True)
    assert response.redirect_chain == [(method_url(account), 302)]
    row = JournalEntry.objects.get()
    assert (row.kind, row.reason, row.state, row.tags) == (
        "skip",
        SKIP_REASON,
        "unsure",
        "late news",
    )
    assert "Logged: 2026-02-03 skip." in text(response)
    # A form posted without a kind, as chapter 10's was, is still a trade.
    old = {key: value for key, value in entry_form(date="2026-01-02").items() if key != "kind"}
    assert owner_client.post(url, old).status_code == 302
    assert JournalEntry.objects.get(date=date(2026, 1, 2)).kind == "trade"


# --- The review: an explained skip, rules unchanged -----------------------------------------------


def test_the_rules_file_and_the_checks_are_unchanged() -> None:
    assert {rule.id for rule in load_method("index-dca").rules} == CHECKED_RULES


@pytest.mark.django_db
def test_a_skip_with_a_reason_explains_a_month_with_no_buy(
    account: Account, plan: MethodPlan
) -> None:
    buy(account, date(2026, 1, 2), tags="first")
    skip(account, date(2026, 2, 3))
    entries = JournalEntry.entries_for(account)
    review = build_review(plan, entries, through=date(2026, 3, 31))
    assert [(f.month, f.rule.id, f.explanation) for f in review.findings] == [
        ("2026-02", "one-buy-each-month", SKIP_REASON),
        ("2026-03", "one-buy-each-month", ""),
    ]
    assert [(row.label, row.status, row.skip_reason) for row in review.months] == [
        ("2026-01", "done", ""),
        ("2026-02", "skipped", SKIP_REASON),
        ("2026-03", "missed", ""),
    ]
    one_buy = review.checks[0]
    assert (one_buy.rule.id, one_buy.status) == ("one-buy-each-month", "fail")
    assert one_buy.evidence == "2 findings: 2026-02, 2026-03 (1 explained)"
    assert (review.months_followed, review.explained_count, len(review.unexplained)) == (1, 1, 1)
    skip(account, date(2026, 3, 20), reason="Away all week.")
    review = build_review(plan, JournalEntry.entries_for(account), through=date(2026, 3, 31))
    assert review.checks[0].status == "explained" and review.unexplained == []
    assert review.months[-1].status == "skipped"
    # A skip does not excuse a sale, or a second buy: only the month with no buy.
    assert [check.status for check in review.checks[1:]] == ["pass"] * 4


def test_a_skipped_month_is_decided_for_the_next_action() -> None:
    plan = MethodPlan(
        method_id="index-dca",
        amount=D("100"),
        buy_window_days=7,
        symbols="INDEX",
        started_on=date(2026, 1, 1),
    ).to_plan()
    assert next_action(plan, [], date(2026, 4, 3)).status == "due"
    later = next_action(plan, [], date(2026, 4, 3), skipped=frozenset({(2026, 4)}))
    assert (later.label, later.status) == ("2026-05", "upcoming")


@pytest.mark.django_db
def test_the_page_shows_the_skip_as_explained_in_every_view(
    owner_client: Client, account: Account, plan: MethodPlan
) -> None:
    buy(account, date(2026, 1, 2))
    skip(account, date(2026, 2, 3))
    for view in ("a", "b", "c"):
        html = text(owner_client.get(method_url(account, f"?view={view}&through=2026-02-28")))
        assert f"Explained by a skip: {SKIP_REASON}" in html, view
        assert f"Why: {SKIP_REASON}" in html, view
    html = text(owner_client.get(method_url(account, "?view=b&through=2026-02-28")))
    checks, months, findings, entries = tables_in(html)
    assert f"Explained by a skip: {SKIP_REASON}" in findings[1][2]
    assert checks[1][:3] == (
        load_method("index-dca").rules[0].text,
        "explained",
        "1 finding: 2026-02 (1 explained)",
    )
    assert months[2][:3] == ("2026-02", "2026-02-07", "skipped")
    assert entries[2][:3] == ("2026-02-03", "Skip", "")


# --- The monthly review: open, close, reopen ------------------------------------------------------


@pytest.mark.django_db
def test_a_review_opens_for_each_month_whose_window_has_closed(plan: MethodPlan) -> None:
    assert [r.month for r in open_due_reviews(plan, date(2026, 3, 6))] == ["2026-01", "2026-02"]
    reviews = open_due_reviews(plan, date(2026, 3, 7))
    assert [(r.month, r.opened_on, r.closed) for r in reviews] == [
        ("2026-01", date(2026, 1, 7), False),
        ("2026-02", date(2026, 2, 7), False),
        ("2026-03", date(2026, 3, 7), False),
    ]
    open_due_reviews(plan, date(2026, 3, 7))
    assert MonthlyReview.objects.count() == 3, "opening twice makes nothing new"


@pytest.mark.django_db
def test_view_a_offers_to_close_last_month_and_view_b_lists_every_month(
    owner_client: Client, account: Account, plan: MethodPlan
) -> None:
    buy(account, date(2026, 1, 2))
    html = text(owner_client.get(method_url(account, "?view=a")))
    assert "Close last month" in html
    assert f'<a href="{review_url(account, "2026-01")}">Review 2026-01</a>' in html
    html = text(owner_client.get(method_url(account, "?view=b")))
    assert "Monthly reviews" in html and "Close last month" not in html
    assert f'<a href="{review_url(account, "2026-01")}">2026-01</a>: open since 2026-01-07' in html
    MonthlyReview.objects.filter(month="2026-01").update(closed_at=timezone.now())
    html = text(owner_client.get(method_url(account, "?view=b")))
    assert f"2026-01</a>: closed {timezone.localdate():%Y-%m-%d}" in html
    html = text(owner_client.get(method_url(account, "?view=a")))
    assert "Review 2026-02" in html and "Review 2026-01" not in html


@pytest.mark.django_db
def test_closing_needs_three_answers_and_no_unexplained_miss(
    owner_client: Client, owner: User, account: Account, plan: MethodPlan
) -> None:
    buy(account, date(2026, 1, 2))
    page = text(owner_client.get(review_url(account, "2026-01")))
    assert "Review of 2026-01" in page and "Every rule passed this month." in page
    refused = owner_client.post(review_url(account, "2026-01", "close/"), {**ANSWERS, "did": ""})
    assert refused.status_code == 200 and "This field is required." in text(refused)
    refused = owner_client.post(review_url(account, "2026-02", "close/"), ANSWERS)
    assert "2026-02 has no buy and no skip with a reason." in text(refused)
    assert not MonthlyReview.objects.get(month="2026-02").closed
    skip(account, date(2026, 2, 9))
    page = text(owner_client.get(review_url(account, "2026-02")))
    assert f"No buy in 2026-02. (skipped: {SKIP_REASON})" in page, "the draft answer"
    closed = owner_client.post(review_url(account, "2026-02", "close/"), ANSWERS, follow=True)
    assert closed.redirect_chain == [(method_url(account), 302)]
    assert "Closed 2026-02. Its entries are read-only now." in text(closed)
    review = MonthlyReview.objects.get(month="2026-02")
    assert review.closed and (review.did, review.next_month) == (
        ANSWERS["did"],
        ANSWERS["next_month"],
    )
    [event] = ReviewEvent.objects.filter(review=review)
    assert (event.action, event.by) == ("closed", owner)
    assert event.text.startswith(f"What I did: {ANSWERS['did']}\nWhat the rules said:")
    again = owner_client.post(review_url(account, "2026-02", "close/"), ANSWERS, follow=True)
    assert "2026-02 is already closed." in text(again)
    assert ReviewEvent.objects.count() == 1


@pytest.mark.django_db
def test_a_closed_month_is_read_only_until_reopened_with_a_reason(
    owner_client: Client, owner: User, account: Account, plan: MethodPlan, admin_client: Client
) -> None:
    january = buy(account, date(2026, 1, 2))
    february = buy(account, date(2026, 2, 3))
    [review] = [r for r in open_due_reviews(plan, date(2026, 2, 28)) if r.month == "2026-01"]
    context = build_review(plan, JournalEntry.entries_for(account), date(2026, 2, 28))
    close_review(review, context, by=owner, **ANSWERS)
    locked = "2026-01 is closed. Reopen its review, with a reason, to change it."
    # A new line dated in the closed month, from the method page's form.
    refused = owner_client.post(method_url(account, "log/"), entry_form(date="2026-01-20"))
    assert refused.status_code == 200 and locked in text(refused)
    # An edit of a line in it: no form at all, and a post is refused.
    edit = logbook_url(account, f"{january.pk}/edit/")
    page = text(owner_client.get(edit))
    assert (
        "2026-01 is closed, so its entries are read-only." in page
        and f'action="{edit}"' not in page
    )
    owner_client.post(edit, entry_form(date="2026-01-02", amount="90"))
    january.refresh_from_db()
    assert january.amount == D("100.00")
    # Moving an open month's line into the closed month is an edit of the closed month too.
    moved = owner_client.post(
        logbook_url(account, f"{february.pk}/edit/"), entry_form(date="2026-01-05")
    )
    assert locked in text(moved)
    # The admin cannot delete it, and cannot save a change to it.
    assert admin_client.get(f"/admin/methods/journalentry/{january.pk}/delete/").status_code == 403
    with pytest.raises(ValidationError, match="2026-01 is closed"):
        january.full_clean()
    # Reopen: a reason is required, then the month opens, and the history has both steps.
    reopen = review_url(account, "2026-01", "reopen/")
    assert "This field is required." in text(owner_client.post(reopen, {"reason": ""}))
    response = owner_client.post(reopen, {"reason": "The statement showed 90.00."}, follow=True)
    assert response.redirect_chain == [(review_url(account, "2026-01"), 302)]
    assert "Reopened 2026-01. Its entries can change again." in text(response)
    assert [(e.action, e.text) for e in ReviewEvent.objects.filter(review=review)][1] == (
        "reopened",
        "The statement showed 90.00.",
    )
    assert owner_client.post(edit, entry_form(date="2026-01-02", amount="90")).status_code == 302
    january.refresh_from_db()
    assert january.amount == D("90.00")
    review.refresh_from_db()
    with pytest.raises(ReviewRefused, match="open already"):
        reopen_review(review, reason="again", by=owner)
    close_review(
        review,
        build_review(plan, JournalEntry.entries_for(account), date(2026, 2, 28)),
        by=owner,
        **ANSWERS,
    )
    page = text(owner_client.get(review_url(account, "2026-01")))
    assert page.count(": Closed by owner.") == 2 and ": Reopened by owner." in page


# --- Plan versions --------------------------------------------------------------------------------


def errors(form: PlanChangeForm) -> str:
    """Every message the form refused with, as plain text."""
    return " ".join(str(message) for messages in form.errors.values() for message in messages)


def change(plan: MethodPlan, today: date, **data: str) -> PlanChangeForm:
    defaults = {
        "what": "change",
        "amount": str(plan.amount),
        "buy_window_days": str(plan.buy_window_days),
        "symbols": plan.symbols,
        "effective": "next",
        "reason": "A raise: I can put more in.",
    }
    return PlanChangeForm(plan, today, {**defaults, **data})


@pytest.mark.django_db
def test_a_change_is_a_new_version_and_each_month_is_judged_by_its_own(
    account: Account, plan: MethodPlan
) -> None:
    form = change(plan, date(2026, 2, 20), amount="150")
    assert form.is_valid(), form.errors
    second = form.apply()
    plan.refresh_from_db()
    assert (plan.active, plan.ended_on, plan.version) == (False, date(2026, 2, 28), 1)
    assert (second.active, second.version, second.previous, second.started_on) == (
        True,
        2,
        plan,
        date(2026, 3, 1),
    )
    assert second.change_reason == "A raise: I can put more in." and second.amount == D("150.00")
    assert [(s.plan.version, s.first, s.last) for s in version_spans(second.versions())] == [
        (1, date(2026, 1, 1), date(2026, 2, 28)),
        (2, date(2026, 3, 1), None),
    ]
    buy(account, date(2026, 1, 2))
    buy(account, date(2026, 2, 3), "150.00")  # February is version 1's: 100.00
    buy(account, date(2026, 3, 3), "150.00")  # March is version 2's: 150.00
    review = build_review(second, JournalEntry.entries_for(account), date(2026, 3, 31))
    assert [(f.month, f.rule.id, f.message) for f in review.findings] == [
        ("2026-02", "fixed-amount", "Bought 150.00; the plan says 100.00.")
    ]
    assert [(row.label, row.version) for row in review.months] == [
        ("2026-01", 1),
        ("2026-02", 1),
        ("2026-03", 2),
    ]
    reviews = open_due_reviews(second, date(2026, 3, 31))
    assert [(r.month, r.plan.version) for r in reviews] == [
        ("2026-01", 1),
        ("2026-02", 1),
        ("2026-03", 2),
    ]
    assert (
        second.in_force(date(2026, 2, 25)) == plan and second.in_force(date(2026, 3, 1)) == second
    )
    assert second.chain_start() == date(2026, 1, 1)


@pytest.mark.django_db
def test_the_change_form_refuses_what_it_should(account: Account, plan: MethodPlan) -> None:
    march_15, march_3 = date(2026, 3, 15), date(2026, 3, 3)
    assert "reason" in change(plan, march_15, reason="").errors
    assert "Nothing changed" in errors(change(plan, march_15))
    assert "A change keeps every number" in errors(change(plan, march_15, amount=""))
    late = change(plan, march_15, amount="150", effective="this")
    assert "This month's window closed on day 7" in errors(late)
    buy(account, date(2026, 3, 2))
    traded = change(plan, march_3, amount="150", effective="this")
    assert "2026-03 already has a trade in the journal" in errors(traded)
    JournalEntry.objects.all().delete()
    now = change(plan, march_3, amount="150", effective="this")
    assert now.is_valid(), now.errors
    second = now.apply()
    assert second.started_on == date(2026, 3, 1) and second.previous == plan
    plan.refresh_from_db()
    assert plan.ended_on == date(2026, 2, 28)
    ended = change(second, march_3, what="end", reason="Done practicing.")
    assert ended.is_valid(), ended.errors
    ended.apply()
    second.refresh_from_db()
    assert (second.active, second.ended_on, second.end_reason) == (
        False,
        march_3,
        "Done practicing.",
    )
    assert MethodPlan.active_for(account) is None and MethodPlan.objects.count() == 2


@pytest.mark.django_db
def test_the_owner_changes_and_ends_the_plan_from_the_page(
    owner_client: Client, account: Account, plan: MethodPlan
) -> None:
    url = method_url(account, "change/")
    page = text(owner_client.get(url))
    assert "Change or end the plan" in page and 'value="100.00"' in page
    data = {
        "what": "change",
        "amount": "150",
        "buy_window_days": "7",
        "symbols": "INDEX",
        "effective": "next",
        "reason": "A raise.",
    }
    response = owner_client.post(url, data, follow=True)
    starts = first_of_next_month(timezone.localdate())
    assert response.redirect_chain == [(method_url(account), 302)]
    assert f"Version 2 of the plan starts on {starts:%Y-%m-%d}." in text(response)
    html = text(owner_client.get(method_url(account, "?view=a")))
    assert "Version 1: $100.00 into INDEX" in html and "Why: A raise." in html
    ended = owner_client.post(url, {**data, "what": "end", "reason": "Stopping."}, follow=True)
    assert "Ended Index investing with a fixed monthly contribution on Practice." in text(ended)
    assert "Start a method on this account" in text(ended)
    assert MethodPlan.objects.filter(active=False).count() == 2
    nothing = owner_client.get(url, follow=True)
    assert "there is no plan to change" in text(nothing)


# --- Place again --------------------------------------------------------------------------------


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> FakeAlpaca:
    fake = FakeAlpaca()
    monkeypatch.setattr(alpaca, "transport", httpx.MockTransport(fake.handle))
    monkeypatch.setattr(orders, "today", lambda: DAY)
    settings.ALPACA_PAPER_KEY_ID = KEY_ID
    settings.ALPACA_PAPER_SECRET_KEY = SECRET
    return fake


@pytest.fixture
def paper_plan(account: Account) -> MethodPlan:
    """Chapter 11's plan: November 2026, 100.00 into INDEX, a budget of 1,000.00, linked."""
    account.alpaca = "paper"
    account.save()
    return MethodPlan.objects.create(
        account=account,
        method_id="index-dca",
        amount=D("100.00"),
        buy_window_days=7,
        symbols="INDEX",
        started_on=date(2026, 11, 1),
        practice_budget=D("1000.00"),
    )


@pytest.mark.django_db
def test_place_again_is_a_new_id_once_after_an_order_ended_unfilled(
    fake: FakeAlpaca, owner_client: Client, paper_plan: MethodPlan
) -> None:
    account = paper_plan.account
    first_id = client_order_id(account.pk, paper_plan.pk, "2026-11", "INDEX")
    assert client_order_id(account.pk, paper_plan.pk, "2026-11", "INDEX", 1) == first_id
    assert client_order_id(account.pk, paper_plan.pk, "2026-11", "INDEX", 2) == f"{first_id}-r2"
    owner_client.post(f"/accounts/{account.pk}/paper/confirm/")
    fake.orders["order-1"]["status"] = "expired"
    orders.sync_orders(alpaca.paper_client())
    assert JournalEntry.objects.count() == 0, "an unfilled order leaves no entry"
    stage = orders.month_buys(paper_plan, DAY)
    [staged] = stage.buys
    assert (staged.attempt, staged.order, staged.client_order_id) == (2, None, f"{first_id}-r2")
    assert staged.previous is not None and staged.previous.status == "expired"
    assert stage.can_confirm and stage.placing_again
    html = text(owner_client.get(method_url(account)))
    assert "the last order ended with nothing filled (expired)" in html
    assert '<button type="submit">Place again</button>' in html
    for _ in range(2):
        owner_client.post(f"/accounts/{account.pk}/paper/confirm/")
    assert len(fake.posted) == 2, "the first order, then one more: never a third"
    assert [p["client_order_id"] for p in fake.posted] == [first_id, f"{first_id}-r2"]
    assert [(o.attempt, o.status) for o in PaperOrder.objects.order_by("attempt")] == [
        (1, "expired"),
        (2, "accepted"),
    ]
    assert JournalEntry.objects.count() == 1
    assert not orders.month_buys(paper_plan, DAY).placing_again
    # Outside the window, an unfilled month is not placed again: the method has no catching up.
    fake.orders["order-2"]["status"] = "canceled"
    orders.sync_orders(alpaca.paper_client())
    late = orders.month_buys(paper_plan, date(2026, 11, 10))
    assert "window closed" in late.refusal and not late.can_confirm


@pytest.mark.django_db
def test_a_skip_this_month_stops_confirm(fake: FakeAlpaca, paper_plan: MethodPlan) -> None:
    skip(paper_plan.account, date(2026, 11, 2))
    stage = orders.month_buys(paper_plan, DAY)
    assert stage.refusal == "You logged a skip for 2026-11, with its reason: nothing is placed."
    with pytest.raises(orders.ConfirmRefused):
        orders.confirm(paper_plan, DAY, alpaca.paper_client())
    assert fake.posted == []


@pytest.mark.django_db
def test_confirm_uses_the_version_in_force_while_a_change_is_scheduled(
    fake: FakeAlpaca, paper_plan: MethodPlan
) -> None:
    form = change(paper_plan, DAY, amount="150")
    assert form.is_valid(), form.errors
    scheduled = form.apply()
    assert scheduled.started_on == date(2026, 12, 1)
    result = orders.confirm(scheduled, DAY, alpaca.paper_client())
    [order] = result.placed
    assert (order.plan, order.notional) == (paper_plan, D("100.00")), "November is version 1's"


# --- The logbook and its export -------------------------------------------------------------------


@pytest.fixture
def logbook_rows(account: Account, plan: MethodPlan) -> list[JournalEntry]:
    return [
        buy(account, date(2026, 1, 2), tags="first", state="calm"),
        skip(account, date(2026, 2, 3), tags="late news", state="unsure"),
        JournalEntry.objects.create(
            account=account, date=date(2026, 2, 10), kind="hold", reason="=SUM(1) is not advice"
        ),
        JournalEntry.objects.create(
            account=account,
            date=date(2026, 3, 3),
            action="sell",
            symbol="INDEX",
            amount=D("50"),
            note="-a note that starts with a minus",
        ),
    ]


@pytest.mark.django_db
def test_the_logbook_filters_by_month_kind_and_tag(
    owner_client: Client, account: Account, logbook_rows: list[JournalEntry]
) -> None:
    html = text(owner_client.get(logbook_url(account)))
    [table] = tables_in(html)
    assert table[0] == (
        "Day",
        "Kind",
        "Symbol",
        "Amount",
        "Shares",
        "State",
        "Tags",
        "Why",
        "Note",
        "Source",
    )
    assert [row[:2] for row in table[1:]] == [
        ("2026-01-02", "Buy"),
        ("2026-02-03", "Skip"),
        ("2026-02-10", "Hold"),
        ("2026-03-03", "Sell"),
    ]
    assert table[2][5:8] == ("Unsure", "late news", SKIP_REASON)
    for query, days in [
        ("?kind=skip", ["2026-02-03"]),
        ("?kind=sell", ["2026-03-03"]),
        ("?month=2026-02", ["2026-02-03", "2026-02-10"]),
        ("?tag=late", ["2026-02-03"]),
        ("?month=2026-02&kind=hold", ["2026-02-10"]),
        ("?kind=bogus&month=26-2&tag=No%20Way", [r.date.isoformat() for r in logbook_rows]),
    ]:
        rows = tables_in(text(owner_client.get(logbook_url(account) + query)))
        found = [row[0] for row in rows[0][1:]] if rows else []
        assert found == days, query
    filtered = text(owner_client.get(logbook_url(account, "?tag=late")))
    assert f'href="{logbook_url(account, "export.csv")}?tag=late"' in filtered
    assert "1 of 4 entries." in filtered


@pytest.mark.django_db
def test_the_csv_export_has_the_documented_columns(
    owner_client: Client, account: Account, plan: MethodPlan, logbook_rows: list[JournalEntry]
) -> None:
    order = PaperOrder.objects.create(
        account=account,
        plan=plan,
        month="2026-01",
        symbol="INDEX",
        notional=D("100"),
        client_order_id="iw-test-2026-01-INDEX",
        alpaca_id="order-x",
        status="filled",
        journal_entry=logbook_rows[0],
    )
    response = owner_client.get(logbook_url(account, "export.csv"))
    assert response["Content-Type"] == "text/csv; charset=utf-8"
    assert (
        response["Content-Disposition"]
        == f'attachment; filename="logbook-account-{account.pk}.csv"'
    )
    assert response["Cache-Control"] == "no-store"
    rows = list(csv.reader(StringIO(response.content.decode("utf-8"))))
    assert (
        tuple(rows[0])
        == CSV_COLUMNS
        == (
            "date",
            "kind",
            "symbol",
            "amount",
            "shares",
            "state",
            "tags",
            "reason",
            "note",
            "source",
            "month_closed",
        )
    )
    assert rows[1] == [
        "2026-01-02",
        "buy",
        "INDEX",
        "100.00",
        "",
        "calm",
        "first",
        "",
        "",
        f"alpaca-paper:{order.client_order_id}",
        "no",
    ]
    assert rows[2][:3] == ["2026-02-03", "skip", ""] and rows[2][7] == SKIP_REASON
    assert rows[3][7] == "'=SUM(1) is not advice", "a formula is exported as text"
    assert rows[4][8] == "'-a note that starts with a minus"
    assert [cell(text) for text in ("\uff1d1+1", "@SUM", "plain")] == [
        "'\uff1d1+1",
        "'@SUM",
        "plain",
    ]
    MonthlyReview.objects.create(
        plan=plan, month="2026-02", opened_on=date(2026, 2, 7), closed_at=timezone.now()
    )
    rows = list(
        csv.reader(
            StringIO(
                owner_client.get(logbook_url(account, "export.csv?month=2026-02")).content.decode()
            )
        )
    )
    assert [(row[1], row[10]) for row in rows[1:]] == [("skip", "yes"), ("hold", "yes")]


@pytest.mark.django_db
def test_the_pages_show_money_and_the_csv_keeps_plain_numbers(
    owner_client: Client, account: Account, plan: MethodPlan
) -> None:
    """Decision 113 on chapter 12's pages: a dollar sign and thousands commas for money, commas
    for shares; the CSV is for a spreadsheet, so it keeps plain decimals."""
    buy(account, date(2026, 1, 2), "1234.50", shares=D("1234.5"))
    [table] = tables_in(text(owner_client.get(logbook_url(account))))
    assert table[1][3:5] == ("$1,234.50", "1,234.5")
    review = text(owner_client.get(review_url(account, "2026-01")))
    assert "1 buy, $1,234.50 in all." in review
    assert "Judged by version 1 of the plan: $100.00 into INDEX" in review
    rows = list(
        csv.reader(StringIO(owner_client.get(logbook_url(account, "export.csv")).content.decode()))
    )
    assert rows[1][3:5] == ["1234.50", "1234.500000"]
    assert not any("$" in value or "," in value for value in rows[1][3:5])


@pytest.mark.django_db
def test_an_entry_a_paper_order_wrote_is_not_edited_by_hand(
    owner_client: Client, account: Account, plan: MethodPlan, logbook_rows: list[JournalEntry]
) -> None:
    PaperOrder.objects.create(
        account=account,
        plan=plan,
        month="2026-01",
        symbol="INDEX",
        notional=D("100"),
        client_order_id="iw-test-2026-01-INDEX",
        journal_entry=logbook_rows[0],
    )
    response = owner_client.get(logbook_url(account, f"{logbook_rows[0].pk}/edit/"), follow=True)
    assert response.redirect_chain == [(logbook_url(account), 302)]
    assert "A paper order wrote this line" in text(response)
    html = text(owner_client.get(logbook_url(account)))
    assert logbook_url(account, f"{logbook_rows[0].pk}/edit/") not in html
    assert logbook_url(account, f"{logbook_rows[1].pk}/edit/") in html


# --- Who may see what --------------------------------------------------------------------------


@pytest.mark.django_db
def test_every_new_route_is_the_owners_alone(
    client: Client,
    owner: User,
    someone: User,
    account: Account,
    plan: MethodPlan,
    logbook_rows: list[JournalEntry],
) -> None:
    open_due_reviews(plan, date(2026, 2, 28))
    entry = logbook_rows[0]
    pages = [
        logbook_url(account),
        logbook_url(account, "export.csv"),
        logbook_url(account, f"{entry.pk}/edit/"),
        method_url(account, "change/"),
        review_url(account, "2026-01"),
    ]
    actions = [review_url(account, "2026-01", "close/"), review_url(account, "2026-01", "reopen/")]
    for url in pages + actions:
        response = client.post(url) if url in actions else client.get(url)
        assert response.status_code == 302 and response["Location"].startswith("/auth/witus/login/")
    client.force_login(someone)
    for url in pages:
        assert client.get(url).status_code == 404, url
    for url in actions:
        assert client.post(url, ANSWERS).status_code == 404, url
    client.force_login(owner)
    for url in actions:
        assert client.get(url).status_code == 405, url
    assert client.get(review_url(account, "2026-1")).status_code == 404
    assert client.get(review_url(account, "2030-01")).status_code == 404
    strict = Client(enforce_csrf_checks=True)
    strict.force_login(owner)
    assert strict.post(actions[0], ANSWERS).status_code == 403
    assert strict.post(method_url(account, "change/"), {}).status_code == 403
    assert not MonthlyReview.objects.filter(closed_at__isnull=False).exists()


@pytest.mark.django_db
def test_the_admin_keeps_reviews_read_only(
    admin_client: Client, owner: User, plan: MethodPlan
) -> None:
    [review, *_] = open_due_reviews(plan, date(2026, 2, 28))
    entries = [buy(plan.account, date(2026, 1, 2))]
    close_review(review, build_review(plan, entries, date(2026, 2, 28)), by=owner, **ANSWERS)
    assert admin_client.get("/admin/methods/monthlyreview/").status_code == 200
    assert admin_client.get("/admin/methods/monthlyreview/add/").status_code == 403
    assert admin_client.get(f"/admin/methods/monthlyreview/{review.pk}/delete/").status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_public_pages_are_unchanged(
    client: Client, plan: MethodPlan, logbook_rows: list[JournalEntry], path: str
) -> None:
    open_due_reviews(plan, timezone.localdate() + timedelta(days=1))
    html = text(client.get(path))
    assert "<table" not in html.lower()
    assert "/accounts/" not in html and "/logbook/" not in html
    for words in ("Logbook", "Close last month", SKIP_REASON, "Monthly reviews"):
        assert words not in html, words
