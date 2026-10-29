"""Chapter 10 checkpoint: the method engine on the web, in three views. A plan row that round-trips
to chapter 03's `Plan` and a journal row that round-trips to its `Entry`; a method started from a
form, one active plan per account; chapter 03's `review` run unchanged against the rows, every
finding shown with its rule's text and its lesson or "lesson coming"; three views, A, B and C, of
one context, for the owner only, the choice remembered in the session; and public pages that
still show no table, no link and no rule."""

from datetime import date
from decimal import Decimal
from html import unescape
from html.parser import HTMLParser
from typing import Protocol

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client
from django.utils import timezone

from invest_witus.adherence.journal import Action, Entry
from invest_witus.adherence.plan import Plan
from invest_witus.adherence.review import CHECKED_RULES
from invest_witus.methods.rulebook import Method, Rule, available_methods, load_method
from invest_witus.prices.csv_file import PricePoint
from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.engine import (
    build_review,
    month_rows,
    next_action,
    rule_lines,
)
from invest_witus_site.methods.models import JournalEntry, MethodPlan
from invest_witus_site.methods.views import SESSION_KEY
from invest_witus_site.prices.models import DailyClose

D = Decimal
# Placeholder symbols only, as every chapter: INDEX and OTHER from chapter 02.
CHARACTER_RULE = "only letters, digits, a dot and a hyphen are allowed"
METHOD_NAME = "Index investing with a fixed monthly contribution"
WINDOW_RULE = (
    "Buy within the plan's buy window at the start of the month, "
    "not when the news makes you feel ready."
)
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
# The three views, by letter, with the heading only that view prints when a plan runs.
VIEW_HEADINGS = {"a": "My plan", "b": "Rule checks", "c": "The rules, and what to re-read"}


# --- Fixtures: an owner, an account, a plan from January, a journal with one break -----------


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("owner", email="owner@example.com")


