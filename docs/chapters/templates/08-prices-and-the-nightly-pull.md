# Chapter 08: Prices and the nightly pull

**Starts from:** tag `v07`. **Ends at:** tag `v08`.
**Written against:** Python 3.14.10, uv 0.13.6, Django 5.2.18, httpx 0.28.1, and Tiingo's documentation and
pricing pages, Alpaca's market data pages and Vercel's cron pages as read on October 28, 2026. Vendors change
their pages; when one and this text disagree, read the page again and note the date.
**Goal:** one closing price per symbol per day in the app's own table, filled once a night by a cron that
Vercel calls with a secret, and the signed-in owner's accounts valued at the latest stored close with the
close's date beside every line. No page ever asks a vendor, no public page shows a price, and the pull can run
twice without harm.
**Time:** 3 to 4 hours for the code and tests. The owner's Tiingo key and the cron secret take 15 minutes.

The listings in this chapter are not typed in by hand. `scripts/render_chapter.py` pastes the real files from
tag `v08` into the chapter text, so what you read and what the tests run are the same bytes.

## What you will learn

- **A `Protocol` as a seam:** two price sources with one shape, so the pull, the command and the cron never
  know which one answered, and the tests use the cheap one.
- **An idempotent job:** an upsert that writes each day once, counts what it did, and leaves a repeated run
  with nothing to do. Why a cron on Vercel's Hobby plan has to be written this way.
- **JSON without floats:** `json.loads(..., parse_float=Decimal)`, and a parser that refuses what it does not
  understand instead of guessing.
- **A management command** with two arguments, its own output streams, and the one error it raises.
- **A cron on Vercel:** `vercel.json`'s `crons`, UTC, the Hobby plan's hour, no retries, and the project's
  `CRON_SECRET` arriving as a bearer token, compared in constant time.
- **`login_required` and an ownership check:** a page for the signed-in owner, a 404 for anyone else, and a
  test that every public page still has no table and no link to it.
- **The newest row per group** with `values().annotate(Max())`, and a template filter.
- **A fake vendor from JSON fixtures** through httpx's `MockTransport`, as chapter 07 faked a provider.

## Before the code: what the vendors say

**Which prices, from where.** The PRD (section 7.4) and research 05 settled this for phase 1: holdings entered
from statements are valued with end-of-day closes from Tiingo's free plan, pulled once a night with the owner's
own key; holdings inside an Alpaca account carry their own prices on Alpaca's position objects and need no
feed, which is chapter 11's work. This chapter builds the first half and leaves a labeled hook for the second.
Every value is shown to the signed-in owner of the account and to nobody else, because the free plan's license
allows nothing more, and because the PRD says no public page renders a price, a chart or a holding.

**What Tiingo's pages say.** Daily prices for one ticker come from
`https://api.tiingo.com/tiingo/daily/<ticker>/prices`, with `startDate`, `endDate` and `format` as query
parameters (Tiingo, n.d.-b). The token goes in the `Authorization` header as `Token <value>`, or in a `token`
query parameter; the examples send `Content-Type: application/json` (Tiingo, n.d.-a). Each day in the answer
carries `date`, `open`, `high`, `low`, `close`, `volume`, the adjusted versions of the four prices and the
volume, `divCash` and `splitFactor`; the page shows no example body, and describes `date` only as "The date
this data pertains to" (Tiingo, n.d.-b), so the parser in this chapter reads the first ten characters of that
field, which is the date whether it arrives bare or as a timestamp, and the fixture in the tests says so. When
the numbers arrive: "Most US Equity prices are available at 5:30 PM EST, however exchanges may send corrections
until 8 PM EST", and "Mutual Fund NAVs are available after 12 AM EST", with the four price fields holding the
NAV for a fund (Tiingo, n.d.-b). The free plan, "Starter" on the pricing page and "Basic" in the overview, is
$0 for 50 requests an hour, 1,000 a day, 500 unique symbols a month and 1 GB a month; its license is "Internal
Use Only", which the page defines: "Internal use means you may only use the data for your own personal use and
you may not display or share the data with another person or organization" (Tiingo, n.d.-d). The overview adds
"We do not rate limit to minute or second" and that the daily count resets at midnight Eastern (Tiingo, n.d.-c).
For later, when other people use the app: Tiingo's developer program covers software "where their software
requires users to supply their own Tiingo API Token", with "Tiingo must be clearly attributed as the data
source" and never the user's password (Tiingo, n.d.-e). Tiingo's full Terms of Use page answered a Cloudflare
challenge to every fetch on the day of writing, as it did to the research; the owner reads it in a browser
(task 09, and PRD open item 3). Decisions log, row 70.

