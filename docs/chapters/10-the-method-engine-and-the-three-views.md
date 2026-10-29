# Chapter 10: The method engine and the three views

**Starts from:** tag `v09`. **Ends at:** tag `v10`.
**Written against:** Python 3.14.10, uv 0.13.6, Django 5.2.18, and the Django 5.2 documentation pages as read on
October 28, 2026.
**Goal:** the product's core on the web. The signed-in owner picks a method the package ships, writes down the
plan's numbers for one account, logs what they bought, and reads chapter 03's review of the journal against the
method's rules, with every rule and every finding linking the lesson that explains it, or saying "lesson coming"
when the rules file has no link yet. The same plan, rules, review and journal render three ways, A, B and C, as
the research named them, through one switch the session remembers. Another owner's account is a 404 for every
view and every action; no public page shows a rule, a table or a link to the page; nothing on the page is a
price.
**Time:** 4 to 5 hours for the code and tests. The owner's step (the migration and the first method on the live
site) takes 15 minutes.

The listings in this chapter are not typed in by hand. `scripts/render_chapter.py` pastes the real files from
tag `v10` into the chapter text, so what you read and what the tests run are the same bytes.

## What you will learn

- **A row that is a value:** two models whose only job is to round-trip to chapter 03's `Plan` and `Entry`, so
  the review written for the command line runs on the web without a line changed.
- **Rules read from the package, not copied into rows:** the plan stores the method's id, and `load_method`
  reads the TOML file at request time, so a lesson link added to the file reaches every page at once and a
  rule with no link reads "lesson coming" because the file says so.
- **A partial unique constraint:** `UniqueConstraint` with a `condition`, which lets one account keep an ended
  plan as history while the database refuses a second active one.
- **A `ModelForm`:** the journal's add form built from the model, with the model's validators running as part
  of the form's own validation.
- **A context built once and rendered three ways:** a service module that arranges the review (per rule, per
  month, the next action), and `{% include %}` with a template name that is a variable.
- **The session as a per-visitor memory:** `request.session` holding the view the person chose, and why that
  choice ends with the sign-out.
- **A `Protocol` in a test,** the smallest type that says "this has `content`".

## Before the code: what the PRD and the research ask, and seven decisions

**What the PRD asks.** Section 7.1: a method is a rule block, each rule with text and a `lesson` field that is
the lesson's URL or empty, shown as "lesson coming"; the user's plan is separate, the method plus their own
numbers; every evaluation shows each rule's status as text, the evidence, and the lesson link; the app never
proposes a security outside the user's plan. Section 7.2: three views over the same data, all built, with a
toggle that is keyboard operable and announces the current view; A as the everyday home, C to start a method,
B behind an "Operator" label; every table captioned with header `scope`; the environment printed as text on
every signed-in page. The research (`docs/research/01-ux-benchmarks-and-three-directions.md`, section 5) names
the three: A, "The Plan and the Logbook", a written plan with one next action and a logbook beside it; B,
"Method Console", a control room with rule checks, evidence and a lesson column; C, "The Lesson Lab", where the
lesson is the screen and the paper account is the lab. The mockup in `docs/research/mockups/` draws each one
with 12-1 momentum as its example; this chapter builds them with the method the package ships, and the mockup
is a guide for what each view puts first, not a contract for its layout.

**Decision 1: a `methods` app beside the library's `methods` package, and the rules stay in the file.** The
library has had the engine since chapter 03: `methods/index_dca.toml`, `rulebook.py`, `adherence/plan.py`,
`adherence/journal.py` and `adherence/review.py`. The web layer wraps them; it does not rewrite them. A
`MethodPlan` row holds the method's id and the person's numbers, never a rule, and `load_method(method_id)`
reads the TOML file whenever a page needs the rules, so a lesson URL added to the file tomorrow reaches every
plan at once and no row goes stale. One function joins the library, `available_methods()`, which lists the
rules files the package ships so the start form reads the list instead of hardcoding it; the no-move rule
holds, nothing from chapters 01 to 09 moved. The import graph stays a line: `methods.models` imports
`holdings.models` and chapter 09's symbol rule from `watchlist.models`; `holdings.views` imports
`methods.models` for one line on the account page; `methods.views` imports `holdings.models` for the ownership
query and nothing from `holdings.views`. Decisions log, row 86.

**Decision 2: the plan row mirrors chapter 03's `Plan`, with symbols as text and one active plan per
account.** `MethodPlan(account, method_id, amount, buy_window_days, symbols, started_on, active)`: the five
fields of the `Plan` value plus the account and a flag. `symbols` is a text column, the symbols separated by
spaces, each through chapter 09's rule on the way in, because the review wants a `frozenset` and a text column
becomes one in a single `split()`; a JSON column or a table of symbols would be more machinery for the same
five characters. A `UniqueConstraint` on the account with `condition=Q(active=True)` lets an ended plan stay as
history, `active` off, while the database refuses a second active one; the form says the same in words before
the database has to. Ending a plan is an admin step in this chapter. The PRD's plan versions with a dated note
are chapter 12's, with the change-of-plan reason the journal needs. Row 87.

**Decision 3: the journal row mirrors `Entry`, plus shares and a note.** `JournalEntry(account, date, action,
symbol, amount, shares, note)`. The action's choices are built from chapter 03's `Action` enum, so a value the
review does not know cannot be stored and the two cannot drift. Shares are optional: a confirmation shows them,
a statement shows them later, and a person logging from memory may not have them; a month whose buys lack them
prints "not recorded" instead of a partial total. This is the minimum the review needs. Chapter 12 builds the
logbook on this table: automatic entries, tags, skips and exceptions with reasons, the rule-following rate, the
export. Row 88.

**Decision 4: `review()` runs unchanged; the engine module arranges.** Two converters, `to_plan()` and
`to_entry()`, and one call, the same as `run_review` made in chapter 03. Everything else in
`methods/engine.py` is arrangement of what comes back: each rule as a line with its lesson URL or `None`,
which the template prints as "lesson coming"; each rule as a check with its status in words and its evidence
in words, "1 finding: 2026-02"; each month of the plan as a row that is done, missed or open, with the buys,
the amount and the shares; and the next action, the next buy window, due now or upcoming. The page reviews
through today unless `?through=YYYY-MM-DD` says otherwise, as chapter 03's `--through` did, and says which day
it reviewed through. Row 89.

**Decision 5: three templates, one context, a switch of plain links remembered in the session.** The page
builds its context once and renders it through `methods/_view_a.html`, `_view_b.html` or `_view_c.html`,
picked by `?view=a|b|c`; the view handling the request writes the choice into `request.session`, and the
next request without `?view=` reads it back. With no choice made, the page opens on A when a method runs and
on C when none does, which is PRD 7.2's "starting a new method opens C; the everyday home is A". The switch is
three links with `aria-current="page"` on the current one, which a screen reader announces, and no script. The
PRD asked for the choice to be saved per user and restored at the next sign-in; the session is what this
chapter has, and `logout()` flushes it, so the choice lasts a sign-in; a preference column on the person is
exercise 1. The PRD also put the toggle in the header; it lives on the method page because the page is per
account. Row 90.

**Decision 6: what each view leaves out, on purpose.** The three views show the same plan, rules, findings,
months and journal; none shows a figure the others hide. B is read-only tables and the same log form the
others carry: no order queue, no envelope chart, no promotion checklist, because there is no broker until
chapter 11 and this method has no backtest range to draw. A's next action is a sentence and the log form is
its "Confirm"; a "Skip" that asks why is a journal entry with a reason, chapter 12's. C's rules do not switch
on one at a time: the package ships one method whose five rules come from one lesson set, and until the
course content exists the plan names the method and all five rules are on. Row 91.

**Decision 7: no price on the method page.** Adherence is about what you did, not what it is worth. The
account page (chapter 08) values the statement; the method page shows amounts and shares from the journal and
nothing from the prices table, so a test can plant a close and assert that no view prints it. The research's
"performance, deliberately small" at the bottom of A waits for the paper account in chapter 11, where a value
has a source the page can name. Row 92.

## Steps

### 10.1 The tests

Listing 10-1, Filename: `tests/test_ch10.py`:

```python
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
    assert [method.id for method in available_methods()] == ["index-dca"]
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
    assert str(earlier) == "2026-01-02 buy 100.01 of INDEX"


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
    assert f"Buy 100.00 of INDEX, OTHER between {start.isoformat()} and {window_end}." in html
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
    assert "Buy 100.00 of INDEX between 2026-03-01 and 2026-03-07." in html
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
        ("2026-01", "2026-01-07", "done", "1", "100.00", "0.50", "none"),
        ("2026-02", "2026-02-07", "done", "1", "100.00", "not recorded", "buy-in-window"),
    ]
    assert findings[1] == (
        "2026-02-12",
        WINDOW_RULE,
        "Bought on day 12; the window is days 1 to 7.",
        "lesson coming",
    )
    assert entries[1] == ("2026-01-02", "Buy", "INDEX", "100.00", "0.50", "first buy")
    assert entries[2] == ("2026-02-12", "Buy", "INDEX", "100.00", "not recorded", "")
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
    assert "Logged: 2026-01-02 buy 100.00 of INDEX." in text(response)
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
```

