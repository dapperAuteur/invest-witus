"""Version 2 of the index rules (2026-11-03, decisions 173 and 174; backlog row 23).

Chapter 03's rules (version 1) expect one buy of the plan's whole amount each month, so a plan
split across several funds (decision 161) read "followed in 0 of N". Version 2 asks for one buy of
each fund and judges the month's total within one cent for each fund after the first. A plan with
one fund is judged exactly as before. A month closed under version 1 keeps version 1's findings;
every other month is judged by the newest version. Placeholder symbols only; no Alpaca call leaves
the test."""

import importlib
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from django.apps import apps
from django.contrib.auth.models import User
from django.test import Client

from invest_witus.adherence import index_dca_v2
from invest_witus.adherence import review as version_1
from invest_witus.adherence.journal import Action, Entry
from invest_witus.adherence.plan import Plan
from invest_witus.adherence.rule_sets import CHECKED_BY_VERSION, CHECKED_RULES
from invest_witus.methods.rulebook import (
    LESSON_COMING,
    UnknownMethodError,
    available_methods,
    latest_method,
    load_method,
    load_method_version,
    method_versions,
)
from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.engine import build_review
from invest_witus_site.methods.models import JournalEntry, MethodPlan, MonthlyReview, ReviewEvent
from invest_witus_site.methods.reviews import close_review, reopen_review
from invest_witus_site.paper import orders
from invest_witus_site.paper.models import PaperOrder, client_order_id
from tests.test_ch10 import text
from tests.test_ch15 import row_for

D = Decimal
V1 = load_method_version("index-dca", 1)
V2 = load_method_version("index-dca", 2)
THREE = Plan(
    method="index-dca",
    start=date(2026, 1, 1),
    amount=D("500.00"),
    symbols=frozenset({"ALPHA", "BETA", "GAMMA"}),
    buy_window_days=7,
)
ONE = Plan("index-dca", date(2026, 1, 1), D("100.00"), frozenset({"INDEX"}), 7)
SPLIT = {"ALPHA": "166.67", "BETA": "166.67", "GAMMA": "166.66"}
ANSWERS = {"did": "Bought each fund.", "rules_said": "Split.", "next_month": "The same."}


def entry(day: date, symbol: str, amount: str, action: Action = Action.BUY) -> Entry:
    return Entry(day=day, action=action, symbol=symbol, amount=D(amount))


def split_month(year: int, month: int, parts: dict[str, str] = SPLIT, day: int = 2) -> list[Entry]:
    return [entry(date(year, month, day), symbol, amount) for symbol, amount in parts.items()]


def said(findings: list[version_1.Finding]) -> list[tuple[date, str, str]]:
    return [(f.day, f.rule_id, f.message) for f in findings]


# --- The rules file and the checks stay equal, per version ----------------------------------------


def test_every_version_of_every_method_has_checks_equal_to_its_rules_file() -> None:
    shipped = {
        (method.id, version)
        for method in available_methods()
        for version in method_versions(method.id)
    }
    assert shipped == set(CHECKED_BY_VERSION)
    for method_id, version in shipped:
        method = load_method_version(method_id, version)
        assert method.version == version
        assert {rule.id for rule in method.rules} == CHECKED_BY_VERSION[(method_id, version)]
        for rule in method.rules:  # every rule names its lesson or says "lesson coming"
            assert method.lesson_for(rule.id) in {rule.lesson or method.lesson, LESSON_COMING}


def test_version_1_is_kept_and_the_start_form_offers_version_2() -> None:
    assert method_versions("index-dca") == [1, 2]
    assert load_method("index-dca") == V1, "chapter 03's file and the command line: version 1"
    assert latest_method("index-dca") == V2
    assert [(m.id, m.version) for m in available_methods()] == [
        ("index-dca", 2),
        ("momentum-12-1", 1),
    ]
    assert CHECKED_RULES["index-dca"] == version_1.CHECKED_RULES == index_dca_v2.CHECKED_RULES
    assert V2.rule("one-buy-each-month").text.startswith("Buy once in every month of the plan:")
    assert all(rule.lesson == "" for rule in V2.rules), "no lesson is published yet"
    with pytest.raises(UnknownMethodError):
        load_method_version("index-dca", 3)


