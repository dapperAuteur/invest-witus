"""Sending `SocialPost` rows to WitUS Outbox: a new draft's rows now, or every unsent row later.

Chapter 13's order: the row is already saved, then it is sent, then the answer is written onto the
row, under a `select_for_update` lock so the nightly job and a click on "Send again" at the same
moment send it once. There is no `after()` on Vercel's Python runtime, so "now" is inline with a
5-second timeout and "later" is the nightly cron route and the admin's button.

The guide says the sender does not retry and Outbox owns reconciliation. That is about posting to
the social networks, which Outbox does after the owner approves a draft. This retry covers only a
draft that never reached Outbox (it was down, unregistered or switched off), and it is safe
because Outbox answers a repeated `external_ref` with the row it already has.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from django.db import transaction
from django.utils import timezone

from invest_witus_site.outbox.client import (
    OutboxBlocked,
    OutboxError,
    OutboxOff,
    OutboxRefused,
    load_config,
    send,
)
from invest_witus_site.outbox.models import (
    BLOCKED,
    ERROR_LIMIT,
    OutboxStatus,
    SocialDraft,
    SocialPost,
)

# At most this many rows per nightly run, as chapter 13's: each may wait out a 5-second timeout.
BATCH = 25
OWNER_ONLY = (
    "Not sent: only drafts written by the site owner (a superuser) go to Outbox, as the guide's "
    "owner-only gate requires."
)


class Outcome(StrEnum):
    SENT = "sent"
    ALREADY_SENT = "already sent"
    REFUSED = "refused"
    UNAVAILABLE = "unavailable"
    OFF = "off"
    BLOCKED = "blocked"


def deliver(post: SocialPost, now: datetime | None = None) -> Outcome:
    """Send one saved row and record the answer on it. Returns what happened; raises nothing."""
    moment = now or timezone.now()
    with transaction.atomic():
        locked = (
            SocialPost.objects.select_related("draft", "draft__created_by")
            .select_for_update(of=("self",))
            .get(pk=post.pk)
        )
        if locked.sent_at is not None:
            outcome = Outcome.ALREADY_SENT
        elif locked.outbox_status == BLOCKED:
            outcome = Outcome.BLOCKED
        else:
            outcome = attempt(locked, moment)
            locked.save()
    post.refresh_from_db()
    return outcome


def attempt(post: SocialPost, moment: datetime) -> Outcome:
    # The guide's gates, in its order: the kill switch, then the owner only. (Its third, a
    # per-user opt-in, waits for other users, which wait for the legal gate in plans/38.)
    try:
        config = load_config()
    except OutboxOff as off:
        post.outbox_status = OutboxStatus.OFF
        post.last_error = off.message[:ERROR_LIMIT]
        return Outcome.OFF
    author = post.draft.created_by
    if author is None or not author.is_superuser:
        post.outbox_status = OutboxStatus.BLOCKED
        post.last_error = OWNER_ONLY[:ERROR_LIMIT]
        return Outcome.BLOCKED
    post.attempts += 1
    post.last_tried_at = moment
    try:
        sent = send(config, post.submission(moment), int(moment.timestamp()))
    except OutboxBlocked as blocked:
        post.outbox_status = OutboxStatus.BLOCKED
        post.last_error = blocked.message[:ERROR_LIMIT]
        return Outcome.BLOCKED
    except OutboxError as error:
        post.outbox_status = OutboxStatus.FAILED
        post.last_error = error.message[:ERROR_LIMIT]
        return Outcome.REFUSED if isinstance(error, OutboxRefused) else Outcome.UNAVAILABLE
    post.outbox_status = OutboxStatus.SENT
    post.sent_at = moment
    post.outbox_id = sent.outbox_id
    post.outbox_record_status = sent.record_status
    post.last_error = ""
    return Outcome.SENT


@dataclass
class DeliveryRun:
    """What one pass did, for the cron's JSON, the admin's message and the command's output."""

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


def run_over(posts: Iterable[SocialPost], now: datetime | None = None) -> DeliveryRun:
    """Try each row once. A timeout or a 5xx stops the run, since the next row would wait out the
    same timeout; a refusal, a block or Outbox off costs no wait, so the rest go on and each row
    records its own reason."""
    run = DeliveryRun()
    for post in posts:
        run.checked += 1
        outcome = deliver(post, now)
        if outcome is Outcome.SENT:
            run.sent += 1
        if outcome in (Outcome.SENT, Outcome.ALREADY_SENT):
            continue
        run.failed += 1
        run.errors.append(f"{post}: {post.last_error}")
        if outcome is Outcome.UNAVAILABLE:
            run.stopped = post.last_error
            break
    return run


def send_draft(draft: SocialDraft, now: datetime | None = None) -> DeliveryRun:
    """A draft's rows that Outbox has not taken: right after it is saved, and on "Send again"."""
    posts = SocialPost.objects.filter(draft=draft, sent_at__isnull=True)
    posts = posts.exclude(outbox_status=BLOCKED).select_related("draft").order_by("pk")
    return run_over(list(posts), now)


def unsent() -> list[SocialPost]:
    """Every row Outbox has not taken and that may be sent, oldest first."""
    posts = SocialPost.objects.filter(sent_at__isnull=True).exclude(
        outbox_status=OutboxStatus.BLOCKED
    )
    return list(posts.select_related("draft").order_by("created_at", "pk")[:BATCH])


def send_unsent(now: datetime | None = None) -> DeliveryRun:
    """The nightly step. Outbox off sends nothing and says why."""
    try:
        load_config()
    except OutboxOff as off:
        return DeliveryRun(stopped=off.message)
    return run_over(unsent(), now)
