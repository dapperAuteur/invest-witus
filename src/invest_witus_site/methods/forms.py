"""The method page's forms: start a method for an account, and log one journal entry. Chapter 12
adds three: change or end the plan with a reason, close a month's review, and reopen it. Chapter
14 adds the top N a 12-1 momentum plan holds, to the start form and the change form, and puts a
momentum plan's candidates on the account's watch list so the nightly pull stores their closes."""

from collections.abc import Mapping
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction

from invest_witus.methods.rulebook import available_methods
from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.models import (
    MAX_WINDOW_DAYS,
    MIN_WINDOW_DAYS,
    MOMENTUM,
    ONE_CENT,
    REASON_MAX_LENGTH,
    TRADE,
    JournalEntry,
    MethodPlan,
    MonthlyReview,
    join_symbols,
    month_of,
    parse_tags,
    validate_symbol_list,
)
from invest_witus_site.methods.momentum import ensure_watched

SYMBOL_BOX = {"autocomplete": "off", "autocapitalize": "characters", "spellcheck": "false"}


def method_choices() -> list[tuple[str, str]]:
    """The methods the package ships, read when the form is built, never typed into the form.
    Chapter 14's second rules file became the second option with no change here."""
    return [(method.id, method.name) for method in available_methods()]


class StartMethodForm(forms.Form):
    """The plan's numbers. The method is a choice from the package; the symbols go through
    chapter 09's rule; the account is the view's, not a field. Valid only while the account
    runs no method, which `clean()` checks and the database's partial unique constraint backs."""

    method_id = forms.ChoiceField(label="Method", choices=method_choices)
    amount = forms.DecimalField(
        label="Amount each month",
        min_value=ONE_CENT,
        max_digits=14,
        decimal_places=2,
        help_text="In dollars, to the cent.",
    )
    buy_window_days = forms.IntegerField(
        label="Buy window, in days",
        min_value=MIN_WINDOW_DAYS,
        max_value=MAX_WINDOW_DAYS,
        initial=7,
        help_text="Buy within the first N days of each month; 1 to 28.",
    )
    symbols = forms.CharField(
        label="Symbols",
        max_length=200,
        widget=forms.TextInput(attrs=SYMBOL_BOX),
        help_text="The fund or funds the plan names, separated by commas or spaces.",
    )
    started_on = forms.DateField(
        label="Start", widget=forms.DateInput(attrs={"type": "date"}), initial=date.today
    )
    # Chapter 11: optional, and used only on an account linked to Alpaca paper, where Confirm
    # refuses buys beyond what is left of it.
    practice_budget = forms.DecimalField(
        label="Practice budget",
        required=False,
        min_value=ONE_CENT,
        max_digits=14,
        decimal_places=2,
        help_text="Paper accounts only: the practice money this plan may spend. Optional.",
    )
    # Chapter 14: 12-1 momentum's one more number. Optional in the form, required by `clean()`
    # for momentum and refused for index investing, which holds every fund it names.
    top_n = forms.IntegerField(
        label="Top N to hold",
        required=False,
        min_value=1,
        help_text=(
            "12-1 momentum only: how many of the ranked candidates to hold, fewer than the "
            "candidates you name. Leave it empty for index investing."
        ),
    )

    def __init__(self, account: Account, data: Mapping[str, Any] | None = None) -> None:
        super().__init__(data)
        self.account = account
        # The symbols the start put on the watch list (momentum only), for the view's message.
        self.watched: list[str] = []

    def clean_symbols(self) -> str:
        """The box as the stored list: each symbol normalized, once, joined by spaces. A refused
        token is a form error naming it; a plan with a typo in its universe would flag every buy."""
        text: str = self.cleaned_data["symbols"]
        validate_symbol_list(text)
        return join_symbols(text)

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean() or {}
        if MethodPlan.active_for(self.account) is not None:
            raise ValidationError(
                "This account already runs a method. End it from the method page before "
                "starting another."
            )
        check_top_n(self, cleaned.get("method_id"), cleaned.get("top_n"), cleaned.get("symbols"))
        return cleaned

    def start(self) -> MethodPlan:
        """The row. Called after `is_valid()`; the model's `save()` normalizes once more."""
        amount: Decimal = self.cleaned_data["amount"]
        plan = MethodPlan.objects.create(
            account=self.account,
            method_id=self.cleaned_data["method_id"],
            amount=amount,
            buy_window_days=self.cleaned_data["buy_window_days"],
            symbols=self.cleaned_data["symbols"],
            started_on=self.cleaned_data["started_on"],
            practice_budget=self.cleaned_data["practice_budget"],
            top_n=self.cleaned_data.get("top_n"),
        )
        if plan.is_momentum:
            self.watched = ensure_watched(self.account, plan.symbol_list())
        return plan


