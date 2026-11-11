"""Refresh filings now (chapter 16): the owner's button on a watched symbol's page.

Checked like the price buttons (`prices/owner_views.py`): a sign-in, a POST with Django's CSRF
token, the account the signed-in owner's and the symbol on its watch list (a 404 otherwise), and
the ten-minute guard per symbol in `ManualRun`. A refusal from the SEC, a pause, or a document
that is not what the SEC describes is a message on the page, never a 500.
"""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from invest_witus import filings as lib
from invest_witus_site.filings import refresh, sec
from invest_witus_site.filings.models import FUND, NOT_LISTED
from invest_witus_site.holdings.models import Account
from invest_witus_site.prices import manual
from invest_witus_site.prices.models import ManualRun
from invest_witus_site.watchlist.models import WatchItem


@login_required
@require_POST
def refresh_now(request: HttpRequest, pk: int, symbol: str) -> HttpResponse:
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    item = get_object_or_404(WatchItem, account=account, symbol=symbol.strip().upper())
    back = redirect(reverse("watch-history", args=[account.pk, item.symbol]) + "#filings-heading")
    if not settings.SEC_FILINGS_ENABLED:
        messages.error(request, "Filings are off on this copy of the app (SEC_FILINGS=off).")
        return back
    now = timezone.now()
    refused_until = manual.claim(ManualRun.Kind.FILINGS, item.symbol, now)
    if refused_until is not None:
        messages.error(
            request,
            f"{item.symbol}'s filings were asked for less than {manual.GUARD_MINUTES} minutes "
            f"ago. Refresh filings now can run for it again at {manual.when(refused_until)}.",
        )
        return back
    try:
        done = refresh.refresh_symbol(item.symbol, now)
    except sec.SecError as error:
        messages.error(
            request, f"Filings are not available right now: {error.problem}. Nothing was changed."
        )
        return back
    except lib.FilingsDataError as error:
        messages.error(
            request,
            f"Filings are not available right now: SEC EDGAR sent data this app could not read "
            f"({error}). Nothing was changed.",
        )
        return back
    if done.kind == FUND:
        messages.info(request, f"{item.symbol} is a fund, so it has no company filings.")
    elif done.kind == NOT_LISTED:
        messages.info(request, f"SEC EDGAR lists no company under {item.symbol}.")
    else:
        note = f" {done.note}." if done.note else ""
        messages.success(
            request,
            f"Fetched {item.symbol}'s filings from SEC EDGAR: {done.filings} filing"
            f"{'' if done.filings == 1 else 's'} listed, {done.facts} reported figure"
            f"{'' if done.facts == 1 else 's'} stored.{note}",
        )
    return back
