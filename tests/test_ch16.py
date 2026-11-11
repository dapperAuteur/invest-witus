"""Chapter 16's checkpoint: reading what a company reports, from SEC EDGAR.

The first half checks the pure library (`invest_witus.filings`) on hand-made JSON in
`tests/fixtures/sec/`, shaped like the SEC's documents as read on November 10, 2026; the numbers
are small enough to check by hand. The second half runs the app's client, the refresh, the
nightly step, the button, the command and the symbol page against an `httpx.MockTransport`.
Nothing here reaches sec.gov. The symbols, names and CIKs are placeholders, not real securities.
"""

import json
from datetime import date, timedelta
from decimal import Decimal
from html import unescape
from io import StringIO
from pathlib import Path

import httpx
import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client
from django.utils import timezone
from pytest_django.fixtures import Settings

from invest_witus import filings as lib
from invest_witus_site.filings import refresh, sec
from invest_witus_site.filings.models import Filing, KeyFact, SecCompany, SecPause
from invest_witus_site.holdings.models import Account, Holding
from invest_witus_site.prices.models import ManualRun
from invest_witus_site.settings import DEFAULT_SEC_USER_AGENT, sec_filings_enabled
from invest_witus_site.watchlist.models import WatchItem

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sec"
USER_AGENT = "Invest.WitUS (https://invest.witus.online)"
SECRET = "test-only-cron-secret-0123456789"
CRON = "/api/cron/pull-prices/"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text("utf-8")


def facts(since: date | None = None) -> list[lib.Fact]:
    return lib.parse_companyfacts(fixture("companyfacts-CORPX.json"), since=since)


def numbers() -> lib.KeyNumbers:
    return lib.key_numbers(facts())


def row(table: lib.KeyNumbers, key: str) -> lib.Row:
    return next(each for each in table.rows if each.key == key)


# --- Names and addresses -------------------------------------------------------------------------


def test_a_symbol_is_written_the_way_edgar_writes_it() -> None:
    assert lib.sec_ticker(" class.b ") == "CLASS-B"
    assert lib.sec_ticker("CORPX") == "CORPX"


def test_the_cik_has_ten_digits_with_leading_zeros_and_nothing_else_is_a_cik() -> None:
    assert lib.padded_cik(1234567) == "0001234567"
    assert lib.padded_cik("0001234567") == "0001234567"
    for bad in ("12a", "", "12345678901", "-1"):
        with pytest.raises(lib.FilingsDataError):
            lib.padded_cik(bad)


def test_the_three_addresses_on_sec_gov() -> None:
    assert lib.submissions_url(1234567) == "https://data.sec.gov/submissions/CIK0001234567.json"
    assert (
        lib.companyfacts_url("1234567")
        == "https://data.sec.gov/api/xbrl/companyfacts/CIK0001234567.json"
    )
    assert (
        lib.document_url("0001234567", "0001234567-26-000002", "corpx-2.htm")
        == "https://www.sec.gov/Archives/edgar/data/1234567/000123456726000002/corpx-2.htm"
    )


# --- The ticker maps -----------------------------------------------------------------------------


def test_the_company_map_keeps_the_first_row_of_a_ticker() -> None:
    companies = lib.parse_company_tickers(fixture("company_tickers.json"))
    assert companies["CORPX"] == lib.Listing(1234567, "PLACEHOLDER CORP")
    assert set(companies) == {"CORPX", "TRUSTX", "CLASS-B"}


def test_the_fund_map_reads_its_columns_from_fields() -> None:
    funds = lib.parse_fund_tickers(fixture("company_tickers_mf.json"))
    assert funds["FUNDX"] == lib.Listing(3333333, "", fund=True)
    reordered = json.dumps({"fields": ["symbol", "cik"], "data": [["FUNDZ", 4]]})
    assert lib.parse_fund_tickers(reordered)["FUNDZ"].cik == 4
    with pytest.raises(lib.FilingsDataError, match="no cik or symbol"):
        lib.parse_fund_tickers(json.dumps({"fields": ["a"], "data": []}))


def test_classify_a_fund_a_company_a_share_class_and_nothing() -> None:
    companies = lib.parse_company_tickers(fixture("company_tickers.json"))
    funds = lib.parse_fund_tickers(fixture("company_tickers_mf.json"))
    assert lib.classify("fundx", companies, funds)[0] == "fund"
    assert lib.classify("CORPX", companies, funds) == ("company", companies["CORPX"])
    assert lib.classify("CLASS.B", companies, funds)[0] == "company"
    assert lib.classify("NONEX", companies, funds) == ("not listed", None)


