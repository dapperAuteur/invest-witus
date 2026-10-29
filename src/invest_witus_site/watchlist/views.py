"""Two POST views on the signed-in owner's account page: add one or many symbols, remove one.
Since 2026-10-29, two GET views too: a watched symbol's stored closes, and the compare page, up to
six of the account's symbols on one chart rebased to 100. Both open on 30, 90 or 365 days and
offer 5 years, 10 years, All and a From and To pair (decision 140); a bad pair is a 400 with the
reason on the page and the default range under it. Their day-by-day tables show 100 rows a page.

Both check ownership the way chapter 08's pages do: the account comes from
`get_object_or_404(Account, pk=pk, owner=request.user)`, so another owner's account is a 404.
Both finish with a redirect to the account page (Post/Redirect/Get, as chapter 04's waitlist),
carrying their report in Django's messages, which the base template prints once.
"""

from dataclasses import dataclass, field
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Page, Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from invest_witus.valuation import STALE_AFTER_DAYS, is_stale
from invest_witus_site.holdings.models import Account, Holding
from invest_witus_site.holdings.views import account_page
from invest_witus_site.methods.models import MethodPlan
from invest_witus_site.methods.momentum import HistoryWindow, history_window
from invest_witus_site.prices import profiles
from invest_witus_site.prices.charts import MAX_LINES, MAX_POINTS, SeriesInput, band, build_plot
from invest_witus_site.prices.history import (
    COMPARE_DEFAULT_RANGE,
    DEFAULT_RANGE,
    PRESETS,
    ChosenRange,
    RangeError,
    StoredSpan,
    chosen_range,
    close_before,
    closes_between,
    preset_key,
    preset_range,
    stored_span,
)
from invest_witus_site.prices.manual import DEFAULT_HISTORY_RANGE, HISTORY_RANGES
from invest_witus_site.prices.models import DailyClose, SymbolProfile
from invest_witus_site.prices.owner_views import run_history_many
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
    if form.cleaned_data["fetch_history"] and report.added:
        # The symbols this submission added, through Get history for several symbols (2026-10-29):
        # one request each within the run's budget and time limit, each symbol's guard kept.
        choice = form.cleaned_data["history_range"] or DEFAULT_HISTORY_RANGE
        run_history_many(request, report.added, choice)
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


# The day-by-day tables under a chart show this many rows a page (`?page=`).
ROWS_PER_PAGE = 100


@dataclass(frozen=True, slots=True)
class RangeChoice:
    """The range a chart page shows, and what the picker needs: an error to print (the page then
    shows the default range and answers 400), the From and To typed, and the stored span that
    bounds the date inputs."""

    chosen: ChosenRange
    error: str
    typed_from: str
    typed_to: str
    span: StoredSpan


def read_range(request: HttpRequest, symbols: list[str], default: int) -> RangeChoice:
    today = timezone.localdate()
    span = stored_span(symbols)
    typed_from = (request.GET.get("from") or "").strip()
    typed_to = (request.GET.get("to") or "").strip()
    try:
        chosen = chosen_range(request.GET, today, span, default=default)
        error = ""
    except RangeError as refused:
        chosen = preset_range(preset_key(None, default), today)
        error = str(refused)
    return RangeChoice(chosen, error, typed_from, typed_to, span)


def range_context(choice: RangeChoice, plot_dates: int, thinned: bool) -> dict[str, object]:
    return {
        "chosen": choice.chosen,
        "range_error": choice.error,
        # The date inputs keep what was typed, so a refused pair can be corrected in place.
        "typed_from": choice.typed_from,
        "typed_to": choice.typed_to,
        "span": choice.span,
        "presets": PRESETS,
        "plot_dates": plot_dates,
        "thinned": thinned,
        "max_points": MAX_POINTS,
        "rows_per_page": ROWS_PER_PAGE,
    }


def page_of[T](rows: list[T], number: str | None) -> Page[T]:
    """One page of a table's rows; a page number out of range is the nearest page."""
    return Paginator(rows, ROWS_PER_PAGE).get_page(number)


