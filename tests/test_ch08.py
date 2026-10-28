"""Chapter 08 checkpoint: closes in the app's own table, the pull that fills it (idempotent; one
vendor refusal never stops the rest), the cron route's three answers, the owner's account page
valued at the latest close, and public pages that still show no price."""

import json
from datetime import date, timedelta
from decimal import Decimal
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path

import httpx
import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.test import Client
from django.urls import resolve
from django.utils import timezone
from pytest_django.fixtures import Settings

from invest_witus.holdings import Position
from invest_witus.prices.csv_file import PricePoint
from invest_witus.valuation import STALE_AFTER_DAYS, Quote, value_positions
from invest_witus_site.holdings.models import Account, Holding, Snapshot, SnapshotLine
from invest_witus_site.prices import pull as pull_module
from invest_witus_site.prices import sources
from invest_witus_site.prices.models import DailyClose
from invest_witus_site.prices.pull import pull, symbol_universe, watch_symbols
from invest_witus_site.prices.sources import (
    CsvPrices,
    PriceSourceError,
    TiingoEod,
    parse_tiingo,
    source_from_settings,
)

BASE_DIR = Path(settings.BASE_DIR)
FIXTURES = BASE_DIR / "tests" / "fixtures" / "tiingo"
# Not secrets: they exist only inside this test run.
TEST_KEY = "test-only-tiingo-key"
SECRET = "test-only-cron-secret-0123456789"
CRON = "/api/cron/pull-prices/"
# The days the Tiingo fixtures cover: made-up closes for placeholder symbols, in the shape the
# documentation describes (the thirteen fields per day), never real quotes.
SINCE, UNTIL = date(2026, 10, 20), date(2026, 10, 22)
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


# --- Fixtures: a CSV folder, a fake Tiingo, an owner with a statement --------------------------


@pytest.fixture(autouse=True)
def no_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    """The courtesy pause between symbols is a second; the tests do not wait for it."""
    monkeypatch.setattr(pull_module, "PAUSE_SECONDS", 0.0)


