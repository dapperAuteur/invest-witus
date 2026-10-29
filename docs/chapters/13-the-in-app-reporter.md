# Chapter 13: Report a bug or ask a question: the in-app reporter

**Starts from:** tag `v12`. **Ends at:** tag `v13`.
**Written against:** Python 3.14.10, uv 0.13.6, Django 5.2.18, httpx 0.28.1, and WitUS Inbox's webhook contract
and ingest code as read on October 29, 2026.
**Goal:** every page gets a "Report a problem or ask a question" link, in the header and the footer, signed in
or not. The form takes a kind (a bug, an idea for a feature, or a question), a message and the page you were on,
filled in from the page you came from. The report is saved in the app's own database first, then sent to WitUS
Inbox, the operator's one inbox for every WitUS app, as a signed request. A send that fails never touches the
person who wrote the report: the row keeps the reason, and the nightly job or the admin's **Send again** tries
it later. Chapter 04's waitlist gets the same treatment, so a new signup reaches Inbox too.
**Time:** 4 to 5 hours for the code and tests. The laptop walk-through takes 10 minutes.

The listings in this chapter are not typed in by hand. `scripts/render_chapter.py` pastes the real files from
tag `v13` into the chapter text, so what you read and what the tests run are the same bytes.

## What you will learn

- **HMAC signing with `hmac` and `hashlib`:** a shared secret, a timestamp and the exact bytes of a body, and
  why the bytes you sign must be the bytes you send.
- **Reading a contract from the other side's code:** the receiver's schema, limits and answers, checked in its
  own source rather than in a summary of it.
- **Local first, then send:** a row that is the record, a copy that may fail, and the columns that say which.
- **Background work without a worker:** "later" as a step in a job that already runs every night, plus a button.
- **A lock around a network call:** `select_for_update` in a transaction, so two senders at once send once.
- **A rate limit with no shared memory:** counting rows in the database, keyed by a hash of the address, never
  the address.
- **Tests that never leave the process:** httpx's `MockTransport` with a fake that verifies the signature the way
  the receiver does, and a guard in `conftest.py` that fails any test that tries to reach the real thing.

## Before the code: what the PRD asks, and eight decisions

**What the PRD asks.** Section 7.8, the in-app reporter: a "Report" control that opens a short form with a kind,
a message, and automatically the page path, the method page's view (A, B or C), the app version and the
browser's user agent. "Stored locally first (the system of record), then mirrored to WitUS Inbox in the
background with a signed request. A failed mirror never blocks the user and is retried by the daily job." An
admin list with a status (new, triaged, done) and a management command that prints open reports. Acceptance: the
payload never carries keys, holdings, prices or journal text unless the person typed them; each kind has its own
`form_type`, a bug goes as `priority: "high"`; and "A test signs a body and verifies it with the Inbox contract's
algorithm." Doc 02, section 1, has the contract as the ecosystem report summarized it, and chapter 04 left a
`TODO(chapter 13)` in the waitlist view.

**Decision 1: the contract comes from Inbox's code, not from a summary of it.** Doc 02 was written from a report
about Inbox. This chapter reads Inbox's own files: `docs/webhook-contract.md`, the ingest route
`app/api/ingest/route.ts`, `lib/hmac.ts` and `lib/ingest-sources.ts` (WitUS Inbox, n.d.). Five things in the code
are not in the summary, and each changed the client. `submitter_name` must be at least one character, so an empty
name is left out of the body rather than sent as `""`. Inbox refuses a secret shorter than 32 characters for its
whole source list, so a shorter one here can never work and switches the client off with that reason. The
five-minute window is checked both ways (`|now - ts| > 300`), so a retry must sign again with a new timestamp:
a stored signature is worthless minutes later. A 500 means Inbox's database failed, which is worth retrying,
while a 401 lumps together an unknown source, a wrong secret and a clock more than five minutes off, and Inbox
says which only in its own logs. And a source is registered by adding `{"slug", "hmac_secret"}` to the
`INGEST_SOURCES` environment variable on the Inbox project and redeploying it: Inbox's `.env.example` mentions a
`webhook_source` table, but no code reads it. Decisions log, row 119.

**Decision 2: sign the bytes you send.** `Submission.body()` serializes once, with `json.dumps(...,
ensure_ascii=True, separators=(",", ":"))`, into ASCII bytes, and `send()` signs those bytes and passes the same
object to httpx as `content=`. Never `json=`: httpx would serialize again, and any difference in spacing or key
order breaks the signature. `ensure_ascii` writes every other character as a `\u` escape, so the bytes are the
same whether Inbox reads them as bytes or as UTF-8 text. The signature is `hmac.new(secret, f"{ts}.".encode() +
raw, hashlib.sha256).hexdigest()` behind `sha256=` (Python Software Foundation, n.d.). The timestamp is an
argument, so a test can sign a fixed one and compare it with a value computed by hand outside Python. Row 120.

**Decision 3: the row is the record, and it says where its copy is.** `Report` and `WaitlistMirror` share an
abstract base, `InboxDelivery`, with `inbox_status` (not tried yet, sent, failed, off), `sent_at`, Inbox's id,
`attempts`, `last_tried_at` and `last_error`. A report is saved before anything is sent, so Inbox down,
unregistered or switched off loses nothing. With the three `INBOX_` names unset the report is still saved, its
status is "off" with the reason, the form says forwarding is off, and nothing is sent; a learner's copy works
this way for good, and the owner reads reports in the admin. Row 121.

**Decision 4: send now, retry nightly, and lock while sending.** On Vercel a function stops when its response
is sent, so there is no "after the response" to send in. The view sends inline with a five-second timeout and
redirects whatever happened. "Later" is a step in chapter 08's cron route, after the paper orders: every unsent
row, oldest first, at most 25 a night, the waitlist's copies with the reports. A 4xx is that row's own problem
and the run goes on; a timeout or a 5xx stops the run, because every following row would wait out the same
timeout. **Send again** in the admin and `manage.py reports --send` do the same by hand. `deliver()` reads the
row again with `select_for_update()` inside a transaction, so the cron and a click at the same moment send it
once; on SQLite the lock does nothing and one writer at a time does the same job (Django Software Foundation,
n.d.). Inbox has no idempotency key, so a send that times out after Inbox stored it can arrive twice; the payload
carries `report_id`, so the operator can see a repeat. Row 122.

**Decision 5: three kinds, three form types.** A bug is `invest-witus-bug-report` with `priority: "high"`, which
makes Inbox text the operator; a feature is `invest-witus-feature-request` and a question
`invest-witus-support-question`, both `normal`. The names follow doc 02 and Tour Manager OS's help bubble, so
the WitUS Triage agent's categories (bug report, feature request, support question) line up. PRD 7.8's fourth
kind, "other", is left out: a question covers it, and a form with fewer choices is quicker to fill in. The payload
holds the kind, the message, `report_id`, the page, the view letter, the version, the user agent, whether the
person was signed in, a link to the row's admin page and the time; nothing from an account. A waitlist copy is
`waitlist-signup`, the name Inbox and the Triage agent already use for signups, at `normal`. Row 123.

**Decision 6: the form knows who is asking.** Signed out, the form asks for an email and requires it, so a reply
can reach the person; signed in, there is no email box, and the WitUS identity's email and name (chapter 07) go
with the report. "What page were you on" starts as the path of the `Referer` when it is a page of this site and
not the form itself, with the query string dropped, and the person can change or clear it. On a method page the
session's view letter goes too. A honeypot keeps simple bots out with the same thank-you a person gets, and CSRF
comes with the form. The thank-you page promises no reply time. Row 124.

**Decision 7: the rate limit counts rows.** Five reports an hour from one address and five from one signed-in
person; the sixth gets the form back with a 429 and a sentence. The count is a query on `Report.created_at`,
because Vercel's functions share no memory (decision 117 said the same for the price buttons). The address is
never stored: `client_key` is an HMAC of it under the app's secret key, cut to 32 hex characters. On Vercel the
address is the first entry of `X-Forwarded-For`, which Vercel overwrites with the client's public IP to prevent
spoofing (Vercel, n.d.-a); anywhere else it is the connection's own address, and a header a client sends to your
laptop is not trusted. Row 125.

**Decision 8: the waitlist's copy is its own row.** `WaitlistMirror` is one-to-one with `WaitlistEntry`, made
only when `join` creates the entry, so joining twice makes one copy, and a bot makes none. The `TODO(chapter 13)`
line in `pages/views.py` is gone. Row 126.

## Steps

### 13.1 The tests

Listing 13-1, Filename: `tests/test_ch13.py`:

```python
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
```

Things to notice:

- **The reference signature was computed outside Python.** `BY_HAND` comes from `openssl dgst -sha256 -hmac`,
  the command Inbox's own contract uses in its `curl` example, so the test does not check the code against
  itself.
- **`FakeInbox` is Inbox, ported.** It checks the source, the five-minute window and the HMAC the way
  `lib/hmac.ts` does, with `hmac.compare_digest`, then the parts of the schema this app could get wrong. A
  request signed over different bytes, or a year-old timestamp, gets Inbox's 401.
- **`answer` forces a status.** Setting `fake.answer = 401` or `500` makes the fake answer like Inbox does when
  something fails: the status and `{"ok":false}`, nothing more.
- **The retry test counts requests.** One failure, one retry, then nothing: `send_unsent()` finds no row, and
  `deliver()` on a sent row answers "already sent" without a request.
- **The log test reads every line.** `caplog` at DEBUG, then the secret, the message, the email and each
  signature must be absent; the source, the form type and the status must be present.

The second file is the shared one. Since chapter 05 every test gets the fast password hasher from it; now every
test also gets Inbox switched off and a transport that fails the test if anything tries to leave the machine, so
a `.env` or a shell with the real names set can never send a test's report to the real Inbox:

Listing 13-2, Filename: `tests/conftest.py`:

```python
"""Fixtures every test file shares. pytest loads this file on its own; nothing imports it.

Added in chapter 05, when tests started creating users: Django's default password hasher is slow
on purpose (it is meant to make guessing expensive), which turns every `admin_client` into half a
second of setup. Tests use the fast hasher instead; the real one still guards real logins.
"""

import httpx
import pytest
from pytest_django.fixtures import Settings

from invest_witus_site.reports import inbox


@pytest.fixture(autouse=True)
def fast_password_hashing(settings: Settings) -> None:
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture(autouse=True)
def no_real_inbox(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    """Chapter 13: WitUS Inbox is off in every test, whatever the shell exports, and a request
    that slipped through would fail here instead of leaving the machine. Tests that want Inbox
    on set the three names and their own fake transport (tests/test_ch13.py)."""
    settings.INBOX_INGEST_URL = ""
    settings.INBOX_SOURCE_SLUG = ""
    settings.INBOX_INGEST_SECRET = ""
    monkeypatch.setattr(inbox, "transport", httpx.MockTransport(refuse_real_inbox))


def refuse_real_inbox(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"a test tried to reach {request.url.host}")
```

Run the tests:

Listing 13-3, Terminal:

```sh
uv run pytest tests/test_ch13.py
```

```text
ImportError while loading conftest '.../tests/conftest.py'.
tests/conftest.py:12: in <module>
    from invest_witus_site.reports import inbox
E   ModuleNotFoundError: No module named 'invest_witus_site.reports'
```

Red before a single test runs: the shared file imports the app this chapter writes, so every test file stops
here until it exists. No package is added this chapter: `hmac`, `hashlib` and `json` are the standard library,
and httpx has been a dependency since chapter 07.

### 13.2 The settings, the app and its URLs

Three names join the settings, read from the environment like every other value, plus the commit Vercel
deploys:

Listing 13-4, Filename: `src/invest_witus_site/settings.py`:

