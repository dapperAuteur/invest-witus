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