**What Alpaca's pages say, and why none of it is built here.** A position in a paper account carries
`current_price`, `lastday_price` ("Last day's asset price per share based on the closing value of the last
trading day") and `market_value` (Alpaca, n.d.-a). Daily bars exist too, with a `feed` parameter that defaults
to `sip`, but "iex" is "the only feed that can be used without a subscription" (Alpaca, 2026c), SIP history
needs an `end` "at least 15 minutes old" (Alpaca, 2026b), and "As an Alpaca Paper Only Account holder, you are
only entitled to receive and make use of IEX market data" (Alpaca, n.d.-b). Whether paper keys reach the data
API at all is not stated on the pages read. So Alpaca stays chapter 11's: positions for Alpaca accounts, read
from the account itself. The `source` column and the `PriceSource` Protocol below leave room for an Alpaca bars
source as research 05's backup, without a line of it written now. Decisions log, row 71.

**What Vercel's pages say about cron.** A cron is an entry in `vercel.json` with a `path` and a `schedule`;
Vercel makes "an HTTP GET request to your project's production deployment URL" at that path, with the user
agent `vercel-cron/1.0` and an `x-vercel-cron-schedule` header naming the expression that fired (Vercel,
2026a). Expressions have five fields, "The timezone is always UTC", names like `MON` are not supported, and the
day-of-month and day-of-week fields cannot both be set (Vercel, 2026a). On the Hobby plan a job runs at most
once a day, and its precision is "Per-hour (±59 min)": `0 6 * * *` fires anywhere between 06:00:00 and
06:59:59 (Vercel, 2026c). "Vercel will not retry an invocation if a cron job fails"; delivery is "best effort",
a run can be missed, and "Cron delivery can also occasionally invoke the same scheduled run more than once", so
jobs "should be resilient to both missed runs and duplicate runs", which the page spells as idempotent (Vercel,
2026b). A redirect ends the run without being followed. And the secret: add `CRON_SECRET` to the project, "a
random string of at least 16 characters", and "The value of the variable will be automatically sent as an
`Authorization` header when Vercel invokes your cron job", with the `Bearer` prefix (Vercel, 2026b). Vercel's
sample answers 401 to a bad header; this route answers 403, since there is nothing a caller could do to
authenticate interactively, and 503 when the secret is unset, so a deploy that forgot the variable fails closed
and the log says why. Decisions log, row 72.

**Three design rules that follow.** First, *the table is the product*: the page reads the table, the pull
writes it, and the vendor is spoken to once a night, which is what both the PRD's acceptance list and the free
plan's budget want. Second, *the pull is idempotent*: it asks for the last seven days every night, writes a day
only when the stored close differs, and so a missed night is filled by the next, a duplicate run writes
nothing, and a vendor's evening correction replaces its row. Third, *one symbol's refusal is not the run's*: an
unknown ticker is recorded for that symbol and the next one is tried; only a rate limit stops the run, because
the next request would fail the same way.

**The schedule.** `0 6 * * *`: 06:00 to 06:59 UTC is 01:00 to 01:59 Eastern in winter and 02:00 to 02:59 in
summer, after Tiingo's "after 12 AM EST" for fund NAVs in both halves of the year, and hours before the US
open. It runs every day; a Sunday run finds nothing new and writes nothing, at the cost of one request per
symbol against a budget of a thousand.

## Steps

### 08.1 The tests

Listing 08-1, Filename: `tests/test_ch08.py`:

{{file:tests/test_ch08.py}}

Things to notice:

- **`FakeTiingo` is the vendor as far as the app can see it.** A token header checked, a path per ticker, a
  JSON file per ticker, a 404 for a ticker without one, and `status` to force a 429 for one test. The fixture
  below has the thirteen fields the documentation lists, with made-up numbers for the placeholder symbols
  `INDEX` and `OTHER`: never real quotes.
- **`csv_folder` dates its rows relative to today,** because the cron route asks for the last seven days from
  today and the test must pass next month too. The row nine days back is outside the window on purpose.
- **`stored()` is the whole table as tuples,** `fetched_at` included. The idempotency test compares the table
  before and after a second run, not just the counts.
- **`no_pause` is `autouse`.** The real pull waits a second between symbols; the tests set the constant to zero
  and one test checks the pause is placed between symbols, not after the last.
- **The cron tests go through the HTTP client with headers,** so the route's three answers are tested as Vercel
  would see them, including a `Token` prefix and a trailing space.
- **The owner page test reads the table row by row**, with `TableRows`, the way chapter 05 read the statements
  page, and asserts the values, the dates and the words "no price yet" and "stale" in their cells.

Listing 08-2, Filename: `tests/fixtures/tiingo/INDEX.json`:

{{file:tests/fixtures/tiingo/INDEX.json|json}}

Run the tests:

Listing 08-3, Terminal:

```sh
uv run pytest tests/test_ch08.py
```

```text
tests/test_ch08.py:24: in <module>
    from invest_witus.valuation import STALE_AFTER_DAYS, Quote, value_positions
E   ModuleNotFoundError: No module named 'invest_witus.valuation'
=========================== short test summary info ============================
ERROR tests/test_ch08.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 1.32s
```

Red at import: the first module the tests name does not exist. No package is added this chapter; httpx came
with chapter 07.

### 08.2 Three names and one app

The settings gain the prices app in `INSTALLED_APPS` and three names at the end. Everything else is as chapter
07 left it.

Listing 08-4, Filename: `src/invest_witus_site/settings.py`:

{{file:src/invest_witus_site/settings.py}}

- **`TIINGO_API_KEY` is the switch between the sources.** Set, the pull talks to Tiingo; empty, it reads CSV
  files from `PRICES_CSV_DIR`, which defaults to `data/private/prices/`, inside the folder git ignores. The
  name follows the ecosystem's `*_API_KEY` habit; Tiingo's own word is "token".
- **`CRON_SECRET` is Vercel's name,** and the only one Vercel will send. Empty means the route refuses to run.

Listing 08-5, Filename: `.env.example`:

{{file:.env.example}}

### 08.3 The value math, in the library

The arithmetic is three lines and belongs beside chapter 01's `to_money`, where it needs no database and the
test can plant its own numbers.

Listing 08-6, Filename: `src/invest_witus/valuation.py`:

{{file:src/invest_witus/valuation.py}}

- **`Quote` is one close with its date and source.** The page prints all three; the PRD's acceptance list says
  "Every displayed price carries its date and source."
- **`value_line` multiplies two Decimals and rounds once,** with `to_money`. The planted example in the test is
  2.5 shares at 101.23: 253.075, which rounds half up to 253.08, the rounding chapter 01 chose. A float in
  either factor fails on the multiplication with a `TypeError`; nothing here converts.
- **No quote, no value.** A line without a close keeps `None`, is listed in `unpriced`, and stays out of the
  total. Showing zero would be a lie with a currency sign on it.
- **`stale` is a calendar test,** more than five days between the close and today. Five covers a weekend, a
  holiday and one missed night.

### 08.4 The table

Listing 08-7, Filename: `src/invest_witus_site/prices/apps.py`:

{{file:src/invest_witus_site/prices/apps.py}}

Listing 08-8, Filename: `src/invest_witus_site/prices/models.py`:

{{file:src/invest_witus_site/prices/models.py}}

- **One row per symbol per day,** and the constraint says so. The PRD sketched a unique key of security, date
  and source; the question the page asks is "what was the close that day", so the source became a column that
  records which source answered, and a second source replaces the first row rather than sitting beside it.
  Symbols stay text, as chapter 05 decided; a `Security` table can come when something needs it.
- **Six places, not two.** A close is a factor, not a money amount; it is multiplied before anything is rounded
  to cents. The same float guard as a statement line sits in `save`.
- **`upsert` is the idempotency,** in plain steps a learner can read: fetch what is stored for those days in one
  query, compare each day, insert the new ones with one `bulk_create`, save a changed one, count the rest as
  unchanged and do not touch them. `bulk_create` skips `save()` (Django Software Foundation, n.d.-d), so the
  rounding and the upper-casing happen before the rows are built. Because an unchanged row is not written,
  `fetched_at` keeps the time the number first arrived, and a repeated run leaves the table byte for byte the
  same; the first test proves it.
- **`latest_for` is two queries.** When `values()` comes before `annotate()`, "the original results are grouped
  according to the unique combinations of the fields specified in the `values()` clause" and "An annotation is
  then provided for each unique group" (Django Software Foundation, n.d.-b): one row per symbol with its newest
  date, then the rows those pairs name. A symbol with no rows is simply absent from the dictionary.

Make the migration and read it:

Listing 08-9, Terminal:

```sh
uv run --env-file .env python manage.py makemigrations prices
uv run ruff format src/invest_witus_site/prices/migrations/
```

```text
Migrations for 'prices':
  src/invest_witus_site/prices/migrations/0001_initial.py
    + Create model DailyClose
1 file reformatted, 1 file left unchanged
```

Listing 08-10, Filename: `src/invest_witus_site/prices/migrations/0001_initial.py`:

{{file:src/invest_witus_site/prices/migrations/0001_initial.py}}

Listing 08-11, Filename: `src/invest_witus_site/prices/admin.py`:

{{file:src/invest_witus_site/prices/admin.py}}

The admin page is for reading what the pull wrote. The one edit that matters is deleting a row, which makes the
next run fetch that day again.

### 08.5 The two sources

Listing 08-12, Filename: `src/invest_witus_site/prices/sources.py`:

{{file:src/invest_witus_site/prices/sources.py}}

- **`PriceSource` is a `Protocol`:** "Base class for protocol classes", used "with static type checkers that
  recognize structural subtyping (static duck-typing)" (Python Software Foundation, n.d.-c). Neither source
  inherits from it; each has a `name` and a `closes` method with the right signature, and pyright accepts both
  where a `PriceSource` is wanted. The pull never imports a vendor.
- **`PriceSourceError` is one symbol's refusal.** It carries the symbol, the problem as text, and
  `retry_later`, which only a 429 sets. The pull reads that flag to decide between "next symbol" and "stop".
- **`CsvPrices` is chapter 02 again:** `load_prices` on `<SYMBOL>.csv`, filtered to the window, and chapter
  02's errors wrapped as this chapter's. On a laptop it is the whole price feed.
- **`TiingoEod` sends the key in the header,** never in the URL, so a log that keeps URLs never keeps the key;
  the test asserts both. The `transport` seam is chapter 07's pattern: `None` in production, a `MockTransport`
  in the tests. A non-200 answer becomes a `PriceSourceError` with the status and the first 200 characters of
  the vendor's body, which names the reason (an unknown ticker, a bad token) and cannot contain the key, since
  the key was in the request.
- **`parse_tiingo` decodes with `parse_float=Decimal`.** The `json` module calls that function "with the string
  of every JSON float to be decoded", and the documentation's own example is `decimal.Decimal` (Python Software
  Foundation, n.d.-a). So `101.23` in the body becomes the Decimal `101.23`, and the test checks that `0.1`
  arrives as `Decimal("0.1")` and not as `Decimal(0.1)`, which is 0.1000000000000000055511151231257827. Whole
  numbers arrive as `int`, which `Decimal` takes exactly; `true` is an `int` in Python and is refused by name.
  Everything the parser does not recognize is a refusal with a reason, never a guess.
