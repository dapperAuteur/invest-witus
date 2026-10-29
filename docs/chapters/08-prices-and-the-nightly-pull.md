# Chapter 08: Prices and the nightly pull

**Starts from:** tag `v07`. **Ends at:** tag `v08`.
**Written against:** Python 3.14.10, uv 0.13.6, Django 5.2.18, httpx 0.28.1, and Tiingo's documentation and
pricing pages, Alpaca's market data pages and Vercel's cron pages as read on October 28, 2026. Vendors change
their pages; when one and this text disagree, read the page again and note the date.
**Goal:** one closing price per symbol per day in the app's own table, filled once a night by a cron that
Vercel calls with a secret, and the signed-in owner's accounts valued at the latest stored close with the
close's date beside every line. No page ever asks a vendor, no public page shows a price, and the pull can run
twice without harm.
**Time:** 3 to 4 hours for the code and tests. The owner's Tiingo key and the cron secret take 15 minutes.

The listings in this chapter are not typed in by hand. `scripts/render_chapter.py` pastes the real files from
tag `v08` into the chapter text, so what you read and what the tests run are the same bytes.

## What you will learn

- **A `Protocol` as a seam:** two price sources with one shape, so the pull, the command and the cron never
  know which one answered, and the tests use the cheap one.
- **An idempotent job:** an upsert that writes each day once, counts what it did, and leaves a repeated run
  with nothing to do. Why a cron on Vercel's Hobby plan has to be written this way.
- **JSON without floats:** `json.loads(..., parse_float=Decimal)`, and a parser that refuses what it does not
  understand instead of guessing.
- **A management command** with two arguments, its own output streams, and the one error it raises.
- **A cron on Vercel:** `vercel.json`'s `crons`, UTC, the Hobby plan's hour, no retries, and the project's
  `CRON_SECRET` arriving as a bearer token, compared in constant time.
- **`login_required` and an ownership check:** a page for the signed-in owner, a 404 for anyone else, and a
  test that every public page still has no table and no link to it.
- **The newest row per group** with `values().annotate(Max())`, and a template filter.
- **A fake vendor from JSON fixtures** through httpx's `MockTransport`, as chapter 07 faked a provider.

## Before the code: what the vendors say

**Which prices, from where.** The PRD (section 7.4) and research 05 settled this for phase 1: holdings entered
from statements are valued with end-of-day closes from Tiingo's free plan, pulled once a night with the owner's
own key; holdings inside an Alpaca account carry their own prices on Alpaca's position objects and need no
feed, which is chapter 11's work. This chapter builds the first half and leaves a labeled hook for the second.
Every value is shown to the signed-in owner of the account and to nobody else, because the free plan's license
allows nothing more, and because the PRD says no public page renders a price, a chart or a holding.

**What Tiingo's pages say.** Daily prices for one ticker come from
`https://api.tiingo.com/tiingo/daily/<ticker>/prices`, with `startDate`, `endDate` and `format` as query
parameters (Tiingo, n.d.-b). The token goes in the `Authorization` header as `Token <value>`, or in a `token`
query parameter; the examples send `Content-Type: application/json` (Tiingo, n.d.-a). Each day in the answer
carries `date`, `open`, `high`, `low`, `close`, `volume`, the adjusted versions of the four prices and the
volume, `divCash` and `splitFactor`; the page shows no example body, and describes `date` only as "The date
this data pertains to" (Tiingo, n.d.-b), so the parser in this chapter reads the first ten characters of that
field, which is the date whether it arrives bare or as a timestamp, and the fixture in the tests says so. When
the numbers arrive: "Most US Equity prices are available at 5:30 PM EST, however exchanges may send corrections
until 8 PM EST", and "Mutual Fund NAVs are available after 12 AM EST", with the four price fields holding the
NAV for a fund (Tiingo, n.d.-b). The free plan, "Starter" on the pricing page and "Basic" in the overview, is
$0 for 50 requests an hour, 1,000 a day, 500 unique symbols a month and 1 GB a month; its license is "Internal
Use Only", which the page defines: "Internal use means you may only use the data for your own personal use and
you may not display or share the data with another person or organization" (Tiingo, n.d.-d). The overview adds
"We do not rate limit to minute or second" and that the daily count resets at midnight Eastern (Tiingo, n.d.-c).
For later, when other people use the app: Tiingo's developer program covers software "where their software
requires users to supply their own Tiingo API Token", with "Tiingo must be clearly attributed as the data
source" and never the user's password (Tiingo, n.d.-e). Tiingo's full Terms of Use page answered a Cloudflare
challenge to every fetch on the day of writing, as it did to the research; the owner reads it in a browser
(task 09, and PRD open item 3). Decisions log, row 70.

