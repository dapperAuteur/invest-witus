"""Chapter 14 checkpoint: a second method, 12-1 momentum. The 12-1 math in Decimal from planted
prices (the window, the month-end close, the return, the ranking with its ties and its missing
history); a rule set per method, each equal to its rules file; the second rule set's findings, one
rule at a time; a momentum plan started from the same form with its top N, its candidates put on
the watch list; the engine ranking every month from stored adjusted closes; the ranked bars with
their table and "How to read this", the shaded window on a history chart, the watch list's badge;
buys on paper for the top N in equal parts, a refusal when nothing is ranked, and the wash-sale
warning. Placeholder symbols only (ALPHA, BETA, GAMMA, DELTA, INDEX, OTHER); every price is planted
here, and no page that is public shows any of it."""

import random
from collections.abc import Iterable
from datetime import date
from decimal import Decimal

import httpx
import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone
from pytest_django.fixtures import Settings

from invest_witus.adherence import momentum as momentum_rules
from invest_witus.adherence.journal import Action, Entry
from invest_witus.adherence.plan import Plan
from invest_witus.adherence.rule_sets import CHECKED_RULES
from invest_witus.methods.momentum_12_1 import (
    Month,
    Ranking,
    Score,
    Unranked,
    Window,
    add_months,
    month_ends,
    rank,
    score,
)
from invest_witus.methods.rulebook import LESSON_COMING, available_methods, load_method
from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.engine import build_review
from invest_witus_site.methods.forms import PlanChangeForm
from invest_witus_site.methods.models import JournalEntry, MethodPlan
from invest_witus_site.methods.momentum import (
    bar_chart,
    percent_text,
    price_series,
    ranking_for,
    rebalance,
)
from invest_witus_site.paper import alpaca, orders
from invest_witus_site.paper.models import PaperOrder
from invest_witus_site.prices.models import DailyClose
from invest_witus_site.watchlist.models import WatchItem
from tests.test_ch10 import tables_in, text
from tests.test_ch11 import DAY, KEY_ID, SECRET, FakeAlpaca

D = Decimal
MOMENTUM = "momentum-12-1"
CANDIDATES = "ALPHA BETA GAMMA DELTA"
CANDIDATE_LIST: list[str] = ["ALPHA", "BETA", "GAMMA", "DELTA"]
PUBLIC_PATHS = ["/", "/faq/", "/privacy/", "/terms/", "/contact/", "/waitlist/"]


# --- Planting prices ------------------------------------------------------------------------------


def monthly(start: Month, count: int) -> list[Month]:
    return [add_months(start, step) for step in range(count)]


def closes(
    months: Iterable[Month], growth: str, base: str = "100", day: int = 28
) -> list[tuple[date, Decimal]]:
    """One close a month on `day`, starting at `base` and growing by `growth` each month."""
    value = D(base)
    rows: list[tuple[date, Decimal]] = []
    for year, month in months:
        rows.append((date(year, month, day), value.quantize(D("0.0001"))))
        value *= 1 + D(growth)
    return rows


def plant(symbol: str, rows: list[tuple[date, Decimal]], adjusted: bool = True) -> None:
    for day, value in rows:
        DailyClose.objects.create(
            symbol=symbol,
            date=day,
            close=value,
            adj_close=value if adjusted else None,
            source="csv",
            fetched_at=timezone.now(),
        )


def plant_candidates(last: Month) -> None:
    """Twenty months ending at `last`: ALPHA rises 2% a month, BETA 1%, GAMMA falls 1% and has no
    adjusted closes (a CSV file), DELTA has only the last six months, so it cannot be ranked."""
    months = monthly(add_months(last, -19), 20)
    plant("ALPHA", closes(months, "0.02"))
    plant("BETA", closes(months, "0.01"))
    plant("GAMMA", closes(months, "-0.01"), adjusted=False)
    plant("DELTA", closes(months[-6:], "0.05"))


# --- Fixtures -------------------------------------------------------------------------------------


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
    """The site owner, a superuser, as chapter 11 needs for Alpaca paper."""
    return django_user_model.objects.create_superuser("owner", "owner@example.com", "pw")


