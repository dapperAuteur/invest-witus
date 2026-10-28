"""The waitlist in the admin: a list to read, search and approve from. Owner only."""

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from invest_witus_site.pages.models import WaitlistEntry


@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(admin.ModelAdmin[WaitlistEntry]):
    list_display = ("email", "name", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("email", "name")
    ordering = ("created_at",)
    # `created_at` is set on insert (auto_now_add); the form shows it and never edits it.
    readonly_fields = ("created_at",)
    actions = ("approve",)

    @admin.action(description="Approve the selected entries")
    def approve(self, request: HttpRequest, queryset: QuerySet[WaitlistEntry]) -> None:
        """One UPDATE for every selected row, then a note at the top of the list."""
        count = queryset.update(status=WaitlistEntry.Status.APPROVED)
        noun = "entry" if count == 1 else "entries"
        self.message_user(request, f"{count} waitlist {noun} approved.")
