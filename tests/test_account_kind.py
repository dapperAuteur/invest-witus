"""Decision 172: a practice account and a real one told apart beside every account name. The kind is
derived from `Account.kind` (Paper is practice; Brokerage and Retirement are real), shown as a
symbol hidden from screen readers plus a word that is read, never by color or symbol alone."""

import re
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.test import Client

from invest_witus_site.holdings.models import Account
from invest_witus_site.holdings.templatetags.holdings_extras import account_kind, account_kind_key
from invest_witus_site.methods.models import MethodPlan

PRACTICE = (
    '<span class="account-kind account-kind-practice" title="Practice account: paper money, for '
    'trying a method"><span aria-hidden="true">\N{TEST TUBE}</span> Practice</span>'
)
REAL = (
    '<span class="account-kind account-kind-real" title="Real account: your broker&#x27;s '
    'statements"><span aria-hidden="true">\N{BANK}</span> Real</span>'
)


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_superuser("owner", "owner@example.com", "pw")


@pytest.fixture
def owner_client(client: Client, owner: User) -> Client:
    client.force_login(owner)
    return client


def make(owner: User, name: str, kind: str) -> Account:
    return Account.objects.create(name=name, broker="Example Broker", kind=kind, owner=owner)


def test_paper_is_practice_and_every_other_kind_is_real() -> None:
    assert account_kind_key(Account(kind="paper")) == "practice"
    assert account_kind_key(Account(kind="brokerage")) == "real"
    assert account_kind_key(Account(kind="retirement")) == "real"


def test_the_badge_is_a_hidden_symbol_and_a_word_that_is_read() -> None:
    assert str(account_kind(Account(kind="paper"))) == PRACTICE
    assert str(account_kind(Account(kind="retirement"))) == REAL


def badge_after(page: str, name: str) -> str:
    """The kind word that follows an account's name on a page, tags stripped."""
    words = " ".join(re.sub(r"<[^>]+>", " ", page).split())
    found = re.search(re.escape(name) + r" \W* (Practice|Real)\b", words)
    return found.group(1) if found else ""


@pytest.mark.django_db
def test_the_account_list_and_each_account_page_say_practice_or_real(
    owner_client: Client, owner: User
) -> None:
    paper = make(owner, "Momentum try", "paper")
    real = make(owner, "Brokerage IRA", "retirement")
    listing = owner_client.get("/accounts/").content.decode()
    assert badge_after(listing, "Momentum try") == "Practice"
    assert badge_after(listing, "Brokerage IRA") == "Real"
    assert PRACTICE in owner_client.get(f"/accounts/{paper.pk}/").content.decode()
    assert REAL in owner_client.get(f"/accounts/{real.pk}/").content.decode()
    assert PRACTICE in owner_client.get(f"/accounts/{paper.pk}/method/").content.decode()
    assert PRACTICE in owner_client.get(f"/accounts/{paper.pk}/logbook/").content.decode()


@pytest.mark.django_db
def test_the_compare_page_and_the_slots_page_say_it_too(owner_client: Client, owner: User) -> None:
    paper = make(owner, "Momentum try", "paper")
    real = make(owner, "Brokerage IRA", "brokerage")
    for each in (paper, real):
        MethodPlan.objects.create(
            account=each,
            method_id="index-dca",
            amount=Decimal("100"),
            buy_window_days=5,
            symbols="INDEX",
            started_on=date(2026, 1, 1),
        )
    page = owner_client.get("/compare/").content.decode()
    assert page.count(PRACTICE) == 2  # the picker and the table
    assert page.count(REAL) == 2
    slots = owner_client.get("/accounts/alpaca-slots/").content.decode()
    assert badge_after(slots, "Momentum try") == "Practice"