- **`source_from_settings`** reads the switch at call time, which is what lets the tests flip it with the
  `settings` fixture.

### 08.6 The pull and the command

Listing 08-13, Filename: `src/invest_witus_site/prices/pull.py`:

{{file:src/invest_witus_site/prices/pull.py}}

- **Three constants, each from a page read that day.** `DAYS_BACK` is the window, for Vercel's missed and
  duplicate runs. `REQUESTS_PER_RUN` is Tiingo's hourly limit, so a run can never exceed it: symbol fifty-one
  is listed as skipped for the next run. `PAUSE_SECONDS` is a courtesy, since Tiingo states no per-minute or
  per-second limit; fifty symbols at a second each still fit inside Vercel's 300-second Hobby maximum.
- **`symbol_universe`** is every held symbol whose kind is not cash, each once, plus `watch_symbols()`, which
  returns nothing and is where chapter 09 plugs in the watch list. The holding's kind is the one the owner set
  in chapter 05's admin; a cash line has nothing to pull.
- **`pull` is one loop with three exits per symbol.** Budget spent: skip. Refused: record the problem, and stop
  the whole run only if the source said to retry later. Answered: upsert and add the counts. The result is a
  dataclass with an `as_dict` for the cron's JSON, and the log line per symbol is what Vercel's log shows.

