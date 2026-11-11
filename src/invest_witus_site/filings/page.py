"""What the symbol page shows from the stored SEC data (chapter 16): the Filings list, the Key
numbers table and its bars, and the words for every case where there is nothing to show.

Nothing here asks the SEC: the page reads the app's own tables, like the closes.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.utils import timezone

from invest_witus import filings as lib
from invest_witus_site.filings import sec
from invest_witus_site.filings.models import FUND, NOT_LISTED, Filing, KeyFact, SecCompany

HUNDRED = Decimal(100)
FORM_WORDS = {
    "10-K": "Annual report",
    "10-Q": "Quarterly report",
    "8-K": "Current report (a major event)",
}
# The bars: three lines of the table, over the fiscal years.
CHARTED = ("revenue", "net_income", "free_cash_flow")


def form_words(form: str) -> str:
    base, _, amended = form.partition("/")
    words = FORM_WORDS.get(base, form)
    return f"{words}, amended" if amended else words


@dataclass(frozen=True, slots=True)
class ShownCell:
    text: str
    title: str
    note: str
    missing: bool


@dataclass(frozen=True, slots=True)
class ShownRow:
    label: str
    derived: bool
    concepts: str
    years: list[ShownCell]
    quarters: list[ShownCell]


@dataclass(frozen=True, slots=True)
class Bar:
    label: str
    text: str
    x: Decimal
    width: Decimal
    direction: str


@dataclass(frozen=True, slots=True)
class BarGroup:
    label: str
    bars: list[Bar]


@dataclass(frozen=True, slots=True)
class KeyChart:
    groups: list[BarGroup]
    zero_x: Decimal
    any_negative: bool


def shown_cell(cell: lib.Cell, unit: str) -> ShownCell:
    if cell.value is None:
        return ShownCell(cell.missing, cell.missing, "", True)
    note = cell.form + (", derived" if cell.derived else "")
    return ShownCell(lib.short_number(cell.value, unit), cell.source, note, False)


def place(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def key_chart(numbers: lib.KeyNumbers) -> KeyChart | None:
    """Bars for revenue, net income and free cash flow per fiscal year, on one scale from the
    lowest figure (or 0) to the highest (or 0), so the zero line is where the bars meet, as in
    chapter 14's ranked bars. None when no figure is known."""
    rows = {row.key: row for row in numbers.rows if row.key in CHARTED}
    values = [
        c.value for key in CHARTED if key in rows for c in rows[key].years if c.value is not None
    ]
    if not values:
        return None
    low, high = min(min(values), Decimal(0)), max(max(values), Decimal(0))
    span = high - low or Decimal(1)
    zero = (0 - low) * HUNDRED / span
    groups: list[BarGroup] = []
    for key in CHARTED:
        row = rows.get(key)
        if row is None:
            continue
        bars: list[Bar] = []
        for period, cell in zip(numbers.years, row.years, strict=True):
            label = f"{period.end:%Y-%m-%d}"
            if cell.value is None:
                bars.append(Bar(label, cell.missing, place(zero), Decimal(0), "none"))
                continue
            end = (cell.value - low) * HUNDRED / span
            direction = "up" if cell.value > 0 else ("down" if cell.value < 0 else "flat")
            bars.append(
                Bar(
                    label,
                    lib.short_number(cell.value, row.unit),
                    place(min(zero, end)),
                    place(max(abs(end - zero), Decimal("0.5"))),
                    direction,
                )
            )
        groups.append(BarGroup(row.label, bars))
    return KeyChart(groups, place(zero), low < 0)


def stored_facts(symbol: str) -> list[lib.Fact]:
    return [
        lib.Fact(
            concept=row.concept,
            unit=row.unit,
            start=row.period_start,
            end=row.period_end,
            value=row.value,
            form=row.form,
            filed=row.filed,
            accession=row.accession,
            fiscal_year=row.fiscal_year,
            fiscal_period=row.fiscal_period,
        )
        for row in KeyFact.objects.filter(symbol=symbol)
    ]


def unavailable(company: SecCompany | None, now: datetime) -> str:
    """Why the page cannot show fresh filings now, in words; empty when nothing is wrong."""
    held = sec.paused_until(now)
    if held is not None:
        return (
            f"SEC EDGAR answered {held.status} at "
            f"{timezone.localtime(held.noted_at):%Y-%m-%d %H:%M}, so the app is leaving it alone "
            f"until {timezone.localtime(held.until):%H:%M %Z}."
        )
    if company is not None and company.problem:
        return f"The last refresh failed: {company.problem}."
    return ""


def filings_context(symbol: str, now: datetime | None = None) -> dict[str, object]:
    now = now or timezone.now()
    company = SecCompany.objects.filter(symbol=symbol).first()
    filings = list(Filing.objects.filter(symbol=symbol).order_by("-filing_date", "-accession"))
    numbers = lib.key_numbers(stored_facts(symbol))
    rows = [
        ShownRow(
            row.label,
            row.derived,
            ", ".join(row.concepts_used) or lib.NOT_TAGGED,
            [shown_cell(cell, row.unit) for cell in row.years],
            [shown_cell(cell, row.unit) for cell in row.quarters],
        )
        for row in numbers.rows
    ]
    return {
        "sec_enabled": settings.SEC_FILINGS_ENABLED,
        "sec_company": company,
        "sec_is_fund": company is not None and company.kind == FUND,
        "sec_not_listed": company is not None and company.kind == NOT_LISTED,
        "sec_filings": [(row, form_words(row.form)) for row in filings],
        "sec_unavailable": unavailable(company, now),
        "sec_numbers": numbers,
        "sec_rows": rows,
        "sec_chart": key_chart(numbers),
        "sec_user_agent": settings.SEC_USER_AGENT,
    }