**What Alpaca's pages say, and why none of it is built here.** A position in a paper account carries
`current_price`, `lastday_price` ("Last day's asset price per share based on the closing value of the last
trading day") and `market_value` (Alpaca, n.d.-a). Daily bars exist too, with a `feed` parameter that defaults
to `sip`, but "iex" is "the only feed that can be used without a subscription" (Alpaca, 2026c), SIP history
needs an `end` "at least 15 minutes old" (Alpaca, 2026b), and "As an Alpaca Paper Only Account holder, you are
only entitled to receive and make use of IEX market data" (Alpaca, n.d.-b). Whether paper keys reach the data
API at all is not stated on the pages read. So Alpaca stays chapter 11's: positions for Alpaca accounts, read
from the account itself. The `source` column and the `PriceSource` Protocol below leave room for an Alpaca bars
source as research 05's backup, without a line of it written now. Decisions log, row 71.

**What Vercel's pages say about cron.** A cron is an entry in `vercel.json` with a `path` and a `schedule`;
Vercel makes "an HTTP GET request to your project's production deployment URL" at that path, with the user
agent `vercel-cron/1.0` and an `x-vercel-cron-schedule` header naming the expression that fired (Vercel,
2026a). Expressions have five fields, "The timezone is always UTC", names like `MON` are not supported, and the
day-of-month and day-of-week fields cannot both be set (Vercel, 2026a). On the Hobby plan a job runs at most
once a day, and its precision is "Per-hour (±59 min)": `0 6 * * *` fires anywhere between 06:00:00 and
06:59:59 (Vercel, 2026c). "Vercel will not retry an invocation if a cron job fails"; delivery is "best effort",
a run can be missed, and "Cron delivery can also occasionally invoke the same scheduled run more than once", so
jobs "should be resilient to both missed runs and duplicate runs", which the page spells as idempotent (Vercel,
2026b). A redirect ends the run without being followed. And the secret: add `CRON_SECRET` to the project, "a
random string of at least 16 characters", and "The value of the variable will be automatically sent as an
`Authorization` header when Vercel invokes your cron job", with the `Bearer` prefix (Vercel, 2026b). Vercel's
sample answers 401 to a bad header; this route answers 403, since there is nothing a caller could do to
authenticate interactively, and 503 when the secret is unset, so a deploy that forgot the variable fails closed
and the log says why. Decisions log, row 72.

**Three design rules that follow.** First, *the table is the product*: the page reads the table, the pull
writes it, and the vendor is spoken to once a night, which is what both the PRD's acceptance list and the free
plan's budget want. Second, *the pull is idempotent*: it asks for the last seven days every night, writes a day
only when the stored close differs, and so a missed night is filled by the next, a duplicate run writes
nothing, and a vendor's evening correction replaces its row. Third, *one symbol's refusal is not the run's*: an
unknown ticker is recorded for that symbol and the next one is tried; only a rate limit stops the run, because
the next request would fail the same way.

**The schedule.** `0 6 * * *`: 06:00 to 06:59 UTC is 01:00 to 01:59 Eastern in winter and 02:00 to 02:59 in
summer, after Tiingo's "after 12 AM EST" for fund NAVs in both halves of the year, and hours before the US
open. It runs every day; a Sunday run finds nothing new and writes nothing, at the cost of one request per
symbol against a budget of a thousand.

## Steps

### 08.1 The tests

Listing 08-1, Filename: `tests/test_ch08.py`:

```python
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
```

Things to notice:

- **`FakeTiingo` is the vendor as far as the app can see it.** A token header checked, a path per ticker, a
  JSON file per ticker, a 404 for a ticker without one, and `status` to force a 429 for one test. The fixture
  below has the thirteen fields the documentation lists, with made-up numbers for the placeholder symbols
  `INDEX` and `OTHER`: never real quotes.
- **`csv_folder` dates its rows relative to today,** because the cron route asks for the last seven days from
  today and the test must pass next month too. The row nine days back is outside the window on purpose.
- **`stored()` is the whole table as tuples,** `fetched_at` included. The idempotency test compares the table
  before and after a second run, not just the counts.
- **`no_pause` is `autouse`.** The real pull waits a second between symbols; the tests set the constant to zero
  and one test checks the pause is placed between symbols, not after the last.
- **The cron tests go through the HTTP client with headers,** so the route's three answers are tested as Vercel
  would see them, including a `Token` prefix and a trailing space.
- **The owner page test reads the table row by row**, with `TableRows`, the way chapter 05 read the statements
  page, and asserts the values, the dates and the words "no price yet" and "stale" in their cells.

Listing 08-2, Filename: `tests/fixtures/tiingo/INDEX.json`:

```json
[
  {"date": "2026-10-20T00:00:00.000Z", "open": 100.75, "high": 102.00, "low": 100.50, "close": 101.23, "volume": 1200, "adjOpen": 100.75, "adjHigh": 102.00, "adjLow": 100.50, "adjClose": 101.23, "adjVolume": 1200, "divCash": 0.0, "splitFactor": 1.0},
  {"date": "2026-10-21T00:00:00.000Z", "open": 101.30, "high": 102.10, "low": 101.00, "close": 101.90, "volume": 980, "adjOpen": 101.30, "adjHigh": 102.10, "adjLow": 101.00, "adjClose": 101.90, "adjVolume": 980, "divCash": 0.0, "splitFactor": 1.0},
  {"date": "2026-10-22T00:00:00.000Z", "open": 101.80, "high": 101.95, "low": 100.10, "close": 100.4, "volume": 1430, "adjOpen": 101.80, "adjHigh": 101.95, "adjLow": 100.10, "adjClose": 100.4, "adjVolume": 1430, "divCash": 0.0, "splitFactor": 1.0}
]
```

Run the tests:

Listing 08-3, Terminal:

```sh
uv run pytest tests/test_ch08.py
```

```text
tests/test_ch08.py:24: in <module>
    from invest_witus.valuation import STALE_AFTER_DAYS, Quote, value_positions
E   ModuleNotFoundError: No module named 'invest_witus.valuation'
=========================== short test summary info ============================
ERROR tests/test_ch08.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 1.32s
```

Red at import: the first module the tests name does not exist. No package is added this chapter; httpx came
with chapter 07.

### 08.2 Three names and one app

The settings gain the prices app in `INSTALLED_APPS` and three names at the end. Everything else is as chapter
07 left it.

Listing 08-4, Filename: `src/invest_witus_site/settings.py`:

```python
"""Django settings for Invest.WitUS.

Anything that differs between your laptop and a server comes from an environment variable, with a
safe default for the laptop. The names are listed in `.env.example`; values never go in git.
Chapter 06 added the server's side: the database from `DATABASE_URL`, a secret key the server
must set, the HTTPS cookie and proxy settings, the folder `collectstatic` fills, and logging a
server can show. Chapter 07 added the four names of Sign in with WitUS; chapter 08 the price
source and the cron secret, at the end.
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

- **`TIINGO_API_KEY` is the switch between the sources.** Set, the pull talks to Tiingo; empty, it reads CSV
  files from `PRICES_CSV_DIR`, which defaults to `data/private/prices/`, inside the folder git ignores. The
  name follows the ecosystem's `*_API_KEY` habit; Tiingo's own word is "token".
- **`CRON_SECRET` is Vercel's name,** and the only one Vercel will send. Empty means the route refuses to run.

Listing 08-5, Filename: `.env.example`:

```sh
# Copy to .env (git ignores it) and run with: uv run --env-file .env python manage.py runserver
# Names only; values never go in git. On Vercel the same names are set in the project's
# Environment Variables page (chapter 06); the laptop and the server share one settings file.

# "1" shows Django's debug pages and serves static files from runserver. Never "1" on a server:
# settings.py refuses to start on Vercel with it set.
DJANGO_DEBUG=1

# Required whenever DJANGO_DEBUG is not 1, which is every server. Make one with:
#   uv run python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
# Leave empty on your laptop: with DJANGO_DEBUG=1 a labeled dev-only key is used instead.
DJANGO_SECRET_KEY=

# Comma-separated host names the site answers to. Default: localhost,127.0.0.1
# Production: invest.witus.online (Vercel's own *.vercel.app host names are added on their own).
DJANGO_ALLOWED_HOSTS=

# Comma-separated origins, scheme and host, that may post the site's forms.
# Production: https://invest.witus.online
DJANGO_CSRF_TRUSTED_ORIGINS=

# The database. Empty: SQLite at data/private/invest-witus.sqlite3. On Vercel the Neon integration
# sets both names: DATABASE_URL is the pooled connection the app uses, DATABASE_URL_UNPOOLED the
# direct one that migrations use (`manage.py migrate --database direct`).
# Shape: postgresql://user:password@host/name?sslmode=require
# If the Vercel connect dialog added a prefix (the production project has STORAGE_), the
# prefixed names STORAGE_DATABASE_URL and STORAGE_DATABASE_URL_UNPOOLED work too.
DATABASE_URL=
DATABASE_URL_UNPOOLED=

# The owner's one-time, non-interactive superuser on a new database (chapter 06). These three are
# set in the shell for that one command, never written to a file:
#   DJANGO_SUPERUSER_USERNAME  DJANGO_SUPERUSER_EMAIL  DJANGO_SUPERUSER_PASSWORD
#   ... vercel env run -e production -- uv run python manage.py createsuperuser --noinput --database direct

# Vercel Web Analytics (chapter 06a). Both are set on Vercel, per environment, never on a laptop: the
# two script tags render only with VERCEL=1 (Vercel's own variable) and VERCEL_ANALYTICS=1, so
# Production can be on while Preview stays off. VERCEL_ANALYTICS_SCRIPT_PATH is the script path the
# project's Analytics page shows once Analytics is enabled (the quickstart writes it as
# /<unique-path>/script.js): copy it from there. Left empty, the FALLBACK /_vercel/insights/script.js
# is used, the shared route the quickstart names, not a value read from your dashboard. If the
# dashboard shows no page views after a deploy, set the path to what the page shows.
VERCEL_ANALYTICS=
VERCEL_ANALYTICS_SCRIPT_PATH=

# Sign in with WitUS (chapter 07): OpenID Connect against the ecosystem's identity provider. The
# client is OFF until WITUS_OIDC_CLIENT_SECRET is set; until then the sign-in route shows the stub
# page from chapter 04 and the site deploys as before. The owner mints the secret in the witus repo
# (`node scripts/gen-oidc-client.mjs invest`), which prints one value for the provider
# (WITUS_OIDC_SECRET__INVEST, on witus-online) and the same value for this app. Mark it Secret on
# Vercel. A learner's copy of the app is not registered with the provider and leaves it empty.
WITUS_OIDC_CLIENT_SECRET=
# The issuer the provider asserts in its discovery document. Default: https://accounts.witus.online,
# the ecosystem's accounts host as read on October 28, 2026. The discovery document is read from
# under it, and its own `issuer` field must match.
WITUS_OIDC_ISSUER=
# This app's client id at the provider. Default: witus-invest (the registry's `witus-<slug>`).
WITUS_OIDC_CLIENT_ID=
# The scopes asked for. Default: openid email profile. `openid` is required.
WITUS_OIDC_SCOPES=

# Prices (chapter 08). The nightly pull stores one close per symbol per day. With TIINGO_API_KEY
# set it asks Tiingo's end-of-day endpoint with your own token (https://www.tiingo.com/signup,
# then https://www.tiingo.com/account/api/token; the free plan allows 50 requests an hour, 1,000 a
# day and 500 unique symbols a month, "Internal Use Only", as read on October 28, 2026). Left
# empty, the pull reads <SYMBOL>.csv files in chapter 02's format from data/private/prices/
# (PRICES_CSV_DIR changes the folder), which is what a laptop uses.
TIINGO_API_KEY=
PRICES_CSV_DIR=
# What Vercel sends as "Authorization: Bearer <value>" to /api/cron/pull-prices/ once a day
# (vercel.json). Set it on Vercel only, Production, marked Sensitive; at least 16 random
# characters, for example: openssl rand -hex 24
# Unset, the route answers 503 and runs nothing, so a deploy without it fails closed.
CRON_SECRET=
```

### 08.3 The value math, in the library

The arithmetic is three lines and belongs beside chapter 01's `to_money`, where it needs no database and the
test can plant its own numbers.

Listing 08-6, Filename: `src/invest_witus/valuation.py`:

```python
"""What a statement's lines are worth at the latest stored close, and when a close is too old.

Pure functions over plain values, like `holdings.py`: no database and no vendor. The Django view
(chapter 08) hands in the lines as `Position`s and one `Quote` per symbol, and prints what comes
back. A symbol with no quote is not valued and is listed, never shown as zero.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from invest_witus.holdings import Position
from invest_witus.money import to_money

# A close older than this many calendar days is marked stale. Five covers a weekend, a market
# holiday and one missed nightly run; anything older deserves a look at the cron's log.
STALE_AFTER_DAYS = 5
ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class Quote:
    """One close for one symbol: the number, the day it is for, and where it came from."""

    close: Decimal
    as_of: date
    source: str


@dataclass(frozen=True, slots=True)
class ValuedLine:
    """One statement line with the quote used, or `None` and no value when there is no close."""

    symbol: str
    shares: Decimal
    quote: Quote | None
    value: Decimal | None
    stale: bool


@dataclass(frozen=True, slots=True)
class Valuation:
    """Every line, the total of the priced ones, and the symbols that have no close yet."""

    lines: list[ValuedLine]
    total: Decimal
    unpriced: list[str]


def value_line(position: Position, quote: Quote | None, today: date) -> ValuedLine:
    """Shares times close, rounded to cents half up (chapter 01's `to_money`). Both factors are
    Decimals; a float in either place fails here with a TypeError instead of a wrong number."""
    if quote is None:
        return ValuedLine(position.symbol, position.shares, None, None, False)
    value = to_money(position.shares * quote.close)
    stale = (today - quote.as_of).days > STALE_AFTER_DAYS
    return ValuedLine(position.symbol, position.shares, quote, value, stale)


def value_positions(
    positions: Iterable[Position], quotes: Mapping[str, Quote], today: date
) -> Valuation:
    """Value each position with its symbol's quote. The total adds the priced lines only."""
    lines = [value_line(position, quotes.get(position.symbol), today) for position in positions]
    total = to_money(sum((line.value for line in lines if line.value is not None), ZERO))
    unpriced = [line.symbol for line in lines if line.quote is None]
    return Valuation(lines, total, unpriced)
```

- **`Quote` is one close with its date and source.** The page prints all three; the PRD's acceptance list says
  "Every displayed price carries its date and source."
- **`value_line` multiplies two Decimals and rounds once,** with `to_money`. The planted example in the test is
  2.5 shares at 101.23: 253.075, which rounds half up to 253.08, the rounding chapter 01 chose. A float in
  either factor fails on the multiplication with a `TypeError`; nothing here converts.
- **No quote, no value.** A line without a close keeps `None`, is listed in `unpriced`, and stays out of the
  total. Showing zero would be a lie with a currency sign on it.
- **`stale` is a calendar test,** more than five days between the close and today. Five covers a weekend, a
  holiday and one missed night.

### 08.4 The table

Listing 08-7, Filename: `src/invest_witus_site/prices/apps.py`:

```python
from django.apps import AppConfig


class PricesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "invest_witus_site.prices"
    verbose_name = "Prices"
```

Listing 08-8, Filename: `src/invest_witus_site/prices/models.py`:

```python
"""One close per symbol per day, in the app's own table, so a page never asks a vendor.

The nightly pull (`pull.py`) writes here through `upsert`, which is idempotent: a day already
stored with the same close is left alone, so a cron that runs twice, or a pull repeated by hand,
changes nothing. The owner's pages read `latest_for`, the newest stored close per symbol, and
show its date beside the value.
"""

import datetime
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db import models
from django.db.models import Max, Q
from django.utils import timezone

from invest_witus.prices.csv_file import PricePoint
from invest_witus.valuation import Quote

# Six decimal places, like shares in chapter 05: a vendor's raw close has two to four, and the
# column keeps what it was sent rather than rounding a price to cents before it is multiplied.
PRICE_PLACES = 6
PRICE_STEP = Decimal(1).scaleb(-PRICE_PLACES)


def to_close(value: Decimal) -> Decimal:
    """Round to the column's places, halves away from zero, before the database rounds for us."""
    return value.quantize(PRICE_STEP, rounding=ROUND_HALF_UP)


@dataclass(frozen=True, slots=True)
class UpsertCount:
    """What one `upsert` did. Added together across symbols by the pull."""

    inserted: int = 0
    updated: int = 0
    unchanged: int = 0

    def __add__(self, other: UpsertCount) -> UpsertCount:
        return UpsertCount(
            self.inserted + other.inserted,
            self.updated + other.updated,
            self.unchanged + other.unchanged,
        )

    def __str__(self) -> str:
        return f"inserted {self.inserted}, updated {self.updated}, unchanged {self.unchanged}"


class DailyClose(models.Model):
    """The closing price of one symbol on one day, and where and when the app got it."""

    symbol: models.CharField[str, str] = models.CharField(max_length=20)
    date: models.DateField[datetime.date, datetime.date] = models.DateField(
        help_text="The trading day the close is for."
    )
    close: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=18, decimal_places=PRICE_PLACES
    )
    source: models.CharField[str, str] = models.CharField(
        max_length=40, help_text="Which source answered: tiingo, or csv on a laptop."
    )
    fetched_at: models.DateTimeField[datetime.datetime, datetime.datetime] = models.DateTimeField(
        help_text="When the pull wrote or last changed this row."
    )

    class Meta:
        ordering = ["symbol", "-date"]
        constraints = [
            models.UniqueConstraint(
                fields=["symbol", "date"], name="close_once_per_symbol_and_day"
            ),
        ]
        verbose_name = "daily close"
        verbose_name_plural = "daily closes"

    def __str__(self) -> str:
        return f"{self.symbol} {self.date:%Y-%m-%d} {self.close}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """The same guards as a statement line: the symbol's case, the rounding, and no float."""
        if isinstance(self.close, float):
            raise TypeError(f"close must be a Decimal, not a float ({self.close!r})")
        self.symbol = self.symbol.strip().upper()
        self.close = to_close(self.close)
        super().save(*args, **kwargs)

    def quote(self) -> Quote:
        return Quote(close=self.close, as_of=self.date, source=self.source)

    @classmethod
    def upsert(
        cls,
        symbol: str,
        points: Iterable[PricePoint],
        source: str,
        now: datetime.datetime | None = None,
    ) -> UpsertCount:
        """Write each day once. A day already stored with the same close and source is left
        alone, `fetched_at` included, so a re-run changes nothing. A different close (a vendor's
        correction, or a second source) replaces the row and counts as an update."""
        symbol = symbol.strip().upper()
        wanted = {point.day: to_close(point.close) for point in points}
        existing = {row.date: row for row in cls.objects.filter(symbol=symbol, date__in=wanted)}
        stamp = now or timezone.now()
        inserted = updated = unchanged = 0
        new_rows: list[DailyClose] = []
        for day, close in sorted(wanted.items()):
            row = existing.get(day)
            if row is None:
                new_rows.append(
                    cls(symbol=symbol, date=day, close=close, source=source, fetched_at=stamp)
                )
                inserted += 1
            elif row.close != close or row.source != source:
                row.close, row.source, row.fetched_at = close, source, stamp
                row.save(update_fields=["close", "source", "fetched_at"])
                updated += 1
            else:
                unchanged += 1
        cls.objects.bulk_create(new_rows)
        return UpsertCount(inserted, updated, unchanged)

    @classmethod
    def latest_for(cls, symbols: Iterable[str]) -> dict[str, Quote]:
        """The newest stored close per symbol, as a `Quote`. A symbol with no rows is absent."""
        wanted = {symbol.strip().upper() for symbol in symbols}
        if not wanted:
            return {}
        # One query for the newest date per symbol, one for those rows. `values().annotate()`
        # groups by the listed field, like SQL's GROUP BY.
        newest = list(
            cls.objects.filter(symbol__in=wanted).values("symbol").annotate(latest=Max("date"))
        )
        if not newest:
            return {}
        picks = Q()
        for row in newest:
            picks |= Q(symbol=row["symbol"], date=row["latest"])
        return {row.symbol: row.quote() for row in cls.objects.filter(picks)}
```

- **One row per symbol per day,** and the constraint says so. The PRD sketched a unique key of security, date
  and source; the question the page asks is "what was the close that day", so the source became a column that
  records which source answered, and a second source replaces the first row rather than sitting beside it.
  Symbols stay text, as chapter 05 decided; a `Security` table can come when something needs it.
- **Six places, not two.** A close is a factor, not a money amount; it is multiplied before anything is rounded
  to cents. The same float guard as a statement line sits in `save`.
- **`upsert` is the idempotency,** in plain steps a learner can read: fetch what is stored for those days in one
  query, compare each day, insert the new ones with one `bulk_create`, save a changed one, count the rest as
  unchanged and do not touch them. `bulk_create` skips `save()` (Django Software Foundation, n.d.-d), so the
  rounding and the upper-casing happen before the rows are built. Because an unchanged row is not written,
  `fetched_at` keeps the time the number first arrived, and a repeated run leaves the table byte for byte the
  same; the first test proves it.
- **`latest_for` is two queries.** When `values()` comes before `annotate()`, "the original results are grouped
  according to the unique combinations of the fields specified in the `values()` clause" and "An annotation is
  then provided for each unique group" (Django Software Foundation, n.d.-b): one row per symbol with its newest
  date, then the rows those pairs name. A symbol with no rows is simply absent from the dictionary.

Make the migration and read it:

Listing 08-9, Terminal:

```sh
uv run --env-file .env python manage.py makemigrations prices
uv run ruff format src/invest_witus_site/prices/migrations/
```

```text
Migrations for 'prices':
  src/invest_witus_site/prices/migrations/0001_initial.py
    + Create model DailyClose
1 file reformatted, 1 file left unchanged
```

Listing 08-10, Filename: `src/invest_witus_site/prices/migrations/0001_initial.py`:

```python
# Generated by Django 5.2.18 on 2026-10-28 22:30

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="DailyClose",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("symbol", models.CharField(max_length=20)),
                ("date", models.DateField(help_text="The trading day the close is for.")),
                ("close", models.DecimalField(decimal_places=6, max_digits=18)),
                (
                    "source",
                    models.CharField(
                        help_text="Which source answered: tiingo, or csv on a laptop.",
                        max_length=40,
                    ),
                ),
                (
                    "fetched_at",
                    models.DateTimeField(help_text="When the pull wrote or last changed this row."),
                ),
            ],
            options={
                "verbose_name": "daily close",
                "verbose_name_plural": "daily closes",
                "ordering": ["symbol", "-date"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("symbol", "date"), name="close_once_per_symbol_and_day"
                    )
                ],
            },
        ),
    ]
