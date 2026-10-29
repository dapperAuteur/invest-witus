"""The logbook: every line of an account's journal on one page, filtered by month, kind and tag,
with an edit form for the lines written by hand and a CSV export.

The method page shows the journal as part of the review; this page is the journal itself. The
filters are plain GET parameters (`?month=2026-11&kind=skip&tag=late`), so a filtered view is a
link the owner can keep, and the export takes the same parameters, so the file holds what the
page shows. Everything here is the owner's only: chapter 08's ownership query, a 404 otherwise.

Two kinds of line cannot be edited here. A line a paper order wrote (chapter 11) is the broker's
record, kept in step by the nightly sync. And a line in a closed month is read-only until the
month's review is reopened with a reason (the model's `clean()` refuses it; this page also says
so before showing a form).
"""

import csv
import re
from dataclasses import dataclass

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render

from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.forms import JournalEntryForm
from invest_witus_site.methods.models import (
    DECISIONS,
    TAG,
    TRADE,
    JournalEntry,
    MonthlyReview,
    month_of,
)
from invest_witus_site.paper.models import PaperOrder

MONTH = re.compile(r"\d{4}-\d{2}")
KINDS = ("buy", "sell", "hold", "skip")
# The export's columns, in order. Documented in chapter 12; a test reads the header row.
CSV_COLUMNS = (
    "date",
    "kind",
    "symbol",
    "amount",
    "shares",
    "state",
    "tags",
    "reason",
    "note",
    "source",
    "month_closed",
)
# A spreadsheet may run a cell that starts with one of these as a formula: OWASP's list, with the
# full-width forms. Text the owner typed is exported with a leading apostrophe instead.
FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r", "\n", "\uff1d", "\uff0b", "\uff0d", "\uff20")


@dataclass(frozen=True, slots=True)
class Filters:
    month: str
    kind: str
    tag: str

    @property
    def query(self) -> str:
        """The same filters as a query string, for the export link."""
        params = QueryDict(mutable=True)
        for name in ("month", "kind", "tag"):
            if value := getattr(self, name):
                params[name] = value
        encoded = params.urlencode()
        return f"?{encoded}" if encoded else ""


def read_filters(request: HttpRequest) -> Filters:
    """Each filter if it is well formed, else nothing: a bad value widens the list, never errors."""
    month = request.GET.get("month", "")
    kind = request.GET.get("kind", "")
    tag = request.GET.get("tag", "").lower()
    return Filters(
        month=month if MONTH.fullmatch(month) else "",
        kind=kind if kind in KINDS else "",
        tag=tag if TAG.fullmatch(tag) else "",
    )


def filtered(account: Account, filters: Filters) -> list[JournalEntry]:
    entries = JournalEntry.objects.filter(account=account)
    if filters.month:
        year, month = (int(part) for part in filters.month.split("-"))
        entries = entries.filter(date__year=year, date__month=month)
    if filters.kind in DECISIONS:
        entries = entries.filter(kind=filters.kind)
    elif filters.kind:
        entries = entries.filter(kind=TRADE, action=filters.kind)
    rows = list(entries)
    if filters.tag:
        # Tags are a short space-separated column, so the last filter runs in Python: a personal
        # journal is hundreds of lines, not millions.
        rows = [entry for entry in rows if filters.tag in entry.tag_list()]
    return rows


@dataclass(frozen=True, slots=True)
class Line:
    """One entry as the logbook shows it: where it came from, and whether it can be edited."""

    entry: JournalEntry
    order_id: str
    month_closed: bool

    @property
    def source(self) -> str:
        return f"alpaca-paper:{self.order_id}" if self.order_id else "hand"

    @property
    def editable(self) -> bool:
        return not self.order_id and not self.month_closed


def lines_for(account: Account, entries: list[JournalEntry]) -> list[Line]:
    """Two queries for the whole page: the orders that wrote entries, and the closed months."""
    orders = dict(
        PaperOrder.objects.filter(account=account)
        .exclude(journal_entry=None)
        .values_list("journal_entry_id", "client_order_id")
    )
    closed = set(
        MonthlyReview.objects.filter(plan__account=account, closed_at__isnull=False).values_list(
            "month", flat=True
        )
    )
    return [
        Line(entry, orders.get(entry.pk, ""), month_of(entry.date) in closed) for entry in entries
    ]


@login_required
def logbook(request: HttpRequest, pk: int) -> HttpResponse:
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    filters = read_filters(request)
    every = JournalEntry.entries_for(account)
    context = {
        "account": account,
        "filters": filters,
        "lines": lines_for(account, filtered(account, filters)),
        "total": len(every),
        "months": sorted({month_of(entry.date) for entry in every}, reverse=True),
        "kinds": KINDS,
        "tags": sorted({tag for entry in every for tag in entry.tag_list()}),
    }
    return render(request, "methods/logbook.html", context)


def cell(text: str) -> str:
    return f"'{text}" if text.startswith(FORMULA_STARTS) else text


def plain(value: object) -> str:
    return "" if value is None else str(value)


@login_required
def logbook_csv(request: HttpRequest, pk: int) -> HttpResponse:
    """The journal as CSV, with the page's filters. UTF-8, a header row, one line per entry,
    numbers as plain decimals (no thousands separator, no currency sign), dates as YYYY-MM-DD.
    `no-store`, because the file is a personal journal and no cache should keep a copy."""
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    lines = lines_for(account, filtered(account, read_filters(request)))
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="logbook-account-{account.pk}.csv"'
    response["Cache-Control"] = "no-store"
    writer = csv.writer(response)
    writer.writerow(CSV_COLUMNS)
    for line in lines:
        entry = line.entry
        writer.writerow(
            [
                f"{entry.date:%Y-%m-%d}",
                entry.what.lower(),
                entry.symbol,
                plain(entry.amount),
                plain(entry.shares),
                entry.state,
                entry.tags,
                cell(entry.reason),
                cell(entry.note),
                line.source,
                "yes" if line.month_closed else "no",
            ]
        )
    return response


@login_required
def edit_entry(request: HttpRequest, pk: int, entry_pk: int) -> HttpResponse:
    """Edit one line written by hand, in a month that is open."""
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    entry = get_object_or_404(JournalEntry, pk=entry_pk, account=account)
    if PaperOrder.objects.filter(journal_entry=entry).exists():
        messages.error(
            request,
            "A paper order wrote this line; the nightly check keeps it in step with Alpaca, so "
            "it is not edited by hand.",
        )
        return redirect("logbook", pk=account.pk)
    closed = MonthlyReview.is_closed(account.pk, entry.date)
    form = JournalEntryForm(request.POST if request.method == "POST" else None, instance=entry)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        messages.success(request, f"Saved: {saved}.")
        return redirect("logbook", pk=account.pk)
    context = {"account": account, "entry": entry, "form": form, "closed": closed}
    return render(request, "methods/entry_edit.html", context)
