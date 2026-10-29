# Chapter 12: The journal and closing the month

**Starts from:** tag `v11`. **Ends at:** tag `v12`.
**Written against:** Python 3.14.10, uv 0.13.6, Django 5.2.18, and the documentation pages named in the
references as read on October 29, 2026.
**Goal:** the journal becomes a logbook, and every month gets a close. An entry can be a hold or a skip as well
as a trade, each with a reason it cannot be saved without, and any entry may carry your state of mind and a few
tags of your own. A skip with its reason explains a month with no buy: the review still lists the miss, says
why beside it, and marks the rule "explained" instead of "fail". Each month whose buy window has closed gets a
review you close with three short answers; once closed, that month's entries are read-only until you reopen it
with a reason, and every close and reopen is kept. A plan changes through a form that keeps the old numbers as
a dated version, and each month is judged by the version in force that month. On a paper account, a month whose
order ended with nothing filled offers "Place again". The logbook page filters by month, kind and tag, and
exports CSV.
**Time:** 5 to 6 hours for the code and tests. Closing your first three months on the laptop takes 15 minutes.

The listings in this chapter are not typed in by hand. `scripts/render_chapter.py` pastes the real files from
tag `v12` into the chapter text, so what you read and what the tests run are the same bytes.

## What you will learn

- **Additive migrations, for real:** `db_default` beside `default`, so the code from the last release can still
  write rows while the migration that added the columns runs.
- **Rules that span fields:** a model's `clean()` that knows a hold needs a reason and a trade needs an amount,
  run by every `ModelForm` and by the admin before anything is saved.
- **History as rows:** a plan that changes becomes a chain of versions, each pointing at the one it replaced,
  and a function that turns the chain into the span of days each version judges.
- **An audit trail:** a table that is only ever added to, and an admin that cannot edit or delete it.
- **Read-only by state:** a closed month refuses changes in the model, in the forms and in the admin, from one
  check.
- **A CSV export that is safe to open:** Python's `csv` module, a download response, and the formula guard a
  spreadsheet needs.

## Before the code: what the PRD asks, and nine decisions