Things to notice:

- **Placeholder symbols only.** `INDEX` and `OTHER` from chapter 02 and one bad token. Never a real symbol, in
  a test or anywhere in the repository.
- **The `plan` and `journal` fixtures are the chapter's worked example.** A plan from January 1, 2026, 100.00
  into `INDEX` within the first seven days; a January buy on day 2 with the shares recorded; a February buy on
  day 12, outside the window. Reviewed through February 28 that is one finding, `buy-in-window`; reviewed
  through January 31 it is none. Most page tests pass `?through=` so they do not depend on the day they run.
- **The form test starts next month.** With `started_on` on the first of next month, no month is due yet
  whatever today's date, so the page reads "You are on plan" and names the coming window. A test that started
  the plan today would read differently on the 3rd and the 20th.
- **`text()` undoes Django's escaping.** The page prints a rule's apostrophe as `&#x27;` and a `&` in a link as
  `&amp;`; the helper runs the page through `html.unescape` so a test can compare the words the person reads.
  The table reader does the same on its own, through `HTMLParser`.
- **`Page` is a `Protocol`.** The test client's response is its own class in the type stubs, not
  `HttpResponse`; the helper asks for the one attribute it reads, `content`, and pyright is satisfied by any
  object that has it.
- **The engine tests build unsaved rows.** `month_rows` reads `JournalEntry` instances for their shares, and
  an instance that is never saved needs no database and no account, so those tests carry no `django_db` mark.
- **The constraint test wraps the second insert in `transaction.atomic()`,** as chapter 09's did, and then
  ends the first plan and saves the second to prove the constraint is on active plans only.
- **The no-price test plants a close.** `DailyClose.upsert` stores `123.456789` for `INDEX`; each view must
  print the plan's `INDEX` and must not print `123.45`.
- **The three headings.** Each view has one `<h2>` the other two never print, "My plan", "Rule checks" and
  "The rules, and what to re-read"; the view test asserts the one and the absence of the other two.

Run the tests:

Listing 10-2, Terminal:

```sh
uv run pytest tests/test_ch10.py
```

```text
tests/test_ch10.py:24: in <module>
    from invest_witus.methods.rulebook import Method, Rule, available_methods, load_method
E   ImportError: cannot import name 'available_methods' from 'invest_witus.methods.rulebook'
=========================== short test summary info ============================
ERROR tests/test_ch10.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.79s ===============================
```

Red at import, and the first missing name is the library's. No package is added this chapter, and no
environment variable.

### 10.2 One function in the library

Listing 10-3, Filename: `src/invest_witus/methods/rulebook.py`:

```python
"""Load a method's rules from the TOML file that ships inside the package."""

import tomllib
from dataclasses import dataclass
from importlib.resources import files

LESSON_COMING = "lesson coming"


class UnknownMethodError(LookupError):
    """No rules file ships for this method id."""


@dataclass(frozen=True, slots=True)
class Rule:
    id: str
    text: str
    lesson: str


@dataclass(frozen=True, slots=True)
class Method:
    id: str
    name: str
    version: int
    summary: str
    lesson: str
    rules: tuple[Rule, ...]

    def rule(self, rule_id: str) -> Rule:
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        raise KeyError(f"method {self.id!r} has no rule {rule_id!r}")

    def lesson_for(self, rule_id: str) -> str:
        """The rule's lesson, else the method's lesson, else 'lesson coming'."""
        return self.rule(rule_id).lesson or self.lesson or LESSON_COMING


def available_methods() -> list[Method]:
    """Every method that ships in this package, by id: one per `.toml` file. Chapter 10's start
    form reads this list, so a method added as a file appears there without a code change."""
    package = files("invest_witus.methods")
    ids = sorted(
        resource.name.removesuffix(".toml").replace("_", "-")
        for resource in package.iterdir()
        if resource.name.endswith(".toml")
    )
    return [load_method(method_id) for method_id in ids]


def load_method(method_id: str) -> Method:
    """Read `<method_id with underscores>.toml` from the methods package."""
    resource = files("invest_witus.methods") / f"{method_id.replace('-', '_')}.toml"
    if not resource.is_file():
        raise UnknownMethodError(f"unknown method {method_id!r}")
    data = tomllib.loads(resource.read_text(encoding="utf-8"))
    return Method(
        id=str(data["id"]),
        name=str(data["name"]),
        version=int(data["version"]),
        summary=str(data["summary"]),
        lesson=str(data.get("lesson", "")),
        rules=tuple(
            Rule(id=str(r["id"]), text=str(r["text"]), lesson=str(r.get("lesson", "")))
            for r in data["rules"]
        ),
    )
```

`available_methods` is the only change to chapter 03's file: the package's `.toml` files, by id, each loaded
through the function that was already there. `files("invest_witus.methods")` is the package as a folder-like
object, and `iterdir()` lists what ships in it, so a second rules file is a second method with no code change.
The test asks for `["index-dca"]` today and reasserts chapter 03's rule, that the file's rule ids equal
`CHECKED_RULES`, because the web layer rests on it.

### 10.3 The app, its settings line and its URLs

Make the folder `src/invest_witus_site/methods/` with an empty `__init__.py`, an empty `migrations/__init__.py`,
and a `templates/methods/` folder for the page and its partials.

Listing 10-4, Filename: `src/invest_witus_site/methods/apps.py`:

```python
from django.apps import AppConfig


class MethodsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "invest_witus_site.methods"
    verbose_name = "Methods"
```

Listing 10-5, Filename: `src/invest_witus_site/settings.py`:

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
```

One line in `INSTALLED_APPS` and one word in the docstring. Everything else is as chapter 09 left it.

Listing 10-6, Filename: `src/invest_witus_site/urls.py`:

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
    # The nightly price pull, called by Vercel's cron with the bearer secret (chapter 08).
    path("api/cron/", include("invest_witus_site.prices.urls")),
    path("", include("invest_witus_site.pages.urls")),
]
```

Listing 10-7, Filename: `src/invest_witus_site/methods/urls.py`:

```python
"""The method page and its two actions. `invest_witus_site/urls.py` mounts this file under
`accounts/<int:pk>/method/`, and the `pk` captured there reaches all three views."""

from django.urls import path

from invest_witus_site.methods import views

urlpatterns = [
    path("", views.method_page, name="method-page"),
    path("start/", views.start_method, name="method-start"),
    path("log/", views.log_entry, name="method-log"),
]
```

The include sits at `accounts/<int:pk>/method/`, beside chapter 09's `watch/`, and the `pk` captured there
reaches the page and both actions. Three names: `method-page`, `method-start`, `method-log`.

### 10.4 The two rows

Listing 10-8, Filename: `src/invest_witus_site/methods/models.py`:

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
        if isinstance(self.amount, float):
            raise TypeError(f"amount must be a Decimal, not a float ({self.amount!r})")
        validate_method_id(self.method_id)
        self.amount = to_money(self.amount)
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

- **Every field of `MethodPlan` has a chapter 03 twin.** `to_plan()` is the row as the value, five fields in
  the same order the `Plan` dataclass names them, and the review never sees the row. `method()` is the rules,
  read from the package now.
- **Three validators, so the admin's form refuses with a message beside the box.** `validate_method_id` asks
  `load_method` and turns its `UnknownMethodError` into a `ValidationError`; `validate_symbol_list` runs
  chapter 09's `parse_symbols` and names each refused token; the field's `MinValueValidator` keeps an amount
  at a cent or more. `save()` runs the first two again, so no caller that skipped the form can store a plan for
  a method that has no rules or a symbol outside the rule, and it raises a `TypeError` for a float, as every
  money column in this app does.
- **The partial unique constraint.** The constraints reference describes `condition` as "A `Q` object that
  specifies the condition you want the constraint to enforce", with the example
  `UniqueConstraint(fields=["user"], condition=Q(status="DRAFT"), name="unique_draft_user")`, which "ensures
  that each user only has one draft" (Django Software Foundation, n.d.-a). Here the field is the account and
  the condition is `active=True`: one active plan, any number of ended ones. The `CheckConstraint` beside it
  keeps the buy window between 1 and 28 in the database as well as in the form, and "Constraints are checked
  during the model validation" (Django Software Foundation, n.d.-a), so `full_clean()` reports a window of 40
  the way it reports a bad symbol.
- **`ACTION_CHOICES` is built from the enum.** A list comprehension over chapter 03's `Action`, so the column
  accepts exactly `buy` and `sell` and `to_entry()`'s `Action(self.action)` can never fail on a stored value.
- **Shares are nullable.** `null=True, blank=True`, rounded down to six places with chapter 01's `to_shares`
  when present, and the page prints "not recorded" when absent.