```

Listing 08-11, Filename: `src/invest_witus_site/prices/admin.py`:

```python
"""The stored closes, read in the admin: what the nightly pull wrote, by symbol and day."""

from django.contrib import admin

from invest_witus_site.prices.models import DailyClose


@admin.register(DailyClose)
class DailyCloseAdmin(admin.ModelAdmin[DailyClose]):
    """Rows come from the pull. The owner can read them here, filter by source, and delete a
    row to make the next run fetch it again."""

    list_display = ("symbol", "date", "close", "source", "fetched_at")
    list_filter = ("source",)
    search_fields = ("symbol",)
    date_hierarchy = "date"
    ordering = ("symbol", "-date")
    readonly_fields = ("fetched_at",)
```

The admin page is for reading what the pull wrote. The one edit that matters is deleting a row, which makes the
next run fetch that day again.

### 08.5 The two sources

Listing 08-12, Filename: `src/invest_witus_site/prices/sources.py`:

```python
"""Where closes come from: a Protocol, Tiingo's end-of-day endpoint over httpx, and a folder of
CSV files for a laptop and the tests.

Every source answers the same question (this symbol, these days) with chapter 02's `PricePoint`s,
and refuses one symbol with `PriceSourceError` rather than a crash, so the pull can record the
refusal and go on to the next symbol.

Tiingo, as read on October 28, 2026 (https://www.tiingo.com/documentation/end-of-day and
/documentation/general/connecting): prices for one ticker come from
`https://api.tiingo.com/tiingo/daily/<ticker>/prices` with `startDate` and `endDate`; the token
goes in the `Authorization` header as `Token <value>`; each day is an object with `date`, `open`,
`high`, `low`, `close`, `volume` and the adjusted and dividend fields. The docs describe `date`
only as "the date this data pertains to", so the parser reads its first ten characters, which
covers a bare date and a timestamp alike.
"""

