"""The watch lists in the admin, for completeness: the owner's page is where they are kept."""

from django.contrib import admin

from invest_witus_site.watchlist.models import WatchItem


@admin.register(WatchItem)
class WatchItemAdmin(admin.ModelAdmin[WatchItem]):
    list_display = ("symbol", "account", "note", "added_at")
    list_filter = ("account",)
    search_fields = ("symbol", "note")
    readonly_fields = ("added_at",)
