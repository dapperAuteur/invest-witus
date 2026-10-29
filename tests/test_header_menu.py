"""The header's Logbook link and its menu on small screens (decision 115, 2026-10-29).

The signed-in owner gets a "Logbook" link to the first account, by id, with a plan or a journal
entry; a visitor and an owner with neither get none, and `/accounts/` links every account's
logbook. A signed-in page's links sit in a list a real `<button>` (`aria-expanded`,
`aria-controls`) folds on a narrow screen; the button starts `hidden`, so with JavaScript off the
list shows. Signed out there is no button and no script, as chapter 06a requires. "Sign in" and
"Sign out" stay outside the folding list with their exact names. Placeholder symbols only.
"""

import re
from datetime import date
from decimal import Decimal
from html import unescape
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.test import Client

from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.models import JournalEntry, MethodPlan
from tests.test_ch04 import PUBLIC_PATHS, SIGN_IN, element, links_in

D = Decimal
STATIC = Path(__file__).resolve().parents[1] / "src/invest_witus_site/pages/static/pages"


def header(client: Client, path: str = "/") -> str:
    response = client.get(path)
    assert response.status_code == 200, path
    return unescape(element(response.content.decode(), "header"))


def folding_list(html: str) -> str:
    match = re.search(r'<ul class="menu-links" id="primary-menu">.*?</ul>', html, re.DOTALL)
    assert match, "no folding list in the header"
    return match.group(0)


def logbook_link(account: Account) -> tuple[str, str]:
    return (f"/accounts/{account.pk}/logbook/", "Logbook")


def plan_on(account: Account) -> MethodPlan:
    return MethodPlan.objects.create(
        account=account,
        method_id="index-dca",
        amount=D("100.00"),
        buy_window_days=7,
        symbols="INDEX",
        started_on=date(2026, 1, 1),
    )


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("owner", "owner@example.com", "pw")


@pytest.fixture
def empty(owner: User) -> Account:
    """The owner's first account, with no plan and no entry."""
    return Account.objects.create(name="Empty", broker="Example", kind="paper", owner=owner)


@pytest.fixture
def practice(owner: User, empty: Account) -> Account:
    """The owner's second account, which runs a plan."""
    account = Account.objects.create(name="Practice", broker="Example", kind="paper", owner=owner)
    plan_on(account)
    return account


# --- The Logbook link -----------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_owner_gets_the_logbook_of_the_first_account_with_a_plan(
    client: Client, owner: User, empty: Account, practice: Account
) -> None:
    client.force_login(owner)
    for path in ("/", "/faq/", "/accounts/", f"/accounts/{practice.pk}/logbook/"):
        links = links_in(header(client, path))
        assert logbook_link(practice) in links, path
        assert logbook_link(empty) not in links, "an account with no plan and no entry"
    assert client.get(logbook_link(practice)[0]).status_code == 200


@pytest.mark.django_db
def test_an_entry_without_a_plan_also_earns_the_link(
    client: Client, owner: User, empty: Account
) -> None:
    client.force_login(owner)
    assert "Logbook" not in header(client)
    JournalEntry.objects.create(
        account=empty, date=date(2026, 1, 2), action="buy", symbol="INDEX", amount=D("100")
    )
    assert logbook_link(empty) in links_in(header(client))


@pytest.mark.django_db
def test_no_logbook_link_signed_out_or_for_someone_elses_account(
    client: Client, django_user_model: type[User], practice: Account
) -> None:
    for path in PUBLIC_PATHS:
        assert "Logbook" not in header(client, path), path
    client.force_login(django_user_model.objects.create_user("someone"))
    assert "Logbook" not in header(client)


@pytest.mark.django_db
def test_the_accounts_list_links_every_accounts_logbook(
    client: Client, owner: User, empty: Account, practice: Account
) -> None:
    client.force_login(owner)
    main = unescape(client.get("/accounts/").content.decode()).split("</header>", 1)[1]
    links = links_in(main)
    assert logbook_link(empty) in links and logbook_link(practice) in links


# --- The menu on small screens --------------------------------------------------------------------


@pytest.mark.django_db
def test_the_signed_in_header_has_a_real_menu_button_that_starts_hidden(
    client: Client, owner: User, practice: Account
) -> None:
    client.force_login(owner)
    html = header(client)
    assert (
        '<button type="button" class="menu-toggle" aria-expanded="false" '
        'aria-controls="primary-menu" hidden>Menu</button>'
    ) in html
    menu = folding_list(html)
    for name in ("FAQ", "Waitlist", "Accounts", "Logbook"):
        assert f">{name}</a></li>" in menu, name
    page = client.get("/").content.decode()
    assert '<script src="/static/pages/menu.js" defer></script>' in page


def test_the_script_toggles_aria_expanded_and_closes_on_escape() -> None:
    script = (STATIC / "menu.js").read_text()
    assert 'getAttribute("aria-controls")' in script
    assert 'setAttribute("aria-expanded"' in script
    assert "button.hidden = false" in script, "the button shows only when the script runs"
    assert '"Escape"' in script and "button.focus()" in script


def test_the_stylesheet_folds_only_narrow_screens_with_44px_targets() -> None:
    css = (STATIC / "site.css").read_text()
    assert ".menu-toggle[hidden] { display: none; }" in css
    assert "min-height: 2.75rem; min-width: 2.75rem;" in css, "44px at a 16px root"
    assert "@media (max-width: 39.99rem)" in css and ".js-menu.is-open .menu-links" in css
    assert "@media (min-width: 40rem) {\n  .menu-toggle { display: none; }" in css


@pytest.mark.django_db
@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_signed_out_there_is_no_button_and_no_script(client: Client, path: str) -> None:
    html = client.get(path).content.decode()
    assert "menu-toggle" not in html and "<script" not in html


# --- The smoke test: the sign-in control stays visible with its exact name ------------------------


@pytest.mark.smoke
@pytest.mark.django_db
@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_sign_in_stays_outside_the_folding_list(client: Client, path: str) -> None:
    html = header(client, path)
    assert SIGN_IN in links_in(html)
    assert "Sign in" not in folding_list(html)


@pytest.mark.smoke
@pytest.mark.django_db
def test_sign_out_stays_outside_the_folding_list(
    client: Client, owner: User, practice: Account
) -> None:
    client.force_login(owner)
    html = header(client)
    assert '<button type="submit">Sign out</button>' in html
    assert "Sign out" not in folding_list(html)
