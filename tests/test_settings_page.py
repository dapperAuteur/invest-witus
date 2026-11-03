"""The Settings page (2026-11-03, decision 163).

BAM could not find "Make <view> my default view": it lived only on a method page, as a small
outlined button under the A/B/C switch. The default view now also lives on `/settings/`, linked
from the header for every signed-in person, where it can be set or cleared; the inline button stays
and says what the default is now. Owner-only by construction: the page reads and writes the
signed-in person's own row, nothing else."""

import re
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.test import Client

from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.models import MethodPlan, ViewPreference
from invest_witus_site.methods.views import SESSION_KEY
from tests.test_ch10 import text
from tests.test_default_view import opens_on, signed_in

SETTINGS = "/settings/"


def checked(html: str) -> str:
    """The value of the default-view radio the page marks as chosen."""
    found = re.findall(r'<input type="radio" name="default_view" value="(\w+)"[^>]*\schecked', html)
    assert len(found) == 1, found
    return found[0]


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("owner")


@pytest.fixture
def someone(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("someone")


@pytest.fixture
def account(owner: User) -> Account:
    account = Account.objects.create(name="Practice", broker="Paper", kind="paper", owner=owner)
    MethodPlan.objects.create(
        account=account,
        method_id="index-dca",
        amount=Decimal("100.00"),
        buy_window_days=7,
        symbols="INDEX",
        started_on=date(2026, 1, 1),
    )
    return account


@pytest.mark.django_db
def test_signed_out_the_page_asks_for_a_sign_in_and_the_header_has_no_link(
    client: Client,
) -> None:
    response = client.get(SETTINGS)
    assert response.status_code == 302 and "/auth/witus/login/" in response.headers["Location"]
    assert 'href="/settings/"' not in text(client.get("/"))


@pytest.mark.django_db
def test_signed_in_every_page_links_settings_from_the_header(client: Client, owner: User) -> None:
    client.force_login(owner)
    for path in ("/", "/accounts/", "/faq/"):
        html = text(client.get(path))
        menu = html[html.index('id="primary-menu"') : html.index("</ul>", html.index("primary"))]
        assert '<a href="/settings/">Settings</a>' in menu, path


@pytest.mark.django_db
def test_the_page_shows_no_default_until_one_is_chosen(client: Client, owner: User) -> None:
    client.force_login(owner)
    html = text(client.get(SETTINGS))
    assert '<h1 id="settings-heading">Settings</h1>' in html
    assert "<legend>Default view on method pages</legend>" in html
    assert checked(html) == "none"
    for label in ("A: The Plan and the Logbook", "B: Method Console", "C: The Lesson Lab"):
        assert label in html


@pytest.mark.django_db
def test_saving_a_view_makes_it_the_default_in_later_sign_ins(
    owner: User, account: Account
) -> None:
    client = signed_in(owner)
    response = client.post(SETTINGS, {"default_view": "b"}, follow=True)
    assert response.redirect_chain == [(SETTINGS, 302)]
    assert "Saved. Method pages open on B: Method Console." in text(response)
    assert ViewPreference.for_user(owner) == "b" and client.session[SESSION_KEY] == "b"
    assert checked(text(response)) == "b"
    assert opens_on(signed_in(owner), account) == "b", "a new sign-in opens on the saved view"


@pytest.mark.django_db
def test_no_default_clears_the_saved_view(owner: User, account: Account) -> None:
    ViewPreference.save_for(owner, "c")
    client = signed_in(owner)
    response = client.post(SETTINGS, {"default_view": "none"}, follow=True)
    assert "Saved. Method pages open on A while a method runs" in text(response)
    assert ViewPreference.for_user(owner) is None and SESSION_KEY not in client.session
    assert opens_on(signed_in(owner), account) == "a"


@pytest.mark.django_db
def test_a_value_that_is_not_a_view_saves_nothing(client: Client, owner: User) -> None:
    client.force_login(owner)
    response = client.post(SETTINGS, {"default_view": "z"})
    assert response.status_code == 200 and "Select a valid choice" in text(response)
    assert ViewPreference.for_user(owner) is None


@pytest.mark.django_db
def test_the_page_writes_only_the_signed_in_persons_row_and_needs_csrf(
    owner: User, someone: User
) -> None:
    ViewPreference.save_for(owner, "c")
    client = Client(enforce_csrf_checks=True)
    client.force_login(someone)
    assert client.post(SETTINGS, {"default_view": "b"}).status_code == 403
    plain = signed_in(someone)
    plain.post(SETTINGS, {"default_view": "b"})
    assert ViewPreference.for_user(someone) == "b" and ViewPreference.for_user(owner) == "c"


@pytest.mark.django_db
def test_the_method_page_keeps_the_button_and_says_where_settings_are(
    owner: User, account: Account
) -> None:
    client = signed_in(owner)
    html = text(client.get(f"/accounts/{account.pk}/method/?view=b"))
    assert "Make B: Method Console my default view" in html
    assert "No default saved: method pages open on A." in html
    assert 'Also in <a href="/settings/">Settings</a>.' in html
    ViewPreference.save_for(owner, "c")
    html = text(client.get(f"/accounts/{account.pk}/method/?view=b"))
    assert "Your default now: view C." in html
    html = text(client.get(f"/accounts/{account.pk}/method/?view=c"))
    assert 'This is your default view. <a href="/settings/">Change it in Settings</a>.' in html
