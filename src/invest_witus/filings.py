"""What a company reports to the SEC, as plain values: no Django, no network (chapter 16).

Three JSON documents from SEC EDGAR, read on November 10, 2026:

- `https://www.sec.gov/files/company_tickers.json`, the ticker-to-CIK map: an object whose values
  are `{"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}`. Share classes use a hyphen
  (`BRK-B`), where this app's symbol rule also allows a dot (`BRK.B`).
- `https://www.sec.gov/files/company_tickers_mf.json`, the same for mutual funds and ETFs:
  `{"fields": ["cik", "seriesId", "classId", "symbol"], "data": [[36405, "S...", "C...", "VOO"]]}`.
- `https://data.sec.gov/submissions/CIK##########.json` ("Each entity's current filing history",
  the ten-digit CIK with leading zeros): the company's name and `entityType`, and under
  `filings.recent` one list per column (`form`, `filingDate`, `reportDate`, `accessionNumber`,
  `primaryDocument`, `primaryDocDescription`, ...), newest first.
- `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json` ("all the company concepts data
  for a company into a single API call"): `facts.<taxonomy>.<concept>.units.<unit>` is a list of
  `{"start", "end", "val", "accn", "fy", "fp", "form", "filed"}`; `start` is missing for a balance
  sheet figure (a value on one day). `fy` is the fiscal year of the filing, not of the figure: a
  10-K repeats last year's numbers as comparatives with this year's `fy`, so a figure is keyed by
  its own dates here, never by `fy`.

The functions below turn those into rows, choose the concept each line of the "Key numbers" table
reads (the names vary by company), and work out the figures the filings do not state directly: a
quarter a 10-Q only reports as year to date, the fourth quarter (the year less nine months), and
free cash flow (operating cash flow less capital expenditure), each marked as derived.
"""

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal, cast

# The forms the Filings list shows: the annual and quarterly reports, current reports, and their
# amendments.
REPORT_FORMS = frozenset({"10-K", "10-K/A", "10-Q", "10-Q/A", "8-K", "8-K/A"})
# The forms whose numbers the Key numbers table reads.
FACT_FORMS = frozenset({"10-K", "10-K/A", "10-Q", "10-Q/A"})
ANNUAL_FORMS = frozenset({"10-K", "10-K/A"})
# Forms an investment company files and an operating company does not. A filer with some of
# these and no 10-K or 10-Q is a fund (SPY's trust, for example, files 497 and N-30D).
FUND_FORMS = frozenset(
    {"485BPOS", "485APOS", "497", "497K", "N-CSR", "N-CSRS", "NPORT-P", "N-CEN", "N-30D", "24F-2NT"}
)
LIST_LENGTH = 8
YEARS_SHOWN = 5
QUARTERS_SHOWN = 4
# A fiscal year of 52 or 53 weeks, or twelve calendar months; a quarter of 13 or 14 weeks, or
# three months.
YEAR_DAYS = range(350, 381)
QUARTER_DAYS = range(80, 101)

ARCHIVES = "https://www.sec.gov/Archives/edgar/data"


class FilingsDataError(ValueError):
    """A document that is not what the SEC's pages describe."""


def sec_ticker(symbol: str) -> str:
    """The app's symbol as EDGAR writes it: upper case, a share class's dot as a hyphen."""
    return symbol.strip().upper().replace(".", "-")


def padded_cik(cik: int | str) -> str:
    """The ten-digit CIK with leading zeros that the data.sec.gov paths need."""
    text = str(cik).strip()
    if not text.isdigit() or len(text) > 10:
        raise FilingsDataError(f"not a CIK: {cik!r}")
    return text.zfill(10)


def submissions_url(cik: int | str) -> str:
    return f"https://data.sec.gov/submissions/CIK{padded_cik(cik)}.json"


def companyfacts_url(cik: int | str) -> str:
    return f"https://data.sec.gov/api/xbrl/companyfacts/CIK{padded_cik(cik)}.json"