Listing 08-14, Filename: `src/invest_witus_site/prices/management/commands/pull_prices.py`:

{{file:src/invest_witus_site/prices/management/commands/pull_prices.py}}

- **Where it lives is its name.** Django registers "a `manage.py` command for each Python module" in an app's
  `management/commands` directory (Django Software Foundation, n.d.-c), so `pull_prices.py` is `manage.py
  pull_prices`. `add_arguments` is argparse; `--since` is parsed by `date.fromisoformat`, so a bad date is
  refused by argparse before `handle` runs.
- **`self.stdout` and `self.stderr`, not `print`:** the documentation asks for the proxies because "it becomes
  much easier to test your custom command" (Django Software Foundation, n.d.-c), and the tests pass a
  `StringIO` for each.
- **One `CommandError`,** for a start date after today. Raising it "is the preferred way to indicate that
  something has gone wrong", printed to stderr with a non-zero exit (Django Software Foundation, n.d.-c). A
  vendor's refusal is not that: it is reported per symbol on stderr, the counts go to stdout, and the command
  exits zero, because a 404 for one symbol is information, not a failure of the command.

### 08.7 The cron route and `vercel.json`

Listing 08-15, Filename: `src/invest_witus_site/prices/views.py`:

{{file:src/invest_witus_site/prices/views.py}}

- **503, then 403, then the pull.** The order matters: a missing secret is the deploy's mistake and is logged as
  an error; a wrong header is a stranger and gets one word. `secrets.compare_digest` compares "using a
  'constant-time compare' to reduce the risk of timing attacks" (Python Software Foundation, n.d.-b), and the
  whole `Bearer <secret>` string is compared, so a `Token` prefix, a lower-case `bearer` or a trailing space are
  all 403, as the parametrized test lists.
