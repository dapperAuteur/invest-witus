"""The method an account runs, and the journal the review reads: two tables, both thin.

A `MethodPlan` is chapter 03's `Plan` as a row: the method's id, the amount, the buy window, the
symbols and the start date, for one account. The method's rules are NOT in the row. They come from
the TOML file that ships in `invest_witus.methods` through `load_method(method_id)` at request
time, so a rule's text or lesson link changes with the package and no row goes stale, and a rule
without a published lesson reads "lesson coming" because the file says so, never because a column
was left empty. A `JournalEntry` is chapter 03's `Entry` as a row: one buy or sell, with the
shares if known and a note. Both convert to the chapter 03 values (`to_plan`, `to_entry`), so
`adherence.review.review` runs on the web exactly as it ran on the command line.

Chapter 12 turns the journal into a logbook and the plan into a history. An entry has a kind: a
trade (buy or sell, as before), a hold or a skip, each of the last two with a required reason; any
entry may carry a reason, a state of mind from a short fixed list, and tags. A plan changes by
becoming a new row, a *version*, that points at the one it replaced, so every month is judged by
the numbers in force that month. And each month whose window has closed gets a `MonthlyReview`,
closed by the owner with a short written review; a closed month's entries are read-only until the
review is reopened with a reason, and every close and reopen is kept as a `ReviewEvent`.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from invest_witus.adherence.journal import Action, Entry
from invest_witus.adherence.plan import Plan
from invest_witus.methods.rulebook import Method, UnknownMethodError, load_method
from invest_witus.money import to_money, to_shares
from invest_witus_site.holdings.models import MONEY_PLACES, SHARE_PLACES, Account
from invest_witus_site.watchlist.models import normalize_symbol, parse_symbols, validate_symbol

# Chapter 03's rule for a plan file, kept here for the form and `full_clean`: a buy window is a
# day of the month that every month has.
MIN_WINDOW_DAYS = 1
MAX_WINDOW_DAYS = 28
# The smallest amount a plan or an entry can carry: one cent. The form says so beside the box.
ONE_CENT = Decimal("0.01")


def validate_method_id(value: str) -> None:
    """The id must name a rules file the package ships. Never a free text: a plan for a method
    that has no rules could not be reviewed."""
    try:
        load_method(value)
    except UnknownMethodError:
        raise ValidationError(f"unknown method {value!r}") from None


def validate_symbol_list(value: str) -> None:
    """The stored list is symbols separated by spaces, each inside chapter 09's rule."""
    parsed = parse_symbols(value)
    if parsed.refused:
        reasons = "; ".join(f"{token} ({reason})" for token, reason in parsed.refused)
        raise ValidationError(f"Not a symbol: {reasons}.")
    if not parsed.symbols:
        raise ValidationError("Name at least one symbol.")


def join_symbols(text: str) -> str:
    """The list as it is stored: each symbol normalized, once, in the order typed, joined by
    single spaces. A refused token raises, as `normalize_symbol` does, so no caller stores one."""
    parsed = parse_symbols(text)
    if parsed.refused:
        token, reason = parsed.refused[0]
        raise ValueError(f"{token}: {reason}")
    if not parsed.symbols:
        raise ValueError("empty")
    return " ".join(parsed.symbols)


