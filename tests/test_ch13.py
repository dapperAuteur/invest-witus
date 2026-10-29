"""Chapter 13 checkpoint: the in-app reporter and its signed copy to WitUS Inbox.

The signature against one computed by hand (openssl, outside Python) and against Inbox's own
verification, ported; the headers and the exact bytes; the body Inbox's schema accepts; the
settings that switch the client off, each with its reason; a 401, a 400, a 500 and a timeout
keeping the row unsent with the reason stored; a retry that sends once and marks the row sent; the
cron step and its stop on a timeout; "Send again" in the admin; the form signed out and signed
in, its honeypot, CSRF and the rate limit; the link on every public page; the waitlist's copy;
and no secret, signature or message in any log line. Every Inbox answer comes from `FakeInbox`
through httpx's `MockTransport`: no request leaves the process, and the secret is made up.
"""

import hashlib
import hmac
import json
import logging
import time
from datetime import timedelta
from io import StringIO
from pathlib import Path

import httpx
import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client
from django.utils import timezone
from pytest_django.fixtures import Settings

from invest_witus_site.accounts.models import WitusIdentity
from invest_witus_site.pages.models import WaitlistEntry
from invest_witus_site.reports import inbox
from invest_witus_site.reports.delivery import Outcome, deliver, send_unsent
from invest_witus_site.reports.inbox import (
    InboxConfig,
    InboxNotConfigured,
    InboxRefused,
    InboxUnavailable,
    Submission,
    load_config,
    send,
    sign,
)
from invest_witus_site.reports.models import InboxStatus, Report, WaitlistMirror
from tests.test_ch04 import PUBLIC_PATHS, element, links_in

URL = "https://inbox.example.test/api/ingest"
SOURCE = "invest-witus"
# Made up, 34 characters: Inbox refuses a secret shorter than 32.
SECRET = "inbox-test-secret-0123456789abcdef"
REPORT = ("/report/", "Report a problem or ask a question")
CRON_SECRET = "test-only-cron-secret-0123456789"
# The reference signature, computed outside Python with:
#   printf '%s.%s' 1761234567 '<BODY>' | openssl dgst -sha256 -hmac "$SECRET" -hex
STAMP = 1761234567
BODY = b'{"form_type":"contact","priority":"normal","payload":{"message":"hello"}}'
BY_HAND = "sha256=193111255314aaaed048522df9132e7b88691d054933a2b7893ef61e039c638e"
MESSAGE = "The method page shows March twice."


class FakeInbox:
    """Inbox's ingest route, as its code reads on October 29, 2026: it checks the headers, the
    source, the five-minute window and the signature over the raw body (`lib/hmac.ts`, ported),
    then the schema, and answers `{"ok":true,"id":...}`. `answer` forces a status instead."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.answer: int | None = None

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.answer is not None:
            return httpx.Response(self.answer, json={"ok": False})
        source = request.headers.get("x-witus-source")
        stamp = request.headers.get("x-witus-timestamp", "")
        signature = request.headers.get("x-witus-signature", "").removeprefix("sha256=")
        raw = request.content
        if source != SOURCE or not inbox_would_verify(stamp, raw, signature):
            return httpx.Response(401, json={"ok": False})
        body = json.loads(raw)
        if not schema_ok(body):
            return httpx.Response(400, json={"ok": False})
        return httpx.Response(200, json={"ok": True, "id": f"inbox-{len(self.requests)}"})

    def bodies(self) -> list[dict[str, object]]:
        return [json.loads(request.content) for request in self.requests]


def inbox_would_verify(stamp: str, raw: bytes, signature: str) -> bool:
    """`verifySignature` from Inbox's `lib/hmac.ts`, in Python: the timestamp within 300 seconds
    of now, then the HMAC of "{timestamp}.{raw body}", compared in constant time."""
    try:
        when = int(stamp)
    except ValueError:
        return False
    if abs(int(time.time()) - when) > 300:
        return False
    expected = hmac.new(SECRET.encode(), f"{stamp}.".encode() + raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def schema_ok(body: object) -> bool:
    """Inbox's `IngestPayload` schema, the parts this app can get wrong."""
    if not isinstance(body, dict):
        return False
    fields: dict[str, object] = body  # pyright: ignore[reportUnknownVariableType]
    form_type = fields.get("form_type")
    name = fields.get("submitter_name", "x")
    return (
        isinstance(form_type, str)
        and 1 <= len(form_type) <= 120
        and isinstance(fields.get("payload"), dict)
        and fields.get("priority", "normal") in ("normal", "high")
        and isinstance(name, str)
        and 1 <= len(name) <= 255
    )


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> FakeInbox:
    settings.INBOX_INGEST_URL = URL
    settings.INBOX_SOURCE_SLUG = SOURCE
    settings.INBOX_INGEST_SECRET = SECRET
    inbox_fake = FakeInbox()
    monkeypatch.setattr(inbox, "transport", httpx.MockTransport(inbox_fake.handle))
    return inbox_fake


