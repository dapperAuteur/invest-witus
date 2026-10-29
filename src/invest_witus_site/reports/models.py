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
