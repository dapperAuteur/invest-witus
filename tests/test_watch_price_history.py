"""Price history for watched symbols (2026-10-29): a symbol's first pull reaches back a year in its
one request, inside the run's budget, and a refused or skipped symbol asks again next run; the
owner's history page draws the closes as an inline SVG line with the same closes as a table; and
no public page shows a price. Every source here is a CSV folder or a `MockTransport`: no request
leaves the process, and the symbols are placeholders.
"""

import re
from datetime import date, timedelta
from decimal import Decimal
from html import unescape
from pathlib import Path
from typing import Protocol

import httpx
import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone
from pytest_django.fixtures import Settings

from invest_witus.prices.csv_file import PricePoint
from invest_witus.valuation import STALE_AFTER_DAYS
from invest_witus_site.holdings.models import Account
from invest_witus_site.prices import pull as pull_module
from invest_witus_site.prices import sources
from invest_witus_site.prices.charts import SeriesInput, build_plot
from invest_witus_site.prices.history import range_days
from invest_witus_site.prices.models import Backfill, DailyClose
from invest_witus_site.prices.pull import BACKFILL_DAYS, pull
from invest_witus_site.prices.sources import CsvPrices, TiingoEod
from invest_witus_site.watchlist.models import WatchItem

D = Decimal
TEST_KEY = "test-only-tiingo-key"
SECRET = "test-only-cron-secret-0123456789"
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


@pytest.fixture(autouse=True)
def no_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pull_module, "PAUSE_SECONDS", 0.0)


def today() -> date:
    return timezone.localdate()