import json
import logging
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Protocol, cast

import httpx
from django.conf import settings

from invest_witus.prices.csv_file import PriceFileError, PricePoint, load_prices

log = logging.getLogger(__name__)

# The seam the tests use, as in chapter 07: a `MockTransport` here and nothing leaves the process.
transport: httpx.BaseTransport | None = None

TIINGO_BASE_URL = "https://api.tiingo.com"
REQUEST_TIMEOUT_SECONDS = 20.0


class PriceSourceError(Exception):
    """One symbol the source could not answer. `retry_later` is True when asking for the next
    symbol now would fail the same way (a rate limit), so the pull should stop for this run."""

    def __init__(self, symbol: str, problem: str, retry_later: bool = False) -> None:
        super().__init__(f"{symbol}: {problem}")
        self.symbol = symbol
        self.problem = problem
        self.retry_later = retry_later


class PriceSource(Protocol):
    """What the pull needs from a source: a name for the `source` column, and closes by day."""

    name: str

    def closes(self, symbol: str, since: date, until: date) -> list[PricePoint]: ...


class CsvPrices:
    """A folder of `<SYMBOL>.csv` files in chapter 02's format (`date,close`)."""

    name = "csv"

    def __init__(self, folder: Path) -> None:
        self.folder = folder

    def closes(self, symbol: str, since: date, until: date) -> list[PricePoint]:
        path = self.folder / f"{symbol}.csv"
        if not path.is_file():
            raise PriceSourceError(symbol, f"no file {path.name} in {self.folder}")
        try:
            points = load_prices(path)
        except PriceFileError as error:
            raise PriceSourceError(symbol, str(error)) from error
        return [point for point in points if since <= point.day <= until]


class TiingoEod:
    """Tiingo's end-of-day prices, one request per symbol, with the owner's own token."""

    name = "tiingo"

    def __init__(self, api_key: str, base_url: str = TIINGO_BASE_URL) -> None:
        if not api_key:
            raise ValueError("TiingoEod needs an API key (TIINGO_API_KEY)")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def closes(self, symbol: str, since: date, until: date) -> list[PricePoint]:
        url = f"{self.base_url}/tiingo/daily/{symbol}/prices"
        params = {"startDate": since.isoformat(), "endDate": until.isoformat(), "format": "json"}
        # The token travels in the header, never in the URL, so no log that keeps URLs has it.
        headers = {"Authorization": f"Token {self.api_key}", "Content-Type": "application/json"}
        try:
            with httpx.Client(transport=transport, timeout=REQUEST_TIMEOUT_SECONDS) as http:
                response = http.get(url, params=params, headers=headers)
        except httpx.HTTPError as error:
            raise PriceSourceError(symbol, f"request failed: {type(error).__name__}") from error
        if response.status_code == 429:
            raise PriceSourceError(
                symbol,
                "Tiingo answered 429: the hourly or daily request limit is reached",
                retry_later=True,
            )
        if response.status_code != 200:
            # The first 200 characters of the body name the reason (an unknown ticker, a bad
            # token). The body is the vendor's; the key is never in it.
            raise PriceSourceError(
                symbol, f"Tiingo answered {response.status_code}: {response.text[:200]}"
            )
        return parse_tiingo(symbol, response.text)


def parse_tiingo(symbol: str, text: str) -> list[PricePoint]:
    """A JSON list of days to `PricePoint`s, decoded with `parse_float=Decimal` so that a close
    written as 101.23 becomes the Decimal 101.23 and never the float 101.23000000000000398."""
    try:
        body: object = json.loads(text, parse_float=Decimal)
    except json.JSONDecodeError as error:
        raise PriceSourceError(symbol, f"not JSON: {error.msg}") from error
    if not isinstance(body, list):
        raise PriceSourceError(symbol, "expected a list of days")
    points: list[PricePoint] = []
    for item in cast(list[object], body):
        if not isinstance(item, dict):
            raise PriceSourceError(symbol, "expected an object per day")
        day_field = cast(dict[str, object], item)
        raw_day, raw_close = day_field.get("date"), day_field.get("close")
        if not isinstance(raw_day, str) or len(raw_day) < 10:
            raise PriceSourceError(symbol, f"not a date: {raw_day!r}")
        try:
            day = date.fromisoformat(raw_day[:10])
        except ValueError:
            raise PriceSourceError(symbol, f"not a date: {raw_day!r}") from None
        # `bool` is an `int` in Python; `true` is not a price.
        if isinstance(raw_close, bool) or not isinstance(raw_close, Decimal | int):
            raise PriceSourceError(symbol, f"close is not a number: {raw_close!r}")
        close = Decimal(raw_close)
        if close <= 0:
            raise PriceSourceError(symbol, f"close must be positive, got {close}")
        points.append(PricePoint(day=day, close=close))
    return sorted(points, key=lambda point: point.day)


def source_from_settings() -> PriceSource:
    """Tiingo when the owner set a key; otherwise the CSV folder, which is what a laptop and a
    learner's copy have."""
    if settings.TIINGO_API_KEY:
        return TiingoEod(settings.TIINGO_API_KEY)
    return CsvPrices(Path(settings.PRICES_CSV_DIR))