```python
"""Django settings for Invest.WitUS.

Anything that differs between your laptop and a server comes from an environment variable, with a
safe default for the laptop. The names are listed in `.env.example`; values never go in git.
Chapter 06 added the server's side: the database from `DATABASE_URL`, a secret key the server
must set, the HTTPS cookie and proxy settings, the folder `collectstatic` fills, and logging a
server can show. Chapter 07 added the four names of Sign in with WitUS; chapter 08 the price
source and the cron secret, at the end. Chapters 09 and 10 add one app each and no names. Chapter
13 adds the three names of WitUS Inbox, at the end.
"""

import contextlib
import os
from pathlib import Path

import django_stubs_ext
from django.core.exceptions import ImproperlyConfigured

from invest_witus_site.database import database_from_url

# django-stubs describes Django's classes as generics (`ModelAdmin[WaitlistEntry]`) so pyright can
# check them, but Django itself does not accept `[...]` on those classes at runtime. This one call
# teaches them to, so the admin code can be written the way the type checker reads it.
django_stubs_ext.monkeypatch()

# The repository root. This file is src/invest_witus_site/settings.py, three levels down.
BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env_list(name: str) -> list[str]:
    """A comma-separated variable as a list, blanks dropped: "a, b," becomes ["a", "b"]."""
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


# Off unless DJANGO_DEBUG=1. Debug pages show settings and source code; never on a server.
DEBUG = os.environ.get("DJANGO_DEBUG") == "1"

# Vercel sets VERCEL=1 on its build machine and inside the function (its system environment
# variables). It is read for one question only: does a proxy that ends HTTPS sit in front?
ON_VERCEL = os.environ.get("VERCEL") == "1"
if DEBUG and ON_VERCEL:
    raise ImproperlyConfigured(
        "DJANGO_DEBUG=1 on Vercel: debug pages would show settings and code to anyone. Unset it."
    )


def secret_key(debug: bool) -> str:
    """DJANGO_SECRET_KEY, which a server must set. With debug off and no key, Django refuses to
    start here, with a message that says what to do, rather than sign sessions with a key anyone
    can read in git."""
    key = os.environ.get("DJANGO_SECRET_KEY", "")
    if key:
        return key
    if not debug:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY is not set and DJANGO_DEBUG is not 1. A server needs a secret key. "
            "Make one with: uv run python -c "
            '"from django.core.management.utils import get_random_secret_key as k; print(k())"'
        )
    # DEV-ONLY FALLBACK, reachable only with DJANGO_DEBUG=1 on a laptop. `check --deploy` warns
    # about the `django-insecure-` prefix, which is the point.
    return "django-insecure-dev-only-set-DJANGO_SECRET_KEY"


SECRET_KEY = secret_key(DEBUG)

# Host names the site answers to. The default answers a laptop and nothing else; production sets
# DJANGO_ALLOWED_HOSTS=invest.witus.online. The host names Vercel gives a deployment (its
# *.vercel.app URLs, and the production domain once one is added) come from Vercel's own
# variables, so a preview deployment answers without anyone listing its URL by hand.
VERCEL_HOSTS = [
    host
    for name in ("VERCEL_URL", "VERCEL_BRANCH_URL", "VERCEL_PROJECT_PRODUCTION_URL")
    if (host := os.environ.get(name))
]
# (dict.fromkeys keeps the order and drops a name listed twice.)
ALLOWED_HOSTS = list(
    dict.fromkeys((env_list("DJANGO_ALLOWED_HOSTS") or ["localhost", "127.0.0.1"]) + VERCEL_HOSTS)
)

# Origins (scheme and host) a form may be posted from. Django compares a POST's Origin header with
# the request's own origin; listing the site's HTTPS origin keeps that check passing even if the
# proxy header below were ever missing. Production sets https://invest.witus.online.
CSRF_TRUSTED_ORIGINS = list(
    dict.fromkeys(
        env_list("DJANGO_CSRF_TRUSTED_ORIGINS") + [f"https://{host}" for host in VERCEL_HOSTS]
    )
)

# Chapter 04 installed only staticfiles and the pages app. The admin (chapter 05) needs the four
# contrib apps it is built on: auth (users and permissions), contenttypes (the table of tables that
# permissions point at), sessions (how a login is remembered) and messages (the "2 entries approved"
# notes after an action). They arrive together because the admin does not start without them.
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "invest_witus_site.pages",
    "invest_witus_site.holdings",
    "invest_witus_site.accounts",
    "invest_witus_site.prices",
    # The watch list (chapter 09): symbols the owner follows, kept per account, pulled nightly.
    "invest_witus_site.watchlist",
    # The method engine (chapter 10): the plan an account runs, its journal, the review, the views.
    "invest_witus_site.methods",
    # Alpaca paper trading (chapter 11): the paper client, the orders, the confirm step, the sync.
    "invest_witus_site.paper",
    # The in-app reporter (chapter 13): reports and waitlist copies, saved, then sent to Inbox.
    "invest_witus_site.reports",
]

# Order matters: a middleware sees the request top to bottom and the response bottom to top.
# Sessions must load before authentication can read the session, and messages after that.
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "invest_witus_site.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Templates live in each app's templates/ folder; nothing outside an app.
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "invest_witus_site.pages.context_processors.site",
                "invest_witus_site.accounts.context_processors.identity",
                # The header's "Paper account" link for the owner of a linked account.
                "invest_witus_site.paper.context_processors.paper_link",
                # The header's "Logbook" link for an owner with a plan or an entry (decision 115).
                "invest_witus_site.methods.context_processors.logbook_link",
            ],
        },
    },
]

# The WSGI application `runserver` loads. It names the bridge file at the repository root, not
# `invest_witus_site.wsgi`, because Vercel turns this value into a file path beside `manage.py`,
# and the bridge is what puts `src/` on the import path there (chapter 06).
WSGI_APPLICATION = "wsgi.application"


# The database. With no DATABASE_URL: SQLite in the folder git ignores, as in chapter 04. On
# Vercel the Neon integration sets DATABASE_URL (the pooled connection, for the app) and
# DATABASE_URL_UNPOOLED (the direct one, for migrations). `database_from_url` reads either shape.
# Vercel's connect dialog can put a prefix on every name the integration writes; the production
# project was connected with the prefix STORAGE (read from its variable list, 2026-10-28), so the
# prefixed names are accepted as well. An unprefixed name wins when both exist.
def first_env(*names: str) -> str | None:
    """The first of `names` that is set and not empty, or None."""
    for name in names:
        if value := os.environ.get(name):
            return value
    return None


DATA_DIR = BASE_DIR / "data" / "private"
POOLED_URL = first_env("DATABASE_URL", "STORAGE_DATABASE_URL")
DATABASE_URL = POOLED_URL or "sqlite:///data/private/invest-witus.sqlite3"
if not POOLED_URL:
    # A server's filesystem may be read-only; then /healthz/ reports the database as missing.
    with contextlib.suppress(OSError):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASES = {"default": database_from_url(DATABASE_URL, BASE_DIR)}
if unpooled := first_env("DATABASE_URL_UNPOOLED", "STORAGE_DATABASE_URL_UNPOOLED"):
    # Neon: schema changes take the direct connection, not the pooler. The owner runs
    # `manage.py migrate --database direct` and `createsuperuser --database direct` against it.
    DATABASES["direct"] = database_from_url(unpooled, BASE_DIR)

# The only password in this app is the owner's admin login (chapter 05). Sign in with WitUS
# (chapter 07) adds no passwords. `createsuperuser` refuses a password these validators reject.
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
# Where `collectstatic` copies every app's static files into one folder (gitignored). Vercel sees
# STATIC_ROOT, runs collectstatic itself during the build, and serves that folder from its CDN at
# STATIC_URL; the function never serves a static file.
STATIC_ROOT = BASE_DIR / "staticfiles"

# HTTPS. Vercel ends TLS at its CDN and calls the function over plain HTTP with the header
# X-Forwarded-Proto: https. Django is told to trust that header only on Vercel, where the proxy
# sets it on every request (Django's warning: never where a client could send it to Django
# directly). Vercel also answers every plain-HTTP request with a 308 to HTTPS before Django sees
# it, and sends Strict-Transport-Security on custom domains, so the redirect below is a second
# line and the HSTS check (security.W004) is silenced on purpose.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if ON_VERCEL else None
SECURE_SSL_REDIRECT = ON_VERCEL
SILENCED_SYSTEM_CHECKS = ["security.W004"]
# Cookies marked Secure travel only over HTTPS. On whenever debug is off, so a server never sends
# the admin's session over plain HTTP. It is also why `runserver` with debug off cannot sign you
# in at http://127.0.0.1:8000/admin/: the browser keeps a Secure cookie off a plain connection.
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# Django's default logging prints to the console only while debug is on, so a server would show
# nothing. This sends warnings and errors (a 500's traceback, a refused host) to stderr, which
# Vercel collects as the function's logs. Nothing here logs a request body or a setting.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"stderr": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["stderr"], "level": "WARNING"},
}

# The FAQ, privacy and terms pages are Markdown files in the repo, so a wording change is a normal
# commit with a diff anyone can read.
SITE_PAGES_DIR = BASE_DIR / "docs" / "site"

# Vercel Web Analytics (chapter 06a): two script tags in the base template, rendered only when
# both hold: the app runs on Vercel, and the owner set VERCEL_ANALYTICS=1 on that environment. So
# production and preview can differ, and `runserver` never emits the tags (debug on Vercel is
# refused above, so a debug server never does either). The script's path belongs to the project:
# once Analytics is enabled, the project's Analytics page shows it, and that value goes in
# VERCEL_ANALYTICS_SCRIPT_PATH. FALLBACK, not a value read from any dashboard: the shared
# `/_vercel/insights/` route the quickstart names, with the file name from its snippet.
VERCEL_ANALYTICS_ENABLED = ON_VERCEL and os.environ.get("VERCEL_ANALYTICS") == "1"
VERCEL_ANALYTICS_SCRIPT_PATH = (
    os.environ.get("VERCEL_ANALYTICS_SCRIPT_PATH") or "/_vercel/insights/script.js"
)
if not VERCEL_ANALYTICS_SCRIPT_PATH.startswith("/"):
    raise ImproperlyConfigured(
        "VERCEL_ANALYTICS_SCRIPT_PATH must be a path on this site, starting with /, such as "
        "/<unique-path>/script.js from the Analytics page of the Vercel project."
    )

# Sign in with WitUS (chapter 07): OpenID Connect against the ecosystem's identity provider. The
# client is ON only when the secret is set; without it the sign-in route shows chapter 04's stub
# page and the site deploys as before. The issuer is what the provider asserts in its discovery
# document; the default is the ecosystem's accounts host as read on October 28, 2026, copied from
# that document, and the client refuses a document whose issuer differs. The client id follows the
# registry's `witus-<slug>` form. The secret is minted in the witus repo (task 07) and never
# written anywhere but the two Vercel projects' Environment Variables pages.
WITUS_OIDC_ISSUER = (os.environ.get("WITUS_OIDC_ISSUER") or "https://accounts.witus.online").rstrip(
    "/"
)
WITUS_OIDC_CLIENT_ID = os.environ.get("WITUS_OIDC_CLIENT_ID") or "witus-invest"
WITUS_OIDC_CLIENT_SECRET = os.environ.get("WITUS_OIDC_CLIENT_SECRET", "")
WITUS_OIDC_SCOPES = os.environ.get("WITUS_OIDC_SCOPES") or "openid email profile"
if not WITUS_OIDC_ISSUER.startswith("https://"):
    raise ImproperlyConfigured(
        "WITUS_OIDC_ISSUER must be the provider's https:// issuer, as its discovery document "
        "states it, such as https://accounts.witus.online"
    )
if "openid" not in WITUS_OIDC_SCOPES.split():
    raise ImproperlyConfigured(
        "WITUS_OIDC_SCOPES must include openid, such as: openid email profile"
    )

# Where `login_required` sends a visitor who is not signed in: the WitUS sign-in route, by name.
LOGIN_URL = "sign-in"

# Prices (chapter 08). The nightly pull writes one close per symbol per day into the app's own
# table. With TIINGO_API_KEY set, the closes come from Tiingo's end-of-day endpoint with the
# owner's own key; the free plan's license is "Internal Use Only" (its pricing page, read October
# 28, 2026), and the values are shown to the signed-in owner and to no one else. Without a key the
# pull reads `<SYMBOL>.csv` files from PRICES_CSV_DIR, chapter 02's format, which is what a laptop
# and a learner's copy use.
TIINGO_API_KEY = os.environ.get("TIINGO_API_KEY", "")
PRICES_CSV_DIR = Path(os.environ.get("PRICES_CSV_DIR") or DATA_DIR / "prices")
# What Vercel sends as `Authorization: Bearer <value>` when it calls the cron route (its docs,
# read October 28, 2026; at least 16 random characters). Empty means the route answers 503 and
# runs nothing: a deploy that forgot the variable fails closed.
CRON_SECRET = os.environ.get("CRON_SECRET", "")

# Alpaca paper trading (chapter 11). The owner's paper keys, from the paper dashboard's API Keys
# module; empty means every Alpaca feature says "not set" and nothing is called. The client's host
# is fixed in `paper/alpaca.py` to paper-api.alpaca.markets, never read from here. Live trading is
# not built: it needs the checklist in a later chapter and separate keys under other names.
ALPACA_PAPER_KEY_ID = os.environ.get("ALPACA_PAPER_KEY_ID", "")
ALPACA_PAPER_SECRET_KEY = os.environ.get("ALPACA_PAPER_SECRET_KEY", "")
# Alpaca's own tools read the host from APCA_API_BASE_URL (its paper trading page, read October
# 29, 2026). This app does not, but a value pointing anywhere except the paper host means someone
# expects live trading here, so the settings refuse to start rather than run beside that belief.
_alpaca_base_url = os.environ.get("APCA_API_BASE_URL", "")
if _alpaca_base_url and _alpaca_base_url.rstrip("/") != "https://paper-api.alpaca.markets":
    raise ImproperlyConfigured(
        "APCA_API_BASE_URL points somewhere other than https://paper-api.alpaca.markets. "
        "This app trades on paper only; unset it or set it to the paper host."
    )

# WitUS Inbox (chapter 13): where in-app reports and new waitlist signups are copied for the
# operator, with a signed request. All three must be set, or nothing is sent and every row waits
# (the report form says forwarding is off). The URL is Inbox's ingest endpoint, the slug is this
# app's source as registered in Inbox's INGEST_SOURCES, and the secret is the same string Inbox
# holds for that slug (at least 32 characters; Inbox refuses shorter ones). None has a default:
# they come from the Vercel project's Environment Variables page, never from this file.
INBOX_INGEST_URL = os.environ.get("INBOX_INGEST_URL", "")
INBOX_SOURCE_SLUG = os.environ.get("INBOX_SOURCE_SLUG", "")
INBOX_INGEST_SECRET = os.environ.get("INBOX_INGEST_SECRET", "")
# The deployed commit, which Vercel sets on every deployment (its system environment variables
# page, read October 29, 2026); empty on a laptop. A report carries it beside the version.
GIT_COMMIT_SHA = os.environ.get("VERCEL_GIT_COMMIT_SHA", "")
```

The new lines are the last block and one entry in `INSTALLED_APPS`. None of the three has a default: an Inbox URL
or slug written into the code would be a guessed value for another app's system. `VERCEL_GIT_COMMIT_SHA` is one
of Vercel's system variables, "The git SHA of the commit the deployment was triggered by" (Vercel, n.d.-b); on a
laptop it is empty.

Make the folder `src/invest_witus_site/reports/` with an empty `__init__.py`, an empty `migrations/__init__.py`,
`management/__init__.py` and `management/commands/__init__.py`, then the app's config:

Listing 13-5, Filename: `src/invest_witus_site/reports/apps.py`:

```python
from django.apps import AppConfig


class ReportsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "invest_witus_site.reports"
    verbose_name = "Reports and WitUS Inbox"
```

Listing 13-6, Filename: `src/invest_witus_site/urls.py`:

```python
"""Where every URL of the site starts. Each app lists its own paths; this file includes them."""

from django.contrib import admin
from django.urls import include, path

from invest_witus_site import health

urlpatterns = [
    # The owner's back office. Every page under it requires a staff login (chapter 05).
    path("admin/", admin.site.urls),
    # Up, version, database: what a monitor asks after a deploy (chapter 06).
    path("healthz/", health.healthz, name="healthz"),
    # Sign in with WitUS: login, callback and logout (chapter 07).
    path("auth/witus/", include("invest_witus_site.accounts.urls")),
    # The signed-in owner's accounts, valued at the latest stored closes (chapter 08).
    path("accounts/", include("invest_witus_site.holdings.urls")),
    # The watch list's add and remove actions on an account page (chapter 09). The `pk` captured
    # here is passed on to the included views.
    path("accounts/<int:pk>/watch/", include("invest_witus_site.watchlist.urls")),
    # The method an account runs, its journal and the review, in three views (chapter 10); the
    # plan's change form and each month's review (chapter 12).
    path("accounts/<int:pk>/method/", include("invest_witus_site.methods.urls")),
    # The account's logbook: every journal line, filtered, edited and exported (chapter 12).
    path("accounts/<int:pk>/logbook/", include("invest_witus_site.methods.logbook_urls")),
    # The account linked to Alpaca paper: its positions, cash and orders, the Confirm step and
    # the order check (chapter 11). Owner, superuser and a linked account only.
    path("accounts/<int:pk>/paper/", include("invest_witus_site.paper.urls")),
    # Report a problem or ask a question, signed in or out; saved here, sent to WitUS Inbox
    # (chapter 13).
    path("report/", include("invest_witus_site.reports.urls")),
    # The nightly price pull, called by Vercel's cron with the bearer secret (chapter 08).
    path("api/cron/", include("invest_witus_site.prices.urls")),
    path("", include("invest_witus_site.pages.urls")),
]
```