# --- The submissions feed ------------------------------------------------------------------------


def test_submissions_become_rows_newest_first_with_their_dates() -> None:
    feed = lib.parse_submissions(fixture("submissions-CORPX.json"))
    assert (feed.cik, feed.name, feed.entity_type) == (1234567, "Placeholder Corp", "operating")
    assert feed.filings[0].form == "4"
    assert feed.filings[2].form == "10-K"
    assert feed.filings[2].report_date == date(2025, 12, 31)
    assert feed.filings[5].report_date is None, "an empty reportDate is no date"


def test_the_list_is_the_last_eight_10k_10q_and_8k_with_amendments() -> None:
    feed = lib.parse_submissions(fixture("submissions-CORPX.json"))
    chosen = lib.recent_reports(feed.filings)
    assert len(chosen) == 8
    assert [row.form for row in chosen] == [
        "8-K", "10-K", "8-K/A", "10-Q", "8-K", "10-Q", "8-K", "10-Q",
    ]  # fmt: skip
    assert "4" not in {row.form for row in chosen} and "S-8" not in {row.form for row in chosen}
    assert chosen[1].url(feed.cik).endswith("/1234567/000123456726000002/corpx-2.htm")


def test_a_column_shorter_than_the_forms_is_refused() -> None:
    body = json.loads(fixture("submissions-CORPX.json"))
    body["filings"]["recent"]["filingDate"].pop()
    with pytest.raises(lib.FilingsDataError, match="filingDate has 12 entries for 13 forms"):
        lib.parse_submissions(json.dumps(body))
    with pytest.raises(lib.FilingsDataError, match="not JSON"):
        lib.parse_submissions("<html>")


def test_a_trust_that_files_fund_forms_and_no_10k_is_a_fund() -> None:
    assert lib.is_fund_filer(lib.parse_submissions(fixture("submissions-TRUSTX.json")))
    assert not lib.is_fund_filer(lib.parse_submissions(fixture("submissions-CORPX.json")))


# --- The companyfacts feed -----------------------------------------------------------------------


def test_only_the_table_s_concepts_from_10k_and_10q_are_kept() -> None:
    kept = facts()
    assert {fact.concept for fact in kept} == {
        "us-gaap:Revenues",
        "us-gaap:ProfitLoss",
        "us-gaap:NetCashProvidedByUsedInOperatingActivities",
        "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
        "us-gaap:CommonStockSharesOutstanding",
        "us-gaap:LongTermDebtNoncurrent",
    }, "no dei cover-page count, no payables, no per-share figure"
    assert {fact.form for fact in kept} <= {"10-K", "10-Q"}, "the 8-K's copy is left out"
    assert all(isinstance(fact.value, Decimal) for fact in kept)


def test_a_figure_reported_twice_keeps_the_latest_filing() -> None:
    year_2023 = [
        f for f in facts() if f.concept == "us-gaap:Revenues" and f.end == date(2023, 12, 31)
    ]
    assert len(year_2023) == 1
    assert year_2023[0].value == Decimal(900), "restated in the next 10-K, not the original 890"
    assert year_2023[0].filed == date(2025, 2, 15)


def test_since_leaves_out_older_figures() -> None:
    assert any(f.end.year == 2019 for f in facts())
    assert not any(f.end.year == 2019 for f in facts(since=date(2020, 1, 1)))


def test_a_value_on_one_day_has_no_start_and_no_length() -> None:
    shares = next(f for f in facts() if f.concept == "us-gaap:CommonStockSharesOutstanding")
    assert shares.start is None and shares.days is None
    revenue = next(f for f in facts() if f.concept == "us-gaap:Revenues")
    assert revenue.days == 365


def test_a_value_that_is_not_a_number_is_refused() -> None:
    body = json.loads(fixture("companyfacts-CORPX.json"))
    body["facts"]["us-gaap"]["Revenues"]["units"]["USD"][0]["val"] = "lots"
    with pytest.raises(lib.FilingsDataError, match="val is not a number"):
        lib.parse_companyfacts(json.dumps(body))