- **`require_GET` and `never_cache`,** as `/healthz/` has: Vercel makes a GET, and a cached 200 would be a run
  that never ran.
- **The schedule header is echoed** so a log line says which cron fired; a call by hand shows an empty string.

Listing 08-16, Filename: `src/invest_witus_site/prices/urls.py`:

{{file:src/invest_witus_site/prices/urls.py}}

Listing 08-17, Filename: `vercel.json`:

{{file:vercel.json|json}}

The `crons` key is the one chapter 06 said would come. Vercel reads it from the production deployment only,
which is why `vercel.json` carries it and no dashboard setting does; the project's **Settings → Cron Jobs**
page lists it, can disable it, can run it by hand, and links its logs (Vercel, 2026b).

### 08.8 The owner's pages

Listing 08-18, Filename: `src/invest_witus_site/prices/portfolio.py`:

{{file:src/invest_witus_site/prices/portfolio.py}}

The join: the latest statement's lines as chapter 05's `Position`s, the holdings' kinds in one query, the newest
close per symbol in two, and cash valued at one dollar a share, dated by the statement and labeled as such.
Then the library does the arithmetic.

Listing 08-19, Filename: `src/invest_witus_site/holdings/views.py`:

{{file:src/invest_witus_site/holdings/views.py}}

- **`login_required`** does two things: "If the user isn't logged in, redirect to `settings.LOGIN_URL`, passing
  the current absolute path in the query string", and otherwise "execute the view normally" (Django Software
  Foundation, n.d.-a). Chapter 07 set `LOGIN_URL = "sign-in"`, a named pattern, which the setting accepts, so
  the redirect goes to the WitUS sign-in with `?next=/accounts/1/`. (The sign-in brings the person home rather
  than to `next`; honoring it is an exercise.)
- **Ownership is in the query.** `get_object_or_404(Account, pk=pk, owner=request.user)`: another owner's id
  is a 404, the same answer as an id that does not exist, so the page says nothing about which ids exist.

Listing 08-20, Filename: `src/invest_witus_site/holdings/urls.py`:

{{file:src/invest_witus_site/holdings/urls.py}}

Listing 08-21, Filename: `src/invest_witus_site/urls.py`:

{{file:src/invest_witus_site/urls.py}}

Listing 08-22, Filename: `src/invest_witus_site/holdings/templates/holdings/account_list.html`:

{{file:src/invest_witus_site/holdings/templates/holdings/account_list.html}}

Listing 08-23, Filename: `src/invest_witus_site/holdings/templates/holdings/account_detail.html`:

{{file:src/invest_witus_site/holdings/templates/holdings/account_detail.html}}

One table, with a caption for screen readers, `scope` on every header cell, and the numbers right-aligned in
tabular figures by five rules added to `site.css` (`.holdings`, its cells, `.num`, the footer row and
`.stale`). A line with no close says "no price yet" across the four cells it cannot fill; the total is labeled
as the total of the priced lines, because that is what it is.

Listing 08-24, Filename: `src/invest_witus_site/holdings/templatetags/holdings_extras.py`:

{{file:src/invest_witus_site/holdings/templatetags/holdings_extras.py}}

`plain_number` is the new filter: a column stores `2.500000` and `101.230000`; the page shows `2.50` and
`101.23`, and `20.005` keeps its third place because it is not a zero.

Listing 08-25, Filename: `src/invest_witus_site/pages/templates/pages/_header.html`:

{{file:src/invest_witus_site/pages/templates/pages/_header.html}}

The "Accounts" link sits on the signed-in branch only. The signed-out branch is byte for byte chapter 07's, so
chapter 04's smoke test holds, and the last page test in this chapter renders every public page and asserts
there is no `<table` and no link to `/accounts/` on any of them.

### 08.9 Green, and the pull on your laptop

Listing 08-26, Terminal:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

```text
240 passed in 12.91s
All checks passed!
114 files already formatted
0 errors, 0 warnings, 0 informations
```

Forty-seven new tests. Now run the pull against chapter 02's made-up prices, as the CSV source:

Listing 08-27, Terminal:

```sh
mkdir -p data/private/prices
cp data/sample/illustrative-daily-prices.csv data/private/prices/INDEX.csv
uv run --env-file .env python manage.py migrate
uv run --env-file .env python manage.py pull_prices --symbols INDEX --since 2026-09-22
uv run --env-file .env python manage.py pull_prices --symbols INDEX --since 2026-09-22
uv run --env-file .env python manage.py pull_prices --symbols INDEX,OTHER --since 2026-09-29
```