@pytest.fixture
def someone(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("someone")


@pytest.fixture
def account(owner: User) -> Account:
    return Account.objects.create(
        name="Practice", broker="Example Broker", kind="paper", owner=owner
    )


@pytest.fixture
def owner_client(client: Client, owner: User) -> Client:
    client.force_login(owner)
    return client


def momentum_plan(account: Account, started_on: date, **extra: object) -> MethodPlan:
    return MethodPlan.objects.create(
        account=account,
        method_id=MOMENTUM,
        amount=D("100.00"),
        buy_window_days=7,
        symbols=CANDIDATES,
        top_n=2,
        started_on=started_on,
        **extra,
    )


def this_month() -> Month:
    today = timezone.localdate()
    return today.year, today.month


@pytest.fixture
def running(account: Account) -> MethodPlan:
    """A momentum plan that started last month, with prices through last month."""
    plant_candidates(add_months(this_month(), -1))
    start = add_months(this_month(), -1)
    return momentum_plan(account, date(start[0], start[1], 1))


# --- The 12-1 math --------------------------------------------------------------------------------


def test_the_window_runs_from_13_months_back_to_2_and_leaves_the_latest_month_out() -> None:
    november = Window.for_month(2026, 11)
    assert (november.start, november.end, november.excluded) == ((2025, 10), (2026, 9), (2026, 10))
    january = Window.for_month(2026, 1)
    assert (january.start, january.end, january.excluded) == ((2024, 12), (2025, 11), (2025, 12))
    assert november.needs == "a close in 2025-10 and in 2026-09"


def test_the_month_end_close_is_the_last_stored_day_of_the_month() -> None:
    rows = [
        (date(2026, 9, 2), D("90")),
        (date(2026, 9, 30), D("101")),
        (date(2026, 9, 29), D("150")),
        (date(2026, 10, 1), D("999")),
    ]
    random.Random(14).shuffle(rows)
    ends = month_ends(rows)
    assert ends[(2026, 9)] == (date(2026, 9, 30), D("101"))
    assert ends[(2026, 10)] == (date(2026, 10, 1), D("999"))
    assert (2026, 8) not in ends, "a month without a close is absent, never filled in"


def test_the_12_1_return_is_end_over_start_less_one_and_ignores_the_excluded_month() -> None:
    window = Window.for_month(2026, 11)
    rows = [
        (date(2025, 10, 31), D("80")),
        (date(2026, 9, 30), D("90")),
        (date(2026, 10, 30), D("5000")),  # the excluded month: no effect
        (date(2026, 11, 2), D("1")),  # the rebalance month itself: no effect
    ]
    found = score("ALPHA", rows, window)
    assert isinstance(found, Score)
    assert found.change == D("0.125")
    assert isinstance(found.change, Decimal)
    assert (found.start_day, found.end_day) == (date(2025, 10, 31), date(2026, 9, 30))
    assert percent_text(found.change) == "+12.5%"
    assert percent_text(D("-0.05")) == "-5.0%"


def test_the_ranking_is_highest_first_with_ties_in_symbol_order() -> None:
    window = Window.for_month(2026, 11)

    def two(end: str) -> list[tuple[date, Decimal]]:
        return [(date(2025, 10, 31), D("100")), (date(2026, 9, 30), D(end))]

    ranking = rank({"GAMMA": two("110"), "BETA": two("120"), "ALPHA": two("110")}, window, 2)
    assert [(p.rank, p.symbol, p.top, p.tied) for p in ranking.places] == [
        (1, "BETA", True, False),
        (2, "ALPHA", True, True),
        (3, "GAMMA", False, True),
    ]
    assert ranking.top == ["BETA", "ALPHA"]
    with pytest.raises(ValueError, match="top_n must be at least 1"):
        rank({}, window, 0)


def test_a_candidate_with_missing_history_is_not_ranked_and_says_what_it_needs() -> None:
    window = Window.for_month(2026, 11)
    short = [(date(2026, 3, 31), D("50")), (date(2026, 9, 30), D("60"))]
    zero = [(date(2025, 10, 31), D("0")), (date(2026, 9, 30), D("60"))]
    ranking = rank({"DELTA": short, "OTHER": zero, "ALPHA": []}, window, 2)
    assert not ranking.ranked and ranking.top == []
    reasons = {item.symbol: item.reason for item in ranking.unranked}
    assert reasons["DELTA"] == (
        "no close stored in 2025-10; the window needs a close in 2025-10 and in 2026-09"
    )
    assert reasons["ALPHA"].startswith("no close stored in 2025-10 or 2026-09")
    assert reasons["OTHER"] == "a close of zero or less in the window"
    assert isinstance(score("DELTA", short, window), Unranked)


def test_the_bars_share_one_scale_with_the_zero_line_between_them() -> None:
    window = Window.for_month(2026, 11)

    def two(end: str) -> list[tuple[date, Decimal]]:
        return [(date(2025, 10, 31), D("100")), (date(2026, 9, 30), D(end))]

    chart = bar_chart(rank({"ALPHA": two("120"), "BETA": two("90")}, window, 1))
    assert chart is not None
    assert chart.zero_x == D("33.33")
    up, down = chart.bars
    assert (up.symbol, up.x, up.width, up.direction, up.text) == (
        "ALPHA",
        D("33.33"),
        D("66.67"),
        "up",
        "+20.0%",
    )
    assert (down.symbol, down.x, down.width, down.direction) == (
        "BETA",
        D("0.00"),
        D("33.33"),
        "down",
    )
    assert bar_chart(rank({}, window, 1)) is None


# --- A rule set per method ------------------------------------------------------------------------


def test_every_method_the_package_ships_has_a_rule_set_equal_to_its_rules_file() -> None:
    shipped = [method.id for method in available_methods()]
    assert shipped == ["index-dca", MOMENTUM]
    for method_id in shipped:
        assert {rule.id for rule in load_method(method_id).rules} == CHECKED_RULES[method_id]
    method = load_method(MOMENTUM)
    assert len(method.rules) == 7
    assert all(rule.lesson == "" for rule in method.rules), "no lesson is published yet"
    assert method.lesson_for("rank-by-12-1") == LESSON_COMING


# --- The second rule set, one rule at a time ------------------------------------------------------

PLAN = Plan(
    method=MOMENTUM,
    start=date(2026, 11, 1),
    amount=D("100.00"),
    symbols=frozenset({"ALPHA", "BETA", "GAMMA", "DELTA"}),
    buy_window_days=7,
)


def november_ranking() -> dict[Month, Ranking]:
    """For November 2026: ALPHA first, BETA second, GAMMA third, DELTA unranked."""
    window = Window.for_month(2026, 11)

    def two(end: str) -> list[tuple[date, Decimal]]:
        return [(date(2025, 10, 31), D("100")), (date(2026, 9, 30), D(end))]

    series = {"ALPHA": two("130"), "BETA": two("120"), "GAMMA": two("95"), "DELTA": []}
    return {(2026, 11): rank(series, window, 2)}


def trade(day: date, symbol: str, amount: str = "50.00", action: Action = Action.BUY) -> Entry:
    return Entry(day=day, action=action, symbol=symbol, amount=D(amount))


def found(journal: list[Entry], through: date = date(2026, 11, 30)) -> list[tuple[str, str]]:
    method = load_method(MOMENTUM)
    findings = momentum_rules.review(method, PLAN, 2, journal, through, november_ranking())
    return [(f.rule_id, f.message) for f in findings]


def test_the_top_n_in_equal_parts_inside_the_window_has_no_findings() -> None:
    assert found([trade(date(2026, 11, 3), "ALPHA"), trade(date(2026, 11, 3), "BETA")]) == []
    assert momentum_rules.equal_parts(D("100.00"), ["A", "B", "C"]) == [
        ("A", D("33.34")),
        ("B", D("33.33")),
        ("C", D("33.33")),
    ]


def test_each_momentum_rule_is_flagged_with_its_reason() -> None:
    nov3 = date(2026, 11, 3)
    assert found([trade(nov3, "ALPHA"), trade(nov3, "BETA"), trade(nov3, "OTHER")]) == [
        ("candidates-only", "Bought OTHER, which is not a candidate.")
    ]
    assert ("rank-by-12-1", "Bought DELTA, which was not ranked in 2026-11.") in found(
        [trade(nov3, "ALPHA"), trade(nov3, "BETA"), trade(nov3, "DELTA")]
    )
    gamma = found([trade(nov3, "ALPHA"), trade(nov3, "GAMMA")])
    assert ("hold-top-n", "Bought GAMMA, ranked 3rd in 2026-11; the plan holds the top 2.") in gamma
    assert ("hold-top-n", "No buy of BETA in 2026-11; it ranked 2nd.") in gamma
    assert found([trade(nov3, "ALPHA", "60.00"), trade(nov3, "BETA", "40.00")]) == [
        ("equal-weight", "Bought 40.00 of BETA; an equal part of 100.00 over 2 is 50.00."),
        ("equal-weight", "Bought 60.00 of ALPHA; an equal part of 100.00 over 2 is 50.00."),
    ]
    late = found([trade(date(2026, 11, 12), "ALPHA"), trade(date(2026, 11, 12), "BETA")])
    assert late == [
        ("trade-only-at-review", "Bought ALPHA on day 12; the window is days 1 to 7."),
        ("trade-only-at-review", "Bought BETA on day 12; the window is days 1 to 7."),
    ]
    assert found([]) == [("rebalance-each-month", "No rebalance in 2026-11.")]


def test_a_holding_that_left_the_top_n_must_be_sold_and_one_inside_it_kept() -> None:
    october = [trade(date(2026, 10, 2), "GAMMA"), trade(date(2026, 10, 2), "ALPHA")]
    nov = [trade(date(2026, 11, 3), "ALPHA"), trade(date(2026, 11, 3), "BETA")]
    method = load_method(MOMENTUM)
    rankings = november_ranking()

    def sells(journal: list[Entry]) -> list[str]:
        findings = momentum_rules.review(
            method, PLAN, 2, journal, date(2026, 11, 30), rankings, held_since=date(2026, 10, 1)
        )
        return [f.message for f in findings if f.rule_id == "sell-what-leaves"]

    assert sells(october + nov) == [
        "Held GAMMA into 2026-11, ranked 3rd, outside the top 2, and did not sell it."
    ]
    sold = trade(date(2026, 11, 3), "GAMMA", "40.00", Action.SELL)
    assert sells([*october, *nov, sold]) == []
    sold_alpha = trade(date(2026, 11, 3), "ALPHA", "40.00", Action.SELL)
    assert sells([*october, *nov, sold, sold_alpha]) == [
        "Sold ALPHA, still in the top 2 in 2026-11."
    ]


def test_a_month_with_nothing_ranked_is_not_judged_by_rank() -> None:
    method = load_method(MOMENTUM)
    nothing = {(2026, 11): rank({"ALPHA": [], "BETA": []}, Window.for_month(2026, 11), 2)}
    journal = [trade(date(2026, 11, 3), "GAMMA"), trade(date(2026, 11, 3), "DELTA")]
    findings = momentum_rules.review(method, PLAN, 2, journal, date(2026, 11, 30), nothing)
    assert {f.rule_id for f in findings} == set(), "no rank, so no rank findings"


# --- Plans ----------------------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_start_form_lists_both_methods_and_starts_a_momentum_plan(
    owner_client: Client, account: Account
) -> None:
    page = text(owner_client.get(f"/accounts/{account.pk}/method/"))
    assert '<option value="index-dca"' in page and f'<option value="{MOMENTUM}"' in page
    assert "12-1 momentum, monthly top N in equal parts" in page
    assert "Top N to hold" in page
    form = {
        "method_id": MOMENTUM,
        "amount": "100",
        "buy_window_days": "7",
        "symbols": "alpha, beta gamma delta",
        "started_on": "2026-11-01",
        "top_n": "2",
    }
    done = owner_client.post(f"/accounts/{account.pk}/method/start/", form, follow=True)
    plan = MethodPlan.objects.get(account=account)
    assert (plan.method_id, plan.symbols, plan.top_n) == (MOMENTUM, CANDIDATES, 2)
    html = text(done)
    assert "Started 12-1 momentum, monthly top N in equal parts on Practice." in html
    assert "Added to the watch list, so the nightly pull stores their closes: ALPHA, BETA" in html
    watched = WatchItem.objects.filter(account=account).values_list("symbol", flat=True)
    assert sorted(watched) == ["ALPHA", "BETA", "DELTA", "GAMMA"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "method_id, symbols, top_n, message",
    [
        (MOMENTUM, CANDIDATES, "", "12-1 momentum needs a top N: how many candidates to hold."),
        (
            MOMENTUM,
            "ALPHA BETA",
            "2",
            "Name more candidates than the top N: 2 candidates and a top 2",
        ),
        (MOMENTUM, CANDIDATES, "0", "Ensure this value is greater than or equal to 1."),
        ("index-dca", "INDEX", "2", "Leave this empty: index investing holds every fund it names."),
    ],
)
def test_the_start_form_refuses_a_bad_top_n(
    owner_client: Client, account: Account, method_id: str, symbols: str, top_n: str, message: str
) -> None:
    form = {
        "method_id": method_id,
        "amount": "100",
        "buy_window_days": "7",
        "symbols": symbols,
        "started_on": "2026-11-01",
        "top_n": top_n,
    }
    page = text(owner_client.post(f"/accounts/{account.pk}/method/start/", form))
    assert message in page
    assert not MethodPlan.objects.exists()


