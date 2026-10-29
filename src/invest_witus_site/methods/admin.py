"""The plans and the journal in the admin. The owner's page is where both are kept; the admin is
where a plan is ended (`active` off) until chapter 12 gives a change of plan its own form."""

from django.contrib import admin

from invest_witus_site.methods.models import JournalEntry, MethodPlan


@admin.register(MethodPlan)
class MethodPlanAdmin(admin.ModelAdmin[MethodPlan]):
    list_display = (
        "method_id",
        "account",
        "amount",
        "symbols",
        "buy_window_days",
        "started_on",
        "active",
    )
    list_editable = ("active",)
    list_filter = ("account", "active")
    readonly_fields = ("created_at",)


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin[JournalEntry]):
    list_display = ("date", "account", "action", "symbol", "amount", "shares", "note")
    list_filter = ("account", "action")
    date_hierarchy = "date"
    search_fields = ("symbol", "note")
    readonly_fields = ("created_at",)
