"""The paper orders in the admin, read-only: Alpaca's answers are copied in by the app, never
typed, so a hand edit could only make the row disagree with Alpaca."""

from django.contrib import admin
from django.http import HttpRequest

from invest_witus_site.paper.models import PaperOrder


@admin.register(PaperOrder)
class PaperOrderAdmin(admin.ModelAdmin[PaperOrder]):
    list_display = ("month", "symbol", "notional", "status", "filled_qty", "account", "alpaca_id")
    list_filter = ("account", "status")
    search_fields = ("client_order_id", "alpaca_id", "symbol")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: PaperOrder | None = None) -> bool:
        return False
