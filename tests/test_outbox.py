"""WitUS Outbox: the owner's "Draft a post", signed and sent as drafts, kept here first.

The signature against one computed by hand (openssl, outside Python) and against Outbox's own
verification, ported; the headers and the exact bytes; every body a draft with no media; the kill
switch off by default and on only for exactly "true"; the guard refusing any body field that
carries account data, before anything is signed; the owner-only gate; a 401, a 400, a 500 and a
timeout keeping the row unsent with the reason stored; a retry that sends once; Outbox's
idempotent answer for a repeated `external_ref`; the cron step, "Draft a post" and "Send again" in
the admin, the command; and no secret, signature or caption in any log line. Every answer comes
from `FakeOutbox` through httpx's `MockTransport`: nothing leaves the process, and the secret is
made up.
"""

import hashlib
import hmac
import json
import logging
import time
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path

import httpx
import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client
from django.utils import timezone
from pytest_django.fixtures import Settings

from invest_witus_site.holdings.models import Account
from invest_witus_site.outbox import client as outbox_client
from invest_witus_site.outbox import guard
from invest_witus_site.outbox.client import (
    OutboxBlocked,
    OutboxConfig,
    OutboxOff,
    Submission,
    load_config,
    send,
)
from invest_witus_site.outbox.delivery import Outcome, deliver, send_draft, send_unsent
from invest_witus_site.outbox.models import OutboxStatus, SocialDraft, SocialPost
from invest_witus_site.prices.models import DailyClose
from invest_witus_site.reports import inbox
from invest_witus_site.signing import sign
from invest_witus_site.watchlist.models import WatchItem

URL = "https://outbox.example.test/api/ingest"
SOURCE = "invest-witus"
# Made up, 34 characters: Outbox refuses a secret shorter than 32.
SECRET = "outbox-test-secret-0123456789abcdef"
CRON_SECRET = "test-only-cron-secret-0123456789"
TEXT = "Invest.WitUS is open for testing."
# The reference signature, computed outside Python with:
#   printf '%s.%s' 1761234567 '<BODY>' | openssl dgst -sha256 -hmac "$SECRET" -hex
STAMP = 1761234567
WHEN = datetime(2026, 11, 5, 12, tzinfo=UTC)
BODY = (
    b'{"external_ref":"milestone-1-linkedin","platform":"linkedin",'
    b'"caption":"Invest.WitUS is open for testing.","media_urls":[],'
    b'"scheduled_at":"2026-11-05T12:00:00Z","as_draft":true}'
)
BY_HAND = "sha256=e6e980e71bd828c0586c1fe90c526952f9818fa78298ad6e86baa68a213cebc4"
PLATFORMS = ("twitter", "instagram", "facebook", "linkedin", "youtube", "bluesky", "tiktok")