Listing 13-7, Filename: `src/invest_witus_site/reports/urls.py`:

```python
"""The report form and its thank-you page. `invest_witus_site/urls.py` mounts this at `report/`."""

from django.urls import path

from invest_witus_site.reports import views

urlpatterns = [
    path("", views.report, name="report"),
    path("thanks/", views.thanks, name="report-thanks"),
]
```

### 13.3 The client

Listing 13-8, Filename: `src/invest_witus_site/reports/inbox.py`:

```python
"""WitUS Inbox's signed webhook, sent with httpx: one function signs a body, one sends it.

Read from Inbox's own code and contract (`witus-inbox/docs/webhook-contract.md`,
`app/api/ingest/route.ts`, `lib/hmac.ts` and `lib/ingest-sources.ts`) on October 29, 2026:

- `POST` the JSON body to the ingest URL with `Content-Type: application/json`,
  `X-Witus-Source` (this app's slug), `X-Witus-Timestamp` (unix seconds) and `X-Witus-Signature`,
  which is `sha256=` and the hex HMAC-SHA256 of `"{timestamp}.{raw body}"` under the shared secret.
  Inbox reads the raw body as text and hashes it before it parses anything, so the bytes signed
  here are the bytes sent, never a second `json.dumps`.
- The body: `form_type` (1 to 120 characters), `submitter_email` (a valid address, at most 255,
  optional), `submitter_name` (1 to 255, optional: an empty string is refused, so an empty name is
  left out), `priority` (`normal` or `high`; high sends the operator a text) and `payload` (an
  object).
- A timestamp more than 300 seconds from Inbox's clock is refused, so a retry signs again with a
  new timestamp; a stored signature would be worthless a few minutes later.
- Inbox refuses a secret shorter than 32 characters for the whole source list, so a shorter one
  here can never match and the client treats it as not configured.
- Answers: 200 `{"ok":true,"id":"<uuid>"}`; 401 for a missing header, an unknown source, a bad
  signature or a stale timestamp; 400 for a body that is not JSON or not the schema; 500 when
  Inbox's database fails. Every failure's body is `{"ok":false}`: Inbox never says which check
  failed, on purpose, so the messages below name the possibilities.

Nothing here logs more than the source, the form type and the HTTP status: never the secret, the
signature, the signed text or the body (the contract's third rule).
"""

import hashlib
import hmac
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Literal, cast
from urllib.parse import urlsplit

import httpx
from django.conf import settings

log = logging.getLogger(__name__)

# The seam the tests use, as in chapters 07, 08 and 11: a `MockTransport` here and nothing leaves
# the process. It is never set outside a test.
transport: httpx.BaseTransport | None = None

# Short on purpose: a report is saved before it is sent, and the person who wrote it is waiting
# for the thank-you page. A send that takes longer is retried by the nightly job.
TIMEOUT_SECONDS = 5.0
MIN_SECRET_LENGTH = 32
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1"})

Priority = Literal["normal", "high"]


class InboxError(Exception):
    """Inbox or the network said no. `message` is safe for the admin and a log: our words, a
    status code, never the secret or the body."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


class InboxNotConfigured(InboxError):
    """The three settings are not all set, or one cannot be right. Nothing was sent."""


class InboxRefused(InboxError):
    """A 4xx: Inbox read the request and refused it. Sending the same thing again will fail the
    same way until something changes (the registration, the secret, the code)."""


class InboxUnavailable(InboxError):
    """No usable answer: a timeout, a dropped connection, a 5xx, or a 2xx without an id. Worth
    trying again later."""


@dataclass(frozen=True, slots=True)
class InboxConfig:
    url: str
    source: str
    # `repr=False`: a config printed in a traceback or a debugger shows no secret.
    secret: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class Submission:
    """One thing for the operator's inbox. `body()` is the exact bytes that are signed and sent."""

    form_type: str
    payload: dict[str, object]
    submitter_email: str = ""
    submitter_name: str = ""
    priority: Priority = "normal"

    def body(self) -> bytes:
        document: dict[str, object] = {"form_type": self.form_type}
        if self.submitter_email:
            document["submitter_email"] = self.submitter_email
        if self.submitter_name:
            document["submitter_name"] = self.submitter_name[:255]
        document["priority"] = self.priority
        document["payload"] = self.payload
        # `ensure_ascii` writes any other character as a \u escape, so the body is plain ASCII:
        # the same bytes whether Inbox reads them as bytes or as UTF-8 text.
        return json.dumps(document, ensure_ascii=True, separators=(",", ":")).encode("ascii")


def load_config() -> InboxConfig:
    """The three settings, checked, or `InboxNotConfigured` with a sentence naming the problem.
    The sentence names variables, never their values."""
    url = str(settings.INBOX_INGEST_URL)
    source = str(settings.INBOX_SOURCE_SLUG)
    secret = str(settings.INBOX_INGEST_SECRET)
    names = {"INBOX_INGEST_URL": url, "INBOX_SOURCE_SLUG": source, "INBOX_INGEST_SECRET": secret}
    missing = [name for name, value in names.items() if not value]
    if missing:
        raise InboxNotConfigured(f"WitUS Inbox is off: {', '.join(missing)} not set.")
    parts = urlsplit(url)
    local = parts.scheme == "http" and parts.hostname in LOCAL_HOSTS
    if not (parts.scheme == "https" and parts.hostname) and not local:
        raise InboxNotConfigured(
            "WitUS Inbox is off: INBOX_INGEST_URL must be an https:// URL "
            "(http:// only for localhost)."
        )
    if not SLUG.fullmatch(source):
        raise InboxNotConfigured(
            "WitUS Inbox is off: INBOX_SOURCE_SLUG must be lower-case words joined by hyphens."
        )
    if len(secret) < MIN_SECRET_LENGTH:
        raise InboxNotConfigured(
            f"WitUS Inbox is off: INBOX_INGEST_SECRET is shorter than {MIN_SECRET_LENGTH} "
            "characters, which Inbox refuses."
        )
    return InboxConfig(url=url, source=source, secret=secret)


def configured() -> bool:
    try:
        load_config()
    except InboxNotConfigured:
        return False
    return True


def sign(secret: str, timestamp: int, raw: bytes) -> str:
    """The header value: `sha256=` and the hex HMAC-SHA256 of `"{timestamp}.{raw}"`. The dot is
    literal, and `raw` is used as bytes, so nothing is decoded or re-encoded on the way."""
    message = f"{timestamp}.".encode("ascii") + raw
    digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def send(config: InboxConfig, submission: Submission, timestamp: int | None = None) -> str:
    """Sign and post one submission; return the id Inbox gave it. Every failure is one of the
    exceptions above, never an httpx error that would become a 500."""
    raw = submission.body()
    stamp = int(time.time()) if timestamp is None else timestamp
    headers = {
        "Content-Type": "application/json",
        "X-Witus-Source": config.source,
        "X-Witus-Timestamp": str(stamp),
        "X-Witus-Signature": sign(config.secret, stamp, raw),
    }
    try:
        with httpx.Client(transport=transport, timeout=TIMEOUT_SECONDS) as http:
            response = http.post(config.url, content=raw, headers=headers)
    except httpx.TimeoutException:
        raise unavailable(config, submission, None, "Inbox did not answer in time.") from None
    except httpx.HTTPError as error:
        raise unavailable(
            config, submission, None, f"Could not reach Inbox ({type(error).__name__})."
        ) from None
    status = response.status_code
    if status == 401:
        raise refused(
            config,
            submission,
            status,
            "Inbox answered 401: the source slug is not registered there, the secret differs "
            "from Inbox's, or this server's clock is more than 5 minutes off. Inbox does not "
            "say which.",
        )
    if 400 <= status < 500:
        raise refused(config, submission, status, f"Inbox answered {status}: it refused the body.")
    if status >= 300:
        raise unavailable(config, submission, status, f"Inbox answered {status}.")
    inbox_id = id_from(response)
    if inbox_id is None:
        raise unavailable(config, submission, status, f"Inbox answered {status} without an id.")
    log.info(
        "inbox: sent source=%s form_type=%s status=%s", config.source, submission.form_type, status
    )
    return inbox_id


def id_from(response: httpx.Response) -> str | None:
    try:
        body: object = json.loads(response.text)
    except json.JSONDecodeError:
        return None
    if not isinstance(body, dict):
        return None
    document = cast(dict[str, object], body)
    found = document.get("id")
    if document.get("ok") is True and isinstance(found, str) and found:
        return found[:64]
    return None


def refused(config: InboxConfig, submission: Submission, status: int, message: str) -> InboxRefused:
    failed(config, submission, status)
    return InboxRefused(message, status)


def unavailable(
    config: InboxConfig, submission: Submission, status: int | None, message: str
) -> InboxUnavailable:
    failed(config, submission, status)
    return InboxUnavailable(message, status)


def failed(config: InboxConfig, submission: Submission, status: int | None) -> None:
    """The one log line a failure writes: the source, the form type and the status."""
    log.warning(
        "inbox: failed source=%s form_type=%s status=%s",
        config.source,
        submission.form_type,
        status if status is not None else "none",
    )
```

Things to notice:

- **`load_config()` names variables, never values.** Each reason ("INBOX_INGEST_SECRET not set", "shorter than
  32 characters") is safe to show the owner in the admin and in the cron's JSON.
- **`InboxConfig.secret` has `field(repr=False)`.** A config in a traceback prints its URL and slug and no
  secret, which chapter 11 did by hand with `__repr__`.
- **`sign()` takes bytes and returns the header value.** The dot and the timestamp are encoded and joined to the
  raw bytes; nothing is decoded on the way.
- **`send()` passes `content=raw`.** Not `json=`, which would serialize a second time.
- **Three exceptions, one log line each.** `InboxRefused` for a 4xx (the same request will fail the same way),
  `InboxUnavailable` for a timeout, a dropped connection, a 5xx or a 2xx without an id (worth trying later),
  `InboxNotConfigured` before anything is sent. `failed()` logs the source, the form type and the status, and
  nothing else.
- **`transport` is the seam,** as in chapters 07, 08 and 11: `None` in production, a `MockTransport` in tests
  (Encode, n.d.).

### 13.4 The rows

Listing 13-9, Filename: `src/invest_witus_site/reports/models.py`:

```python
"""What the app sends to WitUS Inbox, kept here first: in-app reports and the waitlist's copies.

Each row is written before anything is sent, so the app's own database is the record and Inbox
is a copy. A row remembers whether it reached Inbox (`sent_at`, `inbox_id`), how many times it
was tried, and the last refusal in words. A row Inbox has not taken stays unsent and is tried
again by the nightly job or by "Send again" in the admin, so a report is never lost because
Inbox was down, unregistered or switched off.
"""

from datetime import datetime

from django.contrib.auth.models import User
from django.db import models

from invest_witus_site.pages.models import WaitlistEntry
from invest_witus_site.reports.inbox import Priority, Submission

ERROR_LIMIT = 240
MESSAGE_LIMIT = 5000
PAGE_LIMIT = 300
# The form types this app writes, after doc 02's table and Tour Manager OS's names, so the WitUS
# Triage agent's categories (bug_report, feature_request, support_question) line up. A bug goes
# out as `high`, which makes Inbox text the operator (PRD 7.8). The waitlist keeps the name the
# Triage agent and Inbox itself already use for signups.
FORM_TYPES: dict[str, tuple[str, Priority]] = {
    "bug": ("invest-witus-bug-report", "high"),
    "feature": ("invest-witus-feature-request", "normal"),
    "question": ("invest-witus-support-question", "normal"),
}
WAITLIST_FORM_TYPE = "waitlist-signup"


class InboxStatus(models.TextChoices):
    PENDING = "pending", "Not tried yet"
    SENT = "sent", "Sent"
    FAILED = "failed", "Failed, will retry"
    OFF = "off", "Off, will retry"


class InboxDelivery(models.Model):
    """The columns every row bound for Inbox carries. Abstract: no table of its own; each model
    below gets these columns in its table."""

    inbox_status: models.CharField[str, str] = models.CharField(
        max_length=8, choices=InboxStatus.choices, default=InboxStatus.PENDING
    )
    sent_at: models.DateTimeField[datetime | None, datetime | None] = models.DateTimeField(
        null=True, blank=True
    )
    inbox_id: models.CharField[str, str] = models.CharField(
        max_length=64, blank=True, default="", help_text="Inbox's id for the submission."
    )
    attempts: models.PositiveSmallIntegerField[int, int] = models.PositiveSmallIntegerField(
        default=0
    )
    last_tried_at: models.DateTimeField[datetime | None, datetime | None] = models.DateTimeField(
        null=True, blank=True
    )
    # The last failure in our words, or why Inbox is off. Never the secret or the body.
    last_error: models.CharField[str, str] = models.CharField(
        max_length=ERROR_LIMIT, blank=True, default=""
    )
    created_at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True

    def submission(self) -> Submission:
        raise NotImplementedError


class Report(InboxDelivery):
    """One bug, feature request or question, written in the app's report form."""

    class Kind(models.TextChoices):
        BUG = "bug", "Something is broken (a bug)"
        FEATURE = "feature", "An idea for the app (a feature)"
        QUESTION = "question", "A question"

    class Triage(models.TextChoices):
        """The operator's own status, set in the admin (PRD 7.8). Inbox keeps its own."""

        NEW = "new", "New"
        TRIAGED = "triaged", "Triaged"
        DONE = "done", "Done"

    kind: models.CharField[str, str] = models.CharField(max_length=10, choices=Kind.choices)
    message: models.TextField[str, str] = models.TextField(max_length=MESSAGE_LIMIT)
    page: models.CharField[str, str] = models.CharField(
        max_length=PAGE_LIMIT, blank=True, default="", help_text="A path on this site, or empty."
    )
    view: models.CharField[str, str] = models.CharField(
        max_length=1, blank=True, default="", help_text="The method page's view, A, B or C."
    )
    # Signed in: the person, and the email from their WitUS identity. Signed out: the email
    # they typed, and no user.
    user: models.ForeignKey[User | None, User | None] = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    email: models.EmailField[str, str] = models.EmailField(max_length=254, blank=True, default="")
    name: models.CharField[str, str] = models.CharField(max_length=150, blank=True, default="")
    user_agent: models.CharField[str, str] = models.CharField(
        max_length=PAGE_LIMIT, blank=True, default=""
    )
    app_version: models.CharField[str, str] = models.CharField(
        max_length=40, blank=True, default=""
    )
    # Scheme and host the report was written on, so Inbox can link back to this row's admin page.
    origin: models.CharField[str, str] = models.CharField(max_length=200, blank=True, default="")
    # A keyed hash of the sender's IP address, for the rate limit only. The address itself is
    # never stored.
    client_key: models.CharField[str, str] = models.CharField(
        max_length=64, blank=True, default="", db_index=True
    )
    triage: models.CharField[str, str] = models.CharField(
        max_length=8, choices=Triage.choices, default=Triage.NEW
    )

    class Meta(InboxDelivery.Meta):
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{Report.Kind(self.kind).label} #{self.pk}"

    def admin_path(self) -> str:
        return f"/admin/reports/report/{self.pk}/change/"

    def submission(self) -> Submission:
        form_type, priority = FORM_TYPES[self.kind]
        payload: dict[str, object] = {
            "kind": self.kind,
            "message": self.message,
            "report_id": self.pk,
            "page": self.page,
            "view": self.view,
            "app_version": self.app_version,
            "user_agent": self.user_agent,
            "signed_in": self.user is not None,
            "admin_url": f"{self.origin}{self.admin_path()}" if self.origin else "",
            "created_at": self.created_at.isoformat(),
        }
        return Submission(
            form_type=form_type,
            payload=payload,
            submitter_email=self.email,
            submitter_name=self.name,
            priority=priority,
        )


class WaitlistMirror(InboxDelivery):
    """The copy of one new waitlist signup that goes to Inbox. One per entry: joining again with
    the same address makes no second copy, as it makes no second entry."""

    entry: models.OneToOneField[WaitlistEntry, WaitlistEntry] = models.OneToOneField(
        WaitlistEntry, on_delete=models.CASCADE, related_name="inbox_mirror"
    )

    class Meta(InboxDelivery.Meta):
        ordering = ["-created_at"]
        verbose_name = "waitlist copy to Inbox"
        verbose_name_plural = "waitlist copies to Inbox"

    def __str__(self) -> str:
        return f"Waitlist {self.entry.email}"

    def submission(self) -> Submission:
        entry = self.entry
        return Submission(
            form_type=WAITLIST_FORM_TYPE,
            payload={
                "email": entry.email,
                "name": entry.name,
                "submitted_at": entry.created_at.isoformat(),
                "waitlist_entry_id": entry.pk,
            },
            submitter_email=entry.email,
            submitter_name=entry.name,
        )
```

`InboxDelivery` is abstract, so it has no table: each model below gets its columns. Each child's `Meta` inherits
`InboxDelivery.Meta`, which Django turns back into a concrete table and pyright accepts as an override.
`submission()` is the one place a row becomes what Inbox receives, so the view, the cron and the admin all send
the same thing. `FORM_TYPES` sits at module level with string keys, so pyright reads the priority as the literal
`"normal"` or `"high"` the client expects.

Make the migration and format it:

Listing 13-10, Terminal:

```sh
uv run --env-file .env python manage.py makemigrations reports
uv run ruff format .
```

Listing 13-11, Filename: `src/invest_witus_site/reports/migrations/0001_initial.py`:

```python
# Generated by Django 5.2.18 on 2026-10-29 18:26

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("pages", "0002_waitlistentry_status"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Report",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "inbox_status",
                    models.CharField(
                        choices=[
                            ("pending", "Not tried yet"),
                            ("sent", "Sent"),
                            ("failed", "Failed, will retry"),
                            ("off", "Off, will retry"),
                        ],
                        default="pending",
                        max_length=8,
                    ),
                ),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                (
                    "inbox_id",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Inbox's id for the submission.",
                        max_length=64,
                    ),
                ),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("last_tried_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.CharField(blank=True, default="", max_length=240)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("bug", "Something is broken (a bug)"),
                            ("feature", "An idea for the app (a feature)"),
                            ("question", "A question"),
                        ],
                        max_length=10,
                    ),
                ),
                ("message", models.TextField(max_length=5000)),
                (
                    "page",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="A path on this site, or empty.",
                        max_length=300,
                    ),
                ),
                (
                    "view",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="The method page's view, A, B or C.",
                        max_length=1,
                    ),
                ),
                ("email", models.EmailField(blank=True, default="", max_length=254)),
                ("name", models.CharField(blank=True, default="", max_length=150)),
                ("user_agent", models.CharField(blank=True, default="", max_length=300)),
                ("app_version", models.CharField(blank=True, default="", max_length=40)),
                ("origin", models.CharField(blank=True, default="", max_length=200)),
                (
                    "client_key",
                    models.CharField(blank=True, db_index=True, default="", max_length=64),
                ),
                (
                    "triage",
                    models.CharField(
                        choices=[("new", "New"), ("triaged", "Triaged"), ("done", "Done")],
                        default="new",
                        max_length=8,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="WaitlistMirror",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "inbox_status",
                    models.CharField(
                        choices=[
                            ("pending", "Not tried yet"),
                            ("sent", "Sent"),
                            ("failed", "Failed, will retry"),
                            ("off", "Off, will retry"),
                        ],
                        default="pending",
                        max_length=8,
                    ),
                ),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                (
                    "inbox_id",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Inbox's id for the submission.",
                        max_length=64,
                    ),
                ),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("last_tried_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.CharField(blank=True, default="", max_length=240)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "entry",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="inbox_mirror",
                        to="pages.waitlistentry",
                    ),
                ),
            ],
            options={
                "verbose_name": "waitlist copy to Inbox",
                "verbose_name_plural": "waitlist copies to Inbox",
                "ordering": ["-created_at"],
                "abstract": False,
            },
        ),
    ]
```

Two new tables and no column on an old one, so the release before this one keeps working while the migrate
workflow runs.

### 13.5 Sending now, and sending later

Listing 13-12, Filename: `src/invest_witus_site/reports/delivery.py`:

```python
"""Sending the rows in `models.py` to WitUS Inbox: one row now, or every unsent row later.

The order is always the same: the row is already saved, then it is sent, then the answer is
written onto the row. A failure never reaches the person who wrote the report; it becomes the
row's `last_error`, and the row waits for the nightly job or the admin's "Send again".

There is no worker and no queue. Vercel runs the site as functions that stop when the response
is sent, so "later" is the nightly cron route (chapter 08's), which already runs once a day, and
the admin's button. A row is locked while it is sent, so the cron and a click on "Send again" at
the same moment send it once.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from django.db import transaction
from django.utils import timezone

from invest_witus_site.pages.models import WaitlistEntry
from invest_witus_site.reports.inbox import (
    InboxError,
    InboxNotConfigured,
    InboxRefused,
    load_config,
    send,
)
from invest_witus_site.reports.models import (
    ERROR_LIMIT,
    InboxDelivery,
    InboxStatus,
    Report,
    WaitlistMirror,
)

# At most this many rows per nightly run, so the cron stays well inside Vercel's time limit
# (each send may take up to the client's 5-second timeout). The rest go the next night.
BATCH = 25


class Outcome(StrEnum):
    SENT = "sent"
    ALREADY_SENT = "already sent"
    REFUSED = "refused"
    UNAVAILABLE = "unavailable"
    OFF = "off"


def deliver(row: InboxDelivery, now: datetime | None = None) -> Outcome:
    """Send one saved row and record the answer on it. Returns what happened; raises nothing."""
    moment = now or timezone.now()
    with transaction.atomic():
        locked = locked_copy(row)
        if locked.sent_at is not None:
            outcome = Outcome.ALREADY_SENT
        else:
            outcome = attempt(locked, moment)
            locked.save()
    row.refresh_from_db()
    return outcome


def mirror_waitlist(entry: WaitlistEntry) -> WaitlistMirror:
    """Chapter 04's TODO: a new waitlist signup also goes to Inbox as a `waitlist-signup`, by the
    same rule as a report. One copy per entry, made and sent only when the entry is new."""
    mirror, created = WaitlistMirror.objects.get_or_create(entry=entry)
    if created:
        deliver(mirror)
    return mirror


def locked_copy(row: InboxDelivery) -> InboxDelivery:
    """The row again, read with a lock held to the end of the transaction: a second caller waits
    here, then finds `sent_at` set and sends nothing. (`of=("self",)` locks this table's row and
    not the waitlist entry it joins. SQLite has no row locks and one writer at a time.)"""
    if isinstance(row, Report):
        return Report.objects.select_for_update().get(pk=row.pk)
    if isinstance(row, WaitlistMirror):
        mirrors = WaitlistMirror.objects.select_related("entry")
        return mirrors.select_for_update(of=("self",)).get(pk=row.pk)
    raise TypeError(f"not a row for Inbox: {row!r}")


def attempt(row: InboxDelivery, moment: datetime) -> Outcome:
    try:
        config = load_config()
    except InboxNotConfigured as off:
        row.inbox_status = InboxStatus.OFF
        row.last_error = off.message[:ERROR_LIMIT]
        return Outcome.OFF
    row.attempts += 1
    row.last_tried_at = moment
    try:
        row.inbox_id = send(config, row.submission(), int(moment.timestamp()))
    except InboxError as error:
        row.inbox_status = InboxStatus.FAILED
        row.last_error = error.message[:ERROR_LIMIT]
        return Outcome.REFUSED if isinstance(error, InboxRefused) else Outcome.UNAVAILABLE
    row.inbox_status = InboxStatus.SENT
    row.sent_at = moment
    row.last_error = ""
    return Outcome.SENT


@dataclass
class DeliveryRun:
    """What one pass over the unsent rows did, for the cron's JSON and the command's output."""

    checked: int = 0
    sent: int = 0
    failed: int = 0
    stopped: str = ""
    errors: list[str] = field(default_factory=list[str])

    def as_dict(self) -> dict[str, object]:
        return {
            "checked": self.checked,
            "sent": self.sent,
            "failed": self.failed,
            "stopped": self.stopped,
        }


def unsent() -> list[InboxDelivery]:
    """Every row Inbox has not taken, oldest first, reports and waitlist copies together."""
    rows: list[InboxDelivery] = [
        *Report.objects.filter(sent_at__isnull=True).order_by("created_at")[:BATCH],
        *WaitlistMirror.objects.filter(sent_at__isnull=True)
        .select_related("entry")
        .order_by("created_at")[:BATCH],
    ]
    return sorted(rows, key=lambda row: row.created_at)[:BATCH]


def send_unsent(now: datetime | None = None) -> DeliveryRun:
    """Try every unsent row once. Inbox off sends nothing and says why. A timeout or a 5xx stops
    the run, because the next row would wait out the same timeout; a 4xx is that row's own
    problem, so it is recorded and the rest go on."""
    run = DeliveryRun()
    try:
        load_config()
    except InboxNotConfigured as off:
        run.stopped = off.message
        return run
    for row in unsent():
        run.checked += 1
        outcome = deliver(row, now)
        if outcome is Outcome.SENT:
            run.sent += 1
        if outcome in (Outcome.SENT, Outcome.ALREADY_SENT):
            continue
        run.failed += 1
        run.errors.append(f"{row}: {row.last_error}")
        if outcome is Outcome.UNAVAILABLE:
            run.stopped = row.last_error
            break
    return run
```

Things to notice:

- **`deliver()` never raises for Inbox.** Every answer becomes an `Outcome` and a few columns. The caller (the
  view, the cron, the admin) decides what to say.
- **The lock is a second read.** `locked_copy()` reads the row again with `select_for_update()` inside
  `transaction.atomic()`. On Postgres a second caller waits at that line, then sees `sent_at` and sends nothing.
  `of=("self",)` locks the mirror's row and not the waitlist entry `select_related` joins (Django Software
  Foundation, n.d.).
- **Off is not an attempt.** With Inbox off the row's status reads "Off, will retry" and `attempts` stays where
  it was; the count is of requests that left the app.
- **The nightly run stops on a timeout.** `send_unsent()` treats a refusal as that row's and goes on, and treats
  a timeout or a 5xx as Inbox's and stops, with the reason in `stopped`.

### 13.6 The form, the view and the links

Listing 13-13, Filename: `src/invest_witus_site/reports/forms.py`:

```python
"""The report form: a kind, a message, the page, an email when signed out, and the honeypot."""

from typing import Any

from django import forms

from invest_witus_site.reports.models import MESSAGE_LIMIT, PAGE_LIMIT, Report


class ReportForm(forms.Form):
    kind = forms.ChoiceField(
        label="What is this about?", choices=Report.Kind.choices, widget=forms.RadioSelect
    )
    message = forms.CharField(
        label="Your message",
        max_length=MESSAGE_LIMIT,
        widget=forms.Textarea(attrs={"rows": 6}),
        help_text="What happened, or what you want to know. Leave out passwords and keys.",
    )
    page = forms.CharField(
        label="What page were you on? (optional)",
        max_length=PAGE_LIMIT,
        required=False,
        help_text="Filled in from the page you came from. Change or clear it.",
    )
    email = forms.EmailField(
        label="Your email",
        max_length=254,
        required=False,
        help_text="So a reply can reach you. Used for this report only.",
    )
    # The honeypot, as on the waitlist form (chapter 04): people never see it, bots fill it in.
    website = forms.CharField(
        required=False,
        label="Leave this field empty",
        widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}),
    )

    def __init__(self, *args: Any, signed_in: bool = False, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.signed_in = signed_in
        if signed_in:
            # Signed in, the WitUS identity says who wrote it; there is no email to type.
            del self.fields["email"]
        else:
            self.fields["email"].required = True

    def clean_message(self) -> str:
        message = str(self.cleaned_data["message"]).strip()
        if not message:
            raise forms.ValidationError("Write a sentence or two.")
        return message

    def clean_page(self) -> str:
        return page_path(str(self.cleaned_data.get("page") or ""))

    def is_bot(self) -> bool:
        return bool(self.cleaned_data.get("website"))


def page_path(text: str) -> str:
    """A path on this site, without its query string, or empty. Anything else (a full URL to
    another site, a sentence) is kept as typed, trimmed, because the person may mean it."""
    value = text.strip()[:PAGE_LIMIT]
    if value.startswith("/") and not value.startswith("//"):
        return value.split("?", 1)[0].split("#", 1)[0]
    return value
```

`__init__` takes `signed_in`: signed in, the email field is removed; signed out, it is required. `page_path`
keeps a path on this site without its query string, and keeps anything else as typed, because the person may mean
it.

Listing 13-14, Filename: `src/invest_witus_site/reports/views.py`:

```python
"""`/report/`: report a problem or ask a question, signed in or not.

The view saves the report, then sends it to WitUS Inbox, then redirects to the thank-you page
whatever Inbox said: a failed send is the row's business (`delivery.py`), never the person's.
Signed out, the form asks for an email; signed in, the WitUS identity supplies it. A honeypot
keeps simple bots out quietly, CSRF comes with every Django form, and a rate limit counts the
reports already in the database, because Vercel's functions share no memory to count in.
"""

import hashlib
import hmac
from datetime import timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth.models import User
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from invest_witus_site.accounts.models import WitusIdentity
from invest_witus_site.health import app_version
from invest_witus_site.reports.delivery import deliver
from invest_witus_site.reports.forms import ReportForm, page_path
from invest_witus_site.reports.inbox import configured
from invest_witus_site.reports.models import PAGE_LIMIT, Report

# Five reports an hour from one address, and five from one signed-in person. Enough for anyone
# writing by hand; a script hits it on the sixth.
RATE_LIMIT = 5
RATE_WINDOW = timedelta(hours=1)
LIMITED = (
    "You have sent five reports in the last hour, which is the limit. "
    "Your earlier reports are saved; please try again later."
)


def report(request: HttpRequest) -> HttpResponse:
    signed_in = request.user.is_authenticated
    if request.method != "POST":
        form = ReportForm(initial={"page": referrer_path(request)}, signed_in=signed_in)
        return page(request, form)
    form = ReportForm(request.POST, signed_in=signed_in)
    if not form.is_valid():
        return page(request, form)
    if form.is_bot():
        # The same thank-you a person gets, so a bot learns nothing; nothing is saved.
        return redirect("report-thanks")
    user = request.user if isinstance(request.user, User) else None
    key = client_key(request)
    if over_limit(key, user):
        form.add_error(None, LIMITED)
        return page(request, form, status=429)
    email, name = who(user, str(form.cleaned_data.get("email") or ""))
    row = Report.objects.create(
        kind=form.cleaned_data["kind"],
        message=form.cleaned_data["message"],
        page=form.cleaned_data["page"],
        view=view_letter(request, form.cleaned_data["page"]),
        user=user,
        email=email,
        name=name,
        user_agent=request.headers.get("User-Agent", "")[:PAGE_LIMIT],
        app_version=version(),
        origin=request.build_absolute_uri("/").rstrip("/"),
        client_key=key,
    )
    deliver(row)
    return redirect("report-thanks")


def thanks(request: HttpRequest) -> HttpResponse:
    return render(request, "reports/thanks.html")


def page(request: HttpRequest, form: ReportForm, status: int = 200) -> HttpResponse:
    context = {"form": form, "inbox_on": configured()}
    return render(request, "reports/report.html", context, status=status)


def referrer_path(request: HttpRequest) -> str:
    """The path of the page the person came from, when it is a page of this site and not this
    form; otherwise empty. The query string is dropped: it may hold more than the person meant
    to send."""
    referrer = urlsplit(request.headers.get("Referer", ""))
    if referrer.netloc != request.get_host() or referrer.path == reverse("report"):
        return ""
    return page_path(referrer.path)


def view_letter(request: HttpRequest, path: str) -> str:
    """The method page's view (A, B or C, chapter 10) when the report is about a method page."""
    saved = request.session.get("method_view")
    if "/method/" in path and isinstance(saved, str) and saved in ("a", "b", "c"):
        return saved.upper()
    return ""


def client_key(request: HttpRequest) -> str:
    """A keyed hash of the sender's address, so the limit can count without storing the address.
    On Vercel the address is the first entry of `X-Forwarded-For`, which Vercel overwrites with
    the client's public IP (its request headers page, read October 29, 2026); elsewhere it is the
    connection's own address. A header a client sends to a laptop is never trusted."""
    if settings.ON_VERCEL:
        address = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    else:
        address = str(request.META.get("REMOTE_ADDR") or "")
    key = settings.SECRET_KEY.encode("utf-8")
    return hmac.new(key, (address or "unknown").encode("utf-8"), hashlib.sha256).hexdigest()[:32]


def over_limit(key: str, user: User | None) -> bool:
    since = timezone.now() - RATE_WINDOW
    recent = Report.objects.filter(created_at__gte=since)
    if recent.filter(client_key=key).count() >= RATE_LIMIT:
        return True
    return user is not None and recent.filter(user=user).count() >= RATE_LIMIT


def who(user: User | None, typed_email: str) -> tuple[str, str]:
    """The email and name sent with the report: the WitUS identity's when signed in (or the
    user's own, for the owner before their first WitUS sign-in), the typed email otherwise."""
    if user is None:
        return typed_email.strip().lower(), ""
    identity = WitusIdentity.objects.filter(user=user).first()
    if identity is not None:
        return identity.email or user.email, identity.display_name
    return user.email, user.get_username()


def version() -> str:
    """The app's version, and the deployed commit when Vercel names it (PRD 7.8)."""
    commit = settings.GIT_COMMIT_SHA[:7]
    return f"{app_version()}+{commit}" if commit else app_version()
```

Things to notice:

- **Save, send, redirect.** `Report.objects.create(...)`, then `deliver(row)`, then the thank-you, whatever
  `deliver` returned.
- **The honeypot answers like a person's form.** A bot gets the same redirect, and nothing is saved or sent.
- **The limit runs before the save.** Five rows in the last hour from this `client_key`, or from this user,
  and the form comes back with status 429.
- **`client_key` trusts `X-Forwarded-For` only on Vercel,** where Vercel sets it. On a laptop anyone can send
  that header.
- **`who()` prefers the WitUS identity.** The owner's superuser before its first WitUS sign-in sends the user's
  own email and username.

The two templates:

Listing 13-15, Filename: `src/invest_witus_site/reports/templates/reports/report.html`:

```html
{% extends "pages/base.html" %}
{% block title %}Report a problem or ask a question: Invest.WitUS{% endblock %}
{% block content %}
<section class="container narrow">
  <h1>Report a problem or ask a question</h1>
  <p>Tell us what broke, what you wish the app did, or what you want to know. The operator reads every report.</p>
  {% if not inbox_on %}
  {# Chapter 13: with the three INBOX_ names unset (a learner's copy, a laptop) the report is saved here and #}
  {# the owner reads it in the admin; nothing is forwarded. Said plainly, because it is true. #}
  <p class="report-off">On this copy of the app, reports are saved for the owner to read in the admin. Forwarding to WitUS Inbox is off.</p>
  {% endif %}
  <form method="post" action="{% url 'report' %}" class="report-form" novalidate>
    {% csrf_token %}
    {{ form.non_field_errors }}
    <fieldset class="field">
      <legend>{{ form.kind.label }}</legend>
      {{ form.kind }}
      {{ form.kind.errors }}
    </fieldset>
    <div class="field">
      <label for="{{ form.message.id_for_label }}">{{ form.message.label }}</label>
      {{ form.message }}
      <p class="small muted" id="{{ form.message.auto_id }}_helptext">{{ form.message.help_text }}</p>
      {{ form.message.errors }}
    </div>
    <div class="field">
      <label for="{{ form.page.id_for_label }}">{{ form.page.label }}</label>
      {{ form.page }}
      <p class="small muted" id="{{ form.page.auto_id }}_helptext">{{ form.page.help_text }}</p>
      {{ form.page.errors }}
    </div>
    {% if form.email %}
    <div class="field">
      <label for="{{ form.email.id_for_label }}">{{ form.email.label }}</label>
      {{ form.email }}
      <p class="small muted" id="{{ form.email.auto_id }}_helptext">{{ form.email.help_text }}</p>
      {{ form.email.errors }}
    </div>
    {% else %}
    <p class="small muted">Sent as {{ display_name }}, from your WitUS sign-in.</p>
    {% endif %}
    {# The honeypot, as on the waitlist form: hidden from people by the stylesheet and from assistive tech. #}
    <div class="honeypot" aria-hidden="true">
      <label for="{{ form.website.id_for_label }}">Leave this field empty</label>
      {{ form.website }}
    </div>
    <button type="submit">Send</button>
  </form>
</section>
{% endblock %}
```

Listing 13-16, Filename: `src/invest_witus_site/reports/templates/reports/thanks.html`:

```html
{% extends "pages/base.html" %}
{% block title %}Thank you: Invest.WitUS{% endblock %}
{% block content %}
<section class="container narrow">
  <h1>Thank you</h1>
  <p>Your report is saved, and the operator reads every one.</p>
  <p>Meanwhile, the <a href="{% url 'faq' %}">FAQ</a> may already answer a question.</p>
</section>
{% endblock %}
```

Each help text has the id Django's widget names in `aria-describedby`, so a screen reader reads it with the
field. The link goes last in the header's list, so on a phone it folds with the others behind **Menu** when you
are signed in, and in the footer's Partners and Legal column beside **Report a bad actor**:

Listing 13-17, Filename: `src/invest_witus_site/pages/templates/pages/_header.html`:

```html
{% load static %}
{# Logo: gemini/witus/public/brand/04-orbit-type/logomark.svg, drawn for dark backgrounds, copied into static/brand/witus/. #}
<header class="site-header">
  <div class="container header-row">
    <a class="brand" href="{% url 'home' %}">
      <img src="{% static 'brand/witus/logomark.svg' %}" alt="" width="32" height="32">
      Invest.WitUS
    </a>
    <nav class="site-nav" aria-label="Primary" data-menu>
      {% if user.is_authenticated %}
      {# Small screens (decision 115): a signed-in person's links fold behind this button. It starts #}
      {# `hidden`, so with JavaScript off there is no dead button and the list stays visible; #}
      {# pages/menu.js shows it and folds the list only below 40rem. Signed out there are two links #}
      {# and no button, so the public pages keep carrying no script (chapter 06a's test). The sign-in #}
      {# and sign-out control sits outside the list and is always shown. #}
      <button type="button" class="menu-toggle" aria-expanded="false" aria-controls="primary-menu" hidden>Menu</button>
      {% endif %}
      <ul class="menu-links" id="primary-menu">
        <li><a href="{% url 'faq' %}">FAQ</a></li>
        <li><a href="{% url 'home' %}#waitlist">Waitlist</a></li>
        {% if user.is_authenticated %}
        {# Chapter 08: the link to their accounts, valued, on this branch only; no public page links it. #}
        <li><a href="{% url 'account-list' %}">Accounts</a></li>
        {# The Alpaca paper page, for the owner of the account linked to it (`paper_account_id`). #}
        {% if paper_account_id %}<li><a href="{% url 'paper-account' paper_account_id %}">Paper account</a></li>{% endif %}
        {# The first account with a plan or an entry (`logbook_account_id`, decision 115). #}
        {% if logbook_account_id %}<li><a href="{% url 'logbook' logbook_account_id %}">Logbook</a></li>{% endif %}
        {% endif %}
        {# Chapter 13: the in-app reporter, signed in and out, last in the list. #}
        <li><a href="{% url 'report' %}">Report a problem or ask a question</a></li>
      </ul>
      <div class="menu-always">
        {% if user.is_authenticated %}
          {# Signed in (chapter 07): the person's name, then the "Sign out" control, a form. #}
          <span class="who muted">{{ display_name }}</span>
          {% include "accounts/_sign_out_form.html" %}
        {% else %}
          {# While a visitor is signed out, this link's accessible name is exactly "Sign in" on every page. #}
          {# Never rename it (shared UI rule, 2026-10-16): the smoke test in tests/test_ch04.py fails if it changes. #}
          <a class="button" href="{% url 'sign-in' %}">Sign in</a>
        {% endif %}
      </div>
    </nav>
  </div>
</header>
```

Listing 13-18, Filename: `src/invest_witus_site/pages/templates/pages/_footer.html`:

```html
{% load static %}
{# The ecosystem footer, after gemini/witus/public/brand/footer-recipe.md: the same structure as every #}
{# WitUS app in this app's own palette. The Rise Wellness callout and its disclaimer are verbatim (only #}
{# the app name changed) and so is the copyright line. The dashes in them are written as HTML entities #}
{# so the source file stays dash-free; the page shows them. #}
<footer class="site-footer">
  <div class="container">
    <div class="footer-brand">
      {# Logo: gemini/witus/public/brand/04-orbit-type/wordmark.svg, copied into static/brand/witus/. #}
      <img src="{% static 'brand/witus/wordmark.svg' %}" alt="WitUS" width="110" height="28">
      <p class="footer-name">Invest.WitUS</p>
      <p class="muted">Pick a taught investing method and stay with it, on paper first.</p>
      <p class="notice">Not advice. Invest.WitUS is a learning tool: it recommends nothing, holds no money, and shows no market data on public pages.</p>
    </div>

    <section aria-labelledby="rise-wellness-heading" class="rise">
      <header class="rise-header">
        <p class="eyebrow">Mental health support</p>
        <h2 id="rise-wellness-heading">Rise Wellness of Indiana</h2>
        <p class="muted small">Independent mental health provider &middot; Not affiliated with Invest.WitUS</p>
      </header>
      <p>Rise Wellness of Indiana provides compassionate, personalized, holistic mental health care: evidence-based medicine, trauma-informed care, and a whole-person approach to help you heal, grow, and thrive in mind, body, and spirit.</p>
      <div class="rise-grid">
        <div>
          <p class="eyebrow muted">Services</p>
          <ul class="plain small">
            <li>ADHD testing &amp; management (in-person and from home)</li>
            <li>Anxiety &amp; depression</li>
            <li>Maternal mental health</li>
            <li>Medication management</li>
            <li>GeneSight&reg; genetic testing</li>
            <li>Behavioral therapy &amp; coaching</li>
            <li>Routine lab testing</li>
          </ul>
        </div>
        <div>
          <p class="eyebrow muted">Visit or call</p>
          <address class="small">320 North Meridian Street<br>Indianapolis, IN 46204<br>Mon&ndash;Sat by appointment &middot; Sun closed</address>
          <p class="small rise-links">
            <a href="tel:+13179650299">317-965-0299</a>
            <span aria-hidden="true">&middot;</span>
            <a href="https://risewellnessofindiana.com" target="_blank" rel="noopener noreferrer">risewellnessofindiana.com<span class="sr-only"> (opens in new tab)</span></a>
            <span aria-hidden="true">&middot;</span>
            <a href="https://www.centenarianos.com/safety#rise-wellness" target="_blank" rel="noopener noreferrer">Full safety page<span class="sr-only"> on centenarianos.com (opens in new tab)</span></a>
          </p>
        </div>
      </div>
      <blockquote class="rise-quote small">
        &ldquo;At Rise Wellness, we believe everyone has the capacity to rise above challenges and live a fulfilling, healthy life. Our care is guided by the belief that healing is personal, holistic, and rooted in compassion.&rdquo;
        <span class="attribution muted">Rise Wellness of Indiana</span>
      </blockquote>
      {# The non-negotiable disclaimer. Only the app name token changed; never paraphrase, trim or reorder it. #}
      <p class="disclaimer muted">Rise Wellness of Indiana is an independent organization. They are not affiliated with, employed by, or endorsed by Invest.WitUS, CentenarianOS, B4C LLC, AwesomeWebStore.com, or Anthony McDonald. We are grateful for their collaboration on mental health safety resources for our community.</p>
    </section>

    <div class="footer-grid">
      <div>
        <p class="footer-heading">Ecosystem</p>
        <ul class="plain">
          {% for product in ecosystem_products %}
            <li>
              {% if product.status == "coming-soon" %}
                <span class="muted">{{ product.name }} (coming soon)</span>
              {% else %}
                <a href="{{ product.href }}" target="_blank" rel="noopener noreferrer">{{ product.name }}<span class="sr-only"> (opens in new tab)</span></a>
              {% endif %}
            </li>
          {% endfor %}
        </ul>
        <p class="footer-heading">Infrastructure</p>
        <ul class="plain">
          {% for product in infrastructure_products %}
            <li><a href="{{ product.href }}" target="_blank" rel="noopener noreferrer">{{ product.name }}<span class="sr-only"> (opens in new tab)</span></a></li>
          {% endfor %}
        </ul>
      </div>
      <div>
        <p class="footer-heading">Invest.WitUS</p>
        <ul class="plain">
          <li><a href="{% url 'home' %}#roadmap">Roadmap</a></li>
          <li><a href="{% url 'faq' %}">FAQ</a></li>
          {% if user.is_authenticated %}
            <li>{% include "accounts/_sign_out_form.html" %}</li>
          {% else %}
            <li><a href="{% url 'sign-in' %}">Sign in</a></li>
          {% endif %}
        </ul>
      </div>
      <div>
        <p class="footer-heading">Partners &amp; Legal</p>
        <ul class="plain">
          <li>
            <a href="https://www.centenarianos.com/safety#rise-wellness" target="_blank" rel="noopener noreferrer">Rise Wellness<span class="sr-only"> (mental-health partner, opens in new tab)</span></a>
            <p class="muted small">Mental-health partner</p>
          </li>
          <li><a href="{% url 'terms' %}">Terms</a></li>
          <li><a href="{% url 'privacy' %}">Privacy</a></li>
          <li><a href="{% url 'faq' %}#report-a-bad-actor">Report a bad actor</a></li>
          {# Chapter 13: the in-app reporter, on every page, signed in or out. #}
          <li><a href="{% url 'report' %}">Report a problem or ask a question</a></li>
          <li><a href="{% url 'contact' %}">Contact</a></li>
        </ul>
      </div>
    </div>

    <div class="copyright muted small">
      <p>&copy; {{ year }} B4C LLC &mdash; A <a href="https://awesomewebstore.com" target="_blank" rel="noopener noreferrer">AwesomeWebStore.com<span class="sr-only"> (opens in new tab)</span></a> brand</p>
    </div>
  </div>
</footer>
```