Make the migration. The generated file imports the validators from two apps, and ruff wants the imports
grouped, so the fix command runs too:

Listing 10-9, Terminal:

```sh
uv run --env-file .env python manage.py makemigrations methods
uv run ruff format src/invest_witus_site/methods/migrations/
uv run ruff check --fix src/invest_witus_site/methods/migrations/
```

```text
Migrations for 'methods':
  src/invest_witus_site/methods/migrations/0001_initial.py
    + Create model JournalEntry
    + Create model MethodPlan
1 file reformatted, 1 file left unchanged
Found 1 error (1 fixed, 0 remaining).
```

Listing 10-10, Filename: `src/invest_witus_site/methods/migrations/0001_initial.py`:

```python
# Generated by Django 5.2.18 on 2026-10-29 01:12

from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models

import invest_witus_site.methods.models
import invest_witus_site.watchlist.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("holdings", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="JournalEntry",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("date", models.DateField(help_text="The day the trade happened.")),
                (
                    "action",
                    models.CharField(choices=[("buy", "Buy"), ("sell", "Sell")], max_length=4),
                ),
                (
                    "symbol",
                    models.CharField(
                        max_length=20,
                        validators=[invest_witus_site.watchlist.models.validate_symbol],
                    ),
                ),
                (
                    "amount",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="The money that changed hands.",
                        max_digits=14,
                        validators=[django.core.validators.MinValueValidator(Decimal("0.01"))],
                    ),
                ),
                (
                    "shares",
                    models.DecimalField(
                        blank=True,
                        decimal_places=6,
                        help_text="From the confirmation, if shown. Optional.",
                        max_digits=18,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(Decimal("0"))],
                    ),
                ),
                ("note", models.CharField(blank=True, default="", max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="holdings.account"
                    ),
                ),
            ],
            options={
                "verbose_name": "journal entry",
                "verbose_name_plural": "journal entries",
                "ordering": ["account", "date", "pk"],
            },
        ),
        migrations.CreateModel(
            name="MethodPlan",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "method_id",
                    models.CharField(
                        help_text="The id of a rules file the package ships, such as index-dca.",
                        max_length=40,
                        validators=[invest_witus_site.methods.models.validate_method_id],
                    ),
                ),
                (
                    "amount",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="What the method buys each time.",
                        max_digits=14,
                        validators=[django.core.validators.MinValueValidator(Decimal("0.01"))],
                    ),
                ),
                (
                    "buy_window_days",
                    models.PositiveSmallIntegerField(
                        help_text="Buy within the first N days of each month, 1 to 28.",
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                (
                    "symbols",
                    models.CharField(
                        help_text="The fund or funds the plan names, separated by spaces.",
                        max_length=200,
                        validators=[invest_witus_site.methods.models.validate_symbol_list],
                    ),
                ),
                (
                    "started_on",
                    models.DateField(
                        help_text="The plan's first month; earlier trades are not reviewed."
                    ),
                ),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="holdings.account"
                    ),
                ),
            ],
            options={
                "verbose_name": "method plan",
                "verbose_name_plural": "method plans",
                "ordering": ["account", "-started_on", "-pk"],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("active", True)),
                        fields=("account",),
                        name="one_active_plan_per_account",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("buy_window_days__gte", 1), ("buy_window_days__lte", 28)
                        ),
                        name="buy_window_between_1_and_28",
                    ),
                ],
            },
        ),
    ]
```

Both tables depend on the holdings app's first migration, because of the foreign keys, and the two
constraints are written into the migration as the model wrote them, condition included.

Listing 10-11, Filename: `src/invest_witus_site/methods/admin.py`:

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

The admin is where a plan is ended in this chapter: `active` is editable in the list. Everything else about a
plan and a journal happens on the owner's page.

### 10.5 The engine

Listing 10-12, Filename: `src/invest_witus_site/methods/engine.py`:

```python
"""What the method page shows, built once: the plan, its rules with their lessons, the review's
findings, every month of the plan with its status, and the next action.

Chapter 03's `review` is called here exactly as the command line called it, on the values the
two converters in `models.py` produce. Everything else in this module is arrangement: the same
findings grouped by rule for a table, by month for another, and the one sentence that says what
to do next. The three views (A, B and C) render this one `MethodReview`; none of them queries
anything the others do not get.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from invest_witus.adherence.journal import Action, Entry
from invest_witus.adherence.plan import Plan
from invest_witus.adherence.review import Finding, months_due, review
from invest_witus.methods.rulebook import LESSON_COMING, Method
from invest_witus_site.methods.models import JournalEntry, MethodPlan

ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class RuleLine:
    """One rule as a page prints it: its id, its text, and the lesson's URL or `None`, which the
    template renders as the words "lesson coming". The URL is the TOML file's, through
    `Method.lesson_for`; nothing here invents one."""

    id: str
    text: str
    lesson_url: str | None


@dataclass(frozen=True, slots=True)
class FindingLine:
    """One finding with the rule it broke and the month it concerns."""

    day: date
    month: str
    rule: RuleLine
    message: str


@dataclass(frozen=True, slots=True)
class RuleCheck:
    """One rule's result through the review date: pass with no findings, fail with the list."""

    rule: RuleLine
    findings: list[FindingLine]

    @property
    def status(self) -> str:
        return "fail" if self.findings else "pass"

    @property
    def months(self) -> str:
        """The months the findings fall in, each once, in order."""
        return ", ".join(sorted({finding.month for finding in self.findings}))

    @property
    def evidence(self) -> str:
        """The fact that decided it, in words: how many findings, and in which months."""
        if not self.findings:
            return "no findings"
        count = len(self.findings)
        return f"{count} finding{'' if count == 1 else 's'}: {self.months}"


@dataclass(frozen=True, slots=True)
class MonthRow:
    """One month of the plan: the window, what was bought, and whether the month is done,
    missed, or still open on the review date."""

    label: str
    window_closes: date
    status: str
    buys: int
    amount: Decimal
    shares: Decimal | None
    rule_ids: list[str]


@dataclass(frozen=True, slots=True)
class NextAction:
    """The one thing the method asks for next: a buy in a window, and whether that window is
    open now ("due"), or ahead ("upcoming") because this month's buy is done or missed."""

    label: str
    opens: date
    closes: date
    amount: Decimal
    symbols: list[str]
    status: str


@dataclass(frozen=True, slots=True)
class MethodReview:
    """Everything the three views render, from one plan and one journal."""

    plan: MethodPlan
    method: Method
    rules: list[RuleLine]
    through: date
    entries: list[JournalEntry]
    findings: list[FindingLine]
    checks: list[RuleCheck]
    months: list[MonthRow]
    next_action: NextAction

    @property
    def on_plan(self) -> bool:
        return not self.findings

    @property
    def months_done(self) -> int:
        return sum(1 for row in self.months if row.status == "done")

    @property
    def months_due(self) -> int:
        return sum(1 for row in self.months if row.status != "open")


def month_label(year: int, month: int) -> str:
    return f"{year}-{month:02d}"


def rule_lines(method: Method) -> list[RuleLine]:
    """Each rule with its lesson resolved: the rule's own, else the method's, else nothing."""
    lines: list[RuleLine] = []
    for rule in method.rules:
        lesson = method.lesson_for(rule.id)
        lines.append(RuleLine(rule.id, rule.text, None if lesson == LESSON_COMING else lesson))
    return lines


def finding_lines(findings: list[Finding], rules: dict[str, RuleLine]) -> list[FindingLine]:
    return [
        FindingLine(f.day, month_label(f.day.year, f.day.month), rules[f.rule_id], f.message)
        for f in findings
    ]


def rule_checks(rules: list[RuleLine], findings: list[FindingLine]) -> list[RuleCheck]:
    return [RuleCheck(rule, [f for f in findings if f.rule.id == rule.id]) for rule in rules]


def next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def month_rows(
    plan: Plan, entries: list[JournalEntry], findings: list[FindingLine], through: date
) -> list[MonthRow]:
    """Every month from the plan's start through `through`: the months whose window has closed
    (chapter 03's `months_due`) and, if the review date falls inside a window that is still open,
    that month too, marked open. The rows are the journal's own, not chapter 03's values, because
    the shares column exists only here; the shares total is `None` when any buy in the month
    left shares blank, so a partial total is never printed as a whole."""
    due = months_due(plan, through)
    months = list(due)
    if through >= plan.start:
        current = (through.year, through.month)
        if current not in months and current >= (plan.start.year, plan.start.month):
            months.append(current)
    buys = [e for e in entries if e.action == Action.BUY.value and plan.start <= e.date <= through]
    rows: list[MonthRow] = []
    for year, month in months:
        label = month_label(year, month)
        in_month = [b for b in buys if (b.date.year, b.date.month) == (year, month)]
        if in_month:
            status = "done"
        elif (year, month) in due:
            status = "missed"
        else:
            status = "open"
        shares: Decimal | None = None
        if in_month and all(b.shares is not None for b in in_month):
            shares = sum((b.shares for b in in_month if b.shares is not None), ZERO)
        rows.append(
            MonthRow(
                label=label,
                window_closes=date(year, month, plan.buy_window_days),
                status=status,
                buys=len(in_month),
                amount=sum((b.amount for b in in_month), ZERO),
                shares=shares,
                rule_ids=sorted({f.rule.id for f in findings if f.month == label}),
            )
        )
    return rows


def next_action(plan: Plan, entries: list[Entry], today: date) -> NextAction:
    """The next buy. Before the start: the start month's window. In a month with no buy yet and
    the window open: that window, due now. Otherwise, the month after: this month's buy is done,
    or its window has closed (the review says "No buy" for it; the next action is still the
    next window, because the method has no catching up)."""
    bought = {(e.day.year, e.day.month) for e in entries if e.action is Action.BUY}
    if today < plan.start:
        year, month, status = plan.start.year, plan.start.month, "upcoming"
    elif (today.year, today.month) in bought or today.day > plan.buy_window_days:
        (year, month), status = next_month(today.year, today.month), "upcoming"
    else:
        year, month, status = today.year, today.month, "due"
    return NextAction(
        label=month_label(year, month),
        opens=date(year, month, 1),
        closes=date(year, month, plan.buy_window_days),
        amount=plan.amount,
        symbols=sorted(plan.symbols),
        status=status,
    )


def build_review(plan: MethodPlan, entries: list[JournalEntry], through: date) -> MethodReview:
    """The whole context for the method page, from the row, the rows and the date."""
    method = plan.method()
    chapter_plan = plan.to_plan()
    chapter_entries = [entry.to_entry() for entry in entries]
    rules = rule_lines(method)
    by_id = {rule.id: rule for rule in rules}
    findings = finding_lines(review(method, chapter_plan, chapter_entries, through), by_id)
    months = month_rows(chapter_plan, entries, findings, through)
    return MethodReview(
        plan=plan,
        method=method,
        rules=rules,
        through=through,
        entries=entries,
        findings=findings,
        checks=rule_checks(rules, findings),
        months=months,
        next_action=next_action(chapter_plan, chapter_entries, through),
    )
```