class FakeOutbox:
    """Outbox's ingest route as its code reads on October 29, 2026 (`app/api/ingest/route.ts`):
    the headers, the source, the window and the signature over the raw body (`lib/hmac.ts`,
    ported), then the schema, then idempotency on `(source, external_ref)`: a repeat answers the
    existing row's id and status. `answer` forces a status instead."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.answer: int | None = None
        self.rows: dict[str, tuple[str, str]] = {}

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.answer is not None:
            return httpx.Response(self.answer, json={"ok": False})
        source = request.headers.get("x-witus-source")
        stamp = request.headers.get("x-witus-timestamp", "")
        signature = request.headers.get("x-witus-signature", "").removeprefix("sha256=")
        raw = request.content
        if source != SOURCE or not outbox_would_verify(stamp, raw, signature):
            return httpx.Response(401, json={"ok": False})
        body = json.loads(raw)
        if not schema_ok(body):
            return httpx.Response(400, json={"ok": False})
        ref = str(body["external_ref"])
        if ref in self.rows:
            row_id, status = self.rows[ref]
            return httpx.Response(200, json={"ok": True, "id": row_id, "status": status})
        self.rows[ref] = (f"outbox-{len(self.rows) + 1}", "draft")
        return httpx.Response(200, json={"ok": True, "id": self.rows[ref][0], "status": "draft"})

    def bodies(self) -> list[dict[str, object]]:
        return [json.loads(request.content) for request in self.requests]


def outbox_would_verify(stamp: str, raw: bytes, signature: str) -> bool:
    """`verifySignature` from Outbox's `lib/hmac.ts`, in Python (the same as Inbox's)."""
    try:
        when = int(stamp)
    except ValueError:
        return False
    if abs(int(time.time()) - when) > 300:
        return False
    expected = hmac.new(SECRET.encode(), f"{stamp}.".encode() + raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def schema_ok(body: object) -> bool:
    """Outbox's `IngestPayload`, the parts this app can get wrong."""
    if not isinstance(body, dict):
        return False
    fields: dict[str, object] = body  # pyright: ignore[reportUnknownVariableType]
    ref, caption = fields.get("external_ref"), fields.get("caption")
    media = fields.get("media_urls")
    try:
        scheduled = datetime.fromisoformat(str(fields.get("scheduled_at")))
    except ValueError:
        return False
    draft = fields.get("as_draft", False)
    return (
        isinstance(ref, str)
        and 1 <= len(ref) <= 255
        and fields.get("platform") in (*PLATFORMS, "pinterest")
        and isinstance(caption, str)
        and 1 <= len(caption) <= 10_000
        and isinstance(media, list)
        and scheduled.tzinfo is not None
        and isinstance(draft, bool)
        and (draft or scheduled >= datetime.now(UTC) + timedelta(minutes=5))
    )


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> FakeOutbox:
    settings.OUTBOX_TRIGGER_ENABLED = "true"
    settings.OUTBOX_INGEST_URL = URL
    settings.OUTBOX_SOURCE_SLUG = SOURCE
    settings.OUTBOX_INGEST_SECRET = SECRET
    outbox_fake = FakeOutbox()
    monkeypatch.setattr(outbox_client, "transport", httpx.MockTransport(outbox_fake.handle))
    return outbox_fake


