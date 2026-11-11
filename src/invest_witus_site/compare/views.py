"""The Compare methods page (chapter 15): two to four of the signed-in person's accounts on one
chart, each line its value with the money put in left out, rebased to 100, beside a do-nothing
yardstick, and a table of what each account put in, holds and gained.

Owner pages only (`login_required`), and only the person's own accounts: an id that is not theirs
is counted and left out, never named. No vendor is asked for anything while the page draws,
except Alpaca's own equity for an account the site owner linked to Alpaca paper, read with a short
timeout as a cross-check.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.paginator import Page, Paginator
from django.http import HttpRequest, HttpResponse, QueryDict
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from invest_witus.compare import HUNDRED, line_return, max_drawdown
from invest_witus_site.compare.records import (
    MAX_ACCOUNTS,
    MIN_ACCOUNTS,
    SP500_FUNDS,
    AccountResult,
    AlpacaCheck,
    account_result,
    accounts_with_plans,
    alpaca_checks,
    default_yardstick,
    drawdown_text,
    pick_accounts,
    plan_of,
    return_text,
    same_money_for,
    yardstick_choices,
)
from invest_witus_site.holdings.models import Account
from invest_witus_site.holdings.templatetags.holdings_extras import money
from invest_witus_site.prices.charts import (
    LINE_STYLES,
    DayRow,
    Line,
    Plot,
    SeriesInput,
    index_text,
    lay_out,
    line_days,
)
from invest_witus_site.prices.history import RangeError, closes_between, parse_day
from invest_witus_site.prices.manual import HISTORY_RANGES
from invest_witus_site.prices.models import SymbolProfile
from invest_witus_site.watchlist.models import WatchItem

ROWS_PER_PAGE = 100
VALUE_BASIS = "value with the money put in left out"


@dataclass(frozen=True, slots=True)
class Dates:
    """The stretch compared, and the words of a refused pair."""

    start: date
    end: date
    error: str = ""
    typed_from: str = ""
    typed_to: str = ""


def chosen_dates(params: QueryDict, default_start: date, today: date) -> Dates:
    """`?from=` and `?to=`, each optional: From defaults to the earliest plan start, To to today.
    A date that does not parse, a To after today or a From after To is refused in words, and the
    defaults are shown instead."""
    typed_from = (params.get("from") or "").strip()
    typed_to = (params.get("to") or "").strip()
    try:
        start = parse_day(typed_from, "From") if typed_from else default_start
        end = parse_day(typed_to, "To") if typed_to else today
        if end > today:
            raise RangeError(f"To ({end:%Y-%m-%d}) is after today ({today:%Y-%m-%d}).")
        if start > end:
            raise RangeError(f"From ({start:%Y-%m-%d}) must be on or before To ({end:%Y-%m-%d}).")
    except RangeError as refused:
        return Dates(min(default_start, today), today, str(refused), typed_from, typed_to)
    return Dates(start, end, "", typed_from, typed_to)


@dataclass
class Yardstick:
    """The do-nothing line: one symbol's stored closes, rebased to 100 on its first day in the
    stretch. `line` is None when no close is stored inside it."""

    symbol: str
    name: str
    line: Line | None
    watched_on: Account | None
    twr: str = ""
    drop: str = ""


def yardstick_for(symbol: str, user_accounts: list[Account], dates: Dates) -> Yardstick:
    profile = SymbolProfile.objects.filter(symbol=symbol).first()
    watched = WatchItem.objects.filter(account__in=user_accounts, symbol=symbol).first()
    rows = closes_between(symbol, dates.start, dates.end)
    found = Yardstick(
        symbol, profile.name if profile else "", None, watched.account if watched else None
    )
    if not rows:
        return found
    basis, missing, days = line_days(SeriesInput(symbol, rows), rebase=True)
    found.line = Line(symbol, basis, missing, "", "", "", days)
    points = [(row.day, row.index or HUNDRED) for row in days]
    total = line_return(points)
    length = (days[-1].day - days[0].day).days
    found.twr = return_text(total, length) if total is not None else ""
    found.drop = drawdown_text(max_drawdown(points))
    return found


def account_line(result: AccountResult) -> Line | None:
    """The account's time-weighted line as a chart line: each day's level, its dollar value in
    the close column (the table under the chart prints it), and the hover text written here."""
    if result.stretch is None or not result.line:
        return None
    values = {day.day: day for day in result.stretch.days}
    rows: list[DayRow] = []
    readout: dict[date, str] = {}
    for day, level in result.line:
        held = values[day]
        rows.append(
            DayRow(
                day=day,
                close=held.value,
                adj_close=None,
                value=level,
                change=None,
                change_pct=None,
                index=level,
                source="journal",
            )
        )
        put_in = f", {money(held.flow)} put in that day" if held.flow else ""
        readout[day] = (
            f"{index_text(level)} (start = 100), value {money(held.value)}, "
            f"{money(held.put_in)} put in so far{put_in}"
        )
    return Line(result.account.name, VALUE_BASIS, 0, "", "", "", rows, readout=readout)


def same_money_line(result: AccountResult) -> Line | None:
    """Exercise 1 (decision 185): the same money into the yardstick as a chart line, drawn like
    an account's (its value with the money put in left out, 100 on its first day), so it starts on
    the same day as the account's own line; the hover text gives its value in dollars."""
    same = result.same
    if same is None or same.stretch is None or not same.line:
        return None
    values = {day.day: day for day in same.stretch.days}
    rows: list[DayRow] = []
    readout: dict[date, str] = {}
    for day, level in same.line:
        held = values[day]
        rows.append(
            DayRow(
                day=day,
                close=held.value,
                adj_close=None,
                value=level,
                change=None,
                change_pct=None,
                index=level,
                source="journal",
            )
        )
        readout[day] = (
            f"{index_text(level)} (start = 100), value {money(held.value)}, "
            f"{money(held.put_in)} put in so far"
        )
    name = f"{same.label} ({result.account.name})"
    return Line(name, VALUE_BASIS, 0, "", "", "", rows, readout=readout)


