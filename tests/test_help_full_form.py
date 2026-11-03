"""The Help bubble's "Open the full form" keeps what was typed (2026-11-03, decision 165).

It was a plain link to `/report/`, so the bubble's message was lost on the way. It is now a second
submit button of the bubble's own form (`name="open_full"`, `formnovalidate`): the POST carries the
kind, the message and the page with the CSRF token to `/report/`, which keeps them in the session
for one GET and redirects there, where the full form shows them. Nothing is saved or sent to
Inbox, nothing goes in a URL, the email and the honeypot are never carried, and no script is
added (the bubble's dialog is a signed-in page's; public pages still carry none)."""

import pytest
from django.contrib.auth.models import User
from django.test import Client

from invest_witus_site.holdings.models import Account
from invest_witus_site.reports.models import Report
from invest_witus_site.reports.views import DRAFT_KEY
from tests.test_ch10 import text

MESSAGE = "The chart's key covers the last bar & I can't read it."


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("owner", "owner@example.com", "pw")


@pytest.fixture
def account(owner: User) -> Account:
    return Account.objects.create(name="Practice", broker="Example", kind="paper", owner=owner)


def dialog_of(html: str) -> str:
    return html[html.index("<dialog") : html.index("</dialog>")]


@pytest.mark.django_db
def test_the_bubble_offers_the_full_form_as_a_submit_button_not_a_link(
    client: Client, owner: User, account: Account
) -> None:
    client.force_login(owner)
    dialog = dialog_of(client.get(f"/accounts/{account.pk}/").content.decode())
    assert (
        '<button type="submit" name="open_full" value="1" formnovalidate class="link-button">'
        "Open the full form</button>"
    ) in dialog
    assert '<a href="/report/">Open the full form</a>' not in dialog


@pytest.mark.django_db
def test_the_full_form_opens_with_what_was_typed_and_nothing_is_sent(
    client: Client, owner: User, account: Account
) -> None:
    client.force_login(owner)
    path = f"/accounts/{account.pk}/"
    response = client.post(
        "/report/",
        {"kind": "bug", "message": MESSAGE, "page": path, "website": "", "open_full": "1"},
    )
    assert response.status_code == 302 and response.headers["Location"] == "/report/"
    assert Report.objects.count() == 0, "opening the full form saves nothing"
    html = text(client.get("/report/"))
    assert f"{MESSAGE}</textarea>" in html
    assert 'name="kind" value="bug"' in html
    assert html.index('value="bug"') < html.index("checked", html.index('value="bug"'))
    assert f'name="page" value="{path}"' in html
    assert (
        "What you typed in the Help bubble is filled in below. Nothing has been sent yet." in html
    )
    assert DRAFT_KEY not in client.session, "the draft is read once"
    again = text(client.get("/report/"))
    assert MESSAGE not in again and "Help bubble" not in again


@pytest.mark.django_db
def test_an_empty_bubble_opens_an_empty_form(client: Client, owner: User) -> None:
    client.force_login(owner)
    client.post("/report/", {"kind": "", "message": "", "page": "", "open_full": "1"})
    html = text(client.get("/report/"))
    assert "Help bubble" not in html and "</textarea>" in html
    assert Report.objects.count() == 0


@pytest.mark.django_db
def test_the_draft_is_cut_to_the_forms_rules(client: Client, owner: User) -> None:
    client.force_login(owner)
    client.post(
        "/report/",
        {
            "kind": "not-a-kind",
            "message": "x" * 6000,
            "page": "/accounts/1/?token=secret#part",
            "open_full": "1",
        },
    )
    draft = client.session[DRAFT_KEY]
    assert draft == {"kind": "", "message": "x" * 5000, "page": "/accounts/1/"}


@pytest.mark.django_db
def test_a_filled_honeypot_carries_nothing(client: Client, owner: User) -> None:
    client.force_login(owner)
    client.post(
        "/report/", {"kind": "bug", "message": MESSAGE, "website": "spam", "open_full": "1"}
    )
    assert DRAFT_KEY not in client.session
    assert MESSAGE not in text(client.get("/report/"))


@pytest.mark.django_db
def test_the_send_button_still_files_the_report(client: Client, owner: User) -> None:
    client.force_login(owner)
    response = client.post("/report/", {"kind": "question", "message": MESSAGE, "page": "/"})
    assert response.headers["Location"] == "/report/thanks/"
    assert Report.objects.get().message == MESSAGE


@pytest.mark.django_db
def test_the_carry_over_needs_the_csrf_token(owner: User) -> None:
    client = Client(enforce_csrf_checks=True)
    client.force_login(owner)
    response = client.post("/report/", {"kind": "bug", "message": MESSAGE, "open_full": "1"})
    assert response.status_code == 403