def write_csv(path: Path, ages: dict[int, str]) -> None:
    """One row per age in days before today, with its close."""
    rows = sorted((today() - timedelta(days=age), close) for age, close in ages.items())
    lines = ["date,close"] + [f"{day.isoformat()},{close}" for day, close in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture
def csv_folder(tmp_path: Path, settings: Settings) -> Path:
    """FUNDX with a close 400 days back (past the year), 300 and 100 days back, and yesterday;
    INDEX and OTHER with yesterday's only. No file for NONE."""
    write_csv(tmp_path / "FUNDX.csv", {400: "9.00", 300: "10.00", 100: "11.00", 1: "12.34"})
    write_csv(tmp_path / "INDEX.csv", {1: "101.25"})
    write_csv(tmp_path / "OTHER.csv", {1: "20.50"})
    settings.TIINGO_API_KEY = ""
    settings.PRICES_CSV_DIR = tmp_path
    return tmp_path


class Asked(CsvPrices):
    """The CSV source, writing down the first day of every request."""

    def __init__(self, folder: Path) -> None:
        super().__init__(folder)
        self.asked: list[tuple[str, date]] = []

    def closes(self, symbol: str, since: date, until: date) -> list[PricePoint]:
        self.asked.append((symbol, since))
        return super().closes(symbol, since, until)


def stored_days(symbol: str) -> list[int]:
    """The ages, in days before today, of the closes stored for `symbol`, oldest first."""
    rows = DailyClose.objects.filter(symbol=symbol).order_by("date")
    return [(today() - row.date).days for row in rows]


# --- The backfill --------------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_symbols_first_pull_reaches_back_a_year_in_one_request(csv_folder: Path) -> None:
    source = Asked(csv_folder)
    week = today() - timedelta(days=7)
    year = today() - timedelta(days=BACKFILL_DAYS)
    result = pull(source, ["FUNDX"], week, today())
    assert BACKFILL_DAYS == 365
    assert source.asked == [("FUNDX", year)] and result.requests == 1
    assert stored_days("FUNDX") == [300, 100, 1], "the 400-day close is past the year"
    assert result.backfilled == ["FUNDX"] and result.as_dict()["backfilled"] == ["FUNDX"]
    assert Backfill.objects.get(symbol="FUNDX").since == year
    again = pull(source, ["FUNDX"], week, today())
    assert source.asked[1] == ("FUNDX", week), "the year is asked for once"
    assert (again.backfilled, again.counts.inserted, again.counts.unchanged) == ([], 0, 1)


@pytest.mark.django_db
def test_a_symbol_stored_before_the_backfill_existed_gets_its_year_once(csv_folder: Path) -> None:
    """Symbols the nightly pull already knew (a week of closes, no `Backfill` row) are not left
    with a week of history: their next pull asks for the year."""
    DailyClose.upsert("FUNDX", [PricePoint(today() - timedelta(days=1), D("12.34"))], "csv")
    source = Asked(csv_folder)
    result = pull(source, ["FUNDX"], today() - timedelta(days=7), today())
    assert source.asked == [("FUNDX", today() - timedelta(days=BACKFILL_DAYS))]
    assert stored_days("FUNDX") == [300, 100, 1] and result.backfilled == ["FUNDX"]


@pytest.mark.django_db
def test_the_backfill_stays_inside_the_runs_budget_and_finishes_next_run(csv_folder: Path) -> None:
    source = Asked(csv_folder)
    week = today() - timedelta(days=7)
    first = pull(source, ["FUNDX", "INDEX", "OTHER"], week, today(), budget=2)
    assert (first.requests, first.skipped, first.backfilled) == (2, ["OTHER"], ["FUNDX", "INDEX"])
    assert sorted(Backfill.objects.values_list("symbol", flat=True)) == ["FUNDX", "INDEX"]
    second = pull(source, ["OTHER", "FUNDX", "INDEX"], week, today(), budget=2)
    year = today() - timedelta(days=BACKFILL_DAYS)
    assert source.asked[2:] == [("OTHER", year), ("FUNDX", week)]
    assert (second.skipped, second.backfilled) == (["INDEX"], ["OTHER"])


@pytest.mark.django_db
def test_a_refused_symbol_writes_no_backfill_and_asks_for_the_year_again(
    csv_folder: Path,
) -> None:
    source = Asked(csv_folder)
    week = today() - timedelta(days=7)
    year = today() - timedelta(days=BACKFILL_DAYS)
    first = pull(source, ["NONE"], week, today())
    assert "NONE" in first.failed and first.backfilled == []
    assert not Backfill.objects.filter(symbol="NONE").exists()
    write_csv(csv_folder / "NONE.csv", {1: "5.00"})  # the source knows it now
    second = pull(source, ["NONE"], week, today())
    assert source.asked == [("NONE", year), ("NONE", year)]
    assert second.backfilled == ["NONE"] and Backfill.objects.filter(symbol="NONE").exists()


@pytest.mark.django_db
def test_an_explicit_since_further_back_than_a_year_is_kept(csv_folder: Path) -> None:
    source = Asked(csv_folder)
    long_ago = today() - timedelta(days=500)
    result = pull(source, ["FUNDX"], long_ago, today())
    assert source.asked == [("FUNDX", long_ago)]
    assert stored_days("FUNDX") == [400, 300, 100, 1]
    assert result.backfilled == [], "nothing was widened"
    assert Backfill.objects.get(symbol="FUNDX").since == long_ago


@pytest.mark.django_db
def test_tiingo_is_asked_for_the_year_once_per_symbol(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    requests: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        day = (today() - timedelta(days=1)).isoformat()
        return httpx.Response(200, json=[{"date": f"{day}T00:00:00.000Z", "close": 1234.5}])

    monkeypatch.setattr(sources, "transport", httpx.MockTransport(answer))
    settings.TIINGO_API_KEY = TEST_KEY
    pull(TiingoEod(TEST_KEY), ["FUNDX", "INDEX"], today() - timedelta(days=7), today())
    assert len(requests) == 2
    year = (today() - timedelta(days=BACKFILL_DAYS)).isoformat()
    assert [r.url.params["startDate"] for r in requests] == [year, year]
    assert all(TEST_KEY not in str(r.url) for r in requests), "the token stays in the header"


@pytest.mark.django_db
def test_the_cron_route_reports_what_it_backfilled(
    client: Client, settings: Settings, csv_folder: Path, account: Account
) -> None:
    settings.CRON_SECRET = SECRET
    WatchItem.objects.create(account=account, symbol="FUNDX")
    body = client.get(
        "/api/cron/pull-prices/", headers={"Authorization": f"Bearer {SECRET}"}
    ).json()
    assert (body["symbols"], body["backfilled"], body["inserted"]) == (["FUNDX"], ["FUNDX"], 3)


# --- The history page ----------------------------------------------------------------------------


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
def watched(account: Account) -> WatchItem:
    """FUNDX on the watch list, with closes 1, 2, 3, 6 and 7 days back (five in the last 30
    days), 60 days back, and 200 days back."""
    item = WatchItem.objects.create(account=account, symbol="FUNDX", note="from the lesson")
    closes = {1: "1234.5", 2: "1200", 3: "1210.25", 6: "1190", 7: "1180", 60: "1100", 200: "1000"}
    DailyClose.upsert(
        "FUNDX",
        [PricePoint(today() - timedelta(days=age), D(close)) for age, close in closes.items()],
        "csv",
    )
    return item


class Page(Protocol):
    content: bytes


def text(response: Page) -> str:
    return unescape(response.content.decode())


def history_url(account: Account, symbol: str = "FUNDX", query: str = "") -> str:
    return f"/accounts/{account.pk}/watch/{symbol}/{query}"


def polyline_points(html: str) -> list[tuple[float, float]]:
    found = re.search(r'<polyline points="([^"]*)"', html)
    assert found is not None, "no polyline"
    pairs = [pair.split(",") for pair in found.group(1).split()]
    return [(float(x), float(y)) for x, y in pairs]


def table_dates(html: str) -> list[str]:
    return re.findall(r'<th scope="row">(\d{4}-\d{2}-\d{2})</th>', html)


@pytest.mark.django_db
def test_the_chart_has_one_point_per_close_and_the_table_matches(
    client: Client, owner: User, account: Account, watched: WatchItem
) -> None:
    client.force_login(owner)
    response = client.get(history_url(account, query="?days=30"))
    assert response.status_code == 200
    html = text(response)
    points = polyline_points(html)
    assert len(points) == 5 and 'data-points="5"' in html
    assert points == sorted(points), "oldest on the left"
    assert points[0][1] > points[-1][1], "the higher close is drawn higher (smaller y)"
    # Since 2026-10-29 the plot's viewBox is 0 to 100 both ways, stretched to its box, with the
    # axes as HTML beside it (decision 128).
    assert '<svg viewBox="0 0 100 100"' in html and 'role="img"' in html
    assert '<title id="chart-title">FUNDX, last 30 days: 5 closes' in html
    assert "low $1,180.00, high $1,234.50" in html
    assert len(table_dates(html)) == 5, "the table is the chart's text alternative"
    assert table_dates(html)[0] == (today() - timedelta(days=1)).isoformat(), "newest first"
    assert '<td class="num">$1,234.50</td>' in html
    assert f"As of {(today() - timedelta(days=1)).isoformat()}: $1,234.50 (csv)" in html
    # Since 2026-10-29 the owner's chart pages carry the hover script (decision 131); public pages
    # still carry none (the test below and chapter 06a's).
    assert '<script src="/static/prices/chart.js" defer></script>' in html


@pytest.mark.django_db
@pytest.mark.parametrize(("query", "count"), [("?days=90", 6), ("?days=365", 7), ("", 6)])
def test_the_range_picks_the_closes(
    client: Client, owner: User, account: Account, watched: WatchItem, query: str, count: int
) -> None:
    client.force_login(owner)
    html = text(client.get(history_url(account, query=query)))
    assert len(polyline_points(html)) == count and len(table_dates(html)) == count


@pytest.mark.parametrize(
    ("typed", "days"), [("30", 30), ("90", 90), ("365", 365), ("7", 90), ("x", 90), (None, 90)]
)
def test_an_unknown_range_is_the_default(typed: str | None, days: int) -> None:
    assert range_days(typed) == days


@pytest.mark.django_db
def test_a_stale_newest_close_says_so(client: Client, owner: User, account: Account) -> None:
    WatchItem.objects.create(account=account, symbol="OTHER")
    old = today() - timedelta(days=STALE_AFTER_DAYS + 3)
    DailyClose.upsert("OTHER", [PricePoint(old, D("2000"))], "csv")
    client.force_login(owner)
    html = text(client.get(history_url(account, "OTHER")))
    assert f"As of {old.isoformat()}: $2,000.00 (csv)" in html and 'class="stale"' in html


@pytest.mark.django_db
def test_a_watched_symbol_with_no_close_yet_says_the_pull_will_fetch_it(
    client: Client, owner: User, account: Account
) -> None:
    WatchItem.objects.create(account=account, symbol="NONE")
    client.force_login(owner)
    html = text(client.get(history_url(account, "NONE")))
    assert "No close stored yet." in html and "<svg" not in html and "<polyline" not in html


@pytest.mark.django_db
def test_the_history_page_is_the_owners_only(
    client: Client, owner: User, someone: User, account: Account, watched: WatchItem
) -> None:
    signed_out = client.get(history_url(account))
    assert signed_out.status_code == 302 and "/auth/witus/login/" in signed_out["Location"]
    client.force_login(someone)
    assert client.get(history_url(account)).status_code == 404
    client.force_login(owner)
    assert client.get(history_url(account, "OTHER")).status_code == 404, "not on the list"
    assert client.get(history_url(account, "fundx")).status_code == 200, "case does not matter"
    assert client.post(history_url(account)).status_code == 405


@pytest.mark.django_db
def test_each_watch_row_links_to_its_history(
    client: Client, owner: User, account: Account, watched: WatchItem
) -> None:
    client.force_login(owner)
    html = text(client.get(f"/accounts/{account.pk}/"))
    assert f'<a href="/accounts/{account.pk}/watch/FUNDX/">FUNDX</a>' in html


@pytest.mark.django_db
@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_public_pages_show_no_price_and_no_history_link(
    client: Client, account: Account, watched: WatchItem, path: str
) -> None:
    html = client.get(path).content.decode()
    assert "<table" not in html.lower() and "<polyline" not in html
    assert "/accounts/" not in html and "1,234.50" not in html and "1234.5" not in html


def test_one_close_or_a_flat_range_sits_in_the_middle() -> None:
    day = date(2026, 10, 1)
    single = build_plot(
        [SeriesInput("INDEX", [DailyClose(symbol="INDEX", date=day, close=D("5"))])], "t", False
    )
    assert single is not None and single.lines[0].points == "50,50.00"
    flat = build_plot(
        [
            SeriesInput(
                "INDEX",
                [
                    DailyClose(symbol="INDEX", date=day, close=D("5")),
                    DailyClose(symbol="INDEX", date=day + timedelta(days=4), close=D("5")),
                ],
            )
        ],
        "t",
        False,
    )
    assert flat is not None and flat.lines[0].points == "0.00,50.00 100.00,50.00"
    assert build_plot([SeriesInput("INDEX", [])], "t", False) is None