```text
Source csv, 2026-09-22 to 2026-10-28, 1 symbol(s), 1 request(s).
Inserted 7, updated 0, unchanged 0.
Source csv, 2026-09-22 to 2026-10-28, 1 symbol(s), 1 request(s).
Inserted 0, updated 0, unchanged 7.
pull_prices: OTHER: no file OTHER.csv in /your/repo/data/private/prices
Failed OTHER: no file OTHER.csv in /your/repo/data/private/prices
Source csv, 2026-09-29 to 2026-10-28, 2 symbol(s), 2 request(s).
Inserted 0, updated 0, unchanged 2.
```

(The second date is today's, whatever day you run it, and the folder is your repository's; the sample file ends
on September 30, 2026.) Seven
weekdays inserted, then the same seven unchanged, then a symbol with no file recorded while `INDEX` is still
checked. The refusal appears twice: once from the logger, which is what Vercel's log shows, and once from the
command on stderr, which is what a shell shows.

Then the route, without a server, the way chapter 07 looked at the sign-in redirect:

Listing 08-28, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -c "from django.test import Client; r = Client().get('/api/cron/pull-prices/'); print(r.status_code, r.content.decode())"
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
CRON_SECRET=not-the-real-secret-just-for-this-check \
uv run python manage.py shell -c "from django.test import Client; print(Client().get('/api/cron/pull-prices/').status_code); r = Client().get('/api/cron/pull-prices/', headers={'Authorization': 'Bearer not-the-real-secret-just-for-this-check'}); print(r.status_code, r.content.decode())"
```

```text
503 {"error": "CRON_SECRET is not set"}
403
200 {"source": "csv", "since": "2026-10-21", "until": "2026-10-28", "symbols": [], "requests": 0, "inserted": 0, "updated": 0, "unchanged": 0, "failed": {}, "skipped": [], "schedule": ""}
```

`symbols` is empty because no account holds anything yet on this database; enter a statement in the admin
(chapter 05) and the same call lists its symbols. To see the page: sign in at `/admin/` with your chapter 05
superuser (a login is a login, as chapter 07 noted), then open `http://127.0.0.1:8000/accounts/` under
`runserver`.

### 08.10 What the owner does outside the editor

The reference app's key and secret are the owner's; task 09 in the owner's queue has the dashboard steps. A
learner with a Vercel project of their own does the same with their own Tiingo account. The steps, so the
chapter is complete:

1. **A Tiingo account and its token.** Sign up at `https://www.tiingo.com/signup` (the page hands the browser
   to app.tiingo.com); the free plan is the one named Starter on the pricing page. The token is at
   `https://www.tiingo.com/account/api/token`, behind the login (Tiingo, n.d.-c). It goes in a password
   manager, never in a file. Read the Terms of Use in the browser while there; the page refuses automated
   readers.
2. **A cron secret:** at least 16 random characters (Vercel, 2026b). `openssl rand -hex 24`, or
   `python3 -c "import secrets; print(secrets.token_hex(24))"`, which gives 48 hexadecimal characters (Python
   Software Foundation, n.d.-b).
3. **Migrate.** `vercel env run -e production -- uv run python manage.py migrate --database direct`, chapter
   06's recipe; expect `Applying prices.0001_initial... OK`.
4. **Set both names on the Vercel project:** **Settings → Environment Variables**, `TIINGO_API_KEY` and
   `CRON_SECRET`, Production only, marked Sensitive. Crons run against the production deployment only, and a
   preview with the key would spend the hourly budget against a preview database. Then **Redeploy**, so the
   function starts with both.
5. **Run it once, now.** **Settings → Cron Jobs** lists `/api/cron/pull-prices/` with a run button and **View
   Logs** (Vercel, 2026b); or by hand, with the secret in the shell for one command:
   `curl -s -H "Authorization: Bearer $CRON_SECRET" https://<your host>/api/cron/pull-prices/`. Expect 200 and
   JSON with `source` `tiingo`, the held symbols, and `inserted` up to seven per symbol. Run it again: `inserted`
   0, `unchanged` the same number. Without the header: 403. Before step 4: 503.
6. **Open `/accounts/`** signed in, then an account: every line has a close, its date (the last trading day),
   `tiingo` as the source, and a value; a symbol Tiingo did not know is in the response's `failed` and reads
   "no price yet" on the page. The next morning, the Cron Jobs page shows the run after 06:00 UTC.

## Checkpoint

- `uv run pytest` prints `240 passed`; ruff and pyright pass.
- Listing 08-27 inserts seven days the first time and changes nothing the second time.
- Listing 08-28 answers 503, then 403, then 200 with JSON counts.
- Signed out, every public page has no `<table` and no link to `/accounts/`; `/accounts/` itself redirects to
  the sign-in with `?next=/accounts/`.
- Signed in at `/admin/` with a statement entered, `/accounts/<id>/` shows each line with a close, a date and a
  source, or "no price yet".