class MethodPlan(models.Model):
    """One account running one method with the person's own numbers. At most one is active per
    account (a partial unique constraint); an ended plan stays as history with `active` off.

    Chapter 12: a row is one *version* of a plan. Changing the amount, the window or the symbols
    makes a new row that points at the old one through `previous`, starts on the first day of a
    month, and becomes the active row; the old row keeps its numbers, gets `ended_on`, and goes
    on judging the months it was in force. Ending a plan sets `ended_on` and `end_reason`."""

    account: models.ForeignKey[Account, Account] = models.ForeignKey(
        Account, on_delete=models.CASCADE
    )
    method_id: models.CharField[str, str] = models.CharField(
        max_length=40,
        validators=[validate_method_id],
        help_text="The id of a rules file the package ships, such as index-dca.",
    )
    amount: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=14,
        decimal_places=MONEY_PLACES,
        validators=[MinValueValidator(ONE_CENT)],
        help_text="What the method buys each time.",
    )
    buy_window_days: models.PositiveSmallIntegerField[int, int] = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(MIN_WINDOW_DAYS)],
        help_text="Buy within the first N days of each month, 1 to 28.",
    )
    symbols: models.CharField[str, str] = models.CharField(
        max_length=200,
        validators=[validate_symbol_list],
        help_text="The fund or funds the plan names, separated by spaces.",
    )
    started_on: models.DateField[date, date] = models.DateField(
        help_text="The plan's first month; earlier trades are not reviewed."
    )
    active: models.BooleanField[bool, bool] = models.BooleanField(default=True)
    created_at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now_add=True)
    # Chapter 11: the practice money the plan may spend, kept by the app. Alpaca's paper balance
    # cannot be set (research 05), so the plan's budget is this number, not Alpaca's cash.
    practice_budget: models.DecimalField[Decimal | None, Decimal | None] = models.DecimalField(
        max_digits=14,
        decimal_places=MONEY_PLACES,
        null=True,
        blank=True,
        validators=[MinValueValidator(ONE_CENT)],
        help_text="Practice money this plan may spend on a paper account. Empty: not set.",
    )
    # Chapter 12: the plan's history. Every new column has a database default (`db_default`) as
    # well as Django's, so a row written by the previous release's code, which does not know the
    # column, is still valid while the migration workflow runs.
    version: models.PositiveSmallIntegerField[int, int] = models.PositiveSmallIntegerField(
        default=1, db_default=1, help_text="1 for the plan as started; one more for each change."
    )
    previous: models.OneToOneField[MethodPlan | None, MethodPlan | None] = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="next_version",
        help_text="The version this one replaced.",
    )
    change_reason: models.TextField[str, str] = models.TextField(
        blank=True, default="", db_default="", help_text="Why this version replaced the last."
    )
    ended_on: models.DateField[date | None, date | None] = models.DateField(
        null=True, blank=True, help_text="The last day this version was in force."
    )
    end_reason: models.TextField[str, str] = models.TextField(
        blank=True, default="", db_default="", help_text="Why the plan was ended."
    )

    class Meta:
        ordering = ["account", "-started_on", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["account"],
                condition=Q(active=True),
                name="one_active_plan_per_account",
            ),
            models.CheckConstraint(
                condition=Q(buy_window_days__gte=MIN_WINDOW_DAYS)
                & Q(buy_window_days__lte=MAX_WINDOW_DAYS),
                name="buy_window_between_1_and_28",
            ),
        ]
        verbose_name = "method plan"
        verbose_name_plural = "method plans"

    def __str__(self) -> str:
        return f"{self.method_id} on {self.account}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Normalize before the row is written, as every table in this app does: the amount to
        cents, the symbols through chapter 09's rule, a float refused, an unknown method refused."""
        for field in ("amount", "practice_budget"):
            if isinstance(getattr(self, field), float):
                raise TypeError(f"{field} must be a Decimal, not a float")
        validate_method_id(self.method_id)
        self.amount = to_money(self.amount)
        if self.practice_budget is not None:
            self.practice_budget = to_money(self.practice_budget)
        self.symbols = join_symbols(self.symbols)
        super().save(*args, **kwargs)

    @classmethod
    def active_for(cls, account: Account) -> MethodPlan | None:
        return cls.objects.filter(account=account, active=True).first()

    def method(self) -> Method:
        """The rules, read from the package now, never copied into the row."""
        return load_method(self.method_id)

    def symbol_list(self) -> list[str]:
        return self.symbols.split()

    def to_plan(self) -> Plan:
        """Chapter 03's `Plan`, so `review` runs unchanged."""
        return Plan(
            method=self.method_id,
            start=self.started_on,
            amount=self.amount,
            symbols=frozenset(self.symbol_list()),
            buy_window_days=self.buy_window_days,
        )

    def versions(self) -> list[MethodPlan]:
        """Every version up to this one, oldest first, by following `previous` back."""
        chain: list[MethodPlan] = [self]
        while chain[-1].previous is not None:
            chain.append(chain[-1].previous)
        return chain[::-1]

    def latest_version(self) -> MethodPlan:
        """The newest version of the plan this row belongs to, by following the chain forward."""
        latest = self
        while (following := MethodPlan.objects.filter(previous=latest).first()) is not None:
            latest = following
        return latest

    def chain_start(self) -> date:
        """The first day of the first version: where the plan's practice budget began."""
        return self.versions()[0].started_on

    def in_force(self, day: date) -> MethodPlan:
        """The version that judges `day`: the newest whose span has begun, else the first one
        (the plan has not started yet)."""
        spans = version_spans(self.versions())
        begun = [span.plan for span in spans if span.first <= day]
        return begun[-1] if begun else (spans[0].plan if spans else self)


