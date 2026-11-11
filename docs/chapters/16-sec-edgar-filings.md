# Chapter 16: Reading what the company reports: SEC EDGAR

**Starts from:** tag `v15`, plus the reference's work between chapters (step 16.0). **Ends at:** tag `v16`.
**Written against:** Python 3.14.10, uv 0.13.6, Django 5.2.18 and httpx 0.28.1.
**Goal:** every public company in the United States files its annual report (10-K), its quarterly reports (10-Q)
and its reports of major events (8-K) with the Securities and Exchange Commission, and the SEC publishes all of it
free, as web pages and as JSON. This chapter puts a company's last eight filings on a watched stock's page, each a
link that opens the SEC's own copy, and draws its **Key numbers** (revenue, net income, cash flow, capital
expenditure, free cash flow, shares, cash and debt) for five years and four quarters from the figures the company
tagged in those filings. A fund says it has no company filings. Every figure says which form, which period and
which tag it came from.
**Time:** 3 to 4 hours for the code and tests. The laptop walk-through takes 15 minutes.

## What you will learn

- **HTTP as a polite client:** a declared `User-Agent`, `Accept-Encoding`, a timeout, and one place in the code
  that every request goes through.
- **A rate limit you keep yourself:** a throttle shared by every thread of the process, and a pause written to the
  database when the server says no, so every other process waits too.
- **Caching at two levels:** a big file read at most once a day per process, and a small answer per symbol kept in
  a row with the time it was checked.
- **Nested JSON with a schema you do not control:** parallel lists, figures keyed by dates, the same number
  reported three times, and a type check at every step instead of a crash three functions later.
- **Choosing between names:** companies call revenue by different tags, so each line tries a short list in order
  and says which one it used.
- **Deriving what is not stated,** and saying so: a quarter from two year-to-date totals, free cash flow from two
  lines.
- **A template partial** included in an existing page, and a server-drawn bar chart that needs no script.

## Before the code: what the SEC publishes, and the rules for asking

We read the SEC's pages on November 10, 2026.

**The rules.** "Accessing EDGAR Data" (U.S. Securities and Exchange Commission [SEC], 2024) sets the terms for
automated access: "Current max request rate: 10 requests/second"; callers are asked to "declare your user agent in
request headers" and to send `Accept-Encoding: gzip, deflate`; and to "moderate requests to minimize server load".
The page's sample User-Agent is a company name and an admin email. It names no penalty and no length for a block.

**The data.** The SEC's API page (SEC, 2025) describes two JSON documents per company, both addressed by the
company's Central Index Key (CIK) written as ten digits with leading zeros:

- `https://data.sec.gov/submissions/CIK##########.json`: "Each entity's current filing history", with the
  company's name, its `entityType` and, under `filings.recent`, one list per column (`form`, `filingDate`,
  `reportDate`, `accessionNumber`, `primaryDocument`), newest first.
- `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`: "all the company concepts data for a company
  into a single API call". Each figure sits at `facts.<taxonomy>.<concept>.units.<unit>` with its `start` (missing
  for a balance-sheet value), `end`, `val`, `form`, `filed` and the filing's accession number.

The page says neither API needs "any authentication or API keys". It does not name the ticker-to-CIK map; we
fetched `https://www.sec.gov/files/company_tickers.json` (companies) and `company_tickers_mf.json` (mutual funds
and ETFs) and read their shape.

**Why link, not embed.** A filing on sec.gov answers with `X-Frame-Options: SAMEORIGIN`, so a browser refuses to
show it inside another site's page (checked November 2, 2026). The page links to the SEC's copy in a new tab; the
app never copies a filing.