- On the reference app, after 08.10: a run by hand answers 200 with `tiingo` as the source, and the account page
  shows values.
- Commit and push: `git add -A && git commit -m "Chapter 08: Prices and the nightly pull"`.

## Exercises

1. Add `--until YYYY-MM-DD` to the command, defaulting to today, and refuse a window where `--since` is after
   `--until`. Write the test first; the `CommandError` test shows the shape.
2. The cron runs on Saturdays and Sundays and finds nothing. Change the schedule so it runs Tuesday to Saturday
   (Vercel's day-of-week field, with the day-of-month field left as `*`), update the test, and write one
   sentence in your notes about what a Monday holiday does to Tuesday's pull and why the seven-day window still
   covers it.
3. `login_required` sends a visitor to the sign-in with `?next=/accounts/3/`, and chapter 07's callback goes
   home. Store `next` in the flight at `login`, check it with Django's `url_has_allowed_host_and_scheme` at the
   callback, and redirect there. Write the test that a `next` pointing at another host is ignored.

## If you get stuck

- Browse: https://github.com/dapperAuteur/invest-witus/tree/v08
- Diff for this chapter: https://github.com/dapperAuteur/invest-witus/compare/v07...v08
- Zip: https://github.com/dapperAuteur/invest-witus/archive/v08.zip
- Take the reference's files. Chapter 08 changed `.env.example`, `vercel.json`,
  `src/invest_witus_site/settings.py`, `src/invest_witus_site/urls.py`, the template `pages/_header.html`,
  `pages/static/pages/site.css`, `holdings/templatetags/holdings_extras.py` and `docs/site/privacy.md`, and
  added `src/invest_witus/valuation.py`, `src/invest_witus_site/prices/` (the whole app),
  `src/invest_witus_site/holdings/views.py`, `holdings/urls.py`, `holdings/templates/holdings/`,
  `tests/test_ch08.py` and `tests/fixtures/tiingo/`. No package changed. Nothing moved:
  `git fetch reference --tags && git checkout v08 -- src tests .env.example vercel.json docs/site/privacy.md`.
- `No module named 'invest_witus.valuation'` after 08.3: the file is in `src/invest_witus_site/` instead of
  `src/invest_witus/`; the library and the site are two packages.
- `test_upsert_writes_each_day_once_and_a_rerun_changes_nothing` fails on the table comparison: `upsert` saves
  unchanged rows, or sets `fetched_at` on every row; an unchanged day must not be written at all.
- `test_a_close_keeps_six_places_and_a_float_is_refused` fails with a `decimal.InvalidOperation` or a
  `django.core.exceptions.ValidationError`: `to_close` is not applied before `bulk_create`, which skips `save`.
- `test_tiingo_parsing_keeps_the_number_exact_and_takes_a_bare_date` fails on `Decimal(0.1)`: the body was read
  with `response.json()`, which makes floats. Use `json.loads(response.text, parse_float=Decimal)`.
- `test_tiingo_parsing_refuses_a_body_it_does_not_understand[true]` fails: `isinstance(True, int)` is `True`
  in Python; check `bool` first.
- `test_a_rate_limit_stops_the_run_and_lists_what_was_left` has `OTHER` in `failed` instead of `skipped`: the
  loop did not `break` on `retry_later`, or it broke before extending `skipped`.
- `test_the_pause_sits_between_symbols_not_after_the_last` sees three sleeps: the sleep runs before the first
  request; it must be skipped when `requests` is still zero.
- `test_the_cron_route_refuses_anything_but_the_bearer_secret[Bearer ...  ]` (the trailing space) answers
  200: the header was `strip()`ped or split on spaces; compare the whole string.
- `test_the_cron_route_fails_closed_without_a_secret` gets 403: the secret check comes after the header check;
  the empty secret must answer 503 first.
- `test_the_account_pages_need_a_sign_in` gets 200 or `/accounts/login/`: `login_required` is missing, or
  chapter 07's `LOGIN_URL = "sign-in"` was lost from the settings.
- `test_the_account_page_is_the_owners_only` gets 200: `owner=request.user` is missing from
  `get_object_or_404`.
- `test_the_owner_sees_each_line_valued_with_the_closes_date` shows `2.500000`: the `plain_number` filter is
  not applied, or `{% load holdings_extras %}` is missing from the template.
- `test_public_pages_show_no_table_and_do_not_link_the_account_pages` fails on `/`: the "Accounts" link is
  outside the `{% if user.is_authenticated %}` branch of the header.
- On Vercel, the Cron Jobs page shows the job but the log shows 503: the secret was added after the last
  deployment; **Redeploy**. 403 from the dashboard's run button: the variable's value has a space or a quote
  around it.
- The response lists a symbol under `failed` with `Tiingo answered 404`: the statement's symbol is not the
  ticker Tiingo knows; fix it in the admin's Holdings list, or accept "no price yet".

## What we learned

- The table is the product: the page reads it, the pull writes it, and the vendor is asked once a night. Every
  displayed price carries its date and source because the row does.
- An idempotent job compares before it writes, counts what it did, and leaves a repeated run with nothing to
  do; on a platform that may miss a run or deliver it twice, that is the only kind of job to write.
- A `Protocol` is a seam: two sources with one shape, a pull that never names a vendor, tests that use the cheap
  source for the plumbing and a fake vendor for the parsing.
- A vendor's number stays a Decimal from the first byte: `parse_float=Decimal`, a parser that refuses what it
  does not understand, and a column with enough places that nothing is rounded before it is multiplied.
- One symbol's refusal is recorded; only a rate limit stops the run; the key is in a header and never in a URL
  or an error message.
- A cron on Vercel is a GET with a bearer, compared in constant time, in UTC, somewhere inside its hour, and
  without retries; a route that fails closed without its secret is a deploy mistake caught on the first run.
- A page for the owner is `login_required` plus the owner in the query, and the proof that no public page shows
  a price is a test over every public page, not a promise.

## Next

Chapter 09 adds the watch list: symbols the owner follows per account, with the latest stored close and its
date, and no buy button. `watch_symbols()` is where its symbols join the nightly pull; nothing else from this
chapter changes for it.

## References

Alpaca. (2026a, October 6). *About market data API*. Alpaca documentation.
https://docs.alpaca.markets/docs/about-market-data-api (retrieved October 28, 2026)

Alpaca. (2026b, September 21). *Market data FAQ*. Alpaca documentation.
https://docs.alpaca.markets/us/docs/market-data-faq (retrieved October 28, 2026)

Alpaca. (2026c, February 11). *Historical stock data*. Alpaca documentation.
https://docs.alpaca.markets/us/docs/historical-stock-data-1 (retrieved October 28, 2026)

Alpaca. (n.d.-a). *Get all open positions*. Alpaca API reference.
https://docs.alpaca.markets/reference/getallopenpositions (retrieved October 28, 2026)

Alpaca. (n.d.-b). *Paper trading*. Alpaca documentation. https://docs.alpaca.markets/docs/paper-trading
(retrieved October 28, 2026)

Alpaca. (n.d.-c). *Historical bars*. Alpaca API reference. https://docs.alpaca.markets/reference/stockbars
(retrieved October 28, 2026)

Django Software Foundation. (n.d.-a). *Using the Django authentication system*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/auth/default/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-b). *Aggregation*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/db/aggregation/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-c). *How to create custom django-admin commands*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/howto/custom-management-commands/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-d). *QuerySet API reference*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/ref/models/querysets/ (retrieved October 28, 2026)

