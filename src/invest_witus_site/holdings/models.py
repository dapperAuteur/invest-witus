"""Accounts, what they hold, and the dated statements that say so.

Four tables. An `Account` belongs to the owner. A `Snapshot` is one statement for one account on
one date; its `SnapshotLine`s are the numbers on it, one per symbol. A `Holding` is one row per
account and symbol: the symbol's kind and name, which do not change from statement to statement.
The numbers live on the lines, never on the holding, so history is kept and nothing is overwritten.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q

from invest_witus.holdings import Change, Position, compare
from invest_witus.money import to_money, to_shares

# Six decimal places for shares (the share step from chapter 01), two for money. `max_digits`
# counts both sides of the point: 18 and 6 allow up to 999,999,999,999 shares.
SHARE_PLACES = 6
MONEY_PLACES = 2


class Account(models.Model):
    """One account at one broker, entered by hand from its statements.

    `owner` is the Django user who manages the account in the admin: the owner's own login until
    Sign in with WitUS (chapter 07). `witus_user_id` is the WitUS user id (the `sub` claim) the
    account will be matched by after that chapter; it stays empty until then.
    """

    class Kind(models.TextChoices):
        BROKERAGE = "brokerage", "Brokerage (taxable)"
        RETIREMENT = "retirement", "Retirement"
        PAPER = "paper", "Paper (practice)"

    owner: models.ForeignKey[User, User] = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="accounts"
    )
    witus_user_id: models.CharField[str | None, str | None] = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text="Filled by Sign in with WitUS (chapter 07). Leave empty.",
    )
    name: models.CharField[str, str] = models.CharField(max_length=80)
    broker: models.CharField[str, str] = models.CharField(
        max_length=80, help_text="The broker's name as it appears on the statement."
    )
    kind: models.CharField[str, str] = models.CharField(max_length=10, choices=Kind.choices)
    currency: models.CharField[str, str] = models.CharField(
        max_length=3, default="USD", choices=[("USD", "US dollar")]
    )
    created_at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now_add=True)

    class Alpaca(models.TextChoices):
        """Which Alpaca environment the account mirrors (chapter 11). Paper is the only choice:
        live trading needs the checklist in a later chapter and separate keys, and is not here."""

        NONE = "", "Not linked"
        PAPER = "paper", "Alpaca paper"

    alpaca: models.CharField[str, str] = models.CharField(
        max_length=5,
        choices=Alpaca.choices,
        blank=True,
        default="",
        help_text="Chapter 11. Paper accounts only, one per owner.",
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "name"], name="account_name_once_per_owner"),
            # Chapter 11: a link to Alpaca's paper environment only on a paper account, and one per
            # owner, because the server holds one pair of paper keys and two linked rows would
            # count the same orders twice.
            models.CheckConstraint(
                condition=Q(alpaca="") | Q(kind="paper"),
                name="alpaca_link_on_paper_accounts_only",
                violation_error_message="Only a paper account can be linked to Alpaca paper.",
            ),
            models.UniqueConstraint(
                fields=["owner"],
                condition=Q(alpaca="paper"),
                name="one_alpaca_paper_account_per_owner",
                violation_error_message="This owner already has an account linked to Alpaca paper.",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.broker})"

    def snapshots(self) -> models.QuerySet[Snapshot]:
        """Newest first. Written as a query, not `self.snapshot_set`, so pyright can read it."""
        return Snapshot.objects.filter(account=self).order_by("-as_of")

    def latest_snapshot(self) -> Snapshot | None:
        return self.snapshots().first()

    @property
    def is_alpaca_paper(self) -> bool:
        return self.alpaca == "paper"


class Holding(models.Model):
    """One symbol in one account: the parts of a holding that do not change between statements."""

    class Kind(models.TextChoices):
        STOCK = "stock", "Stock"
        ETF = "etf", "ETF"
        MUTUAL_FUND = "mutual_fund", "Mutual fund"
        CASH = "cash", "Cash"

    account: models.ForeignKey[Account, Account] = models.ForeignKey(
        Account, on_delete=models.CASCADE
    )
    symbol: models.CharField[str, str] = models.CharField(max_length=20)
    # Blank until the owner sets it in the admin. The app never guesses a security's kind.
    kind: models.CharField[str, str] = models.CharField(
        max_length=12, choices=Kind.choices, blank=True, default=""
    )
    name: models.CharField[str, str] = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        ordering = ["account", "symbol"]
        constraints = [
            models.UniqueConstraint(fields=["account", "symbol"], name="holding_symbol_once"),
        ]

    def __str__(self) -> str:
        return f"{self.symbol} in {self.account}"


class Snapshot(models.Model):
    """One statement: an account on an as-of date. Its lines are the numbers on it."""

    account: models.ForeignKey[Account, Account] = models.ForeignKey(
        Account, on_delete=models.CASCADE
    )
    as_of: models.DateField[date, date] = models.DateField(
        help_text="The statement's as-of date, not the day you typed it in."
    )
    source: models.CharField[str, str] = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="For example: October statement PDF.",
    )
    created_at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-as_of"]
        constraints = [
            models.UniqueConstraint(fields=["account", "as_of"], name="snapshot_date_once"),
        ]

    def __str__(self) -> str:
        return f"{self.account.name} as of {self.as_of:%Y-%m-%d}"

    def lines(self) -> models.QuerySet[SnapshotLine]:
        return SnapshotLine.objects.filter(snapshot=self).order_by("symbol")

    def positions(self) -> list[Position]:
        """The lines as the library's plain values, ready for `compare`."""
        return [Position(line.symbol, line.shares, line.cost_basis) for line in self.lines()]

    def changes_since(self, earlier: Snapshot) -> list[Change]:
        """Per symbol: shares and cost basis on `earlier`, on this snapshot, and the difference."""
        return compare(earlier.positions(), self.positions())