@pytest.fixture
def someone(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("someone")


@pytest.fixture
def account(owner: User) -> Account:
    return Account.objects.create(
        name="Practice", broker="Example Broker", kind="paper", owner=owner
    )


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
def journal(account: Account) -> list[JournalEntry]:
    """January on time with the shares recorded; February on day 12, outside the window."""
    first = JournalEntry.objects.create(
        account=account,
        date=date(2026, 1, 2),
        action="buy",
        symbol="INDEX",
        amount=D("100.00"),
        shares=D("0.5"),
        note="first buy",
    )
    second = JournalEntry.objects.create(
        account=account, date=date(2026, 2, 12), action="buy", symbol="INDEX", amount=D("100.00")
    )
    return [first, second]


def next_month_first(today: date) -> date:
    return date(today.year + 1, 1, 1) if today.month == 12 else date(today.year, today.month + 1, 1)


class Page(Protocol):
    """What the test client answers with: the one attribute the helper below reads."""

    content: bytes


def text(response: Page) -> str:
    """The page with Django's escaping undone, so a rule's apostrophe and a `&` in a link read
    as they were written. The table reader below does the same on its own."""
    return unescape(response.content.decode())


def page_url(account: Account, query: str = "") -> str:
    return f"/accounts/{account.pk}/method/{query}"


def start_url(account: Account) -> str:
    return f"/accounts/{account.pk}/method/start/"


def log_url(account: Account) -> str:
    return f"/accounts/{account.pk}/method/log/"


def entry(
    day: date, action: str = "buy", amount: str = "100.00", shares: str | None = None
) -> JournalEntry:
    """An unsaved row, for the pure functions: no database, no account."""
    return JournalEntry(
        date=day,
        action=action,
        symbol="INDEX",
        amount=D(amount),
        shares=None if shares is None else D(shares),
    )


class Tables(HTMLParser):
    """Every table on a page as its rows, each row a tuple of its cells' text: chapter 09's
    reader, unchanged."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[tuple[str, ...]]] = []
        self._cells: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self.tables.append([])
        elif tag == "tr":
            self._cells = []
        elif tag in ("td", "th") and self._cells is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._cell is not None and self._cells is not None:
            self._cells.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._cells is not None:
            self.tables[-1].append(tuple(self._cells))
            self._cells = None


def tables_in(html: str) -> list[list[tuple[str, ...]]]:
    parser = Tables()
    parser.feed(html)
    return parser.tables


# --- The package's methods ---------------------------------------------------------------------


def test_the_package_lists_its_methods_and_the_rules_file_still_matches_the_checks() -> None:
    # Chapter 14 ships a second method, so this asserts membership, not the whole list.
    assert "index-dca" in [method.id for method in available_methods()]
    assert {rule.id for rule in load_method("index-dca").rules} == CHECKED_RULES


def test_rule_lines_take_the_lesson_from_the_rule_then_the_method_else_none() -> None:
    method = Method(
        id="example",
        name="Example",
        version=1,
        summary="",
        lesson="https://learn.example/method",
        rules=(
            Rule("own", "Has its own lesson.", "https://learn.example/own"),
            Rule("shared", "Uses the method's lesson.", ""),
        ),
    )
    assert [(line.id, line.lesson_url) for line in rule_lines(method)] == [
        ("own", "https://learn.example/own"),
        ("shared", "https://learn.example/method"),
    ]
    assert [line.lesson_url for line in rule_lines(load_method("index-dca"))] == [None] * 5


# --- The two rows and chapter 03's values ------------------------------------------------------


@pytest.mark.django_db
def test_a_plan_round_trips_to_chapter_03s_plan(account: Account) -> None:
    row = MethodPlan.objects.create(
        account=account,
        method_id="index-dca",
        amount=D("100.005"),
        buy_window_days=7,
        symbols="index, other index",
        started_on=date(2026, 1, 1),
    )
    assert row.symbols == "INDEX OTHER" and row.amount == D("100.01")
    assert row.to_plan() == Plan(
        method="index-dca",
        start=date(2026, 1, 1),
        amount=D("100.01"),
        symbols=frozenset({"INDEX", "OTHER"}),
        buy_window_days=7,
    )
    assert row.method().name == METHOD_NAME and row.active
    assert str(row) == "index-dca on Practice (Example Broker)"
    assert MethodPlan.active_for(account) == row


@pytest.mark.django_db
def test_a_plan_refuses_a_float_an_unknown_method_and_a_bad_symbol(account: Account) -> None:
    fields = {"account": account, "buy_window_days": 7, "started_on": date(2026, 1, 1)}
    with pytest.raises(TypeError, match="not a float"):
        MethodPlan(method_id="index-dca", amount=100.0, symbols="INDEX", **fields).save()  # type: ignore[arg-type]
    unknown = MethodPlan(method_id="get-rich-quick", amount=D("100"), symbols="INDEX", **fields)
    with pytest.raises(ValidationError) as refused:
        unknown.full_clean()
    assert refused.value.message_dict["method_id"] == ["unknown method 'get-rich-quick'"]
    with pytest.raises(ValidationError):
        unknown.save()
    bad = MethodPlan(method_id="index-dca", amount=D("100"), symbols="a$b", **fields)
    with pytest.raises(ValidationError) as refused:
        bad.full_clean()
    assert refused.value.message_dict["symbols"] == [f"Not a symbol: A$B ({CHARACTER_RULE})."]
    with pytest.raises(ValueError, match=CHARACTER_RULE):
        bad.save()
    assert MethodPlan.objects.count() == 0


@pytest.mark.django_db
def test_one_active_plan_per_account(plan: MethodPlan, account: Account) -> None:
    second = MethodPlan(
        account=account,
        method_id="index-dca",
        amount=D("50"),
        buy_window_days=5,
        symbols="OTHER",
        started_on=date(2026, 6, 1),
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        second.save()
    plan.active = False
    plan.save()
    second.save()
    assert MethodPlan.active_for(account) == second
    assert list(MethodPlan.objects.filter(account=account).values_list("active", flat=True)) == [
        True,
        False,
    ]


@pytest.mark.django_db
def test_an_entry_round_trips_to_chapter_03s_entry(account: Account) -> None:
    later = JournalEntry.objects.create(
        account=account, date=date(2026, 2, 2), action="sell", symbol="index", amount=D("50")
    )
    earlier = JournalEntry.objects.create(
        account=account,
        date=date(2026, 1, 2),
        action="buy",
        symbol=" index ",
        amount=D("100.005"),
        shares=D("0.9123456789"),
    )
    assert earlier.symbol == "INDEX" and earlier.amount == D("100.01")
    assert earlier.shares == D("0.912345")
    assert earlier.to_entry() == Entry(date(2026, 1, 2), Action.BUY, "INDEX", D("100.01"))
    assert later.to_entry().action is Action.SELL and later.shares is None
    assert JournalEntry.entries_for(account) == [earlier, later]
    assert str(earlier) == "2026-01-02 buy $100.01 of INDEX"


@pytest.mark.django_db
def test_an_entry_refuses_a_float_a_bad_symbol_a_zero_amount_and_an_unknown_action(
    account: Account,
) -> None:
    fields = {"account": account, "date": date(2026, 1, 2), "symbol": "INDEX"}
    with pytest.raises(TypeError, match="not a float"):
        JournalEntry(action="buy", amount=100.0, **fields).save()  # type: ignore[arg-type]
    with pytest.raises(ValueError, match=CHARACTER_RULE):
        JournalEntry(
            account=account, date=date(2026, 1, 2), action="buy", symbol="AB CD", amount=D("100")
        ).save()
    with pytest.raises(ValidationError) as refused:
        JournalEntry(action="hold", amount=D("0"), **fields).full_clean()
    assert set(refused.value.message_dict) == {"action", "amount"}
    assert JournalEntry.objects.count() == 0


# --- The engine: chapter 03's review, arranged ------------------------------------------------


@pytest.mark.django_db
def test_the_review_on_the_web_is_chapter_03s_review(
    plan: MethodPlan, journal: list[JournalEntry]
) -> None:
    review = build_review(plan, journal, through=date(2026, 2, 28))
    assert review.method.name == METHOD_NAME and review.entries == journal
    assert [(f.month, f.rule.id, f.message, f.rule.lesson_url) for f in review.findings] == [
        ("2026-02", "buy-in-window", "Bought on day 12; the window is days 1 to 7.", None)
    ]
    assert review.findings[0].rule.text == WINDOW_RULE
    assert not review.on_plan and (review.months_done, review.months_due) == (2, 2)
    assert [(c.rule.id, c.status, c.evidence) for c in review.checks] == [
        ("one-buy-each-month", "pass", "no findings"),
        ("buy-in-window", "fail", "1 finding: 2026-02"),
        ("fixed-amount", "pass", "no findings"),
        ("plan-symbols-only", "pass", "no findings"),
        ("no-selling", "pass", "no findings"),
    ]
    assert [(r.label, r.status, r.buys, r.amount, r.shares, r.rule_ids) for r in review.months] == [
        ("2026-01", "done", 1, D("100.00"), D("0.5"), []),
        ("2026-02", "done", 1, D("100.00"), None, ["buy-in-window"]),
    ]
    assert (review.next_action.label, review.next_action.status) == ("2026-03", "upcoming")
    on_plan = build_review(plan, journal, through=date(2026, 1, 31))
    assert on_plan.on_plan and on_plan.findings == [] and on_plan.months_due == 1


def test_month_rows_mark_each_month_done_missed_or_open() -> None:
    plan = Plan("index-dca", date(2026, 1, 1), D("100"), frozenset({"INDEX"}), 7)
    rows = [entry(date(2026, 1, 2), shares="0.5"), entry(date(2026, 3, 3))]
    assert [
        (r.label, r.status, r.buys, r.shares) for r in month_rows(plan, rows, [], date(2026, 3, 5))
    ] == [
        ("2026-01", "done", 1, D("0.5")),
        ("2026-02", "missed", 0, None),
        ("2026-03", "done", 1, None),
    ]
    april = month_rows(plan, rows, [], date(2026, 4, 3))
    assert [(r.label, r.status, r.window_closes) for r in april][-2:] == [
        ("2026-03", "done", date(2026, 3, 7)),
        ("2026-04", "open", date(2026, 4, 7)),
    ]
    assert month_rows(plan, rows, [], date(2025, 12, 31)) == []
    # A buy before the plan's start is not the plan's; a sell is never a buy.
    before = [entry(date(2025, 12, 30)), entry(date(2026, 1, 20), action="sell")]
    assert [(r.status, r.buys) for r in month_rows(plan, before, [], date(2026, 1, 31))] == [
        ("missed", 0)
    ]


def test_the_next_action_is_the_next_window() -> None:
    plan = Plan("index-dca", date(2026, 1, 1), D("100"), frozenset({"INDEX", "OTHER"}), 7)
    bought = [Entry(date(2026, 1, 2), Action.BUY, "INDEX", D("100"))]
    cases: list[tuple[date, list[Entry], str, str]] = [
        (date(2025, 12, 15), [], "2026-01", "upcoming"),
        (date(2026, 1, 3), [], "2026-01", "due"),
        (date(2026, 1, 3), bought, "2026-02", "upcoming"),
        (date(2026, 1, 20), [], "2026-02", "upcoming"),
        (date(2026, 12, 20), [], "2027-01", "upcoming"),
    ]
    for today, entries, label, status in cases:
        action = next_action(plan, entries, today)
        assert (action.label, action.status) == (label, status), today
        assert action.closes == action.opens.replace(day=7) and action.opens.day == 1
        assert action.amount == D("100") and action.symbols == ["INDEX", "OTHER"]


# --- Starting a method, from the form ----------------------------------------------------------


@pytest.mark.django_db
def test_the_owner_starts_a_method_from_the_form(
    client: Client, owner: User, account: Account
) -> None:
    client.force_login(owner)
    start = next_month_first(timezone.localdate())
    data = {
        "method_id": "index-dca",
        "amount": "100",
        "buy_window_days": "7",
        "symbols": "index, other",
        "started_on": start.isoformat(),
    }
    response = client.post(start_url(account), data, follow=True)
    assert response.redirect_chain == [(page_url(account), 302)]
    plan = MethodPlan.objects.get(account=account)
    assert (plan.method_id, plan.amount, plan.symbols, plan.started_on) == (
        "index-dca",
        D("100.00"),
        "INDEX OTHER",
        start,
    )
    html = text(response)
    assert f"Started {METHOD_NAME} on Practice." in html
    assert client.session[SESSION_KEY] == "a" and VIEW_HEADINGS["a"] in html
    assert "You are on plan" in html and "0 of 0 scheduled buys made" in html
    window_end = start.replace(day=7).isoformat()
    assert f"Buy $100.00 of INDEX, OTHER between {start.isoformat()} and {window_end}." in html
    assert html.count("lesson coming") == 5


@pytest.mark.django_db
def test_the_form_refuses_a_second_active_plan_and_bad_numbers(
    client: Client, owner: User, account: Account, plan: MethodPlan
) -> None:
    client.force_login(owner)
    good = {
        "method_id": "index-dca",
        "amount": "100",
        "buy_window_days": "7",
        "symbols": "INDEX",
        "started_on": "2026-06-01",
    }
    response = client.post(start_url(account), good)
    assert response.status_code == 200
    assert "This account already runs a method." in text(response)
    plan.active = False
    plan.save()
    for change, message in [
        ({"symbols": "a$b"}, f"Not a symbol: A$B ({CHARACTER_RULE})."),
        ({"symbols": " , "}, "Name at least one symbol."),
        ({"symbols": ""}, "This field is required."),
        ({"buy_window_days": "40"}, "Ensure this value is less than or equal to 28."),
        ({"amount": "0"}, "Ensure this value is greater than or equal to 0.01."),
        ({"method_id": "get-rich-quick"}, "Select a valid choice."),
    ]:
        refused = client.post(start_url(account), {**good, **change})
        assert refused.status_code == 200 and message in text(refused), change
        assert VIEW_HEADINGS["c"] not in text(refused)
        assert "Start a method on this account" in text(refused)
    assert MethodPlan.objects.filter(active=True).count() == 0


# --- The review page -------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_page_shows_a_planted_break_with_its_rule_text_and_lesson_coming(
    client: Client, owner: User, account: Account, plan: MethodPlan, journal: list[JournalEntry]
) -> None:
    client.force_login(owner)
    html = text(client.get(page_url(account, "?through=2026-02-28")))
    assert "Off plan: 1 thing to look at" in html
    assert "<strong>2026-02</strong> Bought on day 12; the window is days 1 to 7." in html
    assert f"Rule: {WINDOW_RULE}" in html and "lesson coming" in html
    assert "2 of 2 scheduled buys made through 2026-02-28" in html
    assert "Buy $100.00 of INDEX between 2026-03-01 and 2026-03-07." in html
    assert 'href="http' not in html.split("Rule:")[1].split("</li>")[0], "no invented lesson URL"


@pytest.mark.django_db
def test_no_findings_is_a_sentence_in_every_view(
    client: Client, owner: User, account: Account, plan: MethodPlan, journal: list[JournalEntry]
) -> None:
    client.force_login(owner)
    sentences = {
        "a": "You followed every rule through 2026-01-31. Nothing to look at.",
        "b": "No findings through 2026-01-31: every rule passed.",
        "c": "You followed every rule through 2026-01-31. Nothing to look at.",
    }
    for view, sentence in sentences.items():
        html = text(client.get(page_url(account, f"?view={view}&through=2026-01-31")))
        assert sentence in html and "Off plan" not in html, view


@pytest.mark.django_db
def test_view_b_tables_every_month_with_amounts_and_shares(
    client: Client, owner: User, account: Account, plan: MethodPlan, journal: list[JournalEntry]
) -> None:
    client.force_login(owner)
    html = text(client.get(page_url(account, "?view=b&through=2026-02-28")))
    checks, months, findings, entries = tables_in(html)
    assert checks[0] == ("Rule", "Status", "Evidence", "Lesson")
    assert checks[2] == (WINDOW_RULE, "fail", "1 finding: 2026-02", "lesson coming")
    assert [row[1] for row in checks[1:]] == ["pass", "fail", "pass", "pass", "pass"]
    assert months == [
        ("Month", "Window closes", "Status", "Buys", "Amount", "Shares", "Rules flagged"),
        ("2026-01", "2026-01-07", "done", "1", "$100.00", "0.5", "none"),
        ("2026-02", "2026-02-07", "done", "1", "$100.00", "not recorded", "buy-in-window"),
    ]
    assert findings[1] == (
        "2026-02-12",
        WINDOW_RULE,
        "Bought on day 12; the window is days 1 to 7.",
        "lesson coming",
    )
    assert entries[1] == ("2026-01-02", "Buy", "INDEX", "$100.00", "0.5", "first buy")
    assert entries[2] == ("2026-02-12", "Buy", "INDEX", "$100.00", "not recorded", "")
    assert "Paper (practice) (Example Broker)" in html and "version 1 (index-dca)" in html


# --- Three views, one toggle -----------------------------------------------------------------


@pytest.mark.django_db
def test_the_three_views_render_for_the_owner_and_404_for_another_owner(
    client: Client,
    owner: User,
    someone: User,
    account: Account,
    plan: MethodPlan,
    journal: list[JournalEntry],
) -> None:
    client.force_login(owner)
    for view, heading in VIEW_HEADINGS.items():
        response = client.get(page_url(account, f"?view={view}"))
        assert response.status_code == 200
        html = text(response)
        assert heading in html, view
        assert f'<a href="?view={view}" aria-current="page">' in html
        assert html.count('aria-current="page"') == 1
        for other, other_heading in VIEW_HEADINGS.items():
            if other != view:
                assert other_heading not in html, (view, other)
    client.force_login(someone)
    for view in VIEW_HEADINGS:
        assert client.get(page_url(account, f"?view={view}")).status_code == 404
    assert client.post(start_url(account), {}).status_code == 404
    assert client.post(log_url(account), {}).status_code == 404
    assert MethodPlan.objects.count() == 1 and JournalEntry.objects.count() == 2


@pytest.mark.django_db
def test_the_view_choice_persists_in_the_session(
    client: Client, owner: User, account: Account, plan: MethodPlan
) -> None:
    client.force_login(owner)
    assert VIEW_HEADINGS["a"] in text(client.get(page_url(account))), "A is the home"
    client.get(page_url(account, "?view=b"))
    assert client.session[SESSION_KEY] == "b"
    assert VIEW_HEADINGS["b"] in text(client.get(page_url(account)))
    assert VIEW_HEADINGS["b"] in text(client.get(page_url(account, "?view=zzz")))
    assert client.session[SESSION_KEY] == "b"
    html = text(client.get(page_url(account, "?view=c&through=2026-02-28")))
    assert client.session[SESSION_KEY] == "c"
    assert '<a href="?view=a&through=2026-02-28">' in html, "the switch keeps the review date"
    # A fresh session with no choice: C while no method runs, A once one does.
    fresh = Client()
    fresh.force_login(owner)
    plan.active = False
    plan.save()
    assert "Start a method on this account" in text(fresh.get(page_url(account)))
    plan.active = True
    plan.save()
    assert VIEW_HEADINGS["a"] in text(fresh.get(page_url(account)))


@pytest.mark.django_db
def test_every_view_shows_the_same_plan_rules_findings_and_journal_and_no_price(
    client: Client, owner: User, account: Account, plan: MethodPlan, journal: list[JournalEntry]
) -> None:
    DailyClose.upsert("INDEX", [PricePoint(date(2026, 2, 27), D("123.456789"))], "csv")
    client.force_login(owner)
    rules = [rule.text for rule in load_method("index-dca").rules]
    for view in VIEW_HEADINGS:
        html = text(client.get(page_url(account, f"?view={view}&through=2026-02-28")))
        assert "100.00" in html and "INDEX" in html and "2026-01-01" in html, view
        assert all(rule in html for rule in rules), view
        assert html.count("lesson coming") >= 5, view
        assert "Bought on day 12; the window is days 1 to 7." in html, view
        assert "first buy" in html and "2026-01-02" in html and "2026-02-12" in html, view
        assert "Paper (practice) account. Simulated money" in html, view
        assert "123.45" not in html and "123,45" not in html, view
        assert f'action="{log_url(account)}"' in html, view


# --- Logging an entry ------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_owner_logs_an_entry_from_the_form(
    client: Client, owner: User, account: Account, plan: MethodPlan
) -> None:
    client.force_login(owner)
    data = {
        "date": "2026-01-02",
        "action": "buy",
        "symbol": "index",
        "amount": "100",
        "shares": "",
        "note": "",
    }
    response = client.post(log_url(account), data, follow=True)
    assert response.redirect_chain == [(page_url(account), 302)]
    row = JournalEntry.objects.get(account=account)
    assert (row.symbol, row.amount, row.shares) == ("INDEX", D("100.00"), None)
    assert "Logged: 2026-01-02 buy $100.00 of INDEX." in text(response)
    for change, message in [
        ({"amount": "0"}, "Ensure this value is greater than or equal to 0.01."),
        ({"symbol": "AB CD"}, CHARACTER_RULE),
        ({"action": "hold"}, "Select a valid choice."),
        ({"date": ""}, "This field is required."),
    ]:
        refused = client.post(log_url(account), {**data, **change})
        assert refused.status_code == 200 and message in text(refused), change
    assert JournalEntry.objects.count() == 1


@pytest.mark.django_db
def test_the_method_routes_need_a_sign_in_and_the_actions_a_post(
    client: Client, owner: User, account: Account
) -> None:
    for path in (page_url(account), start_url(account), log_url(account)):
        response = client.post(path, {}) if path != page_url(account) else client.get(path)
        assert response.status_code == 302
        assert response["Location"] == f"/auth/witus/login/?next={path}"
    client.force_login(owner)
    assert client.get(start_url(account)).status_code == 405
    assert client.get(log_url(account)).status_code == 405
    strict = Client(enforce_csrf_checks=True)
    strict.force_login(owner)
    assert strict.post(start_url(account), {}).status_code == 403
    assert strict.post(log_url(account), {}).status_code == 403


# --- The account page, the public pages, the admin ------------------------------------------


@pytest.mark.django_db
def test_the_account_page_names_the_method_or_invites_one(
    client: Client, owner: User, account: Account
) -> None:
    client.force_login(owner)
    html = text(client.get(f"/accounts/{account.pk}/"))
    assert "No method yet on this account." in html
    assert f'<a href="{page_url(account)}?view=c">Read the rules and start one.</a>' in html
    MethodPlan.objects.create(
        account=account,
        method_id="index-dca",
        amount=D("100"),
        buy_window_days=7,
        symbols="INDEX",
        started_on=date(2026, 1, 1),
    )
    html = text(client.get(f"/accounts/{account.pk}/"))
    assert f'<a href="{page_url(account)}">{METHOD_NAME}</a>' in html
    assert "100.00 into INDEX within the first 7 days of each month, since 2026-01-01." in html


@pytest.mark.django_db
@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_public_pages_show_no_table_no_method_link_and_no_rule(
    client: Client, plan: MethodPlan, journal: list[JournalEntry], path: str
) -> None:
    html = text(client.get(path))
    assert "<table" not in html.lower()
    assert "/accounts/" not in html and "/method/" not in html
    assert "Buy once in every month of the plan." not in html


@pytest.mark.django_db
def test_the_admin_lists_plans_and_entries_and_refuses_an_unknown_method(
    admin_client: Client, account: Account, plan: MethodPlan, journal: list[JournalEntry]
) -> None:
    assert admin_client.get("/admin/methods/methodplan/").status_code == 200
    assert admin_client.get("/admin/methods/journalentry/").status_code == 200
    data = {
        "account": account.pk,
        "method_id": "get-rich-quick",
        "amount": "100",
        "buy_window_days": "7",
        "symbols": "INDEX",
        "started_on": "2026-06-01",
        "active": "",
    }
    response = admin_client.post("/admin/methods/methodplan/add/", data)
    assert response.status_code == 200
    assert "unknown method 'get-rich-quick'" in text(response)
    assert MethodPlan.objects.count() == 1