def time_out(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("no answer", request=request)


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_superuser("owner", "owner@example.com", "pw")


def write_report(client: Client, **fields: str):  # the test client's response
    data = {"kind": "bug", "message": MESSAGE, "page": "/faq/", "email": "learner@example.com"}
    return client.post("/report/", {**data, **fields})


def a_report(**fields: object) -> Report:
    values: dict[str, object] = {"kind": "question", "message": MESSAGE, "email": "a@example.com"}
    return Report.objects.create(**{**values, **fields})


# --- The signature ------------------------------------------------------------------------------


def test_the_signature_matches_one_computed_by_hand() -> None:
    assert sign(SECRET, STAMP, BODY) == BY_HAND


def test_the_signature_is_what_inbox_verifies_and_nothing_else_is() -> None:
    stamp = int(time.time())
    digest = sign(SECRET, stamp, BODY).removeprefix("sha256=")
    assert inbox_would_verify(str(stamp), BODY, digest)
    assert not inbox_would_verify(str(stamp), BODY + b" ", digest), "one byte more"
    assert not inbox_would_verify(str(stamp - 301), BODY, sign(SECRET, stamp - 301, BODY)[7:])


@pytest.mark.django_db
def test_the_request_carries_the_headers_and_the_signed_bytes(fake: FakeInbox) -> None:
    submission = Submission("contact", {"message": "hello"})
    # The reference timestamp is a year old, so Inbox refuses it: the five-minute window.
    with pytest.raises(InboxRefused):
        send(load_config(), submission, STAMP)
    request = fake.requests[0]
    assert request.method == "POST"
    assert str(request.url) == URL
    assert request.headers["content-type"] == "application/json"
    assert request.headers["x-witus-source"] == SOURCE
    assert request.headers["x-witus-timestamp"] == str(STAMP)
    assert request.content == BODY, "the bytes signed are the bytes sent"
    assert request.headers["x-witus-signature"] == BY_HAND


def test_the_body_leaves_out_an_empty_name_and_email_and_is_plain_ascii() -> None:
    body = Submission("contact", {"message": "café"}, priority="high").body()
    assert json.loads(body) == {
        "form_type": "contact",
        "priority": "high",
        "payload": {"message": "café"},
    }
    assert body.isascii()


# --- Off, with a reason -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "slug", "secret", "reason"),
    [
        ("", "", "", "INBOX_INGEST_URL, INBOX_SOURCE_SLUG, INBOX_INGEST_SECRET not set"),
        (URL, SOURCE, "", "INBOX_INGEST_SECRET not set"),
        ("http://inbox.example.test/api/ingest", SOURCE, SECRET, "must be an https:// URL"),
        (URL, "Invest WitUS", SECRET, "lower-case words joined by hyphens"),
        (URL, SOURCE, "too-short", "shorter than 32 characters"),
    ],
)
def test_the_client_is_off_with_a_reason_and_never_shows_the_secret(
    settings: Settings, url: str, slug: str, secret: str, reason: str
) -> None:
    settings.INBOX_INGEST_URL, settings.INBOX_SOURCE_SLUG = url, slug
    settings.INBOX_INGEST_SECRET = secret
    with pytest.raises(InboxNotConfigured) as refused:
        load_config()
    assert reason in refused.value.message
    assert not secret or secret not in refused.value.message


def test_a_local_inbox_over_http_is_allowed(settings: Settings) -> None:
    settings.INBOX_INGEST_URL = "http://localhost:3000/api/ingest"
    settings.INBOX_SOURCE_SLUG, settings.INBOX_INGEST_SECRET = SOURCE, SECRET
    config = load_config()
    assert config.url.startswith("http://localhost")
    assert SECRET not in repr(config)


