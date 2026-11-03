"""The paper account page and its two actions: Confirm this month's buys, and check orders now.
Decision 159 adds the Link to Alpaca page (choose the account's key slot, check what it reaches,
link or unlink) and the key slot list.

Every view here needs a sign-in, the account's owner, an account linked to Alpaca paper and a
superuser (`alpaca_allowed`); anything else is a 404, which does not say whether the account
exists. The link page needs a paper account rather than a linked one, and the slot list a
superuser. Every Alpaca failure becomes a message on the page, never a 500. The keys never reach a
template: the page gets numbers, Alpaca's messages, a slot's name and the last four characters of
its key id, nothing else.
"""

from typing import Any

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from invest_witus_site.holdings.models import Account
from invest_witus_site.holdings.templatetags.holdings_extras import money
from invest_witus_site.methods.models import MethodPlan
from invest_witus_site.paper import linking, orders, slots
from invest_witus_site.paper.alpaca import (
    PAPER_HOST,
    AlpacaError,
    AlpacaNotConfigured,
    PaperAccount,
    PaperPosition,
    client_for,
)
from invest_witus_site.paper.models import PaperOrder

# The paper limits Alpaca's paper trading page lists (read October 29, 2026). PRD 7.7: stated
# wherever paper results appear.
PAPER_LIMITS = (
    "Alpaca's paper trading does not simulate dividends, price slippage, market impact or "
    "regulatory fees, and fills part of an order at random about one time in ten."
)


def linked_account_or_404(request: HttpRequest, pk: int) -> Account:
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    if not orders.alpaca_allowed(request.user, account):
        raise Http404("No paper account here.")
    return account


@login_required
def paper_account(request: HttpRequest, pk: int) -> HttpResponse:
    account = linked_account_or_404(request, pk)
    plan = MethodPlan.active_for(account)
    alpaca_account: PaperAccount | None = None
    positions: list[PaperPosition] = []
    error = ""
    not_configured = False
    try:
        client = client_for(account)
        alpaca_account = client.account()
        positions = client.positions()
    except AlpacaError as failure:
        error = failure.message
        not_configured = isinstance(failure, AlpacaNotConfigured)
    context = {
        "account": account,
        "plan": plan,
        "spent": orders.practice_spent(plan) if plan is not None else None,
        "alpaca_account": alpaca_account,
        "positions": positions,
        "orders": PaperOrder.objects.filter(account=account),
        "error": error,
        "not_configured": not_configured,
        # Decision 159: what the slot's keys reach now, against the number recorded at linking.
        "number_changed": (
            alpaca_account is not None
            and bool(account.alpaca_account_number)
            and alpaca_account.account_number != account.alpaca_account_number
        ),
        "host": PAPER_HOST,
        "paper_limits": PAPER_LIMITS,
    }
    return render(request, "paper/paper_account.html", context)


@login_required
@require_POST
def confirm_buys(request: HttpRequest, pk: int) -> HttpResponse:
    """The owner's click. Places this month's staged buys once, then back to the method page."""
    account = linked_account_or_404(request, pk)
    plan = MethodPlan.active_for(account)
    if plan is None:
        messages.error(request, "No method runs on this account, so there is nothing to buy.")
        return redirect("method-page", pk=account.pk)
    try:
        result = orders.confirm(plan, orders.today(), client_for(account))
    except orders.ConfirmRefused as refused:
        messages.error(request, str(refused))
    except AlpacaError as error:
        messages.error(request, f"Nothing was placed. {error.message}")
    else:
        report(request, result)
    return redirect("method-page", pk=account.pk)


def report(request: HttpRequest, result: orders.ConfirmResult) -> None:
    for order in result.placed:
        messages.success(
            request, f"Placed: buy {money(order.notional)} of {order.symbol}, {order.status}."
        )
    for order in result.already:
        messages.info(request, f"Already placed: {order.symbol}, {order.status}. Nothing new sent.")
    for symbol, message in result.failed:
        messages.error(request, f"Not placed: {symbol}. {message}")
    if result.placed and not result.clock.is_open:
        messages.info(
            request,
            "The market is closed. Alpaca queues a day order for the next open, "
            f"{timezone.localtime(result.clock.next_open):%Y-%m-%d %H:%M %Z}.",
        )


@login_required
@require_POST
def sync_now(request: HttpRequest, pk: int) -> HttpResponse:
    """The nightly sync for this account's orders, now."""
    account = linked_account_or_404(request, pk)
    try:
        result = orders.sync_orders(client_for(account), account)
    except AlpacaError as error:
        messages.error(request, error.message)
    else:
        messages.info(
            request,
            f"Checked {result.checked} open order{'' if result.checked == 1 else 's'}: "
            f"{result.filled} filled, {result.still_open} still open.",
        )
        for client_order_id, message in result.failed.items():
            messages.error(request, f"{client_order_id}: {message}")
    return redirect("paper-account", pk=account.pk)