Five lines join the stylesheet, at the end: the text box, the three choices as 44-pixel targets, and the
"forwarding is off" note:

Listing 13-19, Filename: `src/invest_witus_site/pages/static/pages/site.css`:

```css
/* Invest.WitUS: one hand-written stylesheet, no build step.
   Dark surface because the WitUS logo (static/brand/witus/, from gemini/witus/public/brand/04-orbit-type/)
   is drawn for dark backgrounds. Accent: sky, this app's color in the ecosystem registry. */

:root {
  --bg: #020617;
  --surface: #0f172a;
  --border: #1e293b;
  --text: #f1f5f9;
  --muted: #94a3b8;
  --accent: #38bdf8;
  --accent-ink: #082f49;
  --danger: #fda4af;
  --max: 64rem;
  --gutter: 1rem;
}

* { box-sizing: border-box; }

html { color-scheme: dark; }

body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 16px/1.6 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}

a { color: var(--accent); }
a:hover { text-decoration-thickness: 2px; }

a:focus-visible, button:focus-visible, input:focus-visible, [tabindex="-1"]:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-radius: 2px;
}

h1, h2, h3 { line-height: 1.2; }
h1 { font-size: clamp(1.6rem, 4vw, 2.4rem); }
h2 { font-size: 1.35rem; margin-top: 2.5rem; }
h3 { font-size: 1.1rem; }

.container { max-width: var(--max); margin: 0 auto; padding: 0 var(--gutter); }
.narrow { max-width: 42rem; }
.muted { color: var(--muted); }
.small { font-size: 0.875rem; }
.eyebrow { font-size: 0.75rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent); font-weight: 600; }
.lead { font-size: 1.125rem; }
.plain { list-style: none; margin: 0; padding: 0; }
.plain li { margin: 0.25rem 0; }

.sr-only {
  position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
  overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;
}

.skip-link { position: absolute; left: -999px; top: 0.5rem; background: var(--accent); color: var(--accent-ink); padding: 0.5rem 1rem; z-index: 10; }
.skip-link:focus { left: 0.5rem; }

/* Header */
.site-header { border-bottom: 1px solid var(--border); background: var(--surface); }
.header-row { display: flex; align-items: center; justify-content: space-between; gap: 1rem; min-height: 3.5rem; flex-wrap: wrap; }
.brand { display: inline-flex; align-items: center; gap: 0.5rem; color: var(--text); font-weight: 800; text-decoration: none; }
.brand img { display: block; }
.site-header nav { display: flex; align-items: center; gap: 0.5rem 1rem; flex-wrap: wrap; min-width: 0; }
.site-header nav a { min-height: 2.75rem; display: inline-flex; align-items: center; }
/* The links as a list (decision 115), laid out in the row as before; no bullets, no indent. */
.menu-links { display: flex; align-items: center; gap: 0 1rem; flex-wrap: wrap; list-style: none; margin: 0; padding: 0; }
.menu-always { display: flex; align-items: center; gap: 0.5rem 1rem; flex-wrap: wrap; min-width: 0; }
/* Signed in (chapter 07): the name and the Sign out form sit in the row like the links. */
.site-header nav form { margin: 0; }
.site-header .who { max-width: 14rem; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
/* The Menu button: a 44px target like every other control. `hidden` wins until menu.js clears it. */
.menu-toggle {
  min-height: 2.75rem; min-width: 2.75rem; padding: 0 1rem; background: transparent; color: var(--text);
  font: inherit; font-weight: 700; border: 1px solid var(--border); border-radius: 0.375rem; cursor: pointer;
}
.menu-toggle[hidden] { display: none; }
.menu-toggle[aria-expanded="true"] { border-color: var(--accent); }
@media (max-width: 39.99rem) {
  .site-header .who { max-width: 9rem; }
  /* With menu.js running, the list folds below the row until the button opens it. */
  .js-menu { width: 100%; justify-content: space-between; }
  .js-menu .menu-links { display: none; order: 3; width: 100%; flex-direction: column; align-items: stretch; padding: 0.25rem 0 0.75rem; }
  .js-menu.is-open .menu-links { display: flex; }
  .js-menu .menu-links a { width: 100%; }
}
@media (min-width: 40rem) {
  .menu-toggle { display: none; }
}
.site-footer form { margin: 0.25rem 0; }
.site-footer button[type="submit"] { min-height: 2.25rem; padding: 0 0.75rem; font-size: 0.875rem; }
.signed-in { margin: 0.5rem 0 0; }

.button {
  display: inline-flex; align-items: center; min-height: 2.75rem; padding: 0 1rem;
  background: var(--accent); color: var(--accent-ink); font-weight: 700; text-decoration: none; border-radius: 0.375rem;
}
.button:hover { background: #7dd3fc; }

main { padding: 1rem 0 3rem; }
.hero { padding-top: 2rem; }
.actions { display: flex; gap: 1rem; align-items: center; flex-wrap: wrap; }
.steps li { margin-bottom: 0.75rem; }

.callout { border: 1px solid var(--accent); background: rgba(56, 189, 248, 0.08); border-radius: 0.5rem; padding: 1rem 1.25rem; }
.callout h2 { margin-top: 0; }

/* Forms */
.waitlist-form { max-width: 28rem; }
.field { margin-bottom: 1rem; }
.field label { display: block; font-weight: 600; margin-bottom: 0.25rem; }
.field input { width: 100%; min-height: 2.75rem; padding: 0.5rem 0.75rem; background: var(--surface); color: var(--text); border: 1px solid var(--border); border-radius: 0.375rem; font: inherit; }
.errorlist { list-style: none; padding: 0; margin: 0.25rem 0 0; color: var(--danger); font-size: 0.875rem; }
button[type="submit"] { min-height: 2.75rem; padding: 0 1.25rem; background: var(--accent); color: var(--accent-ink); font: inherit; font-weight: 700; border: 0; border-radius: 0.375rem; cursor: pointer; }
.honeypot { position: absolute; left: -10000px; top: auto; width: 1px; height: 1px; overflow: hidden; }

/* Markdown pages */
.prose { max-width: 48rem; }
.prose blockquote { margin: 1.5rem 0; padding: 1rem 1.25rem; border-left: 4px solid var(--accent); background: rgba(56, 189, 248, 0.08); border-radius: 0 0.5rem 0.5rem 0; }
.prose a { overflow-wrap: anywhere; }

/* Footer */
.site-footer { border-top: 1px solid var(--border); margin-top: 3rem; padding: 2.5rem 0; background: var(--surface); font-size: 0.9375rem; }
.footer-brand { text-align: center; margin-bottom: 2rem; }
.footer-brand img { display: inline-block; }
.footer-name { font-weight: 800; margin: 0.5rem 0 0; }
.footer-brand p { margin: 0.25rem 0; }
.notice { max-width: 40rem; margin: 0.75rem auto 0; }
.footer-heading { font-weight: 600; margin: 0 0 0.5rem; }
.footer-grid { display: grid; grid-template-columns: 1fr; gap: 2rem; }
@media (min-width: 40rem) { .footer-grid { grid-template-columns: repeat(3, 1fr); } }
.footer-grid a, .rise-links a { display: inline-flex; align-items: center; min-height: 1.75rem; }
.footer-grid .footer-heading + ul + .footer-heading { margin-top: 1.25rem; }
.copyright { margin-top: 2rem; padding-top: 1.5rem; border-top: 1px solid var(--border); text-align: center; }

.rise { border: 1px solid rgba(56, 189, 248, 0.3); background: rgba(56, 189, 248, 0.06); border-radius: 0.5rem; padding: 1.25rem; margin-bottom: 2rem; }
.rise h2 { font-size: 1rem; margin: 0.25rem 0 0; }
.rise-header p { margin: 0; }
.rise-grid { display: grid; grid-template-columns: 1fr; gap: 1rem; margin-top: 1rem; }
@media (min-width: 40rem) { .rise-grid { grid-template-columns: 1fr 1fr; } }
.rise address { font-style: normal; }
.rise-links { display: flex; flex-wrap: wrap; gap: 0.5rem 0.75rem; align-items: center; }
.rise-quote { margin: 1rem 0 0; padding-left: 0.75rem; border-left: 2px solid var(--accent); font-style: italic; }
.rise-quote .attribution { display: block; font-style: normal; margin-top: 0.25rem; }
.disclaimer { font-size: 0.75rem; margin: 1rem 0 0; }

/* The owner's account page (chapter 08): one table, numbers right-aligned in tabular figures. */
.holdings { width: 100%; border-collapse: collapse; margin: 1rem 0; }
.holdings th, .holdings td { padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; }
.holdings .num { text-align: right; font-variant-numeric: tabular-nums; }
.holdings tfoot th, .holdings tfoot td { border-bottom: 0; font-weight: 700; }
.stale { color: var(--danger); font-size: 0.75rem; letter-spacing: 0.08em; text-transform: uppercase; }

/* FAQ: each question is a <details>; the question line is the handle. */
.faq-item { border-top: 1px solid var(--line, #2a2f3a); padding: 0.4rem 0; }
.faq-item > summary { cursor: pointer; font-weight: 600; font-size: 1.05rem; padding: 0.5rem 0; list-style-position: outside; }
.faq-item > summary:hover { text-decoration: underline; }
.faq-item[open] > summary { margin-bottom: 0.25rem; }
/* The watch list (chapter 09): the same table, a short form under it, and a remove button that reads as a link. */
.watch-form { max-width: 28rem; }
.holdings form { margin: 0; }
.holdings .link-button { min-height: 2.25rem; padding: 0 0.5rem; background: transparent; color: var(--accent); font-weight: 600; text-decoration: underline; }
.holdings .link-button:hover { text-decoration-thickness: 2px; }

/* One-time notices after a form was handled (Django's messages, printed by base.html). */
.messages { list-style: none; padding: 0; margin: 1rem 0 0; }
.message { padding: 0.5rem 0.75rem; margin: 0.5rem 0; border: 1px solid var(--border); border-radius: 0.375rem; background: var(--surface); }
.message.success { border-color: var(--accent); }
.message.error { border-color: var(--danger); }

/* The method page (chapter 10): the view switch, the environment band, the status list and the cards. */
.views-list { display: flex; flex-wrap: wrap; gap: 0.5rem 1rem; margin: 1rem 0; }
.views-list a { display: inline-flex; align-items: center; min-height: 2.75rem; padding: 0 0.75rem; border: 1px solid var(--border); border-radius: 0.375rem; text-decoration: none; }
.views-list a[aria-current="page"] { border-color: var(--accent); background: rgba(56, 189, 248, 0.12); font-weight: 700; }
.band { border: 1px dashed var(--muted); border-radius: 0.375rem; padding: 0.5rem 0.75rem; font-size: 0.875rem; }
.card { border: 1px solid var(--border); border-radius: 0.5rem; padding: 1rem 1.25rem; margin: 1.5rem 0; background: var(--surface); }
.card h2 { margin-top: 0; }
.status { display: grid; grid-template-columns: max-content 1fr; gap: 0.25rem 1rem; margin: 1rem 0; font-size: 0.9375rem; }
.status dt { color: var(--muted); }
.status dd { margin: 0; }
.rules li, .findings li { margin-bottom: 0.5rem; }
.method-form { max-width: 28rem; }
.method-form input, .method-form select { width: 100%; min-height: 2.75rem; padding: 0.5rem 0.75rem; background: var(--surface); color: var(--text); border: 1px solid var(--border); border-radius: 0.375rem; font: inherit; }
.helptext { display: block; font-size: 0.875rem; color: var(--muted); margin-top: 0.25rem; }
/* Chapter 12: the logbook's filters, text boxes and radio choices, the explained finding, the lists. */
.method-form textarea, .filters select { width: 100%; padding: 0.5rem 0.75rem; background: var(--surface); color: var(--text); border: 1px solid var(--border); border-radius: 0.375rem; font: inherit; }
.method-form input[type="radio"] { width: auto; min-height: auto; margin-right: 0.5rem; }
.filters { display: flex; flex-wrap: wrap; gap: 0 1rem; align-items: end; }
.filters .field { min-width: 10rem; }
.filters select { min-height: 2.75rem; }
.explained { font-style: italic; }
.reviews li, .versions li, .events li { margin-bottom: 0.375rem; }
fieldset.field { border: 0; padding: 0; margin: 0 0 1rem; }
fieldset.field legend { font-weight: 600; margin-bottom: 0.25rem; padding: 0; }
/* The owner's price buttons (2026-10-29): Fetch prices now under the tables, Get history's range and button in a row. */
.fetch-now { margin: 1rem 0; }
.fetch-now p { margin: 0.5rem 0 0; }
.history-form { display: flex; flex-wrap: wrap; gap: 0.25rem 0.5rem; align-items: center; }
.history-form select { min-height: 2.25rem; padding: 0 0.5rem; background: var(--surface); color: var(--text); border: 1px solid var(--border); border-radius: 0.375rem; font: inherit; }
.get-history { margin: 1.5rem 0; }
/* Chapter 13: the report form, its text box and its three choices (each a 44px target). */
.report-form { max-width: 36rem; }
.report-form textarea { width: 100%; padding: 0.5rem 0.75rem; background: var(--surface); color: var(--text); border: 1px solid var(--border); border-radius: 0.375rem; font: inherit; }
.report-form input[type="radio"] { width: auto; min-height: auto; margin: 0 0.5rem 0 0; }
.report-form fieldset label { display: flex; align-items: center; min-height: 2.75rem; font-weight: 400; margin: 0; }
.report-off { border-left: 3px solid var(--accent); padding-left: 0.75rem; }
```