**What the PRD asks.** Section 7.6, the logbook: manual entries including a skip with a reason, tags for mental
state and mistakes, the rule-following rate as the headline number, months marked by whether the rules were
followed and not by profit or loss, and export to CSV. Section 7.7: "Hold requires a reason", the monthly review
opens when the review day arrives and closing it is the owner's act, and "A review cannot be closed with an
unexplained skip." Section 7.1: "A deviation (a skip, an off-schedule order, drift past the method's band)
cannot be recorded without a reason", and "Changing a running plan's method or parameters creates a new plan
version with a dated note; old reviews keep pointing at the version they judged." Chapter 11's decisions log,
row 102, lists what it left for this chapter: Hold and Skip with a reason, closing the monthly review, ending or
changing a plan with a reason, and placing a month again after its order ended unfilled.

**Decision 1: a kind column, beside the action.** The obvious design adds `hold` and `skip` to the action's
choices. Chapter 10's tests use `hold` as the example of an action the review does not know, and those tests
must keep passing, because a tag never moves. So `JournalEntry` gains `kind`: `trade` (the default, every row
until now), `hold` or `skip`. A trade has an action, a symbol and an amount, as before; a hold or a skip has a
reason and no money, and a symbol is optional. The review only ever sees trades. Decisions log, row 103.

**Decision 2: a short fixed list of states, and free tags.** The state of mind is one of six words: calm,
focused, confident, unsure, stressed, rushed, or empty for not recorded. Each describes you at the moment of the
entry, never the market. Tags are your own: up to five, lower case, letters, digits and hyphens, at most 24
characters each, stored as one space-separated column. Renaming and merging tags, which the PRD lists, waits for
a tag table. Row 104.

**Decision 3: an explained miss is arrangement, not a new rule.** Chapter 03's review is unchanged, and so is
`CHECKED_RULES`: a month with no buy is still a finding of "Buy once in every month of the plan." The engine
attaches the reason of a skip logged in that month to that finding, the month reads "skipped" instead of
"missed", and the rule's status reads "explained" when every finding it has is explained. A skip explains only
a month with no buy; it does not excuse a sale, a late buy or a second buy. The next action treats a skipped
month as decided, and the paper box refuses to place an order for it. Row 105.

**Decision 4: a review row per month, opened when the window closes.** `MonthlyReview` holds the plan version,
the month, `opened_on` (the day the month's window closed), the three answers and `closed_at`. Nothing runs at
the end of a window, so the row is written the first time a page that shows the plan is drawn after that day;
`opened_on` is still the window's last day, whatever day you looked. Closing asks what you did, what the rules
said (started for you from the month's findings) and what you'll do next month, and it is refused while the
month has a missed buy with no skip. Closing writes no journal entry: the review row is the record, and an entry
would sit in the month it just made read-only. Row 106.

**Decision 5: a closed month is read-only, from one check.** `JournalEntry.clean()` refuses a line dated in a
closed month, and a change to a line that was dated in one. The method page's log form, the logbook's edit form
and the admin all run `clean()`, so the rule is written once; the admin also hides Delete for such a line.
Reopening needs a reason, and `ReviewEvent` keeps every close (with the three answers) and every reopen (with the
reason), who did it and when; its admin is read-only. The nightly sync of paper orders is not an edit: it copies
the broker's facts, and its writes go through `save()` without `clean()`. Row 107.

**Decision 6: a plan version is a row.** A change writes a new `MethodPlan` that points at the old one through
`previous`, with one more in `version` and the reason in `change_reason`; the old row gets `ended_on`, the day
before the new one starts, and stays. A change starts on the first day of next month, or of this month while
this month's window is open and nothing is logged in it. The method is not changed here; a different method is
a new plan. Ending a plan sets `ended_on` to today and `end_reason`. `version_spans` turns the chain into the
days each version judges, the engine runs chapter 03's review once per span with that span's numbers, and the
practice budget counts from the first version's start. A paper Confirm uses the version in force on the day.
Row 108.

**Decision 7: Place again, with a new id.** Chapter 11 kept a month whose order ended unfilled from being placed
again. Now the next attempt is staged with the same id plus `-r2` (then `-r3`), and the button reads "Place
again". The attempt number comes from the rows, so two clicks compute the same id and the unique column keeps
it to one order. Every other refusal still applies, the window first: the method has no catching up. Row 109.

**Decision 8: the logbook is its own page, and the export is the page.** `/accounts/<id>/logbook/` lists every
entry with every column, filtered by `?month=`, `?kind=` and `?tag=`; the export takes the same parameters. A line
a paper order wrote is not edited by hand (the sync keeps it in step with Alpaca), and the others are edited on
the logbook's edit page. To add a line you use the method page's log form, as before. Row 110.

**Decision 9: the CSV.** Eleven columns, in this order: `date` (YYYY-MM-DD), `kind` (buy, sell, hold or skip),
`symbol`, `amount` and `shares` (plain decimals, empty when there is none), `state`, `tags` (space-separated),
`reason`, `note`, `source` (`hand` or `alpaca-paper:<client_order_id>`), `month_closed` (yes or no). UTF-8, a
header row, Python's default dialect: lines end with `\r\n` and a field is quoted only when it holds a comma, a
quote or a line break (Python Software Foundation, n.d.). A reason or a note that starts with a character a
spreadsheet reads as a formula is written with a leading apostrophe (OWASP Foundation, n.d.). The response is an
attachment named `logbook-account-<id>.csv` with `Cache-Control: no-store`. Row 110.

## Steps

### 12.1 The tests

Listing 12-1, Filename: `tests/test_ch12.py`:

```python
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
    assert "Version 1: 100.00 into INDEX" in html and "Why: A raise." in html
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
```

Things to notice:

- **The old tests are the first test.** Nothing in `test_ch10.py` or `test_ch11.py` changes. A form posted
  without a kind, as chapter 10's is, is a trade; chapter 10's `hold` is still refused as an action.
- **Real months, past and fixed.** The plan starts on January 1, 2026, so January to March are always in the
  past and their windows closed. Where a test needs "today", it passes a date to the function (`open_due_reviews`,
  `PlanChangeForm`) instead of reading the clock.
- **Chapter 11's fake is imported, not copied.** `FakeAlpaca`, the keys and the pinned day come from
  `tests/test_ch11.py`; the `fake` fixture is the same three lines.
- **Place again counts what Alpaca received.** Two clicks after an unfilled order make exactly one more POST,
  with the `-r2` id, and never a third.
- **The CSV is read back with `csv.reader`,** so the test checks the columns and the quoting the way a
  spreadsheet would see them, and a note that starts with a minus comes back with its apostrophe.

Run the tests:

Listing 12-2, Terminal:

```sh
uv run pytest tests/test_ch12.py
```

```text
tests/test_ch12.py:27: in <module>
    from invest_witus_site.methods.forms import PlanChangeForm, first_of_next_month
E   ImportError: cannot import name 'PlanChangeForm' from 'invest_witus_site.methods.forms' (.../src/invest_witus_site/methods/forms.py)
=========================== short test summary info ============================
ERROR tests/test_ch12.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.90s ===============================
```

Red at import. No package is added this chapter.

### 12.2 The rows

Listing 12-3, Filename: `src/invest_witus_site/methods/models.py`:

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

Chapter 12 turns the journal into a logbook and the plan into a history. An entry has a kind: a
trade (buy or sell, as before), a hold or a skip, each of the last two with a required reason; any
entry may carry a reason, a state of mind from a short fixed list, and tags. A plan changes by
becoming a new row, a *version*, that points at the one it replaced, so every month is judged by
the numbers in force that month. And each month whose window has closed gets a `MonthlyReview`,
closed by the owner with a short written review; a closed month's entries are read-only until the
review is reopened with a reason, and every close and reopen is kept as a `ReviewEvent`.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.conf import settings
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
    account (a partial unique constraint); an ended plan stays as history with `active` off.

    Chapter 12: a row is one *version* of a plan. Changing the amount, the window or the symbols
    makes a new row that points at the old one through `previous`, starts on the first day of a
    month, and becomes the active row; the old row keeps its numbers, gets `ended_on`, and goes
    on judging the months it was in force. Ending a plan sets `ended_on` and `end_reason`."""

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
    # Chapter 12: the plan's history. Every new column has a database default (`db_default`) as
    # well as Django's, so a row written by the previous release's code, which does not know the
    # column, is still valid while the migration workflow runs.
    version: models.PositiveSmallIntegerField[int, int] = models.PositiveSmallIntegerField(
        default=1, db_default=1, help_text="1 for the plan as started; one more for each change."
    )
    previous: models.OneToOneField[MethodPlan | None, MethodPlan | None] = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="next_version",
        help_text="The version this one replaced.",
    )
    change_reason: models.TextField[str, str] = models.TextField(
        blank=True, default="", db_default="", help_text="Why this version replaced the last."
    )
    ended_on: models.DateField[date | None, date | None] = models.DateField(
        null=True, blank=True, help_text="The last day this version was in force."
    )
    end_reason: models.TextField[str, str] = models.TextField(
        blank=True, default="", db_default="", help_text="Why the plan was ended."
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

    def versions(self) -> list[MethodPlan]:
        """Every version up to this one, oldest first, by following `previous` back."""
        chain: list[MethodPlan] = [self]
        while chain[-1].previous is not None:
            chain.append(chain[-1].previous)
        return chain[::-1]

    def latest_version(self) -> MethodPlan:
        """The newest version of the plan this row belongs to, by following the chain forward."""
        latest = self
        while (following := MethodPlan.objects.filter(previous=latest).first()) is not None:
            latest = following
        return latest

    def chain_start(self) -> date:
        """The first day of the first version: where the plan's practice budget began."""
        return self.versions()[0].started_on

    def in_force(self, day: date) -> MethodPlan:
        """The version that judges `day`: the newest whose span has begun, else the first one
        (the plan has not started yet)."""
        spans = version_spans(self.versions())
        begun = [span.plan for span in spans if span.first <= day]
        return begun[-1] if begun else (spans[0].plan if spans else self)


@dataclass(frozen=True, slots=True)
class Span:
    """One version and the days it judges: from its start through `last`, or open-ended."""

    plan: MethodPlan
    first: date
    last: date | None


def version_spans(versions: list[MethodPlan]) -> list[Span]:
    """Each version runs from its start to the day before the next version starts; the newest
    runs to its `ended_on`, or on. A version replaced before it started (a change scheduled for
    next month, then changed again) has no days, and is left out."""
    spans: list[Span] = []
    for index, version in enumerate(versions):
        if index + 1 < len(versions):
            last: date | None = versions[index + 1].started_on - timedelta(days=1)
        else:
            last = version.ended_on
        if last is None or last >= version.started_on:
            spans.append(Span(version, version.started_on, last))
    return spans


# The choices for an entry's action come from chapter 03's enum, so the two cannot drift: a value
# the review does not know cannot be stored.
ACTION_CHOICES = [(action.value, action.value.capitalize()) for action in Action]

# Chapter 12: what an entry is. A trade is chapter 10's row (a buy or a sell); a hold and a skip
# are decisions not to trade, and each needs a reason. Plain strings, not `TextChoices`, so the
# constants read as strings everywhere (chapter 11's note on pyright and choices).
TRADE = "trade"
HOLD = "hold"
SKIP = "skip"
KIND_CHOICES = [(TRADE, "Trade (a buy or a sell)"), (HOLD, "Hold"), (SKIP, "Skip")]
DECISIONS = frozenset({HOLD, SKIP})
# The state of mind an entry may record: a short fixed list, chosen in decisions row 104. Empty
# means not recorded. Each word describes the person at the moment of the entry, never the market.
STATE_CHOICES = [
    ("", "Not recorded"),
    ("calm", "Calm"),
    ("focused", "Focused"),
    ("confident", "Confident"),
    ("unsure", "Unsure"),
    ("stressed", "Stressed"),
    ("rushed", "Rushed"),
]
# Tags: up to five short words of the owner's own, lower case, letters, digits and hyphens.
MAX_TAGS = 5
TAG = re.compile(r"[a-z0-9][a-z0-9-]{0,23}")
REASON_MAX_LENGTH = 1000


def parse_tags(text: str) -> list[str]:
    """`"Late, news  late"` becomes `["late", "news"]`, or a `ValueError` naming the problem."""
    tags: list[str] = []
    for token in text.replace(",", " ").lower().split():
        if TAG.fullmatch(token) is None:
            raise ValueError(
                f"{token!r} is not a tag: letters, digits and hyphens, 24 characters at most"
            )
        if token not in tags:
            tags.append(token)
    if len(tags) > MAX_TAGS:
        raise ValueError(f"{len(tags)} tags; the most is {MAX_TAGS}")
    return tags


def validate_tags(value: str) -> None:
    try:
        parse_tags(value)
    except ValueError as error:
        raise ValidationError(str(error)) from None


def month_of(day: date) -> str:
    return f"{day.year}-{day.month:02d}"


class JournalEntry(models.Model):
    """One line of the logbook. Chapter 10's row was a trade the person logged by hand: the day,
    buy or sell, the symbol, the money, and the shares if the confirmation showed them. Chapter 12
    adds the kind (a hold or a skip is a decision with a reason, and has no amount), the reason,
    the state of mind and the tags."""

    account: models.ForeignKey[Account, Account] = models.ForeignKey(
        Account, on_delete=models.CASCADE
    )
    date: models.DateField[date, date] = models.DateField(help_text="The day it happened.")
    kind: models.CharField[str, str] = models.CharField(
        max_length=5, choices=KIND_CHOICES, default=TRADE, db_default=TRADE
    )
    action: models.CharField[str, str] = models.CharField(
        max_length=4,
        choices=ACTION_CHOICES,
        blank=True,
        help_text="Trades only: buy or sell. Leave empty for a hold or a skip.",
    )
    symbol: models.CharField[str, str] = models.CharField(
        max_length=20,
        validators=[validate_symbol],
        blank=True,
        help_text="Trades name one. Optional for a hold or a skip.",
    )
    amount: models.DecimalField[Decimal | None, Decimal | None] = models.DecimalField(
        max_digits=14,
        decimal_places=MONEY_PLACES,
        null=True,
        blank=True,
        validators=[MinValueValidator(ONE_CENT)],
        help_text="Trades only: the money that changed hands.",
    )
    shares: models.DecimalField[Decimal | None, Decimal | None] = models.DecimalField(
        max_digits=18,
        decimal_places=SHARE_PLACES,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="From the confirmation, if shown. Optional.",
    )
    reason: models.TextField[str, str] = models.TextField(
        blank=True,
        default="",
        db_default="",
        max_length=REASON_MAX_LENGTH,
        help_text="Why. Required for a hold or a skip.",
    )
    state: models.CharField[str, str] = models.CharField(
        max_length=10,
        choices=STATE_CHOICES,
        blank=True,
        default="",
        db_default="",
        help_text="How you were when you decided. Optional.",
    )
    tags: models.CharField[str, str] = models.CharField(
        max_length=200,
        blank=True,
        default="",
        db_default="",
        validators=[validate_tags],
        help_text="Up to five words of your own, separated by spaces or commas. Optional.",
    )
    note: models.CharField[str, str] = models.CharField(max_length=200, blank=True, default="")
    created_at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now_add=True)
    # The foreign key's own column, which Django adds; declared so pyright can read it.
    account_id: int | None

    class Meta:
        ordering = ["account", "date", "pk"]
        verbose_name = "journal entry"
        verbose_name_plural = "journal entries"

    def __str__(self) -> str:
        if self.kind == TRADE:
            return f"{self.date:%Y-%m-%d} {self.action} {self.amount} of {self.symbol}"
        return f"{self.date:%Y-%m-%d} {self.kind}{f' {self.symbol}' if self.symbol else ''}"

    @property
    def is_trade(self) -> bool:
        return self.kind == TRADE

    @property
    def what(self) -> str:
        """The word a table prints: Buy, Sell, Hold or Skip."""
        return (self.action if self.kind == TRADE else self.kind).capitalize()

    @property
    def money(self) -> Decimal:
        """The amount, or zero for a decision with none, for sums."""
        return self.amount if self.amount is not None else Decimal("0")

    def tag_list(self) -> list[str]:
        return self.tags.split()

    def clean(self) -> None:
        """The rules of a line beyond each field's own: a trade is a buy or a sell of a symbol for
        an amount; a hold or a skip has a reason and no money; and nothing is written into a
        month whose review is closed. A `ModelForm` and the admin run this before `save()`."""
        errors: dict[str, str] = {}
        if self.kind == TRADE:
            if self.action not in {action.value for action in Action}:
                errors["action"] = "A trade is a buy or a sell."
            if not self.symbol:
                errors["symbol"] = "A trade names its symbol."
            if self.amount is None:
                errors["amount"] = "A trade has an amount."
        elif self.kind in DECISIONS:
            if not self.reason.strip():
                errors["reason"] = f"A {self.kind} needs a reason: write why, in a sentence."
            if self.action:
                errors["action"] = f"A {self.kind} is not a trade: leave Action empty."
            if self.amount is not None or self.shares is not None:
                errors["amount"] = f"A {self.kind} moves no money: leave Amount and Shares empty."
        if errors:
            raise ValidationError(errors)
        self.refuse_closed_month()

    def refuse_closed_month(self) -> None:
        """A closed month is read-only: a new line dated in it, or a change to a line that was
        dated in it, is refused until its review is reopened with a reason."""
        # An invalid date in a form leaves the field empty, whatever its annotation says.
        day: date | None = getattr(self, "date", None)
        if self.account_id is None or day is None:
            return
        days = {day}
        if self.pk is not None:
            stored = JournalEntry.objects.filter(pk=self.pk).values_list("date", flat=True).first()
            if stored is not None:
                days.add(stored)
        for each in sorted(days):
            if MonthlyReview.is_closed(self.account_id, each):
                raise ValidationError(
                    f"{month_of(each)} is closed. Reopen its review, with a reason, to change it."
                )

    def save(self, *args: Any, **kwargs: Any) -> None:
        """The same guards as a statement line: no float, the symbol's rule, the rounding. A hold
        or a skip without a reason is refused here too, whatever path wrote it."""
        for field in ("amount", "shares"):
            if isinstance(getattr(self, field), float):
                raise TypeError(f"{field} must be a Decimal, not a float")
        if self.kind in DECISIONS and not self.reason.strip():
            raise ValueError(f"a {self.kind} needs a reason")
        if self.symbol:
            self.symbol = normalize_symbol(self.symbol)
        if self.amount is not None:
            self.amount = to_money(self.amount)
        if self.shares is not None:
            self.shares = to_shares(self.shares)
        self.tags = " ".join(parse_tags(self.tags))
        super().save(*args, **kwargs)

    def to_entry(self) -> Entry:
        """Chapter 03's `Entry`, for a trade. `Action(self.action)` raises on a value the enum
        lacks, which the choices and the form make impossible to store. A hold or a skip is not a
        trade, and the review never sees one."""
        if self.kind != TRADE or self.amount is None:
            raise ValueError(f"a {self.kind} is not a trade")
        return Entry(
            day=self.date, action=Action(self.action), symbol=self.symbol, amount=self.amount
        )

    @classmethod
    def entries_for(cls, account: Account) -> list[JournalEntry]:
        """The account's rows in date order, the order `review` and the pages want."""
        return list(cls.objects.filter(account=account))


class MonthlyReview(models.Model):
    """One month of one plan version, opened when the month's buy window closes and closed by the
    owner with three short answers: what I did, what the rules said, what I'll do next month."""

    plan: models.ForeignKey[MethodPlan, MethodPlan] = models.ForeignKey(
        MethodPlan, on_delete=models.PROTECT, related_name="reviews"
    )
    month: models.CharField[str, str] = models.CharField(max_length=7, help_text="YYYY-MM")
    opened_on: models.DateField[date, date] = models.DateField(
        help_text="The day the month's buy window closed."
    )
    did: models.TextField[str, str] = models.TextField(blank=True, default="")
    rules_said: models.TextField[str, str] = models.TextField(blank=True, default="")
    next_month: models.TextField[str, str] = models.TextField(blank=True, default="")
    closed_at: models.DateTimeField[datetime | None, datetime | None] = models.DateTimeField(
        null=True, blank=True
    )
    created_at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["month", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["plan", "month"], name="one_review_per_plan_month")
        ]
        verbose_name = "monthly review"
        verbose_name_plural = "monthly reviews"

    def __str__(self) -> str:
        return f"{self.month} {'closed' if self.closed else 'open'} ({self.plan})"

    @property
    def closed(self) -> bool:
        return self.closed_at is not None

    @classmethod
    def is_closed(cls, account_id: int, day: date) -> bool:
        return cls.objects.filter(
            plan__account_id=account_id, month=month_of(day), closed_at__isnull=False
        ).exists()


class ReviewEvent(models.Model):
    """The audit trail of a review: every close, with what was written, and every reopen, with
    its reason, who did it and when. Rows are only ever added."""

    CLOSED = "closed"
    REOPENED = "reopened"
    ACTIONS = [(CLOSED, "Closed"), (REOPENED, "Reopened")]

    review: models.ForeignKey[MonthlyReview, MonthlyReview] = models.ForeignKey(
        MonthlyReview, on_delete=models.CASCADE, related_name="events"
    )
    action: models.CharField[str, str] = models.CharField(max_length=8, choices=ACTIONS)
    text: models.TextField[str, str] = models.TextField()
    by: models.ForeignKey[Any, Any] = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["at", "pk"]
        verbose_name = "review event"
        verbose_name_plural = "review events"

    def __str__(self) -> str:
        return f"{self.review.month} {self.action} {self.at:%Y-%m-%d %H:%M}"
```

Things to notice:

- **Every new column on an old table has `db_default` as well as `default`.** Django's `default` is applied in
  Python when the ORM makes a row. `db_default` is "set at the database level and will be used when inserting
  rows outside of the ORM or when adding a new field in a migration" (Django Software Foundation, n.d.-b). Chapter
  11's `default=""` alone made the migration fill the old rows and then drop the database default, so the
  previous release, still serving while the migration workflow ran, would have failed to insert a row. With
  both, `default` still "take[s] precedence when creating instances in Python code" (Django Software Foundation,
  n.d.-b), so `entry.reason` is a string before the first save.
- **`amount` became nullable.** A skip moves no money. Dropping a `NOT NULL` is additive too: the old code always
  wrote an amount.
- **`clean()` holds the rules between fields,** and returns a dictionary keyed by field, so each message lands
  beside its box. `save()` refuses a hold or a skip with no reason as well, whatever path wrote it.
- **`refuse_closed_month()` checks two dates** on an edit: the one the line has now and the one it had, so a
  line cannot be moved into a closed month, or out of one.
- **`TextField(max_length=...)` limits the form, not the database** (Django Software Foundation, n.d.-b). That is
  enough here: every reason arrives through a form.
- **`account_id: int | None` is a declaration only,** so pyright can read the column Django adds for the foreign
  key.
- **`version_spans` is a pure function** of the chain. A version replaced before it started has no days and is
  left out, which is how a scheduled change that is changed again disappears from the review but stays in the
  table.

The paper order gains its attempt number, and the order id its suffix:

Listing 12-4, Filename: `src/invest_witus_site/paper/models.py`:

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


def client_order_id(
    account_pk: int, plan_pk: int, month: str, symbol: str, attempt: int = 1
) -> str:
    """The same facts always give the same id, so Alpaca and this table both see a repeat as the
    order they already have. `iw-12-3-2026-11-INDEX`: well under Alpaca's 128 characters (a
    symbol is at most 12). Chapter 12: a month whose order ended with nothing filled may be placed
    again, and the second try is a new order with a new id, `iw-12-3-2026-11-INDEX-r2`; the first
    try keeps the chapter 11 id with no suffix."""
    base = f"iw-{account_pk}-{plan_pk}-{month}-{symbol}"
    return base if attempt == 1 else f"{base}-r{attempt}"


class PaperOrder(models.Model):
    account: models.ForeignKey[Account, Account] = models.ForeignKey(
        Account, on_delete=models.CASCADE
    )
    plan: models.ForeignKey[MethodPlan, MethodPlan] = models.ForeignKey(
        MethodPlan, on_delete=models.PROTECT
    )
    month: models.CharField[str, str] = models.CharField(max_length=7, help_text="YYYY-MM")
    symbol: models.CharField[str, str] = models.CharField(max_length=20)
    # Chapter 12: 1 for the month's first order, 2 for "Place again" after it ended unfilled, and
    # so on. A database default too, so the previous release can still write a row mid-migration.
    attempt: models.PositiveSmallIntegerField[int, int] = models.PositiveSmallIntegerField(
        default=1, db_default=1
    )
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
        ordering = ["-month", "symbol", "-attempt"]
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

    @property
    def ended_unfilled(self) -> bool:
        """Alpaca is done with it and nothing was bought: the month may be placed again."""
        return self.placed and self.final and self.filled_qty == 0

    @classmethod
    def for_month(cls, plan: MethodPlan, month: str) -> list[PaperOrder]:
        """The plan's orders for the month, every attempt, the first try first."""
        return list(cls.objects.filter(plan=plan, month=month).order_by("symbol", "attempt"))

    @classmethod
    def open_orders(cls, account: Account | None = None) -> models.QuerySet[PaperOrder]:
        """Orders Alpaca has and that can still change: the sync's work list."""
        orders = cls.objects.exclude(alpaca_id="").exclude(status__in=FINAL_STATUSES)
        return orders.filter(account=account) if account is not None else orders
```

Attempt 1 keeps chapter 11's id with no suffix, so every order already placed keeps the id Alpaca knows it by.
With both models changed, make the two migrations, then let ruff tidy them:

Listing 12-5, Terminal:

```sh
uv run --env-file .env python manage.py makemigrations methods --name journal_kinds_plan_versions_and_reviews
uv run --env-file .env python manage.py makemigrations paper --name paperorder_attempt
uv run ruff format src/invest_witus_site/*/migrations/
uv run ruff check --fix src/invest_witus_site/*/migrations/
```

```text
Migrations for 'methods':
  src/invest_witus_site/methods/migrations/0003_journal_kinds_plan_versions_and_reviews.py
    + Add field kind to journalentry
    + Add field reason to journalentry
    + Add field state to journalentry
    + Add field tags to journalentry
    + Add field change_reason to methodplan
    + Add field end_reason to methodplan
    + Add field ended_on to methodplan
    + Add field previous to methodplan
    + Add field version to methodplan
    ~ Alter field action on journalentry
    ~ Alter field amount on journalentry
    ~ Alter field date on journalentry
    ~ Alter field symbol on journalentry
    + Create model MonthlyReview
    + Create model ReviewEvent
    + Create constraint one_review_per_plan_month on model monthlyreview
Migrations for 'paper':
  src/invest_witus_site/paper/migrations/0002_paperorder_attempt.py
    ~ Change Meta options on paperorder
    + Add field attempt to paperorder
```

Listing 12-6, Filename: `src/invest_witus_site/methods/migrations/0003_journal_kinds_plan_versions_and_reviews.py`:

```python
# Generated by Django 5.2.18 on 2026-10-29 15:48

from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import invest_witus_site.methods.models
import invest_witus_site.watchlist.models


class Migration(migrations.Migration):
    dependencies = [
        ("methods", "0002_methodplan_practice_budget"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="journalentry",
            name="kind",
            field=models.CharField(
                choices=[("trade", "Trade (a buy or a sell)"), ("hold", "Hold"), ("skip", "Skip")],
                db_default="trade",
                default="trade",
                max_length=5,
            ),
        ),
        migrations.AddField(
            model_name="journalentry",
            name="reason",
            field=models.TextField(
                blank=True,
                db_default="",
                default="",
                help_text="Why. Required for a hold or a skip.",
                max_length=1000,
            ),
        ),
        migrations.AddField(
            model_name="journalentry",
            name="state",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "Not recorded"),
                    ("calm", "Calm"),
                    ("focused", "Focused"),
                    ("confident", "Confident"),
                    ("unsure", "Unsure"),
                    ("stressed", "Stressed"),
                    ("rushed", "Rushed"),
                ],
                db_default="",
                default="",
                help_text="How you were when you decided. Optional.",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="journalentry",
            name="tags",
            field=models.CharField(
                blank=True,
                db_default="",
                default="",
                help_text="Up to five words of your own, separated by spaces or commas. Optional.",
                max_length=200,
                validators=[invest_witus_site.methods.models.validate_tags],
            ),
        ),
        migrations.AddField(
            model_name="methodplan",
            name="change_reason",
            field=models.TextField(
                blank=True,
                db_default="",
                default="",
                help_text="Why this version replaced the last.",
            ),
        ),
        migrations.AddField(
            model_name="methodplan",
            name="end_reason",
            field=models.TextField(
                blank=True, db_default="", default="", help_text="Why the plan was ended."
            ),
        ),
        migrations.AddField(
            model_name="methodplan",
            name="ended_on",
            field=models.DateField(
                blank=True, help_text="The last day this version was in force.", null=True
            ),
        ),
        migrations.AddField(
            model_name="methodplan",
            name="previous",
            field=models.OneToOneField(
                blank=True,
                help_text="The version this one replaced.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="next_version",
                to="methods.methodplan",
            ),
        ),
        migrations.AddField(
            model_name="methodplan",
            name="version",
            field=models.PositiveSmallIntegerField(
                db_default=1,
                default=1,
                help_text="1 for the plan as started; one more for each change.",
            ),
        ),
        migrations.AlterField(
            model_name="journalentry",
            name="action",
            field=models.CharField(
                blank=True,
                choices=[("buy", "Buy"), ("sell", "Sell")],
                help_text="Trades only: buy or sell. Leave empty for a hold or a skip.",
                max_length=4,
            ),
        ),
        migrations.AlterField(
            model_name="journalentry",
            name="amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Trades only: the money that changed hands.",
                max_digits=14,
                null=True,
                validators=[django.core.validators.MinValueValidator(Decimal("0.01"))],
            ),
        ),
        migrations.AlterField(
            model_name="journalentry",
            name="date",
            field=models.DateField(help_text="The day it happened."),
        ),
        migrations.AlterField(
            model_name="journalentry",
            name="symbol",
            field=models.CharField(
                blank=True,
                help_text="Trades name one. Optional for a hold or a skip.",
                max_length=20,
                validators=[invest_witus_site.watchlist.models.validate_symbol],
            ),
        ),
        migrations.CreateModel(
            name="MonthlyReview",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("month", models.CharField(help_text="YYYY-MM", max_length=7)),
                ("opened_on", models.DateField(help_text="The day the month's buy window closed.")),
                ("did", models.TextField(blank=True, default="")),
                ("rules_said", models.TextField(blank=True, default="")),
                ("next_month", models.TextField(blank=True, default="")),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="reviews",
                        to="methods.methodplan",
                    ),
                ),
            ],
            options={
                "verbose_name": "monthly review",
                "verbose_name_plural": "monthly reviews",
                "ordering": ["month", "pk"],
            },
        ),
        migrations.CreateModel(
            name="ReviewEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "action",
                    models.CharField(
                        choices=[("closed", "Closed"), ("reopened", "Reopened")], max_length=8
                    ),
                ),
                ("text", models.TextField()),
                ("at", models.DateTimeField(auto_now_add=True)),
                (
                    "by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "review",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="events",
                        to="methods.monthlyreview",
                    ),
                ),
            ],
            options={
                "verbose_name": "review event",
                "verbose_name_plural": "review events",
                "ordering": ["at", "pk"],
            },
        ),
        migrations.AddConstraint(
            model_name="monthlyreview",
            constraint=models.UniqueConstraint(
                fields=("plan", "month"), name="one_review_per_plan_month"
            ),
        ),
    ]
```

The four `Alter field` lines change no data: `action`, `symbol` and `date` changed only their `blank` flag or help
text, which Django records in the migration and the database ignores; `amount` drops its `NOT NULL`.

Listing 12-7, Filename: `src/invest_witus_site/paper/migrations/0002_paperorder_attempt.py`:

```python
# Generated by Django 5.2.18 on 2026-10-29 15:48

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("paper", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="paperorder",
            options={
                "ordering": ["-month", "symbol", "-attempt"],
                "verbose_name": "paper order",
                "verbose_name_plural": "paper orders",
            },
        ),
        migrations.AddField(
            model_name="paperorder",
            name="attempt",
            field=models.PositiveSmallIntegerField(db_default=1, default=1),
        ),
    ]
```

### 12.3 The engine

Listing 12-8, Filename: `src/invest_witus_site/methods/engine.py`:

```python
"""What the method page shows, built once: the plan, its rules with their lessons, the review's
findings, every month of the plan with its status, and the next action.

Chapter 03's `review` is called here exactly as the command line called it, on the values the
two converters in `models.py` produce. Everything else in this module is arrangement: the same
findings grouped by rule for a table, by month for another, and the one sentence that says what
to do next. The three views (A, B and C) render this one `MethodReview`; none of them queries
anything the others do not get.

Chapter 12 adds three things, all arrangement, none a new rule:

- **Versions.** A plan that changed is several rows; each judges only its own months (its span),
  so `review` runs once per version with that version's numbers and the results are joined.
- **Explained misses.** Chapter 03's "No buy in 2026-03" is still a finding of the rule "buy once
  in every month". When the journal has a skip for that month, the skip's reason is attached to
  the finding, the month reads "skipped" instead of "missed", and the rule's status reads
  "explained" when every finding it has is. The rule and `CHECKED_RULES` are unchanged.
- **The count of months followed:** the months due that were done with no finding.
"""

from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal

from invest_witus.adherence.journal import Action, Entry
from invest_witus.adherence.plan import Plan
from invest_witus.adherence.review import Finding, months_due, review
from invest_witus.methods.rulebook import LESSON_COMING, Method
from invest_witus_site.methods.models import SKIP, JournalEntry, MethodPlan, Span, version_spans

ZERO = Decimal("0")
# The one rule a skip can explain: a month with no buy. The id is the TOML file's.
ONE_BUY = "one-buy-each-month"


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
    """One finding with the rule it broke and the month it concerns. `explanation` is the reason
    of the skip that explains it, or "" when nothing does."""

    day: date
    month: str
    rule: RuleLine
    message: str
    explanation: str = ""

    @property
    def explained(self) -> bool:
        return bool(self.explanation)


@dataclass(frozen=True, slots=True)
class RuleCheck:
    """One rule's result through the review date: pass with no findings, fail with the list."""

    rule: RuleLine
    findings: list[FindingLine]

    @property
    def status(self) -> str:
        """pass with no findings; explained when every finding has a skip's reason; else fail."""
        if not self.findings:
            return "pass"
        return "explained" if all(f.explained for f in self.findings) else "fail"

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
        explained = sum(1 for finding in self.findings if finding.explained)
        note = f" ({explained} explained)" if explained else ""
        return f"{count} finding{'' if count == 1 else 's'}: {self.months}{note}"


@dataclass(frozen=True, slots=True)
class MonthRow:
    """One month of the plan: the window, what was bought, and whether the month is done,
    missed, skipped (no buy, and a skip with its reason), or still open on the review date.
    `version` is the plan version that judged it."""

    label: str
    window_closes: date
    status: str
    buys: int
    amount: Decimal
    shares: Decimal | None
    rule_ids: list[str]
    version: int = 1
    skip_reason: str = ""


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
    spans: list[Span] = field(default_factory=list[Span])

    @property
    def on_plan(self) -> bool:
        return not self.findings

    @property
    def unexplained(self) -> list[FindingLine]:
        return [finding for finding in self.findings if not finding.explained]

    @property
    def explained_count(self) -> int:
        return len(self.findings) - len(self.unexplained)

    @property
    def months_followed(self) -> int:
        """Months due that were done as the rules said: a buy, and no finding in the month."""
        return sum(1 for row in self.months if row.status == "done" and not row.rule_ids)

    def month(self, label: str) -> MonthRow | None:
        return next((row for row in self.months if row.label == label), None)

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
    plan: Plan,
    entries: list[JournalEntry],
    findings: list[FindingLine],
    through: date,
    version: int = 1,
) -> list[MonthRow]:
    """Every month from the plan's start through `through`: the months whose window has closed
    (chapter 03's `months_due`) and, if the review date falls inside a window that is still open,
    that month too, marked open. The rows are the journal's own, not chapter 03's values, because
    the shares column exists only here; the shares total is `None` when any buy in the month
    left shares blank, so a partial total is never printed as a whole. A month with no buy and a
    skip in the journal reads "skipped", with the skip's reason."""
    due = months_due(plan, through)
    months = list(due)
    if through >= plan.start:
        current = (through.year, through.month)
        if current not in months and current >= (plan.start.year, plan.start.month):
            months.append(current)
    buys = [e for e in entries if e.action == Action.BUY.value and plan.start <= e.date <= through]
    skips = [e for e in entries if e.kind == SKIP and plan.start <= e.date <= through]
    rows: list[MonthRow] = []
    for year, month in months:
        label = month_label(year, month)
        in_month = [b for b in buys if (b.date.year, b.date.month) == (year, month)]
        skipped = [s for s in skips if (s.date.year, s.date.month) == (year, month)]
        if in_month:
            status = "done"
        elif skipped:
            status = "skipped"
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
                amount=sum((b.money for b in in_month), ZERO),
                shares=shares,
                rule_ids=sorted({f.rule.id for f in findings if f.month == label}),
                version=version,
                skip_reason=skipped[0].reason if skipped and not in_month else "",
            )
        )
    return rows


def next_action(
    plan: Plan,
    entries: list[Entry],
    today: date,
    skipped: frozenset[tuple[int, int]] = frozenset(),
) -> NextAction:
    """The next buy. Before the start: the start month's window. In a month with no buy yet and
    the window open: that window, due now. Otherwise, the month after: this month's buy is done,
    or its window has closed (the review says "No buy" for it; the next action is still the
    next window, because the method has no catching up). Chapter 12: a month in `skipped` (a
    skip with its reason in the journal) counts as decided, like a month with a buy."""
    bought = {(e.day.year, e.day.month) for e in entries if e.action is Action.BUY} | skipped
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


def explain(findings: list[FindingLine], months: list[MonthRow]) -> list[FindingLine]:
    """Attach a skip's reason to the "No buy" finding of a month the journal says was skipped.
    Only that rule, and only a month with no buy: a skip does not excuse two buys."""
    skipped = {row.label: row.skip_reason for row in months if row.status == "skipped"}
    return [
        replace(finding, explanation=skipped[finding.month])
        if finding.rule.id == ONE_BUY and finding.month in skipped
        else finding
        for finding in findings
    ]


def span_through(span: Span, through: date) -> date:
    return through if span.last is None else min(through, span.last)


def version_on(spans: list[Span], day: date) -> MethodPlan:
    begun = [span.plan for span in spans if span.first <= day]
    return begun[-1] if begun else spans[0].plan


def build_review(plan: MethodPlan, entries: list[JournalEntry], through: date) -> MethodReview:
    """The whole context for the method page, from the row, the rows and the date. `plan` is the
    newest version; each version in its history is reviewed over its own span, with its own
    numbers, and the findings and months are joined in order."""
    method = plan.method()
    spans = version_spans(plan.versions() if plan.pk is not None else [plan])
    if not spans:
        spans = [Span(plan, plan.started_on, plan.ended_on)]
    trades = [entry.to_entry() for entry in entries if entry.is_trade]
    rules = rule_lines(method)
    by_id = {rule.id: rule for rule in rules}
    findings: list[FindingLine] = []
    months: list[MonthRow] = []
    for span in spans:
        upto = span_through(span, through)
        version = span.plan.to_plan()
        found = finding_lines(review(span.plan.method(), version, trades, upto), by_id)
        findings += found
        months += month_rows(version, entries, found, upto, span.plan.version)
    findings = explain(findings, months)
    skipped = frozenset(
        (e.date.year, e.date.month) for e in entries if e.kind == SKIP and e.date >= spans[0].first
    )
    now = version_on(spans, through)
    action = next_action(now.to_plan(), trades, through, skipped)
    if now is not plan and action.opens >= plan.started_on:
        action = next_action(plan.to_plan(), trades, through, skipped)
    return MethodReview(
        plan=plan,
        method=method,
        rules=rules,
        through=through,
        entries=entries,
        findings=findings,
        checks=rule_checks(rules, findings),
        months=months,
        next_action=action,
        spans=spans,
    )
```

Things to notice:

- **`review()` is still called as chapter 03 called it,** once per span, with that version's `Plan` and the
  trades only. The loop joins the findings and the months.
- **`explain` uses `dataclasses.replace`.** A `FindingLine` is frozen; the explained one is a new value with the
  reason filled in.
- **New fields have defaults** (`explanation`, `version`, `skip_reason`, `spans`), so chapter 10's tests, which
  build and read these values, still pass.
- **The next action checks the version once more.** While a change is scheduled for next month, this month
  belongs to the old version, and next month's window to the new one.

### 12.4 The monthly review

Listing 12-9, Filename: `src/invest_witus_site/methods/reviews.py`:

```python
"""The monthly review: opened when a month's buy window closes, closed by the owner with a short
written review, and reopened only with a reason.

A `MonthlyReview` row is made for every month of the plan whose window has closed, the first time
a page that shows the plan is drawn after that day; its `opened_on` is the day the window closed,
not the day the row was written, so the record says when the review became due whatever day the
owner first looked. Closing asks three questions (what I did, what the rules said, what I'll do
next month) and is refused while the month has a missed buy with no skip to explain it: the PRD's
"a review cannot be closed with an unexplained skip". Every close and every reopen is a
`ReviewEvent`, so the history of a month survives a reopen and a second close.
"""

from datetime import date

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.db import transaction
from django.utils import timezone

from invest_witus.adherence.review import months_due
from invest_witus_site.methods.engine import MethodReview, month_label, span_through
from invest_witus_site.methods.models import (
    MethodPlan,
    MonthlyReview,
    ReviewEvent,
    version_spans,
)


class ReviewRefused(Exception):
    """The review cannot be closed or reopened; the message says why, in a sentence."""


def open_due_reviews(plan: MethodPlan, today: date) -> list[MonthlyReview]:
    """Make the review row for every month of the plan whose window has closed by `today`, one per
    version and month, and return them all, oldest first. Safe to call on every page view: the
    rows that exist are left alone, and `ignore_conflicts` lets two requests race harmlessly."""
    spans = version_spans(plan.versions())
    versions = [span.plan for span in spans]
    existing = set(MonthlyReview.objects.filter(plan__in=versions).values_list("plan_id", "month"))
    missing: list[MonthlyReview] = []
    for span in spans:
        for year, month in months_due(span.plan.to_plan(), span_through(span, today)):
            label = month_label(year, month)
            if (span.plan.pk, label) not in existing:
                window_closed = date(year, month, span.plan.buy_window_days)
                missing.append(MonthlyReview(plan=span.plan, month=label, opened_on=window_closed))
    if missing:
        MonthlyReview.objects.bulk_create(missing, ignore_conflicts=True)
    return list(
        MonthlyReview.objects.filter(plan__in=versions).select_related("plan").order_by("month")
    )


def close_refusal(review: MonthlyReview, context: MethodReview) -> str:
    """The reason the month cannot be closed, or "". Only a missed buy with no skip blocks it:
    any other finding (a late buy, a wrong amount) is what the written review is for."""
    if review.closed:
        return f"{review.month} is already closed."
    row = context.month(review.month)
    if row is not None and row.status == "missed":
        return (
            f"{review.month} has no buy and no skip with a reason. Log a skip that says why "
            "the month had no buy, then close it."
        )
    return ""


def written(review: MonthlyReview) -> str:
    """The three answers as one text, the way the audit trail keeps them."""
    return (
        f"What I did: {review.did}\n"
        f"What the rules said: {review.rules_said}\n"
        f"What I'll do next month: {review.next_month}"
    )


def close_review(
    review: MonthlyReview,
    context: MethodReview,
    *,
    did: str,
    rules_said: str,
    next_month: str,
    by: AbstractBaseUser | AnonymousUser,
) -> None:
    refusal = close_refusal(review, context)
    if refusal:
        raise ReviewRefused(refusal)
    with transaction.atomic():
        review.did, review.rules_said, review.next_month = did, rules_said, next_month
        review.closed_at = timezone.now()
        review.save()
        ReviewEvent.objects.create(
            review=review, action=ReviewEvent.CLOSED, text=written(review), by=user_or_none(by)
        )


def reopen_review(
    review: MonthlyReview, *, reason: str, by: AbstractBaseUser | AnonymousUser
) -> None:
    """Open a closed month again so its entries can change. The written review stays on the row
    and in the closed event; the reopen event keeps the reason."""
    if not review.closed:
        raise ReviewRefused(f"{review.month} is open already.")
    with transaction.atomic():
        review.closed_at = None
        review.save(update_fields=["closed_at"])
        ReviewEvent.objects.create(
            review=review, action=ReviewEvent.REOPENED, text=reason, by=user_or_none(by)
        )


def user_or_none(user: AbstractBaseUser | AnonymousUser) -> AbstractBaseUser | None:
    return user if isinstance(user, AbstractBaseUser) else None
```

`open_due_reviews` reads the rows that exist once and writes the missing ones in one `bulk_create` with
`ignore_conflicts=True`, so two pages drawn at once cannot make the same month twice; the unique constraint has
the last word. `close_review` and `reopen_review` change the row and add the event in one transaction, so there is
never a closed month without its record.

### 12.5 The forms

Listing 12-10, Filename: `src/invest_witus_site/methods/forms.py`:

```python
"""The method page's forms: start a method for an account, and log one journal entry. Chapter 12
adds three: change or end the plan with a reason, close a month's review, and reopen it."""

from collections.abc import Mapping
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction

from invest_witus.methods.rulebook import available_methods
from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.models import (
    MAX_WINDOW_DAYS,
    MIN_WINDOW_DAYS,
    ONE_CENT,
    REASON_MAX_LENGTH,
    TRADE,
    JournalEntry,
    MethodPlan,
    MonthlyReview,
    join_symbols,
    month_of,
    parse_tags,
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
                "This account already runs a method. End it from the method page before "
                "starting another."
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
    runs them again. The view passes `instance=JournalEntry(account=account)`, so the model's
    `clean()` knows the account and can refuse a closed month.

    Chapter 12: the kind, the reason, the state and the tags. A form posted without a kind (the
    chapter 10 form, a script) is a trade, as every entry was before this chapter."""

    class Meta:
        model = JournalEntry
        fields = [
            "date",
            "kind",
            "action",
            "symbol",
            "amount",
            "shares",
            "reason",
            "state",
            "tags",
            "note",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "symbol": forms.TextInput(attrs=SYMBOL_BOX),
            "reason": forms.Textarea(attrs={"rows": 2}),
            "tags": forms.TextInput(attrs={"autocomplete": "off", "spellcheck": "false"}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["kind"].required = False

    def clean_kind(self) -> str:
        kind: str = self.cleaned_data.get("kind") or ""
        return kind or TRADE

    def clean_tags(self) -> str:
        try:
            return " ".join(parse_tags(self.cleaned_data.get("tags") or ""))
        except ValueError as error:
            raise ValidationError(str(error)) from None


def first_of_month(day: date) -> date:
    return day.replace(day=1)


def first_of_next_month(day: date) -> date:
    return (day.replace(day=28) + timedelta(days=4)).replace(day=1)


THIS_MONTH = "this"
NEXT_MONTH = "next"
CHANGE = "change"
END = "end"


class PlanChangeForm(forms.Form):
    """Change the plan's amount, window or symbols, or end it, always with a reason. A change
    makes a new version that starts on the first day of this month or next month; the old version
    keeps judging the months before it (PRD 7.1: "old reviews keep pointing at the version they
    judged"). The method itself does not change here: a different method is a new plan."""

    what = forms.ChoiceField(
        label="What to do",
        choices=[(CHANGE, "Change the numbers"), (END, "End the plan")],
        widget=forms.RadioSelect,
        initial=CHANGE,
    )
    amount = forms.DecimalField(
        label="Amount each month",
        required=False,
        min_value=ONE_CENT,
        max_digits=14,
        decimal_places=2,
    )
    buy_window_days = forms.IntegerField(
        label="Buy window, in days",
        required=False,
        min_value=MIN_WINDOW_DAYS,
        max_value=MAX_WINDOW_DAYS,
    )
    symbols = forms.CharField(
        label="Symbols", required=False, max_length=200, widget=forms.TextInput(attrs=SYMBOL_BOX)
    )
    effective = forms.ChoiceField(label="Starting", required=False)
    reason = forms.CharField(
        label="Why",
        max_length=REASON_MAX_LENGTH,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Required. It is kept with the version, dated, for every later review.",
    )

    def __init__(
        self, plan: MethodPlan, today: date, data: Mapping[str, Any] | None = None
    ) -> None:
        initial = {
            "amount": plan.amount,
            "buy_window_days": plan.buy_window_days,
            "symbols": plan.symbols,
            "effective": NEXT_MONTH,
        }
        super().__init__(data, initial=initial)
        self.plan = plan
        self.today = today
        this, following = first_of_month(today), first_of_next_month(today)
        effective = self.fields["effective"]
        assert isinstance(effective, forms.ChoiceField)
        effective.choices = [
            (NEXT_MONTH, f"Next month, from {following:%Y-%m-%d}"),
            (THIS_MONTH, f"This month, from {this:%Y-%m-%d}"),
        ]

    def clean_symbols(self) -> str:
        text: str = self.cleaned_data.get("symbols") or ""
        if not text.strip():
            return ""
        validate_symbol_list(text)
        return join_symbols(text)

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean() or {}
        if cleaned.get("what") != CHANGE:
            return cleaned
        for name in ("amount", "buy_window_days", "symbols"):
            if name not in self.errors and cleaned.get(name) in (None, ""):
                self.add_error(name, "A change keeps every number: fill this in.")
        if self.errors:
            return cleaned
        plan = self.plan
        new = (cleaned["amount"], cleaned["buy_window_days"], cleaned["symbols"])
        if new == (plan.amount, plan.buy_window_days, plan.symbols):
            raise ValidationError("Nothing changed: the amount, the window and the symbols match.")
        if cleaned.get("effective") == THIS_MONTH:
            self.check_this_month()
        return cleaned

    def check_this_month(self) -> None:
        """This month may take the new numbers only while nothing in it is settled: the window is
        still open, no trade is logged in it, and the version in force has started. Otherwise
        the month already belongs to the old numbers, and the change starts next month."""
        plan, today = self.plan, self.today
        if plan.started_on > today:
            raise ValidationError(
                f"Version {plan.version} starts on {plan.started_on:%Y-%m-%d} and has not begun; "
                "a change to it starts next month."
            )
        if today.day > plan.buy_window_days:
            raise ValidationError(
                f"This month's window closed on day {plan.buy_window_days}; the month is judged "
                "by the numbers in force then. Choose next month."
            )
        traded = JournalEntry.objects.filter(
            account=plan.account,
            kind=TRADE,
            date__year=today.year,
            date__month=today.month,
            date__gte=plan.started_on,
        ).exists()
        if traded:
            raise ValidationError(
                f"{month_of(today)} already has a trade in the journal; it stays on version "
                f"{plan.version}. Choose next month."
            )
        if MonthlyReview.is_closed(plan.account.pk, today):
            raise ValidationError(f"{month_of(today)} is closed. Choose next month.")

    def apply(self) -> MethodPlan:
        """Write the change, after `is_valid()`. Ending: the row stays, inactive, with the day and
        the reason. Changing: the old row ends the day before the new version starts, and the
        new row points back at it. One transaction, the old row first, so the partial unique
        constraint (one active plan per account) never sees two."""
        plan, data = self.plan, self.cleaned_data
        reason: str = data["reason"].strip()
        with transaction.atomic():
            if data["what"] == END:
                plan.active = False
                plan.ended_on = self.today
                plan.end_reason = reason
                plan.save()
                return plan
            effective = (
                first_of_month(self.today)
                if data.get("effective") == THIS_MONTH
                else first_of_next_month(self.today)
            )
            starts = max(effective, plan.started_on)
            plan.active = False
            plan.ended_on = starts - timedelta(days=1)
            plan.save()
            return MethodPlan.objects.create(
                account=plan.account,
                method_id=plan.method_id,
                amount=data["amount"],
                buy_window_days=data["buy_window_days"],
                symbols=data["symbols"],
                started_on=starts,
                practice_budget=plan.practice_budget,
                previous=plan,
                version=plan.version + 1,
                change_reason=reason,
            )


TEXT_BOX = {"rows": 3}


class CloseReviewForm(forms.Form):
    """The month's written review: three short answers, each required."""

    did = forms.CharField(
        label="What I did",
        max_length=REASON_MAX_LENGTH,
        widget=forms.Textarea(attrs=TEXT_BOX),
    )
    rules_said = forms.CharField(
        label="What the rules said",
        max_length=REASON_MAX_LENGTH,
        widget=forms.Textarea(attrs=TEXT_BOX),
        help_text="Started for you from the review's findings. Edit it to say it your way.",
    )
    next_month = forms.CharField(
        label="What I'll do next month",
        max_length=REASON_MAX_LENGTH,
        widget=forms.Textarea(attrs=TEXT_BOX),
    )


class ReopenReviewForm(forms.Form):
    reason = forms.CharField(
        label="Why reopen it",
        max_length=REASON_MAX_LENGTH,
        widget=forms.Textarea(attrs=TEXT_BOX),
        help_text="Required, and kept: the month's history shows every close and reopen.",
    )
```

- **The log form's `kind` is not required,** and `clean_kind` turns nothing into `trade`. That keeps chapter 10's
  form, and any script that posts it, working.
- **`PlanChangeForm.apply` saves the old row first,** inactive, then creates the new one, inside one transaction:
  the partial unique constraint from chapter 10 allows one active plan per account, and never sees two.
- **`first_of_next_month`** adds four days to the 28th, which is always in the next month, then goes to its first
  day. No calendar arithmetic to get wrong.

### 12.6 The views and the routes

Listing 12-11, Filename: `src/invest_witus_site/methods/views.py`:

```python
"""The method page for one account, in three views, and its two POST actions.

`method_page` renders the same context through one of three templates, A, B or C, named as the
research named them (`docs/research/01-ux-benchmarks-and-three-directions.md`, section 5). The
choice comes from `?view=a|b|c`, is remembered in the session, and defaults to A when the
account runs a method and to C when it does not (PRD 7.2: C to start a method, A as the home).
Every view sits behind `login_required` and the same ownership query as chapter 08's pages, so
another owner's account is a 404; nothing here is public.

Chapter 12 adds the plan's change form (`change_plan`) and the month's review page with its two
actions (`review_month`, `close_month`, `reopen_month`). The method page opens the review of every
month whose window has closed, and view A offers to close the oldest one still open.
"""

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from invest_witus.methods.rulebook import available_methods
from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.engine import MethodReview, build_review, rule_lines
from invest_witus_site.methods.forms import (
    CloseReviewForm,
    JournalEntryForm,
    PlanChangeForm,
    ReopenReviewForm,
    StartMethodForm,
)
from invest_witus_site.methods.models import (
    JournalEntry,
    MethodPlan,
    MonthlyReview,
    ReviewEvent,
)
from invest_witus_site.methods.reviews import (
    ReviewRefused,
    close_review,
    open_due_reviews,
    reopen_review,
)
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
    # Chapter 12: every month whose window closed by today has a review; the oldest still open
    # is the one view A offers to close. Opened against today, never `?through=`.
    month_reviews = open_due_reviews(plan, today) if plan is not None else []
    still_open = [review for review in month_reviews if not review.closed]
    context = {
        "account": account,
        "plan": plan,
        "review": build_review(plan, entries, through) if plan is not None else None,
        "entries": entries,
        "catalog": [(method, rule_lines(method)) for method in available_methods()],
        "start_form": start_form or StartMethodForm(account),
        "entry_form": entry_form or JournalEntryForm(initial={"date": today}),
        "month_reviews": month_reviews,
        "review_to_close": still_open[0] if still_open else None,
        "open_reviews": len(still_open),
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
    form = JournalEntryForm(request.POST, instance=JournalEntry(account=account))
    if not form.is_valid():
        return render_method_page(request, account, entry_form=form)
    entry = form.save()
    messages.success(request, f"Logged: {entry}.")
    return redirect("method-page", pk=account.pk)


# --- Chapter 12: change or end the plan -----------------------------------------------------------


@login_required
def change_plan(request: HttpRequest, pk: int) -> HttpResponse:
    """GET draws the form with the plan's numbers; POST writes a new version or ends the plan."""
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    plan = MethodPlan.active_for(account)
    if plan is None:
        messages.info(request, "No method runs on this account, so there is no plan to change.")
        return redirect("method-page", pk=account.pk)
    today = timezone.localdate()
    form = PlanChangeForm(plan, today, request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        written = form.apply()
        if written.active:
            messages.success(
                request,
                f"Version {written.version} of the plan starts on {written.started_on:%Y-%m-%d}. "
                f"Version {plan.version} keeps its months, judged by its own numbers.",
            )
        else:
            messages.success(
                request,
                f"Ended {plan.method().name} on {account.name}. Its months and reviews stay; "
                "start a new method when you are ready.",
            )
            # With no plan, the method page is the Lesson Lab, where a new one starts.
            request.session[SESSION_KEY] = "c"
        return redirect("method-page", pk=account.pk)
    context = {"account": account, "plan": plan, "form": form, "versions": plan.versions()}
    return render(request, "methods/plan_change.html", context)


# --- Chapter 12: the month's review ---------------------------------------------------------------


def review_or_404(account: Account, month: str) -> MonthlyReview:
    """The account's review for the month: the newest plan's, if two plans share the month. The
    running plan's due reviews are opened first, so a link to a month works before the method
    page has been drawn that day."""
    plan = MethodPlan.active_for(account)
    if plan is not None:
        open_due_reviews(plan, timezone.localdate())
    review = (
        MonthlyReview.objects.filter(plan__account=account, month=month)
        .select_related("plan")
        .order_by("-plan__pk")
        .first()
    )
    if review is None:
        raise Http404("No review for that month.")
    return review


def month_context(review: MonthlyReview) -> MethodReview:
    """The plan's whole review through today, from the newest version of the review's plan."""
    plan = review.plan.latest_version()
    entries = JournalEntry.entries_for(plan.account)
    return build_review(plan, entries, timezone.localdate())


def rules_said_draft(context: MethodReview, month: str) -> str:
    """The second answer's starting text: the month's findings, or the sentence that none."""
    found = [f for f in context.findings if f.month == month]
    if not found:
        return "Every rule passed this month."
    lines: list[str] = []
    for finding in found:
        line = finding.message
        if finding.explained:
            line += f" (skipped: {finding.explanation})"
        lines.append(line)
    return " ".join(lines)


def render_review_page(
    request: HttpRequest,
    account: Account,
    review: MonthlyReview,
    close_form: CloseReviewForm | None = None,
    reopen_form: ReopenReviewForm | None = None,
) -> HttpResponse:
    context = month_context(review)
    row = context.month(review.month)
    entries = [entry for entry in context.entries if f"{entry.date:%Y-%m}" == review.month]
    page = {
        "account": account,
        "review": review,
        "version": review.plan,
        "row": row,
        "findings": [f for f in context.findings if f.month == review.month],
        "entries": entries,
        "events": list(ReviewEvent.objects.filter(review=review).select_related("by")),
        "close_form": close_form
        or CloseReviewForm(initial={"rules_said": rules_said_draft(context, review.month)}),
        "reopen_form": reopen_form or ReopenReviewForm(),
    }
    return render(request, "methods/review_month.html", page)


@login_required
def review_month(request: HttpRequest, pk: int, month: str) -> HttpResponse:
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    return render_review_page(request, account, review_or_404(account, month))


@login_required
@require_POST
def close_month(request: HttpRequest, pk: int, month: str) -> HttpResponse:
    """Close the month with the three answers. Refused, with the page drawn again, when a field
    is empty or the month has a missed buy that no skip explains."""
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    review = review_or_404(account, month)
    if review.closed:
        messages.error(request, f"{review.month} is already closed.")
        return redirect("method-review", pk=account.pk, month=review.month)
    form = CloseReviewForm(request.POST)
    if not form.is_valid():
        return render_review_page(request, account, review, close_form=form)
    try:
        close_review(review, month_context(review), by=request.user, **form.cleaned_data)
    except ReviewRefused as refused:
        form.add_error(None, str(refused))
        return render_review_page(request, account, review, close_form=form)
    messages.success(request, f"Closed {review.month}. Its entries are read-only now.")
    return redirect("method-page", pk=account.pk)


@login_required
@require_POST
def reopen_month(request: HttpRequest, pk: int, month: str) -> HttpResponse:
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    review = review_or_404(account, month)
    form = ReopenReviewForm(request.POST)
    if not form.is_valid():
        return render_review_page(request, account, review, reopen_form=form)
    try:
        reopen_review(review, reason=form.cleaned_data["reason"], by=request.user)
    except ReviewRefused as refused:
        messages.error(request, str(refused))
    else:
        messages.success(request, f"Reopened {review.month}. Its entries can change again.")
    return redirect("method-review", pk=account.pk, month=review.month)
```

The method page opens the due reviews against today, never against `?through=`, so a page drawn for an old date
does not open a month early or late. The log view passes `instance=JournalEntry(account=account)`, so the model's
`clean()` knows the account when it checks for a closed month.

Listing 12-12, Filename: `src/invest_witus_site/methods/urls.py`:

```python
"""The method page and its actions. `invest_witus_site/urls.py` mounts this file under
`accounts/<int:pk>/method/`, and the `pk` captured there reaches every view. Chapter 12 adds the
plan's change form and a month's review, with its close and reopen."""

from django.urls import path, re_path

from invest_witus_site.methods import views

# A month in a URL is `YYYY-MM`. A regular expression in the route itself, so anything else is
# not a route at all and answers 404 before a view runs.
MONTH = r"(?P<month>\d{4}-\d{2})"

urlpatterns = [
    path("", views.method_page, name="method-page"),
    path("start/", views.start_method, name="method-start"),
    path("log/", views.log_entry, name="method-log"),
    path("change/", views.change_plan, name="method-change"),
    re_path(rf"^review/{MONTH}/$", views.review_month, name="method-review"),
    re_path(rf"^review/{MONTH}/close/$", views.close_month, name="method-review-close"),
    re_path(rf"^review/{MONTH}/reopen/$", views.reopen_month, name="method-review-reopen"),
]
```

`re_path` with `\d{4}-\d{2}` makes `/review/2026-1/` a 404 before any view runs.

The logbook lives beside the method page, not inside it, because it outlives a plan:

Listing 12-13, Filename: `src/invest_witus_site/methods/logbook.py`:

```python
"""The logbook: every line of an account's journal on one page, filtered by month, kind and tag,
with an edit form for the lines written by hand and a CSV export.

The method page shows the journal as part of the review; this page is the journal itself. The
filters are plain GET parameters (`?month=2026-11&kind=skip&tag=late`), so a filtered view is a
link the owner can keep, and the export takes the same parameters, so the file holds what the
page shows. Everything here is the owner's only: chapter 08's ownership query, a 404 otherwise.

Two kinds of line cannot be edited here. A line a paper order wrote (chapter 11) is the broker's
record, kept in step by the nightly sync. And a line in a closed month is read-only until the
month's review is reopened with a reason (the model's `clean()` refuses it; this page also says
so before showing a form).
"""

import csv
import re
from dataclasses import dataclass

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render

from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.forms import JournalEntryForm
from invest_witus_site.methods.models import (
    DECISIONS,
    TAG,
    TRADE,
    JournalEntry,
    MonthlyReview,
    month_of,
)
from invest_witus_site.paper.models import PaperOrder

MONTH = re.compile(r"\d{4}-\d{2}")
KINDS = ("buy", "sell", "hold", "skip")
# The export's columns, in order. Documented in chapter 12; a test reads the header row.
CSV_COLUMNS = (
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
# A spreadsheet may run a cell that starts with one of these as a formula: OWASP's list, with the
# full-width forms. Text the owner typed is exported with a leading apostrophe instead.
FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r", "\n", "\uff1d", "\uff0b", "\uff0d", "\uff20")


@dataclass(frozen=True, slots=True)
class Filters:
    month: str
    kind: str
    tag: str

    @property
    def query(self) -> str:
        """The same filters as a query string, for the export link."""
        params = QueryDict(mutable=True)
        for name in ("month", "kind", "tag"):
            if value := getattr(self, name):
                params[name] = value
        encoded = params.urlencode()
        return f"?{encoded}" if encoded else ""


def read_filters(request: HttpRequest) -> Filters:
    """Each filter if it is well formed, else nothing: a bad value widens the list, never errors."""
    month = request.GET.get("month", "")
    kind = request.GET.get("kind", "")
    tag = request.GET.get("tag", "").lower()
    return Filters(
        month=month if MONTH.fullmatch(month) else "",
        kind=kind if kind in KINDS else "",
        tag=tag if TAG.fullmatch(tag) else "",
    )


def filtered(account: Account, filters: Filters) -> list[JournalEntry]:
    entries = JournalEntry.objects.filter(account=account)
    if filters.month:
        year, month = (int(part) for part in filters.month.split("-"))
        entries = entries.filter(date__year=year, date__month=month)
    if filters.kind in DECISIONS:
        entries = entries.filter(kind=filters.kind)
    elif filters.kind:
        entries = entries.filter(kind=TRADE, action=filters.kind)
    rows = list(entries)
    if filters.tag:
        # Tags are a short space-separated column, so the last filter runs in Python: a personal
        # journal is hundreds of lines, not millions.
        rows = [entry for entry in rows if filters.tag in entry.tag_list()]
    return rows


@dataclass(frozen=True, slots=True)
class Line:
    """One entry as the logbook shows it: where it came from, and whether it can be edited."""

    entry: JournalEntry
    order_id: str
    month_closed: bool

    @property
    def source(self) -> str:
        return f"alpaca-paper:{self.order_id}" if self.order_id else "hand"

    @property
    def editable(self) -> bool:
        return not self.order_id and not self.month_closed


def lines_for(account: Account, entries: list[JournalEntry]) -> list[Line]:
    """Two queries for the whole page: the orders that wrote entries, and the closed months."""
    orders = dict(
        PaperOrder.objects.filter(account=account)
        .exclude(journal_entry=None)
        .values_list("journal_entry_id", "client_order_id")
    )
    closed = set(
        MonthlyReview.objects.filter(plan__account=account, closed_at__isnull=False).values_list(
            "month", flat=True
        )
    )
    return [
        Line(entry, orders.get(entry.pk, ""), month_of(entry.date) in closed) for entry in entries
    ]


@login_required
def logbook(request: HttpRequest, pk: int) -> HttpResponse:
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    filters = read_filters(request)
    every = JournalEntry.entries_for(account)
    context = {
        "account": account,
        "filters": filters,
        "lines": lines_for(account, filtered(account, filters)),
        "total": len(every),
        "months": sorted({month_of(entry.date) for entry in every}, reverse=True),
        "kinds": KINDS,
        "tags": sorted({tag for entry in every for tag in entry.tag_list()}),
    }
    return render(request, "methods/logbook.html", context)


def cell(text: str) -> str:
    return f"'{text}" if text.startswith(FORMULA_STARTS) else text


def plain(value: object) -> str:
    return "" if value is None else str(value)


@login_required
def logbook_csv(request: HttpRequest, pk: int) -> HttpResponse:
    """The journal as CSV, with the page's filters. UTF-8, a header row, one line per entry,
    numbers as plain decimals (no thousands separator, no currency sign), dates as YYYY-MM-DD.
    `no-store`, because the file is a personal journal and no cache should keep a copy."""
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    lines = lines_for(account, filtered(account, read_filters(request)))
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="logbook-account-{account.pk}.csv"'
    response["Cache-Control"] = "no-store"
    writer = csv.writer(response)
    writer.writerow(CSV_COLUMNS)
    for line in lines:
        entry = line.entry
        writer.writerow(
            [
                f"{entry.date:%Y-%m-%d}",
                entry.what.lower(),
                entry.symbol,
                plain(entry.amount),
                plain(entry.shares),
                entry.state,
                entry.tags,
                cell(entry.reason),
                cell(entry.note),
                line.source,
                "yes" if line.month_closed else "no",
            ]
        )
    return response


@login_required
def edit_entry(request: HttpRequest, pk: int, entry_pk: int) -> HttpResponse:
    """Edit one line written by hand, in a month that is open."""
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    entry = get_object_or_404(JournalEntry, pk=entry_pk, account=account)
    if PaperOrder.objects.filter(journal_entry=entry).exists():
        messages.error(
            request,
            "A paper order wrote this line; the nightly check keeps it in step with Alpaca, so "
            "it is not edited by hand.",
        )
        return redirect("logbook", pk=account.pk)
    closed = MonthlyReview.is_closed(account.pk, entry.date)
    form = JournalEntryForm(request.POST if request.method == "POST" else None, instance=entry)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        messages.success(request, f"Saved: {saved}.")
        return redirect("logbook", pk=account.pk)
    context = {"account": account, "entry": entry, "form": form, "closed": closed}
    return render(request, "methods/entry_edit.html", context)
```

Listing 12-14, Filename: `src/invest_witus_site/methods/logbook_urls.py`:

```python
"""The logbook's routes (chapter 12). `invest_witus_site/urls.py` mounts this file under
`accounts/<int:pk>/logbook/`, beside the method page rather than inside it: the logbook is the
account's journal, and it stays when a plan ends."""

from django.urls import path

from invest_witus_site.methods import logbook

urlpatterns = [
    path("", logbook.logbook, name="logbook"),
    path("export.csv", logbook.logbook_csv, name="logbook-csv"),
    path("<int:entry_pk>/edit/", logbook.edit_entry, name="logbook-edit"),
]
```

Listing 12-15, Filename: `src/invest_witus_site/urls.py`:

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
    # The method an account runs, its journal and the review, in three views (chapter 10); the
    # plan's change form and each month's review (chapter 12).
    path("accounts/<int:pk>/method/", include("invest_witus_site.methods.urls")),
    # The account's logbook: every journal line, filtered, edited and exported (chapter 12).
    path("accounts/<int:pk>/logbook/", include("invest_witus_site.methods.logbook_urls")),
    # The account linked to Alpaca paper: its positions, cash and orders, the Confirm step and
    # the order check (chapter 11). Owner, superuser and a linked account only.
    path("accounts/<int:pk>/paper/", include("invest_witus_site.paper.urls")),
    # The nightly price pull, called by Vercel's cron with the bearer secret (chapter 08).
    path("api/cron/", include("invest_witus_site.prices.urls")),
    path("", include("invest_witus_site.pages.urls")),
]
```

- **The filters never raise.** A month that is not `YYYY-MM`, a kind not in the list or a tag outside the tag
  rule is dropped, and the list widens.
- **`csv.writer` writes straight into the response,** which is file-like. The apostrophe guard runs on the two
  columns you type freely; OWASP notes that Excel may still evaluate a guarded cell after the file is saved and
  opened again (OWASP Foundation, n.d.), so treat an exported journal as data, not as a sheet to edit and keep.
- **`no-store`** asks every cache to keep no copy of a personal journal.

### 12.7 Place again

Listing 12-16, Filename: `src/invest_witus_site/paper/orders.py`:

```python
"""The monthly review's buys on a paper account: stage them from the plan, place them when the owner
confirms, and copy Alpaca's answers back into the journal.

Three jobs, in the order they happen:

1. `month_buys` stages this month's buys from the active plan: the plan's amount split across its
   symbols to the cent, each with its deterministic `client_order_id`, and the one reason, if any,
   that Confirm is not offered (outside the window, no practice budget, over the budget, a buy
   already logged by hand, a skip logged for the month, more than one symbol). Chapter 12: when
   the month's order ended with nothing filled, the buy is staged again as a new attempt with its
   own id, and the button reads "Place again".
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
from invest_witus_site.methods.models import SKIP, JournalEntry, MethodPlan
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
    already, so its money is spent the moment it is placed. Chapter 12: since the plan's first
    version started, so a change of amount does not reset what was spent."""
    buys = JournalEntry.objects.filter(
        account=plan.account, action="buy", date__gte=plan.chain_start()
    ).values_list("amount", flat=True)
    return sum((amount for amount in buys if amount is not None), ZERO)


