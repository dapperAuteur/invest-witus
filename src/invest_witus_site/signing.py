"""The WitUS signed-webhook scheme, shared by the WitUS Inbox client and the WitUS Outbox client.

Both receivers verify the same thing, read from their code on October 29, 2026 (`lib/hmac.ts` in
witus-inbox and in witus-outbox, the same function in each): the `X-Witus-Signature` header is
`sha256=` and the hex HMAC-SHA256 of `"{timestamp}.{raw body}"` under the source's secret, the
timestamp is unix seconds and is refused more than 300 seconds from the receiver's clock either
way, and a source's secret shorter than 32 characters is refused (each reads `INGEST_SOURCES`
with the same parser, which then drops the whole list). Chapter 13 wrote this inside
`reports/inbox.py`; it moved here when the Outbox client arrived, so the two cannot drift.

Nothing here logs anything, and nothing keeps a signature: a retry signs again with a new
timestamp, since a stored one is worthless five minutes later.
"""

import hashlib
import hmac
import re
from urllib.parse import urlsplit

MIN_SECRET_LENGTH = 32
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1"})


def sign(secret: str, timestamp: int, raw: bytes) -> str:
    """The header value: `sha256=` and the hex HMAC-SHA256 of `"{timestamp}.{raw}"`. The dot is
    literal, and `raw` is used as bytes, so nothing is decoded or re-encoded on the way."""
    message = f"{timestamp}.".encode("ascii") + raw
    digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def url_allowed(url: str) -> bool:
    """An https:// URL with a host, or http:// to this machine for a receiver run on a laptop."""
    parts = urlsplit(url)
    local = parts.scheme == "http" and parts.hostname in LOCAL_HOSTS
    return bool(parts.scheme == "https" and parts.hostname) or local