Encode. (n.d.). *Transports*. HTTPX documentation. https://www.python-httpx.org/advanced/transports/ (retrieved
October 28, 2026)

Python Software Foundation. (n.d.-a). *json: JSON encoder and decoder*. Python 3 documentation.
https://docs.python.org/3/library/json.html (retrieved October 28, 2026)

Python Software Foundation. (n.d.-b). *secrets: Generate secure random numbers for managing secrets*. Python 3
documentation. https://docs.python.org/3/library/secrets.html (retrieved October 28, 2026)

Python Software Foundation. (n.d.-c). *typing: Support for type hints*. Python 3 documentation.
https://docs.python.org/3/library/typing.html (retrieved October 28, 2026)

Tiingo. (n.d.-a). *Connecting*. Tiingo documentation. https://www.tiingo.com/documentation/general/connecting
(retrieved October 28, 2026)

Tiingo. (n.d.-b). *End-of-day*. Tiingo documentation. https://www.tiingo.com/documentation/end-of-day
(retrieved October 28, 2026)

Tiingo. (n.d.-c). *Overview*. Tiingo documentation. https://www.tiingo.com/documentation/general/overview
(retrieved October 28, 2026)

Tiingo. (n.d.-d). *Pricing*. https://www.tiingo.com/about/pricing (retrieved October 28, 2026)

Tiingo. (n.d.-e). *Developers*. Tiingo documentation. https://www.tiingo.com/documentation/appendix/developers
(retrieved October 28, 2026)

Vercel. (2026a, September 16). *Cron jobs*. Vercel documentation. https://vercel.com/docs/cron-jobs (retrieved
October 28, 2026)

Vercel. (2026b, August 11). *Managing cron jobs*. Vercel documentation.
https://vercel.com/docs/cron-jobs/manage-cron-jobs (retrieved October 28, 2026)

Vercel. (2026c, July 15). *Usage & pricing for cron jobs*. Vercel documentation.
https://vercel.com/docs/cron-jobs/usage-and-pricing (retrieved October 28, 2026)
