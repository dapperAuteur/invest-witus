"""Two POST views on the signed-in owner's account page: add one or many symbols, remove one.
Since 2026-10-29, two GET views too: a watched symbol's stored closes over 30, 90 or 365 days,
and the compare page, up to six of the account's symbols on one chart rebased to 100.

Both check ownership the way chapter 08's pages do: the account comes from
`get_object_or_404(Account, pk=pk, owner=request.user)`, so another owner's account is a 404.
Both finish with a redirect to the account page (Post/Redirect/Get, as chapter 04's waitlist),
carrying their report in Django's messages, which the base template prints once.
"""

from dataclasses import dataclass, field
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from invest_witus.valuation import STALE_AFTER_DAYS, is_stale
from invest_witus_site.holdings.models import Account, Holding
from invest_witus_site.holdings.views import account_page
from invest_witus_site.prices.charts import MAX_LINES, SeriesInput, build_plot
from invest_witus_site.prices.history import (
    COMPARE_DEFAULT_RANGE,
    RANGES,
    close_before,
    closes_since,
    range_days,
)
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
    """A watched symbol's closes: a labelled line chart with a key and a hover readout, and the
    same days as a table, over the range in `?days=` (30, 90 or 365). The symbol must be on this
    account's watch list, and the account the signed-in owner's; anything else is a 404. The "as
    of" line is the newest stored close, with chapter 08's stale rule, even when it falls before
    the range."""
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    item = get_object_or_404(WatchItem, account=account, symbol=symbol.strip().upper())
    days = range_days(request.GET.get("days"))
    today = timezone.localdate()
    since = today - timedelta(days=days)
    closes = closes_since(item.symbol, since)
    series = SeriesInput(item.symbol, closes, close_before(item.symbol, since))
    plot = build_plot([series], f"{item.symbol}, last {days} days", rebase=False)
    latest = DailyClose.latest_for([item.symbol]).get(item.symbol)
    context = {
        "account": account,
        "item": item,
        "days": days,
        "ranges": RANGES,
        "plot": plot,
        "line": plot.lines[0] if plot else None,
        "latest": latest,
        "stale": latest is not None and is_stale(latest, today),
        "stale_after_days": STALE_AFTER_DAYS,
        "history_ranges": [(value, label) for value, (label, _) in HISTORY_RANGES.items()],
    }
    return render(request, "watchlist/history.html", context)


def compare_choices(account: Account) -> list[str]:
    """The symbols the compare page offers for this account: its watch list and its holdings
    (cash has no price), each once, sorted."""
    watched = WatchItem.objects.filter(account=account).values_list("symbol", flat=True)
    held = (
        Holding.objects.filter(account=account)
        .exclude(kind=Holding.Kind.CASH)
        .values_list("symbol", flat=True)
    )
    return sorted(set(watched) | set(held))


@dataclass
class Picked:
    """The symbols asked for, sorted out: the ones charted (in the order asked, at most
    `MAX_LINES`), the ones this account does not watch or hold, and the ones over the limit."""

    symbols: list[str] = field(default_factory=list[str])
    not_allowed: list[str] = field(default_factory=list[str])
    over_limit: list[str] = field(default_factory=list[str])


def pick_symbols(asked: list[str], allowed: list[str]) -> Picked:
    """`?symbols=A,B,C`, or the form's `?symbols=A&symbols=B`, or both: split on commas, upper
    case, each once in the order asked."""
    picked = Picked()
    seen: set[str] = set()
    for value in asked:
        for token in value.split(","):
            symbol = token.strip().upper()
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            if symbol not in allowed:
                picked.not_allowed.append(symbol)
            elif len(picked.symbols) >= MAX_LINES:
                picked.over_limit.append(symbol)
            else:
                picked.symbols.append(symbol)
    return picked


@login_required
@require_GET
def compare(request: HttpRequest, pk: int) -> HttpResponse:
    """Up to six of this account's watched or held symbols on one chart, each rebased to 100 on
    its first stored day in the range, with a table of start, end and change per symbol. The
    account must be the signed-in owner's (404 otherwise); a symbol it neither watches nor holds
    is named and left out, never charted."""
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    allowed = compare_choices(account)
    days = range_days(request.GET.get("days"), default=COMPARE_DEFAULT_RANGE)
    picked = pick_symbols(request.GET.getlist("symbols"), allowed)
    since = timezone.localdate() - timedelta(days=days)
    series = [
        SeriesInput(symbol, closes_since(symbol, since), close_before(symbol, since))
        for symbol in picked.symbols
    ]
    plot = build_plot(series, f"{', '.join(picked.symbols)}: last {days} days", rebase=True)
    charted = {line.symbol for line in plot.lines} if plot else set[str]()
    context = {
        "account": account,
        "allowed": allowed,
        "picked": picked,
        "empty": [symbol for symbol in picked.symbols if symbol not in charted],
        "days": days,
        "ranges": RANGES,
        "max_lines": MAX_LINES,
        "plot": plot,
        "starts_differ": plot is not None and len({line.first.day for line in plot.lines}) > 1,
    }
    return render(request, "watchlist/compare.html", context)
