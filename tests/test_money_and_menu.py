"""Money and share counts as people read them, and the paper page in the menu (2026-10-29).

`money` shows US dollars to the cent with a `$` and thousands commas, halves rounded up; a
negative is `-$1,234.56`. `quantity` shows shares with commas and up to six places, the trailing
zeros dropped. Both read Decimals without a float, and a `None` is the empty text `plain_number`
already gave it. One rendered page per area plants a value of at least 1,000 and finds the `$`
and the comma. The header's "Paper account" link is for the owner who may open the paper page,
and for no one else. Placeholder symbols only.
"""

from datetime import date, timedelta
from decimal import Decimal
from html import unescape
from typing import Protocol

import httpx
import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone
from pytest_django.fixtures import Settings

from invest_witus.prices.csv_file import PricePoint
from invest_witus_site.holdings.models import Account, Snapshot, SnapshotLine
from invest_witus_site.holdings.templatetags.holdings_extras import money, quantity
from invest_witus_site.methods.models import JournalEntry, MethodPlan
from invest_witus_site.paper import alpaca
from invest_witus_site.prices.models import DailyClose
from invest_witus_site.watchlist.models import WatchItem

D = Decimal
PAPER_LINK = "Paper account"


class Page(Protocol):
    content: bytes


def text(response: Page) -> str:
    return unescape(response.content.decode())


# --- The two filters -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "shown"),
    [
        (D("0.005"), "$0.01"),  # half a cent rounds up
        (D("2.675"), "$2.68"),  # a float would have made this 2.67
        (D("2.674999"), "$2.67"),
        (D("-0.005"), "-$0.01"),  # halves go away from zero
        (D("-0.004"), "$0.00"),  # never -$0.00
        (D("-1234.5"), "-$1,234.50"),
        (D("1234567.891"), "$1,234,567.89"),
        (D("101.230000"), "$101.23"),  # a close column's six places
        (D("0"), "$0.00"),
        (5, "$5.00"),
        (None, ""),
    ],
)
def test_money_is_dollars_to_the_cent_with_commas(value: Decimal | int | None, shown: str) -> None:
    assert money(value) == shown


@pytest.mark.parametrize(
    ("value", "shown"),
    [
        (D("1234.500000"), "1,234.5"),
        (D("0.123456"), "0.123456"),
        (D("10.000000"), "10"),
        (D("1234567.1234565"), "1,234,567.123457"),  # six places, half up
        (D("-2.5"), "-2.5"),
        (D("0.0000004"), "0"),
        (None, ""),
    ],
)
def test_quantity_is_shares_with_commas_and_no_trailing_zeros(
    value: Decimal | None, shown: str
) -> None:
    assert quantity(value) == shown


# --- One page per area ---------------------------------------------------------------------------


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("owner", email="owner@example.com")


@pytest.fixture
def account(owner: User) -> Account:
    return Account.objects.create(
        name="Practice", broker="Example Broker", kind="paper", owner=owner
    )


@pytest.mark.django_db
def test_the_account_page_shows_shares_closes_and_values_as_money(
    client: Client, owner: User, account: Account
) -> None:
    snapshot = Snapshot.objects.create(account=account, as_of=date(2026, 10, 25))
    SnapshotLine.objects.create(snapshot=snapshot, symbol="INDEX", shares=D("1500.25"))
    yesterday = timezone.localdate() - timedelta(days=1)
    DailyClose.upsert("INDEX", [PricePoint(yesterday, D("1234.5"))], "csv")
    client.force_login(owner)
    html = text(client.get(f"/accounts/{account.pk}/"))
    assert '<td class="num">1,500.25</td>' in html
    assert '<td class="num">$1,234.50</td>' in html
    assert "$1,852,058.63" in html  # 1500.25 x 1234.5 = 1852058.625, half up


@pytest.mark.django_db
def test_the_watch_list_shows_each_close_as_money(
    client: Client, owner: User, account: Account
) -> None:
    WatchItem.objects.create(account=account, symbol="FUNDX")
    DailyClose.upsert(
        "FUNDX", [PricePoint(timezone.localdate() - timedelta(days=1), D("2345.678"))], "csv"
    )
    client.force_login(owner)
    assert "$2,345.68" in text(client.get(f"/accounts/{account.pk}/"))