### 13.7 The waitlist's copy

Listing 13-20, Filename: `src/invest_witus_site/pages/views.py`:

```python
"""The public pages. A view takes a request and returns a response; the templates do the HTML."""

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.safestring import mark_safe

from invest_witus_site.pages.forms import WaitlistForm
from invest_witus_site.pages.markdown_pages import load_page
from invest_witus_site.pages.models import WaitlistEntry
from invest_witus_site.reports.delivery import mirror_waitlist

# The positioning line, word for word from the PRD (section 7.10).
POSITIONING = (
    "Pick a method you learned. Practice it on paper. "
    "The app keeps you to its rules and shows you the lesson behind each one."
)


def home(request: HttpRequest) -> HttpResponse:
    return render(request, "pages/home.html", {"positioning": POSITIONING, "form": WaitlistForm()})


def waitlist(request: HttpRequest) -> HttpResponse:
    """GET shows the form; POST adds the person once and redirects to the thank-you page.

    Redirecting after a POST (Post/Redirect/Get) means a browser refresh repeats a harmless GET,
    not the form submission. The thank-you is the same whether the address was new or already on
    the list, so the page never reveals who signed up.
    """
    if request.method != "POST":
        return render(request, "pages/waitlist.html", {"form": WaitlistForm()})
    form = WaitlistForm(request.POST)
    if not form.is_valid():
        return render(request, "pages/waitlist.html", {"form": form})
    if not form.is_bot():
        entry, created = WaitlistEntry.join(
            name=form.cleaned_data["name"], email=form.cleaned_data["email"]
        )
        if created:
            # Chapter 13: the new signup is copied to WitUS Inbox, saved first and sent after,
            # and a failed send waits for the nightly retry. The thank-you never depends on it.
            mirror_waitlist(entry)
    return redirect("waitlist-thanks")


def waitlist_thanks(request: HttpRequest) -> HttpResponse:
    return render(request, "pages/waitlist_thanks.html")


def markdown_page(request: HttpRequest, slug: str) -> HttpResponse:
    page = load_page(settings.SITE_PAGES_DIR, slug)
    # Django escapes everything a template prints. This HTML came from our own Markdown file, so
    # it is marked safe here, on purpose, in one place.
    return render(request, "pages/markdown_page.html", {"page": page, "body": mark_safe(page.html)})


def contact(request: HttpRequest) -> HttpResponse:
    return render(request, "pages/contact.html")


def sign_in_stub(request: HttpRequest) -> HttpResponse:
    """The page behind "Sign in" while the WitUS client is off (no `WITUS_OIDC_CLIENT_SECRET`).
    Chapter 04 wrote it as the stub for chapter 07; chapter 07 keeps it for a copy of the app
    that is not registered with the provider, which is every learner's copy."""
    return render(request, "pages/sign_in_stub.html")
```

`join` already returned whether the entry was new (chapter 04); the view now uses it. `mirror_waitlist`, in
`delivery.py` above, makes the copy and sends it. The thank-you is the same either way, as chapter 04 wanted, so
the page still never says whether an address was on the list.

### 13.8 The nightly retry, Send again and the command

Listing 13-21, Filename: `src/invest_witus_site/prices/views.py`:

```python
"""`GET /api/cron/pull-prices/`: the nightly pull, called by Vercel's cron, since chapter 11 the
paper order check after it, and since chapter 13 the retry of what WitUS Inbox has not taken.

Vercel sends the project's `CRON_SECRET` as `Authorization: Bearer <value>` with every cron
request (its docs, read October 28, 2026). The route compares that header with the setting in
constant time and answers 403 to anything else. With no secret configured it answers 503 and runs
nothing: a deploy that forgot the variable fails closed instead of pulling for anyone who asks.
"""

import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from invest_witus_site.paper.alpaca import AlpacaError, keys_configured, paper_client
from invest_witus_site.paper.orders import sync_orders
from invest_witus_site.prices.pull import DAYS_BACK, pull, symbol_universe
from invest_witus_site.prices.sources import source_from_settings
from invest_witus_site.reports.delivery import send_unsent
from invest_witus_site.reports.inbox import configured as inbox_configured

log = logging.getLogger(__name__)


def bearer_matches(header: str, secret: str) -> bool:
    """`compare_digest` takes the same time whether the first or the last byte differs."""
    return secrets.compare_digest(header.encode("utf-8"), f"Bearer {secret}".encode())


@never_cache
@require_GET
def pull_prices_cron(request: HttpRequest) -> JsonResponse:
    secret = settings.CRON_SECRET
    if not secret:
        log.error("cron: CRON_SECRET is not set; the pull did not run")
        return JsonResponse({"error": "CRON_SECRET is not set"}, status=503)
    if not bearer_matches(request.headers.get("Authorization", ""), secret):
        return JsonResponse({"error": "forbidden"}, status=403)
    today = timezone.localdate()
    result = pull(
        source_from_settings(), symbol_universe(), today - timedelta(days=DAYS_BACK), today
    )
    body = result.as_dict()
    # Chapter 11: then the paper orders, once the owner's Alpaca paper keys are set. Without them
    # the body is chapter 08's, unchanged. A failure is reported in the body; the prices stand.
    if keys_configured():
        try:
            body["orders"] = sync_orders(paper_client()).as_dict()
        except AlpacaError as error:
            body["orders"] = {"error": error.message}
    # Chapter 13: then every report and waitlist copy WitUS Inbox has not taken yet, once Inbox is
    # configured. Without it the body is unchanged, as with the Alpaca step above.
    if inbox_configured():
        body["inbox"] = send_unsent().as_dict()
    # Which schedule fired, when more than one cron shares a path; empty for a call by hand.
    body["schedule"] = request.headers.get("x-vercel-cron-schedule", "")
    log.info("cron: pull-prices %s", body)
    return JsonResponse(body)
```

With Inbox configured, the cron's JSON gains an `inbox` object (`checked`, `sent`, `failed`, `stopped`). Without
it the body is chapter 08's, unchanged, which chapter 08's tests still check.

Listing 13-22, Filename: `src/invest_witus_site/reports/admin.py`:

```python
"""Reports and the waitlist's copies in the admin: a list to read and triage, and "Send again".

What a person wrote and what Inbox answered are read-only: the admin is where the owner reads a
report and sets its triage status, not where a report is rewritten. "Send again" is the manual
fallback for the nightly retry; a row already sent is left alone.
"""

from collections.abc import Iterable
from typing import Any

from django.contrib import admin, messages
from django.db.models import QuerySet
from django.http import HttpRequest

from invest_witus_site.reports.delivery import Outcome, deliver
from invest_witus_site.reports.models import InboxDelivery, Report, WaitlistMirror

DELIVERY_FIELDS = (
    "inbox_status",
    "sent_at",
    "inbox_id",
    "attempts",
    "last_tried_at",
    "last_error",
    "created_at",
)


def send_again(
    model_admin: admin.ModelAdmin[Any], request: HttpRequest, rows: Iterable[InboxDelivery]
) -> None:
    """Send each selected row that Inbox has not taken, once, and say what happened."""
    counts = {outcome: 0 for outcome in Outcome}
    errors: list[str] = []
    for row in rows:
        outcome = deliver(row)
        counts[outcome] += 1
        if outcome not in (Outcome.SENT, Outcome.ALREADY_SENT):
            errors.append(f"{row}: {row.last_error}")
    summary = ", ".join(f"{count} {outcome}" for outcome, count in counts.items() if count)
    level = messages.WARNING if errors else messages.SUCCESS
    model_admin.message_user(request, f"Send again: {summary or 'nothing selected'}.", level)
    for error in errors:
        model_admin.message_user(request, error, messages.WARNING)


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin[Report]):
    list_display = ("__str__", "kind", "triage", "inbox_status", "page", "email", "created_at")
    list_filter = ("triage", "kind", "inbox_status")
    search_fields = ("message", "email", "page")
    readonly_fields = (
        "kind",
        "message",
        "page",
        "view",
        "user",
        "email",
        "name",
        "user_agent",
        "app_version",
        "origin",
        *DELIVERY_FIELDS,
    )
    exclude = ("client_key",)
    actions = ("send_selected_again",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    @admin.action(description="Send again to WitUS Inbox")
    def send_selected_again(self, request: HttpRequest, queryset: QuerySet[Report]) -> None:
        send_again(self, request, list(queryset))


@admin.register(WaitlistMirror)
class WaitlistMirrorAdmin(admin.ModelAdmin[WaitlistMirror]):
    list_display = ("__str__", "inbox_status", "attempts", "sent_at", "created_at")
    list_filter = ("inbox_status",)
    readonly_fields = ("entry", *DELIVERY_FIELDS)
    actions = ("send_selected_again",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    @admin.action(description="Send again to WitUS Inbox")
    def send_selected_again(self, request: HttpRequest, queryset: QuerySet[WaitlistMirror]) -> None:
        send_again(self, request, list(queryset.select_related("entry")))
```

What the person wrote and what Inbox answered are read-only; the triage status is the one field the owner edits.
There is no Add button: a report comes from the form. **Send again to WitUS Inbox** in the action menu sends the
selected rows and says what happened ("Send again: 1 sent, 1 already sent."), with each failure on its own line.

Listing 13-23, Filename: `src/invest_witus_site/reports/management/commands/reports.py`:

```python
"""`manage.py reports`: print the open reports, so a coding session in this repo can read them
(PRD 7.8). `--send` first sends every row WitUS Inbox has not taken, the nightly job's step, by
hand."""

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from invest_witus_site.reports.delivery import send_unsent
from invest_witus_site.reports.models import InboxStatus, Report


class Command(BaseCommand):
    help = "List reports not marked done; with --send, send unsent rows to WitUS Inbox first."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--send", action="store_true", help="Send unsent reports and waitlist copies first."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if options["send"]:
            run = send_unsent()
            self.stdout.write(
                f"Inbox: checked {run.checked}, sent {run.sent}, failed {run.failed}."
                + (f" Stopped: {run.stopped}" if run.stopped else "")
            )
            for error in run.errors:
                self.stderr.write(error)
        open_reports = Report.objects.exclude(triage=Report.Triage.DONE).order_by("created_at")
        if not open_reports:
            self.stdout.write("No open reports.")
            return
        for row in open_reports:
            self.stdout.write(
                f"#{row.pk} {row.created_at:%Y-%m-%d %H:%M} {row.kind}, {row.triage}; "
                f"Inbox: {InboxStatus(row.inbox_status).label}; page {row.page or '-'}"
            )
            self.stdout.write(f"    {' '.join(row.message.split())}")
```

### 13.9 The names in `.env.example`

Listing 13-24, Filename: `.env.example`:

```sh
# Copy to .env (git ignores it) and run with: uv run --env-file .env python manage.py runserver
# Names only; values never go in git. On Vercel the same names are set in the project's
# Environment Variables page (chapter 06); the laptop and the server share one settings file.

# "1" shows Django's debug pages and serves static files from runserver. Never "1" on a server:
# settings.py refuses to start on Vercel with it set.
DJANGO_DEBUG=1

# Required whenever DJANGO_DEBUG is not 1, which is every server. Make one with:
#   uv run python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
# Leave empty on your laptop: with DJANGO_DEBUG=1 a labeled dev-only key is used instead.
DJANGO_SECRET_KEY=

# Comma-separated host names the site answers to. Default: localhost,127.0.0.1
# Production: invest.witus.online (Vercel's own *.vercel.app host names are added on their own).
DJANGO_ALLOWED_HOSTS=

# Comma-separated origins, scheme and host, that may post the site's forms.
# Production: https://invest.witus.online
DJANGO_CSRF_TRUSTED_ORIGINS=

# The database. Empty: SQLite at data/private/invest-witus.sqlite3. On Vercel the Neon integration
# sets both names: DATABASE_URL is the pooled connection the app uses, DATABASE_URL_UNPOOLED the
# direct one that migrations use (`manage.py migrate --database direct`).
# Shape: postgresql://user:password@host/name?sslmode=require
# If the Vercel connect dialog added a prefix (the production project has STORAGE_), the
# prefixed names STORAGE_DATABASE_URL and STORAGE_DATABASE_URL_UNPOOLED work too.
DATABASE_URL=
DATABASE_URL_UNPOOLED=

# The owner's one-time, non-interactive superuser on a new database (chapter 06). These three are
# set in the shell for that one command, never written to a file:
#   DJANGO_SUPERUSER_USERNAME  DJANGO_SUPERUSER_EMAIL  DJANGO_SUPERUSER_PASSWORD
#   ... vercel env run -e production -- uv run python manage.py createsuperuser --noinput --database direct

# Vercel Web Analytics (chapter 06a). Both are set on Vercel, per environment, never on a laptop: the
# two script tags render only with VERCEL=1 (Vercel's own variable) and VERCEL_ANALYTICS=1, so
# Production can be on while Preview stays off. VERCEL_ANALYTICS_SCRIPT_PATH is the script path the
# project's Analytics page shows once Analytics is enabled (the quickstart writes it as
# /<unique-path>/script.js): copy it from there. Left empty, the FALLBACK /_vercel/insights/script.js
# is used, the shared route the quickstart names, not a value read from your dashboard. If the
# dashboard shows no page views after a deploy, set the path to what the page shows.
VERCEL_ANALYTICS=
VERCEL_ANALYTICS_SCRIPT_PATH=

# Sign in with WitUS (chapter 07): OpenID Connect against the ecosystem's identity provider. The
# client is OFF until WITUS_OIDC_CLIENT_SECRET is set; until then the sign-in route shows the stub
# page from chapter 04 and the site deploys as before. The owner mints the secret in the witus repo
# (`node scripts/gen-oidc-client.mjs invest`), which prints one value for the provider
# (WITUS_OIDC_SECRET__INVEST, on witus-online) and the same value for this app. Mark it Secret on
# Vercel. A learner's copy of the app is not registered with the provider and leaves it empty.
WITUS_OIDC_CLIENT_SECRET=
# The issuer the provider asserts in its discovery document. Default: https://accounts.witus.online,
# the ecosystem's accounts host as read on October 28, 2026. The discovery document is read from
# under it, and its own `issuer` field must match.
WITUS_OIDC_ISSUER=
# This app's client id at the provider. Default: witus-invest (the registry's `witus-<slug>`).
WITUS_OIDC_CLIENT_ID=
# The scopes asked for. Default: openid email profile. `openid` is required.
WITUS_OIDC_SCOPES=

# Prices (chapter 08). The nightly pull stores one close per symbol per day. With TIINGO_API_KEY
# set it asks Tiingo's end-of-day endpoint with your own token (https://www.tiingo.com/signup,
# then https://www.tiingo.com/account/api/token; the free plan allows 50 requests an hour, 1,000 a
# day and 500 unique symbols a month, "Internal Use Only", as read on October 28, 2026). Left
# empty, the pull reads <SYMBOL>.csv files in chapter 02's format from data/private/prices/
# (PRICES_CSV_DIR changes the folder), which is what a laptop uses.
TIINGO_API_KEY=
PRICES_CSV_DIR=
# What Vercel sends as "Authorization: Bearer <value>" to /api/cron/pull-prices/ once a day
# (vercel.json). Set it on Vercel only, Production, marked Sensitive; at least 16 random
# characters, for example: openssl rand -hex 24
# Unset, the route answers 503 and runs nothing, so a deploy without it fails closed.
CRON_SECRET=

# Alpaca paper trading (chapter 11). Your own PAPER keys: log in at https://app.alpaca.markets,
# switch the environment to paper in the top bar, then API Keys on the right of the dashboard,
# Generate New Key (Alpaca's "API key security" article, read October 29, 2026). The secret is
# shown once. Set both on Vercel as Sensitive, Production only. Empty: every Alpaca feature says
# the keys are not set and nothing is called. The host is fixed to paper-api.alpaca.markets in the
# code and is not a variable; APCA_API_BASE_URL, if set at all, must be that host or the settings
# refuse to start. Live keys never go here: live trading is not built.
ALPACA_PAPER_KEY_ID=
ALPACA_PAPER_SECRET_KEY=

# WitUS Inbox (chapter 13): where in-app reports ("Report a problem or ask a question") and new
# waitlist signups are copied for the operator, as a signed request (Inbox's webhook contract,
# witus-inbox/docs/webhook-contract.md). All three or nothing: with any one empty, reports and
# signups are still saved here and wait, the report form says forwarding is off, and nothing is
# sent. A learner's copy leaves them empty.
# INBOX_INGEST_URL: Inbox's ingest endpoint, https:// (http:// only for localhost), as the Inbox
# owner gives it. INBOX_SOURCE_SLUG: this app's source slug, lower-case words and hyphens, exactly
# as registered in Inbox's INGEST_SOURCES. INBOX_INGEST_SECRET: the same string Inbox holds for
# that slug, at least 32 characters (Inbox refuses shorter ones), one per environment, made with
# openssl rand -hex 32. Set on Vercel as Sensitive.
INBOX_INGEST_URL=
INBOX_SOURCE_SLUG=
INBOX_INGEST_SECRET=
```

The privacy page gains a dated **Reports** item under "What we store, and why", and the waitlist item says a new
signup is copied to Inbox. It is prose, not code; take it from the reference with the command in "If you get
stuck".

### 13.10 Green, and a report on your laptop

Listing 13-25, Terminal:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

```text
558 passed in 28.15s
All checks passed!
202 files already formatted
0 errors, 0 warnings, 0 informations
```

Forty-three new tests. Migrate the laptop database:

Listing 13-26, Terminal:

```sh
uv run --env-file .env python manage.py migrate
```

```text
Operations to perform:
  Apply all migrations: accounts, admin, auth, contenttypes, holdings, methods, pages, paper, prices, reports, sessions, watchlist
Running migrations:
  Applying reports.0001_initial... OK
```

Your laptop has no Inbox, which is the first thing to see. Open the form as if from the FAQ, send a question, and
read the row:

Listing 13-27, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -v 0 -c "
from django.test import Client
from invest_witus_site.reports.models import Report
c = Client()
form = c.get('/report/', headers={'Referer': 'http://testserver/faq/?q=fees'}).content.decode()
print('Inbox off said:', 'Forwarding to WitUS Inbox is off.' in form, '| page filled in:', 'value=\"/faq/\"' in form)
answer = c.post('/report/', {'kind': 'question', 'message': 'Where does the logbook live?', 'page': '/faq/', 'email': 'you@example.com'})
print(answer.status_code, answer['Location'])
row = Report.objects.first()
print(row, '|', row.inbox_status, '|', row.attempts, '|', row.last_error)
"
uv run --env-file .env python manage.py reports
```

```text
Inbox off said: True | page filled in: True
302 /report/thanks/
A question #1 | off | 0 | WitUS Inbox is off: INBOX_INGEST_URL, INBOX_SOURCE_SLUG, INBOX_INGEST_SECRET not set.
#1 2026-10-29 18:26 question, new; Inbox: Off, will retry; page /faq/
    Where does the logbook live?
```

The page came from the referrer without its `?q=fees`. Your date and time are when you ran it, in UTC. Now point
the app at the tests' fake Inbox for one process, make it refuse once, then let the retry through:

Listing 13-28, Terminal:

```sh
DJANGO_DEBUG=1 DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -v 0 -c "
import httpx, json
from django.conf import settings
from invest_witus_site.reports import inbox
from invest_witus_site.reports.delivery import send_unsent
from invest_witus_site.reports.models import Report
from tests.test_ch13 import SECRET, SOURCE, URL, FakeInbox
settings.INBOX_INGEST_URL, settings.INBOX_SOURCE_SLUG, settings.INBOX_INGEST_SECRET = URL, SOURCE, SECRET
fake = FakeInbox(); inbox.transport = httpx.MockTransport(fake.handle)
fake.answer = 401
print(send_unsent().as_dict())
print(Report.objects.first().last_error)
fake.answer = None
print(send_unsent().as_dict())
sent = fake.requests[-1]
print(sent.headers['x-witus-source'], sent.headers['x-witus-signature'][:7] + '...', len(sent.headers['x-witus-signature']))
body = json.loads(sent.content)
print(body['form_type'], body['priority'], body['submitter_email'], sorted(body['payload']))
row = Report.objects.first()
print(row.inbox_status, row.attempts, row.inbox_id)
print(send_unsent().as_dict())
"
```

```text
inbox: failed source=invest-witus form_type=invest-witus-support-question status=401
{'checked': 1, 'sent': 0, 'failed': 1, 'stopped': ''}
Inbox answered 401: the source slug is not registered there, the secret differs from Inbox's, or this server's clock is more than 5 minutes off. Inbox does not say which.
{'checked': 1, 'sent': 1, 'failed': 0, 'stopped': ''}
invest-witus sha256=... 71
invest-witus-support-question normal you@example.com ['admin_url', 'app_version', 'created_at', 'kind', 'message', 'page', 'report_id', 'signed_in', 'user_agent', 'view']
sent 2 inbox-2
{'checked': 0, 'sent': 0, 'failed': 0, 'stopped': ''}
```

The first line is the client's one log line for a failure: source, form type, status. The header is `sha256=`
and 64 hex characters, 71 in all. Two attempts, one sent, and a third run finds nothing to send. In a browser,
the same report is **Report a problem or ask a question** in the footer of any page, and the owner's list is
**Reports and WitUS Inbox**, **Reports** in the admin.

### 13.11 What the owner does outside the editor

The reference app's steps are task 21 in the owner's queue. A learner with a Vercel project and an Inbox of their
own does the same:

1. **Merge the chapter.** The push to `main` runs the migrate workflow (`docs/05-operations.md`), which applies
   `reports.0001`. Check that the run is green.
2. **Register the source in Inbox.** Make one secret per environment (`openssl rand -hex 32`), add
   `{"slug": "<your slug>", "hmac_secret": "<that secret>"}` to the `INGEST_SOURCES` variable of the Inbox
   project for that environment without removing the other entries, and redeploy Inbox: it reads the list when
   it starts.
3. **Set the three names on this app's project** (`INBOX_INGEST_URL`, `INBOX_SOURCE_SLUG`,
   `INBOX_INGEST_SECRET`), Sensitive, the secret identical to Inbox's for that environment, and redeploy.
4. **Send one report** from the live site's footer, and find it in Inbox's list under your slug. If the row in
   this app's admin reads "Failed, will retry" with a 401, compare the slug and the secret on both projects.

## Checkpoint

- `uv run pytest` prints `558 passed`; ruff and pyright pass.
- Every public page has **Report a problem or ask a question** in its header and its footer; signed in, it sits
  in the folding menu.
- Listing 13-27 saves a report with Inbox off and says so, and `manage.py reports` lists it.
- Listing 13-28 refuses once with Inbox's 401, sends on the retry, and finds nothing on the third run.
- No test reaches the network: `tests/conftest.py` fails any that tries.
- Commit and push: `git add -A && git commit -m "Chapter 13: the in-app reporter"`.

## Exercises

1. **Mark it done from Inbox.** The triage status here and Inbox's own status drift apart. Add a management
   command that, given an Inbox id, marks the matching report done, and decide which side is the record for
   triage. Write the reason in the decisions log.
2. **Your reports, signed in.** Add a page that lists the signed-in person's own reports with their kind, date and
   triage status, and nothing from anyone else. A test signs in as a second user and finds none of the first
   user's rows.
3. **A screenshot.** Add an optional image to the form, stored where chapter 06's deploy can keep it, with a size
   limit and a type check, and a link to it in the payload rather than the image itself. Decide what the privacy
   page must say.
4. **Stop retrying a refusal.** A 400 will fail every night until the code changes. Stop retrying a row after
   five refusals, show it in the admin with a filter, and keep **Send again** able to try it.

## If you get stuck

- Browse: https://github.com/dapperAuteur/invest-witus/tree/v13
- Diff for this chapter: https://github.com/dapperAuteur/invest-witus/compare/v12...v13
- Zip: https://github.com/dapperAuteur/invest-witus/archive/v13.zip
- Take the reference's files. Chapter 13 changed `src/invest_witus_site/settings.py`,
  `src/invest_witus_site/urls.py`, `pages/views.py`, `prices/views.py`, the templates `pages/_header.html` and
  `pages/_footer.html`, `pages/static/pages/site.css`, `docs/site/privacy.md`, `.env.example` and
  `tests/conftest.py`, and added the folder `src/invest_witus_site/reports/` (`apps.py`, `inbox.py`,
  `models.py`, `delivery.py`, `forms.py`, `views.py`, `urls.py`, `admin.py`, the command
  `management/commands/reports.py`, the templates `reports/report.html` and `reports/thanks.html`, and
  `migrations/0001_initial.py`) and `tests/test_ch13.py`. No package changed and nothing moved:
  `git fetch reference --tags && git checkout v13 -- src tests docs/site/privacy.md .env.example`.
- `test_the_signature_matches_one_computed_by_hand` fails: `sign` hashed `f"{timestamp}{raw}"` without the dot,
  or decoded the bytes and hashed a `str` built with `json.dumps` a second time.
- `test_the_request_carries_the_headers_and_the_signed_bytes` finds different bytes: `send` passed `json=` to
  httpx instead of `content=raw`.
- `test_the_body_leaves_out_an_empty_name_and_email_and_is_plain_ascii` fails on `isascii`: `ensure_ascii=False`.
- A test fails with `AssertionError: a test tried to reach inbox.example.test`: it set the three names itself
  without asking for the `fake` fixture, so the guard's transport from `conftest.py` is still in place.
- `test_a_retry_sends_once_and_marks_the_report_sent` sends three times: `deliver` checked `sent_at` on the row it
  was given instead of the copy it read with the lock.
- `test_the_rate_limit_counts_reports_in_the_database` lets the sixth through: the limit counts with `>` instead
  of `>=`, or runs after `create`.
- `test_signed_in_the_witus_identity_is_the_sender` finds `name="email"`: the form's `__init__` did not delete
  the field when signed in.
- The cron tests of chapter 08 fail with an extra `inbox` key: the cron adds it even with Inbox off. Guard it with
  `inbox_configured()`.
- On Vercel after the merge, a report's row reads "Failed, will retry" with a 401: the slug is not in Inbox's
  `INGEST_SOURCES` for that environment, Inbox was not redeployed after the change, or the two secrets differ.

## What we learned

- A signature is over bytes. Serialize once, sign that, send that.
- Read the receiver's code before you trust a summary of it: the schema, the limits and the answers are there,
  and a few of them change the sender.
- Saving first and sending second turns a failure into a column, and a column can be retried.
- A job that already runs every night is a queue with one worker; a button beside it is the fallback.
- A lock around a network call keeps two senders from sending twice, and a short timeout keeps the lock short.
- A limit can count rows, and an address can be counted without being kept.

## Next

Chapter 14 adds the second method, 12-1 momentum: rank your universe by its 12-month return without the last
month, hold the top few, and review it with the same engine.

## References

Django Software Foundation. (n.d.). *QuerySet API reference: select_for_update()*. Django 5.2 documentation.
Retrieved October 29, 2026, from https://docs.djangoproject.com/en/5.2/ref/models/querysets/

Encode. (n.d.). *Transports*. HTTPX. Retrieved October 29, 2026, from
https://www.python-httpx.org/advanced/transports/

Python Software Foundation. (n.d.). *hmac: Keyed-hashing for message authentication*. Python documentation.
Retrieved October 29, 2026, from https://docs.python.org/3/library/hmac.html

Vercel. (n.d.-a). *Request headers*. Vercel documentation. Retrieved October 29, 2026, from
https://vercel.com/docs/headers/request-headers

Vercel. (n.d.-b). *System environment variables*. Vercel documentation. Retrieved October 29, 2026, from
https://vercel.com/docs/environment-variables/system-environment-variables

WitUS Inbox. (n.d.). *Signed-webhook contract* [Source code documentation]. GitHub. Retrieved October 29, 2026,
from https://github.com/dapperAuteur/witus-inbox/blob/main/docs/webhook-contract.md
