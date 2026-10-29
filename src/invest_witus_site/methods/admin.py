"""The plans, the journal and the monthly reviews in the admin. Chapter 12 moves ending and changing
a plan to its own form on the method page, so the plan's history columns are read-only here; a
journal line in a closed month cannot be saved (the model's `clean()`) or deleted (below); and the
reviews and their events are read-only, because the audit trail is only ever added to."""

from django.contrib import admin
from django.http import HttpRequest

from invest_witus_site.methods.models import (
    JournalEntry,
    MethodPlan,
    MonthlyReview,
    ReviewEvent,
)


@admin.register(MethodPlan)
class MethodPlanAdmin(admin.ModelAdmin[MethodPlan]):
    list_display = (
        "method_id",
        "account",
        "version",
        "amount",
        "symbols",
        "buy_window_days",
        "started_on",
        "ended_on",
        "practice_budget",
        "active",
    )
    list_editable = ("active",)
    list_filter = ("account", "active")
    readonly_fields = (
        "created_at",
        "version",
        "previous",
        "change_reason",
        "ended_on",
        "end_reason",
    )


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin[JournalEntry]):
    list_display = (
        "date",
        "account",
        "kind",
        "action",
        "symbol",
        "amount",
        "shares",
        "state",
        "tags",
        "note",
    )
    list_filter = ("account", "kind", "action", "state")
    date_hierarchy = "date"
    search_fields = ("symbol", "note", "reason", "tags")
    readonly_fields = ("created_at",)

    def has_delete_permission(self, request: HttpRequest, obj: JournalEntry | None = None) -> bool:
        if (
            obj is not None
            and obj.account_id is not None
            and MonthlyReview.is_closed(obj.account_id, obj.date)
        ):
            return False
        return super().has_delete_permission(request, obj)


class ReviewEventInline(admin.TabularInline[ReviewEvent, MonthlyReview]):
    model = ReviewEvent
    extra = 0
    can_delete = False
    readonly_fields = ("action", "text", "by", "at")

    def has_add_permission(self, request: HttpRequest, obj: MonthlyReview | None = None) -> bool:
        return False


@admin.register(MonthlyReview)
class MonthlyReviewAdmin(admin.ModelAdmin[MonthlyReview]):
    list_display = ("month", "plan", "opened_on", "closed_at")
    list_filter = ("plan__account",)
    inlines = [ReviewEventInline]

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: MonthlyReview | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: MonthlyReview | None = None) -> bool:
        return False