```

- **`PriceSource` is a `Protocol`:** "Base class for protocol classes", used "with static type checkers that
  recognize structural subtyping (static duck-typing)" (Python Software Foundation, n.d.-c). Neither source
  inherits from it; each has a `name` and a `closes` method with the right signature, and pyright accepts both
  where a `PriceSource` is wanted. The pull never imports a vendor.
- **`PriceSourceError` is one symbol's refusal.** It carries the symbol, the problem as text, and
  `retry_later`, which only a 429 sets. The pull reads that flag to decide between "next symbol" and "stop".
- **`CsvPrices` is chapter 02 again:** `load_prices` on `<SYMBOL>.csv`, filtered to the window, and chapter
  02's errors wrapped as this chapter's. On a laptop it is the whole price feed.
- **`TiingoEod` sends the key in the header,** never in the URL, so a log that keeps URLs never keeps the key;
  the test asserts both. The `transport` seam is chapter 07's pattern: `None` in production, a `MockTransport`
  in the tests. A non-200 answer becomes a `PriceSourceError` with the status and the first 200 characters of
  the vendor's body, which names the reason (an unknown ticker, a bad token) and cannot contain the key, since
  the key was in the request.
- **`parse_tiingo` decodes with `parse_float=Decimal`.** The `json` module calls that function "with the string
  of every JSON float to be decoded", and the documentation's own example is `decimal.Decimal` (Python Software
  Foundation, n.d.-a). So `101.23` in the body becomes the Decimal `101.23`, and the test checks that `0.1`
  arrives as `Decimal("0.1")` and not as `Decimal(0.1)`, which is 0.1000000000000000055511151231257827. Whole
  numbers arrive as `int`, which `Decimal` takes exactly; `true` is an `int` in Python and is refused by name.
  Everything the parser does not recognize is a refusal with a reason, never a guess.
- **`source_from_settings`** reads the switch at call time, which is what lets the tests flip it with the
  `settings` fixture.

### 08.6 The pull and the command

Listing 08-13, Filename: `src/invest_witus_site/prices/pull.py`:

```python
"""The nightly pull: which symbols, which days, one request per symbol, and the counts.

Written to be run twice without harm, because Vercel's Hobby cron may fire anywhere inside its
hour, does not retry a failed run, and can occasionally deliver a run twice or not at all
(Vercel's cron docs, read October 28, 2026). Asking for the last `DAYS_BACK` days every night
means one missed night is filled in by the next, and `DailyClose.upsert` means a repeated night
writes nothing.
"""

import logging
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

from invest_witus_site.holdings.models import Holding
from invest_witus_site.prices.models import DailyClose, UpsertCount
from invest_witus_site.prices.sources import PriceSource, PriceSourceError

log = logging.getLogger(__name__)

# How many days back a run asks for. A week of closes is seven small rows per symbol, and it
# makes any single missed night harmless.
DAYS_BACK = 7
# The free plan's hourly limit, from Tiingo's pricing page (read October 28, 2026): 50 requests
# an hour, 1,000 a day, 500 unique symbols a month. One request per symbol per run, and a run
# never makes more than this many; what is left is listed as skipped for the next run.
REQUESTS_PER_RUN = 50
# The pause between two symbols. Tiingo's overview (read the same day) counts requests per hour
# and per day and says "We do not rate limit to minute or second", so this is a courtesy to the
# vendor, not a documented requirement; the budget above is the real guard.
PAUSE_SECONDS = 1.0


def watch_symbols() -> set[str]:
    """Reserved for chapter 09: the symbols on the owner's watch lists. Nothing yet."""
    return set()


def symbol_universe() -> list[str]:
    """Every symbol an account holds (cash has no price), plus the watch list's, each once."""
    held = Holding.objects.exclude(kind=Holding.Kind.CASH).values_list("symbol", flat=True)
    return sorted(set(held) | watch_symbols())


@dataclass
class PullResult:
    """What one run did, for the command's output and the cron route's JSON."""

    source: str
    since: date
    until: date
    symbols: list[str]
    requests: int = 0
    counts: UpsertCount = UpsertCount()
    failed: dict[str, str] = field(default_factory=dict[str, str])
    skipped: list[str] = field(default_factory=list[str])

    def as_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "since": self.since.isoformat(),
            "until": self.until.isoformat(),
            "symbols": self.symbols,
            "requests": self.requests,
            "inserted": self.counts.inserted,
            "updated": self.counts.updated,
            "unchanged": self.counts.unchanged,
            "failed": self.failed,
            "skipped": self.skipped,
        }


def pull(
    source: PriceSource,
    symbols: Iterable[str],
    since: date,
    until: date,
    pause: float | None = None,
    budget: int = REQUESTS_PER_RUN,
) -> PullResult:
    """One request per symbol, in order; a refusal is recorded and the next symbol is tried. A
    rate limit stops the run, and the symbols not reached are listed as skipped."""
    if pause is None:
        pause = PAUSE_SECONDS
    result = PullResult(source.name, since, until, list(symbols))
    for index, symbol in enumerate(result.symbols):
        if result.requests >= budget:
            result.skipped.append(symbol)
            continue
        if result.requests > 0 and pause > 0:
            time.sleep(pause)
        result.requests += 1
        try:
            points = source.closes(symbol, since, until)
        except PriceSourceError as error:
            result.failed[symbol] = error.problem
            log.warning("pull_prices: %s", error)
            if error.retry_later:
                result.skipped.extend(result.symbols[index + 1 :])
                break
            continue
        counts = DailyClose.upsert(symbol, points, source.name)
        result.counts = result.counts + counts
        log.info("pull_prices: %s, %d day(s) from %s: %s", symbol, len(points), source.name, counts)
    return result
```

- **Three constants, each from a page read that day.** `DAYS_BACK` is the window, for Vercel's missed and
  duplicate runs. `REQUESTS_PER_RUN` is Tiingo's hourly limit, so a run can never exceed it: symbol fifty-one
  is listed as skipped for the next run. `PAUSE_SECONDS` is a courtesy, since Tiingo states no per-minute or
  per-second limit; fifty symbols at a second each still fit inside Vercel's 300-second Hobby maximum.
- **`symbol_universe`** is every held symbol whose kind is not cash, each once, plus `watch_symbols()`, which
  returns nothing and is where chapter 09 plugs in the watch list. The holding's kind is the one the owner set
  in chapter 05's admin; a cash line has nothing to pull.
- **`pull` is one loop with three exits per symbol.** Budget spent: skip. Refused: record the problem, and stop
  the whole run only if the source said to retry later. Answered: upsert and add the counts. The result is a
  dataclass with an `as_dict` for the cron's JSON, and the log line per symbol is what Vercel's log shows.

Listing 08-14, Filename: `src/invest_witus_site/prices/management/commands/pull_prices.py`:

```python
"""`manage.py pull_prices [--since YYYY-MM-DD] [--symbols A,B]`: the nightly pull, by hand.

The same code the cron route runs, for a laptop (against the CSV folder) and for the owner's
shell (against Tiingo, with the key in the environment). Running it twice writes nothing twice.
"""

from datetime import date, timedelta
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.utils import timezone

from invest_witus_site.prices.pull import DAYS_BACK, pull, symbol_universe
from invest_witus_site.prices.sources import source_from_settings


def parse_symbols(text: str) -> list[str]:
    """`"index, other"` becomes `["INDEX", "OTHER"]`, each once, in the order given."""
    return list(dict.fromkeys(part.strip().upper() for part in text.split(",") if part.strip()))