class SnapshotLine(models.Model):
    """One symbol on one statement. Shares and money are Decimals, rounded with the library's
    rules before the database applies its own."""

    snapshot: models.ForeignKey[Snapshot, Snapshot] = models.ForeignKey(
        Snapshot, on_delete=models.CASCADE
    )
    symbol: models.CharField[str, str] = models.CharField(max_length=20)
    shares: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=18, decimal_places=SHARE_PLACES
    )
    cost_basis: models.DecimalField[Decimal | None, Decimal | None] = models.DecimalField(
        max_digits=14,
        decimal_places=MONEY_PLACES,
        null=True,
        blank=True,
        help_text="Total cost as the statement prints it; empty if not shown.",
    )
    market_value: models.DecimalField[Decimal | None, Decimal | None] = models.DecimalField(
        max_digits=14,
        decimal_places=MONEY_PLACES,
        null=True,
        blank=True,
        help_text="Value as the statement prints it, if any. No prices yet.",
    )
    notes: models.CharField[str, str] = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["symbol"]
        constraints = [
            models.UniqueConstraint(fields=["snapshot", "symbol"], name="line_symbol_once"),
        ]

    def __str__(self) -> str:
        return f"{self.symbol}: {self.shares} shares"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Normalize before the row is written: the symbol's case and spacing, the decimals'
        rounding, and the rule that a float never reaches a money field."""
        for field in ("shares", "cost_basis", "market_value"):
            value = getattr(self, field)
            if isinstance(value, float):
                raise TypeError(f"{field} must be a Decimal, not a float ({value!r})")
        self.symbol = self.symbol.strip().upper()
        self.shares = to_shares(self.shares)
        if self.cost_basis is not None:
            self.cost_basis = to_money(self.cost_basis)
        if self.market_value is not None:
            self.market_value = to_money(self.market_value)
        super().save(*args, **kwargs)
        # The account's catalog of symbols. The kind stays blank until the owner sets it.
        Holding.objects.get_or_create(account=self.snapshot.account, symbol=self.symbol)
