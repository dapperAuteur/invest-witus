"""The app's own copy of every paper order it placed: one row per account, plan, month and symbol.

Alpaca executes; this table remembers. A paper account deleted on Alpaca's dashboard takes its
history with it (research 05), so every order the app places is written here first, with the
deterministic `client_order_id` that makes a second click or a retry the same order, and the
nightly sync copies Alpaca's status and fill back into the row and into the journal entry it
made.
"""

from datetime import datetime
from decimal import Decimal

from django.db import models

from invest_witus_site.holdings.models import MONEY_PLACES, Account
from invest_witus_site.methods.models import JournalEntry, MethodPlan

# Alpaca reports quantities "up to 9 decimal points" (its order reference, read October 29, 2026).
# The row keeps all nine; the journal keeps six, rounded down, as every share count in the app.
ALPACA_QTY_PLACES = 9
# Statuses after which "no further updates will occur for the order" (Alpaca's order lifecycle
# page). `replaced` is final for the old order; this app never replaces one.
FINAL_STATUSES = frozenset({"filled", "canceled", "expired", "rejected", "replaced"})
# Not yet sent, or sent and refused before Alpaca made an order: the row's own status.
STAGED = "staged"


def client_order_id(account_pk: int, plan_pk: int, month: str, symbol: str) -> str:
    """The same four facts always give the same id, so Alpaca and this table both see a repeat
    as the order they already have. `iw-12-3-2026-11-INDEX`: well under Alpaca's 128 characters
    (a symbol is at most 12)."""
    return f"iw-{account_pk}-{plan_pk}-{month}-{symbol}"


class PaperOrder(models.Model):
    account: models.ForeignKey[Account, Account] = models.ForeignKey(
        Account, on_delete=models.CASCADE
    )
    plan: models.ForeignKey[MethodPlan, MethodPlan] = models.ForeignKey(
        MethodPlan, on_delete=models.PROTECT
    )
    month: models.CharField[str, str] = models.CharField(max_length=7, help_text="YYYY-MM")
    symbol: models.CharField[str, str] = models.CharField(max_length=20)
    notional: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=14, decimal_places=MONEY_PLACES, help_text="The dollars the order asked for."
    )
    client_order_id: models.CharField[str, str] = models.CharField(max_length=128, unique=True)
    alpaca_id: models.CharField[str, str] = models.CharField(
        max_length=64, blank=True, default="", help_text="Alpaca's order id, once it has one."
    )
    status: models.CharField[str, str] = models.CharField(max_length=24, default=STAGED)
    filled_qty: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=20, decimal_places=ALPACA_QTY_PLACES, default=Decimal("0")
    )
    filled_avg_price: models.DecimalField[Decimal | None, Decimal | None] = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True
    )
    submitted_at: models.DateTimeField[datetime | None, datetime | None] = models.DateTimeField(
        null=True, blank=True
    )
    filled_at: models.DateTimeField[datetime | None, datetime | None] = models.DateTimeField(
        null=True, blank=True
    )
    # The last refusal, in Alpaca's words, for a row still `staged`. Never a key.
    message: models.CharField[str, str] = models.CharField(max_length=240, blank=True, default="")
    journal_entry: models.OneToOneField[JournalEntry | None, JournalEntry | None] = (
        models.OneToOneField(JournalEntry, on_delete=models.SET_NULL, null=True, blank=True)
    )
    created_at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-month", "symbol"]
        verbose_name = "paper order"
        verbose_name_plural = "paper orders"

    def __str__(self) -> str:
        return f"{self.month} {self.symbol} {self.notional} ({self.status})"

    @property
    def placed(self) -> bool:
        return bool(self.alpaca_id)

    @property
    def final(self) -> bool:
        return self.status in FINAL_STATUSES

    @classmethod
    def for_month(cls, plan: MethodPlan, month: str) -> list[PaperOrder]:
        return list(cls.objects.filter(plan=plan, month=month))

    @classmethod
    def open_orders(cls, account: Account | None = None) -> models.QuerySet[PaperOrder]:
        """Orders Alpaca has and that can still change: the sync's work list."""
        orders = cls.objects.exclude(alpaca_id="").exclude(status__in=FINAL_STATUSES)
        return orders.filter(account=account) if account is not None else orders