def check_top_n(
    form: forms.Form, method_id: str | None, top_n: int | None, symbols: str | None
) -> None:
    """Chapter 14: a momentum plan names a top N smaller than its candidates (with N equal to the
    list, the ranking would leave nothing out); an index plan names none."""
    if "top_n" in form.errors:
        return
    if method_id != MOMENTUM:
        if top_n is not None:
            form.add_error("top_n", "Leave this empty: index investing holds every fund it names.")
        return
    if top_n is None:
        form.add_error("top_n", "12-1 momentum needs a top N: how many candidates to hold.")
        return
    count = len((symbols or "").split())
    if symbols and top_n >= count:
        form.add_error(
            "top_n",
            f"Name more candidates than the top N: {count} candidate{'' if count == 1 else 's'} "
            f"and a top {top_n} leaves nothing to rank out.",
        )


class JournalEntryForm(forms.ModelForm[JournalEntry]):
    """One row of the journal, as a `ModelForm`: the fields, their labels, help and validators
    come from the model, so the symbol rule and the one-cent minimum run here before `save()`
    runs them again. The view passes `instance=JournalEntry(account=account)`, so the model's
    `clean()` knows the account and can refuse a closed month.

    Chapter 12: the kind, the reason, the state and the tags. A form posted without a kind (the
    chapter 10 form, a script) is a trade, as every entry was before this chapter."""

    class Meta:
        model = JournalEntry
        fields = [
            "date",
            "kind",
            "action",
            "symbol",
            "amount",
            "shares",
            "reason",
            "state",
            "tags",
            "note",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "symbol": forms.TextInput(attrs=SYMBOL_BOX),
            "reason": forms.Textarea(attrs={"rows": 2}),
            "tags": forms.TextInput(attrs={"autocomplete": "off", "spellcheck": "false"}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["kind"].required = False

    def clean_kind(self) -> str:
        kind: str = self.cleaned_data.get("kind") or ""
        return kind or TRADE

    def clean_tags(self) -> str:
        try:
            return " ".join(parse_tags(self.cleaned_data.get("tags") or ""))
        except ValueError as error:
            raise ValidationError(str(error)) from None


def first_of_month(day: date) -> date:
    return day.replace(day=1)


def first_of_next_month(day: date) -> date:
    return (day.replace(day=28) + timedelta(days=4)).replace(day=1)


THIS_MONTH = "this"
NEXT_MONTH = "next"
CHANGE = "change"
END = "end"


class PlanChangeForm(forms.Form):
    """Change the plan's amount, window or symbols, or end it, always with a reason. A change
    makes a new version that starts on the first day of this month or next month; the old version
    keeps judging the months before it (PRD 7.1: "old reviews keep pointing at the version they
    judged"). The method itself does not change here: a different method is a new plan."""

    what = forms.ChoiceField(
        label="What to do",
        choices=[(CHANGE, "Change the numbers"), (END, "End the plan")],
        widget=forms.RadioSelect,
        initial=CHANGE,
    )
    amount = forms.DecimalField(
        label="Amount each month",
        required=False,
        min_value=ONE_CENT,
        max_digits=14,
        decimal_places=2,
    )
    buy_window_days = forms.IntegerField(
        label="Buy window, in days",
        required=False,
        min_value=MIN_WINDOW_DAYS,
        max_value=MAX_WINDOW_DAYS,
    )
    symbols = forms.CharField(
        label="Symbols", required=False, max_length=200, widget=forms.TextInput(attrs=SYMBOL_BOX)
    )
    # Chapter 14: shown for a 12-1 momentum plan only; removed in `__init__` for an index plan.
    top_n = forms.IntegerField(label="Top N to hold", required=False, min_value=1)
    effective = forms.ChoiceField(label="Starting", required=False)
    reason = forms.CharField(
        label="Why",
        max_length=REASON_MAX_LENGTH,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Required. It is kept with the version, dated, for every later review.",
    )

    def __init__(
        self, plan: MethodPlan, today: date, data: Mapping[str, Any] | None = None
    ) -> None:
        initial = {
            "amount": plan.amount,
            "buy_window_days": plan.buy_window_days,
            "symbols": plan.symbols,
            "top_n": plan.top_n,
            "effective": NEXT_MONTH,
        }
        super().__init__(data, initial=initial)
        self.plan = plan
        self.today = today
        self.watched: list[str] = []
        if not plan.is_momentum:
            del self.fields["top_n"]
        this, following = first_of_month(today), first_of_next_month(today)
        effective = self.fields["effective"]
        assert isinstance(effective, forms.ChoiceField)
        effective.choices = [
            (NEXT_MONTH, f"Next month, from {following:%Y-%m-%d}"),
            (THIS_MONTH, f"This month, from {this:%Y-%m-%d}"),
        ]

    def clean_symbols(self) -> str:
        text: str = self.cleaned_data.get("symbols") or ""
        if not text.strip():
            return ""
        validate_symbol_list(text)
        return join_symbols(text)

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean() or {}
        if cleaned.get("what") != CHANGE:
            return cleaned
        for name in ("amount", "buy_window_days", "symbols"):
            if name not in self.errors and cleaned.get(name) in (None, ""):
                self.add_error(name, "A change keeps every number: fill this in.")
        if self.errors:
            return cleaned
        plan = self.plan
        if plan.is_momentum:
            check_top_n(self, plan.method_id, cleaned.get("top_n"), cleaned["symbols"])
            if self.errors:
                return cleaned
        new = (cleaned["amount"], cleaned["buy_window_days"], cleaned["symbols"])
        top_n = cleaned.get("top_n") if plan.is_momentum else plan.top_n
        if new == (plan.amount, plan.buy_window_days, plan.symbols) and top_n == plan.top_n:
            if plan.is_momentum:
                raise ValidationError(
                    "Nothing changed: the amount, the window, the candidates and the top N match."
                )
            raise ValidationError("Nothing changed: the amount, the window and the symbols match.")
        if cleaned.get("effective") == THIS_MONTH:
            self.check_this_month()
        return cleaned

    def check_this_month(self) -> None:
        """This month may take the new numbers only while nothing in it is settled: the window is
        still open, no trade is logged in it, and the version in force has started. Otherwise
        the month already belongs to the old numbers, and the change starts next month."""
        plan, today = self.plan, self.today
        if plan.started_on > today:
            raise ValidationError(
                f"Version {plan.version} starts on {plan.started_on:%Y-%m-%d} and has not begun; "
                "a change to it starts next month."
            )
        if today.day > plan.buy_window_days:
            raise ValidationError(
                f"This month's window closed on day {plan.buy_window_days}; the month is judged "
                "by the numbers in force then. Choose next month."
            )
        traded = JournalEntry.objects.filter(
            account=plan.account,
            kind=TRADE,
            date__year=today.year,
            date__month=today.month,
            date__gte=plan.started_on,
        ).exists()
        if traded:
            raise ValidationError(
                f"{month_of(today)} already has a trade in the journal; it stays on version "
                f"{plan.version}. Choose next month."
            )
        if MonthlyReview.is_closed(plan.account.pk, today):
            raise ValidationError(f"{month_of(today)} is closed. Choose next month.")

    def apply(self) -> MethodPlan:
        """Write the change, after `is_valid()`. Ending: the row stays, inactive, with the day and
        the reason. Changing: the old row ends the day before the new version starts, and the
        new row points back at it. One transaction, the old row first, so the partial unique
        constraint (one active plan per account) never sees two."""
        plan, data = self.plan, self.cleaned_data
        reason: str = data["reason"].strip()
        with transaction.atomic():
            if data["what"] == END:
                plan.active = False
                plan.ended_on = self.today
                plan.end_reason = reason
                plan.save()
                return plan
            effective = (
                first_of_month(self.today)
                if data.get("effective") == THIS_MONTH
                else first_of_next_month(self.today)
            )
            starts = max(effective, plan.started_on)
            plan.active = False
            plan.ended_on = starts - timedelta(days=1)
            plan.save()
            version = MethodPlan.objects.create(
                account=plan.account,
                method_id=plan.method_id,
                amount=data["amount"],
                buy_window_days=data["buy_window_days"],
                symbols=data["symbols"],
                started_on=starts,
                practice_budget=plan.practice_budget,
                previous=plan,
                version=plan.version + 1,
                change_reason=reason,
                top_n=data.get("top_n") if plan.is_momentum else plan.top_n,
            )
            if version.is_momentum:
                self.watched = ensure_watched(version.account, version.symbol_list())
            return version


TEXT_BOX = {"rows": 3}


class CloseReviewForm(forms.Form):
    """The month's written review: three short answers, each required."""

    did = forms.CharField(
        label="What I did",
        max_length=REASON_MAX_LENGTH,
        widget=forms.Textarea(attrs=TEXT_BOX),
    )
    rules_said = forms.CharField(
        label="What the rules said",
        max_length=REASON_MAX_LENGTH,
        widget=forms.Textarea(attrs=TEXT_BOX),
        help_text="Started for you from the review's findings. Edit it to say it your way.",
    )
    next_month = forms.CharField(
        label="What I'll do next month",
        max_length=REASON_MAX_LENGTH,
        widget=forms.Textarea(attrs=TEXT_BOX),
    )


class ReopenReviewForm(forms.Form):
    reason = forms.CharField(
        label="Why reopen it",
        max_length=REASON_MAX_LENGTH,
        widget=forms.Textarea(attrs=TEXT_BOX),
        help_text="Required, and kept: the month's history shows every close and reopen.",
    )