@pytest.mark.django_db
def test_the_change_form_carries_the_top_n_for_momentum_only(account: Account) -> None:
    plan = momentum_plan(account, date(2026, 11, 1))
    WatchItem.add_many(account, CANDIDATE_LIST)
    base = {
        "what": "change",
        "amount": "100.00",
        "buy_window_days": "7",
        "symbols": CANDIDATES,
        "effective": "next",
        "reason": "Hold three.",
    }
    same = PlanChangeForm(plan, date(2026, 11, 20), {**base, "top_n": "2"})
    assert not same.is_valid()
    assert "the candidates and the top N match" in str(same.errors)
    form = PlanChangeForm(
        plan, date(2026, 11, 20), {**base, "symbols": f"{CANDIDATES} OTHER", "top_n": "3"}
    )
    assert form.is_valid(), form.errors
    version = form.apply()
    assert (version.version, version.top_n, version.started_on) == (2, 3, date(2026, 12, 1))
    assert form.watched == ["OTHER"]
    index = MethodPlan.objects.create(
        account=Account.objects.create(name="Index", broker="B", kind="paper", owner=account.owner),
        method_id="index-dca",
        amount=D("100"),
        buy_window_days=7,
        symbols="INDEX",
        started_on=date(2026, 11, 1),
    )
    assert "top_n" not in PlanChangeForm(index, date(2026, 11, 20)).fields