# --- Version 2's checks ---------------------------------------------------------------------------


def test_a_month_split_across_three_funds_follows_version_2_and_broke_version_1() -> None:
    journal = split_month(2026, 1) + split_month(2026, 2)
    through = date(2026, 2, 28)
    assert index_dca_v2.review(V2, THREE, journal, through) == []
    old = [f.rule_id for f in version_1.review(V1, THREE, journal, through)]
    assert old.count("fixed-amount") == 6 and old.count("one-buy-each-month") == 2, "row 23"


@pytest.mark.parametrize(
    ("parts", "found"),
    [
        ({"ALPHA": "33.34", "BETA": "33.34", "GAMMA": "33.34"}, []),  # every part rounded up
        ({"ALPHA": "33.33", "BETA": "33.33", "GAMMA": "33.33"}, []),  # every part rounded down
        (
            {"ALPHA": "33.35", "BETA": "33.34", "GAMMA": "33.34"},
            ["The buys of 2026-01 add up to 100.03; the plan says 100.00 in all (over by 0.03)."],
        ),
        (
            {"ALPHA": "33.32", "BETA": "33.33", "GAMMA": "33.32"},
            ["The buys of 2026-01 add up to 99.97; the plan says 100.00 in all (short by 0.03)."],
        ),
    ],
)
def test_the_total_may_be_off_by_one_cent_for_each_fund_after_the_first(
    parts: dict[str, str], found: list[str]
) -> None:
    plan = Plan("index-dca", date(2026, 1, 1), D("100.00"), THREE.symbols, 7)
    assert index_dca_v2.tolerance(plan) == D("0.02")
    findings = index_dca_v2.review(V2, plan, split_month(2026, 1, parts), date(2026, 1, 31))
    assert [f.message for f in findings] == found
    assert all(f.rule_id == "fixed-amount" and f.day == date(2026, 1, 2) for f in findings)


def test_a_fund_left_out_is_a_finding_with_its_reason_and_the_total_is_not_judged() -> None:
    journal = split_month(2026, 1, {"ALPHA": "166.67", "BETA": "166.67"})
    reasons = {((2026, 1), "GAMMA"): "$166.66 not placed. Alpaca's answer: market closed"}
    findings = index_dca_v2.review(V2, THREE, journal, date(2026, 1, 31), reasons)
    assert said(findings) == [
        (
            date(2026, 1, 1),
            "one-buy-each-month",
            "No buy of GAMMA in 2026-01. $166.66 not placed. Alpaca's answer: market closed",
        )
    ]
    assert isinstance(findings[0], index_dca_v2.SymbolFinding)
    assert findings[0].symbol == "GAMMA"
    assert findings[0].lesson == LESSON_COMING


def test_a_month_with_no_buy_and_a_fund_bought_twice() -> None:
    journal = split_month(2026, 1) + [entry(date(2026, 1, 3), "ALPHA", "10.00")]
    reasons = {((2026, 2), "BETA"): "$166.67 not bought. The order ended with nothing filled."}
    findings = index_dca_v2.review(V2, THREE, journal, date(2026, 2, 28), reasons)
    assert said(findings) == [
        (date(2026, 1, 1), "one-buy-each-month", "2 buys of ALPHA in 2026-01."),
        (
            date(2026, 1, 3),
            "fixed-amount",
            "The buys of 2026-01 add up to 510.00; the plan says 500.00 in all (over by 10.00).",
        ),
        (
            date(2026, 2, 1),
            "one-buy-each-month",
            "No buy in 2026-02. BETA: $166.67 not bought. The order ended with nothing filled.",
        ),
    ]
    assert [getattr(f, "symbol", "") for f in findings] == ["", "", ""], "a skip explains none"


def test_a_part_fill_is_a_short_total_with_alpacas_reason() -> None:
    parts = {"ALPHA": "166.67", "BETA": "120.00", "GAMMA": "166.66"}
    reasons = {((2026, 1), "BETA"): "$120.00 of $166.67. The order ended part filled (canceled)."}
    findings = index_dca_v2.review(
        V2, THREE, split_month(2026, 1, parts), date(2026, 1, 31), reasons
    )
    assert [f.message for f in findings] == [
        "The buys of 2026-01 add up to 453.33; the plan says 500.00 in all (short by 46.67). "
        "BETA: $120.00 of $166.67. The order ended part filled (canceled)."
    ]


