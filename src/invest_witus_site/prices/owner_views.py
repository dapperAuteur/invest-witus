"""The owner's price buttons as POST views (2026-10-29). The logic is in `manual.py`.

Each view checks the sign-in (`login_required`) and the method (`require_POST`, so the CSRF token
of Django's middleware applies), then ownership the way the account pages do: the account comes
from `get_object_or_404(Account, pk=pk, owner=request.user)`, and Get history also needs the
symbol on that account's watch list, so another owner's account or symbol is a 404. Every answer
is a redirect carrying Django's messages (Post/Redirect/Get); a vendor's refusal, a 429 included,
is a message, never a 500.
"""

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from invest_witus_site.holdings.models import Account
from invest_witus_site.prices import manual
from invest_witus_site.prices.models import ManualRun
from invest_witus_site.prices.pull import DAYS_BACK, pull
from invest_witus_site.prices.sources import PriceSourceError, source_from_settings
from invest_witus_site.watchlist.models import WatchItem


def run_fetch_now(request: HttpRequest) -> None:
    """The nightly pull for the signed-in owner's symbols, now, with its report as messages."""
    user = request.user
    symbols = manual.owner_symbols(user)
    if not symbols:
        messages.info(request, "Nothing to fetch: no account of yours holds or watches a symbol.")
        return
    refused_until = manual.claim(ManualRun.Kind.FETCH_NOW, str(user.pk))
    if refused_until is not None:
        messages.error(
            request,
            f"Prices were fetched less than {manual.GUARD_MINUTES} minutes ago. The next "
            f"Fetch prices now can run at {manual.when(refused_until)}.",
        )
        return
    today = timezone.localdate()
    result = pull(
        source_from_settings(),
        symbols,
        today - timedelta(days=DAYS_BACK),
        today,
        time_limit=manual.FETCH_TIME_LIMIT_SECONDS,
    )
    summary, errors, infos = manual.fetch_messages(result)
    messages.success(request, summary)
    for line in errors:
        messages.error(request, line)
    for line in infos:
        messages.info(request, line)


@login_required
@require_POST
def fetch_now(request: HttpRequest) -> HttpResponse:
    """The button on `/accounts/`."""
    run_fetch_now(request)
    return redirect("account-list")


@login_required
@require_POST
def fetch_now_for_account(request: HttpRequest, pk: int) -> HttpResponse:
    """The button on an account page: the same run (every symbol the owner holds or watches),
    back to that page."""
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    run_fetch_now(request)
    return redirect("account-detail", pk=account.pk)


@login_required
@require_POST
def fetch_history(request: HttpRequest, pk: int, symbol: str) -> HttpResponse:
    """One request for one watched symbol's closes over the chosen range. `return_to=history`
    sends the owner back to the symbol's history page; anything else to the account page."""
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    item = get_object_or_404(WatchItem, account=account, symbol=symbol.strip().upper())
    back = (
        redirect("watch-history", pk=account.pk, symbol=item.symbol)
        if request.POST.get("return_to") == "history"
        else redirect("account-detail", pk=account.pk)
    )
    choice = request.POST.get("range", "")
    today = timezone.localdate()
    since = manual.history_since(choice, today)
    if since is None:
        labels = ", ".join(label.lower() for label, _ in manual.HISTORY_RANGES.values())
        messages.error(request, f"Pick a range for {item.symbol}: {labels}.")
        return back
    refused_until = manual.claim(ManualRun.Kind.HISTORY, item.symbol)
    if refused_until is not None:
        messages.error(
            request,
            f"{item.symbol}'s history was fetched less than {manual.GUARD_MINUTES} minutes ago. "
            f"Get history can run for it again at {manual.when(refused_until)}.",
        )
        return back
    try:
        result = manual.fetch_history(source_from_settings(), item.symbol, since, today)
    except PriceSourceError as error:
        later = " Try again after the hour." if error.retry_later else ""
        messages.error(request, f"{item.symbol}: {error.problem}. Nothing was stored.{later}")
        return back
    messages.success(request, manual.history_message(result, manual.HISTORY_RANGES[choice][0]))
    return back


@login_required
@require_POST
def fetch_history_many(request: HttpRequest, pk: int) -> HttpResponse:
    """Fetch history for selected (`which=selected` with the ticked `symbols`) or for all
    (`which=all`) of this account's watched symbols, over one range, back to the account page.
    A ticked symbol not on this account's list is named and left out."""
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    back = redirect("account-detail", pk=account.pk)
    watched = list(
        WatchItem.objects.filter(account=account)
        .order_by("symbol")
        .values_list("symbol", flat=True)
    )
    if request.POST.get("which") == "all":
        symbols = watched
    else:
        asked = {
            value.strip().upper() for value in request.POST.getlist("symbols") if value.strip()
        }
        symbols = [symbol for symbol in watched if symbol in asked]
        if asked - set(watched):
            messages.error(
                request,
                f"Not on this watch list, so left out: {', '.join(sorted(asked - set(watched)))}.",
            )
    if not symbols:
        messages.error(request, "Tick at least one symbol, or press Fetch history for all.")
        return back
    choice = request.POST.get("range", "")
    today = timezone.localdate()
    since = manual.history_since(choice, today)
    if since is None:
        labels = ", ".join(label.lower() for label, _ in manual.HISTORY_RANGES.values())
        messages.error(request, f"Pick a range: {labels}.")
        return back
    result = manual.fetch_history_many(source_from_settings(), symbols, since, today)
    successes, errors, infos = manual.many_messages(result, manual.HISTORY_RANGES[choice][0])
    for line in successes:
        messages.success(request, line)
    for line in errors:
        messages.error(request, line)
    for line in infos:
        messages.info(request, line)
    return back