@dataclass(frozen=True, slots=True)
class Span:
    """One version and the days it judges: from its start through `last`, or open-ended."""

    plan: MethodPlan
    first: date
    last: date | None


def version_spans(versions: list[MethodPlan]) -> list[Span]:
    """Each version runs from its start to the day before the next version starts; the newest
    runs to its `ended_on`, or on. A version replaced before it started (a change scheduled for
    next month, then changed again) has no days, and is left out."""
    spans: list[Span] = []
    for index, version in enumerate(versions):
        if index + 1 < len(versions):
            last: date | None = versions[index + 1].started_on - timedelta(days=1)
        else:
            last = version.ended_on
        if last is None or last >= version.started_on:
            spans.append(Span(version, version.started_on, last))
    return spans


# The choices for an entry's action come from chapter 03's enum, so the two cannot drift: a value
# the review does not know cannot be stored.
ACTION_CHOICES = [(action.value, action.value.capitalize()) for action in Action]

# Chapter 12: what an entry is. A trade is chapter 10's row (a buy or a sell); a hold and a skip
# are decisions not to trade, and each needs a reason. Plain strings, not `TextChoices`, so the
# constants read as strings everywhere (chapter 11's note on pyright and choices).
TRADE = "trade"
HOLD = "hold"
SKIP = "skip"
KIND_CHOICES = [(TRADE, "Trade (a buy or a sell)"), (HOLD, "Hold"), (SKIP, "Skip")]
DECISIONS = frozenset({HOLD, SKIP})
# The state of mind an entry may record: a short fixed list, chosen in decisions row 104. Empty
# means not recorded. Each word describes the person at the moment of the entry, never the market.
STATE_CHOICES = [
    ("", "Not recorded"),
    ("calm", "Calm"),
    ("focused", "Focused"),
    ("confident", "Confident"),
    ("unsure", "Unsure"),
    ("stressed", "Stressed"),
    ("rushed", "Rushed"),
]
# Tags: up to five short words of the owner's own, lower case, letters, digits and hyphens.
MAX_TAGS = 5
TAG = re.compile(r"[a-z0-9][a-z0-9-]{0,23}")
REASON_MAX_LENGTH = 1000


def parse_tags(text: str) -> list[str]:
    """`"Late, news  late"` becomes `["late", "news"]`, or a `ValueError` naming the problem."""
    tags: list[str] = []
    for token in text.replace(",", " ").lower().split():
        if TAG.fullmatch(token) is None:
            raise ValueError(
                f"{token!r} is not a tag: letters, digits and hyphens, 24 characters at most"
            )
        if token not in tags:
            tags.append(token)
    if len(tags) > MAX_TAGS:
        raise ValueError(f"{len(tags)} tags; the most is {MAX_TAGS}")
    return tags


def validate_tags(value: str) -> None:
    try:
        parse_tags(value)
    except ValueError as error:
        raise ValidationError(str(error)) from None


def month_of(day: date) -> str:
    return f"{day.year}-{day.month:02d}"