# --- Quarters, years and the concept per line ----------------------------------------------------


def test_quarters_reported_directly_and_derived_from_year_to_date() -> None:
    revenue = [f for f in facts() if f.concept == "us-gaap:Revenues"]
    quarters = {f.end: f for f in lib.quarter_facts(revenue)}
    assert quarters[date(2025, 3, 31)].value == 260 and not quarters[date(2025, 3, 31)].derived_from
    assert quarters[date(2025, 6, 30)].value == 280, "the reported quarter, not 540 less 260"
    assert not quarters[date(2025, 6, 30)].derived_from
    third = quarters[date(2025, 9, 30)]
    assert third.value == 290 and third.start == date(2025, 7, 1)
    assert third.derived_from == "2025-01-01 to 2025-09-30 less 2025-01-01 to 2025-06-30"
    fourth = quarters[date(2025, 12, 31)]
    assert fourth.value == 270, "the year less nine months"
    assert fourth.form == "10-K"


def test_the_columns_are_the_newest_years_and_quarters() -> None:
    table = numbers()
    assert [p.end for p in table.years] == [
        date(2025, 12, 31), date(2024, 12, 31), date(2023, 12, 31), date(2019, 12, 31),
    ]  # fmt: skip
    assert [p.end for p in table.quarters] == [
        date(2025, 12, 31), date(2025, 9, 30), date(2025, 6, 30), date(2025, 3, 31),
    ]  # fmt: skip
    assert table.years[0].label == "Year to 2025-12-31"
    assert table.quarters[0].label == "3 months to 2025-12-31"


def test_each_line_takes_the_first_concept_it_finds_and_names_it() -> None:
    income = row(numbers(), "net_income")
    assert income.years[0].value == Decimal(-50)
    assert income.years[0].concept == "us-gaap:ProfitLoss", "NetIncomeLoss is not reported"
    assert (
        income.years[0].source
        == "us-gaap:ProfitLoss, 10-K filed 2026-02-10, 2025-01-01 to 2025-12-31"
    )
    assert income.concepts_used == ["us-gaap:ProfitLoss"]


def test_a_line_with_no_known_concept_says_so_instead_of_a_blank() -> None:
    cash = row(numbers(), "cash")
    assert all(cell.value is None for cell in [*cash.years, *cash.quarters])
    assert cash.years[0].missing == "not reported under a standard tag"
    assert cash.concepts_used == []


def test_a_value_on_one_day_is_read_on_the_period_s_last_day() -> None:
    shares = row(numbers(), "shares")
    assert [cell.value for cell in shares.quarters] == [
        Decimal(1000000),
        Decimal(1010000),
        None,
        None,
    ]
    assert shares.quarters[0].source.endswith("on 2025-12-31")


def test_free_cash_flow_is_derived_and_says_why_when_it_cannot_be() -> None:
    fcf = row(numbers(), "free_cash_flow")
    assert fcf.derived and fcf.label == "Free cash flow (derived)"
    assert fcf.years[0].value == Decimal(200)
    assert fcf.years[0].derived == "operating cash flow less capital expenditure"
    assert fcf.years[1].value is None
    assert (
        fcf.years[1].missing
        == "not worked out: capital expenditure is not reported under a standard tag"
    )
    assert fcf.quarters[0].value == Decimal(60), "(300 - 210) less (100 - 70)"
    assert "derived quarters" in fcf.quarters[0].derived


def test_free_cash_flow_comes_right_after_capital_expenditure() -> None:
    assert [each.key for each in numbers().rows] == [
        "revenue", "net_income", "operating_cash_flow", "capex", "free_cash_flow",
        "shares", "cash", "long_term_debt",
    ]  # fmt: skip


def test_no_figures_make_an_empty_table() -> None:
    assert lib.key_numbers([]).empty


@pytest.mark.parametrize(
    ("value", "unit", "words"),
    [
        (Decimal("478830000000"), "USD", "$478.83 billion"),
        (Decimal("-1200000"), "USD", "-$1.20 million"),
        (Decimal("14532259000"), "shares", "14.53 billion shares"),
        (Decimal("2500000000000"), "USD", "$2.50 trillion"),
        (Decimal("950"), "USD", "$950"),
    ],
)
def test_large_figures_in_plain_words(value: Decimal, unit: str, words: str) -> None:
    assert lib.short_number(value, unit) == words


