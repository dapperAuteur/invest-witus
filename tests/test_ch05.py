"""Chapter 05 checkpoint: the admin as the owner's back office, the waitlist list, accounts and
statement snapshots in exact decimals."""

import pytest
from django.conf import settings
from django.core.management import call_command
from django.test import Client

from invest_witus_site.pages.models import WaitlistEntry

ADMIN_LOGIN = "/admin/login/"


@pytest.mark.django_db
def test_models_and_migrations_agree() -> None:
    """`makemigrations --check` exits 1 when a model changed and no migration says so."""
    try:
        call_command("makemigrations", check=True, dry_run=True, verbosity=0)
    except SystemExit:
        pytest.fail("a model changed without a migration: run manage.py makemigrations")


def test_the_admin_and_what_it_needs_are_installed() -> None:
    for app in ("admin", "auth", "contenttypes", "sessions", "messages"):
        assert f"django.contrib.{app}" in settings.INSTALLED_APPS
    assert len(settings.AUTH_PASSWORD_VALIDATORS) == 4


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/admin/", "/admin/pages/waitlistentry/"])
def test_the_admin_sends_a_stranger_to_the_login_page(client: Client, path: str) -> None:
    """Anonymous visitors get a redirect to the login form, never an admin page."""
    response = client.get(path)
    assert response.status_code == 302
    assert response["Location"] == f"{ADMIN_LOGIN}?next={path}"


@pytest.mark.django_db
def test_the_admin_login_page_is_a_page_not_the_public_sign_in(client: Client) -> None:
    html = client.get(ADMIN_LOGIN).content.decode()
    assert 'name="username"' in html and 'name="password"' in html


@pytest.mark.django_db
def test_the_owner_sees_the_waitlist_in_the_admin(admin_client: Client) -> None:
    """`admin_client` is pytest-django's test client logged in as a throw-away superuser."""
    html = admin_client.get("/admin/").content.decode()
    assert "Waitlist entries" in html
    WaitlistEntry.join("Ada", "ada@example.com")
    html = admin_client.get("/admin/pages/waitlistentry/").content.decode()
    assert "ada@example.com" in html
    assert "Approve the selected entries" in html  # the action menu renders only with rows


@pytest.mark.django_db
def test_the_public_form_still_adds_people_as_waiting(client: Client) -> None:
    """The form from chapter 04 is unchanged; it never sets a status, so the default applies."""
    client.post("/waitlist/", {"name": "Ada", "email": "ada@example.com"})
    assert WaitlistEntry.objects.get().status == WaitlistEntry.Status.WAITING


@pytest.mark.django_db
def test_the_approve_action_marks_only_the_selected_entries(admin_client: Client) -> None:
    ada, _ = WaitlistEntry.join("Ada", "ada@example.com")
    bob, _ = WaitlistEntry.join("Bob", "bob@example.com")
    cy, _ = WaitlistEntry.join("Cy", "cy@example.com")
    response = admin_client.post(
        "/admin/pages/waitlistentry/",
        {"action": "approve", "_selected_action": [str(ada.pk), str(bob.pk)]},
        follow=True,
    )
    assert "2 waitlist entries approved." in response.content.decode()
    approved = {e.email for e in WaitlistEntry.objects.filter(status="approved")}
    assert approved == {"ada@example.com", "bob@example.com"}
    assert WaitlistEntry.objects.get(pk=cy.pk).status == "waiting"