@dataclass(frozen=True, slots=True)
class StagedBuy:
    """One symbol's buy this month. `order` is the row for this `client_order_id`, if any;
    `previous` is the attempt before it, set only when that one ended with nothing filled."""

    symbol: str
    notional: Decimal
    client_order_id: str
    order: PaperOrder | None
    attempt: int = 1
    previous: PaperOrder | None = None

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

    @property
    def placing_again(self) -> bool:
        """The button says "Place again" when what it places replaces an unfilled order."""
        return any(buy.previous is not None for buy in self.to_place)


def staged(plan: MethodPlan, month: str, symbol: str, notional: Decimal) -> StagedBuy:
    """The buy for one symbol: the newest attempt's row, or, when that attempt ended with nothing
    filled, the next attempt with its own id. The attempt number comes from the rows, so two
    clicks on "Place again" compute the same id and the unique column keeps it to one order."""
    attempts = [order for order in PaperOrder.for_month(plan, month) if order.symbol == symbol]
    latest = attempts[-1] if attempts else None
    account_pk = plan.account.pk
    if latest is not None and latest.ended_unfilled:
        attempt = latest.attempt + 1
        cid = client_order_id(account_pk, plan.pk, month, symbol, attempt)
        return StagedBuy(symbol, notional, cid, None, attempt, previous=latest)
    attempt = latest.attempt if latest is not None else 1
    cid = client_order_id(account_pk, plan.pk, month, symbol, attempt)
    return StagedBuy(symbol, notional, cid, latest, attempt)