@pytest.mark.django_db
@pytest.mark.parametrize("view", ["a", "b", "c"])
def test_each_method_view_shows_the_plan_and_the_journal_as_money(
    client: Client, owner: User, account: Account, view: str
) -> None:
    MethodPlan.objects.create(
        account=account,
        method_id="index-dca",
        amount=D("1500.00"),
        buy_window_days=7,
        symbols="INDEX",
        started_on=date(2026, 1, 1),
    )
    JournalEntry.objects.create(
        account=account,
        date=date(2026, 1, 2),
        action="buy",
        symbol="INDEX",
        amount=D("1500.00"),
        shares=D("1234.5"),
    )
    client.force_login(owner)
    html = text(client.get(f"/accounts/{account.pk}/method/?view={view}&through=2026-01-31"))
    assert "$1,500.00 into INDEX" in html
    if view != "c":
        assert '<td class="num">1,234.5</td>' in html, "the journal's shares"


@pytest.fixture
def superowner(django_user_model: type[User]) -> User:
    """The site owner: a superuser, as the paper page requires (chapter 11)."""
    return django_user_model.objects.create_superuser("site-owner", "site@example.com", "pw")


@pytest.fixture
def linked(superowner: User) -> Account:
    return Account.objects.create(
        name="Paper", broker="Alpaca", kind="paper", alpaca="paper", owner=superowner
    )


def alpaca_answers(request: httpx.Request) -> httpx.Response:
    """Alpaca's account and positions with made-up numbers above 1,000."""
    if request.url.path == "/v2/account":
        body: object = {
            "cash": "12345.67",
            "buying_power": "24691.34",
            "equity": "13579.01",
            "status": "ACTIVE",
            "trading_blocked": False,
        }
        return httpx.Response(200, json=body)
    if request.url.path == "/v2/positions":
        position = {
            "symbol": "INDEX",
            "qty": "1500.5",
            "avg_entry_price": "1.00",
            "current_price": "1.25",
            "lastday_price": "1.20",
            "market_value": "1875.63",
        }
        return httpx.Response(200, json=[position])
    return httpx.Response(404, json={"message": "no such route"})


@pytest.mark.django_db
def test_the_paper_page_shows_the_budget_alpacas_cash_and_shares_formatted(
    client: Client,
    superowner: User,
    linked: Account,
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
) -> None:
    monkeypatch.setattr(alpaca, "transport", httpx.MockTransport(alpaca_answers))
    settings.ALPACA_PAPER_KEY_ID = "TESTKEYID0000"
    settings.ALPACA_PAPER_SECRET_KEY = "test-secret-not-a-real-key"
    MethodPlan.objects.create(
        account=linked,
        method_id="index-dca",
        amount=D("100.00"),
        buy_window_days=7,
        symbols="INDEX",
        started_on=date(2026, 11, 1),
        practice_budget=D("25000.00"),
    )
    client.force_login(superowner)
    html = text(client.get(f"/accounts/{linked.pk}/paper/"))
    assert "<dt>Budget</dt><dd>$25,000.00</dd>" in html
    assert "<dt>Cash</dt><dd>$12,345.67</dd>" in html
    assert '<td class="num">1,500.5</td>' in html and "$1,875.63" in html


# --- The paper page in the menu ------------------------------------------------------------------


def paper_href(account: Account) -> str:
    return f'<a href="/accounts/{account.pk}/paper/">{PAPER_LINK}</a>'


@pytest.mark.django_db
def test_the_owner_of_a_linked_account_finds_the_paper_page_in_the_header_and_the_list(
    client: Client, superowner: User, linked: Account
) -> None:
    client.force_login(superowner)
    for path in ("/", "/faq/", "/accounts/", f"/accounts/{linked.pk}/"):
        assert paper_href(linked) in text(client.get(path)), path
    listing = text(client.get("/accounts/"))
    assert listing.count(paper_href(linked)) == 2, "once in the header, once on the account's row"


@pytest.mark.django_db
def test_no_paper_link_signed_out(client: Client, linked: Account) -> None:
    for path in ("/", "/faq/", "/privacy/"):
        html = text(client.get(path))
        assert PAPER_LINK not in html and "/paper/" not in html, path


@pytest.mark.django_db
def test_no_paper_link_for_an_owner_without_a_linked_account(
    client: Client, owner: User, account: Account, superowner: User, linked: Account
) -> None:
    # A plain owner of an unlinked paper account, while someone else's account is linked.
    client.force_login(owner)
    for path in ("/", "/accounts/"):
        assert PAPER_LINK not in text(client.get(path)), path
    # A superuser whose only paper account is not linked.
    Account.objects.filter(pk=linked.pk).update(alpaca="")
    client.force_login(superowner)
    for path in ("/", "/accounts/"):
        assert PAPER_LINK not in text(client.get(path)), path


@pytest.mark.django_db
def test_the_sign_out_control_is_unchanged_beside_the_new_link(
    client: Client, superowner: User, linked: Account
) -> None:
    client.force_login(superowner)
    html = text(client.get("/"))
    header = html.split("<header", 1)[1].split("</header>", 1)[0]
    assert header.index(PAPER_LINK) < header.index("Sign out")
