"""Two POST views on the signed-in owner's account page: add one or many symbols, remove one.
Since 2026-10-29, one GET view too: a watched symbol's stored closes over 30, 90 or 365 days.

Both check ownership the way chapter 08's pages do: the account comes from
`get_object_or_404(Account, pk=pk, owner=request.user)`, so another owner's account is a 404.
Both finish with a redirect to the account page (Post/Redirect/Get, as chapter 04's waitlist),
carrying their report in Django's messages, which the base template prints once.
"""

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from invest_witus.valuation import STALE_AFTER_DAYS, is_stale
from invest_witus_site.holdings.models import Account
from invest_witus_site.holdings.views import account_page
from invest_witus_site.prices.history import RANGES, closes_since, line_chart, range_days
from invest_witus_site.prices.manual import HISTORY_RANGES
from invest_witus_site.prices.models import DailyClose
from invest_witus_site.watchlist.forms import WatchForm
from invest_witus_site.watchlist.models import WatchItem


@login_required
@require_POST
def add(request: HttpRequest, pk: int) -> HttpResponse:
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    form = WatchForm(request.POST)
    if not form.is_valid():
        # Nothing could be added: the account page again, with the reason beside the box.
        return account_page(request, account, form)
    parsed = form.cleaned_data["symbols"]
    report = WatchItem.add_many(account, parsed.symbols, form.cleaned_data["note"])
    if report.added:
        messages.success(request, f"Added to the watch list: {', '.join(report.added)}.")
    if report.existing:
        messages.info(request, f"Already on the watch list: {', '.join(report.existing)}.")
    if parsed.refused:
        reasons = "; ".join(f"{token} ({reason})" for token, reason in parsed.refused)
        messages.error(request, f"Refused: {reasons}.")
    return redirect("account-detail", pk=account.pk)


@login_required
@require_POST
def remove(request: HttpRequest, pk: int, item_pk: int) -> HttpResponse:
    """The row is looked up inside the account named in the URL, so an id from another
    account, the owner's own or anyone else's, is a 404. Stored closes are not touched: the
    table of prices is the pull's, and a symbol may be watched again or held tomorrow."""
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    item = get_object_or_404(WatchItem, pk=item_pk, account=account)
    item.delete()
    messages.success(request, f"Removed {item.symbol} from the watch list.")
    return redirect("account-detail", pk=account.pk)


@login_required
@require_GET
def history(request: HttpRequest, pk: int, symbol: str) -> HttpResponse:
    """A watched symbol's closes: a line chart and the same closes as a table, over the range in
    `?days=` (30, 90 or 365). The symbol must be on this account's watch list, and the account
    the signed-in owner's; anything else is a 404. The "as of" line is the newest stored close,
    with chapter 08's stale rule, even when it falls before the range."""
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    item = get_object_or_404(WatchItem, account=account, symbol=symbol.strip().upper())
    days = range_days(request.GET.get("days"))
    today = timezone.localdate()
    closes = closes_since(item.symbol, today - timedelta(days=days))
    latest = DailyClose.latest_for([item.symbol]).get(item.symbol)
    context = {
        "account": account,
        "item": item,
        "days": days,
        "ranges": RANGES,
        "closes": list(reversed(closes)),
        "chart": line_chart(closes),
        "latest": latest,
        "stale": latest is not None and is_stale(latest, today),
        "stale_after_days": STALE_AFTER_DAYS,
        "history_ranges": [(value, label) for value, (label, _) in HISTORY_RANGES.items()],
    }
    return render(request, "watchlist/history.html", context)
