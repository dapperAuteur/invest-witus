"""The symbol profile (2026-10-30, decision 150, backlog item 3): the symbol page shows what the
vendor says the symbol is (name, exchange, a short description) with its source and date, from
Tiingo's ticker metadata endpoint, stored in `SymbolProfile` and refreshed at most weekly by the
nightly pull or Get description. The Wikipedia link is the search page only, never a guessed
article. Owner only. Every request here goes to an `httpx.MockTransport`; the symbols and the
fixture are placeholders, not real securities.
"""

import json
from datetime import timedelta
from html import unescape
from pathlib import Path

import httpx
import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone
from pytest_django.fixtures import Settings

from invest_witus_site.holdings.models import Account
from invest_witus_site.prices import profiles, sources
from invest_witus_site.prices import pull as pull_module
from invest_witus_site.prices.models import ManualRun, SymbolProfile
from invest_witus_site.prices.profiles import (
    PROFILES_PER_RUN,
    REFRESH_DAYS,
    fetch_profile,
    parse_profile,
    refresh_profiles,
    wikipedia_search_url,
)
from invest_witus_site.prices.sources import PriceSourceError, TiingoEod
from invest_witus_site.watchlist.models import WatchItem

BASE_DIR = Path(__file__).resolve().parent.parent
FIXTURE = (BASE_DIR / "tests" / "fixtures" / "tiingo" / "meta-FUNDX.json").read_text("utf-8")
TEST_KEY = "test-only-tiingo-key"
SECRET = "test-only-cron-secret-0123456789"
CRON = "/api/cron/pull-prices/"


