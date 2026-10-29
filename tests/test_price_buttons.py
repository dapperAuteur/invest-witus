"""The owner's price buttons (2026-10-29): **Fetch prices now** runs the nightly pull for the
signed-in owner's symbols and reports its counts; **Get history** asks one watched symbol's
range in one request and reports the days added and the earliest close stored. Each has a
ten-minute guard, each is a 404 for anyone but the account's owner, a vendor's refusal is a
message and never a 500, and no public page shows either. Every source is a CSV folder or an
`httpx.MockTransport`: no request leaves the process, and the symbols are placeholders.
"""

from datetime import date, datetime, timedelta
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

from invest_witus_site.holdings.models import Account, Holding, Snapshot, SnapshotLine
from invest_witus_site.prices import manual, sources
from invest_witus_site.prices import pull as pull_module
from invest_witus_site.prices.models import Backfill, DailyClose, ManualRun
from invest_witus_site.prices.pull import REQUESTS_PER_RUN, pull
from invest_witus_site.prices.sources import CsvPrices
from invest_witus_site.watchlist.models import WatchItem

TEST_KEY = "test-only-tiingo-key"
PUBLIC_PATHS = [
    "/",
    "/faq/",
    "/privacy/",
    "/terms/",
    "/contact/",
    "/waitlist/",
    "/waitlist/thanks/",
]


@pytest.fixture(autouse=True)
def no_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pull_module, "PAUSE_SECONDS", 0.0)


def today() -> date:
    return timezone.localdate()


