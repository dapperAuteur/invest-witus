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