def test_the_window_the_plans_funds_and_selling_are_judged_as_in_version_1() -> None:
    journal = [
        *split_month(2026, 1, {"ALPHA": "166.67", "BETA": "166.67"}),
        entry(date(2026, 1, 12), "GAMMA", "166.66"),
        entry(date(2026, 1, 3), "OTHER", "5.00"),
        entry(date(2026, 1, 20), "ALPHA", "50.00", Action.SELL),
    ]
    findings = index_dca_v2.review(V2, THREE, journal, date(2026, 1, 31))
    assert said(findings) == [
        (date(2026, 1, 3), "plan-symbols-only", "Bought OTHER, which is not in the plan."),
        (date(2026, 1, 12), "buy-in-window", "Bought GAMMA on day 12; the window is days 1 to 7."),
        (date(2026, 1, 20), "no-selling", "Sold 50.00 of ALPHA."),
    ]


# One fund: the two versions give the same findings, word for word (chapter 03's cases and more).
ONE_FUND_JOURNALS = [
    [entry(date(2026, 1, 2), "INDEX", "100.00"), entry(date(2026, 2, 2), "INDEX", "100.00")],
    [entry(date(2026, 1, 2), "INDEX", "100.00")],
    [entry(date(2026, 1, 2), "INDEX", "100.00"), entry(date(2026, 2, 12), "INDEX", "100.00")],
    [entry(date(2026, 1, 2), "INDEX", "100.00"), entry(date(2026, 2, 2), "INDEX", "150.00")],
    [entry(date(2026, 1, 2), "INDEX", "100.00"), entry(date(2026, 2, 2), "OTHER", "100.00")],
    [
        entry(date(2026, 1, 2), "INDEX", "100.00"),
        entry(date(2026, 1, 5), "INDEX", "100.00"),
        entry(date(2026, 2, 2), "INDEX", "100.00"),
    ],
    [
        entry(date(2026, 1, 2), "INDEX", "100.00"),
        entry(date(2026, 1, 20), "INDEX", "50.00", Action.SELL),
        entry(date(2026, 2, 2), "INDEX", "99.99"),
    ],
    [entry(date(2026, 1, 2), "INDEX", "60.00"), entry(date(2026, 1, 3), "INDEX", "40.00")],
    [],
]


@pytest.mark.parametrize("journal", ONE_FUND_JOURNALS)
def test_a_plan_with_one_fund_is_judged_the_same_by_both_versions(journal: list[Entry]) -> None:
    through = date(2026, 2, 28)
    reasons = {((2026, 2), "INDEX"): "$100.00 not placed. Alpaca's answer: market closed"}
    old = version_1.review(V1, ONE, journal, through)
    new = index_dca_v2.review(V2, ONE, journal, through, reasons)
    assert said(new) == said(old)
    assert [f.lesson for f in new] == [f.lesson for f in old]


# --- On the web: each month judged by its version ------------------------------------------------


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_superuser("owner", "owner@example.com", "pw")


@pytest.fixture
def account(owner: User) -> Account:
    return Account.objects.create(name="B_INDEX", broker="Paper", kind="paper", owner=owner)


@pytest.fixture
def owner_client(client: Client, owner: User) -> Client:
    client.force_login(owner)
    return client


@pytest.fixture
def plan(account: Account) -> MethodPlan:
    return MethodPlan.objects.create(
        account=account,
        method_id="index-dca",
        amount=D("500.00"),
        buy_window_days=7,
        symbols="ALPHA BETA GAMMA",
        started_on=date(2026, 1, 1),
    )


def log_split(account: Account, year: int, month: int, parts: dict[str, str] = SPLIT) -> None:
    for symbol, amount in parts.items():
        JournalEntry.objects.create(
            account=account,
            date=date(year, month, 2),
            action="buy",
            symbol=symbol,
            amount=D(amount),
        )