def write_csv(path: Path, ages: dict[int, str]) -> None:
    rows = sorted((today() - timedelta(days=age), close) for age, close in ages.items())
    lines = ["date,close"] + [f"{day.isoformat()},{close}" for day, close in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture
def csv_folder(tmp_path: Path, settings: Settings) -> Path:
    """INDEX held, FUNDX watched by the owner, OTHER watched by someone else; no NONE file."""
    write_csv(tmp_path / "INDEX.csv", {1: "101.25", 2: "100.00"})
    write_csv(tmp_path / "FUNDX.csv", {1: "12.34"})
    write_csv(tmp_path / "OTHER.csv", {1: "20.50"})
    settings.TIINGO_API_KEY = ""
    settings.PRICES_CSV_DIR = tmp_path
    return tmp_path


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("owner", email="owner@example.com")


@pytest.fixture
def someone(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("someone")


@pytest.fixture
def account(owner: User) -> Account:
    """The owner's account: INDEX and cash on a statement, FUNDX and NONE on the watch list."""
    account = Account.objects.create(
        name="Practice", broker="Example Broker", kind="paper", owner=owner
    )
    snapshot = Snapshot.objects.create(account=account, as_of=date(2026, 10, 25), source="test")
    for symbol, shares in (("INDEX", "2.5"), ("CASH", "500")):
        SnapshotLine.objects.create(snapshot=snapshot, symbol=symbol, shares=Decimal(shares))
    Holding.objects.filter(account=account, symbol="CASH").update(kind=Holding.Kind.CASH)
    WatchItem.add_many(account, ["FUNDX", "NONE"])
    return account


@pytest.fixture
def other_account(someone: User) -> Account:
    account = Account.objects.create(name="Theirs", broker="Other", kind="paper", owner=someone)
    WatchItem.objects.create(account=account, symbol="OTHER")
    return account


class Page(Protocol):
    content: bytes


def text(response: Page) -> str:
    return unescape(response.content.decode())


def fetch_url(account: Account | None = None) -> str:
    return f"/accounts/{account.pk}/fetch-prices/" if account else "/accounts/fetch-prices/"


def history_url(account: Account, symbol: str = "FUNDX") -> str:
    return f"/accounts/{account.pk}/watch/{symbol}/fetch-history/"


def tiingo(
    monkeypatch: pytest.MonkeyPatch, settings: Settings, answer: httpx.Response | None = None
) -> list[httpx.Request]:
    """Tiingo behind a `MockTransport`: every request is written down and answered with
    `answer`, or with three closes (400 days, 30 days and 1 day back)."""
    asked: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        asked.append(request)
        if answer is not None:
            return answer
        days = [today() - timedelta(days=age) for age in (400, 30, 1)]
        return httpx.Response(200, json=[{"date": f"{d}T00:00:00.000Z", "close": 10} for d in days])

    monkeypatch.setattr(sources, "transport", httpx.MockTransport(respond))
    settings.TIINGO_API_KEY = TEST_KEY
    return asked


# --- Fetch prices now ----------------------------------------------------------------------------


@pytest.mark.django_db
def test_fetch_now_pulls_the_owners_symbols_and_reports_the_counts(
    client: Client, owner: User, account: Account, other_account: Account, csv_folder: Path
) -> None:
    client.force_login(owner)
    response = client.post(fetch_url(account), follow=True)
    assert response.redirect_chain == [(f"/accounts/{account.pk}/", 302)]
    html = text(response)
    assert (
        "Fetched closes from csv for 3 symbols in 3 requests: 3 inserted, 0 updated, "
        "0 unchanged, 1 refused, 2 backfilled, 0 skipped for budget."
    ) in html
    assert f"Refused NONE: no file NONE.csv in {csv_folder}" in html
    assert "A year of closes, first time: FUNDX, INDEX." in html
    assert "The rest continue tonight." not in html
    assert not DailyClose.objects.filter(symbol="OTHER").exists(), "another owner's symbol"
    assert not DailyClose.objects.filter(symbol="CASH").exists(), "cash has no price"


@pytest.mark.django_db
def test_fetch_now_from_the_accounts_page_returns_there(
    client: Client, owner: User, account: Account, csv_folder: Path
) -> None:
    client.force_login(owner)
    response = client.post(fetch_url(), follow=True)
    assert response.redirect_chain == [("/accounts/", 302)]
    assert "Fetched closes from csv for 3 symbols in 3 requests" in text(response)


@pytest.mark.django_db
def test_fetch_now_with_nothing_held_or_watched_says_so_and_spends_no_guard(
    client: Client, owner: User, csv_folder: Path
) -> None:
    client.force_login(owner)
    html = text(client.post(fetch_url(), follow=True))
    assert "Nothing to fetch: no account of yours holds or watches a symbol." in html
    assert not ManualRun.objects.exists()


@pytest.mark.django_db
def test_a_second_fetch_within_ten_minutes_is_refused_with_the_time_it_can_run(
    client: Client,
    owner: User,
    someone: User,
    account: Account,
    other_account: Account,
    csv_folder: Path,
) -> None:
    client.force_login(owner)
    client.post(fetch_url(account), follow=True)  # the first run's messages are read here
    run = ManualRun.objects.get(kind=ManualRun.Kind.FETCH_NOW, key=str(owner.pk))
    again = text(client.post(fetch_url(account), follow=True))
    next_run = timezone.localtime(run.ran_at + timedelta(minutes=10))
    assert (
        "Prices were fetched less than 10 minutes ago. The next Fetch prices now can run at "
        f"{next_run:%Y-%m-%d %H:%M %Z}."
    ) in again
    assert "Fetched closes" not in again
    client.force_login(someone)
    assert "Fetched closes" in text(client.post(fetch_url(), follow=True)), "per owner"
    ManualRun.objects.filter(pk=run.pk).update(ran_at=run.ran_at - timedelta(minutes=11))
    client.force_login(owner)
    later = text(client.post(fetch_url(account), follow=True))
    assert "0 inserted, 0 updated, 3 unchanged" in later, "a rerun writes nothing twice"


def test_the_guard_claims_once_inside_ten_minutes(db: None) -> None:
    start = timezone.now()
    assert manual.claim("fetch-now", "1", start) is None
    assert manual.claim("fetch-now", "1", start + timedelta(minutes=9)) == start + timedelta(
        minutes=10
    )
    assert manual.claim("fetch-now", "2", start) is None, "another key is not held up"
    assert manual.claim("fetch-now", "1", start + timedelta(minutes=10)) is None
    assert manual.GUARD_MINUTES == 10


@pytest.mark.django_db
def test_fetch_now_stops_at_the_budget_and_says_the_rest_continue_tonight(
    client: Client, owner: User, csv_folder: Path
) -> None:
    account = Account.objects.create(name="Wide", broker="Example", kind="paper", owner=owner)
    symbols = [f"S{number:02d}" for number in range(REQUESTS_PER_RUN + 2)]
    WatchItem.add_many(account, symbols)
    client.force_login(owner)
    html = text(client.post(fetch_url(account), follow=True))
    assert REQUESTS_PER_RUN == 50
    assert "for 52 symbols in 50 requests" in html and "50 refused" in html
    assert "2 skipped for budget." in html
    assert (
        "Stopped by the 50-request limit for one run; not reached: S50, S51. "
        "The rest continue tonight."
    ) in html


def test_the_time_limit_skips_what_is_left(tmp_path: Path, db: None) -> None:
    """The button's run checks its clock before each request; past the limit, the symbols not
    reached are skipped like the budget's, so the page answers inside the function's maximum."""
    write_csv(tmp_path / "INDEX.csv", {1: "1"})
    ticks = iter([0.0, 0.0, 300.0, 300.0])
    result = pull(
        CsvPrices(tmp_path),
        ["INDEX", "FUNDX", "OTHER"],
        today() - timedelta(days=7),
        today(),
        time_limit=manual.FETCH_TIME_LIMIT_SECONDS,
        clock=lambda: next(ticks),
    )
    assert (result.requests, result.skipped, result.stopped) == (
        1,
        ["FUNDX", "OTHER"],
        "time limit",
    )
    assert "Stopped by the time one press may take" in manual.fetch_messages(result)[2][-1]
    assert manual.FETCH_TIME_LIMIT_SECONDS + sources.REQUEST_TIMEOUT_SECONDS < 300


@pytest.mark.django_db
def test_a_tiingo_429_during_fetch_now_is_a_message_not_a_500(
    client: Client,
    owner: User,
    account: Account,
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    asked = tiingo(monkeypatch, settings, httpx.Response(429, text="Too many requests"))
    client.force_login(owner)
    response = client.post(fetch_url(account), follow=True)
    assert response.status_code == 200 and len(asked) == 1
    html = text(response)
    assert "Refused FUNDX: Tiingo answered 429" in html
    assert (
        "Stopped by Tiingo's hourly or daily limit; not reached: INDEX, NONE. "
        "The rest continue tonight."
    ) in html
    assert all(TEST_KEY not in str(request.url) for request in asked)


# --- Get history ---------------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(("choice", "years"), [("1y", 1), ("5y", 5), ("10y", 10), ("all", None)])
def test_each_range_asks_one_request_from_the_right_start_date(
    client: Client,
    owner: User,
    account: Account,
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    choice: str,
    years: int | None,
) -> None:
    asked = tiingo(monkeypatch, settings)
    client.force_login(owner)
    client.post(history_url(account), {"range": choice})
    start = date(1900, 1, 1) if years is None else manual.years_before(today(), years)
    assert len(asked) == 1, "one request for the whole range"
    assert asked[0].url.path == "/tiingo/daily/FUNDX/prices"
    assert asked[0].url.params["startDate"] == start.isoformat()
    assert asked[0].url.params["endDate"] == today().isoformat()


def test_years_before_keeps_the_calendar_day() -> None:
    assert manual.years_before(date(2026, 10, 29), 10) == date(2016, 10, 29)
    assert manual.years_before(date(2028, 2, 29), 1) == date(2027, 2, 28)
    assert manual.history_since("all", date(2026, 10, 29)) == manual.ALL_AVAILABLE_SINCE
    assert manual.history_since("7y", date(2026, 10, 29)) is None


@pytest.mark.django_db
def test_get_history_reports_days_added_and_the_earliest_close_and_a_rerun_adds_none(
    client: Client,
    owner: User,
    account: Account,
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    tiingo(monkeypatch, settings)
    client.force_login(owner)
    response = client.post(history_url(account), {"range": "5y"}, follow=True)
    assert response.redirect_chain == [(f"/accounts/{account.pk}/", 302)]
    earliest = today() - timedelta(days=400)
    since = manual.years_before(today(), 5)
    assert (
        f"FUNDX, 5 years asked (from {since:%Y-%m-%d}): 3 days added, 0 updated, 0 unchanged. "
        f"Earliest close returned: {earliest:%Y-%m-%d}; earliest close now stored: "
        f"{earliest:%Y-%m-%d}."
    ) in text(response)
    assert Backfill.objects.get(symbol="FUNDX").since == since, "the night will not ask again"
    ManualRun.objects.all().delete()  # past the guard
    again = client.post(history_url(account), {"range": "5y", "return_to": "history"}, follow=True)
    assert again.redirect_chain == [(f"/accounts/{account.pk}/watch/FUNDX/", 302)]
    assert "0 days added, 0 updated, 3 unchanged." in text(again)
    assert DailyClose.objects.filter(symbol="FUNDX").count() == 3


@pytest.mark.django_db
def test_get_history_has_its_own_ten_minute_guard_per_symbol(
    client: Client,
    owner: User,
    account: Account,
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    asked = tiingo(monkeypatch, settings)
    client.force_login(owner)
    client.post(history_url(account), {"range": "1y"})
    run = ManualRun.objects.get(kind=ManualRun.Kind.HISTORY, key="FUNDX")
    html = text(client.post(history_url(account), {"range": "10y"}, follow=True))
    next_run = timezone.localtime(run.ran_at + timedelta(minutes=10))
    assert (
        "FUNDX's history was fetched less than 10 minutes ago. Get history can run for it "
        f"again at {next_run:%Y-%m-%d %H:%M %Z}."
    ) in html
    assert len(asked) == 1
    client.post(history_url(account, "NONE"), {"range": "1y"})
    assert len(asked) == 2, "another symbol is not held up"


@pytest.mark.django_db
def test_an_unknown_range_is_refused_before_any_request(
    client: Client,
    owner: User,
    account: Account,
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    asked = tiingo(monkeypatch, settings)
    client.force_login(owner)
    html = text(client.post(history_url(account), {"range": "7y"}, follow=True))
    assert "Pick a range for FUNDX: 1 year, 5 years, 10 years, all available." in html
    assert asked == [] and not ManualRun.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        (
            404,
            "Ticker not found",
            "FUNDX: Tiingo answered 404: Ticker not found. Nothing was stored.",
        ),
        (
            429,
            "Too many requests",
            "FUNDX: Tiingo answered 429: the hourly or daily request limit is reached. "
            "Nothing was stored. Try again after the hour.",
        ),
    ],
)
def test_a_tiingo_refusal_is_a_message_not_a_500(
    client: Client,
    owner: User,
    account: Account,
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    status: int,
    body: str,
    expected: str,
) -> None:
    tiingo(monkeypatch, settings, httpx.Response(status, text=body))
    client.force_login(owner)
    response = client.post(history_url(account), {"range": "1y"}, follow=True)
    assert response.status_code == 200 and expected in text(response)
    assert not DailyClose.objects.filter(symbol="FUNDX").exists()


@pytest.mark.django_db
def test_an_empty_answer_says_the_source_returned_nothing(
    client: Client,
    owner: User,
    account: Account,
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    tiingo(monkeypatch, settings, httpx.Response(200, json=[]))
    client.force_login(owner)
    html = text(client.post(history_url(account), {"range": "all"}, follow=True))
    assert "FUNDX, all available asked (from 1900-01-01): the source returned no closes." in html


# --- Who sees the buttons ------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_buttons_are_the_owners_only(
    client: Client,
    owner: User,
    someone: User,
    account: Account,
    other_account: Account,
    csv_folder: Path,
) -> None:
    for url in (fetch_url(), fetch_url(account), history_url(account)):
        signed_out = client.post(url, {"range": "1y"})
        assert signed_out.status_code == 302 and "/auth/witus/login/" in signed_out["Location"]
    client.force_login(someone)
    assert client.post(fetch_url(account)).status_code == 404
    assert client.post(history_url(account), {"range": "1y"}).status_code == 404
    client.force_login(owner)
    assert client.post(history_url(other_account, "OTHER"), {"range": "1y"}).status_code == 404
    assert client.post(history_url(account, "OTHER"), {"range": "1y"}).status_code == 404
    for url in (fetch_url(), fetch_url(account), history_url(account)):
        assert client.get(url).status_code == 405
    assert not ManualRun.objects.exists() and not DailyClose.objects.exists()


@pytest.mark.django_db
def test_the_buttons_need_the_csrf_token(owner: User, account: Account, csv_folder: Path) -> None:
    strict = Client(enforce_csrf_checks=True)
    strict.force_login(owner)
    assert strict.post(fetch_url(account)).status_code == 403
    assert strict.post(history_url(account), {"range": "1y"}).status_code == 403
    assert not ManualRun.objects.exists()


@pytest.mark.django_db
def test_the_owners_pages_show_the_buttons(
    client: Client, owner: User, account: Account, csv_folder: Path
) -> None:
    client.force_login(owner)
    page = text(client.get(f"/accounts/{account.pk}/"))
    assert f'action="/accounts/{account.pk}/fetch-prices/"' in page
    assert f'action="/accounts/{account.pk}/watch/FUNDX/fetch-history/"' in page
    assert '<option value="10y">10 years</option>' in page
    assert f'action="/accounts/{account.pk}/watch/NONE/fetch-history/"' in page
    listing = text(client.get("/accounts/"))
    assert 'action="/accounts/fetch-prices/"' in listing and "Fetch prices now" in listing
    history = text(client.get(f"/accounts/{account.pk}/watch/FUNDX/"))
    assert f'action="/accounts/{account.pk}/watch/FUNDX/fetch-history/"' in history
    assert 'name="return_to" value="history"' in history


@pytest.mark.django_db
@pytest.mark.parametrize("path", PUBLIC_PATHS)
@pytest.mark.parametrize("signed_in", [False, True])
def test_public_pages_show_neither_button(
    client: Client, owner: User, account: Account, path: str, signed_in: bool
) -> None:
    if signed_in:
        client.force_login(owner)
    html = client.get(path).content.decode()
    assert "Fetch prices now" not in html and "Get history" not in html
    assert "fetch-prices" not in html and "fetch-history" not in html


def test_a_manual_run_reads_as_its_kind_key_and_time() -> None:
    run = ManualRun(kind="history", key="FUNDX", ran_at=datetime(2026, 10, 29, 14, 3))
    assert str(run) == "Get history FUNDX at 2026-10-29 14:03"
