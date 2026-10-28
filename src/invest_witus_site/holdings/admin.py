"""Accounts, holdings and statements in the admin. This is the owner's whole back office for
entering a statement: a snapshot with its lines, typed in by hand. A CSV import is a later chapter.
"""

from django.contrib import admin

from invest_witus_site.holdings.models import Account, Holding, Snapshot, SnapshotLine


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin[Account]):
    list_display = ("name", "broker", "kind", "currency", "owner")
    list_filter = ("kind",)
    search_fields = ("name", "broker")
    readonly_fields = ("created_at",)


@admin.register(Holding)
class HoldingAdmin(admin.ModelAdmin[Holding]):
    """Rows appear on their own when a statement line names a new symbol. The owner's job here
    is to set each one's kind (stock, ETF, mutual fund, cash) and, if wanted, a name."""

    list_display = ("symbol", "account", "kind", "name")
    list_editable = ("kind", "name")
    list_filter = ("kind", "account")
    search_fields = ("symbol", "name")


class SnapshotLineInline(admin.TabularInline[SnapshotLine, Snapshot]):
    """The statement's lines, edited on the snapshot's own page as a grid."""

    model = SnapshotLine
    fields = ("symbol", "shares", "cost_basis", "market_value", "notes")
    extra = 3  # three empty rows to start; the page adds more on demand


@admin.register(Snapshot)
class SnapshotAdmin(admin.ModelAdmin[Snapshot]):
    list_display = ("as_of", "account", "source", "line_count")
    list_filter = ("account",)
    date_hierarchy = "as_of"
    readonly_fields = ("created_at",)
    inlines = (SnapshotLineInline,)

    @admin.display(description="Lines")
    def line_count(self, snapshot: Snapshot) -> int:
        return snapshot.lines().count()