# --- The engine -----------------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_engine_ranks_each_month_from_stored_adjusted_closes(account: Account) -> None:
    plant_candidates((2026, 11))
    # BETA splits 2-for-1 in 2026-05: the close halves, the adjusted close does not.
    DailyClose.objects.filter(symbol="BETA", date__gte=date(2026, 5, 1)).update(close=D("1"))
    plan = momentum_plan(account, date(2026, 11, 1))
    for symbol in ("ALPHA", "BETA"):
        JournalEntry.objects.create(
            account=account, date=date(2026, 11, 3), action="buy", symbol=symbol, amount=D("50")
        )
    JournalEntry.objects.create(
        account=account, date=date(2026, 12, 4), kind="skip", reason="Practice: read the lesson."
    )
    review = build_review(plan, JournalEntry.entries_for(account), date(2026, 12, 31))
    assert [(row.label, row.status, row.ranking) for row in review.months] == [
        ("2026-11", "done", "ALPHA, BETA"),
        ("2026-12", "skipped", "ALPHA, BETA"),
    ]
    [finding] = review.findings
    assert (finding.rule.id, finding.message, finding.explained) == (
        "rebalance-each-month",
        "No rebalance in 2026-12.",
        True,
    )
    check = next(c for c in review.checks if c.rule.id == "rebalance-each-month")
    assert check.status == "explained"
    assert review.momentum is not None
    ranking = review.momentum.ranking
    assert [p.symbol for p in ranking.places] == ["ALPHA", "BETA", "GAMMA"]
    assert [u.symbol for u in ranking.unranked] == ["DELTA"]
    # GAMMA's closes from the first window's start (2025-10) on, fourteen months, had none.
    assert review.momentum.unadjusted == 14
    assert review.next_action.symbols == ["ALPHA", "BETA"]