- **`build_review` is the whole page's context.** The row becomes the value, the rows become the values,
  `review` runs as chapter 03 wrote it, and the rest of the function arranges what it returned. Nothing here
  decides whether a rule was broken; chapter 03 did.
- **`rule_lines` resolves the lesson once.** `Method.lesson_for` returns the rule's lesson, else the method's,
  else the words `LESSON_COMING`; the line keeps a URL or `None`, and the template prints "lesson coming" for
  `None`. No template, no view and no test carries a lesson URL: the only place one can come from is the
  TOML file, which is the authoritative-values rule applied to lessons.
- **`RuleCheck.evidence` is a sentence.** PRD 7.1 asks for the fact that decided each check; for this method
  the fact is the count of findings and the months they fall in, "1 finding: 2026-02", or "no findings".
  Status is the word `pass` or `fail`, never a color.
- **`month_rows` adds the open month.** Chapter 03's `months_due` lists the months whose window has closed.
  The page also shows the month the review date falls in when its window is still open, marked `open`, so the
  operator sees this month's row before it can be missed. A month is `done` when it has a buy, whatever the
  review found about that buy; the "Rules flagged" column carries the findings.
- **`next_action` is one rule.** Before the start, the start month's window; in a month with no buy and the
  window open, that window, due now; otherwise the next month's window, because this month is done or its
  window has closed and the method has no catching up. The date it reasons from is the review date, so
  `?through=` moves the next action with the findings.

### 10.6 The forms

Listing 10-13, Filename: `src/invest_witus_site/methods/forms.py`:

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

- **The method is a `ChoiceField` whose choices are a function.** The fields reference allows "a callable
  that returns such an iterable" and says "If the argument is a callable, it is evaluated each time the
  field's form is initialized, in addition to during rendering" (Django Software Foundation, n.d.-b), so the
  form reads the package's list when it is built. A method id typed by hand, `get-rich-quick`, is "Select a
  valid choice."
- **The amount is a `DecimalField`,** which "Normalizes to: A Python `decimal`" (Django Software Foundation,
  n.d.-b): the form hands the model a `Decimal`, never a float, which is what `save()`'s guard is for.
- **`clean_symbols` returns the stored string,** the way chapter 09's returned a parsed value: the list
  validated by the model's own validator, then joined. A refused token is a form error naming it; a plan with
  a typo in its universe would flag every buy.
- **`clean()` refuses a second active plan in words,** before the constraint has to. The account comes in
  through `__init__`, not a field, so no request can name another account than the one in the URL.
- **`JournalEntryForm` is a `ModelForm`.** "If you're building a database-driven app, chances are you'll have
  forms that map closely to Django models", and then "it would be redundant to define the field types in your
  form, because you've already defined the fields in your model" (Django Software Foundation, n.d.-c). The
  fields, labels, help text, choices and validators are the model's; "`Model` validation (`Model.full_clean()`)
  is triggered from within the form validation step, right after the form's `clean()` method is called"
  (Django Software Foundation, n.d.-c), which is how `AB CD` and an amount of zero become messages beside their
  boxes. The two widgets are the only things the form adds.

### 10.7 The views and the switch

Listing 10-14, Filename: `src/invest_witus_site/methods/views.py`:

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

- **`VIEWS` is the only place the three are named,** by letter, with the label the switch prints and the
  template the page includes. The research's names are the labels.
- **`chosen_view` reads the session.** "The session framework lets you store and retrieve arbitrary data on a
  per-site-visitor basis. It stores data on the server side and abstracts the sending and receiving of
  cookies" (Django Software Foundation, n.d.-d); with the middleware on since chapter 05, `request.session` is
  "a dictionary-like object" (Django Software Foundation, n.d.-d) and the view writes one key into it. The
  `isinstance` check before `in VIEWS` is for pyright: a session value is typed as anything. Sign-out ends it:
  `django.contrib.auth.logout()` "calls the `flush()` method of `request.session`" (Django Software Foundation,
  n.d.-d), so the next sign-in starts from the default again, which decision 5 wrote down.
- **`render_method_page` is the context builder the two actions call back into,** as chapter 09's
  `account_page` was. `force_view="c"` draws the start form again with its errors whichever view the session
  holds; a refused log entry comes back in the view the person was in.
- **`through_query` keeps the review date in the switch.** The three links carry `&through=` only when a date
  was given, so flipping views does not lose it.
- **`start_method` sets the view to A** after a plan is written, the everyday home, and `log_entry` leaves
  the view alone. Both are `login_required` then `require_POST`, in that order, for the reason chapter 09 gave.
- **The ownership query is chapter 08's,** `get_object_or_404(Account, pk=pk, owner=request.user)`, in all
  three views, so another owner's account is a 404 for the page and for both actions.

### 10.8 The templates: one page, three arrangements