class JournalEntry(models.Model):
    """One line of the logbook. Chapter 10's row was a trade the person logged by hand: the day,
    buy or sell, the symbol, the money, and the shares if the confirmation showed them. Chapter 12
    adds the kind (a hold or a skip is a decision with a reason, and has no amount), the reason,
    the state of mind and the tags."""

    account: models.ForeignKey[Account, Account] = models.ForeignKey(
        Account, on_delete=models.CASCADE
    )
    date: models.DateField[date, date] = models.DateField(help_text="The day it happened.")
    kind: models.CharField[str, str] = models.CharField(
        max_length=5, choices=KIND_CHOICES, default=TRADE, db_default=TRADE
    )
    action: models.CharField[str, str] = models.CharField(
        max_length=4,
        choices=ACTION_CHOICES,
        blank=True,
        help_text="Trades only: buy or sell. Leave empty for a hold or a skip.",
    )
    symbol: models.CharField[str, str] = models.CharField(
        max_length=20,
        validators=[validate_symbol],
        blank=True,
        help_text="Trades name one. Optional for a hold or a skip.",
    )
    amount: models.DecimalField[Decimal | None, Decimal | None] = models.DecimalField(
        max_digits=14,
        decimal_places=MONEY_PLACES,
        null=True,
        blank=True,
        validators=[MinValueValidator(ONE_CENT)],
        help_text="Trades only: the money that changed hands.",
    )
    shares: models.DecimalField[Decimal | None, Decimal | None] = models.DecimalField(
        max_digits=18,
        decimal_places=SHARE_PLACES,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="From the confirmation, if shown. Optional.",
    )
    reason: models.TextField[str, str] = models.TextField(
        blank=True,
        default="",
        db_default="",
        max_length=REASON_MAX_LENGTH,
        help_text="Why. Required for a hold or a skip.",
    )
    state: models.CharField[str, str] = models.CharField(
        max_length=10,
        choices=STATE_CHOICES,
        blank=True,
        default="",
        db_default="",
        help_text="How you were when you decided. Optional.",
    )
    tags: models.CharField[str, str] = models.CharField(
        max_length=200,
        blank=True,
        default="",
        db_default="",
        validators=[validate_tags],
        help_text="Up to five words of your own, separated by spaces or commas. Optional.",
    )
    note: models.CharField[str, str] = models.CharField(max_length=200, blank=True, default="")
    created_at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now_add=True)
    # The foreign key's own column, which Django adds; declared so pyright can read it.
    account_id: int | None

    class Meta:
        ordering = ["account", "date", "pk"]
        verbose_name = "journal entry"
        verbose_name_plural = "journal entries"

    def __str__(self) -> str:
        if self.kind == TRADE:
            return f"{self.date:%Y-%m-%d} {self.action} {self.amount} of {self.symbol}"
        return f"{self.date:%Y-%m-%d} {self.kind}{f' {self.symbol}' if self.symbol else ''}"

    @property
    def is_trade(self) -> bool:
        return self.kind == TRADE

    @property
    def what(self) -> str:
        """The word a table prints: Buy, Sell, Hold or Skip."""
        return (self.action if self.kind == TRADE else self.kind).capitalize()

    @property
    def money(self) -> Decimal:
        """The amount, or zero for a decision with none, for sums."""
        return self.amount if self.amount is not None else Decimal("0")

    def tag_list(self) -> list[str]:
        return self.tags.split()

    def clean(self) -> None:
        """The rules of a line beyond each field's own: a trade is a buy or a sell of a symbol for
        an amount; a hold or a skip has a reason and no money; and nothing is written into a
        month whose review is closed. A `ModelForm` and the admin run this before `save()`."""
        errors: dict[str, str] = {}
        if self.kind == TRADE:
            if self.action not in {action.value for action in Action}:
                errors["action"] = "A trade is a buy or a sell."
            if not self.symbol:
                errors["symbol"] = "A trade names its symbol."
            if self.amount is None:
                errors["amount"] = "A trade has an amount."
        elif self.kind in DECISIONS:
            if not self.reason.strip():
                errors["reason"] = f"A {self.kind} needs a reason: write why, in a sentence."
            if self.action:
                errors["action"] = f"A {self.kind} is not a trade: leave Action empty."
            if self.amount is not None or self.shares is not None:
                errors["amount"] = f"A {self.kind} moves no money: leave Amount and Shares empty."
        if errors:
            raise ValidationError(errors)
        self.refuse_closed_month()

    def refuse_closed_month(self) -> None:
        """A closed month is read-only: a new line dated in it, or a change to a line that was
        dated in it, is refused until its review is reopened with a reason."""
        # An invalid date in a form leaves the field empty, whatever its annotation says.
        day: date | None = getattr(self, "date", None)
        if self.account_id is None or day is None:
            return
        days = {day}
        if self.pk is not None:
            stored = JournalEntry.objects.filter(pk=self.pk).values_list("date", flat=True).first()
            if stored is not None:
                days.add(stored)
        for each in sorted(days):
            if MonthlyReview.is_closed(self.account_id, each):
                raise ValidationError(
                    f"{month_of(each)} is closed. Reopen its review, with a reason, to change it."
                )

    def save(self, *args: Any, **kwargs: Any) -> None:
        """The same guards as a statement line: no float, the symbol's rule, the rounding. A hold
        or a skip without a reason is refused here too, whatever path wrote it."""
        for field in ("amount", "shares"):
            if isinstance(getattr(self, field), float):
                raise TypeError(f"{field} must be a Decimal, not a float")
        if self.kind in DECISIONS and not self.reason.strip():
            raise ValueError(f"a {self.kind} needs a reason")
        if self.symbol:
            self.symbol = normalize_symbol(self.symbol)
        if self.amount is not None:
            self.amount = to_money(self.amount)
        if self.shares is not None:
            self.shares = to_shares(self.shares)
        self.tags = " ".join(parse_tags(self.tags))
        super().save(*args, **kwargs)

    def to_entry(self) -> Entry:
        """Chapter 03's `Entry`, for a trade. `Action(self.action)` raises on a value the enum
        lacks, which the choices and the form make impossible to store. A hold or a skip is not a
        trade, and the review never sees one."""
        if self.kind != TRADE or self.amount is None:
            raise ValueError(f"a {self.kind} is not a trade")
        return Entry(
            day=self.date, action=Action(self.action), symbol=self.symbol, amount=self.amount
        )

    @classmethod
    def entries_for(cls, account: Account) -> list[JournalEntry]:
        """The account's rows in date order, the order `review` and the pages want."""
        return list(cls.objects.filter(account=account))