@pytest.mark.django_db
def test_an_index_plan_takes_the_path_it_took_before(account: Account) -> None:
    plan = MethodPlan.objects.create(
        account=account,
        method_id="index-dca",
        amount=D("100"),
        buy_window_days=7,
        symbols="INDEX",
        started_on=date(2026, 1, 1),
    )
    review = build_review(plan, [], date(2026, 2, 28))
    assert review.momentum is None
    assert [row.ranking for row in review.months] == ["", ""]
    assert {f.rule.id for f in review.findings} == {"one-buy-each-month"}


@pytest.mark.django_db
def test_the_rebalance_lists_sells_and_warns_of_a_wash_sale(account: Account) -> None:
    plant_candidates((2026, 11))
    plan = momentum_plan(account, date(2026, 10, 1))
    entry = JournalEntry.objects.create
    entry(account=account, date=date(2026, 10, 2), action="buy", symbol="GAMMA", amount=D("50"))
    entry(account=account, date=date(2026, 10, 2), action="buy", symbol="ALPHA", amount=D("50"))
    entry(account=account, date=date(2026, 10, 20), action="sell", symbol="ALPHA", amount=D("40"))
    ranking = ranking_for(plan, (2026, 11), price_series(CANDIDATES.split()))
    planned = rebalance(plan, ranking, date(2026, 11, 3))
    assert planned.parts == [("ALPHA", D("50.00")), ("BETA", D("50.00"))]
    assert planned.sells == ["GAMMA"]
    [warning] = planned.warnings
    assert warning.startswith("You sold ALPHA on 2026-10-20, 14 days before 2026-11-03.")
    assert "wash sale" in warning and "IRS Publication 550" in warning


