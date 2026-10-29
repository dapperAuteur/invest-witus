"""The add form's "Fetch their history now" and a typed list for Fetch history for selected
(BAM, 2026-10-29).

The price source is a CSV folder (no Tiingo key), so no request leaves the process; the symbols
are placeholders.
"""

from datetime import date, timedelta
from html import unescape
from pathlib import Path
from typing import Protocol

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone
from pytest_django.fixtures import Settings

from invest_witus_site.holdings.models import Account
from invest_witus_site.prices import manual
from invest_witus_site.prices import pull as pull_module
from invest_witus_site.prices.models import DailyClose, ManualRun
from invest_witus_site.prices.sources import PriceSource
from invest_witus_site.watchlist.models import WatchItem


class Page(Protocol):
    content: bytes


def text(response: Page) -> str:
    return unescape(response.content.decode())


def today() -> date:
    return timezone.localdate()


STORED = today() - timedelta(days=100)  # inside every Get history range


@pytest.fixture(autouse=True)
def no_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pull_module, "PAUSE_SECONDS", 0.0)


@pytest.fixture
def csv_folder(tmp_path: Path, settings: Settings) -> Path:
    for symbol in ("FUNDX", "OTHER", "INDEX"):
        (tmp_path / f"{symbol}.csv").write_text(f"date,close\n{STORED.isoformat()},10\n")
    settings.TIINGO_API_KEY = ""
    settings.PRICES_CSV_DIR = tmp_path
    return tmp_path


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("owner")


@pytest.fixture
def someone(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("someone")


@pytest.fixture
def account(owner: User) -> Account:
    """FUNDX already on the watch list."""
    account = Account.objects.create(
        name="Practice", broker="Example Broker", kind="paper", owner=owner
    )
    WatchItem.add_many(account, ["FUNDX"])
    return account


def add_url(account: Account) -> str:
    return f"/accounts/{account.pk}/watch/add/"


def many_url(account: Account) -> str:
    return f"/accounts/{account.pk}/watch/fetch-history/"


def fetched_keys() -> list[str]:
    return list(ManualRun.objects.order_by("pk").values_list("key", flat=True))


# --- The add form -------------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_add_form_offers_fetch_now_ticked_with_a_range(
    client: Client, owner: User, account: Account
) -> None:
    client.force_login(owner)
    html = text(client.get(f"/accounts/{account.pk}/"))
    assert 'name="fetch_history" id="id_fetch_history" checked' in html
    assert "Fetch their history now</label>" in html
    assert '<option value="1y" selected>1 year</option>' in html
    for value in ("5y", "10y", "all"):
        assert f'<option value="{value}">' in html


@pytest.mark.django_db
def test_ticked_the_new_symbols_are_added_and_fetched_in_one_request(
    client: Client, owner: User, account: Account, csv_folder: Path
) -> None:
    client.force_login(owner)
    response = client.post(
        add_url(account),
        {"symbols": "fundx, other INDEX", "fetch_history": "on", "history_range": "5y"},
    )
    assert response.status_code == 302 and response["Location"] == f"/accounts/{account.pk}/"
    html = text(client.get(response["Location"]))
    assert "Added to the watch list: OTHER, INDEX." in html
    assert "Already on the watch list: FUNDX." in html
    for symbol in ("INDEX", "OTHER"):
        assert (
            f"{symbol}, 5 years: 1 day added, 0 updated; earliest close stored {STORED:%Y-%m-%d}."
        ) in html
    assert "FUNDX, 5 years" not in html, "only the symbols this submission added"
    assert sorted(fetched_keys()) == ["INDEX", "OTHER"]
    assert DailyClose.objects.filter(symbol__in=["INDEX", "OTHER"]).count() == 2


@pytest.mark.django_db
def test_unticked_keeps_the_old_behaviour(
    client: Client, owner: User, account: Account, csv_folder: Path
) -> None:
    client.force_login(owner)
    html = text(
        client.post(add_url(account), {"symbols": "OTHER", "history_range": "all"}, follow=True)
    )
    assert "Added to the watch list: OTHER." in html
    assert fetched_keys() == [] and not DailyClose.objects.exists()