class FakeTiingo:
    """Answers the metadata endpoint from the fixture (any ticker, its own symbol in `ticker`),
    the prices endpoint with one close, and a status per ticker when told to."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.status: dict[str, int] = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        parts = request.url.path.split("/")  # ["", "tiingo", "daily", ticker, ("prices")]
        ticker = parts[3]
        if ticker in self.status:
            return httpx.Response(self.status[ticker], text=f"status for {ticker}")
        if len(parts) == 5:
            day = (timezone.localdate() - timedelta(days=1)).isoformat()
            return httpx.Response(200, json=[{"date": day, "close": 12.34}])
        body = json.loads(FIXTURE)
        body["ticker"] = ticker
        return httpx.Response(200, json=body)

    def meta_paths(self) -> list[str]:
        return [r.url.path for r in self.requests if not r.url.path.endswith("/prices")]


@pytest.fixture
def tiingo(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> FakeTiingo:
    fake = FakeTiingo()
    monkeypatch.setattr(sources, "transport", httpx.MockTransport(fake))
    monkeypatch.setattr(pull_module, "PAUSE_SECONDS", 0.0)
    settings.TIINGO_API_KEY = TEST_KEY
    return fake


@pytest.fixture
def no_key(settings: Settings, tmp_path: Path) -> None:
    settings.TIINGO_API_KEY = ""
    settings.PRICES_CSV_DIR = tmp_path


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("owner")


@pytest.fixture
def someone(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("someone")


@pytest.fixture
def account(owner: User) -> Account:
    account = Account.objects.create(owner=owner, name="Practice", broker="Example Broker")
    WatchItem.objects.create(account=account, symbol="FUNDX")
    return account


def page(account: Account, symbol: str = "FUNDX") -> str:
    return f"/accounts/{account.pk}/watch/{symbol}/"


def button(account: Account, symbol: str = "FUNDX") -> str:
    return f"/accounts/{account.pk}/watch/{symbol}/profile/"


def text(response: object) -> str:
    return unescape(response.content.decode())  # type: ignore[attr-defined]


def stored(**overrides: object) -> SymbolProfile:
    values: dict[str, object] = {
        "symbol": "FUNDX",
        "name": "Example Total Market Index Fund",
        "exchange_code": "NYSE ARCA",
        "description": "A placeholder fund for the tests.",
        "source": "tiingo",
        "fetched_at": timezone.now(),
    }
    values.update(overrides)
    return SymbolProfile.objects.create(**values)


# --- Parsing and the request ---------------------------------------------------------------------


def test_the_metadata_fixture_parses_to_every_documented_field() -> None:
    data = parse_profile("FUNDX", FIXTURE)
    assert data.name == "Example Total Market Index Fund"
    assert data.exchange_code == "NYSE ARCA"
    assert data.description.startswith("A placeholder fund for the tests.")
    assert (data.start_date.isoformat(), data.end_date.isoformat()) == (  # type: ignore[union-attr]
        "1993-01-29",
        "2026-10-29",
    )


def test_null_fields_are_empty_and_whitespace_is_collapsed() -> None:
    body = (
        '{"name": "  Example\\n  Fund ", "description": null, "startDate": null, "endDate": null}'
    )
    data = parse_profile("FUNDX", body)
    assert (data.name, data.exchange_code, data.description) == ("Example Fund", "", "")
    assert (data.start_date, data.end_date) == (None, None)


def test_a_long_name_is_cut_to_its_column() -> None:
    data = parse_profile("FUNDX", json.dumps({"name": "x" * 500}))
    assert len(data.name) == 200


@pytest.mark.parametrize(
    ("body", "problem"),
    [
        ("not json", "not JSON"),
        ("[]", "expected one object of metadata"),
        ('{"name": 7}', "name is not text"),
        ('{"startDate": "soon"}', "startDate is not a date"),
    ],
)
def test_a_body_it_does_not_understand_is_refused(body: str, problem: str) -> None:
    with pytest.raises(PriceSourceError) as caught:
        parse_profile("FUNDX", body)
    assert problem in caught.value.problem


@pytest.mark.django_db
def test_the_request_is_one_get_to_the_metadata_endpoint_with_the_token_in_the_header(
    tiingo: FakeTiingo,
) -> None:
    profile = fetch_profile(TiingoEod(TEST_KEY), "FUNDX")
    (request,) = tiingo.requests
    assert (request.method, request.url.host) == ("GET", "api.tiingo.com")
    assert request.url.path == "/tiingo/daily/FUNDX"
    assert request.headers["Authorization"] == f"Token {TEST_KEY}"
    assert TEST_KEY not in str(request.url)
    assert (profile.name, profile.exchange_code, profile.source) == (
        "Example Total Market Index Fund",
        "NYSE ARCA",
        "tiingo",
    )


@pytest.mark.django_db
def test_a_refusal_stores_nothing_and_a_429_says_retry_later(tiingo: FakeTiingo) -> None:
    tiingo.status = {"NONE": 404, "BUSY": 429}
    with pytest.raises(PriceSourceError) as missing:
        fetch_profile(TiingoEod(TEST_KEY), "NONE")
    assert "Tiingo answered 404" in missing.value.problem and not missing.value.retry_later
    with pytest.raises(PriceSourceError) as busy:
        fetch_profile(TiingoEod(TEST_KEY), "BUSY")
    assert busy.value.retry_later
    assert not SymbolProfile.objects.exists()


def test_the_wikipedia_link_is_the_search_page_for_the_name() -> None:
    url = wikipedia_search_url("Example Fund & Co")
    assert url == "https://en.wikipedia.org/w/index.php?search=Example+Fund+%26+Co"


# --- Weekly refresh ------------------------------------------------------------------------------


@pytest.mark.django_db
def test_refresh_asks_only_for_missing_or_week_old_profiles(tiingo: FakeTiingo) -> None:
    now = timezone.now()
    stored(symbol="FRESH", fetched_at=now - timedelta(days=REFRESH_DAYS - 1))
    stored(symbol="STALE", fetched_at=now - timedelta(days=REFRESH_DAYS + 1), name="Old")
    run = refresh_profiles(TiingoEod(TEST_KEY), ["FRESH", "NEW", "STALE"], budget=50, now=now)
    assert tiingo.meta_paths() == ["/tiingo/daily/NEW", "/tiingo/daily/STALE"]
    assert (run.requests, run.fetched, run.failed, run.skipped) == (2, ["NEW", "STALE"], {}, [])
    assert SymbolProfile.objects.get(symbol="STALE").name == "Example Total Market Index Fund"


@pytest.mark.django_db
def test_refresh_stays_inside_the_budget_and_the_per_run_cap(tiingo: FakeTiingo) -> None:
    symbols = [f"S{n:02d}" for n in range(PROFILES_PER_RUN + 3)]
    run = refresh_profiles(TiingoEod(TEST_KEY), symbols, budget=50)
    assert run.requests == PROFILES_PER_RUN and run.skipped == symbols[PROFILES_PER_RUN:]
    small = refresh_profiles(TiingoEod(TEST_KEY), symbols, budget=1)
    assert small.requests == 1 and small.fetched == [symbols[PROFILES_PER_RUN]]
    assert refresh_profiles(TiingoEod(TEST_KEY), symbols, budget=0).requests == 0


@pytest.mark.django_db
def test_refresh_stops_at_a_rate_limit_and_records_a_refusal(tiingo: FakeTiingo) -> None:
    tiingo.status = {"NONE": 404, "BUSY": 429}
    run = refresh_profiles(TiingoEod(TEST_KEY), ["NONE", "BUSY", "LATER"], budget=50)
    assert set(run.failed) == {"NONE", "BUSY"} and run.skipped == ["LATER"]
    assert run.requests == 2 and not SymbolProfile.objects.exists()


@pytest.mark.django_db
def test_the_cron_fetches_profiles_after_the_closes_with_the_budget_left(
    client: Client, settings: Settings, tiingo: FakeTiingo, account: Account
) -> None:
    settings.CRON_SECRET = SECRET
    body = client.get(CRON, headers={"Authorization": f"Bearer {SECRET}"}).json()
    assert body["requests"] == 1
    assert body["profiles"] == {"requests": 1, "fetched": ["FUNDX"], "failed": {}, "skipped": []}
    assert [r.url.path for r in tiingo.requests] == [
        "/tiingo/daily/FUNDX/prices",
        "/tiingo/daily/FUNDX",
    ]
    again = client.get(CRON, headers={"Authorization": f"Bearer {SECRET}"}).json()
    assert again["profiles"]["requests"] == 0, "at most weekly"


@pytest.mark.django_db
def test_the_cron_body_is_unchanged_without_a_tiingo_key(
    client: Client, settings: Settings, no_key: None, account: Account
) -> None:
    settings.CRON_SECRET = SECRET
    body = client.get(CRON, headers={"Authorization": f"Bearer {SECRET}"}).json()
    assert "profiles" not in body


# --- The symbol page -----------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_page_shows_name_exchange_short_description_source_and_date(
    client: Client, owner: User, account: Account, tiingo: FakeTiingo
) -> None:
    profile = fetch_profile(TiingoEod(TEST_KEY), "FUNDX")
    client.force_login(owner)
    html = text(client.get(page(account)))
    assert '<h2 id="profile-heading">About FUNDX</h2>' in html
    assert "<strong>Example Total Market Index Fund</strong> · Exchange: NYSE ARCA" in html
    assert "<summary>Full description</summary>" in html, "the long description is cut"
    assert "thirty the end." in html.split("<summary>")[1]
    assert f"Description from Tiingo, as of {profile.fetched_at:%Y-%m-%d}." in html
    assert "Information only, not advice or a recommendation." in html
    assert "The source has prices from 1993-01-29 to 2026-10-29." in html
    assert (
        'More about Example Total Market Index Fund: <a href="https://en.wikipedia.org/w/'
        'index.php?search=Example+Total+Market+Index+Fund" rel="noopener noreferrer">'
        "Search Wikipedia</a>"
    ) in html
    assert "wikipedia.org/wiki/" not in html, "never a guessed article"
    assert "Refreshes at most once every 7 days." in html and "Get description" not in html


@pytest.mark.django_db
def test_no_name_means_no_wikipedia_link(client: Client, owner: User, account: Account) -> None:
    stored(name="", description="")
    client.force_login(owner)
    html = text(client.get(page(account)))
    assert "Search Wikipedia" not in html and "No name in the source's metadata." in html
    assert "The source has no description for FUNDX." in html


@pytest.mark.django_db
def test_with_no_profile_the_page_offers_get_description(
    client: Client, owner: User, account: Account, tiingo: FakeTiingo
) -> None:
    client.force_login(owner)
    html = text(client.get(page(account)))
    assert "No description stored yet. The nightly pull fetches it;" in html
    assert f'action="{button(account)}"' in html and ">Get description</button>" in html
    assert tiingo.requests == [], "a page never asks the vendor"


@pytest.mark.django_db
def test_without_a_key_the_page_says_where_descriptions_come_from(
    client: Client, owner: User, account: Account, no_key: None
) -> None:
    client.force_login(owner)
    html = text(client.get(page(account)))
    assert "this copy has no Tiingo key" in html and "Get description" not in html


# --- Get description -----------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_description_fetches_once_and_then_waits_a_week(
    client: Client, owner: User, account: Account, tiingo: FakeTiingo
) -> None:
    client.force_login(owner)
    response = client.post(button(account), follow=True)
    assert response.redirect_chain[-1][0] == page(account)
    assert "Fetched FUNDX's name and description from Tiingo." in text(response)
    assert tiingo.meta_paths() == ["/tiingo/daily/FUNDX"]
    again = text(client.post(button(account), follow=True))
    assert "refreshes at most once every 7 days" in again
    assert len(tiingo.requests) == 1


@pytest.mark.django_db
def test_a_week_old_profile_can_be_fetched_again(
    client: Client, owner: User, account: Account, tiingo: FakeTiingo
) -> None:
    stored(name="Old name", fetched_at=timezone.now() - timedelta(days=REFRESH_DAYS + 1))
    client.force_login(owner)
    assert ">Get description again</button>" in text(client.get(page(account)))
    client.post(button(account))
    assert SymbolProfile.objects.get(symbol="FUNDX").name == "Example Total Market Index Fund"


@pytest.mark.django_db
def test_a_refusal_is_a_message_and_the_guard_holds_ten_minutes(
    client: Client, owner: User, account: Account, tiingo: FakeTiingo
) -> None:
    tiingo.status = {"FUNDX": 404}
    client.force_login(owner)
    html = text(client.post(button(account), follow=True))
    assert "FUNDX: Tiingo answered 404" in html and "Nothing was stored." in html
    html = text(client.post(button(account), follow=True))
    assert "Get description can run for it again at" in html
    assert len(tiingo.requests) == 1
    assert ManualRun.objects.filter(kind="profile", key="FUNDX").exists()


@pytest.mark.django_db
def test_get_description_without_a_key_asks_nothing(
    client: Client, owner: User, account: Account, no_key: None
) -> None:
    client.force_login(owner)
    html = text(client.post(button(account), follow=True))
    assert "TIINGO_API_KEY is not set here" in html and not SymbolProfile.objects.exists()


@pytest.mark.django_db
def test_owner_only_and_post_only(
    client: Client, owner: User, someone: User, account: Account, tiingo: FakeTiingo
) -> None:
    stored()
    signed_out = client.get(page(account))
    assert signed_out.status_code == 302 and "Example Total" not in text(signed_out)
    assert client.post(button(account)).status_code == 302  # to the sign-in page
    client.force_login(someone)
    assert client.get(page(account)).status_code == 404
    assert client.post(button(account)).status_code == 404
    client.force_login(owner)
    assert client.post(button(account, "OTHER")).status_code == 404, "not on this watch list"
    assert client.get(button(account)).status_code == 405
    assert tiingo.requests == []


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/", "/faq/", "/privacy/", "/terms/", "/contact/", "/waitlist/"])
def test_no_public_page_shows_a_description(client: Client, path: str) -> None:
    stored()
    assert "Example Total Market Index Fund" not in text(client.get(path))


def test_profile_constants() -> None:
    assert (REFRESH_DAYS, PROFILES_PER_RUN) == (7, 10)
    assert profiles.WIKIPEDIA_SEARCH.startswith("https://en.wikipedia.org/w/index.php?search=")