class Command(BaseCommand):
    help = "Store end-of-day closes for every held symbol, or for --symbols, since a date."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--since",
            type=date.fromisoformat,
            help=f"First day to ask for, YYYY-MM-DD. Default: {DAYS_BACK} days ago.",
        )
        parser.add_argument(
            "--symbols",
            help="Comma-separated symbols instead of every held symbol, such as INDEX,OTHER.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        today = timezone.localdate()
        since: date = options["since"] or today - timedelta(days=DAYS_BACK)
        if since > today:
            raise CommandError(f"--since {since} is after today ({today})")
        symbols = parse_symbols(options["symbols"]) if options["symbols"] else symbol_universe()
        if not symbols:
            self.stdout.write("Nothing to pull: no account holds a symbol yet.")
            return
        result = pull(source_from_settings(), symbols, since, today)
        self.stdout.write(
            f"Source {result.source}, {result.since} to {result.until}, "
            f"{len(result.symbols)} symbol(s), {result.requests} request(s)."
        )
        self.stdout.write(f"{result.counts}.".capitalize())
        for symbol, problem in result.failed.items():
            self.stderr.write(f"Failed {symbol}: {problem}")
        if result.skipped:
            self.stderr.write(f"Skipped, for the next run: {', '.join(result.skipped)}")
```

- **Where it lives is its name.** Django registers "a `manage.py` command for each Python module" in an app's
  `management/commands` directory (Django Software Foundation, n.d.-c), so `pull_prices.py` is `manage.py
  pull_prices`. `add_arguments` is argparse; `--since` is parsed by `date.fromisoformat`, so a bad date is
  refused by argparse before `handle` runs.
- **`self.stdout` and `self.stderr`, not `print`:** the documentation asks for the proxies because "it becomes
  much easier to test your custom command" (Django Software Foundation, n.d.-c), and the tests pass a
  `StringIO` for each.
- **One `CommandError`,** for a start date after today. Raising it "is the preferred way to indicate that
  something has gone wrong", printed to stderr with a non-zero exit (Django Software Foundation, n.d.-c). A
  vendor's refusal is not that: it is reported per symbol on stderr, the counts go to stdout, and the command
  exits zero, because a 404 for one symbol is information, not a failure of the command.

### 08.7 The cron route and `vercel.json`

Listing 08-15, Filename: `src/invest_witus_site/prices/views.py`:

```python
"""`GET /api/cron/pull-prices/`: the nightly pull, called by Vercel's cron.

Vercel sends the project's `CRON_SECRET` as `Authorization: Bearer <value>` with every cron
request (its docs, read October 28, 2026). The route compares that header with the setting in
constant time and answers 403 to anything else. With no secret configured it answers 503 and runs
nothing: a deploy that forgot the variable fails closed instead of pulling for anyone who asks.
"""

import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from invest_witus_site.prices.pull import DAYS_BACK, pull, symbol_universe
from invest_witus_site.prices.sources import source_from_settings

log = logging.getLogger(__name__)


def bearer_matches(header: str, secret: str) -> bool:
    """`compare_digest` takes the same time whether the first or the last byte differs."""
    return secrets.compare_digest(header.encode("utf-8"), f"Bearer {secret}".encode())


@never_cache
@require_GET
def pull_prices_cron(request: HttpRequest) -> JsonResponse:
    secret = settings.CRON_SECRET
    if not secret:
        log.error("cron: CRON_SECRET is not set; the pull did not run")
        return JsonResponse({"error": "CRON_SECRET is not set"}, status=503)
    if not bearer_matches(request.headers.get("Authorization", ""), secret):
        return JsonResponse({"error": "forbidden"}, status=403)
    today = timezone.localdate()
    result = pull(
        source_from_settings(), symbol_universe(), today - timedelta(days=DAYS_BACK), today
    )
    body = result.as_dict()
    # Which schedule fired, when more than one cron shares a path; empty for a call by hand.
    body["schedule"] = request.headers.get("x-vercel-cron-schedule", "")
    log.info("cron: pull-prices %s", body)
    return JsonResponse(body)
```

- **503, then 403, then the pull.** The order matters: a missing secret is the deploy's mistake and is logged as
  an error; a wrong header is a stranger and gets one word. `secrets.compare_digest` compares "using a
  'constant-time compare' to reduce the risk of timing attacks" (Python Software Foundation, n.d.-b), and the
  whole `Bearer <secret>` string is compared, so a `Token` prefix, a lower-case `bearer` or a trailing space are
  all 403, as the parametrized test lists.
- **`require_GET` and `never_cache`,** as `/healthz/` has: Vercel makes a GET, and a cached 200 would be a run
  that never ran.
- **The schedule header is echoed** so a log line says which cron fired; a call by hand shows an empty string.

Listing 08-16, Filename: `src/invest_witus_site/prices/urls.py`:

```python
"""The cron route. `invest_witus_site/urls.py` mounts this file at `api/cron/`."""

from django.urls import path

from invest_witus_site.prices import views

urlpatterns = [
    path("pull-prices/", views.pull_prices_cron, name="cron-pull-prices"),
]
```

Listing 08-17, Filename: `vercel.json`:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "ignoreCommand": "if [ \"$VERCEL_ENV\" = \"production\" ]; then exit 1; fi; case \"$VERCEL_GIT_COMMIT_REF\" in bundle/*) exit 1;; *) echo \"skip preview for $VERCEL_GIT_COMMIT_REF\"; exit 0;; esac",
  "functions": {
    "wsgi.py": {
      "excludeFiles": "{tests/**,docs/chapters/**,docs/research/**,data/**,scripts/**,plans/**,staticfiles/**,.github/**,.githooks/**}"
    }
  },
  "crons": [
    {
      "path": "/api/cron/pull-prices/",
      "schedule": "0 6 * * *"
    }
  ]
}
```

The `crons` key is the one chapter 06 said would come. Vercel reads it from the production deployment only,
which is why `vercel.json` carries it and no dashboard setting does; the project's **Settings → Cron Jobs**
page lists it, can disable it, can run it by hand, and links its logs (Vercel, 2026b).

### 08.8 The owner's pages

Listing 08-18, Filename: `src/invest_witus_site/prices/portfolio.py`:

```python
"""A statement valued at the latest stored closes: the join between holdings and prices."""

from datetime import date
from decimal import Decimal

from invest_witus.valuation import Quote, Valuation, value_positions
from invest_witus_site.holdings.models import Holding, Snapshot
from invest_witus_site.prices.models import DailyClose

# A cash line is worth its amount. It is never pulled: no vendor has a close for "CASH".
CASH_CLOSE = Decimal("1")


def value_snapshot(snapshot: Snapshot, today: date) -> Valuation:
    """Each line of the statement at its symbol's newest close; cash at face, dated by the
    statement; a symbol with no close yet is listed, not valued."""
    positions = snapshot.positions()
    kinds: dict[str, str] = dict(
        Holding.objects.filter(account=snapshot.account).values_list("symbol", "kind")
    )
    cash = {position.symbol for position in positions if kinds.get(position.symbol) == "cash"}
    quotes = DailyClose.latest_for(
        position.symbol for position in positions if position.symbol not in cash
    )
    for symbol in cash:
        quotes[symbol] = Quote(close=CASH_CLOSE, as_of=snapshot.as_of, source="statement")
    return value_positions(positions, quotes, today)
```

The join: the latest statement's lines as chapter 05's `Position`s, the holdings' kinds in one query, the newest
close per symbol in two, and cash valued at one dollar a share, dated by the statement and labeled as such.
Then the library does the arithmetic.

Listing 08-19, Filename: `src/invest_witus_site/holdings/views.py`:

```python
"""The owner's accounts, outside the admin: a list, and one account valued at the latest closes.

Both views sit behind `login_required`, which sends a visitor to `LOGIN_URL` (the WitUS sign-in,
chapter 07), and both read only the accounts the signed-in user owns. Someone else's account is a
404, not a 403: the page does not say whether the id exists.
"""

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from invest_witus_site.holdings.models import Account
from invest_witus_site.prices.portfolio import value_snapshot


@login_required
def account_list(request: HttpRequest) -> HttpResponse:
    accounts = Account.objects.filter(owner=request.user)
    return render(request, "holdings/account_list.html", {"accounts": accounts})


@login_required
def account_detail(request: HttpRequest, pk: int) -> HttpResponse:
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    snapshot = account.latest_snapshot()
    valuation = value_snapshot(snapshot, timezone.localdate()) if snapshot is not None else None
    context = {"account": account, "snapshot": snapshot, "valuation": valuation}
    return render(request, "holdings/account_detail.html", context)
```

- **`login_required`** does two things: "If the user isn't logged in, redirect to `settings.LOGIN_URL`, passing
  the current absolute path in the query string", and otherwise "execute the view normally" (Django Software
  Foundation, n.d.-a). Chapter 07 set `LOGIN_URL = "sign-in"`, a named pattern, which the setting accepts, so
  the redirect goes to the WitUS sign-in with `?next=/accounts/1/`. (The sign-in brings the person home rather
  than to `next`; honoring it is an exercise.)
- **Ownership is in the query.** `get_object_or_404(Account, pk=pk, owner=request.user)`: another owner's id
  is a 404, the same answer as an id that does not exist, so the page says nothing about which ids exist.

Listing 08-20, Filename: `src/invest_witus_site/holdings/urls.py`:

```python
"""The owner's own pages. `invest_witus_site/urls.py` mounts this file at `accounts/`."""

from django.urls import path

from invest_witus_site.holdings import views

urlpatterns = [
    path("", views.account_list, name="account-list"),
    path("<int:pk>/", views.account_detail, name="account-detail"),
]
```

Listing 08-21, Filename: `src/invest_witus_site/urls.py`:

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
    # The nightly price pull, called by Vercel's cron with the bearer secret (chapter 08).
    path("api/cron/", include("invest_witus_site.prices.urls")),
    path("", include("invest_witus_site.pages.urls")),
]
```

Listing 08-22, Filename: `src/invest_witus_site/holdings/templates/holdings/account_list.html`:

```html
{% extends "pages/base.html" %}
{% block title %}Your accounts: Invest.WitUS{% endblock %}
{% block content %}
<section class="container narrow" aria-labelledby="accounts-heading">
  <p class="eyebrow">Signed in</p>
  <h1 id="accounts-heading">Your accounts</h1>
  {% if accounts %}
  <ul>
    {% for account in accounts %}
    <li><a href="{% url 'account-detail' account.pk %}">{{ account.name }}</a> <span class="muted">({{ account.broker }}, {{ account.get_kind_display|lower }})</span></li>
    {% endfor %}
  </ul>
  <p class="muted">Each page values the account's latest statement at the latest close the app has stored, with the close's date beside it. Information, not advice.</p>
  {% else %}
  <p>No accounts yet.{% if user.is_staff %} <a href="{% url 'admin:holdings_account_add' %}">Add one in the admin.</a>{% endif %}</p>
  {% endif %}
</section>
{% endblock %}
```

Listing 08-23, Filename: `src/invest_witus_site/holdings/templates/holdings/account_detail.html`:

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
  <p><a href="{% url 'account-list' %}">All accounts</a></p>
</section>
{% endblock %}
```

One table, with a caption for screen readers, `scope` on every header cell, and the numbers right-aligned in
tabular figures by five rules added to `site.css` (`.holdings`, its cells, `.num`, the footer row and
`.stale`). A line with no close says "no price yet" across the four cells it cannot fill; the total is labeled
as the total of the priced lines, because that is what it is.