# --- Decision 159: link an account to Alpaca paper through a key slot ----------------------------


def superuser_or_404(request: HttpRequest) -> None:
    if not getattr(request.user, "is_superuser", False):
        raise Http404("No paper account here.")


def paper_kind_account_or_404(request: HttpRequest, pk: int) -> Account:
    """The owner's paper account, linked or not, for the site owner's superuser only."""
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    superuser_or_404(request)
    if account.kind != "paper":
        raise Http404("Only a paper account can be linked to Alpaca paper.")
    return account


def slot_label(row: linking.SlotRow, account: Account) -> str:
    """A slot as one radio label: its name, the last four of its key id or what is missing, and
    the accounts already linked through it. Never more of a key than four characters."""
    if row.complete:
        state = f"key id ending {row.key_hint}" if row.key_hint else "keys set"
    elif row.conflicting:
        state = "conflicting: set in both name forms with different values, not used"
    else:
        state = f"keys incomplete: {' and '.join(row.missing)} not set"
    users = [a.name for a in row.accounts if a.pk != account.pk and a.owner_id == account.owner_id]
    used = f"; linked to {', '.join(users)}" if users else ""
    current = account.is_alpaca_paper and account.alpaca_slot_name == row.name
    here = "; this account's slot now" if current else ""
    return f"{row.name} ({state}{used}{here})"


class LinkForm(forms.Form):
    """The slot to link through. Its choices are the slots the server has, read when the form is
    built; an incomplete slot is listed so its state is visible, and refused if chosen."""

    slot = forms.ChoiceField(widget=forms.RadioSelect, label="Key slot")

    def __init__(self, account: Account, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.rows = [row for row in linking.slot_rows() if row.on_server]
        self.complete = {row.name for row in self.rows if row.complete}
        self.conflicting = {row.name for row in self.rows if row.conflicting}
        slot = self.fields["slot"]
        assert isinstance(slot, forms.ChoiceField)
        slot.choices = [(row.name, slot_label(row, account)) for row in self.rows]
        if account.is_alpaca_paper:
            self.initial.setdefault("slot", account.alpaca_slot_name)

    def clean_slot(self) -> str:
        chosen: str = self.cleaned_data["slot"]
        if chosen in self.conflicting:
            raise forms.ValidationError(
                slots.SlotKeys(chosen, "", "", conflicting=True).conflict_message
            )
        if chosen not in self.complete:
            key_name, secret_name = slots.env_names(chosen)
            raise forms.ValidationError(
                f"Slot {chosen}'s keys are incomplete on the server: set both {key_name} and "
                f"{secret_name}, then redeploy."
            )
        return chosen


@login_required
def link_alpaca(request: HttpRequest, pk: int) -> HttpResponse:
    """GET: the slot choice. POST `action=check`: read what the slot reaches, save nothing.
    POST `action=link`: the same check, then save the link. POST `action=unlink`: drop it."""
    account = paper_kind_account_or_404(request, pk)
    check: linking.LinkCheck | None = None
    form = LinkForm(account)
    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "unlink":
            blocked = linking.unlink_block(account)
            if blocked:
                messages.error(request, blocked)
            elif account.is_alpaca_paper:
                linking.unlink(account)
                messages.success(
                    request, "Unlinked from Alpaca paper. The orders table and the journal stay."
                )
            return redirect("account-detail", pk=account.pk)
        form = LinkForm(account, request.POST)
        if form.is_valid() and action in ("check", "link"):
            slot: str = form.cleaned_data["slot"]
            if action == "check":
                check = linking.check_slot(account, slot)
            else:
                check = linking.link(account, slot)
                if check.ok and check.reached is not None:
                    messages.success(
                        request,
                        f"Linked to Alpaca paper account {check.reached.account_number} through "
                        f"slot {check.slot}.",
                    )
                    return redirect("paper-account", pk=account.pk)
    context = {
        "account": account,
        "form": form,
        "check": check,
        "unusable": slots.unusable(),
        "open_orders": PaperOrder.open_orders(account).count() if account.is_alpaca_paper else 0,
        "host": PAPER_HOST,
    }
    return render(request, "paper/link.html", context)


@login_required
def key_slots(request: HttpRequest) -> HttpResponse:
    """The site owner's list of key slots: name, last four of the key id, complete or not, and
    the Invest accounts linked through each; then every `ALPACA_PAPER_` variable the app could not
    use, by name with the reason (decision 166). Reads the settings and the database only."""
    superuser_or_404(request)
    example_key, example_secret = slots.example_names()
    context = {
        "rows": linking.slot_rows(),
        "unusable": slots.unusable(),
        "example_key": example_key,
        "example_secret": example_secret,
        "paper_accounts": Account.objects.filter(owner=request.user, kind=Account.Kind.PAPER),
    }
    return render(request, "paper/key_slots.html", context)