@dataclass(frozen=True, slots=True)
class Lines:
    """The chart's lines, and the same-money lines left off it for want of a line style."""

    lines: list[Line]
    left_off: list[str]


def chart_lines(results: list[AccountResult], yardstick: Yardstick | None) -> Lines:
    """The accounts, then the yardstick, then each account's same money in the yardstick while
    the chart has a line style left (six); the rest stay in the table and are named."""
    lines = [line for line in (account_line(result) for result in results) if line is not None]
    if yardstick is not None and yardstick.line is not None:
        lines.append(yardstick.line)
    left_off: list[str] = []
    for result in results:
        line = same_money_line(result)
        if line is None:
            continue
        if len(lines) < len(LINE_STYLES):
            lines.append(line)
        else:
            left_off.append(result.account.name)
    return Lines(lines, left_off)


def build_chart(
    results: list[AccountResult], yardstick: Yardstick | None, title: str
) -> Plot | None:
    lines = chart_lines(results, yardstick).lines
    for position, line in enumerate(lines):
        line.color, line.dash, line.pattern = LINE_STYLES[position]
    plot = lay_out(lines, title, rebase=True, noun="day value")
    if plot is not None:
        words = [
            "Each account's line is its value with the money put in left out, so a deposit never "
            "looks like growth; it starts at 100 on the account's first day with a holding in the "
            "range."
        ]
        if yardstick is not None and yardstick.line is not None:
            words.append(
                f"The yardstick, {yardstick.symbol}, is its stored {yardstick.line.basis}, "
                "rebased to 100 on its first day in the range."
            )
        if any(line.symbol.startswith("Same money into ") for line in lines):
            words.append(
                'Each "Same money" line is that account\'s own deposits put into the yardstick '
                "on the same days, drawn the same way, so it starts with the account's line."
            )
        words.append(
            f"Values from your journal and the app's stored closes, as of {plot.last:%Y-%m-%d}."
        )
        plot.caption = " ".join(words)
        plot.desc = (
            "One line per account, and the yardstick's line if it has closes, oldest day on the "
            "left, each starting at 100."
        )
    return plot