Listing 10-15, Filename: `src/invest_witus_site/methods/templates/methods/method_page.html`:

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
  {# The same context, one of three arrangements (chapter 10). The view's letter is the research's. #}
  {% include view_template %}
  <p><a href="{% url 'account-detail' account.pk %}">Back to the account</a></p>
</section>
{% endblock %}
```

The page prints the environment as text under the heading, the band PRD 7.2 asks for, from the account's kind;
then the switch; then `{% include view_template %}`, where "The template name can either be a variable or a
hard-coded (quoted) string" and "An included template is rendered within the context of the template that
includes it" (Django Software Foundation, n.d.-e). One context, three templates.

Listing 10-16, Filename: `src/invest_witus_site/methods/templates/methods/_switch.html`:

```html
{# The view switch (chapter 10): three plain links. The current one carries aria-current, which #}
{# a screen reader announces; the choice is remembered in the session by the view that handles ?view=. #}
<nav class="views" aria-label="View">
  <ul class="plain views-list">
    {% for key, label in views %}
    <li><a href="?view={{ key }}{{ through_query }}"{% if key == view %} aria-current="page"{% endif %}>{{ label }}</a></li>
    {% endfor %}
  </ul>
  <p class="small muted">Three arrangements of the same plan, rules, review and journal. Reviewed through {{ through|date:"Y-m-d" }}.</p>
</nav>
```

Three links in a `<nav aria-label="View">`; the current one has `aria-current="page"`, which the stylesheet
draws and a screen reader reads. A link is the right control: it is keyboard operable by nature, it needs no
script, and the choice is a GET with no side effect beyond a session key.

Listing 10-17, Filename: `src/invest_witus_site/methods/templates/methods/_rules.html`:

```html
{# The rules of one method, each with its lesson (chapter 10). Included with `rules`, a list of RuleLine. #}
{# A rule whose TOML has no lesson URL reads "lesson coming": the words come from the file, never a guessed link. #}
<ol class="rules">
  {% for rule in rules %}
  <li id="rule-{{ rule.id }}">{{ rule.text }} <span class="small">{% if rule.lesson_url %}<a href="{{ rule.lesson_url }}">Why this rule</a>{% else %}<span class="muted">lesson coming</span>{% endif %}</span></li>
  {% endfor %}
</ol>
```

Listing 10-18, Filename: `src/invest_witus_site/methods/templates/methods/_findings.html`:

```html
{# The review's findings as a list (chapter 10). "No findings" is a sentence, never an empty box. #}
{% if review.findings %}
<ul class="findings">
  {% for finding in review.findings %}
  <li><strong>{{ finding.month }}</strong> {{ finding.message }} <span class="small">Rule: {{ finding.rule.text }} {% if finding.rule.lesson_url %}<a href="{{ finding.rule.lesson_url }}">Read the lesson</a>{% else %}<span class="muted">lesson coming</span>{% endif %}</span></li>
  {% endfor %}
</ul>
{% else %}
<p class="on-plan">You followed every rule through {{ review.through|date:"Y-m-d" }}. Nothing to look at.</p>
{% endif %}
```

Listing 10-19, Filename: `src/invest_witus_site/methods/templates/methods/_entries.html`:

```html
{% load holdings_extras %}
{# The journal as a table (chapter 10). Included with `entries`; the caption is the including view's. #}
{% if entries %}
<table class="holdings">
  <caption class="sr-only">{{ caption }}</caption>
  <thead>
    <tr>
      <th scope="col">Day</th>
      <th scope="col">Action</th>
      <th scope="col">Symbol</th>
      <th scope="col" class="num">Amount</th>
      <th scope="col" class="num">Shares</th>
      <th scope="col">Note</th>
    </tr>
  </thead>
  <tbody>
    {% for entry in entries %}
    <tr>
      <th scope="row">{{ entry.date|date:"Y-m-d" }}</th>
      <td>{{ entry.get_action_display }}</td>
      <td>{{ entry.symbol }}</td>
      <td class="num">{{ entry.amount|plain_number }}</td>
      <td class="num">{% if entry.shares is not None %}{{ entry.shares|plain_number }}{% else %}<span class="muted">not recorded</span>{% endif %}</td>
      <td>{{ entry.note }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% else %}
<p>Nothing logged yet.</p>
{% endif %}
```

Listing 10-20, Filename: `src/invest_witus_site/methods/templates/methods/_log_form.html`:

```html
{# The one-row add form (chapter 10): a buy or a sell, by hand, as the confirmation shows it. Chapter 12 builds the logbook. #}
<form method="post" action="{% url 'method-log' account.pk %}" class="method-form" novalidate>
  {% csrf_token %}
  {{ entry_form.non_field_errors }}
  {% for field in entry_form %}
  <div class="field">
    <label for="{{ field.id_for_label }}">{{ field.label }}</label>
    {{ field }}
    {{ field.errors }}
    {% if field.help_text %}<span class="helptext">{{ field.help_text }}</span>{% endif %}
  </div>
  {% endfor %}
  <button type="submit">Log it</button>
</form>
<p class="small muted">Logging records what you did; it places no order. The review reads the journal, not the broker.</p>
```

Listing 10-21, Filename: `src/invest_witus_site/methods/templates/methods/_start_form.html`:

```html
{# The start form (chapter 10): the method from the package's list, and the person's own numbers. #}
<form method="post" action="{% url 'method-start' account.pk %}" class="method-form" novalidate>
  {% csrf_token %}
  {{ start_form.non_field_errors }}
  {% for field in start_form %}
  <div class="field">
    <label for="{{ field.id_for_label }}">{{ field.label }}</label>
    {{ field }}
    {{ field.errors }}
    {% if field.help_text %}<span class="helptext">{{ field.help_text }}</span>{% endif %}
  </div>
  {% endfor %}
  <button type="submit">Start this method</button>
</form>
<p class="small muted">Starting a method writes your plan down. It places no order and recommends nothing: the symbols are yours, from the lesson, and the app only checks what you log against the rules you chose.</p>
```

Five partials the views share, so a rule, a finding, a journal row and the two forms are written once. The
rules list and the entries table are included "using keyword arguments" after `with` (Django Software
Foundation, n.d.-e), `rules=` for the list and `caption=` for the table. "No findings" is a sentence in
`_findings.html`, never an empty list; "lesson coming" is the words, never an empty link.

Listing 10-22, Filename: `src/invest_witus_site/methods/templates/methods/_view_a.html`:

```html
{% load holdings_extras %}
{# View A, "The Plan and the Logbook" (research 01, direction A): the everyday home. One next action, #}
{# the on-plan status with its fixes, the plan's rules each with its lesson, and the logbook. #}
{% if plan %}
<section class="card" aria-labelledby="next-heading">
  <h2 id="next-heading">Next</h2>
  <p>{% if review.next_action.status == "due" %}Due now: buy {{ review.next_action.amount|plain_number }} of {{ review.next_action.symbols|join:", " }} by {{ review.next_action.closes|date:"Y-m-d" }}, the end of this month's window.{% else %}Buy {{ review.next_action.amount|plain_number }} of {{ review.next_action.symbols|join:", " }} between {{ review.next_action.opens|date:"Y-m-d" }} and {{ review.next_action.closes|date:"Y-m-d" }}. Nothing to do before then.{% endif %}</p>
</section>

<section aria-labelledby="status-heading">
  <h2 id="status-heading">{% if review.on_plan %}You are on plan{% else %}Off plan: {{ review.findings|length }} thing{{ review.findings|length|pluralize }} to look at{% endif %}</h2>
  <p>{{ review.months_done }} of {{ review.months_due }} scheduled buy{{ review.months_due|pluralize }} made through {{ review.through|date:"Y-m-d" }}. A finding is a place the journal left the method; the lesson beside it says why the rule exists.</p>
  {% include "methods/_findings.html" %}
</section>

<section aria-labelledby="plan-heading">
  <h2 id="plan-heading">My plan</h2>
  <p>{{ review.method.summary }}</p>
  <p>{{ plan.amount|plain_number }} into {{ plan.symbols }} within the first {{ plan.buy_window_days }} day{{ plan.buy_window_days|pluralize }} of each month, since {{ plan.started_on|date:"Y-m-d" }}.</p>
  <h3>The rules</h3>
  {% include "methods/_rules.html" with rules=review.rules %}
</section>

<section aria-labelledby="logbook-heading">
  <h2 id="logbook-heading">Logbook</h2>
  {% include "methods/_entries.html" with caption="Every trade logged for this account, in date order" %}
  <h3>Write a log entry</h3>
  {% include "methods/_log_form.html" %}
</section>
{% else %}
<p>No method yet on this account. <a href="?view=c">Read the rules and start one in the Lesson Lab</a>.</p>
{% endif %}
```

A, the home: one next action in a card, the on-plan status with the findings as its fix list, the plan with its
rules and their lessons, the logbook with the form under it. The order is the research's: the one thing to do
next comes before everything else.

Listing 10-23, Filename: `src/invest_witus_site/methods/templates/methods/_view_b.html`:

```html
{% load holdings_extras %}
{# View B, "Method Console" (research 01, direction B): the operator's view. Status, the rule checks #}
{# with evidence and a lesson column, every month of the plan, the findings and the journal as tables. #}
{# Read-only by design: the one form is the same log form the other views carry. No order queue yet #}
{# (chapter 11) and no envelope chart: the method has no backtest range to draw. #}
{% if plan %}
<dl class="status" aria-label="Status">
  <dt>Environment</dt><dd>{{ account.get_kind_display }} ({{ account.broker }})</dd>
  <dt>Method</dt><dd>{{ review.method.name }}, version {{ review.method.version }} ({{ review.method.id }})</dd>
  <dt>Plan</dt><dd>{{ plan.amount|plain_number }} into {{ plan.symbols }}, days 1 to {{ plan.buy_window_days }}, since {{ plan.started_on|date:"Y-m-d" }}</dd>
  <dt>Reviewed through</dt><dd>{{ review.through|date:"Y-m-d" }}</dd>
  <dt>Months</dt><dd>{{ review.months_done }} done of {{ review.months_due }} due</dd>
  <dt>Findings</dt><dd>{{ review.findings|length }}</dd>
  <dt>Journal</dt><dd>{{ entries|length }} entr{{ entries|length|pluralize:"y,ies" }}</dd>
</dl>

<h2>Rule checks</h2>
<table class="holdings">
  <caption class="sr-only">Each rule of the method, its result through the review date, the evidence and its lesson</caption>
  <thead>
    <tr>
      <th scope="col">Rule</th>
      <th scope="col">Status</th>
      <th scope="col">Evidence</th>
      <th scope="col">Lesson</th>
    </tr>
  </thead>
  <tbody>
    {% for check in review.checks %}
    <tr>
      <th scope="row">{{ check.rule.text }}</th>
      <td>{{ check.status }}</td>
      <td>{{ check.evidence }}</td>
      <td>{% if check.rule.lesson_url %}<a href="{{ check.rule.lesson_url }}">{{ check.rule.id }}</a>{% else %}<span class="muted">lesson coming</span>{% endif %}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>

<h2>Months</h2>
<table class="holdings">
  <caption class="sr-only">Every month of the plan through the review date: its window, what was bought, and whether it is done, missed or open</caption>
  <thead>
    <tr>
      <th scope="col">Month</th>
      <th scope="col">Window closes</th>
      <th scope="col">Status</th>
      <th scope="col" class="num">Buys</th>
      <th scope="col" class="num">Amount</th>
      <th scope="col" class="num">Shares</th>
      <th scope="col">Rules flagged</th>
    </tr>
  </thead>
  <tbody>
    {% for row in review.months %}
    <tr>
      <th scope="row">{{ row.label }}</th>
      <td>{{ row.window_closes|date:"Y-m-d" }}</td>
      <td>{{ row.status }}</td>
      <td class="num">{{ row.buys }}</td>
      <td class="num">{{ row.amount|plain_number }}</td>
      <td class="num">{% if row.shares is not None %}{{ row.shares|plain_number }}{% elif row.buys %}<span class="muted">not recorded</span>{% endif %}</td>
      <td>{% if row.rule_ids %}{{ row.rule_ids|join:", " }}{% else %}<span class="muted">none</span>{% endif %}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>

<h2>Findings</h2>
{% if review.findings %}
<table class="holdings">
  <caption class="sr-only">Every finding of the review, by day</caption>
  <thead>
    <tr>
      <th scope="col">Day</th>
      <th scope="col">Rule</th>
      <th scope="col">What happened</th>
      <th scope="col">Lesson</th>
    </tr>
  </thead>
  <tbody>
    {% for finding in review.findings %}
    <tr>
      <th scope="row">{{ finding.day|date:"Y-m-d" }}</th>
      <td>{{ finding.rule.text }}</td>
      <td>{{ finding.message }}</td>
      <td>{% if finding.rule.lesson_url %}<a href="{{ finding.rule.lesson_url }}">{{ finding.rule.id }}</a>{% else %}<span class="muted">lesson coming</span>{% endif %}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% else %}
<p class="on-plan">No findings through {{ review.through|date:"Y-m-d" }}: every rule passed.</p>
{% endif %}

<h2>Journal</h2>
{% include "methods/_entries.html" with caption="Every trade logged for this account, in date order" %}
<h3>Log an entry</h3>
{% include "methods/_log_form.html" %}
{% else %}
<p>No method runs on this account, so there is nothing to supervise. <a href="?view=c">Start one in the Lesson Lab</a>.</p>
{% endif %}
```

B, the console: a status list, then four tables, rule checks with status, evidence and a lesson column, every
month of the plan with its window, its buys, the amount and the shares, the findings by day, and the journal.
Each table has a caption for screen readers, header `scope` on every heading cell, and right-aligned tabular
numbers through chapter 08's `.num` class.

Listing 10-24, Filename: `src/invest_witus_site/methods/templates/methods/_view_c.html`:

```html
{% load holdings_extras %}
{# View C, "The Lesson Lab" (research 01, direction C): the lesson is the screen. The rules are read #}
{# before the plan is written; once it runs, a broken rule points back at its lesson, and the journal #}
{# is the lab notebook. No points, no streaks: a rule is on when the plan names the method. #}
{% if plan %}
<p class="lead">You are running <strong>{{ review.method.name }}</strong>. {{ review.method.summary }}</p>
<p>Your plan: {{ plan.amount|plain_number }} into {{ plan.symbols }} within the first {{ plan.buy_window_days }} day{{ plan.buy_window_days|pluralize }} of each month, since {{ plan.started_on|date:"Y-m-d" }}.</p>
<h2>The rules, and what to re-read</h2>
<p>Each rule comes from one lesson. A rule the review flagged names how often, and its lesson is the place to go back to before the next window.</p>
<ol class="rules">
  {% for check in review.checks %}
  <li id="rule-{{ check.rule.id }}">{{ check.rule.text }} <span class="small">{% if check.rule.lesson_url %}<a href="{{ check.rule.lesson_url }}">Open the lesson</a>{% else %}<span class="muted">lesson coming</span>{% endif %}{% if check.findings %} <strong>Flagged {{ check.findings|length }} time{{ check.findings|length|pluralize }}, in {{ check.months }}.</strong>{% else %} Followed so far.{% endif %}</span></li>
  {% endfor %}
</ol>
<h2>This month's lab</h2>
<p>{% if review.next_action.status == "due" %}The window is open: buy {{ review.next_action.amount|plain_number }} of {{ review.next_action.symbols|join:", " }} by {{ review.next_action.closes|date:"Y-m-d" }}, then log it below.{% else %}The next window is {{ review.next_action.opens|date:"Y-m-d" }} to {{ review.next_action.closes|date:"Y-m-d" }}: {{ review.next_action.amount|plain_number }} of {{ review.next_action.symbols|join:", " }}. Until then, read.{% endif %} {{ review.months_done }} of {{ review.months_due }} scheduled buy{{ review.months_due|pluralize }} made through {{ review.through|date:"Y-m-d" }}.</p>
{% include "methods/_findings.html" %}
<h2>Lab notebook</h2>
{% include "methods/_entries.html" with caption="Every trade logged for this account, in date order" %}
<h3>Add to the notebook</h3>
{% include "methods/_log_form.html" %}
{# A start submitted while a method runs lands here with its reason; the form itself is not shown. #}
{{ start_form.non_field_errors }}
<p class="small muted">This account runs one method at a time. Ending it is an admin step for now; a change of plan with its reason is chapter 12's.</p>
{% else %}
<p class="lead">A method is a short list of rules, each taught by one lesson. Read them before you commit: once the plan is written, the app holds you to every one and sends you back to the lesson when the journal leaves it.</p>
{% for method, rules in catalog %}
<section aria-labelledby="catalog-{{ method.id }}">
  <h2 id="catalog-{{ method.id }}">{{ method.name }} <span class="muted small">(version {{ method.version }})</span></h2>
  <p>{{ method.summary }} {% if method.lesson %}<a href="{{ method.lesson }}">The lesson</a>{% else %}<span class="muted">lesson coming</span>{% endif %}</p>
  {% include "methods/_rules.html" with rules=rules %}
</section>
{% endfor %}
<section aria-labelledby="start-heading">
  <h2 id="start-heading">Start a method on this account</h2>
  {% include "methods/_start_form.html" %}
</section>
{% endif %}
```

C, the lab: with no method running, each method the package ships, its summary, its rules with their lessons,
and the start form under them, so the rules are read before the plan is written; with one running, the rules
again, each saying "Followed so far" or how often it was flagged and in which months, this month's lab (the next
window), the findings, and the journal as the lab notebook. A start submitted while a method runs lands in this
branch with its reason printed, since the form itself is not shown.

### 10.9 The account page's line

Listing 10-25, Filename: `src/invest_witus_site/holdings/views.py`:

```python
"""The owner's accounts, outside the admin: a list, and one account valued at the latest closes
with its watch list underneath (chapter 09) and a line naming the method it runs (chapter 10).

Both views sit behind `login_required`, which sends a visitor to `LOGIN_URL` (the WitUS sign-in,
chapter 07), and both read only the accounts the signed-in user owns. Someone else's account is a
404, not a 403: the page does not say whether the id exists.
"""

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.models import MethodPlan
from invest_witus_site.prices.portfolio import value_snapshot, watch_list
from invest_witus_site.watchlist.forms import WatchForm


@login_required
def account_list(request: HttpRequest) -> HttpResponse:
    accounts = Account.objects.filter(owner=request.user)
    return render(request, "holdings/account_list.html", {"accounts": accounts})


@login_required
def account_detail(request: HttpRequest, pk: int) -> HttpResponse:
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    return account_page(request, account)


def account_page(
    request: HttpRequest, account: Account, watch_form: WatchForm | None = None
) -> HttpResponse:
    """The account page: the latest statement valued, then the watch list with its add form.
    The ownership check is the caller's. Chapter 09's add view renders the page again through
    this function, with the bound form, when nothing in a submission could be added."""
    today = timezone.localdate()
    snapshot = account.latest_snapshot()
    valuation = value_snapshot(snapshot, today) if snapshot is not None else None
    context = {
        "account": account,
        "snapshot": snapshot,
        "valuation": valuation,
        "watch": watch_list(account, today),
        "watch_form": watch_form or WatchForm(),
        # Chapter 10: the method this account runs, or None; the method page holds the rest.
        "method_plan": MethodPlan.active_for(account),
    }
    return render(request, "holdings/account_detail.html", context)
```

Listing 10-26, Filename: `src/invest_witus_site/holdings/templates/holdings/account_detail.html`:

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
  {# The watch list (chapter 09): the symbols followed here, the latest close beside each, the add form. #}
  {% include "watchlist/_section.html" %}
  <p><a href="{% url 'account-list' %}">All accounts</a></p>
</section>
{% endblock %}
```

One key in the context, `method_plan`, and one section on the page between the statement and the watch list:
the method's name as a link to the method page with the plan's numbers, or the invitation to read the rules and
start one, which opens view C. The header is untouched: the way to the method page is through the account, and
no public page links it.

Thirteen rules go at the end of `site.css`: `.views-list` and its links draw the switch as a row of boxes with
the current one filled; `.band` is the dashed environment line; `.card` is the next-action box; `.status` is a
two-column definition list; `.rules li` and `.findings li` space the lists; `.method-form`, its inputs and
selects, and `.helptext` style the two forms the way chapter 04's waitlist form was styled.

### 10.10 Green, and your first method on your laptop

Listing 10-27, Terminal:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

```text
309 passed in 9.77s
All checks passed!
146 files already formatted
0 errors, 0 warnings, 0 informations
```

Thirty new tests. Now migrate the laptop database:

Listing 10-28, Terminal:

```sh
uv run --env-file .env python manage.py migrate
```

```text
Operations to perform:
  Apply all migrations: accounts, admin, auth, contenttypes, holdings, methods, pages, prices, sessions, watchlist
Running migrations:
  Applying methods.0001_initial... OK
```

Then use it as the owner. Under `runserver`, sign in at `/admin/` with your chapter 05 superuser, open
`/accounts/`, then an account. Under the statement, or under "No statement yet.", the Method section reads "No
method yet on this account" with a link; it opens the method page on view C, with the one method the package
ships, its five rules each reading "lesson coming", and the start form. Pick the method, type `100` as the
amount, `7` as the window, `INDEX` as the symbols and `2026-01-01` as the start, and submit. The page comes back
on view A with a green notice, "Started Index investing with a fixed monthly contribution on Practice.", the
next window, and the on-plan status, which on a plan from January reviewed through today is off plan: every
month since January with no buy is a finding. Log a buy on January 2 and one on February 12, and read the
findings change. Press the three links to flip the views.

Without a browser, the same through the test client, the way chapter 09 looked at the watch list. Start the
method:

Listing 10-29, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -c "from django.contrib.auth.models import User; from django.test import Client; from invest_witus_site.holdings.models import Account; from invest_witus_site.methods.models import MethodPlan; u = User.objects.get(is_superuser=True); a = Account.objects.filter(owner=u).first(); c = Client(); c.force_login(u); r = c.post(f'/accounts/{a.pk}/method/start/', {'method_id': 'index-dca', 'amount': '100', 'buy_window_days': '7', 'symbols': 'INDEX', 'started_on': '2026-01-01'}, follow=True); print(r.redirect_chain); [print(line.strip()) for line in r.content.decode().splitlines() if 'class=\"message ' in line]; print(MethodPlan.active_for(a).to_plan())"
```

```text
[('/accounts/1/method/', 302)]
<li class="message success">Started Index investing with a fixed monthly contribution on Practice.</li>
Plan(method='index-dca', start=datetime.date(2026, 1, 1), amount=Decimal('100.00'), symbols=frozenset({'INDEX'}), buy_window_days=7)
```

(The account id is whichever account is first in your database. Run it twice and the second answer is the page
again, status 200, with "This account already runs a method." in it and still one plan.) The last line is the
row as chapter 03's value, which is what the review will read. Log two entries, the second outside the window:

Listing 10-30, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -c "from django.contrib.auth.models import User; from django.test import Client; from invest_witus_site.holdings.models import Account; from invest_witus_site.methods.models import JournalEntry; u = User.objects.get(is_superuser=True); a = Account.objects.filter(owner=u).first(); c = Client(); c.force_login(u); [print([line.strip() for line in c.post(f'/accounts/{a.pk}/method/log/', row, follow=True).content.decode().splitlines() if 'class=\"message ' in line][0]) for row in ({'date': '2026-01-02', 'action': 'buy', 'symbol': 'INDEX', 'amount': '100', 'shares': '0.5', 'note': 'first buy'}, {'date': '2026-02-12', 'action': 'buy', 'symbol': 'index', 'amount': '100', 'shares': '', 'note': ''})]; print([e.to_entry() for e in JournalEntry.entries_for(a)])"
```

```text
<li class="message success">Logged: 2026-01-02 buy 100.00 of INDEX.</li>
<li class="message success">Logged: 2026-02-12 buy 100.00 of INDEX.</li>
[Entry(day=datetime.date(2026, 1, 2), action=<Action.BUY: 'buy'>, symbol='INDEX', amount=Decimal('100.00')), Entry(day=datetime.date(2026, 2, 12), action=<Action.BUY: 'buy'>, symbol='INDEX', amount=Decimal('100.00'))]
```

The lower-case `index` was stored as `INDEX`, the empty shares as none, and the two rows read back as chapter
03's values. Now the review, through February 28, as view B's tables, read with the test file's own reader:

Listing 10-31, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -c "from django.contrib.auth.models import User; from django.test import Client; from invest_witus_site.holdings.models import Account; from tests.test_ch10 import tables_in, text; u = User.objects.get(is_superuser=True); a = Account.objects.filter(owner=u).first(); c = Client(); c.force_login(u); html = text(c.get(f'/accounts/{a.pk}/method/?view=b&through=2026-02-28')); [print(row) for table in tables_in(html)[:3] for row in table]"
```

```text
('Rule', 'Status', 'Evidence', 'Lesson')
('Buy once in every month of the plan.', 'pass', 'no findings', 'lesson coming')
("Buy within the plan's buy window at the start of the month, not when the news makes you feel ready.", 'fail', '1 finding: 2026-02', 'lesson coming')
("Buy the plan's amount every time: no more after a good month, no less after a bad one.", 'pass', 'no findings', 'lesson coming')
('Buy only the fund or funds named in your plan.', 'pass', 'no findings', 'lesson coming')
('This method has no sell rule. A sale is a change of plan and needs a written reason.', 'pass', 'no findings', 'lesson coming')
('Month', 'Window closes', 'Status', 'Buys', 'Amount', 'Shares', 'Rules flagged')
('2026-01', '2026-01-07', 'done', '1', '100.00', '0.50', 'none')
('2026-02', '2026-02-07', 'done', '1', '100.00', 'not recorded', 'buy-in-window')
('Day', 'Rule', 'What happened', 'Lesson')
('2026-02-12', "Buy within the plan's buy window at the start of the month, not when the news makes you feel ready.", 'Bought on day 12; the window is days 1 to 7.', 'lesson coming')
```

Three tables: every rule with its status and evidence, every month with its buys, amount and shares (February's
"not recorded", because that entry had none), and the one finding with the rule's text and the words "lesson
coming", which is what the TOML file says until a lesson is published. Change `through=2026-02-28` to
`2026-01-31` and the third table is replaced by the sentence "No findings through 2026-01-31: every rule
passed." Last, flip the views:

Listing 10-32, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -c "
import re
from django.contrib.auth.models import User
from django.test import Client
from invest_witus_site.holdings.models import Account
from tests.test_ch10 import text
u = User.objects.get(is_superuser=True); a = Account.objects.filter(owner=u).first(); c = Client(); c.force_login(u)
for view in 'abc':
    html = text(c.get(f'/accounts/{a.pk}/method/?view={view}&through=2026-02-28'))
    print(view, c.session['method_view'], re.findall(r'<h2[^>]*>([^<]+)</h2>', html))
html = text(c.get(f'/accounts/{a.pk}/method/'))
print('plain', re.search(r'aria-current=\"page\">([^<]+)<', html).group(1))
"
```

```text
a a ['Next', 'Off plan: 1 thing to look at', 'My plan', 'Logbook', 'Rise Wellness of Indiana']
b b ['Rule checks', 'Months', 'Findings', 'Journal', 'Rise Wellness of Indiana']
c c ['The rules, and what to re-read', "This month's lab", 'Lab notebook', 'Rise Wellness of Indiana']
plain C: The Lesson Lab
```

Each request names a view, the session keeps it, and the request with no `?view=` lands on the last one chosen.
The last heading on each line is the footer's, which every page carries. The same plan, the same finding and the
same two entries are behind all three lists of headings; what differs is what comes first.

### 10.11 What the owner does outside the editor

The reference app's steps are task 13 in the owner's queue. A learner with a Vercel project of their own does
the same:

1. **Merge the chapter** and let Vercel deploy `main`.
2. **Migrate,** from your machine against the direct connection, with chapter 06's recipe as task 04 corrected
   it: one line, `STORAGE_DATABASE_URL_UNPOOLED=<the direct string from the Neon console>`, in a throwaway
   `.env.migrate` (git ignores `.env.*`), then `DJANGO_SECRET_KEY=only-for-this-shell-not-the-real-one VERCEL=
   uv run --env-file .env.migrate python manage.py migrate --database direct`, then delete the file. Expect
   `Applying methods.0001_initial... OK`. Between the merge and the migration every account page answers 500,
   because the page asks the new table for the account's plan, so do the two in one sitting.
3. **Start the method,** signed in with WitUS, from an account's page: the Method section's link opens view C;
   read the rules, type the amount, the window, the symbols and the start, and submit.
4. **Log the first purchase** from the form under the logbook, as the confirmation shows it.
5. **Read the review** in view A, then flip to B and C. Every rule says "lesson coming" until the lesson exists.

## Checkpoint

- `uv run pytest` prints `309 passed`; ruff and pyright pass.
- Listing 10-29 answers with the notice and the plan as chapter 03's value; a second run is a 200 with "This
  account already runs a method."
- Listing 10-30 logs two entries and reads them back as chapter 03's values.
- Listing 10-31 prints the three tables with the one finding, its rule's text and "lesson coming"; with
  `through=2026-01-31` it prints the no-findings sentence instead of the third table.
- Listing 10-32 prints a different list of headings per view and the session's choice after each request.
- Signed out, every public page has no `<table`, no link to `/accounts/` or `/method/` and no rule; a GET of
  `/accounts/<id>/method/` redirects to the sign-in.
- Signed in as someone who does not own the account, the page and both actions are 404.
- Commit and push: `git add -A && git commit -m "Chapter 10: The method engine and the three views"`.

## Exercises

1. The PRD wants the view saved per user and restored at the next sign-in. Add a `preferred_view` to chapter
   07's `WitusIdentity` (one field, one migration), write it when `?view=` is handled, and read it in
   `chosen_view` when the session has no choice. Write the test first: sign out, sign in, the view is still B.
2. End a plan from the page. Add a POST view `method-end` that sets `active` off and writes a journal note with
   the reason the form requires, and show "Ended on <date>: <reason>" above the start form in view C. Decide,
   and write down, what the review shows for an ended plan.
3. The months table prints "not recorded" when any buy in the month lacks shares. Change `month_rows` so a
   month with two buys, one with shares and one without, prints the known total with an asterisk and a footnote,
   and change the test that pins the current behavior.
4. A second rules file. Copy `index_dca.toml` to `index_dca_quarterly.toml` with a new id and name and a
   `buy_every_months = 3` setting, and see what breaks: `available_methods` lists it at once, the start form
   offers it, and chapter 03's test that the rule ids equal `CHECKED_RULES` tells you the review has no check
   for a quarter. That test is the point of this exercise; chapter 14 adds the second method properly.

## If you get stuck

- Browse: https://github.com/dapperAuteur/invest-witus/tree/v10
- Diff for this chapter: https://github.com/dapperAuteur/invest-witus/compare/v09...v10
- Zip: https://github.com/dapperAuteur/invest-witus/archive/v10.zip
- Take the reference's files. Chapter 10 changed `src/invest_witus/methods/rulebook.py`,
  `src/invest_witus_site/settings.py`, `src/invest_witus_site/urls.py`, `holdings/views.py`, the template
  `holdings/account_detail.html`, `pages/static/pages/site.css` and `docs/site/privacy.md`, and added
  `src/invest_witus_site/methods/` (the whole app) and `tests/test_ch10.py`. No package changed, no
  environment variable was added, nothing moved:
  `git fetch reference --tags && git checkout v10 -- src tests docs/site/privacy.md`.
- `ImportError: cannot import name 'available_methods'` after 10.2: the function is in a different module, or
  the name differs. It lives in `rulebook.py` beside `load_method`.
- `No module named 'invest_witus_site.methods'` after 10.3: the folder has no `__init__.py`, or it was made
  under `holdings/` or inside the library's `invest_witus/methods/` instead of beside the other apps.
- A circular import at startup naming `holdings.views` and `methods.views`: `methods/views.py` imports from
  `holdings/views.py`. It imports `holdings.models` only.
- `test_a_plan_round_trips_to_chapter_03s_plan` fails on `symbols`: `save()` does not call `join_symbols`, or
  the join uses a comma. The stored form is single spaces.
- `test_one_active_plan_per_account` raises no `IntegrityError`: the `UniqueConstraint` lacks its
  `condition`, or names other fields. It raises on the second row's `save()` too, after the first plan was
  ended: the condition is missing, so the constraint covers ended plans as well.
- `test_an_entry_refuses_a_float_a_bad_symbol_a_zero_amount_and_an_unknown_action` passes `hold`: the
  `choices` argument is missing from the `action` field, or was typed by hand with more values than the enum.
- `test_the_review_on_the_web_is_chapter_03s_review` has `shares` of `None` for January: `month_rows` reads
  chapter 03's `Entry` values, which have no shares. It reads the journal rows.
- `test_month_rows_mark_each_month_done_missed_or_open` lacks the `open` row: the current month is only
  appended when it is not already in `months_due` and not before the start.
- `test_the_next_action_is_the_next_window` returns `due` on January 20: the window test compares the wrong
  side. A day past `buy_window_days` moves to the next month.
- `test_the_owner_starts_a_method_from_the_form` gets 200 instead of a redirect: the form is invalid. Print
  `form.errors` in the view for a moment; a missing `started_on` initial or a `choices` list that is empty
  because `available_methods` found no file are the usual causes.
- `test_the_form_refuses_a_second_active_plan_and_bad_numbers` has no "already runs" message: the error is
  raised in `clean_method_id` or the view instead of `clean()`, or view C's running branch does not print
  `start_form.non_field_errors`.
- `test_the_page_shows_a_planted_break_with_its_rule_text_and_lesson_coming` cannot find the rule's text: the
  test compares escaped HTML. Every page assertion goes through `text()`.
- `test_view_b_tables_every_month_with_amounts_and_shares` cannot unpack four tables: the findings table is
  missing when there are findings, or the journal table rendered a `<table>` with no rows; `_entries.html`
  guards with `{% if entries %}`.
- `test_the_three_views_render_for_the_owner_and_404_for_another_owner` finds a heading from another view:
  two views share an `<h2>`. The three headings in `VIEW_HEADINGS` belong to one view each.
- `test_the_view_choice_persists_in_the_session` keeps `zzz`: `chosen_view` writes the session before checking
  the value is in `VIEWS`.
- `test_every_view_shows_the_same_plan_rules_findings_and_journal_and_no_price` fails on `2026-01-01` in C:
  the running branch of view C does not print the plan's numbers. Every view prints the plan, the rules, the
  findings and the journal.
- The same test finds `123.45`: a view prints a close. Nothing on the method page reads the prices table.
- `test_the_method_routes_need_a_sign_in_and_the_actions_a_post` sees 405 for the anonymous POST: the
  decorators are in the other order; `login_required` goes on top.
- `test_public_pages_show_no_table_no_method_link_and_no_rule` finds `/method/` on a public page: the header
  or the footer links the method page. The way in is the account page only.
- `test_the_admin_lists_plans_and_entries_and_refuses_an_unknown_method` gets a 500 instead of the message:
  `validators=[validate_method_id]` is missing from the field, so the admin's form reached `save()`.
- `pyright` reports the test client's response is not an `HttpResponse`: the `text()` helper's parameter is
  typed as `HttpResponse`. The `Page` protocol is the type.
- `ruff check` reports an import-order error in the migration: Listing 10-9's third command.
- On Vercel after the merge, the account page answers 500 and the log says `relation "methods_methodplan"
  does not exist`: step 2 of 10.11 has not run.

## What we learned

- A row can be a value in waiting: two models whose converters hand chapter 03's functions the values they
  were written for, so the review runs on the web without a rewrite, and a test can prove the round trip.
- Rules that live in a file reach every page through one loader; a row that copied them would be a second
  source of truth that goes stale the day the file changes.
- A unique constraint with a condition says "one of these at a time" without forbidding history; the form says
  the same in words so the person never meets the database's error.
- A `ModelForm` takes the fields, the choices and the validators from the model, and runs the model's
  validation inside its own, so the boundary rules are written once and the form inherits them.
- One context, three templates: a view can build everything once and let `{% include %}` with a variable name
  decide the arrangement, and a test can assert that nothing differs between the arrangements but the order.
- The session is a per-visitor dictionary on the server, written in one view and read in the next; a sign-out
  flushes it, so a preference that must outlive the sign-in belongs on the person, not the session.
- "Lesson coming" is a value the file produces, not a default the template invents; the page can print a
  lesson it was given and nothing it was not.

## Next

Chapter 11 brings the paper broker: Alpaca's paper account behind a `Protocol`, orders staged from the plan's
next action and placed on confirm, fills copied into the journal as automatic entries, and the practice budget.
View B gets its order queue then. The method page and its three views do not change for it; the next action
gains a button.

## References

Django Software Foundation. (n.d.-a). *Constraints reference*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/ref/models/constraints/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-b). *Form fields*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/ref/forms/fields/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-c). *Creating forms from models*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/forms/modelforms/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-d). *How to use sessions*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/http/sessions/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-e). *Built-in template tags and filters*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/ref/templates/builtins/ (retrieved October 28, 2026)
