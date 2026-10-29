"""WitUS Outbox's ingest, sent with httpx: Outbox's `examples/sender.ts`, in Python.

Read from Outbox's guide and code on October 29, 2026 (`examples/INTEGRATE.md`,
`examples/README.md`, `examples/sender.ts`, `app/api/ingest/route.ts`, `lib/hmac.ts`,
`lib/ingest-sources.ts`):

- `POST` the JSON body to the ingest URL with `Content-Type: application/json`, `X-Witus-Source`,
  `X-Witus-Timestamp` and `X-Witus-Signature`: the same scheme as WitUS Inbox, in
  `invest_witus_site/signing.py`. Outbox hashes the raw text before it parses it, so the bytes
  signed are the bytes sent.
- The body: `external_ref` (1 to 255 characters), `platform` (one of Outbox's eight),
  `caption` (1 to 10,000), `media_urls` (https only, may be empty), `scheduled_at` (ISO 8601 with
  an offset) and `as_draft`. With `as_draft` true, the row lands in Outbox as a draft, nothing is
  posted, and the five-minute lead on `scheduled_at` is waived: the date is a placeholder and the
  operator picks the real one when promoting the draft in Outbox.
- Outbox is idempotent on `(source, external_ref)`: a repeat answers 200 with the existing row's
  id and its current status, and inserts nothing. That is why a retry from this app is harmless.
- Answers: 200 `{"ok":true,"id":"<uuid>","status":"draft"}`; 401 for a missing header, an unknown
  source, a bad signature or a stale timestamp, which Outbox does not tell apart; 400 for a body
  that is not JSON or not the schema; 500 for its database.

The guide says to copy `sender.ts` unchanged. This app is Python, so this module is that file's
contract, checked as chapter 13 checked Inbox: against a signature computed outside Python and
against Outbox's verification ported into the tests (`tests/test_outbox.py`).

Two things this app always does, whatever the caller asks: `as_draft` is true, so the owner
approves every post in Outbox, and the body carries no media, links or profile ids. Every body is
checked by `guard.py` before it is signed. Nothing here logs more than the source, the platform,
the `external_ref` and the HTTP status (the guide's third rule).
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import cast

import httpx
from django.conf import settings

from invest_witus_site.outbox import guard
from invest_witus_site.signing import MIN_SECRET_LENGTH, SLUG, sign, url_allowed

log = logging.getLogger(__name__)

# The seam the tests use, as in chapter 13: a `MockTransport` here and nothing leaves the process.
transport: httpx.BaseTransport | None = None

TIMEOUT_SECONDS = 5.0
# The kill switch must be exactly this, as the guide's helper checks it (`!== "true"`): "1",
# "True" or "yes" leave every trigger off.
ENABLED_VALUE = "true"
# Outbox's platform list (`lib/platforms.ts`) and the three the guide's helper uses by default.
# This app sends text only, so it offers only the default three, which need no image.
OUTBOX_PLATFORMS = (
    "twitter",
    "instagram",
    "facebook",
    "linkedin",
    "youtube",
    "bluesky",
    "tiktok",
    "pinterest",
)
DEFAULT_PLATFORMS = ("linkedin", "twitter", "bluesky")


class OutboxError(Exception):
    """Outbox, the network or this app's own checks said no. `message` is safe for the admin and
    a log: our words and a status code, never the secret, the caption or the body."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


class OutboxOff(OutboxError):
    """The kill switch is not on, or the three settings are not all set or cannot be right."""


class OutboxBlocked(OutboxError):
    """`guard.py` refused the body before it was signed. Nothing was sent; sending the same body
    again will be refused the same way, so it is not retried."""


class OutboxRefused(OutboxError):
    """A 4xx: Outbox read the request and refused it."""


class OutboxUnavailable(OutboxError):
    """No usable answer: a timeout, a dropped connection, a 5xx, or a 2xx without an id."""


@dataclass(frozen=True, slots=True)
class OutboxConfig:
    url: str
    source: str
    secret: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class Submission:
    """One draft for one platform. `body()` is the exact bytes that are signed and sent."""

    external_ref: str
    platform: str
    caption: str
    scheduled_at: datetime

    def document(self) -> dict[str, object]:
        when = self.scheduled_at.astimezone(UTC).replace(microsecond=0)
        return {
            "external_ref": self.external_ref,
            "platform": self.platform,
            "caption": self.caption,
            "media_urls": [],
            "scheduled_at": when.isoformat().replace("+00:00", "Z"),
            "as_draft": True,
        }

    def body(self) -> bytes:
        # ASCII with \u escapes, as chapter 13's Inbox body: the same bytes as bytes or as text.
        return json.dumps(self.document(), ensure_ascii=True, separators=(",", ":")).encode("ascii")