class MonthlyReview(models.Model):
    """One month of one plan version, opened when the month's buy window closes and closed by the
    owner with three short answers: what I did, what the rules said, what I'll do next month."""

    plan: models.ForeignKey[MethodPlan, MethodPlan] = models.ForeignKey(
        MethodPlan, on_delete=models.PROTECT, related_name="reviews"
    )
    month: models.CharField[str, str] = models.CharField(max_length=7, help_text="YYYY-MM")
    opened_on: models.DateField[date, date] = models.DateField(
        help_text="The day the month's buy window closed."
    )
    did: models.TextField[str, str] = models.TextField(blank=True, default="")
    rules_said: models.TextField[str, str] = models.TextField(blank=True, default="")
    next_month: models.TextField[str, str] = models.TextField(blank=True, default="")
    closed_at: models.DateTimeField[datetime | None, datetime | None] = models.DateTimeField(
        null=True, blank=True
    )
    created_at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["month", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["plan", "month"], name="one_review_per_plan_month")
        ]
        verbose_name = "monthly review"
        verbose_name_plural = "monthly reviews"

    def __str__(self) -> str:
        return f"{self.month} {'closed' if self.closed else 'open'} ({self.plan})"

    @property
    def closed(self) -> bool:
        return self.closed_at is not None

    @classmethod
    def is_closed(cls, account_id: int, day: date) -> bool:
        return cls.objects.filter(
            plan__account_id=account_id, month=month_of(day), closed_at__isnull=False
        ).exists()


class ReviewEvent(models.Model):
    """The audit trail of a review: every close, with what was written, and every reopen, with
    its reason, who did it and when. Rows are only ever added."""

    CLOSED = "closed"
    REOPENED = "reopened"
    ACTIONS = [(CLOSED, "Closed"), (REOPENED, "Reopened")]

    review: models.ForeignKey[MonthlyReview, MonthlyReview] = models.ForeignKey(
        MonthlyReview, on_delete=models.CASCADE, related_name="events"
    )
    action: models.CharField[str, str] = models.CharField(max_length=8, choices=ACTIONS)
    text: models.TextField[str, str] = models.TextField()
    by: models.ForeignKey[Any, Any] = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["at", "pk"]
        verbose_name = "review event"
        verbose_name_plural = "review events"

    def __str__(self) -> str:
        return f"{self.review.month} {self.action} {self.at:%Y-%m-%d %H:%M}"
