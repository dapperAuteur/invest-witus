"""What the app sends to WitUS Outbox, kept here first: the owner's post drafts, one row per
platform.

The owner writes a short post in the admin ("Draft a post"): the site launch, once, or a milestone
of their choosing. It is saved, then one `SocialPost` per platform is sent to Outbox as a draft,
where the owner edits, schedules, approves or rejects it. Nothing here is posted to a social
network by this app, and nothing from an account goes into a post (`guard.py`).

Each platform's row remembers whether Outbox took it (`sent_at`, `outbox_id`, and Outbox's status
for the row), how many times it was tried, and the last failure in words, as chapter 13's rows
for Inbox do. A row Outbox has not taken is tried again by the nightly job or by "Send again".
"""

from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models

from invest_witus_site.outbox import guard
from invest_witus_site.outbox.client import DEFAULT_PLATFORMS, Submission

ERROR_LIMIT = 240
# One text for every platform, so it must fit the shortest: X counts 280 characters (Outbox
# enforces no vendor limit; its guide leaves that to the sending app).
TEXT_LIMIT = 280
# The guide's placeholder for a draft's date: a week ahead. Outbox ignores it for a draft; the
# owner picks the real time when promoting the draft there.
PLACEHOLDER_AHEAD = timedelta(days=7)
PLATFORM_CHOICES = [
    ("linkedin", "LinkedIn"),
    ("twitter", "X (Twitter)"),
    ("bluesky", "Bluesky"),
]
assert tuple(value for value, _ in PLATFORM_CHOICES) == DEFAULT_PLATFORMS


class OutboxStatus(models.TextChoices):
    PENDING = "pending", "Not tried yet"
    SENT = "sent", "In Outbox"
    FAILED = "failed", "Failed, will retry"
    OFF = "off", "Off, will retry"
    BLOCKED = "blocked", "Blocked, not sent"


# The two values compared in code, as plain strings (pyright reads a `TextChoices` member as its
# tuple; methods/models.py does the same with TRADE).
SENT = "sent"
BLOCKED = "blocked"
LAUNCH = "launch"


class SocialDraft(models.Model):
    """One post the owner wrote, for one or more platforms."""

    class Occasion(models.TextChoices):
        LAUNCH = "launch", "Invest.WitUS is live (the launch, once)"
        MILESTONE = "milestone", "A milestone you choose"

    occasion: models.CharField[str, str] = models.CharField(
        max_length=10, choices=Occasion.choices, default=Occasion.MILESTONE
    )
    text: models.CharField[str, str] = models.CharField(
        max_length=TEXT_LIMIT,
        help_text="280 characters at most. No amounts, percentages or symbols.",
    )
    created_by: models.ForeignKey[User | None, User | None] = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, editable=False
    )
    created_at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "post draft for WitUS Outbox"
        verbose_name_plural = "post drafts for WitUS Outbox"
        constraints = [
            # The launch is announced once: a second launch draft would reuse the first one's
            # `external_ref`, and Outbox would answer with the first one's rows.
            models.UniqueConstraint(
                fields=["occasion"],
                condition=models.Q(occasion=LAUNCH),
                name="outbox_one_launch_draft",
                violation_error_message="There is a launch draft already. Use a milestone.",
            )
        ]

    def __str__(self) -> str:
        return f"{SocialDraft.Occasion(self.occasion).label.split(' (')[0]} #{self.pk}"

    def clean(self) -> None:
        super().clean()
        problems = guard.text_problems("The text", self.text or "", guard.account_symbols())
        if problems:
            raise ValidationError({"text": problems})

    def ref_base(self) -> str:
        """The stable part of each platform's `external_ref`, so a resend is the same row in
        Outbox (it is idempotent on source and `external_ref`)."""
        if self.occasion == LAUNCH:
            return "site-launch"
        return f"milestone-{self.pk}"


class SocialPost(models.Model):
    """One platform's copy of a draft, and what Outbox said about it."""

    draft: models.ForeignKey[SocialDraft, SocialDraft] = models.ForeignKey(
        SocialDraft, on_delete=models.CASCADE, related_name="posts"
    )
    platform: models.CharField[str, str] = models.CharField(max_length=16, choices=PLATFORM_CHOICES)
    outbox_status: models.CharField[str, str] = models.CharField(
        max_length=8, choices=OutboxStatus.choices, default=OutboxStatus.PENDING
    )
    sent_at: models.DateTimeField[datetime | None, datetime | None] = models.DateTimeField(
        null=True, blank=True
    )
    outbox_id: models.CharField[str, str] = models.CharField(
        max_length=64, blank=True, default="", help_text="Outbox's id for the row."
    )
    # What Outbox said the row's status was: `draft` for a new row, or the existing row's status
    # when Outbox already had this `external_ref` (then nothing new was made there).
    outbox_record_status: models.CharField[str, str] = models.CharField(
        max_length=16, blank=True, default=""
    )
    attempts: models.PositiveSmallIntegerField[int, int] = models.PositiveSmallIntegerField(
        default=0
    )
    last_tried_at: models.DateTimeField[datetime | None, datetime | None] = models.DateTimeField(
        null=True, blank=True
    )
    # The last failure in our words, or why Outbox is off. Never the secret or the caption.
    last_error: models.CharField[str, str] = models.CharField(
        max_length=ERROR_LIMIT, blank=True, default=""
    )
    created_at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["draft", "platform"], name="outbox_one_post_per_platform"
            )
        ]

    def __str__(self) -> str:
        return f"{self.draft} on {self.platform}"

    def external_ref(self) -> str:
        return f"{self.draft.ref_base()}-{self.platform}"

    def submission(self, moment: datetime) -> Submission:
        return Submission(
            external_ref=self.external_ref(),
            platform=self.platform,
            caption=self.draft.text,
            scheduled_at=moment + PLACEHOLDER_AHEAD,
        )
