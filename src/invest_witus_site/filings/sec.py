"""The one way this app asks SEC EDGAR for anything: a declared User-Agent, a shared throttle,
and a pause after a refusal (chapter 16, decisions 178 and 179).

SEC's "Accessing EDGAR Data" page, read on November 10, 2026
(https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data, last reviewed
June 26, 2024) says "Current max request rate: 10 requests/second", asks callers to "declare your
user agent in request headers" (its example is a company name and an admin email) and to send
`Accept-Encoding: gzip, deflate`, and says "please moderate requests to minimize server load".
It names no penalty and no length for a block.

So every request here:
- carries `settings.SEC_USER_AGENT`, by default the app's name and address and never a person's
  email (the ecosystem rule; the SEC answered 200 to it on November 2 and 10, 2026);
- asks for gzip or deflate (httpx decodes either);
- waits its turn in `throttle`, at most `REQUESTS_PER_SECOND` (4, well under the SEC's 10) for the
  whole process;
- is not sent at all while `SecPause` says the SEC refused us: a 403 or a 429 writes that row
  for `PAUSE_MINUTES` (10, our choice: the page names no length), so every Vercel function that
  reads the database waits too, and the page says "Filings are not available right now".
"""

import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta

import httpx
from django.conf import settings
from django.utils import timezone

from invest_witus_site.filings.models import SecPause

# The seam the tests use: a `MockTransport` here and nothing leaves the process.
transport: httpx.BaseTransport | None = None
# The seams for the throttle's clock, so a test neither waits nor depends on the machine's speed.
clock: Callable[[], float] = time.monotonic
sleep: Callable[[float], None] = time.sleep

REQUESTS_PER_SECOND = 4
PAUSE_MINUTES = 10
REQUEST_TIMEOUT_SECONDS = 20.0
PAUSE_ID = 1


class SecError(Exception):
    """A request the SEC did not answer with a document. `retry_later` is True for a refusal
    (403, 429) or a pause: asking for the next symbol now would fail the same way."""

    def __init__(self, problem: str, status: int | None = None, retry_later: bool = False) -> None:
        super().__init__(problem)
        self.problem = problem
        self.status = status
        self.retry_later = retry_later


class Throttle:
    """At most `per_second` requests a second across every thread of the process: each caller
    takes the next free slot, then sleeps until it comes."""

    def __init__(self, per_second: int) -> None:
        self.interval = 1.0 / per_second
        self.lock = threading.Lock()
        self.next_at = 0.0

    def wait(self) -> None:
        with self.lock:
            now = clock()
            at = max(now, self.next_at)
            self.next_at = at + self.interval
        if at > now:
            sleep(at - now)


throttle = Throttle(REQUESTS_PER_SECOND)


def paused_until(now: datetime | None = None) -> SecPause | None:
    """The pause in force, or None."""
    now = now or timezone.now()
    return SecPause.objects.filter(pk=PAUSE_ID, until__gt=now).first()


def pause(status: int, now: datetime | None = None) -> SecPause:
    now = now or timezone.now()
    row, _ = SecPause.objects.update_or_create(
        pk=PAUSE_ID,
        defaults={
            "until": now + timedelta(minutes=PAUSE_MINUTES),
            "status": status,
            "noted_at": now,
        },
    )
    return row


def headers() -> dict[str, str]:
    return {"User-Agent": settings.SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}


def get(url: str, now: datetime | None = None) -> str:
    """One GET; the body's text, or `SecError`. A 404 is not a refusal (a company with no XBRL
    figures has no companyfacts document)."""
    held = paused_until(now)
    if held is not None:
        raise SecError(
            f"SEC EDGAR answered {held.status} at {timezone.localtime(held.noted_at):%H:%M}; "
            f"the app waits until {timezone.localtime(held.until):%H:%M %Z} before asking again",
            status=held.status,
            retry_later=True,
        )
    throttle.wait()
    try:
        with httpx.Client(transport=transport, timeout=REQUEST_TIMEOUT_SECONDS) as http:
            response = http.get(url, headers=headers())
    except httpx.HTTPError as error:
        raise SecError(f"the request failed: {type(error).__name__}") from error
    if response.status_code in (403, 429):
        pause(response.status_code, now)
        raise SecError(
            f"SEC EDGAR answered {response.status_code} (too many requests or a refused client); "
            f"the app waits {PAUSE_MINUTES} minutes before asking again",
            status=response.status_code,
            retry_later=True,
        )
    if response.status_code != 200:
        raise SecError(f"SEC EDGAR answered {response.status_code}", status=response.status_code)
    return response.text