# --- The pages ------------------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_method_page_shows_the_ranked_bars_with_a_table_and_how_to_read_them(
    owner_client: Client, running: MethodPlan
) -> None:
    account = running.account
    html = text(owner_client.get(f"/accounts/{account.pk}/method/?view=a"))
    month = this_month()
    assert f"The ranking for {month[0]}-{month[1]:02d}" in html
    assert "on adjusted closes." in html and "the latest full month, is left out" in html
    assert html.count('class="rank-bar"') == 3
    assert html.count("bar-out") == 1, "GAMMA, outside the top 2, is an outline"
    assert "How to read this." in html and "Lesson coming." in html
    tables = tables_in(html)
    ranking = next(t for t in tables if t[0][:3] == ("Rank", "Symbol", "12-1 return"))
    assert [(row[0], row[1], row[5]) for row in ranking[1:]] == [
        ("1", "ALPHA", "yes"),
        ("2", "BETA", "yes"),
        ("3", "GAMMA", "no"),
    ]
    assert ranking[3][2].startswith("-")
    assert "DELTA: no close stored in" in html
    assert "Get 5 years of history for DELTA" in html
    assert "Buy $50.00 of ALPHA" in html and "Buy $50.00 of BETA" in html
    assert "stored closes had no adjusted close" in html
    assert "Information, not advice." in html
    for view in ("b", "c"):
        assert "The ranking for" in text(
            owner_client.get(f"/accounts/{account.pk}/method/?view={view}")
        )
    tables = tables_in(text(owner_client.get(f"/accounts/{account.pk}/method/?view=b")))
    months = next(t for t in tables if t[0][0] == "Month")
    assert months[0][-1] == "Top 2"


@pytest.mark.django_db
def test_the_watch_list_shows_a_12_1_badge_only_on_a_momentum_account(
    owner_client: Client, running: MethodPlan
) -> None:
    account = running.account
    WatchItem.add_many(account, CANDIDATE_LIST)
    html = text(owner_client.get(f"/accounts/{account.pk}/"))
    assert '<th scope="col">12-1 return</th>' in html
    assert "▲ up +" in html and "▼ down -" in html
    assert "not ranked" in html
    assert "How to read this." in html
    other = Account.objects.create(name="Index", broker="B", kind="paper", owner=account.owner)
    WatchItem.add_many(other, ["ALPHA"])
    assert "12-1 return" not in text(owner_client.get(f"/accounts/{other.pk}/"))