def write_csv(path: Path, rows: list[tuple[date, str]]) -> None:
    lines = ["date,close"] + [f"{day.isoformat()},{close}" for day, close in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture
def csv_folder(tmp_path: Path, settings: Settings) -> Path:
    """Two symbols in chapter 02's format, dated relative to today so the cron's seven-day
    window finds them, and the settings pointed at the folder with no Tiingo key."""
    today = timezone.localdate()
    write_csv(
        tmp_path / "INDEX.csv",
        [
            (today - timedelta(days=9), "98.00"),  # outside the cron's window
            (today - timedelta(days=2), "100.00"),
            (today - timedelta(days=1), "101.25"),
        ],
    )
    write_csv(tmp_path / "OTHER.csv", [(today - timedelta(days=1), "20.5")])
    settings.TIINGO_API_KEY = ""
    settings.PRICES_CSV_DIR = tmp_path
    return tmp_path


class FakeTiingo:
    """Tiingo's end-of-day endpoint as far as this app can see it: a token header, a path per
    ticker, a JSON list of days. Each ticker's answer is a fixture file; a ticker without one is
    a 404; `status` forces another answer for one ticker."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.status: dict[str, int] = {}

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.headers.get("Authorization") != f"Token {TEST_KEY}":
            return httpx.Response(401, json={"detail": "Invalid token."})
        symbol = request.url.path.split("/")[3]  # /tiingo/daily/<ticker>/prices
        if symbol in self.status:
            return httpx.Response(self.status[symbol], json={"detail": "forced by the test"})
        fixture = FIXTURES / f"{symbol}.json"
        if not fixture.is_file():
            return httpx.Response(404, json={"detail": "Not found."})
        return httpx.Response(
            200, content=fixture.read_bytes(), headers={"Content-Type": "application/json"}
        )


@pytest.fixture
def tiingo(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> FakeTiingo:
    fake = FakeTiingo()
    monkeypatch.setattr(sources, "transport", httpx.MockTransport(fake.handle))
    settings.TIINGO_API_KEY = TEST_KEY
    return fake


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("owner", email="owner@example.com")


@pytest.fixture
def account(owner: User) -> Account:
    """One statement with four lines: two symbols a pull can price, one no source knows, and
    cash. Chapter 05's `SnapshotLine.save` catalogs the holdings; the cash one gets its kind."""
    account = Account.objects.create(
        name="Practice", broker="Example Broker", kind="paper", owner=owner
    )
    snapshot = Snapshot.objects.create(account=account, as_of=date(2026, 10, 25), source="test")
    for symbol, shares in (("INDEX", "2.5"), ("OTHER", "10"), ("NONE", "1"), ("CASH", "500")):
        SnapshotLine.objects.create(snapshot=snapshot, symbol=symbol, shares=Decimal(shares))
    Holding.objects.filter(account=account, symbol="CASH").update(kind=Holding.Kind.CASH)
    return account


@pytest.fixture
def valued_account(account: Account) -> Account:
    """The same account after a pull stored closes: a fresh one for INDEX, an old one for OTHER."""
    today = timezone.localdate()
    DailyClose.upsert(
        "INDEX",
        [
            PricePoint(today - timedelta(days=2), Decimal("100")),
            PricePoint(today - timedelta(days=1), Decimal("101.23")),
        ],
        "tiingo",
    )
    stale_day = today - timedelta(days=STALE_AFTER_DAYS + 3)
    DailyClose.upsert("OTHER", [PricePoint(stale_day, Decimal("20.005"))], "csv")
    return account


class TableRows(HTMLParser):
    """Every table row as a tuple of its cells' text, as chapter 05's test read the statements."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[tuple[str, ...]] = []
        self._cells: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
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
            self.rows.append(tuple(self._cells))
            self._cells = None


def rows_in(html: str) -> list[tuple[str, ...]]:
    parser = TableRows()
    parser.feed(html)
    return parser.rows


def stored() -> list[tuple[str, date, Decimal, str, object]]:
    return list(DailyClose.objects.values_list("symbol", "date", "close", "source", "fetched_at"))


# --- The table ------------------------------------------------------------------------------


@pytest.mark.django_db
def test_upsert_writes_each_day_once_and_a_rerun_changes_nothing() -> None:
    points = [
        PricePoint(date(2026, 10, 20), Decimal("100.00")),
        PricePoint(date(2026, 10, 21), Decimal("101.25")),
    ]
    first = DailyClose.upsert("index", points, "csv")  # lower-case in, upper-case stored
    assert (first.inserted, first.updated, first.unchanged) == (2, 0, 0)
    before = stored()
    again = DailyClose.upsert("INDEX", points, "csv")
    assert (again.inserted, again.updated, again.unchanged) == (0, 0, 2)
    assert stored() == before, "a repeated pull must leave every column alone, fetched_at too"
    assert [row[0] for row in before] == ["INDEX", "INDEX"]


@pytest.mark.django_db
def test_a_corrected_close_replaces_the_row_and_counts_as_updated() -> None:
    day = date(2026, 10, 20)
    DailyClose.upsert("INDEX", [PricePoint(day, Decimal("100.00"))], "tiingo")
    stamp = DailyClose.objects.get().fetched_at
    later = stamp + timedelta(hours=1)
    corrected = DailyClose.upsert(
        "INDEX", [PricePoint(day, Decimal("100.05"))], "tiingo", now=later
    )
    assert (corrected.inserted, corrected.updated, corrected.unchanged) == (0, 1, 0)
    row = DailyClose.objects.get()
    assert (row.close, row.fetched_at) == (Decimal("100.05"), later)


@pytest.mark.django_db
def test_a_close_keeps_six_places_and_a_float_is_refused() -> None:
    DailyClose.upsert("INDEX", [PricePoint(date(2026, 10, 20), Decimal("1.23456789"))], "csv")
    assert DailyClose.objects.get().close == Decimal("1.234568")
    row = DailyClose(symbol="INDEX", date=date(2026, 10, 21), close=1.5, source="csv")
    with pytest.raises(TypeError, match="float"):
        row.save()


@pytest.mark.django_db
def test_latest_for_picks_the_newest_day_per_symbol() -> None:
    DailyClose.upsert(
        "INDEX",
        [
            PricePoint(date(2026, 10, 20), Decimal("100")),
            PricePoint(date(2026, 10, 22), Decimal("102")),
            PricePoint(date(2026, 10, 21), Decimal("101")),
        ],
        "tiingo",
    )
    DailyClose.upsert("OTHER", [PricePoint(date(2026, 10, 21), Decimal("20.5"))], "csv")
    latest = DailyClose.latest_for(["index", "OTHER", "NONE"])
    assert latest == {
        "INDEX": Quote(Decimal("102"), date(2026, 10, 22), "tiingo"),
        "OTHER": Quote(Decimal("20.5"), date(2026, 10, 21), "csv"),
    }
    assert DailyClose.latest_for([]) == {}


# --- The two sources ------------------------------------------------------------------------


def test_the_csv_source_reads_chapter_02s_files_and_names_a_missing_one(csv_folder: Path) -> None:
    today = timezone.localdate()
    source = CsvPrices(csv_folder)
    points = source.closes("INDEX", today - timedelta(days=7), today)
    assert [(point.day, str(point.close)) for point in points] == [
        (today - timedelta(days=2), "100.00"),
        (today - timedelta(days=1), "101.25"),
    ]
    with pytest.raises(PriceSourceError, match="no file NONE.csv") as refused:
        source.closes("NONE", today - timedelta(days=7), today)
    assert (refused.value.symbol, refused.value.retry_later) == ("NONE", False)


def test_tiingo_is_asked_with_the_token_in_the_header_and_answers_decimals(
    tiingo: FakeTiingo,
) -> None:
    points = TiingoEod(TEST_KEY).closes("INDEX", SINCE, UNTIL)
    request = tiingo.requests[0]
    assert (request.url.host, request.url.path) == ("api.tiingo.com", "/tiingo/daily/INDEX/prices")
    assert dict(request.url.params) == {
        "startDate": "2026-10-20",
        "endDate": "2026-10-22",
        "format": "json",
    }
    assert request.headers["Authorization"] == f"Token {TEST_KEY}"
    assert TEST_KEY not in str(request.url), "the key travels in a header, never in a URL"
    assert [(point.day, point.close) for point in points] == [
        (date(2026, 10, 20), Decimal("101.23")),
        (date(2026, 10, 21), Decimal("101.90")),
        (date(2026, 10, 22), Decimal("100.4")),
    ]
    assert all(type(point.close) is Decimal for point in points)


def test_tiingo_parsing_keeps_the_number_exact_and_takes_a_bare_date() -> None:
    (point,) = parse_tiingo("INDEX", '[{"date": "2026-10-22", "close": 0.1}]')
    assert point == PricePoint(date(2026, 10, 22), Decimal("0.1"))
    assert point.close == Decimal("0.1") and point.close != Decimal(0.1)
    (whole,) = parse_tiingo("INDEX", '[{"date": "2026-10-22T00:00:00.000Z", "close": 100}]')
    assert whole.close == Decimal("100") and str(whole.close) == "100"


@pytest.mark.parametrize(
    ("body", "problem"),
    [
        ("not json", "not JSON"),
        ("{}", "expected a list of days"),
        ("[1]", "expected an object per day"),
        ('[{"date": "nope", "close": 1}]', "not a date"),
        ('[{"close": 1}]', "not a date"),
        ('[{"date": "2026-10-22", "close": "1"}]', "close is not a number"),
        ('[{"date": "2026-10-22", "close": true}]', "close is not a number"),
        ('[{"date": "2026-10-22", "close": -1}]', "close must be positive"),
    ],
)
def test_tiingo_parsing_refuses_a_body_it_does_not_understand(body: str, problem: str) -> None:
    with pytest.raises(PriceSourceError, match=problem):
        parse_tiingo("INDEX", body)


def test_the_source_follows_the_key(settings: Settings, tmp_path: Path) -> None:
    settings.TIINGO_API_KEY = ""
    settings.PRICES_CSV_DIR = tmp_path
    csv = source_from_settings()
    assert isinstance(csv, CsvPrices) and csv.folder == tmp_path
    settings.TIINGO_API_KEY = TEST_KEY
    assert isinstance(source_from_settings(), TiingoEod)
    with pytest.raises(ValueError, match="TIINGO_API_KEY"):
        TiingoEod("")


# --- The pull -------------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_refusal_for_one_symbol_is_recorded_and_the_others_continue(tiingo: FakeTiingo) -> None:
    result = pull(TiingoEod(TEST_KEY), ["INDEX", "NONE", "OTHER"], SINCE, UNTIL)
    assert list(result.failed) == ["NONE"]
    assert result.failed["NONE"].startswith("Tiingo answered 404")
    assert (result.requests, result.skipped) == (3, [])
    assert (result.counts.inserted, result.counts.updated, result.counts.unchanged) == (5, 0, 0)
    assert sorted({row[0] for row in stored()}) == ["INDEX", "OTHER"]


@pytest.mark.django_db
def test_a_rate_limit_stops_the_run_and_lists_what_was_left(tiingo: FakeTiingo) -> None:
    tiingo.status["INDEX"] = 429
    result = pull(TiingoEod(TEST_KEY), ["INDEX", "OTHER"], SINCE, UNTIL)
    assert "429" in result.failed["INDEX"]
    assert (result.requests, result.skipped) == (1, ["OTHER"])
    assert stored() == []


@pytest.mark.django_db
def test_a_bad_key_fails_each_symbol_without_showing_the_key(tiingo: FakeTiingo) -> None:
    result = pull(TiingoEod("wrong-key"), ["INDEX"], SINCE, UNTIL)
    assert result.failed["INDEX"].startswith("Tiingo answered 401")
    assert "wrong-key" not in result.failed["INDEX"]


@pytest.mark.django_db
def test_a_run_stays_inside_the_hourly_budget(csv_folder: Path) -> None:
    today = timezone.localdate()
    result = pull(CsvPrices(csv_folder), ["INDEX", "OTHER", "NONE"], today, today, budget=2)
    assert (result.requests, result.skipped) == (2, ["NONE"])
    assert pull_module.REQUESTS_PER_RUN == 50 and pull_module.DAYS_BACK == 7


@pytest.mark.django_db
def test_the_pause_sits_between_symbols_not_after_the_last(
    csv_folder: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    slept: list[float] = []
    monkeypatch.setattr(pull_module.time, "sleep", slept.append)
    today = timezone.localdate()
    pull(CsvPrices(csv_folder), ["INDEX", "OTHER", "NONE"], today, today, pause=0.25)
    assert slept == [0.25, 0.25]


@pytest.mark.django_db
def test_the_symbol_universe_is_every_held_symbol_once_without_cash(
    account: Account, owner: User
) -> None:
    second = Account.objects.create(
        name="Retirement", broker="Other Broker", kind="retirement", owner=owner
    )
    snapshot = Snapshot.objects.create(account=second, as_of=date(2026, 10, 25))
    for symbol in ("INDEX", "MORE"):
        SnapshotLine.objects.create(snapshot=snapshot, symbol=symbol, shares=Decimal("1"))
    assert symbol_universe() == ["INDEX", "MORE", "NONE", "OTHER"]
    assert watch_symbols() == set(), "chapter 09's placeholder"


# --- The command ----------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_command_pulls_the_held_symbols_and_runs_twice_without_harm(
    csv_folder: Path, account: Account
) -> None:
    since = (timezone.localdate() - timedelta(days=3)).isoformat()
    out, err = StringIO(), StringIO()
    call_command("pull_prices", "--since", since, stdout=out, stderr=err)
    assert "Source csv" in out.getvalue() and "3 symbol(s), 3 request(s)" in out.getvalue()
    assert "Inserted 3, updated 0, unchanged 0." in out.getvalue()
    assert "Failed NONE: no file NONE.csv" in err.getvalue()
    out = StringIO()
    call_command("pull_prices", "--since", since, stdout=out, stderr=StringIO())
    assert "Inserted 0, updated 0, unchanged 3." in out.getvalue()


@pytest.mark.django_db
def test_the_command_takes_named_symbols_and_refuses_a_future_date(csv_folder: Path) -> None:
    out, err = StringIO(), StringIO()
    call_command("pull_prices", "--symbols", "other, none, other", stdout=out, stderr=err)
    assert "2 symbol(s), 2 request(s)" in out.getvalue()
    assert "Inserted 1," in out.getvalue() and "Failed NONE" in err.getvalue()
    tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
    with pytest.raises(CommandError, match="after today"):
        call_command("pull_prices", "--since", tomorrow)
    out = StringIO()
    call_command("pull_prices", stdout=out)
    assert "Nothing to pull" in out.getvalue()


# --- The cron route -------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_cron_route_fails_closed_without_a_secret(
    client: Client, settings: Settings, csv_folder: Path, account: Account
) -> None:
    settings.CRON_SECRET = ""
    response = client.get(CRON, headers={"Authorization": "Bearer anything"})
    assert response.status_code == 503
    assert response.json() == {"error": "CRON_SECRET is not set"}
    assert stored() == []


@pytest.mark.django_db
@pytest.mark.parametrize(
    "header", ["", "Bearer wrong", f"Token {SECRET}", f"bearer {SECRET}", f"Bearer {SECRET} "]
)
def test_the_cron_route_refuses_anything_but_the_bearer_secret(
    client: Client, settings: Settings, csv_folder: Path, account: Account, header: str
) -> None:
    settings.CRON_SECRET = SECRET
    response = client.get(CRON, headers={"Authorization": header} if header else {})
    assert response.status_code == 403
    assert stored() == []


@pytest.mark.django_db
def test_the_cron_route_pulls_the_last_seven_days_and_answers_counts(
    client: Client, settings: Settings, csv_folder: Path, account: Account
) -> None:
    settings.CRON_SECRET = SECRET
    today = timezone.localdate()
    headers = {"Authorization": f"Bearer {SECRET}", "x-vercel-cron-schedule": "0 6 * * *"}
    response = client.get(CRON, headers=headers)
    assert response.status_code == 200
    assert response.json() == {
        "source": "csv",
        "since": (today - timedelta(days=7)).isoformat(),
        "until": today.isoformat(),
        "symbols": ["INDEX", "NONE", "OTHER"],
        "requests": 3,
        "inserted": 3,
        "updated": 0,
        "unchanged": 0,
        "failed": {"NONE": f"no file NONE.csv in {csv_folder}"},
        "skipped": [],
        "schedule": "0 6 * * *",
    }
    again = client.get(CRON, headers={"Authorization": f"Bearer {SECRET}"}).json()
    assert (again["inserted"], again["unchanged"], again["schedule"]) == (0, 3, "")


@pytest.mark.django_db
def test_the_cron_route_is_get_only(client: Client, settings: Settings) -> None:
    settings.CRON_SECRET = SECRET
    assert client.post(CRON, headers={"Authorization": f"Bearer {SECRET}"}).status_code == 405


def test_vercel_calls_the_route_once_a_day_after_midnight_eastern() -> None:
    config = json.loads((BASE_DIR / "vercel.json").read_text(encoding="utf-8"))
    assert config["crons"] == [{"path": CRON, "schedule": "0 6 * * *"}]
    assert resolve(CRON).url_name == "cron-pull-prices"


# --- The value math -------------------------------------------------------------------------


def test_values_are_shares_times_close_in_decimal_rounded_to_cents() -> None:
    today = date(2026, 10, 28)
    positions = [
        Position("INDEX", Decimal("2.5")),
        Position("OTHER", Decimal("10")),
        Position("NONE", Decimal("1")),
    ]
    quotes = {
        "INDEX": Quote(Decimal("101.23"), date(2026, 10, 27), "tiingo"),
        "OTHER": Quote(Decimal("20.005"), date(2026, 10, 20), "csv"),
    }
    valuation = value_positions(positions, quotes, today)
    index, other, none = valuation.lines
    assert (index.value, index.stale) == (Decimal("253.08"), False)  # 253.075 rounds half up
    assert (other.value, other.stale) == (Decimal("200.05"), True)  # eight days old
    assert (none.quote, none.value, none.stale) == (None, None, False)
    assert valuation.total == Decimal("453.13")
    assert valuation.unpriced == ["NONE"]
    assert all(type(line.value) is Decimal for line in (index, other))


# --- The owner's page -----------------------------------------------------------------------


@pytest.mark.django_db
def test_the_account_pages_need_a_sign_in(client: Client, valued_account: Account) -> None:
    for path in ("/accounts/", f"/accounts/{valued_account.pk}/"):
        response = client.get(path)
        assert response.status_code == 302
        assert response["Location"] == f"/auth/witus/login/?next={path}"


@pytest.mark.django_db
def test_the_account_page_is_the_owners_only(
    client: Client, valued_account: Account, django_user_model: type[User]
) -> None:
    someone = django_user_model.objects.create_user("someone")
    client.force_login(someone)
    assert client.get(f"/accounts/{valued_account.pk}/").status_code == 404
    html = client.get("/accounts/").content.decode()
    assert "No accounts yet." in html and "Practice" not in html


@pytest.mark.django_db
def test_the_owner_sees_each_line_valued_with_the_closes_date(
    client: Client, owner: User, valued_account: Account
) -> None:
    today = timezone.localdate()
    client.force_login(owner)
    response = client.get(f"/accounts/{valued_account.pk}/")
    assert response.status_code == 200
    html = response.content.decode()
    fresh = (today - timedelta(days=1)).isoformat()
    old = (today - timedelta(days=STALE_AFTER_DAYS + 3)).isoformat()
    assert rows_in(html) == [
        ("Symbol", "Shares", "Close", "As of", "Source", "Value"),
        ("CASH", "500.00", "1.00", "2026-10-25", "statement", "500.00"),
        ("INDEX", "2.50", "101.23", fresh, "tiingo", "253.08"),
        ("NONE", "1.00", "no price yet"),
        ("OTHER", "10.00", "20.005", f"{old} stale", "csv", "200.05"),
        ("Total of the priced lines", "953.13"),
    ]
    assert "Statement as of 2026-10-25" in html
    assert "No price yet for NONE" in html
    assert "Information, not advice." in html


@pytest.mark.django_db
def test_the_account_list_and_the_header_link_appear_only_signed_in(
    client: Client, owner: User, valued_account: Account
) -> None:
    assert 'href="/accounts/"' not in client.get("/").content.decode()
    client.force_login(owner)
    home = client.get("/").content.decode()
    assert '<a href="/accounts/">Accounts</a>' in home
    listing = client.get("/accounts/").content.decode()
    assert f'<a href="/accounts/{valued_account.pk}/">Practice</a>' in listing
    assert "<table" not in listing, "the list names accounts; the values are one page further"


@pytest.mark.django_db
@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_public_pages_show_no_table_and_do_not_link_the_account_pages(
    client: Client, valued_account: Account, path: str
) -> None:
    html = client.get(path).content.decode()
    assert "<table" not in html.lower()
    assert "/accounts/" not in html


def test_env_example_names_the_two_variables() -> None:
    text = (BASE_DIR / ".env.example").read_text(encoding="utf-8")
    assert "\nTIINGO_API_KEY=\n" in text and "\nCRON_SECRET=\n" in text
    assert "https://www.tiingo.com/signup" in text and "openssl rand" in text