@dataclass(frozen=True, slots=True)
class DailyCell:
    level: str
    amount: str


def daily_rows(plot: Plot) -> list[tuple[date, list[DailyCell | None]]]:
    """Newest first: each date with each line's level and dollar amount (an account's value, the
    yardstick's close), or None where a line has no day."""
    maps = [{row.day: row for row in line.days} for line in plot.lines]
    rows: list[tuple[date, list[DailyCell | None]]] = []
    for day in reversed(plot.all_dates):
        cells: list[DailyCell | None] = []
        for found in maps:
            row = found.get(day)
            cells.append(None if row is None else DailyCell(row.index_label, money(row.close)))
        rows.append((day, cells))
    return rows


def page_of[T](rows: list[T], number: str | None) -> Page[T]:
    return Paginator(rows, ROWS_PER_PAGE).get_page(number)


def query_without_page(params: QueryDict) -> str:
    kept = params.copy()
    kept.pop("page", None)
    return kept.urlencode()


@login_required
@require_GET
def compare_methods(request: HttpRequest) -> HttpResponse:
    today = timezone.localdate()
    owned = list(Account.objects.filter(owner_id=request.user.pk).order_by("name"))
    with_plans = accounts_with_plans(request.user)
    picked = pick_accounts(request.GET.getlist("accounts"), owned, with_plans)
    plans = {account.pk: plan_of(account) for account in owned}
    starts = [
        plan.chain_start()
        for account in picked.accounts
        if (plan := plans.get(account.pk)) is not None
    ]
    dates = chosen_dates(request.GET, min(starts) if starts else today, today)
    results = [
        account_result(account, dates.start, dates.end, today) for account in picked.accounts
    ]
    choices = yardstick_choices(request.user)
    asked = (request.GET.get("yardstick") or "").strip().upper()
    if "yardstick" in request.GET:
        symbol = asked if asked in choices else ""
    else:
        symbol = default_yardstick(choices)
    yardstick = yardstick_for(symbol, owned, dates) if symbol else None
    # Exercise 1 (decision 185): each account's own money, on its own days, into the yardstick.
    if symbol:
        for result in results:
            result.same = same_money_for(result, symbol, dates.start, dates.end)
    names = ", ".join(account.name for account in picked.accounts)
    title = f"{names}: {dates.start:%Y-%m-%d} to {dates.end:%Y-%m-%d}"
    plot = build_chart(results, yardstick, title) if picked.accounts else None
    checks: dict[int, AlpacaCheck] = alpaca_checks(request.user, picked.accounts)
    page = request.GET.get("page")
    context = {
        "owned": owned,
        "plans": plans,
        "picked": picked,
        "picked_pks": [account.pk for account in picked.accounts],
        "too_few": 0 < len(picked.accounts) < MIN_ACCOUNTS,
        "min_accounts": MIN_ACCOUNTS,
        "max_accounts": MAX_ACCOUNTS,
        "dates": dates,
        "results": results,
        "rows": [(result, checks.get(result.account.pk)) for result in results],
        "any_check": bool(checks),
        "choices": choices,
        "asked_yardstick": asked if "yardstick" in request.GET else None,
        "yardstick": yardstick,
        "sp500_funds": SP500_FUNDS,
        "plot": plot,
        "same_left_off": chart_lines(results, yardstick).left_off if plot else [],
        "any_same": any(result.same is not None for result in results),
        "daily": page_of(daily_rows(plot) if plot else [], page),
        "daily_open": page is not None,
        "base_query": query_without_page(request.GET),
        "return_query": query_without_page(request.GET),
        "history_ranges": [(value, label) for value, (label, _) in HISTORY_RANGES.items()],
        "rows_per_page": ROWS_PER_PAGE,
        "zero": Decimal(0),
    }
    status = 400 if dates.error else 200
    return render(request, "compare/compare_methods.html", context, status=status)