@pytest.mark.django_db
def test_fetch_on_add_uses_the_multi_symbol_path_with_its_guard(
    client: Client, owner: User, account: Account, csv_folder: Path
) -> None:
    manual.claim(ManualRun.Kind.HISTORY, "OTHER")
    client.force_login(owner)
    html = text(
        client.post(
            add_url(account),
            {"symbols": "OTHER INDEX", "fetch_history": "on", "history_range": "1y"},
            follow=True,
        )
    )
    assert "Added to the watch list: OTHER, INDEX." in html
    assert "INDEX, 1 year: 1 day added" in html
    assert "Skipped, fetched less than 10 minutes ago" in html and "OTHER (at " in html


@pytest.mark.django_db
def test_fetch_on_add_hands_the_added_symbols_and_range_to_fetch_history_many(
    client: Client,
    owner: User,
    account: Account,
    csv_folder: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], date]] = []
    real = manual.fetch_history_many

    def spy(source: PriceSource, symbols: list[str], since: date, until: date) -> object:
        calls.append((list(symbols), since))
        return real(source, symbols, since, until)

    monkeypatch.setattr(manual, "fetch_history_many", spy)
    client.force_login(owner)
    client.post(
        add_url(account), {"symbols": "FUNDX OTHER", "fetch_history": "on", "history_range": "all"}
    )
    assert calls == [(["OTHER"], manual.ALL_AVAILABLE_SINCE)]


@pytest.mark.django_db
def test_nothing_new_added_means_nothing_fetched(
    client: Client, owner: User, account: Account, csv_folder: Path
) -> None:
    client.force_login(owner)
    html = text(
        client.post(
            add_url(account),
            {"symbols": "FUNDX", "fetch_history": "on", "history_range": "1y"},
            follow=True,
        )
    )
    assert "Already on the watch list: FUNDX." in html and fetched_keys() == []


@pytest.mark.django_db
def test_another_owner_cannot_add_or_fetch(
    client: Client, someone: User, account: Account, csv_folder: Path
) -> None:
    client.force_login(someone)
    response = client.post(
        add_url(account), {"symbols": "OTHER", "fetch_history": "on", "history_range": "1y"}
    )
    assert response.status_code == 404
    assert fetched_keys() == [] and WatchItem.objects.filter(symbol="OTHER").count() == 0


# --- A typed list for Fetch history for selected ------------------------------------------------


@pytest.mark.django_db
def test_the_bulk_form_has_a_typed_box(client: Client, owner: User, account: Account) -> None:
    client.force_login(owner)
    html = text(client.get(f"/accounts/{account.pk}/"))
    assert '<label for="bulk-history-typed">Or type symbols</label>' in html
    assert 'name="typed" id="bulk-history-typed"' in html


@pytest.mark.django_db
def test_a_typed_list_is_parsed_like_the_add_box_and_kept_to_this_list(
    client: Client, owner: User, account: Account, csv_folder: Path
) -> None:
    WatchItem.add_many(account, ["OTHER"])
    client.force_login(owner)
    html = text(
        client.post(
            many_url(account),
            {"which": "selected", "typed": "other, fundx  index other bad$sym", "range": "1y"},
            follow=True,
        )
    )
    for symbol in ("FUNDX", "OTHER"):
        assert f"{symbol}, 1 year: 1 day added" in html
    assert "Not on this watch list, so left out: INDEX." in html
    assert "Refused: BAD$SYM (" in html
    assert sorted(fetched_keys()) == ["FUNDX", "OTHER"], "each once, INDEX never asked"


@pytest.mark.django_db
def test_typed_and_ticked_symbols_join(
    client: Client, owner: User, account: Account, csv_folder: Path
) -> None:
    WatchItem.add_many(account, ["OTHER"])
    client.force_login(owner)
    client.post(
        many_url(account),
        {"which": "selected", "symbols": ["FUNDX"], "typed": "other", "range": "1y"},
    )
    assert sorted(fetched_keys()) == ["FUNDX", "OTHER"]


@pytest.mark.django_db
def test_a_typed_list_with_nothing_on_this_list_fetches_nothing(
    client: Client, owner: User, account: Account, csv_folder: Path
) -> None:
    client.force_login(owner)
    html = text(
        client.post(
            many_url(account), {"which": "selected", "typed": "INDEX", "range": "1y"}, follow=True
        )
    )
    assert "Not on this watch list, so left out: INDEX." in html
    assert "Tick or type at least one symbol on this list" in html and fetched_keys() == []
