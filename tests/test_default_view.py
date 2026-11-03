"""The default view saved per person (2026-11-02, decision 155; chapter 10's exercise 1).

Chapter 10 remembered the view only for the sign-in. Now "Make this my default" saves it in
`ViewPreference`, and a method page with no view asked for in the URL or the session opens on it
while a method runs; with no method it still opens on C, where a method starts. An explicit
`?view=` still wins for the rest of the session. One row per person, owner-only POST with CSRF."""

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.test import Client

from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.models import MethodPlan, ViewPreference
from invest_witus_site.methods.views import SESSION_KEY
from tests.test_ch10 import VIEW_HEADINGS, text

D = Decimal


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("owner")


@pytest.fixture
def someone(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("someone")


@pytest.fixture
def account(owner: User) -> Account:
    return Account.objects.create(name="Practice", broker="Paper", kind="paper", owner=owner)


@pytest.fixture
def plan(account: Account) -> MethodPlan:
    return MethodPlan.objects.create(
        account=account,
        method_id="index-dca",
        amount=D("100.00"),
        buy_window_days=7,
        symbols="INDEX",
        started_on=date(2026, 1, 1),
    )


def page(account: Account, query: str = "") -> str:
    return f"/accounts/{account.pk}/method/{query}"


def default_url(account: Account) -> str:
    return f"/accounts/{account.pk}/method/default-view/"


def signed_in(user: User) -> Client:
    """A fresh browser: a new session, as after signing out and in again."""
    client = Client()
    client.force_login(user)
    return client


def opens_on(client: Client, account: Account, query: str = "") -> str:
    """The letter the switch marks as current. While a method runs, that view's own heading is
    on the page too (chapter 10's test of the three views)."""
    html = text(client.get(page(account, query)))
    found = [key for key in "abc" if f'?view={key}" aria-current="page"' in html]
    assert len(found) == 1, found
    if "No method yet" not in html and "Start a method on this account" not in html:
        assert VIEW_HEADINGS[found[0]] in html
    return found[0]


@pytest.mark.django_db
def test_without_a_saved_default_chapter_10s_defaults_hold(
    owner: User, account: Account, plan: MethodPlan
) -> None:
    assert opens_on(signed_in(owner), account) == "a"
    plan.active = False
    plan.save()
    assert opens_on(signed_in(owner), account) == "c"
    assert not ViewPreference.objects.exists()


@pytest.mark.django_db
def test_make_this_my_default_saves_it_for_every_later_sign_in(
    owner: User, account: Account, plan: MethodPlan
) -> None:
    client = signed_in(owner)
    html = text(client.get(page(account, "?view=b")))
    assert '<input type="hidden" name="view" value="b">' in html
    assert "Make B: Method Console my default view" in html
    response = client.post(default_url(account), {"view": "b"})
    assert response.status_code == 302 and response["Location"] == page(account)
    assert ViewPreference.objects.get(user=owner).view == "b"
    assert client.session[SESSION_KEY] == "b"
    after = text(client.get(page(account)))
    assert "B: Method Console is your default view." in after, "the message"
    assert "This is your default view." in after
    assert "my default view</button>" not in after
    # A new sign-in: the session is empty, the saved default decides.
    fresh = signed_in(owner)
    assert opens_on(fresh, account) == "b"
    # An explicit choice still wins, and is remembered for this sign-in only.
    assert opens_on(fresh, account, "?view=c") == "c"
    assert opens_on(fresh, account) == "c"
    assert "Make C: The Lesson Lab my default view" in text(fresh.get(page(account)))
    assert opens_on(signed_in(owner), account) == "b", "the next sign-in is back on the default"
    # Choosing again replaces the row; there is only ever one per person.
    fresh.post(default_url(account), {"view": "a"})
    assert list(ViewPreference.objects.values_list("view", flat=True)) == ["a"]


@pytest.mark.django_db
def test_with_no_method_the_page_still_opens_where_one_starts(
    owner: User, account: Account, plan: MethodPlan
) -> None:
    ViewPreference.save_for(owner, "b")
    plan.active = False
    plan.save()
    assert opens_on(signed_in(owner), account) == "c"


@pytest.mark.django_db
def test_starting_a_method_lands_on_the_saved_default(owner: User, account: Account) -> None:
    ViewPreference.save_for(owner, "b")
    client = signed_in(owner)
    form = {
        "method_id": "index-dca",
        "amount": "100",
        "buy_window_days": "7",
        "symbols": "INDEX",
        "started_on": "2026-01-01",
    }
    client.post(page(account, "start/"), form)
    assert client.session[SESSION_KEY] == "b"
    assert opens_on(client, account) == "b"


@pytest.mark.django_db
def test_the_default_is_per_person_and_a_bad_letter_saves_nothing(
    owner: User, someone: User, account: Account, plan: MethodPlan
) -> None:
    theirs = Account.objects.create(name="Theirs", broker="Paper", kind="paper", owner=someone)
    MethodPlan.objects.create(
        account=theirs,
        method_id="index-dca",
        amount=D("50.00"),
        buy_window_days=7,
        symbols="INDEX",
        started_on=date(2026, 1, 1),
    )
    ViewPreference.save_for(owner, "c")
    assert opens_on(signed_in(someone), theirs) == "a"
    client = signed_in(owner)
    response = client.post(default_url(account), {"view": "z"}, follow=True)
    assert "Choose view A, B or C." in text(response)
    assert ViewPreference.objects.get(user=owner).view == "c"
    with pytest.raises(ValueError):
        ViewPreference.save_for(owner, "z")


@pytest.mark.django_db
def test_the_route_is_the_owners_post_with_csrf(
    owner: User, someone: User, account: Account, plan: MethodPlan
) -> None:
    anonymous = Client().post(default_url(account), {"view": "b"})
    assert anonymous.status_code == 302
    assert anonymous["Location"].startswith("/auth/witus/login/")
    assert signed_in(someone).post(default_url(account), {"view": "b"}).status_code == 404
    assert signed_in(owner).get(default_url(account)).status_code == 405
    strict = Client(enforce_csrf_checks=True)
    strict.force_login(owner)
    assert strict.post(default_url(account), {"view": "b"}).status_code == 403
    assert not ViewPreference.objects.exists()
    html = text(signed_in(owner).get(page(account)))
    form = html.split(f'action="{default_url(account)}"')[1].split("</form>")[0]
    assert 'name="csrfmiddlewaretoken"' in form