Listing 08-24, Filename: `src/invest_witus_site/holdings/templatetags/holdings_extras.py`:

```python
"""Template filters for the holdings pages. `{% load holdings_extras %}` makes them available."""

from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def signed(value: Decimal | None) -> str:
    """A change with its sign: `+1.500000`, `-500.00`, or plain `0.00`. None: the statement
    did not show the number, so there is nothing to compare."""
    if value is None:
        return "not shown"
    if value == 0:
        return str(value)
    return f"{value:+}"


@register.filter
def plain_number(value: Decimal | None) -> str:
    """A Decimal without the column's trailing zeros, with at least two places: `2.500000`
    becomes `2.50`, `101.230000` becomes `101.23`, `12.3456` stays, `1` becomes `1.00`."""
    if value is None:
        return ""
    text = f"{value:f}"
    whole, point, fraction = text.partition(".")
    fraction = fraction.rstrip("0") if point else ""
    return f"{whole}.{fraction.ljust(2, '0')}"
```

`plain_number` is the new filter: a column stores `2.500000` and `101.230000`; the page shows `2.50` and
`101.23`, and `20.005` keeps its third place because it is not a zero.

Listing 08-25, Filename: `src/invest_witus_site/pages/templates/pages/_header.html`:

```html
{% load static %}
{# Logo: gemini/witus/public/brand/04-orbit-type/logomark.svg, drawn for dark backgrounds, copied into static/brand/witus/. #}
<header class="site-header">
  <div class="container header-row">
    <a class="brand" href="{% url 'home' %}">
      <img src="{% static 'brand/witus/logomark.svg' %}" alt="" width="32" height="32">
      Invest.WitUS
    </a>
    <nav aria-label="Primary">
      <a href="{% url 'faq' %}">FAQ</a>
      <a href="{% url 'home' %}#waitlist">Waitlist</a>
      {% if user.is_authenticated %}
        {# Signed in (chapter 07): the person's name, then the "Sign out" control, a form. #}
        {# Chapter 08: the link to their accounts, valued, on this branch only; no public page links it. #}
        <a href="{% url 'account-list' %}">Accounts</a>
        <span class="who muted">{{ display_name }}</span>
        {% include "accounts/_sign_out_form.html" %}
      {% else %}
        {# While a visitor is signed out, this link's accessible name is exactly "Sign in" on every page. #}
        {# Never rename it (shared UI rule, 2026-10-16): the smoke test in tests/test_ch04.py fails if it changes. #}
        <a class="button" href="{% url 'sign-in' %}">Sign in</a>
      {% endif %}
    </nav>
  </div>
</header>
```

The "Accounts" link sits on the signed-in branch only. The signed-out branch is byte for byte chapter 07's, so
chapter 04's smoke test holds, and the last page test in this chapter renders every public page and asserts
there is no `<table` and no link to `/accounts/` on any of them.

### 08.9 Green, and the pull on your laptop

Listing 08-26, Terminal:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

```text
240 passed in 12.91s
All checks passed!
114 files already formatted
0 errors, 0 warnings, 0 informations
```

Forty-seven new tests. Now run the pull against chapter 02's made-up prices, as the CSV source:

Listing 08-27, Terminal:

```sh
mkdir -p data/private/prices
cp data/sample/illustrative-daily-prices.csv data/private/prices/INDEX.csv
uv run --env-file .env python manage.py migrate
uv run --env-file .env python manage.py pull_prices --symbols INDEX --since 2026-09-22
uv run --env-file .env python manage.py pull_prices --symbols INDEX --since 2026-09-22
uv run --env-file .env python manage.py pull_prices --symbols INDEX,OTHER --since 2026-09-29
```

```text
Source csv, 2026-09-22 to 2026-10-28, 1 symbol(s), 1 request(s).
Inserted 7, updated 0, unchanged 0.
Source csv, 2026-09-22 to 2026-10-28, 1 symbol(s), 1 request(s).
Inserted 0, updated 0, unchanged 7.
pull_prices: OTHER: no file OTHER.csv in /your/repo/data/private/prices
Failed OTHER: no file OTHER.csv in /your/repo/data/private/prices
Source csv, 2026-09-29 to 2026-10-28, 2 symbol(s), 2 request(s).
Inserted 0, updated 0, unchanged 2.
```

(The second date is today's, whatever day you run it, and the folder is your repository's; the sample file ends
on September 30, 2026.) Seven
weekdays inserted, then the same seven unchanged, then a symbol with no file recorded while `INDEX` is still
checked. The refusal appears twice: once from the logger, which is what Vercel's log shows, and once from the
command on stderr, which is what a shell shows.

Then the route, without a server, the way chapter 07 looked at the sign-in redirect:

Listing 08-28, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -c "from django.test import Client; r = Client().get('/api/cron/pull-prices/'); print(r.status_code, r.content.decode())"
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
CRON_SECRET=not-the-real-secret-just-for-this-check \
uv run python manage.py shell -c "from django.test import Client; print(Client().get('/api/cron/pull-prices/').status_code); r = Client().get('/api/cron/pull-prices/', headers={'Authorization': 'Bearer not-the-real-secret-just-for-this-check'}); print(r.status_code, r.content.decode())"
```

```text
503 {"error": "CRON_SECRET is not set"}
403
200 {"source": "csv", "since": "2026-10-21", "until": "2026-10-28", "symbols": [], "requests": 0, "inserted": 0, "updated": 0, "unchanged": 0, "failed": {}, "skipped": [], "schedule": ""}
```

`symbols` is empty because no account holds anything yet on this database; enter a statement in the admin
(chapter 05) and the same call lists its symbols. To see the page: sign in at `/admin/` with your chapter 05
superuser (a login is a login, as chapter 07 noted), then open `http://127.0.0.1:8000/accounts/` under
`runserver`.

### 08.10 What the owner does outside the editor

The reference app's key and secret are the owner's; task 09 in the owner's queue has the dashboard steps. A
learner with a Vercel project of their own does the same with their own Tiingo account. The steps, so the
chapter is complete:

1. **A Tiingo account and its token.** Sign up at `https://www.tiingo.com/signup` (the page hands the browser
   to app.tiingo.com); the free plan is the one named Starter on the pricing page. The token is at
   `https://www.tiingo.com/account/api/token`, behind the login (Tiingo, n.d.-c). It goes in a password
   manager, never in a file. Read the Terms of Use in the browser while there; the page refuses automated
   readers.
2. **A cron secret:** at least 16 random characters (Vercel, 2026b). `openssl rand -hex 24`, or
   `python3 -c "import secrets; print(secrets.token_hex(24))"`, which gives 48 hexadecimal characters (Python
   Software Foundation, n.d.-b).
3. **Migrate.** `vercel env run -e production -- uv run python manage.py migrate --database direct`, chapter
   06's recipe; expect `Applying prices.0001_initial... OK`.
4. **Set both names on the Vercel project:** **Settings → Environment Variables**, `TIINGO_API_KEY` and
   `CRON_SECRET`, Production only, marked Sensitive. Crons run against the production deployment only, and a
   preview with the key would spend the hourly budget against a preview database. Then **Redeploy**, so the
   function starts with both.
5. **Run it once, now.** **Settings → Cron Jobs** lists `/api/cron/pull-prices/` with a run button and **View
   Logs** (Vercel, 2026b); or by hand, with the secret in the shell for one command:
   `curl -s -H "Authorization: Bearer $CRON_SECRET" https://<your host>/api/cron/pull-prices/`. Expect 200 and
   JSON with `source` `tiingo`, the held symbols, and `inserted` up to seven per symbol. Run it again: `inserted`
   0, `unchanged` the same number. Without the header: 403. Before step 4: 503.
6. **Open `/accounts/`** signed in, then an account: every line has a close, its date (the last trading day),
   `tiingo` as the source, and a value; a symbol Tiingo did not know is in the response's `failed` and reads
   "no price yet" on the page. The next morning, the Cron Jobs page shows the run after 06:00 UTC.

## Checkpoint

- `uv run pytest` prints `240 passed`; ruff and pyright pass.
- Listing 08-27 inserts seven days the first time and changes nothing the second time.
- Listing 08-28 answers 503, then 403, then 200 with JSON counts.
- Signed out, every public page has no `<table` and no link to `/accounts/`; `/accounts/` itself redirects to
  the sign-in with `?next=/accounts/`.
- Signed in at `/admin/` with a statement entered, `/accounts/<id>/` shows each line with a close, a date and a
  source, or "no price yet".
- On the reference app, after 08.10: a run by hand answers 200 with `tiingo` as the source, and the account page
  shows values.
- Commit and push: `git add -A && git commit -m "Chapter 08: Prices and the nightly pull"`.

## Exercises

1. Add `--until YYYY-MM-DD` to the command, defaulting to today, and refuse a window where `--since` is after
   `--until`. Write the test first; the `CommandError` test shows the shape.