def time_out(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("no answer", request=request)


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_superuser("owner", "owner@example.com", "pw")


def a_draft(by: User | None, text: str = TEXT, platforms: tuple[str, ...] = ("linkedin",)):
    draft = SocialDraft.objects.create(text=text, created_by=by)
    for platform in platforms:
        SocialPost.objects.create(draft=draft, platform=platform)
    return draft


def config() -> OutboxConfig:
    return OutboxConfig(url=URL, source=SOURCE, secret=SECRET)


# --- The signature and the body -----------------------------------------------------------------


def test_the_body_and_signature_match_ones_computed_by_hand() -> None:
    submission = Submission("milestone-1-linkedin", "linkedin", TEXT, WHEN)
    assert submission.body() == BODY
    assert sign(SECRET, STAMP, BODY) == BY_HAND


def test_inbox_and_outbox_share_one_signing_function() -> None:
    assert inbox.sign is sign
    assert outbox_client.sign is sign


def test_the_signature_is_what_outbox_verifies_and_a_stale_one_is_not() -> None:
    stamp = int(time.time())
    assert outbox_would_verify(str(stamp), BODY, sign(SECRET, stamp, BODY)[7:])
    assert not outbox_would_verify(str(stamp - 301), BODY, sign(SECRET, stamp - 301, BODY)[7:])


@pytest.mark.django_db
def test_the_request_carries_the_headers_and_the_signed_bytes(fake: FakeOutbox) -> None:
    sent = send(config(), Submission("milestone-1-linkedin", "linkedin", TEXT, WHEN))
    assert (sent.outbox_id, sent.record_status) == ("outbox-1", "draft")
    request = fake.requests[0]
    assert request.headers["content-type"] == "application/json"
    assert request.headers["x-witus-source"] == SOURCE
    stamp = int(request.headers["x-witus-timestamp"])
    assert request.headers["x-witus-signature"] == sign(SECRET, stamp, request.content)
    assert request.content == BODY


@pytest.mark.django_db
def test_every_post_is_a_draft_with_no_media_and_a_placeholder_date(
    fake: FakeOutbox, owner: User
) -> None:
    draft = a_draft(owner, platforms=("linkedin", "twitter", "bluesky"))
    now = timezone.now()
    run = send_draft(draft, now)
    assert (run.checked, run.sent) == (3, 3)
    for body in fake.bodies():
        assert body["as_draft"] is True
        assert body["media_urls"] == []
        assert set(body) == guard.ALLOWED_KEYS
        assert body["scheduled_at"] == (now + timedelta(days=7)).astimezone(UTC).replace(
            microsecond=0
        ).isoformat().replace("+00:00", "Z")
    refs = [body["external_ref"] for body in fake.bodies()]
    assert refs == [f"milestone-{draft.pk}-{p}" for p in ("linkedin", "twitter", "bluesky")]


# --- The kill switch and the settings -----------------------------------------------------------


@pytest.mark.parametrize("value", ["", "1", "True", "TRUE", "yes", "on", " true", "true "])
def test_the_kill_switch_is_off_unless_exactly_true(
    settings: Settings, fake: FakeOutbox, value: str
) -> None:
    settings.OUTBOX_TRIGGER_ENABLED = value
    with pytest.raises(OutboxOff, match='OUTBOX_TRIGGER_ENABLED is not "true"'):
        load_config()


def test_the_switch_has_no_default_but_off() -> None:
    source = Path("src/invest_witus_site/settings.py").read_text(encoding="utf-8")
    assert 'OUTBOX_TRIGGER_ENABLED = os.environ.get("OUTBOX_TRIGGER_ENABLED", "")' in source
    assert "OUTBOX_TRIGGER_ENABLED=\n" in Path(".env.example").read_text(encoding="utf-8")


def test_each_setting_switches_the_client_off_with_a_reason(
    settings: Settings, fake: FakeOutbox
) -> None:
    assert load_config() == config()
    assert SECRET not in repr(load_config())
    settings.OUTBOX_INGEST_SECRET = "short"
    with pytest.raises(OutboxOff, match="shorter than 32") as off:
        load_config()
    assert "short" not in off.value.message.replace("shorter", "")
    settings.OUTBOX_INGEST_SECRET = SECRET
    settings.OUTBOX_SOURCE_SLUG = "Invest WitUS"
    with pytest.raises(OutboxOff, match="lower-case"):
        load_config()
    settings.OUTBOX_SOURCE_SLUG = SOURCE
    settings.OUTBOX_INGEST_URL = "http://outbox.example.test/api/ingest"
    with pytest.raises(OutboxOff, match="https"):
        load_config()
    settings.OUTBOX_INGEST_URL = ""
    with pytest.raises(OutboxOff, match="OUTBOX_INGEST_URL not set"):
        load_config()


@pytest.mark.django_db
def test_with_the_switch_off_a_draft_is_kept_and_nothing_is_sent(
    settings: Settings, fake: FakeOutbox, owner: User
) -> None:
    settings.OUTBOX_TRIGGER_ENABLED = ""
    draft = a_draft(owner, platforms=("linkedin", "twitter"))
    run = send_draft(draft)
    assert (run.checked, run.sent, run.failed) == (2, 0, 2)
    assert fake.requests == []
    for post in SocialPost.objects.all():
        assert post.outbox_status == OutboxStatus.OFF
        assert post.attempts == 0
        assert "OUTBOX_TRIGGER_ENABLED" in post.last_error
    assert send_unsent().stopped.startswith("WitUS Outbox is off")


# --- The guard: nothing from an account ---------------------------------------------------------


@pytest.fixture
def symbols(owner: User) -> frozenset[str]:
    account = Account.objects.create(name="Practice", broker="Example", kind="paper", owner=owner)
    WatchItem.objects.create(account=account, symbol="INDEX")
    DailyClose.objects.create(
        symbol="BONDS",
        date=date(2026, 10, 28),
        close=Decimal("10"),
        source="csv",
        fetched_at=timezone.now(),
    )
    return guard.account_symbols()


@pytest.mark.django_db
def test_the_account_symbols_come_from_the_tables(symbols: frozenset[str]) -> None:
    assert {"INDEX", "BONDS"} <= symbols


ACCOUNT_DATA = {
    "money": "Up $1,200 this month",
    "money in words": "Put 500 dollars in",
    "percentage": "Returned 12% so far",
    "share count": "Bought 40 shares",
    "cashtag": "Watching $ABC closely",
    "a watched symbol": "My INDEX plan is on track",
    "a priced symbol": "Added BONDS.",
}


@pytest.mark.django_db
@pytest.mark.parametrize("field", ["caption", "external_ref"])
@pytest.mark.parametrize("kind", sorted(ACCOUNT_DATA))
def test_any_body_field_carrying_account_data_is_refused(
    symbols: frozenset[str], field: str, kind: str
) -> None:
    document = Submission("milestone-1-linkedin", "linkedin", TEXT, WHEN).document()
    document[field] = ACCOUNT_DATA[kind]
    assert guard.body_problems(document, symbols), f"{kind} in {field} was let through"


@pytest.mark.django_db
def test_a_field_this_app_does_not_send_media_or_a_non_draft_is_refused(
    symbols: frozenset[str],
) -> None:
    clean = Submission("milestone-1-linkedin", "linkedin", TEXT, WHEN).document()
    assert guard.body_problems(clean, symbols) == []
    for extra in ({"holdings": ["INDEX"]}, {"price": 10}, {"links": ["https://example.test"]}):
        assert guard.body_problems({**clean, **extra}, symbols), extra
    assert guard.body_problems({**clean, "media_urls": ["https://example.test/chart.png"]}, [])
    assert guard.body_problems({**clean, "as_draft": False}, [])


@pytest.mark.django_db
def test_a_blocked_body_is_never_signed_or_sent(
    fake: FakeOutbox, owner: User, symbols: frozenset[str]
) -> None:
    with pytest.raises(OutboxBlocked, match="INDEX"):
        send(config(), Submission("milestone-1-linkedin", "linkedin", "INDEX day", WHEN))
    draft = a_draft(owner, text="Holding INDEX")
    assert deliver(SocialPost.objects.get(draft=draft)) == Outcome.BLOCKED
    post = SocialPost.objects.get(draft=draft)
    assert (post.outbox_status, post.sent_at) == (OutboxStatus.BLOCKED, None)
    assert send_unsent().checked == 0, "a blocked row is not retried"
    assert fake.requests == []


@pytest.mark.django_db
def test_plain_words_and_numbers_that_are_not_account_data_pass(symbols: frozenset[str]) -> None:
    text = "Invest.WitUS chapter 13 is out: 2026 is the year to practise on paper first."
    assert guard.text_problems("The text", text, symbols) == []


# --- The owner only -----------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_draft_not_written_by_the_owner_is_not_sent(
    fake: FakeOutbox, django_user_model: type[User]
) -> None:
    staff = django_user_model.objects.create_user("staff", "s@example.com", "pw", is_staff=True)
    for author in (staff, None):
        draft = a_draft(author)
        assert deliver(SocialPost.objects.get(draft=draft)) == Outcome.BLOCKED
    assert fake.requests == []
    assert "site owner" in SocialPost.objects.first().last_error  # type: ignore[union-attr]