@login_required
@require_GET
def history(request: HttpRequest, pk: int, symbol: str) -> HttpResponse:
    """A watched symbol's closes: a labelled line chart with a key and a hover readout, and the
    same days as a table (100 rows a page), over the range from `?days=` (30, 90, 365, 5y, 10y or
    all) or `?from=` and `?to=`. The symbol must be on this account's watch list, and the account
    the signed-in owner's; anything else is a 404. The "as of" line is the newest stored close,
    with chapter 08's stale rule, even when it falls before the range."""
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    item = get_object_or_404(WatchItem, account=account, symbol=symbol.strip().upper())
    choice = read_range(request, [item.symbol], DEFAULT_RANGE)
    chosen = choice.chosen
    closes = closes_between(item.symbol, chosen.since, chosen.until)
    series = SeriesInput(item.symbol, closes, close_before(item.symbol, chosen.since))
    plot = build_plot([series], f"{item.symbol}, {chosen.title}", rebase=False)
    line = plot.lines[0] if plot else None
    window = momentum_window(account, item.symbol, timezone.localdate())
    if plot is not None and window is not None:
        shaded = (
            band(plot, "window", "12-1 window", window.first, window.last),
            band(plot, "excluded", "excluded", window.excluded_first, window.excluded_last),
        )
        plot.bands = [each for each in shaded if each is not None]
    latest = DailyClose.latest_for([item.symbol]).get(item.symbol)
    today = timezone.localdate()
    context = {
        "account": account,
        "item": item,
        **profile_context(item.symbol),
        "plot": plot,
        "line": line,
        "rows": page_of(line.newest_first if line else [], request.GET.get("page")),
        "latest": latest,
        "stale": latest is not None and is_stale(latest, today),
        "stale_after_days": STALE_AFTER_DAYS,
        "history_ranges": [(value, label) for value, (label, _) in HISTORY_RANGES.items()],
        **range_context(choice, plot.total_days if plot else 0, bool(plot and plot.thinned)),
        # Chapter 14: this month's 12-1 window, on an account running 12-1 momentum only, and
        # the From and To that show all of it when the stored closes reach back that far.
        "momentum_window": window,
        "window_query": window_query(window, choice.span) if window is not None else "",
    }
    status = 400 if choice.error else 200
    return render(request, "watchlist/history.html", context, status=status)


def profile_context(symbol: str) -> dict[str, object]:
    """Decision 150: the stored profile for the "About" section, its short description, the
    Wikipedia search link (only with a name), and whether Get description may run now."""
    profile = SymbolProfile.objects.filter(symbol=symbol).first()
    short, cut = profiles.short_description(profile.description) if profile else ("", False)
    return {
        "profile": profile,
        "profile_short": short,
        "profile_cut": cut,
        "profile_search": (
            profiles.wikipedia_search_url(profile.name) if profile and profile.name else ""
        ),
        "profile_can_refresh": not profiles.is_fresh(profile, timezone.now()),
        "profile_refresh_days": profiles.REFRESH_DAYS,
        "profile_source_set": profiles.profile_source_from_settings() is not None,
    }


def momentum_window(account: Account, symbol: str, today: date) -> HistoryWindow | None:
    plan = MethodPlan.active_for(account)
    if plan is None or not plan.is_momentum:
        return None
    return history_window(symbol, today)


def window_query(window: HistoryWindow, span: StoredSpan) -> str:
    """`from=...&to=...` covering the window and the excluded month, or "" when the stored closes
    do not reach the window's start (the range would be refused)."""
    if span.first is None or span.last is None or span.first > window.first:
        return ""
    until = span.last
    if until <= window.first:
        return ""
    return f"from={window.first:%Y-%m-%d}&to={until:%Y-%m-%d}"


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
    is named and left out, never charted. The range works as on the history page, bounded by the
    stored closes of the symbols picked; each line is rebased on its first stored day in it."""
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    allowed = compare_choices(account)
    picked = pick_symbols(request.GET.getlist("symbols"), allowed)
    choice = read_range(request, picked.symbols or allowed, COMPARE_DEFAULT_RANGE)
    chosen = choice.chosen
    series = [
        SeriesInput(
            symbol,
            closes_between(symbol, chosen.since, chosen.until),
            close_before(symbol, chosen.since),
        )
        for symbol in picked.symbols
    ]
    plot = build_plot(series, f"{', '.join(picked.symbols)}: {chosen.title}", rebase=True)
    charted = {line.symbol for line in plot.lines} if plot else set[str]()
    page = request.GET.get("page")
    context = {
        "account": account,
        "allowed": allowed,
        "picked": picked,
        "symbols_query": ",".join(picked.symbols),
        "empty": [symbol for symbol in picked.symbols if symbol not in charted],
        "max_lines": MAX_LINES,
        "plot": plot,
        "daily": page_of(plot.daily_rows() if plot else [], page),
        "daily_open": page is not None,
        "starts_differ": plot is not None and len({line.first.day for line in plot.lines}) > 1,
        **range_context(choice, plot.total_days if plot else 0, bool(plot and plot.thinned)),
    }
    status = 400 if choice.error else 200
    return render(request, "watchlist/compare.html", context, status=status)
