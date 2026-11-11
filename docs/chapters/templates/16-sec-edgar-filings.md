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

{{file:tests/fixtures/sec/companyfacts-CORPX.json|json}}

Take the other four (`company_tickers.json`, `company_tickers_mf.json`, `submissions-CORPX.json`,
`submissions-TRUSTX.json`) from the tag: `git checkout v16 -- tests/fixtures/sec`.

Listing 16-3, Filename: `tests/test_ch16.py`:

{{file:tests/test_ch16.py}}

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

{{file:src/invest_witus/filings.py}}

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

{{file:src/invest_witus_site/filings/models.py}}

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

{{file:src/invest_witus_site/filings/sec.py}}

### 16.5 Refreshing a symbol, and the nightly step

`resolve` answers "what is this symbol?" from the stored row when it was checked in the last day, otherwise from
the maps, which this process reads at most once a day. `refresh_symbol` stops early for a fund or an unlisted
symbol. `refresh_watched` is the cron's step: only symbols whose data is older than 20 hours, so a cron delivered
twice asks for nothing the second time.

Listing 16-9, Filename: `src/invest_witus_site/filings/refresh.py`:

{{file:src/invest_witus_site/filings/refresh.py}}

Then the step in `prices/views.py`'s cron, after the profiles and before the paper orders:

```python
    if settings.SEC_FILINGS_ENABLED:
        body["filings"] = refresh_watched().as_dict()
```

And the command for a laptop and for the day the cron is broken:

Listing 16-10, Filename: `src/invest_witus_site/filings/management/commands/refresh_filings.py`:

{{file:src/invest_witus_site/filings/management/commands/refresh_filings.py}}

### 16.6 The page, the partials and the button

`page.py` turns the stored rows back into the library's values and the library's values into words; nothing on
the page asks the SEC.

Listing 16-11, Filename: `src/invest_witus_site/filings/page.py`:

{{file:src/invest_witus_site/filings/page.py}}

Listing 16-12, Filename: `src/invest_witus_site/filings/views.py`:

{{file:src/invest_witus_site/filings/views.py}}

The two partials. `_filings.html` is included once in `watchlist/history.html`, after **About**; it includes
`_key_numbers.html`. The bars reuse chapter 14's `.rank-bars` track, one group per line.

Listing 16-13, Filename: `src/invest_witus_site/filings/templates/filings/_filings.html`:

{{file:src/invest_witus_site/filings/templates/filings/_filings.html}}

Listing 16-14, Filename: `src/invest_witus_site/filings/templates/filings/_key_numbers.html`:

{{file:src/invest_witus_site/filings/templates/filings/_key_numbers.html}}

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