def closed(plan: MethodPlan, month: str, rules_version: int | None) -> MonthlyReview:
    return MonthlyReview.objects.create(
        plan=plan,
        month=month,
        opened_on=date(int(month[:4]), int(month[5:]), 7),
        closed_at=datetime(2026, 3, 8, tzinfo=UTC),
        rules_version=rules_version,
        **ANSWERS,
    )


@pytest.mark.django_db
def test_months_split_across_the_funds_read_followed(account: Account, plan: MethodPlan) -> None:
    log_split(account, 2026, 1)
    log_split(account, 2026, 2)
    review = build_review(plan, JournalEntry.entries_for(account), date(2026, 2, 28))
    assert review.findings == [] and review.months_followed == 2
    assert review.method.version == 2 and review.older_rules == []
    assert [row.rules_version for row in review.months] == [2, 2]


@pytest.mark.django_db
def test_a_month_closed_under_version_1_keeps_its_findings(
    owner_client: Client, account: Account, plan: MethodPlan
) -> None:
    log_split(account, 2026, 1)
    log_split(account, 2026, 2)
    closed(plan, "2026-01", 1)
    review = build_review(plan, JournalEntry.entries_for(account), date(2026, 2, 28))
    january = [f for f in review.findings if f.month == "2026-01"]
    assert [f.rule.id for f in january] == ["one-buy-each-month"] + ["fixed-amount"] * 3
    assert january[0].message == "3 buys in 2026-01."
    assert january[1].message == "Bought 166.67; the plan says 500.00."
    assert january[0].rule.text == V1.rule("one-buy-each-month").text, "version 1's own words"
    assert [f for f in review.findings if f.month == "2026-02"] == []
    assert [(row.label, row.rules_version) for row in review.months] == [
        ("2026-01", 1),
        ("2026-02", 2),
    ]
    assert review.older_rules == [(1, "2026-01")] and review.months_followed == 1
    page = text(owner_client.get(f"/accounts/{account.pk}/method/?through=2026-02-28"))
    assert "Judged by version 1 of the rules, the version they were closed under: 2026-01." in page
    assert "Every other month is judged by version 2." in page
    month = text(owner_client.get(f"/accounts/{account.pk}/method/review/2026-01/"))
    assert "Rules: version 1, the version this month was closed under" in month


@pytest.mark.django_db
def test_closing_writes_the_version_and_a_reopen_keeps_it(
    owner: User, account: Account, plan: MethodPlan
) -> None:
    log_split(account, 2026, 1)
    log_split(account, 2026, 2)
    january = closed(plan, "2026-01", 1)
    february = MonthlyReview.objects.create(plan=plan, month="2026-02", opened_on=date(2026, 2, 7))
    context = build_review(plan, JournalEntry.entries_for(account), date(2026, 2, 28))
    close_review(february, context, by=owner, **ANSWERS)
    february.refresh_from_db()
    assert february.rules_version == 2
    reopen_review(january, reason="A typo in the note.", by=owner)
    january.refresh_from_db()
    assert january.rules_version == 1, "a reopened month stays on the version it was closed under"
    context = build_review(plan, JournalEntry.entries_for(account), date(2026, 2, 28))
    close_review(january, context, by=owner, **ANSWERS)
    january.refresh_from_db()
    assert january.rules_version == 1


@pytest.mark.django_db
def test_a_skip_that_names_the_fund_explains_its_missing_buy(
    account: Account, plan: MethodPlan
) -> None:
    log_split(account, 2026, 1, {"ALPHA": "166.67", "BETA": "166.67"})
    JournalEntry.objects.create(
        account=account, date=date(2026, 1, 3), kind="skip", symbol="GAMMA", reason="Held cash."
    )
    review = build_review(plan, JournalEntry.entries_for(account), date(2026, 1, 31))
    assert [(f.message, f.explanation) for f in review.findings] == [
        ("No buy of GAMMA in 2026-01.", "Held cash.")
    ]
    check = next(c for c in review.checks if c.rule.id == "one-buy-each-month")
    assert check.status == "explained"