@pytest.mark.django_db
def test_staff_who_are_not_the_owner_do_not_see_the_drafts(
    client: Client, django_user_model: type[User]
) -> None:
    staff = django_user_model.objects.create_user("staff", "s@example.com", "pw", is_staff=True)
    client.force_login(staff)
    assert client.get("/admin/outbox/socialdraft/add/").status_code == 403
    assert "WitUS Outbox" not in client.get("/admin/").content.decode()


# --- Failures, the retry, idempotency -----------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("status", "words"),
    [(401, "not in its INGEST_SOURCES"), (400, "refused the body"), (500, "Outbox answered 500")],
)
def test_a_failure_keeps_the_row_unsent_with_the_reason(
    fake: FakeOutbox, owner: User, status: int, words: str
) -> None:
    fake.answer = status
    post = SocialPost.objects.get(draft=a_draft(owner))
    deliver(post)
    assert (post.outbox_status, post.sent_at, post.attempts) == (OutboxStatus.FAILED, None, 1)
    assert words in post.last_error


@pytest.mark.django_db
def test_a_retry_sends_once_and_marks_the_row_sent(fake: FakeOutbox, owner: User) -> None:
    fake.answer = 500
    post = SocialPost.objects.get(draft=a_draft(owner))
    assert deliver(post) == Outcome.UNAVAILABLE
    fake.answer = None
    run = send_unsent()
    assert (run.checked, run.sent) == (1, 1)
    post.refresh_from_db()
    assert (post.outbox_status, post.outbox_id, post.attempts) == (OutboxStatus.SENT, "outbox-1", 2)
    assert post.last_error == ""
    assert deliver(post) == Outcome.ALREADY_SENT
    assert send_unsent().checked == 0
    assert len(fake.requests) == 2, "sent once after the failure, and never again"


