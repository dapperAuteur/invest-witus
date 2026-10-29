"""The paper account page and its two actions: Confirm this month's buys, and check orders now.

Every view here needs a sign-in, the account's owner, an account linked to Alpaca paper and a
superuser (`alpaca_allowed`); anything else is a 404, which does not say whether the account
exists. Every Alpaca failure becomes a message on the page, never a 500. The keys never reach a
template: the page gets numbers and Alpaca's messages, nothing else.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.models import MethodPlan
from invest_witus_site.paper import orders
from invest_witus_site.paper.alpaca import (
    PAPER_HOST,
    AlpacaError,
    PaperAccount,
    PaperPosition,
    paper_client,
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
    try:
        client = paper_client()
        alpaca_account = client.account()
        positions = client.positions()
    except AlpacaError as failure:
        error = failure.message
    context = {
        "account": account,
        "plan": plan,
        "spent": orders.practice_spent(plan) if plan is not None else None,
        "alpaca_account": alpaca_account,
        "positions": positions,
        "orders": PaperOrder.objects.filter(account=account),
        "error": error,
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
        result = orders.confirm(plan, orders.today(), paper_client())
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
            request, f"Placed: buy {order.notional:.2f} of {order.symbol}, {order.status}."
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
        result = orders.sync_orders(paper_client(), account)
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