@pytest.mark.django_db
def test_with_inbox_off_a_report_is_kept_and_the_form_says_so(client: Client) -> None:
    page = client.get("/report/").content.decode()
    assert "Forwarding to WitUS Inbox is off." in page
    response = write_report(client)
    assert response.status_code == 302
    row = Report.objects.get()
    assert (row.inbox_status, row.sent_at, row.attempts) == (InboxStatus.OFF, None, 0)
    assert "not set" in row.last_error


# --- Failures keep the row ----------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("status", "outcome", "words"),
    [
        (401, Outcome.REFUSED, "not registered there"),
        (400, Outcome.REFUSED, "refused the body"),
        (500, Outcome.UNAVAILABLE, "Inbox answered 500"),
    ],
)
def test_a_refusal_keeps_the_report_unsent_with_the_reason(
    fake: FakeInbox, status: int, outcome: Outcome, words: str
) -> None:
    fake.answer = status
    row = a_report()
    assert deliver(row) == outcome
    assert (row.inbox_status, row.sent_at, row.attempts) == (InboxStatus.FAILED, None, 1)
    assert words in row.last_error


@pytest.mark.django_db
def test_a_timeout_keeps_the_report_unsent(
    fake: FakeInbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(inbox, "transport", httpx.MockTransport(time_out))
    row = a_report()
    assert deliver(row) == Outcome.UNAVAILABLE
    assert (row.inbox_status, row.sent_at) == (InboxStatus.FAILED, None)
    assert row.last_error == "Inbox did not answer in time."


@pytest.mark.django_db
def test_a_200_without_an_id_is_not_a_send(
    fake: FakeInbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_id(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="ok")

    monkeypatch.setattr(inbox, "transport", httpx.MockTransport(no_id))
    with pytest.raises(InboxUnavailable):
        send(load_config(), Submission("contact", {}))
    config = InboxConfig(URL, SOURCE, SECRET)
    fake.answer = 401
    monkeypatch.setattr(inbox, "transport", httpx.MockTransport(fake.handle))
    with pytest.raises(InboxRefused):
        send(config, Submission("contact", {}))


# --- Retry ----------------------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_retry_sends_once_and_marks_the_report_sent(fake: FakeInbox) -> None:
    fake.answer = 500
    row = a_report(kind="bug")
    deliver(row)
    fake.answer = None
    run = send_unsent()
    assert run.as_dict() == {"checked": 1, "sent": 1, "failed": 0, "stopped": ""}
    row.refresh_from_db()
    assert (row.inbox_status, row.inbox_id, row.attempts, row.last_error) == (
        InboxStatus.SENT,
        "inbox-2",
        2,
        "",
    )
    assert row.sent_at is not None
    assert deliver(row) == Outcome.ALREADY_SENT
    assert send_unsent().checked == 0
    assert len(fake.requests) == 2, "sent once after the failure, and never again"
    body = fake.bodies()[1]
    assert (body["form_type"], body["priority"]) == ("invest-witus-bug-report", "high")


@pytest.mark.django_db
def test_a_timeout_stops_the_nightly_run_and_a_refusal_does_not(
    fake: FakeInbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    for _ in range(3):
        a_report()
    fake.answer = 400
    run = send_unsent()
    assert (run.checked, run.failed, run.stopped) == (3, 3, "")
    monkeypatch.setattr(inbox, "transport", httpx.MockTransport(time_out))
    run = send_unsent()
    assert (run.checked, run.failed, run.stopped) == (1, 1, "Inbox did not answer in time.")


@pytest.mark.django_db
def test_the_nightly_cron_sends_what_inbox_has_not_taken(
    client: Client, settings: Settings, fake: FakeInbox, tmp_path: Path
) -> None:
    settings.CRON_SECRET = CRON_SECRET
    settings.PRICES_CSV_DIR = tmp_path
    a_report()
    response = client.get(
        "/api/cron/pull-prices/", headers={"Authorization": f"Bearer {CRON_SECRET}"}
    )
    assert response.json()["inbox"] == {"checked": 1, "sent": 1, "failed": 0, "stopped": ""}
    assert Report.objects.get().inbox_status == InboxStatus.SENT


@pytest.mark.django_db
def test_send_again_in_the_admin_sends_the_selected_rows(
    client: Client, owner: User, fake: FakeInbox
) -> None:
    client.force_login(owner)
    waiting, done = a_report(), a_report()
    deliver(done)
    response = client.post(
        "/admin/reports/report/",
        {"action": "send_selected_again", "_selected_action": [waiting.pk, done.pk]},
        follow=True,
    )
    page = response.content.decode()
    assert "Send again: 1 sent, 1 already sent." in page
    assert len(fake.requests) == 2
    waiting.refresh_from_db()
    assert waiting.inbox_status == InboxStatus.SENT


@pytest.mark.django_db
def test_the_reports_command_lists_open_reports_and_sends_with_send(fake: FakeInbox) -> None:
    a_report(message="Where is\nthe logbook?")
    a_report(triage=Report.Triage.DONE, message="Old")
    out = StringIO()
    call_command("reports", "--send", stdout=out)
    text = out.getvalue()
    assert "Inbox: checked 2, sent 2, failed 0." in text
    assert "Where is the logbook?" in text
    assert "Old" not in text


# --- The form -----------------------------------------------------------------------------------


@pytest.mark.django_db
def test_signed_out_a_report_needs_an_email_and_is_sent(client: Client, fake: FakeInbox) -> None:
    response = write_report(client, email="")
    assert response.status_code == 200
    assert Report.objects.count() == 0
    response = client.post(
        "/report/",
        {"kind": "question", "message": MESSAGE, "page": "/faq/?q=1", "email": "A@Example.com"},
        headers={"User-Agent": "TestBrowser/1.0"},
        follow=True,
    )
    assert response.redirect_chain == [("/report/thanks/", 302)]
    page = response.content.decode()
    assert "Thank you" in page
    assert "within" not in page and "hours" not in page, "no promise of a reply time"
    row = Report.objects.get()
    assert (row.email, row.page, row.user, row.inbox_status) == (
        "a@example.com",
        "/faq/",
        None,
        InboxStatus.SENT,
    )
    body = fake.bodies()[0]
    assert body["form_type"] == "invest-witus-support-question"
    assert body["submitter_email"] == "a@example.com"
    assert "submitter_name" not in body
    payload = body["payload"]
    assert isinstance(payload, dict)
    assert payload["message"] == MESSAGE
    assert payload["user_agent"] == "TestBrowser/1.0"
    assert payload["admin_url"] == f"http://testserver/admin/reports/report/{row.pk}/change/"


@pytest.mark.django_db
def test_signed_in_the_witus_identity_is_the_sender(
    client: Client, owner: User, fake: FakeInbox
) -> None:
    WitusIdentity.objects.create(
        user=owner, sub="w-1", email="me@witus.example", name="Owner", last_login_at=timezone.now()
    )
    client.force_login(owner)
    session = client.session
    session["method_view"] = "b"
    session.save()
    form = client.get("/report/", headers={"Referer": "http://testserver/accounts/1/method/?x=1"})
    html = form.content.decode()
    assert 'name="email"' not in html
    assert 'value="/accounts/1/method/"' in html, "the page filled in from the referrer"
    client.post("/report/", {"kind": "feature", "message": MESSAGE, "page": "/accounts/1/method/"})
    row = Report.objects.get()
    assert (row.user, row.email, row.name, row.view) == (owner, "me@witus.example", "Owner", "B")
    body = fake.bodies()[0]
    assert (body["form_type"], body["submitter_name"]) == ("invest-witus-feature-request", "Owner")


@pytest.mark.django_db
def test_a_referrer_from_another_site_fills_in_nothing(client: Client) -> None:
    html = client.get("/report/", headers={"Referer": "https://elsewhere.example/x"}).content
    assert b"elsewhere" not in html


@pytest.mark.django_db
def test_the_honeypot_saves_nothing_and_says_thank_you(client: Client, fake: FakeInbox) -> None:
    response = write_report(client, website="http://spam.example")
    assert response["Location"] == "/report/thanks/"
    assert Report.objects.count() == 0
    assert fake.requests == []


@pytest.mark.django_db
def test_a_post_without_a_csrf_token_is_refused() -> None:
    client = Client(enforce_csrf_checks=True)
    assert write_report(client).status_code == 403
    assert Report.objects.count() == 0


@pytest.mark.django_db
def test_the_rate_limit_counts_reports_in_the_database(client: Client) -> None:
    for _ in range(5):
        assert write_report(client).status_code == 302
    sixth = write_report(client)
    assert sixth.status_code == 429
    assert "five reports in the last hour" in sixth.content.decode()
    assert Report.objects.count() == 5
    Report.objects.update(created_at=timezone.now() - timedelta(hours=2))
    assert write_report(client).status_code == 302


@pytest.mark.django_db
def test_the_rate_limit_follows_a_signed_in_person_across_addresses(
    client: Client, owner: User
) -> None:
    client.force_login(owner)
    for number in range(5):
        a_report(user=owner, client_key=f"elsewhere-{number}")
    response = client.post("/report/", {"kind": "bug", "message": MESSAGE})
    assert response.status_code == 429
    assert Report.objects.count() == 5


@pytest.mark.django_db
def test_the_address_is_stored_only_as_a_keyed_hash(client: Client) -> None:
    data = {"kind": "bug", "message": MESSAGE, "email": "learner@example.com"}
    client.post("/report/", data, REMOTE_ADDR="203.0.113.9")
    row = Report.objects.get()
    assert len(row.client_key) == 32
    assert "203.0.113" not in row.client_key


@pytest.mark.django_db
@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_every_public_page_links_the_reporter_in_header_and_footer(
    client: Client, path: str
) -> None:
    html = client.get(path).content.decode()
    assert REPORT in links_in(element(html, "header"))
    assert REPORT in links_in(element(html, "footer"))


@pytest.mark.django_db
def test_a_signed_in_page_links_the_reporter_in_the_menu(client: Client, owner: User) -> None:
    client.force_login(owner)
    html = client.get("/").content.decode()
    menu = html.split('id="primary-menu">', 1)[1].split("</ul>", 1)[0]
    assert REPORT in links_in(menu)


# --- The waitlist's copy ------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_waitlist_signup_creates_a_mirror_row_once(client: Client, fake: FakeInbox) -> None:
    signup = {"name": "Pat Learner", "email": "pat@example.com"}
    client.post("/waitlist/", signup)
    client.post("/waitlist/", {**signup, "email": "PAT@example.com"})
    mirror = WaitlistMirror.objects.get()
    assert mirror.entry == WaitlistEntry.objects.get()
    assert mirror.inbox_status == InboxStatus.SENT
    assert len(fake.requests) == 1
    body = fake.bodies()[0]
    assert (body["form_type"], body["priority"], body["submitter_email"]) == (
        "waitlist-signup",
        "normal",
        "pat@example.com",
    )


@pytest.mark.django_db
def test_a_waitlist_signup_with_inbox_down_is_kept_and_retried(
    client: Client, fake: FakeInbox
) -> None:
    fake.answer = 503
    response = client.post("/waitlist/", {"name": "Pat", "email": "pat@example.com"})
    assert response["Location"] == "/waitlist/thanks/"
    assert WaitlistMirror.objects.get().inbox_status == InboxStatus.FAILED
    fake.answer = None
    assert send_unsent().sent == 1
    assert WaitlistMirror.objects.get().sent_at is not None


@pytest.mark.django_db
def test_a_bot_on_the_waitlist_makes_no_copy(client: Client, fake: FakeInbox) -> None:
    client.post("/waitlist/", {"name": "Bot", "email": "bot@example.com", "website": "x"})
    assert WaitlistMirror.objects.count() == 0
    assert fake.requests == []


def test_the_chapter_04_todo_is_gone() -> None:
    from invest_witus_site.pages import views

    source = open(views.__file__, encoding="utf-8").read()
    assert "TODO(chapter 13)" not in source


# --- Logs ---------------------------------------------------------------------------------------


@pytest.mark.django_db
def test_no_secret_signature_or_message_reaches_a_log(
    client: Client, fake: FakeInbox, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    write_report(client)
    fake.answer = 401
    write_report(client, message="Second report text")
    logged = caplog.text
    assert "inbox: sent source=invest-witus form_type=invest-witus-bug-report status=200" in logged
    assert (
        "inbox: failed source=invest-witus form_type=invest-witus-bug-report status=401" in logged
    )
    for secret_thing in (SECRET, MESSAGE, "Second report text", "learner@example.com"):
        assert secret_thing not in logged
    for request in fake.requests:
        assert request.headers["x-witus-signature"].removeprefix("sha256=") not in logged
