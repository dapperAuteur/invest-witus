"""The stored closes, read in the admin: what the nightly pull wrote, by symbol and day."""

from django.contrib import admin

from invest_witus_site.prices.models import Backfill, DailyClose, ManualRun, SymbolProfile


@admin.register(DailyClose)
class DailyCloseAdmin(admin.ModelAdmin[DailyClose]):
    """Rows come from the pull. The owner can read them here, filter by source, and delete a
    row to make the next run fetch it again."""

    list_display = ("symbol", "date", "close", "adj_close", "source", "fetched_at")
    list_filter = ("source",)
    search_fields = ("symbol",)
    date_hierarchy = "date"
    ordering = ("symbol", "-date")
    readonly_fields = ("fetched_at",)


@admin.register(Backfill)
class BackfillAdmin(admin.ModelAdmin[Backfill]):
    """Which symbols have had their first two years of closes. Delete a row to ask for them
    again on the next pull."""

    list_display = ("symbol", "since", "done_at")
    search_fields = ("symbol",)
    readonly_fields = ("since", "done_at")


@admin.register(ManualRun)
class ManualRunAdmin(admin.ModelAdmin[ManualRun]):
    """When each owner button last ran. Delete a row to lift its ten-minute guard."""

    list_display = ("kind", "key", "ran_at")
    list_filter = ("kind",)
    search_fields = ("key",)
    readonly_fields = ("kind", "key", "ran_at")


@admin.register(SymbolProfile)
class SymbolProfileAdmin(admin.ModelAdmin[SymbolProfile]):
    """What the vendor says each symbol is (decision 150). Delete a row to fetch it again on the
    next pull."""

    list_display = ("symbol", "name", "exchange_code", "source", "fetched_at")
    search_fields = ("symbol", "name")
    readonly_fields = ("fetched_at",)