2. The cron runs on Saturdays and Sundays and finds nothing. Change the schedule so it runs Tuesday to Saturday
   (Vercel's day-of-week field, with the day-of-month field left as `*`), update the test, and write one
   sentence in your notes about what a Monday holiday does to Tuesday's pull and why the seven-day window still
   covers it.
3. `login_required` sends a visitor to the sign-in with `?next=/accounts/3/`, and chapter 07's callback goes
   home. Store `next` in the flight at `login`, check it with Django's `url_has_allowed_host_and_scheme` at the
   callback, and redirect there. Write the test that a `next` pointing at another host is ignored.

## If you get stuck

- Browse: https://github.com/dapperAuteur/invest-witus/tree/v08
- Diff for this chapter: https://github.com/dapperAuteur/invest-witus/compare/v07...v08
- Zip: https://github.com/dapperAuteur/invest-witus/archive/v08.zip
- Take the reference's files. Chapter 08 changed `.env.example`, `vercel.json`,
  `src/invest_witus_site/settings.py`, `src/invest_witus_site/urls.py`, the template `pages/_header.html`,
  `pages/static/pages/site.css`, `holdings/templatetags/holdings_extras.py` and `docs/site/privacy.md`, and
  added `src/invest_witus/valuation.py`, `src/invest_witus_site/prices/` (the whole app),
  `src/invest_witus_site/holdings/views.py`, `holdings/urls.py`, `holdings/templates/holdings/`,
  `tests/test_ch08.py` and `tests/fixtures/tiingo/`. No package changed. Nothing moved:
  `git fetch reference --tags && git checkout v08 -- src tests .env.example vercel.json docs/site/privacy.md`.
- `No module named 'invest_witus.valuation'` after 08.3: the file is in `src/invest_witus_site/` instead of
  `src/invest_witus/`; the library and the site are two packages.
- `test_upsert_writes_each_day_once_and_a_rerun_changes_nothing` fails on the table comparison: `upsert` saves
  unchanged rows, or sets `fetched_at` on every row; an unchanged day must not be written at all.
- `test_a_close_keeps_six_places_and_a_float_is_refused` fails with a `decimal.InvalidOperation` or a
  `django.core.exceptions.ValidationError`: `to_close` is not applied before `bulk_create`, which skips `save`.
- `test_tiingo_parsing_keeps_the_number_exact_and_takes_a_bare_date` fails on `Decimal(0.1)`: the body was read
  with `response.json()`, which makes floats. Use `json.loads(response.text, parse_float=Decimal)`.
- `test_tiingo_parsing_refuses_a_body_it_does_not_understand[true]` fails: `isinstance(True, int)` is `True`
  in Python; check `bool` first.
- `test_a_rate_limit_stops_the_run_and_lists_what_was_left` has `OTHER` in `failed` instead of `skipped`: the
  loop did not `break` on `retry_later`, or it broke before extending `skipped`.
- `test_the_pause_sits_between_symbols_not_after_the_last` sees three sleeps: the sleep runs before the first
  request; it must be skipped when `requests` is still zero.
- `test_the_cron_route_refuses_anything_but_the_bearer_secret[Bearer ...  ]` (the trailing space) answers
  200: the header was `strip()`ped or split on spaces; compare the whole string.
- `test_the_cron_route_fails_closed_without_a_secret` gets 403: the secret check comes after the header check;
  the empty secret must answer 503 first.
- `test_the_account_pages_need_a_sign_in` gets 200 or `/accounts/login/`: `login_required` is missing, or
  chapter 07's `LOGIN_URL = "sign-in"` was lost from the settings.
- `test_the_account_page_is_the_owners_only` gets 200: `owner=request.user` is missing from
  `get_object_or_404`.
- `test_the_owner_sees_each_line_valued_with_the_closes_date` shows `2.500000`: the `plain_number` filter is
  not applied, or `{% load holdings_extras %}` is missing from the template.
- `test_public_pages_show_no_table_and_do_not_link_the_account_pages` fails on `/`: the "Accounts" link is
  outside the `{% if user.is_authenticated %}` branch of the header.
- On Vercel, the Cron Jobs page shows the job but the log shows 503: the secret was added after the last
  deployment; **Redeploy**. 403 from the dashboard's run button: the variable's value has a space or a quote
  around it.
- The response lists a symbol under `failed` with `Tiingo answered 404`: the statement's symbol is not the
  ticker Tiingo knows; fix it in the admin's Holdings list, or accept "no price yet".

## What we learned

- The table is the product: the page reads it, the pull writes it, and the vendor is asked once a night. Every
  displayed price carries its date and source because the row does.
- An idempotent job compares before it writes, counts what it did, and leaves a repeated run with nothing to
  do; on a platform that may miss a run or deliver it twice, that is the only kind of job to write.
- A `Protocol` is a seam: two sources with one shape, a pull that never names a vendor, tests that use the cheap
  source for the plumbing and a fake vendor for the parsing.
- A vendor's number stays a Decimal from the first byte: `parse_float=Decimal`, a parser that refuses what it
  does not understand, and a column with enough places that nothing is rounded before it is multiplied.
- One symbol's refusal is recorded; only a rate limit stops the run; the key is in a header and never in a URL
  or an error message.
- A cron on Vercel is a GET with a bearer, compared in constant time, in UTC, somewhere inside its hour, and
  without retries; a route that fails closed without its secret is a deploy mistake caught on the first run.
- A page for the owner is `login_required` plus the owner in the query, and the proof that no public page shows
  a price is a test over every public page, not a promise.

## Next

Chapter 09 adds the watch list: symbols the owner follows per account, with the latest stored close and its
date, and no buy button. `watch_symbols()` is where its symbols join the nightly pull; nothing else from this
chapter changes for it.

## References

Alpaca. (2026a, October 6). *About market data API*. Alpaca documentation.
https://docs.alpaca.markets/docs/about-market-data-api (retrieved October 28, 2026)

Alpaca. (2026b, September 21). *Market data FAQ*. Alpaca documentation.
https://docs.alpaca.markets/us/docs/market-data-faq (retrieved October 28, 2026)

Alpaca. (2026c, February 11). *Historical stock data*. Alpaca documentation.
https://docs.alpaca.markets/us/docs/historical-stock-data-1 (retrieved October 28, 2026)

Alpaca. (n.d.-a). *Get all open positions*. Alpaca API reference.
https://docs.alpaca.markets/reference/getallopenpositions (retrieved October 28, 2026)

Alpaca. (n.d.-b). *Paper trading*. Alpaca documentation. https://docs.alpaca.markets/docs/paper-trading
(retrieved October 28, 2026)

Alpaca. (n.d.-c). *Historical bars*. Alpaca API reference. https://docs.alpaca.markets/reference/stockbars
(retrieved October 28, 2026)

Django Software Foundation. (n.d.-a). *Using the Django authentication system*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/auth/default/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-b). *Aggregation*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/db/aggregation/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-c). *How to create custom django-admin commands*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/howto/custom-management-commands/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-d). *QuerySet API reference*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/ref/models/querysets/ (retrieved October 28, 2026)

Encode. (n.d.). *Transports*. HTTPX documentation. https://www.python-httpx.org/advanced/transports/ (retrieved
October 28, 2026)

Python Software Foundation. (n.d.-a). *json: JSON encoder and decoder*. Python 3 documentation.
https://docs.python.org/3/library/json.html (retrieved October 28, 2026)

Python Software Foundation. (n.d.-b). *secrets: Generate secure random numbers for managing secrets*. Python 3
documentation. https://docs.python.org/3/library/secrets.html (retrieved October 28, 2026)

Python Software Foundation. (n.d.-c). *typing: Support for type hints*. Python 3 documentation.
https://docs.python.org/3/library/typing.html (retrieved October 28, 2026)

Tiingo. (n.d.-a). *Connecting*. Tiingo documentation. https://www.tiingo.com/documentation/general/connecting
(retrieved October 28, 2026)

Tiingo. (n.d.-b). *End-of-day*. Tiingo documentation. https://www.tiingo.com/documentation/end-of-day
(retrieved October 28, 2026)

Tiingo. (n.d.-c). *Overview*. Tiingo documentation. https://www.tiingo.com/documentation/general/overview
(retrieved October 28, 2026)

Tiingo. (n.d.-d). *Pricing*. https://www.tiingo.com/about/pricing (retrieved October 28, 2026)

Tiingo. (n.d.-e). *Developers*. Tiingo documentation. https://www.tiingo.com/documentation/appendix/developers
(retrieved October 28, 2026)

Vercel. (2026a, September 16). *Cron jobs*. Vercel documentation. https://vercel.com/docs/cron-jobs (retrieved
October 28, 2026)

Vercel. (2026b, August 11). *Managing cron jobs*. Vercel documentation.
https://vercel.com/docs/cron-jobs/manage-cron-jobs (retrieved October 28, 2026)

Vercel. (2026c, July 15). *Usage & pricing for cron jobs*. Vercel documentation.
https://vercel.com/docs/cron-jobs/usage-and-pricing (retrieved October 28, 2026)