@dataclass(frozen=True, slots=True)
class Sent:
    """Outbox's answer: its row id, and the row's status there (`draft` for a new row; anything
    else means the row already existed and this send changed nothing)."""

    outbox_id: str
    record_status: str


def switched_on() -> bool:
    return str(settings.OUTBOX_TRIGGER_ENABLED) == ENABLED_VALUE


def load_config() -> OutboxConfig:
    """The kill switch and the three settings, checked, or `OutboxOff` with a sentence naming the
    problem. The sentence names variables, never their values."""
    if not switched_on():
        raise OutboxOff(f'WitUS Outbox is off: OUTBOX_TRIGGER_ENABLED is not "{ENABLED_VALUE}".')
    url = str(settings.OUTBOX_INGEST_URL)
    source = str(settings.OUTBOX_SOURCE_SLUG)
    secret = str(settings.OUTBOX_INGEST_SECRET)
    names = {"OUTBOX_INGEST_URL": url, "OUTBOX_SOURCE_SLUG": source, "OUTBOX_INGEST_SECRET": secret}
    missing = [name for name, value in names.items() if not value]
    if missing:
        raise OutboxOff(f"WitUS Outbox is off: {', '.join(missing)} not set.")
    if not url_allowed(url):
        raise OutboxOff(
            "WitUS Outbox is off: OUTBOX_INGEST_URL must be an https:// URL "
            "(http:// only for localhost)."
        )
    if not SLUG.fullmatch(source):
        raise OutboxOff(
            "WitUS Outbox is off: OUTBOX_SOURCE_SLUG must be lower-case words joined by hyphens."
        )
    if len(secret) < MIN_SECRET_LENGTH:
        raise OutboxOff(
            f"WitUS Outbox is off: OUTBOX_INGEST_SECRET is shorter than {MIN_SECRET_LENGTH} "
            "characters, which Outbox refuses."
        )
    return OutboxConfig(url=url, source=source, secret=secret)


def configured() -> bool:
    try:
        load_config()
    except OutboxOff:
        return False
    return True


def send(config: OutboxConfig, submission: Submission, timestamp: int | None = None) -> Sent:
    """Check, sign and post one draft; return Outbox's id and status for it. Every failure is one
    of the exceptions above, never an httpx error that would become a 500."""
    problems = guard.body_problems(submission.document(), guard.account_symbols())
    if problems:
        failed(config, submission, None, "blocked")
        raise OutboxBlocked("Not sent: " + " ".join(problems))
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
        failed(config, submission, None)
        raise OutboxUnavailable("Outbox did not answer in time.") from None
    except httpx.HTTPError as error:
        failed(config, submission, None)
        raise OutboxUnavailable(f"Could not reach Outbox ({type(error).__name__}).") from None
    status = response.status_code
    if status == 401:
        failed(config, submission, status)
        raise OutboxRefused(
            "Outbox answered 401: the source slug is not in its INGEST_SOURCES, the secret "
            "differs from Outbox's, or this server's clock is more than 5 minutes off. Outbox "
            "does not say which.",
            status,
        )
    if 400 <= status < 500:
        failed(config, submission, status)
        raise OutboxRefused(f"Outbox answered {status}: it refused the body.", status)
    if status >= 300:
        failed(config, submission, status)
        raise OutboxUnavailable(f"Outbox answered {status}.", status)
    sent = sent_from(response)
    if sent is None:
        failed(config, submission, status)
        raise OutboxUnavailable(f"Outbox answered {status} without an id.", status)
    log.info(
        "outbox: sent source=%s platform=%s external_ref=%s status=%s",
        config.source,
        submission.platform,
        submission.external_ref,
        status,
    )
    return sent


def sent_from(response: httpx.Response) -> Sent | None:
    try:
        body: object = json.loads(response.text)
    except json.JSONDecodeError:
        return None
    if not isinstance(body, dict):
        return None
    document = cast(dict[str, object], body)
    found = document.get("id")
    if document.get("ok") is not True or not isinstance(found, str) or not found:
        return None
    record_status = document.get("status")
    return Sent(found[:64], record_status[:16] if isinstance(record_status, str) else "")


def failed(
    config: OutboxConfig, submission: Submission, status: int | None, reason: str = ""
) -> None:
    """The one log line a failure writes: source, platform, external_ref and status."""
    log.warning(
        "outbox: failed source=%s platform=%s external_ref=%s status=%s",
        config.source,
        submission.platform,
        submission.external_ref,
        reason or (status if status is not None else "none"),
    )