def document_url(cik: int | str, accession: str, primary_document: str) -> str:
    """The filing's main document on sec.gov: the archive folder is the CIK without its zeros
    and the accession number without its hyphens."""
    folder = accession.replace("-", "")
    return f"{ARCHIVES}/{int(padded_cik(cik))}/{folder}/{primary_document}"


def load(text: str) -> object:
    try:
        return json.loads(text, parse_float=Decimal)
    except json.JSONDecodeError as error:
        raise FilingsDataError(f"not JSON: {error.msg}") from error


def as_dict(value: object, what: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise FilingsDataError(f"{what} is not an object")
    return cast(dict[str, object], value)


def as_list(value: object, what: str) -> list[object]:
    if not isinstance(value, list):
        raise FilingsDataError(f"{what} is not a list")
    return cast(list[object], value)


def as_int(value: object, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise FilingsDataError(f"{what} is not a whole number: {value!r}")
    return value


def as_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def as_date(value: object, what: str) -> date:
    if not isinstance(value, str):
        raise FilingsDataError(f"{what} is not a date: {value!r}")
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        raise FilingsDataError(f"{what} is not a date: {value!r}") from None


def optional_date(value: object, what: str) -> date | None:
    return None if value in (None, "") else as_date(value, what)


# The ticker maps


@dataclass(frozen=True, slots=True)
class Listing:
    """One ticker in a map: its CIK, the name the SEC files it under, and whether the fund map
    listed it."""

    cik: int
    title: str
    fund: bool = False


def parse_company_tickers(text: str) -> dict[str, Listing]:
    """`company_tickers.json` to `{ticker: Listing}`. A ticker listed twice keeps its first row."""
    body = as_dict(load(text), "company_tickers.json")
    found: dict[str, Listing] = {}
    for key, raw in body.items():
        row = as_dict(raw, f"row {key}")
        ticker = sec_ticker(as_text(row.get("ticker")))
        if ticker and ticker not in found:
            found[ticker] = Listing(
                as_int(row.get("cik_str"), f"row {key}'s cik_str"), as_text(row.get("title"))
            )
    return found


def parse_fund_tickers(text: str) -> dict[str, Listing]:
    """`company_tickers_mf.json` to `{ticker: Listing(fund=True)}`, its columns read from
    `fields` rather than assumed."""
    body = as_dict(load(text), "company_tickers_mf.json")
    fields = [as_text(name) for name in as_list(body.get("fields"), "fields")]
    try:
        cik_at, symbol_at = fields.index("cik"), fields.index("symbol")
    except ValueError:
        raise FilingsDataError("company_tickers_mf.json has no cik or symbol field") from None
    found: dict[str, Listing] = {}
    for index, raw in enumerate(as_list(body.get("data"), "data")):
        row = as_list(raw, f"data row {index}")
        if len(row) <= max(cik_at, symbol_at):
            raise FilingsDataError(f"data row {index} is too short")
        ticker = sec_ticker(as_text(row[symbol_at]))
        if ticker and ticker not in found:
            found[ticker] = Listing(as_int(row[cik_at], f"data row {index}'s cik"), "", fund=True)
    return found


Kind = Literal["company", "fund", "not listed"]


def classify(
    symbol: str, companies: dict[str, Listing], funds: dict[str, Listing]
) -> tuple[Kind, Listing | None]:
    """A fund when the fund map lists the ticker; a company when only the company map does (the
    submissions may still show a fund, see `is_fund_filer`); otherwise not listed."""
    ticker = sec_ticker(symbol)
    if ticker in funds:
        return "fund", funds[ticker]
    if ticker in companies:
        return "company", companies[ticker]
    return "not listed", None


# The submissions feed


@dataclass(frozen=True, slots=True)
class FilingRow:
    """One filing from the submissions feed."""

    form: str
    filed: date
    report_date: date | None
    accession: str
    primary_document: str
    description: str

    def url(self, cik: int | str) -> str:
        return document_url(cik, self.accession, self.primary_document)


@dataclass(frozen=True, slots=True)
class Submissions:
    cik: int
    name: str
    entity_type: str
    filings: list[FilingRow]

    @property
    def forms(self) -> set[str]:
        return {row.form for row in self.filings}


def parse_submissions(text: str) -> Submissions:
    """The feed to its name, entity type and every recent filing, newest first. The columns of
    `filings.recent` are parallel lists; a column shorter than `form` is refused."""
    body = as_dict(load(text), "the submissions feed")
    cik_raw = body.get("cik")
    cik = int(padded_cik(cik_raw if isinstance(cik_raw, int | str) else ""))
    recent = as_dict(as_dict(body.get("filings"), "filings").get("recent"), "filings.recent")
    forms = as_list(recent.get("form"), "form")
    columns = {
        name: as_list(recent.get(name, [""] * len(forms)), name)
        for name in (
            "filingDate",
            "reportDate",
            "accessionNumber",
            "primaryDocument",
            "primaryDocDescription",
        )
    }
    for name, values in columns.items():
        if len(values) < len(forms):
            raise FilingsDataError(f"{name} has {len(values)} entries for {len(forms)} forms")
    rows: list[FilingRow] = []
    for i, form in enumerate(forms):
        accession = as_text(columns["accessionNumber"][i])
        if not accession:
            raise FilingsDataError(f"filing {i} has no accession number")
        rows.append(
            FilingRow(
                form=as_text(form),
                filed=as_date(columns["filingDate"][i], f"filing {i}'s filingDate"),
                report_date=optional_date(columns["reportDate"][i], f"filing {i}'s reportDate"),
                accession=accession,
                primary_document=as_text(columns["primaryDocument"][i]),
                description=as_text(columns["primaryDocDescription"][i]),
            )
        )
    rows.sort(key=lambda row: (row.filed, row.accession), reverse=True)
    return Submissions(cik, as_text(body.get("name")), as_text(body.get("entityType")), rows)


def recent_reports(filings: Iterable[FilingRow], limit: int = LIST_LENGTH) -> list[FilingRow]:
    """The newest `limit` 10-K, 10-Q and 8-K filings (with amendments) that name a document."""
    chosen = [row for row in filings if row.form in REPORT_FORMS and row.primary_document]
    return sorted(chosen, key=lambda row: (row.filed, row.accession), reverse=True)[:limit]


def is_fund_filer(submissions: Submissions) -> bool:
    """A filer that is not an operating company and files fund forms but no 10-K or 10-Q."""
    forms = submissions.forms
    if forms & FACT_FORMS:
        return False
    return submissions.entity_type != "operating" and bool(forms & FUND_FORMS)


# The companyfacts feed


@dataclass(frozen=True, slots=True)
class Fact:
    """One reported figure. `start` is None for a value on one day (a balance sheet line)."""

    concept: str
    unit: str
    start: date | None
    end: date
    value: Decimal
    form: str
    filed: date
    accession: str
    fiscal_year: int | None = None
    fiscal_period: str = ""
    # For a quarter worked out from two year-to-date figures: the subtraction, in words.
    derived_from: str = ""

    @property
    def days(self) -> int | None:
        """The length of the period, both ends counted; None for a value on one day."""
        return None if self.start is None else (self.end - self.start).days + 1


@dataclass(frozen=True, slots=True)
class LineSpec:
    """One line of the Key numbers table: the concepts it may read, in order of preference."""

    key: str
    label: str
    kind: Literal["duration", "instant"]
    unit: str
    concepts: tuple[str, ...]


# Short ordered lists per line, the first found in a period wins. Concept names are the US GAAP
# taxonomy's (`us-gaap:`), as they appear in companyfacts. Companies moved from the older names
# (SalesRevenueNet) to the revenue standard's in 2018, so a long table may use both.
LINES: tuple[LineSpec, ...] = (
    LineSpec(
        "revenue",
        "Revenue",
        "duration",
        "USD",
        (
            "us-gaap:Revenues",
            "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
            "us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax",
            "us-gaap:SalesRevenueNet",
        ),
    ),
    LineSpec(
        "net_income",
        "Net income",
        "duration",
        "USD",
        (
            "us-gaap:NetIncomeLoss",
            "us-gaap:ProfitLoss",
            "us-gaap:NetIncomeLossAvailableToCommonStockholdersBasic",
        ),
    ),
    LineSpec(
        "operating_cash_flow",
        "Operating cash flow",
        "duration",
        "USD",
        (
            "us-gaap:NetCashProvidedByUsedInOperatingActivities",
            "us-gaap:NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
        ),
    ),
    LineSpec(
        "capex",
        "Capital expenditure",
        "duration",
        "USD",
        (
            "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
            "us-gaap:PaymentsToAcquireProductiveAssets",
        ),
    ),
    LineSpec(
        "shares",
        "Shares outstanding",
        "instant",
        "shares",
        ("us-gaap:CommonStockSharesOutstanding",),
    ),
    LineSpec(
        "cash",
        "Cash and cash equivalents",
        "instant",
        "USD",
        (
            "us-gaap:CashAndCashEquivalentsAtCarryingValue",
            "us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
            "us-gaap:Cash",
        ),
    ),
    LineSpec(
        "long_term_debt",
        "Long-term debt",
        "instant",
        "USD",
        (
            "us-gaap:LongTermDebtNoncurrent",
            "us-gaap:LongTermDebt",
            "us-gaap:LongTermDebtAndCapitalLeaseObligations",
        ),
    ),
)
CONCEPTS: frozenset[str] = frozenset(concept for line in LINES for concept in line.concepts)


def parse_companyfacts(
    text: str, concepts: frozenset[str] = CONCEPTS, since: date | None = None
) -> list[Fact]:
    """Every figure of the concepts asked for, from a 10-K or a 10-Q, ending on or after `since`.
    A figure reported again in a later filing (a comparative, or a restatement) is kept once,
    from the latest filing, which is the company's newest word on it."""
    body = as_dict(load(text), "companyfacts")
    taxonomies = as_dict(body.get("facts", {}), "facts")
    latest: dict[tuple[str, str, date | None, date], Fact] = {}
    for taxonomy, raw_concepts in taxonomies.items():
        for name, raw_concept in as_dict(raw_concepts, taxonomy).items():
            concept = f"{taxonomy}:{name}"
            if concept not in concepts:
                continue
            units = as_dict(as_dict(raw_concept, concept).get("units", {}), f"{concept}.units")
            for unit, raw_rows in units.items():
                for index, raw in enumerate(as_list(raw_rows, f"{concept} {unit}")):
                    fact = read_fact(concept, unit, as_dict(raw, f"{concept} {unit} {index}"))
                    if fact is None or (since is not None and fact.end < since):
                        continue
                    key = (concept, unit, fact.start, fact.end)
                    kept = latest.get(key)
                    if kept is None or (fact.filed, fact.accession) > (kept.filed, kept.accession):
                        latest[key] = fact
    return sorted(latest.values(), key=lambda f: (f.concept, f.unit, f.end, f.start or f.end))


def read_fact(concept: str, unit: str, row: dict[str, object]) -> Fact | None:
    form = as_text(row.get("form"))
    if form not in FACT_FORMS:
        return None
    raw_value = row.get("val")
    if isinstance(raw_value, bool) or not isinstance(raw_value, int | Decimal):
        raise FilingsDataError(f"{concept}: val is not a number: {raw_value!r}")
    fy = row.get("fy")
    return Fact(
        concept=concept,
        unit=unit,
        start=optional_date(row.get("start"), f"{concept} start"),
        end=as_date(row.get("end"), f"{concept} end"),
        value=Decimal(raw_value),
        form=form,
        filed=as_date(row.get("filed"), f"{concept} filed"),
        accession=as_text(row.get("accn")),
        fiscal_year=fy if isinstance(fy, int) and not isinstance(fy, bool) else None,
        fiscal_period=as_text(row.get("fp")),
    )


# The Key numbers table


@dataclass(frozen=True, slots=True)
class Period:
    """A column: a fiscal year or a quarter, named by its last day."""

    kind: Literal["year", "quarter"]
    end: date
    start: date | None = None

    @property
    def label(self) -> str:
        if self.kind == "year":
            return f"Year to {self.end:%Y-%m-%d}"
        return f"3 months to {self.end:%Y-%m-%d}"


@dataclass(frozen=True, slots=True)
class Cell:
    """One figure, where it came from, or why there is none."""

    value: Decimal | None
    concept: str = ""
    form: str = ""
    filed: date | None = None
    start: date | None = None
    end: date | None = None
    derived: str = ""
    missing: str = ""

    @property
    def source(self) -> str:
        """The words for the cell's title attribute: the concept, the form and the period."""
        if self.value is None:
            return self.missing
        period = (
            f"{self.start:%Y-%m-%d} to {self.end:%Y-%m-%d}"
            if self.start and self.end
            else (f"on {self.end:%Y-%m-%d}" if self.end else "")
        )
        filed = f" filed {self.filed:%Y-%m-%d}" if self.filed else ""
        text = f"{self.concept}, {self.form}{filed}, {period}".strip(", ")
        return f"{text}; derived: {self.derived}" if self.derived else text


NOT_TAGGED = "not reported under a standard tag"


@dataclass(frozen=True, slots=True)
class Row:
    key: str
    label: str
    unit: str
    years: list[Cell]
    quarters: list[Cell]
    derived: bool = False

    @property
    def concepts_used(self) -> list[str]:
        used: list[str] = []
        for cell in [*self.years, *self.quarters]:
            for name in cell.concept.split(" less "):
                if name and name not in used:
                    used.append(name)
        return used


@dataclass(frozen=True, slots=True)
class KeyNumbers:
    years: list[Period]
    quarters: list[Period]
    rows: list[Row] = field(default_factory=list[Row])

    @property
    def empty(self) -> bool:
        return not self.years and not self.quarters


def quarter_facts(facts: Sequence[Fact]) -> list[Fact]:
    """The three-month figures of one concept and unit: those reported as a quarter, then the
    ones derived from two year-to-date figures with the same start (six months less three, nine
    less six, the year less nine), where no quarter was reported for that end."""
    direct = [f for f in facts if f.days is not None and f.days in QUARTER_DAYS]
    have = {f.end for f in direct}
    derived: list[Fact] = []
    spans = sorted((f for f in facts if f.start is not None), key=lambda f: f.end)
    for longer in spans:
        if longer.end in have:
            continue
        for shorter in spans:
            if shorter.start != longer.start or shorter.end >= longer.end:
                continue
            gap = (longer.end - shorter.end).days
            if gap not in QUARTER_DAYS:
                continue
            derived.append(
                replace(
                    longer,
                    start=shorter.end + timedelta(days=1),
                    value=longer.value - shorter.value,
                    derived_from=(
                        f"{longer.start:%Y-%m-%d} to {longer.end:%Y-%m-%d} less "
                        f"{shorter.start:%Y-%m-%d} to {shorter.end:%Y-%m-%d}"
                    ),
                )
            )
            have.add(longer.end)
            break
    return sorted([*direct, *derived], key=lambda f: f.end)


def periods(facts: Sequence[Fact]) -> tuple[list[Period], list[Period]]:
    """The columns: the newest `YEARS_SHOWN` fiscal years a 10-K reports a duration line for,
    and the newest `QUARTERS_SHOWN` quarters any duration line has a three-month figure for."""
    durations = {line.key: line for line in LINES if line.kind == "duration"}
    year_ends: dict[date, date | None] = {}
    quarter_ends: dict[date, date | None] = {}
    for group in grouped(facts).values():
        first = group[0]
        if not any(
            first.concept in line.concepts and first.unit == line.unit
            for line in durations.values()
        ):
            continue
        for fact in group:
            if fact.form in ANNUAL_FORMS and fact.days is not None and fact.days in YEAR_DAYS:
                year_ends.setdefault(fact.end, fact.start)
        for fact in quarter_facts(group):
            quarter_ends.setdefault(fact.end, fact.start)
    years = [
        Period("year", end, year_ends[end]) for end in sorted(year_ends, reverse=True)[:YEARS_SHOWN]
    ]
    quarters = [
        Period("quarter", end, quarter_ends[end])
        for end in sorted(quarter_ends, reverse=True)[:QUARTERS_SHOWN]
    ]
    return years, quarters


def grouped(facts: Iterable[Fact]) -> dict[tuple[str, str], list[Fact]]:
    groups: dict[tuple[str, str], list[Fact]] = {}
    for fact in facts:
        groups.setdefault((fact.concept, fact.unit), []).append(fact)
    return groups


def cell_for(line: LineSpec, period: Period, groups: dict[tuple[str, str], list[Fact]]) -> Cell:
    """The first concept of the line's list with a figure for the period: a duration of the
    period's length ending on its last day, or a value on that day."""
    for concept in line.concepts:
        group = groups.get((concept, line.unit), [])
        if not group:
            continue
        candidates: list[Fact]
        if line.kind == "instant":
            candidates = [f for f in group if f.start is None and f.end == period.end]
        elif period.kind == "year":
            candidates = [
                f
                for f in group
                if f.end == period.end and f.days is not None and f.days in YEAR_DAYS
            ]
        else:
            candidates = [f for f in quarter_facts(group) if f.end == period.end]
        if candidates:
            fact = max(candidates, key=lambda f: (not f.derived_from, f.filed))
            return Cell(
                value=fact.value,
                concept=concept,
                form=fact.form,
                filed=fact.filed,
                start=fact.start,
                end=fact.end,
                derived=fact.derived_from,
            )
    return Cell(None, missing=NOT_TAGGED)


def free_cash_flow(operating: Cell, capex: Cell) -> Cell:
    """Operating cash flow less capital expenditure, for the same period; with either missing,
    the reason. Companies report capital expenditure as a positive payment."""
    if operating.value is None or capex.value is None:
        which = "operating cash flow" if operating.value is None else "capital expenditure"
        return Cell(None, missing=f"not worked out: {which} is {NOT_TAGGED}")
    steps = "operating cash flow less capital expenditure"
    if operating.derived or capex.derived:
        steps += ", from derived quarters"
    return Cell(
        value=operating.value - capex.value,
        concept=f"{operating.concept} less {capex.concept}",
        form=operating.form,
        filed=max(d for d in (operating.filed, capex.filed) if d is not None)
        if operating.filed or capex.filed
        else None,
        start=operating.start,
        end=operating.end,
        derived=steps,
    )


def key_numbers(facts: Sequence[Fact]) -> KeyNumbers:
    """The table: one row per line in `LINES`, with free cash flow derived after capital
    expenditure, over the newest fiscal years and quarters."""
    years, quarters = periods(facts)
    groups = grouped(facts)
    rows: list[Row] = []
    by_key: dict[str, Row] = {}
    for line in LINES:
        row = Row(
            line.key,
            line.label,
            line.unit,
            [cell_for(line, period, groups) for period in years],
            [cell_for(line, period, groups) for period in quarters],
        )
        rows.append(row)
        by_key[line.key] = row
        if line.key == "capex":
            operating = by_key["operating_cash_flow"]
            fcf = Row(
                "free_cash_flow",
                "Free cash flow (derived)",
                "USD",
                [free_cash_flow(o, c) for o, c in zip(operating.years, row.years, strict=True)],
                [
                    free_cash_flow(o, c)
                    for o, c in zip(operating.quarters, row.quarters, strict=True)
                ],
                derived=True,
            )
            rows.append(fcf)
            by_key[fcf.key] = fcf
    return KeyNumbers(years, quarters, rows)


def short_number(value: Decimal, unit: str) -> str:
    """A large figure in plain words: '$478.83 billion', '-$1.20 million' or
    '14.53 billion shares'."""
    sign = "-" if value < 0 else ""
    size = abs(value)
    for limit, word in (
        (Decimal(10) ** 12, "trillion"),
        (Decimal(10) ** 9, "billion"),
        (Decimal(10) ** 6, "million"),
    ):
        if size >= limit:
            amount = f"{size / limit:,.2f} {word}"
            break
    else:
        amount = f"{size:,.0f}"
    if unit == "USD":
        return f"{sign}${amount}"
    if unit == "shares":
        return f"{sign}{amount} shares"
    return f"{sign}{amount} {unit}"