@pytest.mark.django_db
def test_a_history_chart_shades_the_window_and_labels_the_excluded_month(
    owner_client: Client, running: MethodPlan
) -> None:
    account = running.account
    WatchItem.add_many(account, ["ALPHA"])
    html = text(owner_client.get(f"/accounts/{account.pk}/watch/ALPHA/?days=all"))
    assert 'class="chart-band-window"' in html and 'class="chart-band-excluded"' in html
    assert ">12-1 window</span>" in html and ">excluded</span>" in html
    assert "The 12-1 window for" in html and "How to read this." in html
    window = Window.for_month(*this_month())
    excluded = f"{window.excluded[0]}-{window.excluded[1]:02d}"
    strip = f"The lighter strip with a dashed edge is {excluded}, the latest full month"
    assert f'{strip}, labelled "excluded"' in html
    assert "Show the whole window" in html


@pytest.mark.django_db
def test_the_momentum_pages_are_the_owners_and_no_public_page_shows_them(
    client: Client, someone: User, running: MethodPlan
) -> None:
    account = running.account
    client.force_login(someone)
    assert client.get(f"/accounts/{account.pk}/method/").status_code == 404
    client.logout()
    for path in PUBLIC_PATHS:
        page = text(client.get(path))
        assert "ALPHA" not in page and "rank-bar" not in page and "<table" not in page


# --- Buys on paper --------------------------------------------------------------------------------


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> FakeAlpaca:
    fake = FakeAlpaca()
    monkeypatch.setattr(alpaca, "transport", httpx.MockTransport(fake.handle))
    monkeypatch.setattr(orders, "today", lambda: DAY)
    settings.ALPACA_PAPER_KEY_ID = KEY_ID
    settings.ALPACA_PAPER_SECRET_KEY = SECRET
    return fake


@pytest.mark.django_db
def test_confirm_buys_the_top_n_in_equal_parts_once(
    fake: FakeAlpaca, owner_client: Client, account: Account
) -> None:
    plant_candidates((2026, 10))
    account.alpaca = "paper"
    account.save()
    plan = momentum_plan(account, date(2026, 11, 1), practice_budget=D("1000.00"))
    stage = orders.month_buys(plan, DAY)
    assert [(b.symbol, b.notional) for b in stage.buys] == [
        ("ALPHA", D("50.00")),
        ("BETA", D("50.00")),
    ]
    assert stage.refusal == "" and stage.can_confirm
    page = text(owner_client.get(f"/accounts/{account.pk}/method/"))
    assert "Buy $50.00 of ALPHA" in page and '<button type="submit">Confirm</button>' in page
    owner_client.post(f"/accounts/{account.pk}/paper/confirm/")
    owner_client.post(f"/accounts/{account.pk}/paper/confirm/")
    assert [sent["client_order_id"] for sent in fake.posted] == [
        f"iw-{account.pk}-{plan.pk}-2026-11-ALPHA",
        f"iw-{account.pk}-{plan.pk}-2026-11-BETA",
    ], "one order per top-N symbol, and a second click sends nothing"
    assert PaperOrder.objects.count() == 2
    buys = JournalEntry.objects.filter(account=account).values_list("symbol", "amount")
    assert sorted(buys) == [("ALPHA", D("50.00")), ("BETA", D("50.00"))]


@pytest.mark.django_db
def test_confirm_is_refused_when_nothing_is_ranked(fake: FakeAlpaca, account: Account) -> None:
    account.alpaca = "paper"
    account.save()
    plan = momentum_plan(account, date(2026, 11, 1), practice_budget=D("1000.00"))
    stage = orders.month_buys(plan, DAY)
    assert stage.buys == []
    assert stage.refusal.startswith("No candidate is ranked for 2026-11")
    with pytest.raises(orders.ConfirmRefused):
        orders.confirm(plan, DAY, alpaca.paper_client())
    assert fake.posted == []