# --- The client ----------------------------------------------------------------------------------


class FakeSec:
    """Answers the five documents from the fixtures, a status per path when told to, and
    records every request."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.status: dict[str, int] = {}
        self.bodies: dict[str, str] = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path in self.status:
            return httpx.Response(self.status[path], text="refused")
        if path in self.bodies:
            return httpx.Response(200, text=self.bodies[path])
        names = {
            "/files/company_tickers.json": "company_tickers.json",
            "/files/company_tickers_mf.json": "company_tickers_mf.json",
            "/submissions/CIK0001234567.json": "submissions-CORPX.json",
            "/submissions/CIK0007654321.json": "submissions-TRUSTX.json",
            "/api/xbrl/companyfacts/CIK0001234567.json": "companyfacts-CORPX.json",
        }
        if path not in names:
            return httpx.Response(404, text="not found")
        return httpx.Response(200, text=fixture(names[path]))

    def paths(self) -> list[str]:
        return [request.url.path for request in self.requests]


@pytest.fixture
def fake_sec(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> FakeSec:
    fake = FakeSec()
    settings.SEC_FILINGS_ENABLED = True
    monkeypatch.setattr(sec, "transport", httpx.MockTransport(fake))
    return fake


@pytest.mark.django_db
def test_every_request_declares_the_app_and_asks_for_gzip(fake_sec: FakeSec) -> None:
    refresh.refresh_symbol("CORPX")
    assert len(fake_sec.requests) == 4
    for request in fake_sec.requests:
        assert request.headers["User-Agent"] == USER_AGENT
        assert request.headers["Accept-Encoding"] == "gzip, deflate"
        assert "@" not in request.headers["User-Agent"], "never a person's email"


def test_the_throttle_spaces_requests_four_a_second(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [100.0]
    slept: list[float] = []

    def fake_sleep(seconds: float) -> None:
        slept.append(round(seconds, 6))

    monkeypatch.setattr(sec, "clock", lambda: now[0])
    monkeypatch.setattr(sec, "sleep", fake_sleep)
    throttle = sec.Throttle(4)
    for _ in range(4):
        throttle.wait()
    assert slept == [0.25, 0.5, 0.75], "the first goes at once, then one every quarter second"
    now[0] = 200.0
    throttle.wait()
    assert slept == [0.25, 0.5, 0.75], "after a quiet second, no wait"
    assert sec.REQUESTS_PER_SECOND == 4 and sec.REQUESTS_PER_SECOND < 10


@pytest.mark.django_db
@pytest.mark.parametrize("status", [403, 429])
def test_a_refusal_pauses_every_request_for_ten_minutes(fake_sec: FakeSec, status: int) -> None:
    fake_sec.status["/files/company_tickers.json"] = status
    with pytest.raises(sec.SecError) as refused:
        refresh.refresh_symbol("CORPX")
    assert refused.value.retry_later and refused.value.status == status
    pause = SecPause.objects.get()
    assert pause.status == status
    assert timedelta(minutes=9) < pause.until - timezone.now() <= timedelta(minutes=10)
    sent = len(fake_sec.requests)
    with pytest.raises(sec.SecError, match="waits until"):
        sec.get("https://data.sec.gov/submissions/CIK0001234567.json")
    assert len(fake_sec.requests) == sent, "nothing is sent during the pause"


@pytest.mark.django_db
def test_a_pause_that_has_ended_lets_requests_through(fake_sec: FakeSec) -> None:
    sec.pause(429, timezone.now() - timedelta(minutes=11))
    assert sec.paused_until() is None
    assert sec.get("https://www.sec.gov/files/company_tickers.json")


@pytest.mark.django_db
def test_a_network_failure_and_a_500_are_errors_without_a_pause(
    fake_sec: FakeSec, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_sec.status["/files/company_tickers.json"] = 500
    with pytest.raises(sec.SecError, match="answered 500") as error:
        sec.get("https://www.sec.gov/files/company_tickers.json")
    assert not error.value.retry_later
    assert not SecPause.objects.exists()

    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow", request=request)

    monkeypatch.setattr(sec, "transport", httpx.MockTransport(broken))
    with pytest.raises(sec.SecError, match="ConnectTimeout"):
        sec.get("https://www.sec.gov/files/company_tickers.json")


# --- The refresh ---------------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_company_s_refresh_stores_eight_filings_and_its_figures(fake_sec: FakeSec) -> None:
    done = refresh.refresh_symbol("corpx")
    assert (done.symbol, done.kind, done.filings) == ("CORPX", "company", 8)
    assert fake_sec.paths() == [
        "/files/company_tickers.json",
        "/files/company_tickers_mf.json",
        "/submissions/CIK0001234567.json",
        "/api/xbrl/companyfacts/CIK0001234567.json",
    ]
    company = SecCompany.objects.get(symbol="CORPX")
    assert (company.cik, company.name, company.problem) == ("0001234567", "Placeholder Corp", "")
    assert company.filings_fetched_at and company.facts_fetched_at
    newest = Filing.objects.filter(symbol="CORPX").order_by("-filing_date").first()
    assert newest is not None and newest.form == "8-K"
    assert newest.document_url.startswith("https://www.sec.gov/Archives/edgar/data/1234567/")
    assert KeyFact.objects.filter(symbol="CORPX").count() == done.facts > 0


@pytest.mark.django_db
def test_a_second_refresh_in_a_day_reads_no_ticker_map_and_replaces_the_rows(
    fake_sec: FakeSec,
) -> None:
    refresh.refresh_symbol("CORPX")
    refresh.forget_maps()
    fake_sec.requests.clear()
    refresh.refresh_symbol("CORPX")
    assert fake_sec.paths() == [
        "/submissions/CIK0001234567.json",
        "/api/xbrl/companyfacts/CIK0001234567.json",
    ], "the stored CIK is good for a day"
    assert Filing.objects.filter(symbol="CORPX").count() == 8, "replaced, not doubled"


@pytest.mark.django_db
def test_the_maps_are_read_once_a_day_per_process(fake_sec: FakeSec) -> None:
    now = timezone.now()
    refresh.ticker_maps(now)
    refresh.ticker_maps(now + timedelta(hours=23))
    assert len(fake_sec.requests) == 2
    refresh.ticker_maps(now + timedelta(hours=25))
    assert len(fake_sec.requests) == 4


@pytest.mark.django_db
def test_a_fund_in_the_fund_map_asks_for_nothing_more(fake_sec: FakeSec) -> None:
    done = refresh.refresh_symbol("FUNDX")
    assert done.kind == "fund"
    assert len(fake_sec.requests) == 2, "the two maps only"
    assert not Filing.objects.filter(symbol="FUNDX").exists()


@pytest.mark.django_db
def test_a_symbol_held_as_an_etf_is_a_fund_without_a_request(
    fake_sec: FakeSec, django_user_model: type[User]
) -> None:
    owner = django_user_model.objects.create_user("holder")
    account = Account.objects.create(owner=owner, name="Real", broker="Example Broker")
    Holding.objects.create(account=account, symbol="CORPX", kind=Holding.Kind.ETF)
    assert refresh.refresh_symbol("CORPX").kind == "fund"
    assert fake_sec.requests == []


@pytest.mark.django_db
def test_a_trust_in_the_company_map_that_files_fund_forms_is_a_fund(fake_sec: FakeSec) -> None:
    done = refresh.refresh_symbol("TRUSTX")
    assert done.kind == "fund"
    assert SecCompany.objects.get(symbol="TRUSTX").kind == "fund"
    assert "/api/xbrl/companyfacts/CIK0007654321.json" not in fake_sec.paths()


@pytest.mark.django_db
def test_an_unlisted_symbol_is_not_listed(fake_sec: FakeSec) -> None:
    assert refresh.refresh_symbol("NONEX").kind == "not listed"
    assert SecCompany.objects.get(symbol="NONEX").cik == ""


@pytest.mark.django_db
def test_a_company_with_no_companyfacts_keeps_its_filings(fake_sec: FakeSec) -> None:
    fake_sec.status["/api/xbrl/companyfacts/CIK0001234567.json"] = 404
    done = refresh.refresh_symbol("CORPX")
    assert done.filings == 8 and done.facts == 0
    assert done.note == "SEC EDGAR has no XBRL figures for this company"


@pytest.mark.django_db
def test_a_failed_refresh_keeps_the_old_rows_and_the_problem(fake_sec: FakeSec) -> None:
    refresh.refresh_symbol("CORPX")
    fake_sec.bodies["/submissions/CIK0001234567.json"] = "not json"
    with pytest.raises(lib.FilingsDataError):
        refresh.refresh_symbol("CORPX")
    company = SecCompany.objects.get(symbol="CORPX")
    assert company.problem.startswith("unexpected data: not JSON")
    assert Filing.objects.filter(symbol="CORPX").count() == 8


# --- The nightly step ----------------------------------------------------------------------------


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("owner")


@pytest.fixture
def account(owner: User) -> Account:
    account = Account.objects.create(owner=owner, name="Practice", broker="Example Broker")
    for symbol in ("CORPX", "FUNDX", "NONEX"):
        WatchItem.objects.create(account=account, symbol=symbol)
    return account


@pytest.fixture
def cron(settings: Settings, tmp_path: Path) -> None:
    settings.CRON_SECRET = SECRET
    settings.TIINGO_API_KEY = ""
    settings.PRICES_CSV_DIR = tmp_path


def call_cron(client: Client) -> dict[str, object]:
    return client.get(CRON, headers={"Authorization": f"Bearer {SECRET}"}).json()


@pytest.mark.django_db
def test_the_cron_refreshes_every_watched_symbol_once(
    client: Client, fake_sec: FakeSec, account: Account, cron: None
) -> None:
    body = call_cron(client)
    assert body["filings"] == {
        "refreshed": ["CORPX"],
        "funds": ["FUNDX"],
        "not_listed": ["NONEX"],
        "failed": {},
        "skipped": [],
        "stopped": "",
    }
    sent = len(fake_sec.requests)
    again = call_cron(client)
    assert again["filings"]["refreshed"] == [], "a repeated cron asks for nothing"  # type: ignore[index]
    assert len(fake_sec.requests) == sent


@pytest.mark.django_db
def test_the_cron_stops_at_a_refusal_and_lists_the_rest(
    client: Client, fake_sec: FakeSec, account: Account, cron: None
) -> None:
    fake_sec.status["/submissions/CIK0001234567.json"] = 429
    body = call_cron(client)
    step = body["filings"]
    assert step["stopped"] == "refused"  # type: ignore[index]
    assert "CORPX" in step["failed"]  # type: ignore[index]
    assert step["skipped"] == ["FUNDX", "NONEX"]  # type: ignore[index]
    assert "requests" in body, "the prices stand"


@pytest.mark.django_db
def test_the_cron_stops_at_its_time_limit(fake_sec: FakeSec, account: Account) -> None:
    run = refresh.refresh_watched(time_limit=-1.0)
    assert run.stopped == "time limit" and run.skipped == ["CORPX", "FUNDX", "NONEX"]
    assert fake_sec.requests == []


@pytest.mark.django_db
def test_the_cron_body_is_unchanged_with_filings_off(
    client: Client, account: Account, cron: None
) -> None:
    assert "filings" not in call_cron(client)


@pytest.mark.django_db
def test_a_symbol_whose_refresh_failed_is_due_again(fake_sec: FakeSec, account: Account) -> None:
    now = timezone.now()
    refresh.refresh_watched(now)
    assert refresh.due_symbols(now) == []
    SecCompany.objects.filter(symbol="CORPX").update(problem="SEC EDGAR answered 500")
    assert refresh.due_symbols(now) == ["CORPX"]
    assert refresh.due_symbols(now + timedelta(hours=21)) == ["CORPX", "FUNDX", "NONEX"]


# --- The command ---------------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_command_refreshes_named_symbols_and_prints_the_user_agent(fake_sec: FakeSec) -> None:
    out = StringIO()
    call_command("refresh_filings", "corpx", "fundx", stdout=out)
    text = out.getvalue()
    assert f"User-Agent: {USER_AGENT}" in text
    assert "CORPX: company, 8 filing(s)" in text
    assert "FUNDX: fund, 0 filing(s)" in text


@pytest.mark.django_db
def test_the_command_refuses_with_filings_off_or_nothing_named(settings: Settings) -> None:
    with pytest.raises(CommandError, match="SEC_FILINGS=off"):
        call_command("refresh_filings", "CORPX")
    settings.SEC_FILINGS_ENABLED = True
    with pytest.raises(CommandError, match="at least one symbol"):
        call_command("refresh_filings")


@pytest.mark.django_db
def test_the_command_reports_a_refusal(fake_sec: FakeSec) -> None:
    fake_sec.status["/files/company_tickers.json"] = 403
    err = StringIO()
    with pytest.raises(CommandError):
        call_command("refresh_filings", "CORPX", stdout=StringIO(), stderr=err)
    assert "answered 403" in err.getvalue()


# --- The symbol page -----------------------------------------------------------------------------


def page(account: Account, symbol: str = "CORPX") -> str:
    return f"/accounts/{account.pk}/watch/{symbol}/"


def button(account: Account, symbol: str = "CORPX") -> str:
    return f"/accounts/{account.pk}/watch/{symbol}/filings/"


def text(response: object) -> str:
    return unescape(response.content.decode())  # type: ignore[attr-defined]


@pytest.mark.django_db
def test_the_page_lists_the_filings_with_links_that_open_on_sec_gov(
    client: Client, fake_sec: FakeSec, owner: User, account: Account
) -> None:
    refresh.refresh_symbol("CORPX")
    client.force_login(owner)
    response = client.get(page(account))
    assert response.status_code == 200
    body = text(response)
    assert '<h2 id="filings-heading">Filings</h2>' in body
    link = (
        '<a href="https://www.sec.gov/Archives/edgar/data/1234567/000123456726000002/corpx-2.htm" '
        'target="_blank" rel="noopener">Read the 10-K on sec.gov'
    )
    assert link in body
    assert body.count('target="_blank" rel="noopener">Read the ') == 8
    assert "Annual report" in body and "Current report (a major event), amended" in body
    assert f"Source: SEC EDGAR, fetched {timezone.localdate():%Y-%m-%d}" in body


@pytest.mark.django_db
def test_the_page_shows_key_numbers_with_their_form_period_and_concept(
    client: Client, fake_sec: FakeSec, owner: User, account: Account
) -> None:
    refresh.refresh_symbol("CORPX")
    client.force_login(owner)
    body = text(client.get(page(account)))
    assert '<h3 id="key-numbers-heading">Key numbers</h3>' in body
    assert "Year to 2025-12-31" in body and "3 months to 2025-12-31" in body
    assert (
        'title="us-gaap:Revenues, 10-K filed 2026-02-10, 2025-01-01 to 2025-12-31">$1,100' in body
    )
    assert "10-Q, derived" in body
    assert "Free cash flow (derived)" in body
    assert "not reported under a standard tag" in body
    assert "<strong>How to read this.</strong>" in body
    assert f"Source: SEC EDGAR (XBRL), as of {timezone.localdate():%Y-%m-%d}" in body
    assert "Revenue, net income and free cash flow by fiscal year" in body
    assert 'class="bar-down"' in body, "the loss is drawn left of the zero line"


@pytest.mark.django_db
def test_the_page_links_the_sec_s_guide_to_reading_a_10k(
    client: Client, owner: User, account: Account, settings: Settings
) -> None:
    settings.SEC_FILINGS_ENABLED = True
    client.force_login(owner)
    body = text(client.get(page(account)))
    assert "<summary>How to read a 10-K</summary>" in body
    assert 'href="https://www.sec.gov/answers/reada10k.htm" target="_blank" rel="noopener"' in body
    assert "No filings stored yet." in body and "Refresh filings now" in body


@pytest.mark.django_db
def test_a_fund_says_it_has_no_company_filings(
    client: Client, fake_sec: FakeSec, owner: User, account: Account
) -> None:
    refresh.refresh_symbol("FUNDX")
    client.force_login(owner)
    body = text(client.get(page(account, "FUNDX")))
    assert "No company filings: this is a fund; see the issuer's page." in body
    assert "Key numbers" not in body


@pytest.mark.django_db
def test_an_unlisted_symbol_says_edgar_lists_no_company(
    client: Client, fake_sec: FakeSec, owner: User, account: Account
) -> None:
    refresh.refresh_symbol("NONEX")
    client.force_login(owner)
    assert "SEC EDGAR lists no company under NONEX." in text(client.get(page(account, "NONEX")))


@pytest.mark.django_db
def test_a_pause_shows_filings_are_not_available_with_the_last_list(
    client: Client, fake_sec: FakeSec, owner: User, account: Account
) -> None:
    refresh.refresh_symbol("CORPX")
    sec.pause(429)
    client.force_login(owner)
    response = client.get(page(account))
    assert response.status_code == 200
    body = text(response)
    assert "Filings are not available right now." in body
    assert "SEC EDGAR answered 429" in body
    assert "The list below is the last one stored." in body
    assert "Traceback" not in body


@pytest.mark.django_db
def test_the_page_says_filings_are_off_and_offers_no_button(
    client: Client, owner: User, account: Account
) -> None:
    client.force_login(owner)
    body = text(client.get(page(account)))
    assert "Filings are off on this copy of the app" in body
    assert "Refresh filings now" not in body


# --- Refresh filings now -------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_button_fetches_and_says_what_it_stored(
    client: Client, fake_sec: FakeSec, owner: User, account: Account
) -> None:
    client.force_login(owner)
    response = client.post(button(account), follow=True)
    assert response.redirect_chain[-1][0] == page(account) + "#filings-heading"
    body = text(response)
    assert "Fetched CORPX's filings from SEC EDGAR: 8 filings listed" in body
    assert ManualRun.objects.filter(kind=ManualRun.Kind.FILINGS, key="CORPX").exists()


@pytest.mark.django_db
def test_a_second_press_inside_ten_minutes_is_refused_without_a_request(
    client: Client, fake_sec: FakeSec, owner: User, account: Account
) -> None:
    client.force_login(owner)
    client.post(button(account))
    sent = len(fake_sec.requests)
    body = text(client.post(button(account), follow=True))
    assert "less than 10 minutes ago" in body
    assert len(fake_sec.requests) == sent


@pytest.mark.django_db
@pytest.mark.parametrize("status", [403, 429])
def test_a_refusal_during_the_button_is_a_message_not_an_error(
    client: Client, fake_sec: FakeSec, owner: User, account: Account, status: int
) -> None:
    fake_sec.status["/files/company_tickers.json"] = status
    client.force_login(owner)
    response = client.post(button(account), follow=True)
    assert response.status_code == 200
    body = text(response)
    assert f"Filings are not available right now: SEC EDGAR answered {status}" in body


@pytest.mark.django_db
def test_data_it_cannot_read_is_a_message_not_an_error(
    client: Client, fake_sec: FakeSec, owner: User, account: Account
) -> None:
    fake_sec.bodies["/submissions/CIK0001234567.json"] = "[]"
    client.force_login(owner)
    response = client.post(button(account), follow=True)
    assert response.status_code == 200
    assert "SEC EDGAR sent data this app could not read" in text(response)


@pytest.mark.django_db
def test_the_button_needs_a_sign_in_a_post_the_owner_and_a_watched_symbol(
    client: Client, fake_sec: FakeSec, owner: User, account: Account, django_user_model: type[User]
) -> None:
    signed_out = client.post(button(account))
    assert signed_out.status_code == 302 and "login" in signed_out["Location"]
    client.force_login(owner)
    assert client.get(button(account)).status_code == 405
    assert client.post(button(account, "OTHERX")).status_code == 404
    someone = django_user_model.objects.create_user("someone")
    client.force_login(someone)
    assert client.post(button(account)).status_code == 404
    assert fake_sec.requests == []


@pytest.mark.django_db
def test_the_button_with_filings_off_says_so(client: Client, owner: User, account: Account) -> None:
    client.force_login(owner)
    assert "Filings are off on this copy" in text(client.post(button(account), follow=True))


# --- Settings and the public pages ---------------------------------------------------------------


def test_the_default_user_agent_is_the_app_name_and_address_and_off_means_off() -> None:
    assert DEFAULT_SEC_USER_AGENT == USER_AGENT
    assert "@" not in DEFAULT_SEC_USER_AGENT, "never a person's email"
    assert sec_filings_enabled("") and sec_filings_enabled("on")
    assert not sec_filings_enabled(" OFF ") and not sec_filings_enabled("off")


def test_env_example_lists_the_two_names() -> None:
    text_ = (Path(__file__).resolve().parent.parent / ".env.example").read_text("utf-8")
    assert "\nSEC_USER_AGENT=\n" in text_ and "\nSEC_FILINGS=\n" in text_


@pytest.mark.django_db
def test_no_public_page_mentions_filings(client: Client) -> None:
    for path in ("/", "/faq/", "/privacy/", "/terms/"):
        body = text(client.get(path))
        assert "Key numbers" not in body and "sec.gov/Archives" not in body