**How to read a 10-K.** The SEC's own guide (SEC, 2011) lists the 10-K's items in their fixed order. Four answer
most questions: Item 1 (Business), Item 1A (Risk Factors), Item 7 (Management's Discussion and Analysis) and Item 8
(Financial Statements). The page's help note says this in a sentence each and links the guide.

**Decision 1: build it, with the app's name as the User-Agent.** BAM answered the design note's three questions
with its recommendations: build it now; the User-Agent is the app's name and address, never a person's email
(the ecosystem rule); funds are skipped in this version. The SEC answered 200 to that User-Agent on November 2 and
November 10, 2026. Row 177.

**Decision 2: four requests a second, one throttle, one pause.** Ten is the ceiling, so the app stays at four.
Every request waits in one `Throttle` for the whole process. A 403 or 429 writes one `SecPause` row for ten
minutes (our choice; the page names no length), and every request in every process reads it first. Row 178.

**Decision 3: four models, replaced whole.** `SecCompany` (what the ticker maps say a symbol is, checked once a
day), `Filing` (the last eight reports), `KeyFact` (the figures of the table's tags, seven years) and `SecPause`.
A refresh deletes a symbol's filings and figures and writes the new ones in one transaction. Row 179.

**Decision 4: a fund is skipped, and said.** A ticker in the fund map, a holding you marked ETF or Mutual fund,
or a filer that files fund forms (a prospectus, a shareholder report) and no 10-K is a fund: "No company filings:
this is a fund; see the issuer's page." Row 180.

**Decision 5: a figure is keyed by its own dates.** A figure's `fy` is the fiscal year of the filing that
reported it, not of the figure (a 10-K repeats last year's numbers with this year's `fy`), so the table keys every
figure by its start and end. The latest filing wins, so a restated number replaces the original. Row 181.

## Steps

### 16.0 Take the work between chapters

Between `v15` and this chapter the reference took five pieces of work that are not chapters (decisions 172 to 176,
plus error pages that keep the header): a Practice or Real badge beside every account name, version 2 of the
index rules with each month judged by the version it was closed under, stronger table stripes, PostHog page views
on signed-in pages, and 404 and 500 pages with the site's header and footer. Take them from the commit this chapter
starts from, then migrate:

Listing 16-1, Terminal:

```sh
git fetch reference --tags
git checkout 9b8ed3e -- src tests .env.example vercel.json
uv run --env-file .env python manage.py migrate
uv run pytest -q
```

```text
Operations to perform:
  Apply all migrations: accounts, admin, auth, contenttypes, holdings, methods, outbox, pages, paper, prices, reports, sessions, watchlist
Running migrations:
  Applying methods.0006_monthlyreview_rules_version... OK
1068 passed
```

Commit that as its own step (`git commit -am "Take the reference's work between chapters 15 and 16"`).

### 16.1 The tests

Start red. The fixtures are five small JSON files shaped like the SEC's, with a placeholder company (`CORPX`), a
placeholder fund (`FUNDX`) and a trust that files fund forms (`TRUSTX`). Write them first; the numbers are small
enough to check by hand: revenue of 260, 280, then 830 for nine months and 1,100 for the year, so the third
quarter is 830 less 540 and the fourth 1,100 less 830.

Listing 16-2, Filename: `tests/fixtures/sec/companyfacts-CORPX.json`:

```json
{
 "cik": 1234567,
 "entityName": "Placeholder Corp",
 "facts": {
  "dei": {
   "EntityCommonStockSharesOutstanding": {
    "units": {
     "shares": [
      {
       "end": "2026-02-01",
       "val": 999000,
       "accn": "0001234567-26-000002",
       "fy": 2025,
       "fp": "FY",
       "form": "10-K",
       "filed": "2026-02-10"
      }
     ]
    }
   }
  },
  "us-gaap": {
   "Revenues": {
    "label": "Revenues",
    "units": {
     "USD": [
      {
       "start": "2023-01-01",
       "end": "2023-12-31",
       "val": 890,
       "accn": "0001234567-24-000010",
       "fy": 2023,
       "fp": "FY",
       "form": "10-K",
       "filed": "2024-02-15"
      },
      {
       "start": "2023-01-01",
       "end": "2023-12-31",
       "val": 900,
       "accn": "0001234567-25-000010",
       "fy": 2024,
       "fp": "FY",
       "form": "10-K",
       "filed": "2025-02-15"
      },
      {
       "start": "2024-01-01",
       "end": "2024-12-31",
       "val": 1000,
       "accn": "0001234567-25-000010",
       "fy": 2024,
       "fp": "FY",
       "form": "10-K",
       "filed": "2025-02-15"
      },
      {
       "start": "2024-01-01",
       "end": "2024-12-31",
       "val": 1000,
       "accn": "0001234567-26-000002",
       "fy": 2025,
       "fp": "FY",
       "form": "10-K",
       "filed": "2026-02-10"
      },
      {
       "start": "2025-01-01",
       "end": "2025-03-31",
       "val": 260,
       "accn": "0001234567-25-000009",
       "fy": 2025,
       "fp": "Q1",
       "form": "10-Q",
       "filed": "2025-05-01"
      },
      {
       "start": "2025-01-01",
       "end": "2025-06-30",
       "val": 540,
       "accn": "0001234567-25-000007",
       "fy": 2025,
       "fp": "Q2",
       "form": "10-Q",
       "filed": "2025-08-01"
      },
      {
       "start": "2025-04-01",
       "end": "2025-06-30",
       "val": 280,
       "accn": "0001234567-25-000007",
       "fy": 2025,
       "fp": "Q2",
       "form": "10-Q",
       "filed": "2025-08-01"
      },
      {
       "start": "2025-01-01",
       "end": "2025-09-30",
       "val": 830,
       "accn": "0001234567-25-000004",
       "fy": 2025,
       "fp": "Q3",
       "form": "10-Q",
       "filed": "2025-11-01"
      },
      {
       "start": "2025-01-01",
       "end": "2025-12-31",
       "val": 1100,
       "accn": "0001234567-26-000002",
       "fy": 2025,
       "fp": "FY",
       "form": "10-K",
       "filed": "2026-02-10"
      },
      {
       "start": "2025-01-01",
       "end": "2025-12-31",
       "val": 1100,
       "accn": "0001234567-26-000001",
       "fy": 2025,
       "fp": "FY",
       "form": "8-K",
       "filed": "2026-02-20"
      },
      {
       "start": "2019-01-01",
       "end": "2019-12-31",
       "val": 500,
       "accn": "0001234567-20-000001",
       "fy": 2019,
       "fp": "FY",
       "form": "10-K",
       "filed": "2020-02-15"
      }
     ]
    }
   },
   "ProfitLoss": {
    "units": {
     "USD": [
      {
       "start": "2024-01-01",
       "end": "2024-12-31",
       "val": 80,
       "accn": "0001234567-25-000010",
       "fy": 2024,
       "fp": "FY",
       "form": "10-K",
       "filed": "2025-02-15"
      },
      {
       "start": "2025-01-01",
       "end": "2025-12-31",
       "val": -50,
       "accn": "0001234567-26-000002",
       "fy": 2025,
       "fp": "FY",
       "form": "10-K",
       "filed": "2026-02-10"
      }
     ]
    }
   },
   "NetCashProvidedByUsedInOperatingActivities": {
    "units": {
     "USD": [
      {
       "start": "2024-01-01",
       "end": "2024-12-31",
       "val": 250,
       "accn": "0001234567-25-000010",
       "fy": 2024,
       "fp": "FY",
       "form": "10-K",
       "filed": "2025-02-15"
      },
      {
       "start": "2025-01-01",
       "end": "2025-09-30",
       "val": 210,
       "accn": "0001234567-25-000004",
       "fy": 2025,
       "fp": "Q3",
       "form": "10-Q",
       "filed": "2025-11-01"
      },
      {
       "start": "2025-01-01",
       "end": "2025-12-31",
       "val": 300,
       "accn": "0001234567-26-000002",
       "fy": 2025,
       "fp": "FY",
       "form": "10-K",
       "filed": "2026-02-10"
      }
     ]
    }
   },
   "PaymentsToAcquirePropertyPlantAndEquipment": {
    "units": {
     "USD": [
      {
       "start": "2025-01-01",
       "end": "2025-09-30",
       "val": 70,
       "accn": "0001234567-25-000004",
       "fy": 2025,
       "fp": "Q3",
       "form": "10-Q",
       "filed": "2025-11-01"
      },
      {
       "start": "2025-01-01",
       "end": "2025-12-31",
       "val": 100,
       "accn": "0001234567-26-000002",
       "fy": 2025,
       "fp": "FY",
       "form": "10-K",
       "filed": "2026-02-10"
      }
     ]
    }
   },
   "CommonStockSharesOutstanding": {
    "units": {
     "shares": [
      {
       "end": "2025-12-31",
       "val": 1000000,
       "accn": "0001234567-26-000002",
       "fy": 2025,
       "fp": "FY",
       "form": "10-K",
       "filed": "2026-02-10"
      },
      {
       "end": "2025-09-30",
       "val": 1010000,
       "accn": "0001234567-25-000004",
       "fy": 2025,
       "fp": "Q3",
       "form": "10-Q",
       "filed": "2025-11-01"
      }
     ]
    }
   },
   "LongTermDebtNoncurrent": {
    "units": {
     "USD": [
      {
       "end": "2025-12-31",
       "val": 400,
       "accn": "0001234567-26-000002",
       "fy": 2025,
       "fp": "FY",
       "form": "10-K",
       "filed": "2026-02-10"
      }
     ]
    }
   },
   "AccountsPayableCurrent": {
    "units": {
     "USD": [
      {
       "end": "2025-12-31",
       "val": 12,
       "accn": "0001234567-26-000002",
       "fy": 2025,
       "fp": "FY",
       "form": "10-K",
       "filed": "2026-02-10"
      }
     ]
    }
   },
   "EarningsPerShareBasic": {
    "units": {
     "USD/shares": [
      {
       "start": "2025-01-01",
       "end": "2025-12-31",
       "val": 1.25,
       "accn": "0001234567-26-000002",
       "fy": 2025,
       "fp": "FY",
       "form": "10-K",
       "filed": "2026-02-10"
      }
     ]
    }
   }
  }
 }
}
```

Take the other four (`company_tickers.json`, `company_tickers_mf.json`, `submissions-CORPX.json`,
`submissions-TRUSTX.json`) from the tag: `git checkout v16 -- tests/fixtures/sec`.

Listing 16-3, Filename: `tests/test_ch16.py`:

```python
"""Chapter 16's checkpoint: reading what a company reports, from SEC EDGAR.

The first half checks the pure library (`invest_witus.filings`) on hand-made JSON in
`tests/fixtures/sec/`, shaped like the SEC's documents as read on November 10, 2026; the numbers
are small enough to check by hand. The second half runs the app's client, the refresh, the
nightly step, the button, the command and the symbol page against an `httpx.MockTransport`.
Nothing here reaches sec.gov. The symbols, names and CIKs are placeholders, not real securities.
"""

import json
from datetime import date, timedelta
from decimal import Decimal
from html import unescape
from io import StringIO
from pathlib import Path

import httpx
import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client
from django.utils import timezone
from pytest_django.fixtures import Settings

from invest_witus import filings as lib
from invest_witus_site.filings import refresh, sec
from invest_witus_site.filings.models import Filing, KeyFact, SecCompany, SecPause
from invest_witus_site.holdings.models import Account, Holding
from invest_witus_site.prices.models import ManualRun
from invest_witus_site.settings import DEFAULT_SEC_USER_AGENT, sec_filings_enabled
from invest_witus_site.watchlist.models import WatchItem

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sec"
USER_AGENT = "Invest.WitUS (https://invest.witus.online)"
SECRET = "test-only-cron-secret-0123456789"
CRON = "/api/cron/pull-prices/"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text("utf-8")


def facts(since: date | None = None) -> list[lib.Fact]:
    return lib.parse_companyfacts(fixture("companyfacts-CORPX.json"), since=since)


def numbers() -> lib.KeyNumbers:
    return lib.key_numbers(facts())


def row(table: lib.KeyNumbers, key: str) -> lib.Row:
    return next(each for each in table.rows if each.key == key)


# --- Names and addresses -------------------------------------------------------------------------


def test_a_symbol_is_written_the_way_edgar_writes_it() -> None:
    assert lib.sec_ticker(" class.b ") == "CLASS-B"
    assert lib.sec_ticker("CORPX") == "CORPX"


def test_the_cik_has_ten_digits_with_leading_zeros_and_nothing_else_is_a_cik() -> None:
    assert lib.padded_cik(1234567) == "0001234567"
    assert lib.padded_cik("0001234567") == "0001234567"
    for bad in ("12a", "", "12345678901", "-1"):
        with pytest.raises(lib.FilingsDataError):
            lib.padded_cik(bad)


def test_the_three_addresses_on_sec_gov() -> None:
    assert lib.submissions_url(1234567) == "https://data.sec.gov/submissions/CIK0001234567.json"
    assert (
        lib.companyfacts_url("1234567")
        == "https://data.sec.gov/api/xbrl/companyfacts/CIK0001234567.json"
    )
    assert (
        lib.document_url("0001234567", "0001234567-26-000002", "corpx-2.htm")
        == "https://www.sec.gov/Archives/edgar/data/1234567/000123456726000002/corpx-2.htm"
    )


# --- The ticker maps -----------------------------------------------------------------------------


def test_the_company_map_keeps_the_first_row_of_a_ticker() -> None:
    companies = lib.parse_company_tickers(fixture("company_tickers.json"))
    assert companies["CORPX"] == lib.Listing(1234567, "PLACEHOLDER CORP")
    assert set(companies) == {"CORPX", "TRUSTX", "CLASS-B"}


def test_the_fund_map_reads_its_columns_from_fields() -> None:
    funds = lib.parse_fund_tickers(fixture("company_tickers_mf.json"))
    assert funds["FUNDX"] == lib.Listing(3333333, "", fund=True)
    reordered = json.dumps({"fields": ["symbol", "cik"], "data": [["FUNDZ", 4]]})
    assert lib.parse_fund_tickers(reordered)["FUNDZ"].cik == 4
    with pytest.raises(lib.FilingsDataError, match="no cik or symbol"):
        lib.parse_fund_tickers(json.dumps({"fields": ["a"], "data": []}))


def test_classify_a_fund_a_company_a_share_class_and_nothing() -> None:
    companies = lib.parse_company_tickers(fixture("company_tickers.json"))
    funds = lib.parse_fund_tickers(fixture("company_tickers_mf.json"))
    assert lib.classify("fundx", companies, funds)[0] == "fund"
    assert lib.classify("CORPX", companies, funds) == ("company", companies["CORPX"])
    assert lib.classify("CLASS.B", companies, funds)[0] == "company"
    assert lib.classify("NONEX", companies, funds) == ("not listed", None)


# --- The submissions feed ------------------------------------------------------------------------


def test_submissions_become_rows_newest_first_with_their_dates() -> None:
    feed = lib.parse_submissions(fixture("submissions-CORPX.json"))
    assert (feed.cik, feed.name, feed.entity_type) == (1234567, "Placeholder Corp", "operating")
    assert feed.filings[0].form == "4"
    assert feed.filings[2].form == "10-K"
    assert feed.filings[2].report_date == date(2025, 12, 31)
    assert feed.filings[5].report_date is None, "an empty reportDate is no date"


def test_the_list_is_the_last_eight_10k_10q_and_8k_with_amendments() -> None:
    feed = lib.parse_submissions(fixture("submissions-CORPX.json"))
    chosen = lib.recent_reports(feed.filings)
    assert len(chosen) == 8
    assert [row.form for row in chosen] == [
        "8-K", "10-K", "8-K/A", "10-Q", "8-K", "10-Q", "8-K", "10-Q",
    ]  # fmt: skip
    assert "4" not in {row.form for row in chosen} and "S-8" not in {row.form for row in chosen}
    assert chosen[1].url(feed.cik).endswith("/1234567/000123456726000002/corpx-2.htm")


def test_a_column_shorter_than_the_forms_is_refused() -> None:
    body = json.loads(fixture("submissions-CORPX.json"))
    body["filings"]["recent"]["filingDate"].pop()
    with pytest.raises(lib.FilingsDataError, match="filingDate has 12 entries for 13 forms"):
        lib.parse_submissions(json.dumps(body))
    with pytest.raises(lib.FilingsDataError, match="not JSON"):
        lib.parse_submissions("<html>")


def test_a_trust_that_files_fund_forms_and_no_10k_is_a_fund() -> None:
    assert lib.is_fund_filer(lib.parse_submissions(fixture("submissions-TRUSTX.json")))
    assert not lib.is_fund_filer(lib.parse_submissions(fixture("submissions-CORPX.json")))


# --- The companyfacts feed -----------------------------------------------------------------------


def test_only_the_table_s_concepts_from_10k_and_10q_are_kept() -> None:
    kept = facts()
    assert {fact.concept for fact in kept} == {
        "us-gaap:Revenues",
        "us-gaap:ProfitLoss",
        "us-gaap:NetCashProvidedByUsedInOperatingActivities",
        "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
        "us-gaap:CommonStockSharesOutstanding",
        "us-gaap:LongTermDebtNoncurrent",
    }, "no dei cover-page count, no payables, no per-share figure"
    assert {fact.form for fact in kept} <= {"10-K", "10-Q"}, "the 8-K's copy is left out"
    assert all(isinstance(fact.value, Decimal) for fact in kept)


def test_a_figure_reported_twice_keeps_the_latest_filing() -> None:
    year_2023 = [
        f for f in facts() if f.concept == "us-gaap:Revenues" and f.end == date(2023, 12, 31)
    ]
    assert len(year_2023) == 1
    assert year_2023[0].value == Decimal(900), "restated in the next 10-K, not the original 890"
    assert year_2023[0].filed == date(2025, 2, 15)


def test_since_leaves_out_older_figures() -> None:
    assert any(f.end.year == 2019 for f in facts())
    assert not any(f.end.year == 2019 for f in facts(since=date(2020, 1, 1)))


def test_a_value_on_one_day_has_no_start_and_no_length() -> None:
    shares = next(f for f in facts() if f.concept == "us-gaap:CommonStockSharesOutstanding")
    assert shares.start is None and shares.days is None
    revenue = next(f for f in facts() if f.concept == "us-gaap:Revenues")
    assert revenue.days == 365


def test_a_value_that_is_not_a_number_is_refused() -> None:
    body = json.loads(fixture("companyfacts-CORPX.json"))
    body["facts"]["us-gaap"]["Revenues"]["units"]["USD"][0]["val"] = "lots"
    with pytest.raises(lib.FilingsDataError, match="val is not a number"):
        lib.parse_companyfacts(json.dumps(body))


# --- Quarters, years and the concept per line ----------------------------------------------------


def test_quarters_reported_directly_and_derived_from_year_to_date() -> None:
    revenue = [f for f in facts() if f.concept == "us-gaap:Revenues"]
    quarters = {f.end: f for f in lib.quarter_facts(revenue)}
    assert quarters[date(2025, 3, 31)].value == 260 and not quarters[date(2025, 3, 31)].derived_from
    assert quarters[date(2025, 6, 30)].value == 280, "the reported quarter, not 540 less 260"
    assert not quarters[date(2025, 6, 30)].derived_from
    third = quarters[date(2025, 9, 30)]
    assert third.value == 290 and third.start == date(2025, 7, 1)
    assert third.derived_from == "2025-01-01 to 2025-09-30 less 2025-01-01 to 2025-06-30"
    fourth = quarters[date(2025, 12, 31)]
    assert fourth.value == 270, "the year less nine months"
    assert fourth.form == "10-K"


def test_the_columns_are_the_newest_years_and_quarters() -> None:
    table = numbers()
    assert [p.end for p in table.years] == [
        date(2025, 12, 31), date(2024, 12, 31), date(2023, 12, 31), date(2019, 12, 31),
    ]  # fmt: skip
    assert [p.end for p in table.quarters] == [
        date(2025, 12, 31), date(2025, 9, 30), date(2025, 6, 30), date(2025, 3, 31),
    ]  # fmt: skip
    assert table.years[0].label == "Year to 2025-12-31"
    assert table.quarters[0].label == "3 months to 2025-12-31"


def test_each_line_takes_the_first_concept_it_finds_and_names_it() -> None:
    income = row(numbers(), "net_income")
    assert income.years[0].value == Decimal(-50)
    assert income.years[0].concept == "us-gaap:ProfitLoss", "NetIncomeLoss is not reported"
    assert (
        income.years[0].source
        == "us-gaap:ProfitLoss, 10-K filed 2026-02-10, 2025-01-01 to 2025-12-31"
    )
    assert income.concepts_used == ["us-gaap:ProfitLoss"]


def test_a_line_with_no_known_concept_says_so_instead_of_a_blank() -> None:
    cash = row(numbers(), "cash")
    assert all(cell.value is None for cell in [*cash.years, *cash.quarters])
    assert cash.years[0].missing == "not reported under a standard tag"
    assert cash.concepts_used == []


def test_a_value_on_one_day_is_read_on_the_period_s_last_day() -> None:
    shares = row(numbers(), "shares")
    assert [cell.value for cell in shares.quarters] == [
        Decimal(1000000),
        Decimal(1010000),
        None,
        None,
    ]
    assert shares.quarters[0].source.endswith("on 2025-12-31")


def test_free_cash_flow_is_derived_and_says_why_when_it_cannot_be() -> None:
    fcf = row(numbers(), "free_cash_flow")
    assert fcf.derived and fcf.label == "Free cash flow (derived)"
    assert fcf.years[0].value == Decimal(200)
    assert fcf.years[0].derived == "operating cash flow less capital expenditure"
    assert fcf.years[1].value is None
    assert (
        fcf.years[1].missing
        == "not worked out: capital expenditure is not reported under a standard tag"
    )
    assert fcf.quarters[0].value == Decimal(60), "(300 - 210) less (100 - 70)"
    assert "derived quarters" in fcf.quarters[0].derived


def test_free_cash_flow_comes_right_after_capital_expenditure() -> None:
    assert [each.key for each in numbers().rows] == [
        "revenue", "net_income", "operating_cash_flow", "capex", "free_cash_flow",
        "shares", "cash", "long_term_debt",
    ]  # fmt: skip


def test_no_figures_make_an_empty_table() -> None:
    assert lib.key_numbers([]).empty


@pytest.mark.parametrize(
    ("value", "unit", "words"),
    [
        (Decimal("478830000000"), "USD", "$478.83 billion"),
        (Decimal("-1200000"), "USD", "-$1.20 million"),
        (Decimal("14532259000"), "shares", "14.53 billion shares"),
        (Decimal("2500000000000"), "USD", "$2.50 trillion"),
        (Decimal("950"), "USD", "$950"),
    ],
)
def test_large_figures_in_plain_words(value: Decimal, unit: str, words: str) -> None:
    assert lib.short_number(value, unit) == words


# --- The client ----------------------------------------------------------------------------------


class FakeSec:
    """Answers the five documents from the fixtures, a status per path when told to, and
    records every request."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.status: dict[str, int] = {}
        self.bodies: dict[str, str] = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path in self.status:
            return httpx.Response(self.status[path], text="refused")
        if path in self.bodies:
            return httpx.Response(200, text=self.bodies[path])
        names = {
            "/files/company_tickers.json": "company_tickers.json",
            "/files/company_tickers_mf.json": "company_tickers_mf.json",
            "/submissions/CIK0001234567.json": "submissions-CORPX.json",
            "/submissions/CIK0007654321.json": "submissions-TRUSTX.json",
            "/api/xbrl/companyfacts/CIK0001234567.json": "companyfacts-CORPX.json",
        }
        if path not in names:
            return httpx.Response(404, text="not found")
        return httpx.Response(200, text=fixture(names[path]))

    def paths(self) -> list[str]:
        return [request.url.path for request in self.requests]


@pytest.fixture
def fake_sec(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> FakeSec:
    fake = FakeSec()
    settings.SEC_FILINGS_ENABLED = True
    monkeypatch.setattr(sec, "transport", httpx.MockTransport(fake))
    return fake


@pytest.mark.django_db
def test_every_request_declares_the_app_and_asks_for_gzip(fake_sec: FakeSec) -> None:
    refresh.refresh_symbol("CORPX")
    assert len(fake_sec.requests) == 4
    for request in fake_sec.requests:
        assert request.headers["User-Agent"] == USER_AGENT
        assert request.headers["Accept-Encoding"] == "gzip, deflate"
        assert "@" not in request.headers["User-Agent"], "never a person's email"


def test_the_throttle_spaces_requests_four_a_second(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [100.0]
    slept: list[float] = []

    def fake_sleep(seconds: float) -> None:
        slept.append(round(seconds, 6))

    monkeypatch.setattr(sec, "clock", lambda: now[0])
    monkeypatch.setattr(sec, "sleep", fake_sleep)
    throttle = sec.Throttle(4)
    for _ in range(4):
        throttle.wait()
    assert slept == [0.25, 0.5, 0.75], "the first goes at once, then one every quarter second"
    now[0] = 200.0
    throttle.wait()
    assert slept == [0.25, 0.5, 0.75], "after a quiet second, no wait"
    assert sec.REQUESTS_PER_SECOND == 4 and sec.REQUESTS_PER_SECOND < 10


@pytest.mark.django_db
@pytest.mark.parametrize("status", [403, 429])
def test_a_refusal_pauses_every_request_for_ten_minutes(fake_sec: FakeSec, status: int) -> None:
    fake_sec.status["/files/company_tickers.json"] = status
    with pytest.raises(sec.SecError) as refused:
        refresh.refresh_symbol("CORPX")
    assert refused.value.retry_later and refused.value.status == status
    pause = SecPause.objects.get()
    assert pause.status == status
    assert timedelta(minutes=9) < pause.until - timezone.now() <= timedelta(minutes=10)
    sent = len(fake_sec.requests)
    with pytest.raises(sec.SecError, match="waits until"):
        sec.get("https://data.sec.gov/submissions/CIK0001234567.json")
    assert len(fake_sec.requests) == sent, "nothing is sent during the pause"


@pytest.mark.django_db
def test_a_pause_that_has_ended_lets_requests_through(fake_sec: FakeSec) -> None:
    sec.pause(429, timezone.now() - timedelta(minutes=11))
    assert sec.paused_until() is None
    assert sec.get("https://www.sec.gov/files/company_tickers.json")


@pytest.mark.django_db
def test_a_network_failure_and_a_500_are_errors_without_a_pause(
    fake_sec: FakeSec, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_sec.status["/files/company_tickers.json"] = 500
    with pytest.raises(sec.SecError, match="answered 500") as error:
        sec.get("https://www.sec.gov/files/company_tickers.json")
    assert not error.value.retry_later
    assert not SecPause.objects.exists()

    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow", request=request)

    monkeypatch.setattr(sec, "transport", httpx.MockTransport(broken))
    with pytest.raises(sec.SecError, match="ConnectTimeout"):
        sec.get("https://www.sec.gov/files/company_tickers.json")


# --- The refresh ---------------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_company_s_refresh_stores_eight_filings_and_its_figures(fake_sec: FakeSec) -> None:
    done = refresh.refresh_symbol("corpx")
    assert (done.symbol, done.kind, done.filings) == ("CORPX", "company", 8)
    assert fake_sec.paths() == [
        "/files/company_tickers.json",
        "/files/company_tickers_mf.json",
        "/submissions/CIK0001234567.json",
        "/api/xbrl/companyfacts/CIK0001234567.json",
    ]
    company = SecCompany.objects.get(symbol="CORPX")
    assert (company.cik, company.name, company.problem) == ("0001234567", "Placeholder Corp", "")
    assert company.filings_fetched_at and company.facts_fetched_at
    newest = Filing.objects.filter(symbol="CORPX").order_by("-filing_date").first()
    assert newest is not None and newest.form == "8-K"
    assert newest.document_url.startswith("https://www.sec.gov/Archives/edgar/data/1234567/")
    assert KeyFact.objects.filter(symbol="CORPX").count() == done.facts > 0


@pytest.mark.django_db
def test_a_second_refresh_in_a_day_reads_no_ticker_map_and_replaces_the_rows(
    fake_sec: FakeSec,
) -> None:
    refresh.refresh_symbol("CORPX")
    refresh.forget_maps()
    fake_sec.requests.clear()
    refresh.refresh_symbol("CORPX")
    assert fake_sec.paths() == [
        "/submissions/CIK0001234567.json",
        "/api/xbrl/companyfacts/CIK0001234567.json",
    ], "the stored CIK is good for a day"
    assert Filing.objects.filter(symbol="CORPX").count() == 8, "replaced, not doubled"


@pytest.mark.django_db
def test_the_maps_are_read_once_a_day_per_process(fake_sec: FakeSec) -> None:
    now = timezone.now()
    refresh.ticker_maps(now)
    refresh.ticker_maps(now + timedelta(hours=23))
    assert len(fake_sec.requests) == 2
    refresh.ticker_maps(now + timedelta(hours=25))
    assert len(fake_sec.requests) == 4


@pytest.mark.django_db
def test_a_fund_in_the_fund_map_asks_for_nothing_more(fake_sec: FakeSec) -> None:
    done = refresh.refresh_symbol("FUNDX")
    assert done.kind == "fund"
    assert len(fake_sec.requests) == 2, "the two maps only"
    assert not Filing.objects.filter(symbol="FUNDX").exists()


@pytest.mark.django_db
def test_a_symbol_held_as_an_etf_is_a_fund_without_a_request(
    fake_sec: FakeSec, django_user_model: type[User]
) -> None:
    owner = django_user_model.objects.create_user("holder")
    account = Account.objects.create(owner=owner, name="Real", broker="Example Broker")
    Holding.objects.create(account=account, symbol="CORPX", kind=Holding.Kind.ETF)
    assert refresh.refresh_symbol("CORPX").kind == "fund"
    assert fake_sec.requests == []


@pytest.mark.django_db
def test_a_trust_in_the_company_map_that_files_fund_forms_is_a_fund(fake_sec: FakeSec) -> None:
    done = refresh.refresh_symbol("TRUSTX")
    assert done.kind == "fund"
    assert SecCompany.objects.get(symbol="TRUSTX").kind == "fund"
    assert "/api/xbrl/companyfacts/CIK0007654321.json" not in fake_sec.paths()


@pytest.mark.django_db
def test_an_unlisted_symbol_is_not_listed(fake_sec: FakeSec) -> None:
    assert refresh.refresh_symbol("NONEX").kind == "not listed"
    assert SecCompany.objects.get(symbol="NONEX").cik == ""


@pytest.mark.django_db
def test_a_company_with_no_companyfacts_keeps_its_filings(fake_sec: FakeSec) -> None:
    fake_sec.status["/api/xbrl/companyfacts/CIK0001234567.json"] = 404
    done = refresh.refresh_symbol("CORPX")
    assert done.filings == 8 and done.facts == 0
    assert done.note == "SEC EDGAR has no XBRL figures for this company"


@pytest.mark.django_db
def test_a_failed_refresh_keeps_the_old_rows_and_the_problem(fake_sec: FakeSec) -> None:
    refresh.refresh_symbol("CORPX")
    fake_sec.bodies["/submissions/CIK0001234567.json"] = "not json"
    with pytest.raises(lib.FilingsDataError):
        refresh.refresh_symbol("CORPX")
    company = SecCompany.objects.get(symbol="CORPX")
    assert company.problem.startswith("unexpected data: not JSON")
    assert Filing.objects.filter(symbol="CORPX").count() == 8


# --- The nightly step ----------------------------------------------------------------------------


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("owner")


@pytest.fixture
def account(owner: User) -> Account:
    account = Account.objects.create(owner=owner, name="Practice", broker="Example Broker")
    for symbol in ("CORPX", "FUNDX", "NONEX"):
        WatchItem.objects.create(account=account, symbol=symbol)
    return account


@pytest.fixture
def cron(settings: Settings, tmp_path: Path) -> None:
    settings.CRON_SECRET = SECRET
    settings.TIINGO_API_KEY = ""
    settings.PRICES_CSV_DIR = tmp_path


def call_cron(client: Client) -> dict[str, object]:
    return client.get(CRON, headers={"Authorization": f"Bearer {SECRET}"}).json()


@pytest.mark.django_db
def test_the_cron_refreshes_every_watched_symbol_once(
    client: Client, fake_sec: FakeSec, account: Account, cron: None
) -> None:
    body = call_cron(client)
    assert body["filings"] == {
        "refreshed": ["CORPX"],
        "funds": ["FUNDX"],
        "not_listed": ["NONEX"],
        "failed": {},
        "skipped": [],
        "stopped": "",
    }
    sent = len(fake_sec.requests)
    again = call_cron(client)
    assert again["filings"]["refreshed"] == [], "a repeated cron asks for nothing"  # type: ignore[index]
    assert len(fake_sec.requests) == sent


@pytest.mark.django_db
def test_the_cron_stops_at_a_refusal_and_lists_the_rest(
    client: Client, fake_sec: FakeSec, account: Account, cron: None
) -> None:
    fake_sec.status["/submissions/CIK0001234567.json"] = 429
    body = call_cron(client)
    step = body["filings"]
    assert step["stopped"] == "refused"  # type: ignore[index]
    assert "CORPX" in step["failed"]  # type: ignore[index]
    assert step["skipped"] == ["FUNDX", "NONEX"]  # type: ignore[index]
    assert "requests" in body, "the prices stand"


@pytest.mark.django_db
def test_the_cron_stops_at_its_time_limit(fake_sec: FakeSec, account: Account) -> None:
    run = refresh.refresh_watched(time_limit=-1.0)
    assert run.stopped == "time limit" and run.skipped == ["CORPX", "FUNDX", "NONEX"]
    assert fake_sec.requests == []


@pytest.mark.django_db
def test_the_cron_body_is_unchanged_with_filings_off(
    client: Client, account: Account, cron: None
) -> None:
    assert "filings" not in call_cron(client)


@pytest.mark.django_db
def test_a_symbol_whose_refresh_failed_is_due_again(fake_sec: FakeSec, account: Account) -> None:
    now = timezone.now()
    refresh.refresh_watched(now)
    assert refresh.due_symbols(now) == []
    SecCompany.objects.filter(symbol="CORPX").update(problem="SEC EDGAR answered 500")
    assert refresh.due_symbols(now) == ["CORPX"]
    assert refresh.due_symbols(now + timedelta(hours=21)) == ["CORPX", "FUNDX", "NONEX"]


# --- The command ---------------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_command_refreshes_named_symbols_and_prints_the_user_agent(fake_sec: FakeSec) -> None:
    out = StringIO()
    call_command("refresh_filings", "corpx", "fundx", stdout=out)
    text = out.getvalue()
    assert f"User-Agent: {USER_AGENT}" in text
    assert "CORPX: company, 8 filing(s)" in text
    assert "FUNDX: fund, 0 filing(s)" in text


@pytest.mark.django_db
def test_the_command_refuses_with_filings_off_or_nothing_named(settings: Settings) -> None:
    with pytest.raises(CommandError, match="SEC_FILINGS=off"):
        call_command("refresh_filings", "CORPX")
    settings.SEC_FILINGS_ENABLED = True
    with pytest.raises(CommandError, match="at least one symbol"):
        call_command("refresh_filings")


@pytest.mark.django_db
def test_the_command_reports_a_refusal(fake_sec: FakeSec) -> None:
    fake_sec.status["/files/company_tickers.json"] = 403
    err = StringIO()
    with pytest.raises(CommandError):
        call_command("refresh_filings", "CORPX", stdout=StringIO(), stderr=err)
    assert "answered 403" in err.getvalue()


# --- The symbol page -----------------------------------------------------------------------------


def page(account: Account, symbol: str = "CORPX") -> str:
    return f"/accounts/{account.pk}/watch/{symbol}/"


def button(account: Account, symbol: str = "CORPX") -> str:
    return f"/accounts/{account.pk}/watch/{symbol}/filings/"


def text(response: object) -> str:
    return unescape(response.content.decode())  # type: ignore[attr-defined]


@pytest.mark.django_db
def test_the_page_lists_the_filings_with_links_that_open_on_sec_gov(
    client: Client, fake_sec: FakeSec, owner: User, account: Account
) -> None:
    refresh.refresh_symbol("CORPX")
    client.force_login(owner)
    response = client.get(page(account))
    assert response.status_code == 200
    body = text(response)
    assert '<h2 id="filings-heading">Filings</h2>' in body
    link = (
        '<a href="https://www.sec.gov/Archives/edgar/data/1234567/000123456726000002/corpx-2.htm" '
        'target="_blank" rel="noopener">Read the 10-K on sec.gov'
    )
    assert link in body
    assert body.count('target="_blank" rel="noopener">Read the ') == 8
    assert "Annual report" in body and "Current report (a major event), amended" in body
    assert f"Source: SEC EDGAR, fetched {timezone.localdate():%Y-%m-%d}" in body


@pytest.mark.django_db
def test_the_page_shows_key_numbers_with_their_form_period_and_concept(
    client: Client, fake_sec: FakeSec, owner: User, account: Account
) -> None:
    refresh.refresh_symbol("CORPX")
    client.force_login(owner)
    body = text(client.get(page(account)))
    assert '<h3 id="key-numbers-heading">Key numbers</h3>' in body
    assert "Year to 2025-12-31" in body and "3 months to 2025-12-31" in body
    assert (
        'title="us-gaap:Revenues, 10-K filed 2026-02-10, 2025-01-01 to 2025-12-31">$1,100' in body
    )
    assert "10-Q, derived" in body
    assert "Free cash flow (derived)" in body
    assert "not reported under a standard tag" in body
    assert "<strong>How to read this.</strong>" in body
    assert f"Source: SEC EDGAR (XBRL), as of {timezone.localdate():%Y-%m-%d}" in body
    assert "Revenue, net income and free cash flow by fiscal year" in body
    assert 'class="bar-down"' in body, "the loss is drawn left of the zero line"


@pytest.mark.django_db
def test_the_page_links_the_sec_s_guide_to_reading_a_10k(
    client: Client, owner: User, account: Account, settings: Settings
) -> None:
    settings.SEC_FILINGS_ENABLED = True
    client.force_login(owner)
    body = text(client.get(page(account)))
    assert "<summary>How to read a 10-K</summary>" in body
    assert 'href="https://www.sec.gov/answers/reada10k.htm" target="_blank" rel="noopener"' in body
    assert "No filings stored yet." in body and "Refresh filings now" in body


@pytest.mark.django_db
def test_a_fund_says_it_has_no_company_filings(
    client: Client, fake_sec: FakeSec, owner: User, account: Account
) -> None:
    refresh.refresh_symbol("FUNDX")
    client.force_login(owner)
    body = text(client.get(page(account, "FUNDX")))
    assert "No company filings: this is a fund; see the issuer's page." in body
    assert "Key numbers" not in body


@pytest.mark.django_db
def test_an_unlisted_symbol_says_edgar_lists_no_company(
    client: Client, fake_sec: FakeSec, owner: User, account: Account
) -> None:
    refresh.refresh_symbol("NONEX")
    client.force_login(owner)
    assert "SEC EDGAR lists no company under NONEX." in text(client.get(page(account, "NONEX")))


@pytest.mark.django_db
def test_a_pause_shows_filings_are_not_available_with_the_last_list(
    client: Client, fake_sec: FakeSec, owner: User, account: Account
) -> None:
    refresh.refresh_symbol("CORPX")
    sec.pause(429)
    client.force_login(owner)
    response = client.get(page(account))
    assert response.status_code == 200
    body = text(response)
    assert "Filings are not available right now." in body
    assert "SEC EDGAR answered 429" in body
    assert "The list below is the last one stored." in body
    assert "Traceback" not in body


@pytest.mark.django_db
def test_the_page_says_filings_are_off_and_offers_no_button(
    client: Client, owner: User, account: Account
) -> None:
    client.force_login(owner)
    body = text(client.get(page(account)))
    assert "Filings are off on this copy of the app" in body
    assert "Refresh filings now" not in body


# --- Refresh filings now -------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_button_fetches_and_says_what_it_stored(
    client: Client, fake_sec: FakeSec, owner: User, account: Account
) -> None:
    client.force_login(owner)
    response = client.post(button(account), follow=True)
    assert response.redirect_chain[-1][0] == page(account) + "#filings-heading"
    body = text(response)
    assert "Fetched CORPX's filings from SEC EDGAR: 8 filings listed" in body
    assert ManualRun.objects.filter(kind=ManualRun.Kind.FILINGS, key="CORPX").exists()


@pytest.mark.django_db
def test_a_second_press_inside_ten_minutes_is_refused_without_a_request(
    client: Client, fake_sec: FakeSec, owner: User, account: Account
) -> None:
    client.force_login(owner)
    client.post(button(account))
    sent = len(fake_sec.requests)
    body = text(client.post(button(account), follow=True))
    assert "less than 10 minutes ago" in body
    assert len(fake_sec.requests) == sent


@pytest.mark.django_db
@pytest.mark.parametrize("status", [403, 429])
def test_a_refusal_during_the_button_is_a_message_not_an_error(
    client: Client, fake_sec: FakeSec, owner: User, account: Account, status: int
) -> None:
    fake_sec.status["/files/company_tickers.json"] = status
    client.force_login(owner)
    response = client.post(button(account), follow=True)
    assert response.status_code == 200
    body = text(response)
    assert f"Filings are not available right now: SEC EDGAR answered {status}" in body


@pytest.mark.django_db
def test_data_it_cannot_read_is_a_message_not_an_error(
    client: Client, fake_sec: FakeSec, owner: User, account: Account
) -> None:
    fake_sec.bodies["/submissions/CIK0001234567.json"] = "[]"
    client.force_login(owner)
    response = client.post(button(account), follow=True)
    assert response.status_code == 200
    assert "SEC EDGAR sent data this app could not read" in text(response)


@pytest.mark.django_db
def test_the_button_needs_a_sign_in_a_post_the_owner_and_a_watched_symbol(
    client: Client, fake_sec: FakeSec, owner: User, account: Account, django_user_model: type[User]
) -> None:
    signed_out = client.post(button(account))
    assert signed_out.status_code == 302 and "login" in signed_out["Location"]
    client.force_login(owner)
    assert client.get(button(account)).status_code == 405
    assert client.post(button(account, "OTHERX")).status_code == 404
    someone = django_user_model.objects.create_user("someone")
    client.force_login(someone)
    assert client.post(button(account)).status_code == 404
    assert fake_sec.requests == []


@pytest.mark.django_db
def test_the_button_with_filings_off_says_so(client: Client, owner: User, account: Account) -> None:
    client.force_login(owner)
    assert "Filings are off on this copy" in text(client.post(button(account), follow=True))


# --- Settings and the public pages ---------------------------------------------------------------


def test_the_default_user_agent_is_the_app_name_and_address_and_off_means_off() -> None:
    assert DEFAULT_SEC_USER_AGENT == USER_AGENT
    assert "@" not in DEFAULT_SEC_USER_AGENT, "never a person's email"
    assert sec_filings_enabled("") and sec_filings_enabled("on")
    assert not sec_filings_enabled(" OFF ") and not sec_filings_enabled("off")


def test_env_example_lists_the_two_names() -> None:
    text_ = (Path(__file__).resolve().parent.parent / ".env.example").read_text("utf-8")
    assert "\nSEC_USER_AGENT=\n" in text_ and "\nSEC_FILINGS=\n" in text_


@pytest.mark.django_db
def test_no_public_page_mentions_filings(client: Client) -> None:
    for path in ("/", "/faq/", "/privacy/", "/terms/"):
        body = text(client.get(path))
        assert "Key numbers" not in body and "sec.gov/Archives" not in body
```

One more change in `tests/conftest.py`: an autouse fixture that turns filings off in every test and points the SEC
client at a transport that fails the test, so chapter 08's cron tests keep their body and no test reaches sec.gov.

Run them: every test fails on the first import, `invest_witus.filings`.

### 16.2 The library, with no Django

Plain values in and out, like chapter 15's `compare.py`. Read three functions closely. `parse_submissions` turns
parallel lists into rows and refuses a column shorter than the forms, instead of an `IndexError` later.
`quarter_facts` finds the three-month figures: those reported as a quarter, then those derived from two
year-to-date figures with the same start that end about a quarter apart. `cell_for` walks a line's tags in order
and takes the first that has a figure for the period.

Listing 16-4, Filename: `src/invest_witus/filings.py`:

```python
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
```

Try it before any page exists:

Listing 16-5, Terminal:

```sh
uv run python - <<'PY'
from pathlib import Path
from invest_witus import filings as lib

text = Path("tests/fixtures/sec/companyfacts-CORPX.json").read_text()
table = lib.key_numbers(lib.parse_companyfacts(text))
print([p.label for p in table.quarters])
for row in table.rows[:5]:
    print(row.label, [c.value if c.value is not None else c.missing for c in row.quarters])
print(table.rows[0].quarters[1].source)
PY
```

```text
['3 months to 2025-12-31', '3 months to 2025-09-30', '3 months to 2025-06-30', '3 months to 2025-03-31']
Revenue [Decimal('270'), Decimal('290'), Decimal('280'), Decimal('260')]
Net income ['not reported under a standard tag', 'not reported under a standard tag', 'not reported under a standard tag', 'not reported under a standard tag']
Operating cash flow [Decimal('90'), 'not reported under a standard tag', 'not reported under a standard tag', 'not reported under a standard tag']
Capital expenditure [Decimal('30'), 'not reported under a standard tag', 'not reported under a standard tag', 'not reported under a standard tag']
Free cash flow (derived) [Decimal('60'), 'not worked out: operating cash flow is not reported under a standard tag', 'not worked out: operating cash flow is not reported under a standard tag', 'not worked out: operating cash flow is not reported under a standard tag']
us-gaap:Revenues, 10-Q filed 2025-11-01, 2025-07-01 to 2025-09-30; derived: 2025-01-01 to 2025-09-30 less 2025-01-01 to 2025-06-30
```

The third quarter's revenue is 290, worked out and labelled. Operating cash flow has no third quarter: the 10-Q
reported nine months and there is no six-month figure to subtract, so the cell says so.

### 16.3 The models

Listing 16-6, Filename: `src/invest_witus_site/filings/models.py`:

```python
"""A company's recent filings and key numbers from SEC EDGAR, kept in the app's own tables so a
page never asks the SEC (chapter 16, decisions 177 to 184).

`SecCompany` is what EDGAR says a symbol is (a company with a CIK, a fund, or not listed), checked
against the ticker maps at most once a day. `Filing` holds the last eight 10-K, 10-Q and 8-K
filings, `KeyFact` the figures of the Key numbers table's concepts, both replaced whole on each
refresh. `SecPause` is the one row that says the SEC refused us (403 or 429) and until when the
app leaves it alone, shared by every Vercel function through the database.
"""

import datetime
from decimal import Decimal
from typing import Any

from django.db import models

CIK_LENGTH = 10
FORM_MAX = 20
CONCEPT_MAX = 120
# The three kinds, as the strings the column holds (compared as strings, like `Account.kind`).
COMPANY = "company"
FUND = "fund"
NOT_LISTED = "not listed"


class SecCompany(models.Model):
    """One row per symbol: the CIK the ticker map gave it, what kind of filer it is, and when
    the filings and the figures were last stored."""

    class Kind(models.TextChoices):
        COMPANY = COMPANY, "Company"
        FUND = FUND, "Fund"
        NOT_LISTED = NOT_LISTED, "Not listed with the SEC"

    symbol: models.CharField[str, str] = models.CharField(max_length=20, unique=True)
    cik: models.CharField[str, str] = models.CharField(
        max_length=CIK_LENGTH, blank=True, help_text="Ten digits with leading zeros."
    )
    name: models.CharField[str, str] = models.CharField(max_length=200, blank=True)
    kind: models.CharField[str, str] = models.CharField(
        max_length=20, choices=Kind.choices, default=Kind.NOT_LISTED
    )
    checked_at: models.DateTimeField[datetime.datetime, datetime.datetime] = models.DateTimeField(
        help_text="When the ticker maps were last read for this symbol."
    )
    filings_fetched_at: models.DateTimeField[datetime.datetime | None, datetime.datetime | None] = (
        models.DateTimeField(null=True, blank=True)
    )
    facts_fetched_at: models.DateTimeField[datetime.datetime | None, datetime.datetime | None] = (
        models.DateTimeField(null=True, blank=True)
    )
    problem: models.CharField[str, str] = models.CharField(
        max_length=300, blank=True, help_text="Why the last refresh failed; empty after a good one."
    )
    problem_at: models.DateTimeField[datetime.datetime | None, datetime.datetime | None] = (
        models.DateTimeField(null=True, blank=True)
    )

    class Meta:
        ordering = ["symbol"]
        verbose_name = "SEC company"
        verbose_name_plural = "SEC companies"

    def __str__(self) -> str:
        return f"{self.symbol} ({self.Kind(self.kind).label})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.symbol = self.symbol.strip().upper()
        super().save(*args, **kwargs)


class Filing(models.Model):
    """One of a company's recent 10-K, 10-Q or 8-K filings, with its document's address on
    sec.gov. The page links there; it never copies the document."""

    symbol: models.CharField[str, str] = models.CharField(max_length=20)
    cik: models.CharField[str, str] = models.CharField(max_length=CIK_LENGTH)
    form: models.CharField[str, str] = models.CharField(max_length=FORM_MAX)
    filing_date: models.DateField[datetime.date, datetime.date] = models.DateField()
    report_date: models.DateField[datetime.date | None, datetime.date | None] = models.DateField(
        null=True, blank=True, help_text="The period the filing reports on, when it names one."
    )
    accession: models.CharField[str, str] = models.CharField(max_length=25)
    primary_document: models.CharField[str, str] = models.CharField(max_length=200)
    document_url: models.URLField[str, str] = models.URLField(max_length=400)
    description: models.CharField[str, str] = models.CharField(max_length=200, blank=True)
    fetched_at: models.DateTimeField[datetime.datetime, datetime.datetime] = models.DateTimeField()

    class Meta:
        ordering = ["symbol", "-filing_date", "-accession"]
        constraints = [
            models.UniqueConstraint(fields=["symbol", "accession"], name="filing_once_per_symbol")
        ]

    def __str__(self) -> str:
        return f"{self.symbol} {self.form} {self.filing_date:%Y-%m-%d}"


class KeyFact(models.Model):
    """One reported figure of a Key numbers concept. `period_start` is empty for a value on one
    day (a balance sheet line)."""

    symbol: models.CharField[str, str] = models.CharField(max_length=20)
    concept: models.CharField[str, str] = models.CharField(max_length=CONCEPT_MAX)
    unit: models.CharField[str, str] = models.CharField(max_length=20)
    period_start: models.DateField[datetime.date | None, datetime.date | None] = models.DateField(
        null=True, blank=True
    )
    period_end: models.DateField[datetime.date, datetime.date] = models.DateField()
    # Companies report whole dollars and shares; four places leave room for the few that do not.
    value: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=28, decimal_places=4
    )
    form: models.CharField[str, str] = models.CharField(max_length=FORM_MAX)
    filed: models.DateField[datetime.date, datetime.date] = models.DateField()
    accession: models.CharField[str, str] = models.CharField(max_length=25)
    fiscal_year: models.IntegerField[int | None, int | None] = models.IntegerField(
        null=True, blank=True
    )
    fiscal_period: models.CharField[str, str] = models.CharField(max_length=4, blank=True)
    fetched_at: models.DateTimeField[datetime.datetime, datetime.datetime] = models.DateTimeField()

    class Meta:
        ordering = ["symbol", "concept", "period_end"]
        indexes = [models.Index(fields=["symbol", "concept"], name="keyfact_symbol_concept")]

    def __str__(self) -> str:
        return f"{self.symbol} {self.concept} {self.period_end:%Y-%m-%d}: {self.value}"


class SecPause(models.Model):
    """The SEC's last refusal (403 or 429) and the time before which no request is sent. One
    row, id 1."""

    until: models.DateTimeField[datetime.datetime, datetime.datetime] = models.DateTimeField()
    status: models.IntegerField[int, int] = models.IntegerField()
    noted_at: models.DateTimeField[datetime.datetime, datetime.datetime] = models.DateTimeField()

    class Meta:
        verbose_name = "SEC pause"
        verbose_name_plural = "SEC pause"

    def __str__(self) -> str:
        return f"SEC answered {self.status}; paused until {self.until:%Y-%m-%d %H:%M}"
```

Add `"invest_witus_site.filings"` to `INSTALLED_APPS`, the two settings (`SEC_USER_AGENT` with the app's name as
its default, `SEC_FILINGS`, where `off` stops every request), a `FILINGS` choice on `ManualRun.Kind`, and make the
migrations:

Listing 16-7, Terminal:

```sh
uv run --env-file .env python manage.py makemigrations filings prices
uv run --env-file .env python manage.py migrate
```

```text
Migrations for 'filings':
  src/invest_witus_site/filings/migrations/0001_initial.py
    + Create model SecCompany
    + Create model SecPause
    + Create model Filing
    + Create model KeyFact
Migrations for 'prices':
  src/invest_witus_site/prices/migrations/0006_alter_manualrun_kind.py
    ~ Alter field kind on manualrun
```

### 16.4 One way to ask the SEC

Every request in the app goes through `get`. Notice the order: the pause is read before the throttle, so a
refused app sends nothing at all; the throttle takes a slot under its lock and sleeps outside it, so a waiting
thread never blocks the others from taking theirs.

Listing 16-8, Filename: `src/invest_witus_site/filings/sec.py`:

```python
"""The one way this app asks SEC EDGAR for anything: a declared User-Agent, a shared throttle,
and a pause after a refusal (chapter 16, decisions 178 and 179).

SEC's "Accessing EDGAR Data" page, read on November 10, 2026
(https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data, last reviewed
June 26, 2024) says "Current max request rate: 10 requests/second", asks callers to "declare your
user agent in request headers" (its example is a company name and an admin email) and to send
`Accept-Encoding: gzip, deflate`, and says "please moderate requests to minimize server load".
It names no penalty and no length for a block.

So every request here:
- carries `settings.SEC_USER_AGENT`, by default the app's name and address and never a person's
  email (the ecosystem rule; the SEC answered 200 to it on November 2 and 10, 2026);
- asks for gzip or deflate (httpx decodes either);
- waits its turn in `throttle`, at most `REQUESTS_PER_SECOND` (4, well under the SEC's 10) for the
  whole process;
- is not sent at all while `SecPause` says the SEC refused us: a 403 or a 429 writes that row
  for `PAUSE_MINUTES` (10, our choice: the page names no length), so every Vercel function that
  reads the database waits too, and the page says "Filings are not available right now".
"""

import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta

import httpx
from django.conf import settings
from django.utils import timezone

from invest_witus_site.filings.models import SecPause

# The seam the tests use: a `MockTransport` here and nothing leaves the process.
transport: httpx.BaseTransport | None = None
# The seams for the throttle's clock, so a test neither waits nor depends on the machine's speed.
clock: Callable[[], float] = time.monotonic
sleep: Callable[[float], None] = time.sleep

REQUESTS_PER_SECOND = 4
PAUSE_MINUTES = 10
REQUEST_TIMEOUT_SECONDS = 20.0
PAUSE_ID = 1


class SecError(Exception):
    """A request the SEC did not answer with a document. `retry_later` is True for a refusal
    (403, 429) or a pause: asking for the next symbol now would fail the same way."""

    def __init__(self, problem: str, status: int | None = None, retry_later: bool = False) -> None:
        super().__init__(problem)
        self.problem = problem
        self.status = status
        self.retry_later = retry_later


class Throttle:
    """At most `per_second` requests a second across every thread of the process: each caller
    takes the next free slot, then sleeps until it comes."""

    def __init__(self, per_second: int) -> None:
        self.interval = 1.0 / per_second
        self.lock = threading.Lock()
        self.next_at = 0.0

    def wait(self) -> None:
        with self.lock:
            now = clock()
            at = max(now, self.next_at)
            self.next_at = at + self.interval
        if at > now:
            sleep(at - now)


throttle = Throttle(REQUESTS_PER_SECOND)


def paused_until(now: datetime | None = None) -> SecPause | None:
    """The pause in force, or None."""
    now = now or timezone.now()
    return SecPause.objects.filter(pk=PAUSE_ID, until__gt=now).first()


def pause(status: int, now: datetime | None = None) -> SecPause:
    now = now or timezone.now()
    row, _ = SecPause.objects.update_or_create(
        pk=PAUSE_ID,
        defaults={
            "until": now + timedelta(minutes=PAUSE_MINUTES),
            "status": status,
            "noted_at": now,
        },
    )
    return row


def headers() -> dict[str, str]:
    return {"User-Agent": settings.SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}


def get(url: str, now: datetime | None = None) -> str:
    """One GET; the body's text, or `SecError`. A 404 is not a refusal (a company with no XBRL
    figures has no companyfacts document)."""
    held = paused_until(now)
    if held is not None:
        raise SecError(
            f"SEC EDGAR answered {held.status} at {timezone.localtime(held.noted_at):%H:%M}; "
            f"the app waits until {timezone.localtime(held.until):%H:%M %Z} before asking again",
            status=held.status,
            retry_later=True,
        )
    throttle.wait()
    try:
        with httpx.Client(transport=transport, timeout=REQUEST_TIMEOUT_SECONDS) as http:
            response = http.get(url, headers=headers())
    except httpx.HTTPError as error:
        raise SecError(f"the request failed: {type(error).__name__}") from error
    if response.status_code in (403, 429):
        pause(response.status_code, now)
        raise SecError(
            f"SEC EDGAR answered {response.status_code} (too many requests or a refused client); "
            f"the app waits {PAUSE_MINUTES} minutes before asking again",
            status=response.status_code,
            retry_later=True,
        )
    if response.status_code != 200:
        raise SecError(f"SEC EDGAR answered {response.status_code}", status=response.status_code)
    return response.text
```

### 16.5 Refreshing a symbol, and the nightly step

`resolve` answers "what is this symbol?" from the stored row when it was checked in the last day, otherwise from
the maps, which this process reads at most once a day. `refresh_symbol` stops early for a fund or an unlisted
symbol. `refresh_watched` is the cron's step: only symbols whose data is older than 20 hours, so a cron delivered
twice asks for nothing the second time.

Listing 16-9, Filename: `src/invest_witus_site/filings/refresh.py`:

```python
"""Fetching and storing: the ticker maps, one symbol's filings and figures, and the nightly run
over the watched symbols (chapter 16).

A refresh of one company is at most four requests: the two ticker maps when this process has
not read them in the last day, the submissions feed, and companyfacts. Each request waits its
turn in `sec.throttle`. The nightly run asks only for watched symbols whose data is older than
`STALE_HOURS`, so a cron delivered twice does nothing the second time, and it stops at a refusal
or at its time limit; what is left waits for the next night.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from invest_witus import filings as lib
from invest_witus_site.filings import sec
from invest_witus_site.filings.models import COMPANY, FUND, NOT_LISTED, Filing, KeyFact, SecCompany
from invest_witus_site.holdings.models import Holding
from invest_witus_site.watchlist.models import WatchItem

log = logging.getLogger(__name__)

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FUND_TICKERS_URL = "https://www.sec.gov/files/company_tickers_mf.json"
# The ticker maps change when a company lists, renames or delists: once a day is enough.
MAPS_MAX_AGE = timedelta(days=1)
# A symbol's filings are fetched again by the nightly run once this old.
STALE_HOURS = 20
# The nightly run's own ceiling, after the price pull: about 4 requests a second and two per
# symbol, so about 120 symbols fit; a longer list continues the next night.
RUN_TIME_LIMIT_SECONDS = 60.0
# Figures older than this are not stored: the table shows five years.
FACT_YEARS = 7
FUND_KINDS = (Holding.Kind.ETF, Holding.Kind.MUTUAL_FUND)


@dataclass(frozen=True, slots=True)
class TickerMaps:
    companies: dict[str, lib.Listing]
    funds: dict[str, lib.Listing]
    read_at: datetime


_maps: TickerMaps | None = None
_maps_lock = threading.Lock()


def ticker_maps(now: datetime) -> TickerMaps:
    """Both maps, from this process's copy when it is under a day old (two requests otherwise)."""
    global _maps
    with _maps_lock:
        if _maps is not None and now - _maps.read_at < MAPS_MAX_AGE:
            return _maps
    companies = lib.parse_company_tickers(sec.get(TICKERS_URL, now))
    funds = lib.parse_fund_tickers(sec.get(FUND_TICKERS_URL, now))
    fresh = TickerMaps(companies, funds, now)
    with _maps_lock:
        _maps = fresh
    return fresh


def forget_maps() -> None:
    """Drop this process's copy of the maps (the tests start each from nothing)."""
    global _maps
    with _maps_lock:
        _maps = None


def held_as_fund(symbol: str) -> bool:
    """The owner marked the symbol an ETF or a mutual fund on a holding (chapter 05)."""
    return Holding.objects.filter(symbol=symbol, kind__in=FUND_KINDS).exists()


def resolve(symbol: str, now: datetime) -> SecCompany:
    """What EDGAR says the symbol is, from the stored row when it was checked in the last day."""
    stored = SecCompany.objects.filter(symbol=symbol).first()
    if stored is not None and now - stored.checked_at < MAPS_MAX_AGE:
        return stored
    if held_as_fund(symbol):
        kind, listing = SecCompany.Kind.FUND, None
    else:
        maps = ticker_maps(now)
        found, listing = lib.classify(symbol, maps.companies, maps.funds)
        kind = SecCompany.Kind(found)
    company = stored or SecCompany(symbol=symbol)
    company.kind = kind
    company.cik = lib.padded_cik(listing.cik) if listing is not None else ""
    if listing is not None and listing.title:
        company.name = listing.title
    company.checked_at = now
    company.save()
    return company


def store_filings(company: SecCompany, submissions: lib.Submissions, now: datetime) -> int:
    rows = lib.recent_reports(submissions.filings)
    with transaction.atomic():
        Filing.objects.filter(symbol=company.symbol).delete()
        Filing.objects.bulk_create(
            Filing(
                symbol=company.symbol,
                cik=company.cik,
                form=row.form,
                filing_date=row.filed,
                report_date=row.report_date,
                accession=row.accession,
                primary_document=row.primary_document,
                document_url=row.url(company.cik),
                description=row.description[:200],
                fetched_at=now,
            )
            for row in rows
        )
    return len(rows)


def store_facts(symbol: str, facts: list[lib.Fact], now: datetime) -> int:
    with transaction.atomic():
        KeyFact.objects.filter(symbol=symbol).delete()
        KeyFact.objects.bulk_create(
            KeyFact(
                symbol=symbol,
                concept=fact.concept,
                unit=fact.unit,
                period_start=fact.start,
                period_end=fact.end,
                value=fact.value,
                form=fact.form,
                filed=fact.filed,
                accession=fact.accession,
                fiscal_year=fact.fiscal_year,
                fiscal_period=fact.fiscal_period[:4],
                fetched_at=now,
            )
            for fact in facts
        )
    return len(facts)


@dataclass
class Refreshed:
    """What one symbol's refresh did."""

    symbol: str
    kind: str
    filings: int = 0
    facts: int = 0
    note: str = ""


def refresh_symbol(symbol: str, now: datetime | None = None) -> Refreshed:
    """Resolve the symbol, then for a company store its recent filings and its figures. A fund
    or an unlisted symbol stops after the maps, with its stored filings removed. Raises
    `sec.SecError` (the row keeps the problem) or `lib.FilingsDataError`."""
    now = now or timezone.now()
    symbol = symbol.strip().upper()
    company: SecCompany | None = None
    try:
        company = resolve(symbol, now)
        if company.kind != COMPANY:
            Filing.objects.filter(symbol=symbol).delete()
            KeyFact.objects.filter(symbol=symbol).delete()
            mark_good(company, filings=False, facts=False, now=now)
            return Refreshed(symbol, company.kind)
        submissions = lib.parse_submissions(sec.get(lib.submissions_url(company.cik), now))
        if lib.is_fund_filer(submissions):
            company.kind = SecCompany.Kind.FUND
            company.save(update_fields=["kind"])
            Filing.objects.filter(symbol=symbol).delete()
            KeyFact.objects.filter(symbol=symbol).delete()
            mark_good(company, filings=False, facts=False, now=now)
            return Refreshed(symbol, company.kind)
        if submissions.name:
            company.name = submissions.name[:200]
        result = Refreshed(symbol, company.kind)
        result.filings = store_filings(company, submissions, now)
        try:
            text = sec.get(lib.companyfacts_url(company.cik), now)
        except sec.SecError as error:
            if error.status != 404:
                raise
            text = '{"facts": {}}'
            result.note = "SEC EDGAR has no XBRL figures for this company"
        since = date(now.year - FACT_YEARS, 1, 1)
        result.facts = store_facts(symbol, lib.parse_companyfacts(text, since=since), now)
        mark_good(company, filings=True, facts=True, now=now)
        return result
    except (sec.SecError, lib.FilingsDataError) as error:
        problem = error.problem if isinstance(error, sec.SecError) else f"unexpected data: {error}"
        target = company or SecCompany.objects.filter(symbol=symbol).first()
        if target is not None:
            target.problem = problem[:300]
            target.problem_at = now
            target.save(update_fields=["problem", "problem_at"])
        raise


def mark_good(company: SecCompany, filings: bool, facts: bool, now: datetime) -> None:
    company.problem = ""
    company.problem_at = None
    if filings:
        company.filings_fetched_at = now
    if facts:
        company.facts_fetched_at = now
    company.save()


@dataclass
class FilingsRun:
    """What the nightly run did, for the cron's JSON."""

    refreshed: list[str] = field(default_factory=list[str])
    funds: list[str] = field(default_factory=list[str])
    not_listed: list[str] = field(default_factory=list[str])
    failed: dict[str, str] = field(default_factory=dict[str, str])
    skipped: list[str] = field(default_factory=list[str])
    stopped: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "refreshed": self.refreshed,
            "funds": self.funds,
            "not_listed": self.not_listed,
            "failed": self.failed,
            "skipped": self.skipped,
            "stopped": self.stopped,
        }


def due_symbols(now: datetime) -> list[str]:
    """Every watched symbol with no data, or data older than `STALE_HOURS`, in order."""
    watched = sorted(set(WatchItem.objects.values_list("symbol", flat=True)))
    cutoff = now - timedelta(hours=STALE_HOURS)
    company = Q(kind=SecCompany.Kind.COMPANY, filings_fetched_at__gt=cutoff)
    other = ~Q(kind=SecCompany.Kind.COMPANY) & Q(checked_at__gt=cutoff)
    fresh = set(
        SecCompany.objects.filter(symbol__in=watched, problem="")
        .filter(company | other)
        .values_list("symbol", flat=True)
    )
    return [symbol for symbol in watched if symbol not in fresh]


def refresh_watched(
    now: datetime | None = None, time_limit: float = RUN_TIME_LIMIT_SECONDS
) -> FilingsRun:
    """The nightly step: each due watched symbol once, stopping at a refusal or the time limit."""
    now = now or timezone.now()
    run = FilingsRun()
    pending = due_symbols(now)
    started = time.monotonic()
    for index, symbol in enumerate(pending):
        if time.monotonic() - started > time_limit:
            run.skipped.extend(pending[index:])
            run.stopped = "time limit"
            break
        try:
            done = refresh_symbol(symbol, now)
        except sec.SecError as error:
            run.failed[symbol] = error.problem
            if error.retry_later:
                run.skipped.extend(pending[index + 1 :])
                run.stopped = "refused"
                break
            continue
        except lib.FilingsDataError as error:
            run.failed[symbol] = f"unexpected data: {error}"
            continue
        if done.kind == FUND:
            run.funds.append(symbol)
        elif done.kind == NOT_LISTED:
            run.not_listed.append(symbol)
        else:
            run.refreshed.append(symbol)
    log.info("filings: %s", run.as_dict())
    return run
```

Then the step in `prices/views.py`'s cron, after the profiles and before the paper orders:

```python
    if settings.SEC_FILINGS_ENABLED:
        body["filings"] = refresh_watched().as_dict()
```

And the command for a laptop and for the day the cron is broken:

Listing 16-10, Filename: `src/invest_witus_site/filings/management/commands/refresh_filings.py`:

```python
"""`manage.py refresh_filings SYMBOL [SYMBOL ...]` or `manage.py refresh_filings --watched`:
the SEC refresh by hand (chapter 16), the same code the button and the nightly step run.

Each request waits its turn in the shared throttle and carries the app's User-Agent, which the
command prints, so a refusal can be checked against what was sent.
"""

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from invest_witus import filings as lib
from invest_witus_site.filings import refresh, sec


class Command(BaseCommand):
    help = "Fetch the recent filings and key figures of one or more symbols from SEC EDGAR."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "symbols", nargs="*", help="Symbols such as CORPX (upper or lower case)."
        )
        parser.add_argument(
            "--watched", action="store_true", help="Every watched symbol that is due, as the cron."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.SEC_FILINGS_ENABLED:
            raise CommandError("Filings are off on this copy of the app (SEC_FILINGS=off).")
        self.stdout.write(f"User-Agent: {settings.SEC_USER_AGENT}")
        if options["watched"]:
            run = refresh.refresh_watched()
            self.stdout.write(f"Refreshed: {', '.join(run.refreshed) or 'none'}.")
            if run.funds:
                self.stdout.write(f"Funds, no company filings: {', '.join(run.funds)}.")
            if run.not_listed:
                self.stdout.write(f"Not listed with the SEC: {', '.join(run.not_listed)}.")
            for symbol, problem in run.failed.items():
                self.stderr.write(f"Failed {symbol}: {problem}")
            if run.skipped:
                self.stderr.write(f"Skipped ({run.stopped}): {', '.join(run.skipped)}")
            return
        if not options["symbols"]:
            raise CommandError("Name at least one symbol, or pass --watched.")
        failed = False
        for symbol in options["symbols"]:
            try:
                done = refresh.refresh_symbol(symbol)
            except (sec.SecError, lib.FilingsDataError) as error:
                self.stderr.write(f"Failed {symbol.upper()}: {error}")
                failed = True
                if isinstance(error, sec.SecError) and error.retry_later:
                    break
                continue
            note = f" ({done.note})" if done.note else ""
            self.stdout.write(
                f"{done.symbol}: {done.kind}, {done.filings} filing(s), "
                f"{done.facts} figure(s){note}."
            )
        if failed:
            raise CommandError("Some symbols failed; see above.")
```

### 16.6 The page, the partials and the button

`page.py` turns the stored rows back into the library's values and the library's values into words; nothing on
the page asks the SEC.

Listing 16-11, Filename: `src/invest_witus_site/filings/page.py`:

```python
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
```

Listing 16-12, Filename: `src/invest_witus_site/filings/views.py`:

```python
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
```

The two partials. `_filings.html` is included once in `watchlist/history.html`, after **About**; it includes
`_key_numbers.html`. The bars reuse chapter 14's `.rank-bars` track, one group per line.

Listing 16-13, Filename: `src/invest_witus_site/filings/templates/filings/_filings.html`:

```html
{# What the company reports to the SEC (chapter 16): the last eight 10-K, 10-Q and 8-K filings, each a link #}
{# to the document on sec.gov in a new tab, then the Key numbers. Included by watchlist/history.html with #}
{# `account`, `item` and the `sec_` names from filings/page.py. The owner's page only. #}
<section class="sec-filings" aria-labelledby="filings-heading">
  <h2 id="filings-heading">Filings</h2>
  {% if not sec_enabled %}
  <p class="muted">Filings are off on this copy of the app (<code>SEC_FILINGS=off</code>).</p>
  {% elif sec_is_fund %}
  <p>No company filings: this is a fund; see the issuer's page. A fund reports to the SEC on other forms (a prospectus and shareholder reports), which this app does not read.</p>
  {% elif sec_not_listed %}
  <p>SEC EDGAR lists no company under {{ item.symbol }}. Only companies registered with the SEC file a 10-K or 10-Q; a company based outside the United States may file other forms.</p>
  {% else %}
  {% if sec_unavailable %}<p role="status"><strong>Filings are not available right now.</strong> {{ sec_unavailable }}{% if sec_filings %} The list below is the last one stored.{% endif %}</p>{% endif %}
  {% if sec_filings %}
  <div class="table-scroll" role="region" aria-labelledby="filings-caption" tabindex="0">
  <table class="holdings">
    <caption id="filings-caption">{{ sec_company.name|default:item.symbol }}: the last {{ sec_filings|length }} annual, quarterly and current reports, newest first. Each link opens the filing on sec.gov in a new tab.</caption>
    <thead>
      <tr>
        <th scope="col">Filed</th>
        <th scope="col">Form</th>
        <th scope="col">What it is</th>
        <th scope="col">Period</th>
        <th scope="col">Document</th>
      </tr>
    </thead>
    <tbody>
      {% for filing, words in sec_filings %}
      <tr>
        <th scope="row">{{ filing.filing_date|date:"Y-m-d" }}</th>
        <td>{{ filing.form }}</td>
        <td>{{ words }}</td>
        <td>{% if filing.report_date %}{{ filing.report_date|date:"Y-m-d" }}{% else %}<span class="muted">none named</span>{% endif %}</td>
        <td><a href="{{ filing.document_url }}" target="_blank" rel="noopener">Read the {{ filing.form }} on sec.gov<span class="sr-only"> (opens in a new tab)</span></a></td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  </div>
  <p class="small muted">Source: SEC EDGAR, fetched {{ sec_company.filings_fetched_at|date:"Y-m-d" }}. The nightly pull refreshes it; the links go to the SEC's own copy.</p>
  {% elif not sec_unavailable %}
  <p class="muted">No filings stored yet.{% if sec_company %} SEC EDGAR lists no 10-K, 10-Q or 8-K for {{ item.symbol }}.{% else %} The nightly pull fetches them; <strong>Refresh filings now</strong> fetches them now.{% endif %}</p>
  {% endif %}
  <details class="how-to-read-10k">
    <summary>How to read a 10-K</summary>
    <p>A <strong>10-K</strong> is the company's annual report to the SEC, a <strong>10-Q</strong> its report for each of the first three quarters, and an <strong>8-K</strong> a short report of a major event (results, a merger, a new chief executive). The 10-K follows a set order. Four parts answer most questions:</p>
    <ul>
      <li><strong>Item 1, Business:</strong> what the company sells, where, and to whom.</li>
      <li><strong>Item 1A, Risk Factors:</strong> what the company says could hurt it, most important first.</li>
      <li><strong>Item 7, Management's Discussion and Analysis:</strong> management explains the year's results in its own words.</li>
      <li><strong>Item 8, Financial Statements:</strong> the audited income statement, balance sheet and cash flows, with notes. The Key numbers below come from these.</li>
    </ul>
    <p>Read a 10-Q the same way for a quarter; its statements are not audited. A figure means more beside the same figure a year earlier than on its own.</p>
    <p class="small">The SEC's guide: <a href="https://www.sec.gov/answers/reada10k.htm" target="_blank" rel="noopener">How to Read a 10-K<span class="sr-only"> (opens in a new tab)</span></a>. Information, not advice.</p>
  </details>
  {% include "filings/_key_numbers.html" %}
  {% endif %}
  {% if sec_enabled %}
  <form method="post" action="{% url 'watch-refresh-filings' account.pk item.symbol %}">
    {% csrf_token %}
    <button type="submit">Refresh filings now</button>
    <p class="small muted">Asks SEC EDGAR for {{ item.symbol }}'s filings and reported figures now: up to four requests, at most four a second, once every 10 minutes per symbol.</p>
  </form>
  {% endif %}
</section>
```

Listing 16-14, Filename: `src/invest_witus_site/filings/templates/filings/_key_numbers.html`:

```html
{# Key numbers (chapter 16): figures from the company's XBRL data in its 10-K and 10-Q filings, chosen by #}
{# `invest_witus.filings.key_numbers`. Each cell's title names the concept, the form, the filing day and the #}
{# period. The bars are drawn on the server; the table is their text alternative. No script. #}
<section class="key-numbers" aria-labelledby="key-numbers-heading">
  <h3 id="key-numbers-heading">Key numbers</h3>
  {% if sec_numbers.empty %}
  <p class="muted">No reported figures stored yet{% if sec_company.facts_fetched_at %}: the company's filings carry none of the figures this table reads{% endif %}.</p>
  {% else %}
  {% if sec_chart %}
  <figure class="rank-chart key-chart" aria-labelledby="key-chart-title">
    <figcaption>
      <p class="chart-title" id="key-chart-title">Revenue, net income and free cash flow by fiscal year, from the 10-K</p>
      <p class="small muted">One scale for every bar, so their lengths compare. {% if sec_chart.any_negative %}Bars left of the line are losses or outflows. {% endif %}Each bar is labelled with the year's last day.</p>
    </figcaption>
    {% for group in sec_chart.groups %}
    <p class="small key-chart-group">{{ group.label }}</p>
    <ol class="rank-bars">
      {% for bar in group.bars %}
      <li class="rank-bar">
        <span class="rank-label">{{ bar.label }}</span>
        <svg class="rank-track" viewBox="0 0 100 10" preserveAspectRatio="none" aria-hidden="true" focusable="false"><title>{{ group.label }}, year to {{ bar.label }}: {{ bar.text }}</title>{% if bar.direction != "none" %}<rect class="bar-{{ bar.direction }}" x="{{ bar.x }}" y="1.5" width="{{ bar.width }}" height="7" vector-effect="non-scaling-stroke"/>{% endif %}<line class="zero" x1="{{ sec_chart.zero_x }}" x2="{{ sec_chart.zero_x }}" y1="0" y2="10" vector-effect="non-scaling-stroke"/></svg>
        <span class="rank-value">{{ bar.text }}</span>
      </li>
      {% endfor %}
    </ol>
    {% endfor %}
  </figure>
  {% endif %}
  <p class="how-to-read"><strong>How to read this.</strong> Each figure is what the company reported to the SEC for that period, in its 10-K (a year) or 10-Q (a quarter); hover or focus a figure to see the exact tag, form, filing day and dates. "Derived" means the app worked it out: free cash flow is operating cash flow less capital expenditure, and a quarter a filing reports only as "year to date" is that total less the one before it (the fourth quarter is the year less nine months). Shares, cash and debt are values on the period's last day. Compare a figure with the same period a year earlier; one number on its own says little. <span class="muted">Lesson coming.</span></p>
  <div class="table-scroll" role="region" aria-labelledby="key-years-caption" tabindex="0">
  <table class="holdings key-table">
    <caption id="key-years-caption">The last {{ sec_numbers.years|length }} fiscal year{{ sec_numbers.years|length|pluralize }}, newest first</caption>
    <thead>
      <tr>
        <th scope="col">Line</th>
        {% for period in sec_numbers.years %}<th scope="col" class="num">{{ period.label }}</th>{% endfor %}
      </tr>
    </thead>
    <tbody>
      {% for row in sec_rows %}
      <tr>
        <th scope="row" title="Tags used: {{ row.concepts }}">{{ row.label }}</th>
        {% for cell in row.years %}<td class="num" title="{{ cell.title }}">{% if cell.missing %}<span class="muted small">{{ cell.text }}</span>{% else %}{{ cell.text }} <span class="small muted">{{ cell.note }}</span>{% endif %}</td>{% endfor %}
      </tr>
      {% endfor %}
    </tbody>
  </table>
  </div>
  {% if sec_numbers.quarters %}
  <div class="table-scroll" role="region" aria-labelledby="key-quarters-caption" tabindex="0">
  <table class="holdings key-table">
    <caption id="key-quarters-caption">The last {{ sec_numbers.quarters|length }} quarter{{ sec_numbers.quarters|length|pluralize }}, newest first</caption>
    <thead>
      <tr>
        <th scope="col">Line</th>
        {% for period in sec_numbers.quarters %}<th scope="col" class="num">{{ period.label }}</th>{% endfor %}
      </tr>
    </thead>
    <tbody>
      {% for row in sec_rows %}
      <tr>
        <th scope="row" title="Tags used: {{ row.concepts }}">{{ row.label }}</th>
        {% for cell in row.quarters %}<td class="num" title="{{ cell.title }}">{% if cell.missing %}<span class="muted small">{{ cell.text }}</span>{% else %}{{ cell.text }} <span class="small muted">{{ cell.note }}</span>{% endif %}</td>{% endfor %}
      </tr>
      {% endfor %}
    </tbody>
  </table>
  </div>
  {% endif %}
  <details class="small">
    <summary>Which tags each line read</summary>
    <ul>
      {% for row in sec_rows %}<li>{{ row.label }}: {{ row.concepts }}</li>{% endfor %}
    </ul>
    <p>Companies name the same figure differently (revenue may be <code>Revenues</code> or <code>RevenueFromContractWithCustomerExcludingAssessedTax</code>), so each line tries a short list in order and uses the first the company reported for that period.</p>
  </details>
  <p class="small muted">Source: SEC EDGAR (XBRL), as of {{ sec_company.facts_fetched_at|date:"Y-m-d" }}. "Not reported under a standard tag" means the company's filings use none of the tags this table reads for that line, not that the figure is zero. Information, not advice.</p>
  {% endif %}
</section>
```

Then the small changes: `**filings_context(item.symbol)` in `watchlist/views.py`'s `history`, the
`<str:symbol>/filings/` path in `watchlist/urls.py`, the admin registrations, two lines in `site.css`, and the two
names in `.env.example`. Take them from the tag if you prefer:
`git checkout v16 -- src/invest_witus_site/watchlist src/invest_witus_site/filings/admin.py`.

### 16.7 Green, and the page on your laptop

Listing 16-15, Terminal:

```sh
uv run pytest -q
uv run ruff check . && uv run ruff format --check . && uv run pyright
uv run --env-file .env python manage.py makemigrations --check --dry-run
```

```text
1138 passed
All checks passed!
288 files already formatted
0 errors, 0 warnings, 0 informations
No changes detected
```

On your laptop, set `SEC_USER_AGENT` in `.env` to your own app's name and address (never your email), put a stock
on a watch list and fetch it once:

Listing 16-16, Terminal:

```sh
uv run --env-file .env python manage.py refresh_filings AAPL
```

```text
User-Agent: Your App (https://your-app.example)
AAPL: company, 8 filing(s), 305 figure(s).
```

(The symbol is an example of a company that files with the SEC, not a pick. The figure count changes with each
filing.) Open the symbol's page: the Filings table, the Key numbers bars and both tables. Point at a figure to read
its tag and its dates. Put a fund on the watch list and press **Refresh filings now** on its page: it says it is a
fund.

### 16.8 What the owner does outside the editor

Nothing to set up: SEC EDGAR needs no key, and the default User-Agent is the app's. Merge; the migrate workflow
applies `filings/0001_initial` and `prices/0006_alter_manualrun_kind`. Open a watched stock's page and press
**Refresh filings now** once, or wait for the nightly run.

## Checkpoint

- `uv run pytest` prints `1138 passed`; ruff, pyright and `makemigrations --check` pass.
- Listing 16-5 prints the four quarters with 270, 290, 280 and 260, and a free cash flow of 60 for the fourth.
- Every request in the tests carries the app's User-Agent and `gzip, deflate`; a 403 or 429 sends nothing more
  for ten minutes.
- A fund's page says it has no company filings; a stock's page links eight filings that open on sec.gov.
- Commit and push: `git add -A && git commit -m "Chapter 16: reading what the company reports"`.

## Exercises

1. **Per-share numbers.** Add earnings per share (`us-gaap:EarningsPerShareBasic`, unit `USD/shares`) as a line.
   What does `short_number` print for it, and how would you fix that?
2. **Year over year.** Beside each fiscal year's revenue, show its change from the year before as a percent, with
   the reason where either year is missing.
3. **A reader view.** For the newest 10-K, fetch the document server-side and show Item 1A's headings as a list,
   linking the original. Write the decision first: what do the SEC's terms say about showing a filing's text, and
   how big is a 10-K's HTML?
4. **The fund side.** For a fund, read its expense ratio from the issuer's page. Which source would you trust, and
   how would the app say where the number came from?

## If you get stuck

- Browse: https://github.com/dapperAuteur/invest-witus/tree/v16
- Diff for this chapter: https://github.com/dapperAuteur/invest-witus/compare/9b8ed3e...v16 (the diff from `v15`
  also holds the work between chapters that step 16.0 takes)
- Zip: https://github.com/dapperAuteur/invest-witus/archive/v16.zip
- Take the reference's files. Chapter 16 added `src/invest_witus/filings.py`, the
  `src/invest_witus_site/filings/` app, `tests/test_ch16.py` and `tests/fixtures/sec/`; and changed
  `settings.py`, `prices/models.py` (one choice), `prices/views.py` (the cron step), `watchlist/views.py`,
  `watchlist/urls.py`, `watchlist/templates/watchlist/history.html`, `pages/static/pages/site.css`,
  `tests/conftest.py` and `.env.example`. Nothing moved:
  `git fetch reference --tags && git checkout v16 -- src tests`.
- Every page test fails with `a test tried to reach data.sec.gov`: your `fake_sec` fixture did not replace
  `sec.transport`, or the page asked the SEC; the page reads only the app's tables.
- The third quarter reads 830: `quarter_facts` matched the nine-month figure as a quarter. A quarter is 80 to 100
  days long.
- The 2023 revenue reads 890: you kept the first filing's figure, not the latest.
- Chapter 08's cron tests now find a `filings` key: the conftest fixture that turns filings off is missing.

## What we learned

- A public API still has rules. Read them, name yourself, and stay well under the ceiling.
- One function for every request is where the throttle, the pause and the headers live, and the one seam the tests
  replace.
- JSON you do not control is checked at the edge, with a sentence for each way it can be wrong.
- The same number can be reported three times; decide which one wins and write the rule down.
- A derived figure is fine when it says it is derived and shows its sum.

## Next

Chapter 17 sends signed events to CentenarianOS and checks the lesson links against Learn.WitUS.

## References

U.S. Securities and Exchange Commission. (2011, July 1). *How to read a 10-K*.
https://www.sec.gov/answers/reada10k.htm

U.S. Securities and Exchange Commission. (2024, June 26). *Accessing EDGAR data*.
https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data

U.S. Securities and Exchange Commission. (2025, April 8). *EDGAR application programming interfaces (APIs)*.
https://www.sec.gov/search-filings/edgar-application-programming-interfaces