@pytest.mark.django_db
def test_outbox_answers_a_repeated_ref_with_the_row_it_has(fake: FakeOutbox, owner: User) -> None:
    fake.rows["milestone-7-linkedin"] = ("outbox-existing", "posted")
    draft = SocialDraft.objects.create(pk=7, text=TEXT, created_by=owner)
    post = SocialPost.objects.create(draft=draft, platform="linkedin")
    assert deliver(post) == Outcome.SENT
    assert (post.outbox_id, post.outbox_record_status) == ("outbox-existing", "posted")


@pytest.mark.django_db
def test_a_timeout_stops_the_nightly_run_and_a_refusal_does_not(
    fake: FakeOutbox, owner: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    a_draft(owner, platforms=("linkedin", "twitter", "bluesky"))
    fake.answer = 400
    run = send_unsent()
    assert (run.checked, run.failed, run.stopped) == (3, 3, "")
    monkeypatch.setattr(outbox_client, "transport", httpx.MockTransport(time_out))
    run = send_unsent()
    assert (run.checked, run.failed, run.stopped) == (1, 1, "Outbox did not answer in time.")


@pytest.mark.django_db
def test_the_nightly_cron_sends_what_outbox_has_not_taken(
    client: Client, settings: Settings, fake: FakeOutbox, owner: User, tmp_path: Path
) -> None:
    settings.CRON_SECRET = CRON_SECRET
    settings.PRICES_CSV_DIR = tmp_path
    a_draft(owner)
    bearer = {"Authorization": f"Bearer {CRON_SECRET}"}
    response = client.get("/api/cron/pull-prices/", headers=bearer)
    assert response.json()["outbox"] == {"checked": 1, "sent": 1, "failed": 0, "stopped": ""}
    settings.OUTBOX_TRIGGER_ENABLED = ""
    assert "outbox" not in client.get("/api/cron/pull-prices/", headers=bearer).json()


# --- The admin and the command ------------------------------------------------------------------


@pytest.mark.django_db
def test_draft_a_post_in_the_admin_sends_one_draft_per_platform(
    client: Client, owner: User, fake: FakeOutbox
) -> None:
    client.force_login(owner)
    listing = client.get("/admin/outbox/socialdraft/").content.decode()
    assert "Draft a post" in listing
    response = client.post(
        "/admin/outbox/socialdraft/add/",
        {
            "occasion": "milestone",
            "text": TEXT,
            "platforms": ["linkedin", "bluesky"],
            "posts-TOTAL_FORMS": "0",
            "posts-INITIAL_FORMS": "0",
        },
        follow=True,
    )
    assert "Outbox: 2 of 2 sent." in response.content.decode()
    draft = SocialDraft.objects.get()
    assert draft.created_by == owner
    assert [body["platform"] for body in fake.bodies()] == ["linkedin", "bluesky"]
    assert {p.outbox_status for p in SocialPost.objects.all()} == {OutboxStatus.SENT}


@pytest.mark.django_db
def test_the_admin_refuses_a_text_with_account_data(
    client: Client, owner: User, fake: FakeOutbox, symbols: frozenset[str]
) -> None:
    client.force_login(owner)
    response = client.post(
        "/admin/outbox/socialdraft/add/",
        {
            "occasion": "milestone",
            "text": "My INDEX plan is up 4%",
            "platforms": ["linkedin"],
            "posts-TOTAL_FORMS": "0",
            "posts-INITIAL_FORMS": "0",
        },
    )
    page = response.content.decode()
    assert response.status_code == 200
    assert "has a percentage" in page and "names INDEX" in page
    assert not SocialDraft.objects.exists()
    assert fake.requests == []


@pytest.mark.django_db
def test_the_launch_is_drafted_once(client: Client, owner: User, fake: FakeOutbox) -> None:
    client.force_login(owner)
    data = {
        "occasion": "launch",
        "text": "Invest.WitUS is live at invest.witus.online.",
        "platforms": ["linkedin"],
        "posts-TOTAL_FORMS": "0",
        "posts-INITIAL_FORMS": "0",
    }
    client.post("/admin/outbox/socialdraft/add/", data)
    assert fake.bodies()[0]["external_ref"] == "site-launch-linkedin"
    second = client.post("/admin/outbox/socialdraft/add/", data)
    assert "There is a launch draft already" in second.content.decode()
    assert SocialDraft.objects.count() == 1


@pytest.mark.django_db
def test_send_again_in_the_admin_sends_the_selected_drafts(
    client: Client, owner: User, fake: FakeOutbox
) -> None:
    client.force_login(owner)
    fake.answer = 500
    waiting = a_draft(owner, platforms=("linkedin", "twitter"))
    send_draft(waiting)
    fake.answer = None
    response = client.post(
        "/admin/outbox/socialdraft/",
        {"action": "send_selected_again", "_selected_action": [waiting.pk]},
        follow=True,
    )
    assert "Outbox: 2 of 2 sent." in response.content.decode()
    assert set(SocialPost.objects.values_list("outbox_status", flat=True)) == {OutboxStatus.SENT}


@pytest.mark.django_db
def test_the_command_sends_and_says_when_outbox_is_off(
    settings: Settings, fake: FakeOutbox, owner: User
) -> None:
    a_draft(owner)
    out = StringIO()
    call_command("send_outbox", stdout=out)
    assert "checked 1, sent 1, failed 0." in out.getvalue()
    settings.OUTBOX_TRIGGER_ENABLED = "no"
    out = StringIO()
    call_command("send_outbox", stdout=out)
    assert "Stopped: WitUS Outbox is off" in out.getvalue()


@pytest.mark.django_db
def test_no_secret_signature_or_caption_reaches_a_log(
    fake: FakeOutbox, owner: User, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    draft = a_draft(owner)
    send_draft(draft)
    fake.answer = 401
    send_draft(a_draft(owner, text="A second milestone note"))
    logged = caplog.text
    ref = f"milestone-{draft.pk}-linkedin"
    assert f"outbox: sent source={SOURCE} platform=linkedin external_ref={ref} status=200" in logged
    assert "status=401" in logged
    for secret_thing in (SECRET, TEXT, "A second milestone note"):
        assert secret_thing not in logged
    for request in fake.requests:
        assert request.headers["x-witus-signature"].removeprefix("sha256=") not in logged