def month_buys(plan: MethodPlan, day: date) -> MonthBuys:
    month = month_of(day)
    parts = split_amount(plan.amount, plan.symbol_list())
    buys = [staged(plan, month, symbol, notional) for symbol, notional in parts]
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
    if skip_logged(plan, day):
        return f"You logged a skip for {month_of(day)}, with its reason: nothing is placed."
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


def skip_logged(plan: MethodPlan, day: date) -> bool:
    """A skip this month in the journal: the owner decided not to buy, and said why."""
    return JournalEntry.objects.filter(
        account=plan.account, kind=SKIP, date__year=day.year, date__month=day.month
    ).exists()


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
    """Built by the method page for a linked account. One request to Alpaca, the clock. The
    buys come from the plan version in force today (chapter 12), which is not the active row
    while a change is scheduled for next month."""
    day = today()
    stage = month_buys(plan.in_force(day), day)
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
    server, whatever the page showed: a stale tab cannot buy outside the window or the budget.
    The plan is the version in force on `day`."""
    plan = plan.in_force(day)
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
                "attempt": buy.attempt,
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

`staged()` is the new piece: the newest attempt's row for the symbol, or, when that attempt ended with nothing
filled, a new attempt with the `-r` id and the old row in `previous`. `confirm` and `paper_section` take the
version in force on the day, and `practice_spent` counts from the chain's start.

Listing 12-17, Filename: `src/invest_witus_site/paper/templates/paper/_month_buys.html`:

```html
{% load holdings_extras %}
{# This month's buys (chapter 11), on the method page of an account linked to Alpaca paper. Included by #}
{# methods/method_page.html with `account` and `paper` (a PaperSection: the staged buys, the clock, an error). #}
<section class="card" aria-labelledby="buys-heading">
  <h2 id="buys-heading">This month's buys</h2>
  <p class="band">Alpaca paper ({{ paper.host }}). Paper money. Live trading needs the checklist in a later chapter and separate keys.</p>
  <ul>
    {% for buy in paper.stage.buys %}
    <li>Buy {{ buy.notional|plain_number }} of {{ buy.symbol }}{% if buy.placed %}: placed, {{ buy.order.status }}{% elif buy.order.message %}: not placed. {{ buy.order.message }}{% elif buy.previous %}: the last order ended with nothing filled ({{ buy.previous.status }}){% endif %}</li>
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
    <button type="submit">{% if paper.stage.placing_again %}Place again{% else %}Confirm{% endif %}{% if not paper.clock.is_open %}: queue for the open{% endif %}</button>
  </form>
  {% if paper.stage.placing_again %}<p class="small muted">A new order with a new id ending in "-r{{ paper.stage.to_place.0.attempt }}". The order that ended unfilled stays on the paper page.</p>{% endif %}
  <p class="small muted">One market order per symbol for the dollar amount, good for the day, on Alpaca's paper account. Each order goes in the journal at once; the nightly check fills in the shares.</p>
  {% else %}
  <p>This month's buys are placed. The nightly check copies the fills into the journal. <a href="{% url 'paper-account' account.pk %}">See the orders</a>.</p>
  {% endif %}
</section>
```

### 12.8 The pages

The method page gains one line under the switch, the same in every view:

Listing 12-18, Filename: `src/invest_witus_site/methods/templates/methods/method_page.html`:

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
  {# Chapter 12: the logbook and the plan's change form, the same two links in every view. #}
  <p class="small"><a href="{% url 'logbook' account.pk %}">Open the logbook</a>: every entry, with filters and a CSV export.{% if plan %} <a href="{% url 'method-change' account.pk %}">Change or end this plan</a>, with a reason.{% endif %}</p>
  {# Chapter 11: on an account linked to Alpaca paper, this month's buys and the Confirm button. #}
  {% if paper %}{% include "paper/_month_buys.html" %}{% endif %}
  {# The same context, one of three arrangements (chapter 10). The view's letter is the research's. #}
  {% include view_template %}
  <p><a href="{% url 'account-detail' account.pk %}">Back to the account</a></p>
</section>
{% endblock %}
```

View A offers "Close last month", and shows the versions under the plan:

Listing 12-19, Filename: `src/invest_witus_site/methods/templates/methods/_view_a.html`:

```html
{% load holdings_extras %}
{# View A, "The Plan and the Logbook" (research 01, direction A): the everyday home. One next action, #}
{# the on-plan status with its fixes, the plan's rules each with its lesson, and the logbook. #}
{% if plan %}
<section class="card" aria-labelledby="next-heading">
  <h2 id="next-heading">Next</h2>
  <p>{% if review.next_action.status == "due" %}Due now: buy {{ review.next_action.amount|plain_number }} of {{ review.next_action.symbols|join:", " }} by {{ review.next_action.closes|date:"Y-m-d" }}, the end of this month's window.{% else %}Buy {{ review.next_action.amount|plain_number }} of {{ review.next_action.symbols|join:", " }} between {{ review.next_action.opens|date:"Y-m-d" }} and {{ review.next_action.closes|date:"Y-m-d" }}. Nothing to do before then.{% endif %}</p>
</section>

{% if review_to_close %}{% include "methods/_close_month.html" %}{% endif %}

<section aria-labelledby="status-heading">
  <h2 id="status-heading">{% if review.on_plan %}You are on plan{% else %}Off plan: {{ review.findings|length }} thing{{ review.findings|length|pluralize }} to look at{% endif %}</h2>
  <p>{{ review.months_done }} of {{ review.months_due }} scheduled buy{{ review.months_due|pluralize }} made through {{ review.through|date:"Y-m-d" }}. A finding is a place the journal left the method; the lesson beside it says why the rule exists.</p>
  {% include "methods/_findings.html" %}
</section>

<section aria-labelledby="plan-heading">
  <h2 id="plan-heading">My plan</h2>
  <p>{{ review.method.summary }}</p>
  <p>{{ plan.amount|plain_number }} into {{ plan.symbols }} within the first {{ plan.buy_window_days }} day{{ plan.buy_window_days|pluralize }} of each month, since {{ plan.started_on|date:"Y-m-d" }}.</p>
  {% include "methods/_versions.html" %}
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

View B lists every month's review state. It is a list, not a fifth table: chapter 10's test reads view B's four
tables by position.

Listing 12-20, Filename: `src/invest_witus_site/methods/templates/methods/_view_b.html`:

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
  <dt>Months</dt><dd>{{ review.months_done }} done of {{ review.months_due }} due; {{ review.months_followed }} followed every rule</dd>
  <dt>Findings</dt><dd>{{ review.findings|length }}{% if review.explained_count %}, {{ review.explained_count }} explained by a skip{% endif %}</dd>
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
      <td>{{ finding.message }}{% if finding.explained %} <span class="explained">Explained by a skip: {{ finding.explanation }}</span>{% endif %}</td>
      <td>{% if finding.rule.lesson_url %}<a href="{{ finding.rule.lesson_url }}">{{ finding.rule.id }}</a>{% else %}<span class="muted">lesson coming</span>{% endif %}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% else %}
<p class="on-plan">No findings through {{ review.through|date:"Y-m-d" }}: every rule passed.</p>
{% endif %}

<h2>Monthly reviews</h2>
{% include "methods/_reviews.html" %}
{% include "methods/_versions.html" %}

<h2>Journal</h2>
{% include "methods/_entries.html" with caption="Every trade logged for this account, in date order" %}
<h3>Log an entry</h3>
{% include "methods/_log_form.html" %}
{% else %}
<p>No method runs on this account, so there is nothing to supervise. <a href="?view=c">Start one in the Lesson Lab</a>.</p>
{% endif %}
```

Listing 12-21, Filename: `src/invest_witus_site/methods/templates/methods/_view_c.html`:

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
<p class="small muted">This account runs one method at a time. To change its numbers or end it, use the change form above; each change is kept as a dated version with its reason.</p>
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

The shared pieces: the journal table (the word for each kind, and the reason, state and tags in the note
column), the findings (with a skip's reason), and the log form's closing line.

Listing 12-22, Filename: `src/invest_witus_site/methods/templates/methods/_entries.html`:

```html
{% load holdings_extras %}
{# The journal as a table (chapter 10). Included with `entries`; the caption is the including view's. #}
{# Chapter 12: the Action column says Buy, Sell, Hold or Skip, and the Note column adds the reason, the #}
{# state and the tags when an entry has them. The full logbook, with every column, is its own page. #}
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
      <td>{{ entry.what }}</td>
      <td>{{ entry.symbol }}</td>
      <td class="num">{% if entry.amount is not None %}{{ entry.amount|plain_number }}{% endif %}</td>
      <td class="num">{% if entry.shares is not None %}{{ entry.shares|plain_number }}{% elif entry.is_trade %}<span class="muted">not recorded</span>{% endif %}</td>
      <td>{{ entry.note }}{% if entry.reason %} <span class="small">Why: {{ entry.reason }}</span>{% endif %}{% if entry.state %} <span class="small muted">{{ entry.get_state_display }}</span>{% endif %}{% if entry.tags %} <span class="small muted">#{{ entry.tag_list|join:" #" }}</span>{% endif %}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% else %}
<p>Nothing logged yet.</p>
{% endif %}
```

Listing 12-23, Filename: `src/invest_witus_site/methods/templates/methods/_findings.html`:

```html
{# The review's findings as a list (chapter 10). "No findings" is a sentence, never an empty box. #}
{# Chapter 12: a month with no buy and a skip in the journal is still a finding; the skip's reason is shown beside it. #}
{% if review.findings %}
<ul class="findings">
  {% for finding in review.findings %}
  <li><strong>{{ finding.month }}</strong> {{ finding.message }}{% if finding.explained %} <span class="explained">Explained by a skip: {{ finding.explanation }}</span>{% endif %} <span class="small">Rule: {{ finding.rule.text }} {% if finding.rule.lesson_url %}<a href="{{ finding.rule.lesson_url }}">Read the lesson</a>{% else %}<span class="muted">lesson coming</span>{% endif %}</span></li>
  {% endfor %}
</ul>
{% else %}
<p class="on-plan">You followed every rule through {{ review.through|date:"Y-m-d" }}. Nothing to look at.</p>
{% endif %}
```

Listing 12-24, Filename: `src/invest_witus_site/methods/templates/methods/_log_form.html`:

```html
{# The one-row add form (chapter 10): a buy or a sell, by hand, as the confirmation shows it. #}
{# Chapter 12: a hold or a skip too, each with its reason, and the state and tags any entry may carry. #}
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
<p class="small muted">Logging records what you did; it places no order. The review reads the journal, not the broker. A trade needs Action, Symbol and Amount; a hold or a skip needs only the day and why, and a skip explains a month with no buy.</p>
```

Four new partials:

Listing 12-25, Filename: `src/invest_witus_site/methods/templates/methods/_close_month.html`:

```html
{# View A's "Close last month" (chapter 12): the oldest month whose review is still open. The review page #}
{# has the month's findings and entries and the three questions; closing it makes its entries read-only. #}
<section class="card" aria-labelledby="close-heading">
  <h2 id="close-heading">Close last month</h2>
  <p>{{ review_to_close.month }}'s window closed on {{ review_to_close.opened_on|date:"Y-m-d" }}. Write its review in three short answers: what you did, what the rules said, and what you'll do next month.{% if open_reviews > 1 %} {{ open_reviews|add:"-1" }} more month{{ open_reviews|add:"-1"|pluralize }} after it {{ open_reviews|add:"-1"|pluralize:"is,are" }} open too.{% endif %}</p>
  <p><a href="{% url 'method-review' account.pk review_to_close.month %}">Review {{ review_to_close.month }}</a></p>
</section>
```

Listing 12-26, Filename: `src/invest_witus_site/methods/templates/methods/_reviews.html`:

```html
{# Every month's review state (chapter 12), for view B: a list, oldest first, each linking to its page. #}
{% if month_reviews %}
<ul class="reviews">
  {% for item in month_reviews %}
  <li><a href="{% url 'method-review' account.pk item.month %}">{{ item.month }}</a>: {% if item.closed %}closed {{ item.closed_at|date:"Y-m-d" }}{% else %}open since {{ item.opened_on|date:"Y-m-d" }}{% endif %} <span class="small muted">(version {{ item.plan.version }})</span></li>
  {% endfor %}
</ul>
{% else %}
<p>No month's window has closed yet, so there is nothing to review.</p>
{% endif %}
```

Listing 12-27, Filename: `src/invest_witus_site/methods/templates/methods/_versions.html`:

```html
{# The plan's versions (chapter 12), shown once the plan has changed: each with its numbers, its dates and its reason. #}
{% load holdings_extras %}
{% if review.spans|length > 1 %}
<h3>Versions</h3>
<ol class="versions">
  {% for span in review.spans %}
  <li>Version {{ span.plan.version }}: {{ span.plan.amount|plain_number }} into {{ span.plan.symbols }}, days 1 to {{ span.plan.buy_window_days }}, from {{ span.first|date:"Y-m-d" }}{% if span.last %} to {{ span.last|date:"Y-m-d" }}{% endif %}.{% if span.plan.change_reason %} <span class="small">Why: {{ span.plan.change_reason }}</span>{% endif %}</li>
  {% endfor %}
</ol>
{% endif %}
```

Listing 12-28, Filename: `src/invest_witus_site/methods/templates/methods/_form_fields.html`:

```html
{# A form's fields with their labels, errors and help (chapter 12), shared by the change, review and edit pages. #}
{# A group of radio buttons gets a fieldset and a legend (Django's `use_fieldset`), so a screen reader names the group. #}
{{ form.non_field_errors }}
{% for field in form %}
{% if field.use_fieldset %}
<fieldset class="field">
  <legend>{{ field.label }}</legend>
  {{ field }}
  {{ field.errors }}
  {% if field.help_text %}<span class="helptext">{{ field.help_text }}</span>{% endif %}
</fieldset>
{% else %}
<div class="field">
  <label for="{{ field.id_for_label }}">{{ field.label }}</label>
  {{ field }}
  {{ field.errors }}
  {% if field.help_text %}<span class="helptext">{{ field.help_text }}</span>{% endif %}
</div>
{% endif %}
{% endfor %}
```

`field.use_fieldset` is Django's flag for a widget that is a group, such as radio buttons; the group gets a
`<fieldset>` and a `<legend>`, so a screen reader names it (Django Software Foundation, n.d.-a).

And four new pages:

Listing 12-29, Filename: `src/invest_witus_site/methods/templates/methods/plan_change.html`:

```html
{% extends "pages/base.html" %}
{% load holdings_extras %}
{% block title %}Change the plan: {{ account.name }}: Invest.WitUS{% endblock %}
{% block content %}
<section class="container" aria-labelledby="change-heading">
  <p class="eyebrow">{{ account.name }} <span class="muted">({{ account.broker }})</span></p>
  <h1 id="change-heading">Change or end the plan</h1>
  <p>Version {{ plan.version }}: {{ plan.amount|plain_number }} into {{ plan.symbols }} within the first {{ plan.buy_window_days }} day{{ plan.buy_window_days|pluralize }} of each month, from {{ plan.started_on|date:"Y-m-d" }}.</p>
  <p>A change makes a new version that starts on the first day of a month. The months before it stay judged by the numbers that were in force then, and this version stays in the history with its dates. Ending the plan stops the reviews from today; its months, reviews and journal stay. Either way, write why: the reason is kept with the date.</p>
  <form method="post" action="{% url 'method-change' account.pk %}" class="method-form" novalidate>
    {% csrf_token %}
    {% include "methods/_form_fields.html" %}
    <button type="submit">Save the change</button>
  </form>
  <p class="small muted">This changes your own numbers. The app recommends no amount and no symbol; the method's rules stay the same.</p>
  <p><a href="{% url 'method-page' account.pk %}">Back to the method</a></p>
</section>
{% endblock %}
```

Listing 12-30, Filename: `src/invest_witus_site/methods/templates/methods/review_month.html`:

```html
{% extends "pages/base.html" %}
{% load holdings_extras %}
{% block title %}Review of {{ review.month }}: {{ account.name }}: Invest.WitUS{% endblock %}
{% block content %}
<section class="container" aria-labelledby="review-heading">
  <p class="eyebrow">{{ account.name }} <span class="muted">({{ account.broker }})</span></p>
  <h1 id="review-heading">Review of {{ review.month }}</h1>
  <p class="band">{% if review.closed %}Closed {{ review.closed_at|date:"Y-m-d" }}. This month's entries are read-only until the review is reopened with a reason.{% else %}Open since {{ review.opened_on|date:"Y-m-d" }}, the day the month's window closed.{% endif %}</p>
  <p>Judged by version {{ version.version }} of the plan: {{ version.amount|plain_number }} into {{ version.symbols }} within the first {{ version.buy_window_days }} day{{ version.buy_window_days|pluralize }} of the month.{% if row %} The month is <strong>{{ row.status }}</strong>: {{ row.buys }} buy{{ row.buys|pluralize }}, {{ row.amount|plain_number }} in all.{% endif %}</p>

  <h2>What the review found</h2>
  {% if findings %}
  <ul class="findings">
    {% for finding in findings %}
    <li>{{ finding.message }}{% if finding.explained %} <span class="explained">Explained by a skip: {{ finding.explanation }}</span>{% endif %} <span class="small">Rule: {{ finding.rule.text }}</span></li>
    {% endfor %}
  </ul>
  {% else %}
  <p class="on-plan">Every rule passed in {{ review.month }}.</p>
  {% endif %}

  <h2>The month's entries</h2>
  {% include "methods/_entries.html" with caption="Every entry dated in this month" %}

  {% if review.closed %}
  <h2>The written review</h2>
  <dl class="status">
    <dt>What I did</dt><dd>{{ review.did|linebreaksbr }}</dd>
    <dt>What the rules said</dt><dd>{{ review.rules_said|linebreaksbr }}</dd>
    <dt>What I'll do next month</dt><dd>{{ review.next_month|linebreaksbr }}</dd>
  </dl>
  <h2>Reopen the month</h2>
  <form method="post" action="{% url 'method-review-reopen' account.pk review.month %}" class="method-form" novalidate>
    {% csrf_token %}
    {% include "methods/_form_fields.html" with form=reopen_form %}
    <button type="submit">Reopen {{ review.month }}</button>
  </form>
  {% else %}
  <h2>Close the month</h2>
  <p>Three short answers. Closing makes this month's entries read-only; you can reopen it later with a reason.</p>
  <form method="post" action="{% url 'method-review-close' account.pk review.month %}" class="method-form" novalidate>
    {% csrf_token %}
    {% include "methods/_form_fields.html" with form=close_form %}
    <button type="submit">Close {{ review.month }}</button>
  </form>
  {% endif %}

  {% if events %}
  <h2>History</h2>
  <ol class="events">
    {% for event in events %}
    <li>{{ event.at|date:"Y-m-d H:i" }}: {{ event.get_action_display }}{% if event.by %} by {{ event.by.get_username }}{% endif %}. <span class="small">{{ event.text|linebreaksbr }}</span></li>
    {% endfor %}
  </ol>
  {% endif %}
  <p><a href="{% url 'method-page' account.pk %}">Back to the method</a> · <a href="{% url 'logbook' account.pk %}?month={{ review.month }}">This month in the logbook</a></p>
</section>
{% endblock %}
```

Listing 12-31, Filename: `src/invest_witus_site/methods/templates/methods/logbook.html`:

```html
{% extends "pages/base.html" %}
{% load holdings_extras %}
{% block title %}Logbook: {{ account.name }}: Invest.WitUS{% endblock %}
{% block content %}
<section class="container" aria-labelledby="logbook-page-heading">
  <p class="eyebrow">{{ account.name }} <span class="muted">({{ account.broker }})</span></p>
  <h1 id="logbook-page-heading">Logbook</h1>
  <p>Every entry on this account: trades, holds and skips, with the reason, the state and the tags each carries. What you did, never what it is worth. Information, not advice.</p>
  <form method="get" class="filters" aria-label="Filter the logbook">
    <div class="field">
      <label for="filter-month">Month</label>
      <select id="filter-month" name="month">
        <option value="">Every month</option>
        {% for month in months %}<option value="{{ month }}"{% if month == filters.month %} selected{% endif %}>{{ month }}</option>{% endfor %}
      </select>
    </div>
    <div class="field">
      <label for="filter-kind">Kind</label>
      <select id="filter-kind" name="kind">
        <option value="">Every kind</option>
        {% for kind in kinds %}<option value="{{ kind }}"{% if kind == filters.kind %} selected{% endif %}>{{ kind|capfirst }}</option>{% endfor %}
      </select>
    </div>
    <div class="field">
      <label for="filter-tag">Tag</label>
      <select id="filter-tag" name="tag">
        <option value="">Every tag</option>
        {% for tag in tags %}<option value="{{ tag }}"{% if tag == filters.tag %} selected{% endif %}>{{ tag }}</option>{% endfor %}
      </select>
    </div>
    <button type="submit">Show</button>
  </form>
  <p class="small">{{ lines|length }} of {{ total }} entr{{ total|pluralize:"y,ies" }}. <a href="{% url 'logbook-csv' account.pk %}{{ filters.query }}">Download these as CSV</a>{% if filters.query %} · <a href="{% url 'logbook' account.pk %}">Clear the filters</a>{% endif %}</p>
  {% if lines %}
  <table class="holdings">
    <caption class="sr-only">The account's journal entries, filtered as chosen above, in date order</caption>
    <thead>
      <tr>
        <th scope="col">Day</th>
        <th scope="col">Kind</th>
        <th scope="col">Symbol</th>
        <th scope="col" class="num">Amount</th>
        <th scope="col" class="num">Shares</th>
        <th scope="col">State</th>
        <th scope="col">Tags</th>
        <th scope="col">Why</th>
        <th scope="col">Note</th>
        <th scope="col">Source</th>
      </tr>
    </thead>
    <tbody>
      {% for line in lines %}
      <tr>
        <th scope="row">{{ line.entry.date|date:"Y-m-d" }}</th>
        <td>{{ line.entry.what }}</td>
        <td>{{ line.entry.symbol }}</td>
        <td class="num">{% if line.entry.amount is not None %}{{ line.entry.amount|plain_number }}{% endif %}</td>
        <td class="num">{% if line.entry.shares is not None %}{{ line.entry.shares|plain_number }}{% endif %}</td>
        <td>{{ line.entry.get_state_display }}</td>
        <td>{{ line.entry.tags }}</td>
        <td>{{ line.entry.reason }}</td>
        <td>{{ line.entry.note }}</td>
        <td>{% if line.order_id %}Alpaca paper{% elif line.month_closed %}By hand, month closed{% else %}By hand <a href="{% url 'logbook-edit' account.pk line.entry.pk %}">Edit<span class="sr-only"> the entry of {{ line.entry.date|date:"Y-m-d" }}</span></a>{% endif %}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p>No entry matches.</p>
  {% endif %}
  <p class="small muted">To add an entry, use the log form on the method page. A line a paper order wrote is kept in step with Alpaca by the nightly check and is not edited by hand; a line in a closed month is read-only until its review is reopened.</p>
  <p><a href="{% url 'method-page' account.pk %}">Back to the method</a> · <a href="{% url 'account-detail' account.pk %}">Back to the account</a></p>
</section>
{% endblock %}
```

Listing 12-32, Filename: `src/invest_witus_site/methods/templates/methods/entry_edit.html`:

```html
{% extends "pages/base.html" %}
{% block title %}Edit an entry: {{ account.name }}: Invest.WitUS{% endblock %}
{% block content %}
<section class="container" aria-labelledby="edit-heading">
  <p class="eyebrow">{{ account.name }} <span class="muted">({{ account.broker }})</span></p>
  <h1 id="edit-heading">Edit the entry of {{ entry.date|date:"Y-m-d" }}</h1>
  {% if closed %}
  <p class="band">{{ entry.date|date:"Y-m" }} is closed, so its entries are read-only. Reopen its review, with a reason, to change this one.</p>
  <p><a href="{% url 'method-review' account.pk entry.date|date:'Y-m' %}">The review of {{ entry.date|date:"Y-m" }}</a></p>
  {% else %}
  <form method="post" action="{% url 'logbook-edit' account.pk entry.pk %}" class="method-form" novalidate>
    {% csrf_token %}
    {% include "methods/_form_fields.html" %}
    <button type="submit">Save the entry</button>
  </form>
  {% endif %}
  <p><a href="{% url 'logbook' account.pk %}">Back to the logbook</a></p>
</section>
{% endblock %}
```

The stylesheet gains nine rules at the end, for text boxes, radio buttons, the filter row, the fieldset and the
three lists:

Listing 12-33, Filename: `src/invest_witus_site/pages/static/pages/site.css`:

```css
/* Invest.WitUS: one hand-written stylesheet, no build step.
   Dark surface because the WitUS logo (static/brand/witus/, from gemini/witus/public/brand/04-orbit-type/)
   is drawn for dark backgrounds. Accent: sky, this app's color in the ecosystem registry. */

:root {
  --bg: #020617;
  --surface: #0f172a;
  --border: #1e293b;
  --text: #f1f5f9;
  --muted: #94a3b8;
  --accent: #38bdf8;
  --accent-ink: #082f49;
  --danger: #fda4af;
  --max: 64rem;
  --gutter: 1rem;
}

* { box-sizing: border-box; }

html { color-scheme: dark; }

body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 16px/1.6 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}

a { color: var(--accent); }
a:hover { text-decoration-thickness: 2px; }

a:focus-visible, button:focus-visible, input:focus-visible, [tabindex="-1"]:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-radius: 2px;
}

h1, h2, h3 { line-height: 1.2; }
h1 { font-size: clamp(1.6rem, 4vw, 2.4rem); }
h2 { font-size: 1.35rem; margin-top: 2.5rem; }
h3 { font-size: 1.1rem; }

.container { max-width: var(--max); margin: 0 auto; padding: 0 var(--gutter); }
.narrow { max-width: 42rem; }
.muted { color: var(--muted); }
.small { font-size: 0.875rem; }
.eyebrow { font-size: 0.75rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent); font-weight: 600; }
.lead { font-size: 1.125rem; }
.plain { list-style: none; margin: 0; padding: 0; }
.plain li { margin: 0.25rem 0; }

.sr-only {
  position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
  overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;
}

.skip-link { position: absolute; left: -999px; top: 0.5rem; background: var(--accent); color: var(--accent-ink); padding: 0.5rem 1rem; z-index: 10; }
.skip-link:focus { left: 0.5rem; }

/* Header */
.site-header { border-bottom: 1px solid var(--border); background: var(--surface); }
.header-row { display: flex; align-items: center; justify-content: space-between; gap: 1rem; min-height: 3.5rem; flex-wrap: wrap; }
.brand { display: inline-flex; align-items: center; gap: 0.5rem; color: var(--text); font-weight: 800; text-decoration: none; }
.brand img { display: block; }
.site-header nav { display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }
.site-header nav a { min-height: 2.75rem; display: inline-flex; align-items: center; }
/* Signed in (chapter 07): the name and the Sign out form sit in the row like the links. */
.site-header nav form { margin: 0; }
.site-header .who { max-width: 14rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.site-footer form { margin: 0.25rem 0; }
.site-footer button[type="submit"] { min-height: 2.25rem; padding: 0 0.75rem; font-size: 0.875rem; }
.signed-in { margin: 0.5rem 0 0; }

.button {
  display: inline-flex; align-items: center; min-height: 2.75rem; padding: 0 1rem;
  background: var(--accent); color: var(--accent-ink); font-weight: 700; text-decoration: none; border-radius: 0.375rem;
}
.button:hover { background: #7dd3fc; }

main { padding: 1rem 0 3rem; }
.hero { padding-top: 2rem; }
.actions { display: flex; gap: 1rem; align-items: center; flex-wrap: wrap; }
.steps li { margin-bottom: 0.75rem; }

.callout { border: 1px solid var(--accent); background: rgba(56, 189, 248, 0.08); border-radius: 0.5rem; padding: 1rem 1.25rem; }
.callout h2 { margin-top: 0; }

/* Forms */
.waitlist-form { max-width: 28rem; }
.field { margin-bottom: 1rem; }
.field label { display: block; font-weight: 600; margin-bottom: 0.25rem; }
.field input { width: 100%; min-height: 2.75rem; padding: 0.5rem 0.75rem; background: var(--surface); color: var(--text); border: 1px solid var(--border); border-radius: 0.375rem; font: inherit; }
.errorlist { list-style: none; padding: 0; margin: 0.25rem 0 0; color: var(--danger); font-size: 0.875rem; }
button[type="submit"] { min-height: 2.75rem; padding: 0 1.25rem; background: var(--accent); color: var(--accent-ink); font: inherit; font-weight: 700; border: 0; border-radius: 0.375rem; cursor: pointer; }
.honeypot { position: absolute; left: -10000px; top: auto; width: 1px; height: 1px; overflow: hidden; }

/* Markdown pages */
.prose { max-width: 48rem; }
.prose blockquote { margin: 1.5rem 0; padding: 1rem 1.25rem; border-left: 4px solid var(--accent); background: rgba(56, 189, 248, 0.08); border-radius: 0 0.5rem 0.5rem 0; }
.prose a { overflow-wrap: anywhere; }

/* Footer */
.site-footer { border-top: 1px solid var(--border); margin-top: 3rem; padding: 2.5rem 0; background: var(--surface); font-size: 0.9375rem; }
.footer-brand { text-align: center; margin-bottom: 2rem; }
.footer-brand img { display: inline-block; }
.footer-name { font-weight: 800; margin: 0.5rem 0 0; }
.footer-brand p { margin: 0.25rem 0; }
.notice { max-width: 40rem; margin: 0.75rem auto 0; }
.footer-heading { font-weight: 600; margin: 0 0 0.5rem; }
.footer-grid { display: grid; grid-template-columns: 1fr; gap: 2rem; }
@media (min-width: 40rem) { .footer-grid { grid-template-columns: repeat(3, 1fr); } }
.footer-grid a, .rise-links a { display: inline-flex; align-items: center; min-height: 1.75rem; }
.footer-grid .footer-heading + ul + .footer-heading { margin-top: 1.25rem; }
.copyright { margin-top: 2rem; padding-top: 1.5rem; border-top: 1px solid var(--border); text-align: center; }

.rise { border: 1px solid rgba(56, 189, 248, 0.3); background: rgba(56, 189, 248, 0.06); border-radius: 0.5rem; padding: 1.25rem; margin-bottom: 2rem; }
.rise h2 { font-size: 1rem; margin: 0.25rem 0 0; }
.rise-header p { margin: 0; }
.rise-grid { display: grid; grid-template-columns: 1fr; gap: 1rem; margin-top: 1rem; }
@media (min-width: 40rem) { .rise-grid { grid-template-columns: 1fr 1fr; } }
.rise address { font-style: normal; }
.rise-links { display: flex; flex-wrap: wrap; gap: 0.5rem 0.75rem; align-items: center; }
.rise-quote { margin: 1rem 0 0; padding-left: 0.75rem; border-left: 2px solid var(--accent); font-style: italic; }
.rise-quote .attribution { display: block; font-style: normal; margin-top: 0.25rem; }
.disclaimer { font-size: 0.75rem; margin: 1rem 0 0; }

/* The owner's account page (chapter 08): one table, numbers right-aligned in tabular figures. */
.holdings { width: 100%; border-collapse: collapse; margin: 1rem 0; }
.holdings th, .holdings td { padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; }
.holdings .num { text-align: right; font-variant-numeric: tabular-nums; }
.holdings tfoot th, .holdings tfoot td { border-bottom: 0; font-weight: 700; }
.stale { color: var(--danger); font-size: 0.75rem; letter-spacing: 0.08em; text-transform: uppercase; }

/* FAQ: each question is a <details>; the question line is the handle. */
.faq-item { border-top: 1px solid var(--line, #2a2f3a); padding: 0.4rem 0; }
.faq-item > summary { cursor: pointer; font-weight: 600; font-size: 1.05rem; padding: 0.5rem 0; list-style-position: outside; }
.faq-item > summary:hover { text-decoration: underline; }
.faq-item[open] > summary { margin-bottom: 0.25rem; }
/* The watch list (chapter 09): the same table, a short form under it, and a remove button that reads as a link. */
.watch-form { max-width: 28rem; }
.holdings form { margin: 0; }
.holdings .link-button { min-height: 2.25rem; padding: 0 0.5rem; background: transparent; color: var(--accent); font-weight: 600; text-decoration: underline; }
.holdings .link-button:hover { text-decoration-thickness: 2px; }

/* One-time notices after a form was handled (Django's messages, printed by base.html). */
.messages { list-style: none; padding: 0; margin: 1rem 0 0; }
.message { padding: 0.5rem 0.75rem; margin: 0.5rem 0; border: 1px solid var(--border); border-radius: 0.375rem; background: var(--surface); }
.message.success { border-color: var(--accent); }
.message.error { border-color: var(--danger); }

/* The method page (chapter 10): the view switch, the environment band, the status list and the cards. */
.views-list { display: flex; flex-wrap: wrap; gap: 0.5rem 1rem; margin: 1rem 0; }
.views-list a { display: inline-flex; align-items: center; min-height: 2.75rem; padding: 0 0.75rem; border: 1px solid var(--border); border-radius: 0.375rem; text-decoration: none; }
.views-list a[aria-current="page"] { border-color: var(--accent); background: rgba(56, 189, 248, 0.12); font-weight: 700; }
.band { border: 1px dashed var(--muted); border-radius: 0.375rem; padding: 0.5rem 0.75rem; font-size: 0.875rem; }
.card { border: 1px solid var(--border); border-radius: 0.5rem; padding: 1rem 1.25rem; margin: 1.5rem 0; background: var(--surface); }
.card h2 { margin-top: 0; }
.status { display: grid; grid-template-columns: max-content 1fr; gap: 0.25rem 1rem; margin: 1rem 0; font-size: 0.9375rem; }
.status dt { color: var(--muted); }
.status dd { margin: 0; }
.rules li, .findings li { margin-bottom: 0.5rem; }
.method-form { max-width: 28rem; }
.method-form input, .method-form select { width: 100%; min-height: 2.75rem; padding: 0.5rem 0.75rem; background: var(--surface); color: var(--text); border: 1px solid var(--border); border-radius: 0.375rem; font: inherit; }
.helptext { display: block; font-size: 0.875rem; color: var(--muted); margin-top: 0.25rem; }
/* Chapter 12: the logbook's filters, text boxes and radio choices, the explained finding, the lists. */
.method-form textarea, .filters select { width: 100%; padding: 0.5rem 0.75rem; background: var(--surface); color: var(--text); border: 1px solid var(--border); border-radius: 0.375rem; font: inherit; }
.method-form input[type="radio"] { width: auto; min-height: auto; margin-right: 0.5rem; }
.filters { display: flex; flex-wrap: wrap; gap: 0 1rem; align-items: end; }
.filters .field { min-width: 10rem; }
.filters select { min-height: 2.75rem; }
.explained { font-style: italic; }
.reviews li, .versions li, .events li { margin-bottom: 0.375rem; }
fieldset.field { border: 0; padding: 0; margin: 0 0 1rem; }
fieldset.field legend { font-weight: 600; margin-bottom: 0.25rem; padding: 0; }
```

### 12.9 The admin

Listing 12-34, Filename: `src/invest_witus_site/methods/admin.py`:

```python
"""The plans, the journal and the monthly reviews in the admin. Chapter 12 moves ending and changing
a plan to its own form on the method page, so the plan's history columns are read-only here; a
journal line in a closed month cannot be saved (the model's `clean()`) or deleted (below); and the
reviews and their events are read-only, because the audit trail is only ever added to."""

from django.contrib import admin
from django.http import HttpRequest

from invest_witus_site.methods.models import (
    JournalEntry,
    MethodPlan,
    MonthlyReview,
    ReviewEvent,
)


@admin.register(MethodPlan)
class MethodPlanAdmin(admin.ModelAdmin[MethodPlan]):
    list_display = (
        "method_id",
        "account",
        "version",
        "amount",
        "symbols",
        "buy_window_days",
        "started_on",
        "ended_on",
        "practice_budget",
        "active",
    )
    list_editable = ("active",)
    list_filter = ("account", "active")
    readonly_fields = (
        "created_at",
        "version",
        "previous",
        "change_reason",
        "ended_on",
        "end_reason",
    )


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin[JournalEntry]):
    list_display = (
        "date",
        "account",
        "kind",
        "action",
        "symbol",
        "amount",
        "shares",
        "state",
        "tags",
        "note",
    )
    list_filter = ("account", "kind", "action", "state")
    date_hierarchy = "date"
    search_fields = ("symbol", "note", "reason", "tags")
    readonly_fields = ("created_at",)

    def has_delete_permission(self, request: HttpRequest, obj: JournalEntry | None = None) -> bool:
        if (
            obj is not None
            and obj.account_id is not None
            and MonthlyReview.is_closed(obj.account_id, obj.date)
        ):
            return False
        return super().has_delete_permission(request, obj)


class ReviewEventInline(admin.TabularInline[ReviewEvent, MonthlyReview]):
    model = ReviewEvent
    extra = 0
    can_delete = False
    readonly_fields = ("action", "text", "by", "at")

    def has_add_permission(self, request: HttpRequest, obj: MonthlyReview | None = None) -> bool:
        return False


@admin.register(MonthlyReview)
class MonthlyReviewAdmin(admin.ModelAdmin[MonthlyReview]):
    list_display = ("month", "plan", "opened_on", "closed_at")
    list_filter = ("plan__account",)
    inlines = [ReviewEventInline]

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: MonthlyReview | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: MonthlyReview | None = None) -> bool:
        return False
```

The plan's history columns are read-only, a closed month's line has no Delete, and the reviews have no Add, no
change and no Delete; their events show inline, read-only.

### 12.10 Green, and three months closed on your laptop

Listing 12-35, Terminal:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

```text
395 passed in 12.29s
All checks passed!
174 files already formatted
0 errors, 0 warnings, 0 informations
```

Twenty-nine new tests. Migrate the laptop database:

Listing 12-36, Terminal:

```sh
uv run --env-file .env python manage.py migrate
```

```text
Operations to perform:
  Apply all migrations: accounts, admin, auth, contenttypes, holdings, methods, pages, paper, prices, sessions, watchlist
Running migrations:
  Applying methods.0003_journal_kinds_plan_versions_and_reviews... OK
  Applying paper.0002_paperorder_attempt... OK
```

Your journal from chapters 10 and 11 has a buy on January 2 and a late buy on February 12, and March has nothing.
Log a skip for March, first without its reason, then with it, and read view B through March 31:

Listing 12-37, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -v 0 -c "
import re
from django.contrib.auth.models import User
from django.test import Client
from invest_witus_site.holdings.models import Account
from tests.test_ch10 import tables_in, text
u = User.objects.get(is_superuser=True); a = Account.objects.get(owner=u, name='Practice'); c = Client(); c.force_login(u)
skip = {'date': '2026-03-04', 'kind': 'skip', 'reason': 'Practice month: I read the lesson again instead.', 'state': 'unsure', 'tags': 'practice'}
for row in ({**skip, 'reason': ''}, skip):
    page = text(c.post(f'/accounts/{a.pk}/method/log/', row, follow=True))
    print(re.findall(r'class=\"message \w+\">([^<]+)<', page) or re.findall(r'class=\"errorlist\"[^>]*><li>([^<]+)<', page))
checks, months, *rest = tables_in(text(c.get(f'/accounts/{a.pk}/method/?view=b&through=2026-03-31')))
for row in checks[:2] + months: print(row)
"
```

```text
['A skip needs a reason: write why, in a sentence.']
['Logged: 2026-03-04 skip.']
('Rule', 'Status', 'Evidence', 'Lesson')
('Buy once in every month of the plan.', 'explained', '1 finding: 2026-03 (1 explained)', 'lesson coming')
('Month', 'Window closes', 'Status', 'Buys', 'Amount', 'Shares', 'Rules flagged')
('2026-01', '2026-01-07', 'done', '1', '100.00', '0.50', 'none')
('2026-02', '2026-02-07', 'done', '1', '100.00', 'not recorded', 'buy-in-window')
('2026-03', '2026-03-07', 'skipped', '0', '0.00', '', 'one-buy-each-month')
```

March is still flagged under its rule, and the rule reads "explained". Now close the three months with the
answer the page drafts for "What the rules said", try to log a buy into closed March, and reopen it:

Listing 12-38, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -v 0 -c "
import re
from django.contrib.auth.models import User
from django.test import Client
from invest_witus_site.holdings.models import Account
from tests.test_ch10 import text
u = User.objects.get(is_superuser=True); a = Account.objects.get(owner=u, name='Practice'); c = Client(); c.force_login(u)
said = lambda page: re.findall(r'class=\"message \w+\">([^<]+)<', page) or re.findall(r'class=\"errorlist[^\"]*\"[^>]*><li>([^<]+)<', page)
did = {'2026-01': 'Bought on day 2.', '2026-02': 'Bought on day 12, late.', '2026-03': 'Skipped, and wrote why.'}
for month, done in did.items():
    draft = re.search(r'name=\"rules_said\"[^>]*>\s*([^<]*)<', text(c.get(f'/accounts/{a.pk}/method/review/{month}/'))).group(1).strip()
    answers = {'did': done, 'rules_said': draft, 'next_month': 'Buy in the first week.'}
    print(month, '|', draft, '|', said(text(c.post(f'/accounts/{a.pk}/method/review/{month}/close/', answers, follow=True))))
late = {'date': '2026-03-20', 'action': 'buy', 'symbol': 'INDEX', 'amount': '100'}
print(said(text(c.post(f'/accounts/{a.pk}/method/log/', late, follow=True))))
print(said(text(c.post(f'/accounts/{a.pk}/method/review/2026-03/reopen/', {'reason': ''}, follow=True))))
print(said(text(c.post(f'/accounts/{a.pk}/method/review/2026-03/reopen/', {'reason': 'The skip was logged on the wrong day.'}, follow=True))))
history = text(c.get(f'/accounts/{a.pk}/method/review/2026-03/')).split('<ol class=\"events\">')[1].split('</ol>')[0]
for item in history.split('<li>')[1:]: print(' '.join(re.sub(r'<[^>]+>', ' ', item).split()))
"
```

```text
2026-01 | Every rule passed this month. | ['Closed 2026-01. Its entries are read-only now.']
2026-02 | Bought on day 12; the window is days 1 to 7. | ['Closed 2026-02. Its entries are read-only now.']
2026-03 | No buy in 2026-03. (skipped: Practice month: I read the lesson again instead.) | ['Closed 2026-03. Its entries are read-only now.']
['2026-03 is closed. Reopen its review, with a reason, to change it.']
['This field is required.']
['Reopened 2026-03. Its entries can change again.']
2026-10-29 16:08: Closed by owner. What I did: Skipped, and wrote why. What the rules said: No buy in 2026-03. (skipped: Practice month: I read the lesson again instead.) What I'll do next month: Buy in the first week.
2026-10-29 16:08: Reopened by owner. The skip was logged on the wrong day.
```

Your times are the time you ran it, in UTC, and the name is your superuser's. Last, the export:

Listing 12-39, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -v 0 -c "
from django.contrib.auth.models import User
from django.test import Client
from invest_witus_site.holdings.models import Account
u = User.objects.get(is_superuser=True); a = Account.objects.get(owner=u, name='Practice'); c = Client(); c.force_login(u)
response = c.get(f'/accounts/{a.pk}/logbook/export.csv')
print(response['Content-Disposition'])
print(response.content.decode(), end='')
"
```

```text
attachment; filename="logbook-account-1.csv"
date,kind,symbol,amount,shares,state,tags,reason,note,source,month_closed
2026-01-02,buy,INDEX,100.00,0.500000,,,,first buy,hand,yes
2026-02-12,buy,INDEX,100.00,,,,,,hand,yes
2026-03-04,skip,,,,unsure,practice,Practice month: I read the lesson again instead.,,hand,no
2026-11-03,buy,INDEX,100.00,0.496277,,,,"Alpaca paper order order-1: filled, 0.496277 shares at 201.5 on 2026-11-04",alpaca-paper:iw-1-1-2026-11-INDEX,no
```

March reads `no` because you reopened it. The November note is quoted because it holds a comma. In a browser,
the same file is **Download these as CSV** on the logbook page, which you reach from **Open the logbook** under
the view switch.

To try a change of plan, open **Change or end this plan** under the view switch, pick **Change the numbers**, set
the amount, leave **Starting** on next month, write why, and save. View A then lists both versions with their
dates and your reason. Put the plan back the same way if you do not mean to keep it; each change is a version.

### 12.11 What the owner does outside the editor

The reference app's steps are task 17 in the owner's queue. A learner with a Vercel project of their own does
the same:

1. **Merge the chapter.** The push to `main` runs the migrate workflow described in `docs/05-operations.md`.
   Every new column has a database default, so the release before this one keeps working while it runs.
2. **Check the run.** GitHub, the repository, **Actions**, **Migrate production database**: the run for the merge
   must be green, and its summary lists `methods.0003` and `paper.0002`.
3. **Close your first month.** On the method page, view A shows **Close last month**. If a month had no buy, log
   a skip that says why before you close it.

## Checkpoint

- `uv run pytest` prints `395 passed`; ruff and pyright pass.
- Listing 12-37 refuses the skip without a reason, logs it with one, and prints March as `skipped` and the rule
  as `explained`.
- Listing 12-38 closes three months, refuses a buy dated in closed March, refuses a reopen without a reason, and
  prints the close and the reopen in the history.
- Listing 12-39 prints the eleven columns and one line per entry.
- Signed out, every public page has no `<table`, no link to `/accounts/` or `/logbook/`, and no "Close last
  month"; signed in as anyone but the owner, every new route is a 404.
- Commit and push: `git add -A && git commit -m "Chapter 12: the journal and closing the month"`.

## Exercises

1. **The rule-following rate as a number.** View B prints "N followed every rule". Add the share of due months
   followed, computed from the month rows, to view B and the logbook, and a test that reproduces it from journal
   rows (PRD 7.6's acceptance line). Decide whether an explained skip counts as followed, and write the reason
   in the decisions log.
2. **A tag table.** Move tags into a `Tag` model per owner with a group (mental state or mistake), and add rename
   and merge in the owner's pages. Keep the CSV's `tags` column the same.
3. **Soft delete.** PRD 7.6 asks for deleting an entry "with a reason". Add a `deleted_reason` column, a Delete
   button on the edit page that requires it, hide deleted lines from the review and the logbook by default, and
   list them behind a filter.
4. **An event on close.** Write the closed review as a JSON event in an `OutboundEvent` table with a
   deterministic id (`review-<plan>-<month>-<close number>`), ready for chapter 15 to send.

## If you get stuck

- Browse: https://github.com/dapperAuteur/invest-witus/tree/v12
- Diff for this chapter: https://github.com/dapperAuteur/invest-witus/compare/v11...v12
- Zip: https://github.com/dapperAuteur/invest-witus/archive/v12.zip
- Take the reference's files. Chapter 12 changed `src/invest_witus_site/urls.py`, `methods/models.py`,
  `methods/engine.py`, `methods/forms.py`, `methods/views.py`, `methods/urls.py`, `methods/admin.py`, the method
  templates `method_page.html`, `_view_a.html`, `_view_b.html`, `_view_c.html`, `_entries.html`, `_findings.html`
  and `_log_form.html`, `paper/models.py`, `paper/orders.py`, the template `paper/_month_buys.html` and
  `pages/static/pages/site.css` and `docs/site/privacy.md` (the journal's new fields and the CSV download), and
  added `methods/reviews.py`, `methods/logbook.py`, `methods/logbook_urls.py`,
  the templates `_close_month.html`, `_reviews.html`, `_versions.html`, `_form_fields.html`, `plan_change.html`,
  `review_month.html`, `logbook.html` and `entry_edit.html`,
  `methods/migrations/0003_journal_kinds_plan_versions_and_reviews.py`,
  `paper/migrations/0002_paperorder_attempt.py` and `tests/test_ch12.py`. No package changed, no environment
  variable was added, nothing moved:
  `git fetch reference --tags && git checkout v12 -- src tests docs/site/privacy.md`.
- `test_an_entry_refuses_a_float_a_bad_symbol_a_zero_amount_and_an_unknown_action` (chapter 10) passes `hold`
  and expects it refused: you added `hold` to the action's choices instead of a `kind` column.
- `test_the_owner_logs_an_entry_from_the_form` (chapter 10) answers "This field is required." for the kind: the
  form's `kind` field is required. Set `required = False` in `__init__` and default it in `clean_kind`.
- `test_view_b_tables_every_month_with_amounts_and_shares` (chapter 10) fails to unpack: view B has a fifth table.
  The month reviews are a list.
- `test_a_two_symbol_plan_shows_the_split_without_a_confirm_button` (chapter 11) finds "Confirm": a new sentence
  on the method page uses the word.
- A form for a closed month saves anyway: the view built the form without `instance=JournalEntry(account=account)`,
  so `clean()` had no account to check.
- `test_closing_needs_three_answers_and_no_unexplained_miss` gets a 404 for the review page: `review_or_404` does
  not call `open_due_reviews` before it looks.
- `test_a_change_is_a_new_version_and_each_month_is_judged_by_its_own` raises `IntegrityError` on
  `one_active_plan_per_account`: `apply` creates the new row before it saves the old one inactive.
- `test_place_again_is_a_new_id_once_after_an_order_ended_unfilled` sends a third order: `staged` takes the first
  attempt instead of the newest, so it keeps seeing the unfilled one.
- `test_the_csv_export_has_the_documented_columns` finds `=SUM(1)` without its apostrophe: the guard runs on
  `note` only, or `cell` checks `text[0] == "="` and misses the others.
- `ruff check` reports `E501` in a migration: run the format step of Listing 12-5 before the check.
- On Vercel after the merge, a page answers 500 with `no such column: kind` or `relation
  "methods_monthlyreview" does not exist` for about a minute: the migrate workflow is still running. Longer than
  that, open GitHub Actions and read the run.

## What we learned

- A migration is additive only when the old code can still write rows: a new `NOT NULL` column needs a database
  default, not just a Python one.
- Rules between fields belong in the model's `clean()`, where every form and the admin run them, and a rule that
  depends on state (a closed month) can sit there too.
- History is cheapest as rows that point back: a changed plan is a new version, and the old one keeps judging
  its own months.
- An audit trail is a table nobody can edit, written in the same transaction as the change it records.
- An explanation is not an excuse. The miss stays a finding; the reason sits beside it, and the person reading
  the review decides.
- An export is part of the product: documented columns, a predictable format, and a guard for the program that
  will open it.

## Next

Chapter 13 is the in-app reporter: a bug, a feature request or a question, stored in the app and mirrored to
WitUS Inbox with a signed request, retried by the daily job.

## References

Django Software Foundation. (n.d.-a). *Working with forms*. Django 5.2 documentation. Retrieved October 29, 2026,
from https://docs.djangoproject.com/en/5.2/topics/forms/

Django Software Foundation. (n.d.-b). *Model field reference*. Django 5.2 documentation. Retrieved October 29,
2026, from https://docs.djangoproject.com/en/5.2/ref/models/fields/

OWASP Foundation. (n.d.). *CSV injection*. Retrieved October 29, 2026, from
https://community.owasp.org/attacks/CSV_Injection

Python Software Foundation. (n.d.). *csv: CSV file reading and writing*. Python documentation. Retrieved October
29, 2026, from https://docs.python.org/3/library/csv.html
