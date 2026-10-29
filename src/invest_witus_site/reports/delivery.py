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