@pytest.mark.django_db
def test_a_refused_paper_order_names_alpacas_answer_in_the_finding(
    account: Account, plan: MethodPlan
) -> None:
    log_split(account, 2026, 1, {"ALPHA": "166.67", "BETA": "166.67"})
    PaperOrder.objects.create(
        account=account,
        plan=plan,
        month="2026-01",
        symbol="GAMMA",
        notional=D("166.66"),
        client_order_id=client_order_id(account.pk, plan.pk, "2026-01", "GAMMA"),
        message="asset GAMMA is not tradable",
    )
    assert orders.order_shortfalls(plan) == {
        ((2026, 1), "GAMMA"): "$166.66 not placed. Alpaca's answer: asset GAMMA is not tradable"
    }
    review = build_review(plan, JournalEntry.entries_for(account), date(2026, 1, 31))
    assert [f.message for f in review.findings] == [
        "No buy of GAMMA in 2026-01. $166.66 not placed. Alpaca's answer: asset GAMMA is not "
        "tradable"
    ]


@pytest.mark.django_db
def test_a_one_fund_plan_reads_the_same_on_the_page(account: Account) -> None:
    single = MethodPlan.objects.create(
        account=account,
        method_id="index-dca",
        amount=D("100.00"),
        buy_window_days=7,
        symbols="INDEX",
        started_on=date(2026, 1, 1),
    )
    for day, amount in ((date(2026, 1, 2), "100.00"), (date(2026, 2, 12), "150.00")):
        JournalEntry.objects.create(
            account=account, date=day, action="buy", symbol="INDEX", amount=D(amount)
        )
    trades = [e.to_entry() for e in JournalEntry.entries_for(account)]
    review = build_review(single, JournalEntry.entries_for(account), date(2026, 3, 31))
    expected = version_1.review(V1, single.to_plan(), trades, date(2026, 3, 31))
    assert [(f.day, f.rule.id, f.message) for f in review.findings] == said(expected)


@pytest.mark.django_db
def test_compare_counts_each_closed_month_by_its_own_version(
    owner_client: Client, owner: User, account: Account, plan: MethodPlan
) -> None:
    other = Account.objects.create(name="Other", broker="Paper", kind="paper", owner=owner)
    MethodPlan.objects.create(
        account=other,
        method_id="index-dca",
        amount=D("100.00"),
        buy_window_days=7,
        symbols="INDEX",
        started_on=date(2026, 1, 1),
    )
    log_split(account, 2026, 1)
    log_split(account, 2026, 2)
    closed(plan, "2026-01", 1)
    closed(plan, "2026-02", 2)
    assert row_for(text(owner_client.get("/compare/")), "B_INDEX")[-1] == (
        "followed in 1 of 2 closed months"
    )
    MonthlyReview.objects.filter(month="2026-01").update(rules_version=None)
    assert row_for(text(owner_client.get("/compare/")), "B_INDEX")[-1] == (
        "followed in 2 of 2 closed months"
    )


# --- The migration's data step --------------------------------------------------------------------


@pytest.mark.django_db
def test_the_migration_pins_every_reviewed_month_to_version_1_and_is_safe_twice(
    plan: MethodPlan,
) -> None:
    step = importlib.import_module(
        "invest_witus_site.methods.migrations.0006_monthlyreview_rules_version"
    ).pin_reviewed_months_to_version_1
    closed_month = closed(plan, "2026-01", None)
    reopened = MonthlyReview.objects.create(plan=plan, month="2026-02", opened_on=date(2026, 2, 7))
    ReviewEvent.objects.create(review=reopened, action=ReviewEvent.CLOSED, text="Closed once.")
    ReviewEvent.objects.create(review=reopened, action=ReviewEvent.REOPENED, text="A typo.")
    never = MonthlyReview.objects.create(plan=plan, month="2026-03", opened_on=date(2026, 3, 7))
    newer = closed(plan, "2026-04", 2)
    for _ in range(2):
        step(apps, None)
        pinned = {
            review.month: review.rules_version
            for review in MonthlyReview.objects.filter(
                pk__in=[closed_month.pk, reopened.pk, never.pk, newer.pk]
            )
        }
        assert pinned == {"2026-01": 1, "2026-02": 1, "2026-03": None, "2026-04": 2}
