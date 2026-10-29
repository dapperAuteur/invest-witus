"""Accounts, holdings and statements in the admin. This is the owner's whole back office for
entering a statement: a snapshot with its lines, typed in by hand. A CSV import is a later chapter.
"""

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import URLPattern, path, reverse
from django.utils.html import format_html

from invest_witus_site.holdings.models import Account, Holding, Snapshot, SnapshotLine
from invest_witus_site.prices.splits import split_notes


def pick(
    snapshots: list[Snapshot], chosen: str | None, default: Snapshot | None
) -> Snapshot | None:
    """The snapshot whose id was chosen in the form, or the default when none (or nonsense) was."""
    for snapshot in snapshots:
        if str(snapshot.pk) == chosen:
            return snapshot
    return default


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin[Account]):
    list_display = ("name", "broker", "kind", "alpaca", "currency", "owner", "statements")
    list_filter = ("kind",)
    search_fields = ("name", "broker")
    readonly_fields = ("created_at",)

    def get_urls(self) -> list[URLPattern]:
        """One page of our own under the account's admin URLs. `admin_view` wraps it in the
        same login and staff checks every built-in admin page gets."""
        statements = path(
            "<int:pk>/statements/",
            self.admin_site.admin_view(self.statements_view),
            name="holdings_account_statements",
        )
        return [statements, *super().get_urls()]

    @admin.display(description="Statements")
    def statements(self, account: Account) -> str:
        url = reverse("admin:holdings_account_statements", args=[account.pk])
        count = account.snapshots().count()
        return format_html('<a href="{}">{} statement{}</a>', url, count, "" if count == 1 else "s")

    def statements_view(self, request: HttpRequest, pk: int) -> HttpResponse:
        """The account's statements by date, and the change between any two of them.

        With no choice made, the two newest are compared. Whichever two are chosen, the earlier
        date is "from" and the later is "to". A symbol with a stored split between the two dates
        gets a note row under it (2026-10-29); the statements are not changed.
        """
        account = get_object_or_404(Account, pk=pk)
        if not self.has_view_permission(request, account):
            raise PermissionDenied
        snapshots = list(account.snapshots())  # newest first
        newest = snapshots[0] if snapshots else None
        second = snapshots[1] if len(snapshots) > 1 else None
        earlier = pick(snapshots, request.GET.get("earlier"), second)
        later = pick(snapshots, request.GET.get("later"), newest)
        pair: tuple[Snapshot, Snapshot] | None = None
        if earlier is not None and later is not None:
            pair = (earlier, later) if earlier.as_of <= later.as_of else (later, earlier)
        changes = pair[1].changes_since(pair[0]) if pair else []
        context = {
            **self.admin_site.each_context(request),
            "title": f"Statements for {account}",
            "account": account,
            "snapshots": snapshots,
            "pair": pair,
            "changes": changes,
            # A stored split between the two dates, as a note under the symbol (decision 138).
            "change_rows": split_notes(changes, pair[0].as_of, pair[1].as_of) if pair else [],
        }
        return TemplateResponse(request, "admin/holdings/account/snapshots.html", context)


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
