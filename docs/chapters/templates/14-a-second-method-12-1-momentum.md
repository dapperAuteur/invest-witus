# Chapter 14: A second method: 12-1 momentum

**Starts from:** tag `v13`, plus the reference's work between chapters (step 14.0). **Ends at:** tag `v14`.
**Written against:** Python 3.14.10, uv 0.13.6, Django 5.2.18, and IRS Publication 550 (2025) as read on October
29, 2026.
**Goal:** the app holds you to a second method. 12-1 momentum ranks a list of candidates you chose by how much each
rose over the past year without its latest month, and puts the month's money into the top few, in equal parts. You
write the method's seven rules into a TOML file next to chapter 03's, compute the ranking in a small module with no
Django in it, check the journal against the new rules with a second rule set, and teach the engine to run whichever
set the plan's method names. A momentum plan starts from the same form with one more number, the top N. The method
page draws the ranking as bars with a table under them, a watched symbol's chart shades the window the return is
measured over, the watch list shows each symbol's number with an arrow, and each picture carries a short "How to read
this". On a paper account, Confirm buys this month's top N.
**Time:** 5 to 6 hours for the code and tests. The laptop walk-through takes 10 minutes.

The listings in this chapter are not typed in by hand. `scripts/render_chapter.py` pastes the real files from
tag `v14` into the chapter text, so what you read and what the tests run are the same bytes.

## What you will learn

- **Windowing by calendar month:** the last stored close of a month, month arithmetic that crosses a year, and a
  window defined by months back from today instead of by days.
- **Ranking with `Decimal`:** a sort key that orders by return and breaks ties the same way every time, and a
  result type that keeps the candidates it could not rank with the reason.
- **A second rule set in the same shape as the first:** a registry from method id to the rules it checks, and a
  test that walks every rules file the package ships.
- **Generalizing without rewriting:** one branch in the engine, optional arguments with the old behavior as the
  default, and an earlier chapter's test that pinned a list.
- **Charts that read without color or script:** bars drawn on the server, a filled or outlined shape, a sign and a
  word beside each number, and a table as the text alternative.

## Before the code: what the PRD asks, and seven decisions

**What the PRD asks.** Section 7.1, method 2: "Rank the user's own universe by return from 12 months ago to 1 month
ago (skipping the most recent month); hold the top N, equal weight; review monthly; trade only at a review." And:
"Method 2 warns before a sell-and-rebuy of the same security within 30 days (wash-sale rule, IRS Publication 550)".
The roadmap's row 14 adds "a second rule block on the same engine". Ranking a list by its past return is the idea
Gray and Vogel (2016) build their momentum system on; their system also screens for the quality of the rise and
rebalances each quarter. This chapter builds the PRD's simpler monthly version. The book's system can come later as
a separately named method, and nothing from the book is copied here.

**Decision 1: seven rules, written before the code.** Each rule is a sentence you can follow without the app, and
each has a check the app can run on your journal (decisions log, row 142):

| Rule id | What it says | What the review flags |
|---|---|---|
| `candidates-only` | Rank and buy only the candidates your plan names | a buy of any other symbol |
| `rank-by-12-1` | Rank by the 12-1 return; a candidate without both closes is not ranked and not bought | a buy of a candidate that was not ranked that month |
| `hold-top-n` | At each rebalance, buy every candidate in the top N and none below | a buy ranked below the top N; a top-N candidate with no buy in a month that had one |
| `equal-weight` | Split the month's amount equally across the symbols you buy, to the cent | a buy more than a cent away from its equal part |
| `sell-what-leaves` | Sell the whole holding once it leaves the top N, and nothing still in it | a holding not sold in a month it ranked outside; a sale of a symbol inside |
| `rebalance-each-month` | Rebalance once in every month of the plan | a month due with no trade (a skip with its reason explains it) |
| `trade-only-at-review` | Trade only within the plan's window at the start of the month | a trade after the window |

Every `lesson` is empty. The lessons will live in the Learn.WitUS preview course "A Method You Can Keep", one per
rule, and none is published yet, so every rule reads "lesson coming". A rule id becomes the second half of its
lesson's address, so choose ids you will not want to rename. The wash-sale warning is not a rule: the method can
require buying back in November what it sold in October, so a rule against that would contradict `hold-top-n`.

**Decision 2: the window, the month-end close and ties.** A rebalance in month M reads the last stored close of
month M-13 and of month M-2. For a rebalance in November 2026 that is the end of October 2025 to the end of
September 2026, and October 2026, the latest full month, is left out. The month-end close is the latest day stored
inside the calendar month, whatever day that is; a month with no close is missing, never filled in from a
neighbor. The return is `end / start - 1`, exact in `Decimal`. Highest first; equal returns are ordered by symbol,
A to Z, and marked tied, so the same prices always give the same order. Row 143.

**Decision 3: adjusted closes.** A split halves the close and leaves the adjusted close alone, so a ranking on
closes would read a split as a fall. The web reads `adj_close` where the row has it and the close where it does not
(a CSV file on a laptop has none), and the page says how many closes had no adjusted value. Row 143.

**Decision 4: one more number on the plan.** `MethodPlan.top_n`, nullable, so the migration is additive. The
candidates are the plan's `symbols`, and `amount` is the month's money, split equally across that month's top N:
method 1's monthly contribution, applied to a ranked list. Equal weight is therefore about each month's new money,
not the value you already hold; rebalancing what you hold back to equal parts needs each position's value and is
left for later. Starting a momentum plan puts every candidate on the watch list, because the nightly pull only
fetches symbols you hold or watch. Row 144.

**Decision 5: a rule set per method.** Chapter 03's `review` and its `CHECKED_RULES` stay exactly as they are. The
new rules get their own module, `adherence/momentum.py`, with its own `CHECKED_RULES` and a `review` that takes the
month's rankings as an argument, and `adherence/rule_sets.py` maps each method id to its set. The engine branches
once on the plan's method. A month where no candidate can be ranked is not judged by rank: a missing price is the
app's gap, not your mistake. Row 145.

**Decision 6: buys only, and a wash-sale warning.** On a paper account, Confirm stages one buy per top-N symbol,
the amount split to the cent in rank order, through chapter 11's ids, budget and sync. A holding that left the top
N is listed as "Sell all of GAMMA" and is not placed by the app. Selling on Alpaca's paper account does not need
the live-trading checklist; the sell path (read the position, close it, book what it brought into the journal and
the sync) is a design of its own, so it waits for a later addendum, and you sell in Alpaca's paper dashboard and
log the sale here. Before a buy of a symbol the journal shows sold in the last 30 days, the page prints a wash-sale
warning. IRS Publication 550 says a wash sale "occurs when you sell or trade stock or securities at a loss and
within 30 days before or after the sale you" buy substantially identical stock or securities, and that the
disallowed loss is added to the cost of the new shares (Internal Revenue Service [IRS], 2026). A paper account has
no tax effect; the warning is there for the day the account is live. Row 146.

**Decision 7: three pictures, each with "How to read this".** Ranked bars on the method page; the window shaded on
a watched symbol's chart, with the excluded month lighter and labelled "excluded"; and a 12-1 column on the watch
list with an arrow, the word up or down, and the number. All three are for the account's owner, on an account that
runs momentum, drawn on the server, with no script. Row 147. Rank changes from month to month and a rolling 12-1
line are chapter 14a.

## Steps

### 14.0 Take the work between chapters

Between `v13` and this chapter the reference took three pieces of work that are not chapters: adjusted closes,
splits and dividends with the price charts and their ranges (decisions 114 to 141), the price buttons, and WitUS
Outbox. This chapter's shaded window draws on those charts, and its ranking on the adjusted closes. Take them from
the reference at the commit this chapter starts from, then migrate:

Listing 14-1, Terminal:

```sh
git fetch reference --tags
git checkout e635e10 -- src tests .env.example
uv run --env-file .env python manage.py migrate
uv run pytest -q
```

```text
Operations to perform:
  Apply all migrations: accounts, admin, auth, contenttypes, holdings, methods, outbox, pages, paper, prices, reports, sessions, watchlist
Running migrations:
  Applying outbox.0001_initial... OK
  Applying prices.0004_daily_close_adjustments... OK
696 passed in 27.36s
```

Commit that as its own step (`git commit -am "Take the reference's work between chapters 13 and 14"`), so this
chapter's diff is only this chapter.

### 14.1 The tests

Listing 14-2, Filename: `tests/test_ch14.py`:

{{file:tests/test_ch14.py}}

Things to notice:

- **Every price is planted.** `closes` writes one close a month that grows by a fixed rate, so the ranking is
  known before the test runs: ALPHA rises 2% a month, BETA 1%, GAMMA falls 1%, and DELTA has six months, too few
  to rank. The symbols are placeholders, and so are the prices.
- **The math tests need no database.** The window, the month-end close, the return, the ranking and the bars take
  plain lists, the way chapter 01's tests took plain numbers.
- **The month-end test shuffles its input.** A month-end close that depended on the order the rows arrived would
  pass with sorted rows and fail on a real query someday.
- **One rule at a time.** `found` runs the second rule set on a hand-made ranking, and each test plants exactly one
  mistake.
- **Dates relative to today, where the page reads today.** The method page and the watch list read the clock, so
  `running` plants prices through last month, whatever month you run it in.
- **The paper fake is chapter 11's,** imported, with the day fixed on November 3, 2026.

Run the tests:

Listing 14-3, Terminal:

```sh
uv run pytest tests/test_ch14.py
```

```text
tests/test_ch14.py:23: in <module>
    from invest_witus.adherence import momentum as momentum_rules
E   ImportError: cannot import name 'momentum' from 'invest_witus.adherence' (.../src/invest_witus/adherence/__init__.py)
=========================== short test summary info ============================
ERROR tests/test_ch14.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.88s ===============================
```

Red at import. No package is added this chapter.

### 14.2 The rules file

Listing 14-4, Filename: `src/invest_witus/methods/momentum_12_1.toml`:

{{file:src/invest_witus/methods/momentum_12_1.toml}}

Chapter 10's `available_methods()` lists every `.toml` file in the package, so this file is the second option in
the start form with no other change. It also breaks one earlier test, on purpose:
`test_the_package_lists_its_methods_and_the_rules_file_still_matches_the_checks` in `tests/test_ch10.py` asserted
the whole list, `["index-dca"]`. That was true at `v10` and is not now. Change its first line to assert membership:

Listing 14-5, Filename: `tests/test_ch10.py` (one line changed):

```python
    # Chapter 14 ships a second method, so this asserts membership, not the whole list.
    assert "index-dca" in [method.id for method in available_methods()]
```

A test that pins a whole list breaks when the list grows by design. Chapter 14's own test pins the list instead,
because this chapter decides what it holds.

### 14.3 The 12-1 math

Listing 14-6, Filename: `src/invest_witus/methods/momentum_12_1.py`:

{{file:src/invest_witus/methods/momentum_12_1.py}}

Things to notice:

- **Months as `(year, month)` tuples.** `add_months` turns a month into a count of months since year zero, adds,
  and turns it back, so January minus two is November of the year before without a special case.
- **`month_ends` keeps the latest day per month,** comparing days, so the order of the input does not matter.
- **`score` returns a `Score` or an `Unranked`,** never `None`: a candidate that cannot be ranked carries its
  reason to the page.
- **The sort key is `(-change, symbol)`.** Negating a `Decimal` sorts highest first; the symbol settles a tie the
  same way every time. `tied` is computed after, so the page can say so.
- **`change` is a property, not a stored field,** so the ranking and the page divide the same two numbers.

### 14.4 The second rule set

Listing 14-7, Filename: `src/invest_witus/adherence/momentum.py`:

{{file:src/invest_witus/adherence/momentum.py}}

Listing 14-8, Filename: `src/invest_witus/adherence/rule_sets.py`:

{{file:src/invest_witus/adherence/rule_sets.py}}

Things to notice:

- **The same shape as chapter 03.** A frozen set of ids, a `Finding` per break with its lesson, sorted by day.
  Chapter 03's module is imported for `Finding` and `months_due`, and not changed.
- **The rankings are an argument.** The rule set never reads a price. Whoever calls it decides where the prices
  come from: planted lists in the tests, stored closes on the web.
- **A month with nothing ranked skips the rank checks.** Without that guard, a candidate whose prices were never
  fetched would turn every buy into a finding.
- **`Holdings.before` reads the journal,** not the broker: a symbol whose latest trade before the month was a buy.
  The method sells a holding whole, so one sale ends it.
- **`equal_parts` is chapter 11's split,** written once more here so the library needs nothing from the web app.

### 14.5 The plan's top N

Listing 14-9, Filename: `src/invest_witus_site/methods/models.py`:

{{file:src/invest_witus_site/methods/models.py}}

The new column is nullable, which is the additive form of a new column: an old row and an insert from the release
before this one both leave it `NULL`. Make the migration and tidy it:

Listing 14-10, Terminal:

```sh
uv run --env-file .env python manage.py makemigrations methods --name methodplan_top_n
uv run ruff format src/invest_witus_site/methods/migrations/
uv run ruff check --fix src/invest_witus_site/methods/migrations/
```

```text
Migrations for 'methods':
  src/invest_witus_site/methods/migrations/0004_methodplan_top_n.py
    + Add field top_n to methodplan
```

Listing 14-11, Filename: `src/invest_witus_site/methods/migrations/0004_methodplan_top_n.py`:

{{file:src/invest_witus_site/methods/migrations/0004_methodplan_top_n.py}}

### 14.6 Prices, rankings and pictures for the web

Listing 14-12, Filename: `src/invest_witus_site/methods/momentum.py`:

{{file:src/invest_witus_site/methods/momentum.py}}

Things to notice:

- **One query per page.** `price_series` reads every candidate's rows from the first window's start, oldest
  first, and the engine ranks every month from that one result.
- **`adj_close` if stored, else `close`,** counted in `unadjusted`, so the page can say so instead of hiding it.
- **`bar_chart` puts every bar on one scale,** from the lowest return or zero to the highest or zero. The zero line
  sits where they meet, and a bar never shrinks below half a percent of the track, so a return of 0.1% still shows.
- **`wash_sale_warnings` reads only the journal,** and words the rule as the IRS states it, without a tax figure.
- **`ensure_watched` reuses chapter 09's `WatchItem.add_many`,** so the symbol rule and the one-row-per-symbol
  constraint apply.

### 14.7 The engine's second path

Listing 14-13, Filename: `src/invest_witus_site/methods/engine.py`:

{{file:src/invest_witus_site/methods/engine.py}}

The change is one branch in `build_review`. An index plan takes the path it took in chapter 12, line for line;
`test_ch10.py` and `test_ch12.py` prove it. A momentum plan reads its prices once, ranks the months each version
covers, runs the momentum rule set per version, and adds the ranking to each month row. `month_rows` and `explain`
gain one argument each with the old behavior as its default: a month with only a sale is a rebalance, and the skip
explains "No rebalance" the way it explains "No buy".

### 14.8 The forms and the views

Listing 14-14, Filename: `src/invest_witus_site/methods/forms.py`:

{{file:src/invest_witus_site/methods/forms.py}}

Listing 14-15, Filename: `src/invest_witus_site/methods/views.py`:

{{file:src/invest_witus_site/methods/views.py}}

Things to notice:

- **`check_top_n` is one function for two forms.** It reads the method from the form's data, so the start form,
  where the method is a field, and the change form, where it is the plan's, share every message.
- **The change form removes its field for an index plan.** `del self.fields["top_n"]` keeps chapter 12's form and
  its tests exactly as they were.
- **The form returns the plan, as before.** The symbols it added to the watch list go in `form.watched`, so
  `start()` keeps the signature chapter 10's tests call.

### 14.9 The pages

The momentum section is one partial, included above the view, so views A, B and C each show it without three
copies:

Listing 14-16, Filename: `src/invest_witus_site/methods/templates/methods/_momentum.html`:

{{file:src/invest_witus_site/methods/templates/methods/_momentum.html}}

Listing 14-17, Filename: `src/invest_witus_site/methods/templates/methods/method_page.html`:

{{file:src/invest_witus_site/methods/templates/methods/method_page.html}}

Things to notice:

- **The bars are an ordered list.** Each item is the rank, the symbol, a small SVG and the number with its sign and
  the word up or down. A screen reader reads the list; the SVG is `aria-hidden` and carries a `<title>` for a mouse
  pointer.
- **Filled or outlined.** A bar in the top N is filled and one below it is an outline, so the line between them
  does not depend on telling two colors apart. The fill colors are the chart palette's blue and orange, each at
  least 3:1 against the page.
- **The table under the bars** holds the same ranking with the two closes and their days: the text alternative,
  and the place to check the arithmetic by hand.
- **"Get 5 years of history"** posts to the watch list's Fetch history for selected, with the unranked symbols
  typed in. No new view.

The views print the plan in momentum's words, in the same `if` everywhere. View A, for example:

Listing 14-18, Filename: `src/invest_witus_site/methods/templates/methods/_view_a.html`:

{{file:src/invest_witus_site/methods/templates/methods/_view_a.html}}

`_view_b.html` adds a **Top N** column to the Months table for a momentum plan, and `_view_c.html`,
`_versions.html` and `plan_change.html` change the plan's sentence the same way. Each `else` branch is the chapter
12 text, byte for byte, because chapter 10's tests compare it.

### 14.10 The shaded window and the badge

The chart gains bands: a stretch of days, clipped to the range on screen.

Listing 14-19, Filename: `src/invest_witus_site/prices/charts.py`:

{{file:src/invest_witus_site/prices/charts.py}}

Listing 14-20, Filename: `src/invest_witus_site/prices/templates/prices/_chart.html`:

{{file:src/invest_witus_site/prices/templates/prices/_chart.html}}

The history page adds the bands when the account runs momentum, and a section with the symbol's number and its
note:

Listing 14-21, Filename: `src/invest_witus_site/watchlist/views.py`:

{{file:src/invest_witus_site/watchlist/views.py}}

Listing 14-22, Filename: `src/invest_witus_site/watchlist/templates/watchlist/_momentum_window.html`:

{{file:src/invest_witus_site/watchlist/templates/watchlist/_momentum_window.html}}

The watch list's column needs a dictionary lookup by a variable, which Django's templates do not do, so
`holdings_extras` gains one small filter:

Listing 14-23, Filename: `src/invest_witus_site/holdings/templatetags/holdings_extras.py`:

{{file:src/invest_witus_site/holdings/templatetags/holdings_extras.py}}

Listing 14-24, Filename: `src/invest_witus_site/watchlist/templates/watchlist/_section.html`:

{{file:src/invest_witus_site/watchlist/templates/watchlist/_section.html}}

`holdings/views.py` passes `momentum_badges` (or `None` for an account without momentum), `history.html` includes
the window partial under the chart, and `site.css` gets the bar, band and badge styles. The home page's line about
methods now names both.

### 14.11 Buys on paper

Listing 14-25, Filename: `src/invest_witus_site/paper/orders.py`:

{{file:src/invest_witus_site/paper/orders.py}}

`month_symbols` is the one new idea: an index plan buys every symbol it names, a momentum plan its top N for the
day's month. Everything after it, the ids, the split, the budget, Confirm, Place again and the sync, is chapter 11
and 12's. Chapter 11's one-symbol refusal still applies to index plans; a momentum plan with nothing ranked is
refused in words.

### 14.12 Green, and a momentum plan on your laptop

Listing 14-26, Terminal:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run --env-file .env python manage.py migrate
```

```text
722 passed in 26.87s
All checks passed!
231 files already formatted
0 errors, 0 warnings, 0 informations
Operations to perform:
  Apply all migrations: accounts, admin, auth, contenttypes, holdings, methods, outbox, pages, paper, prices, reports, sessions, watchlist
Running migrations:
  Applying methods.0004_methodplan_top_n... OK
```

Twenty-six new tests. Your laptop's `Practice` account runs index investing from chapter 10, and an account runs
one method at a time, so start momentum on a second account. The first two tries are refused on purpose:

Listing 14-27, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -v 0 -c "
import re
from django.contrib.auth.models import User
from django.test import Client
from invest_witus_site.holdings.models import Account
u = User.objects.get(is_superuser=True); c = Client(); c.force_login(u)
a, _ = Account.objects.get_or_create(owner=u, name='Momentum practice', defaults={'broker': 'Example Brokerage', 'kind': 'paper'})
said = lambda page: re.findall(r'class=\"message \w+\">([^<]+)<', page) or re.findall(r'class=\"errorlist[^\"]*\"[^>]*><li>([^<]+)<', page)
form = {'method_id': 'momentum-12-1', 'amount': '100', 'buy_window_days': '7', 'symbols': 'ALPHA BETA GAMMA DELTA', 'started_on': '2026-10-01'}
for top_n in ('', '4', '2'):
    for line in said(c.post(f'/accounts/{a.pk}/method/start/', {**form, 'top_n': top_n}, follow=True).content.decode()):
        print(line)
"
```

```text
12-1 momentum needs a top N: how many candidates to hold.
Name more candidates than the top N: 4 candidates and a top 4 leaves nothing to rank out.
Started 12-1 momentum, monthly top N in equal parts on Momentum practice.
Added to the watch list, so the nightly pull stores their closes: ALPHA, BETA, GAMMA, DELTA. A candidate needs a year of closes or more to be ranked; Get history fetches them now.
```

Use the first day of your current month for `started_on`. The four symbols are placeholders, so no price source
knows them; plant twenty months of made-up closes with the test's own helper, and read the ranking:

Listing 14-28, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -v 0 -c "
import re
from django.contrib.auth.models import User
from django.test import Client
from invest_witus_site.holdings.models import Account
from tests.test_ch10 import tables_in, text
from tests.test_ch14 import add_months, plant_candidates, this_month
u = User.objects.get(is_superuser=True); a = Account.objects.get(owner=u, name='Momentum practice'); c = Client(); c.force_login(u)
plant_candidates(add_months(this_month(), -1))
page = text(c.get(f'/accounts/{a.pk}/method/?view=b'))
print(re.search(r'<h2 id=\"ranking-heading\">([^<]+)<', page).group(1))
for row in next(t for t in tables_in(page) if t[0][0] == 'Rank'): print(row)
print(re.findall(r'<li>(DELTA: [^<]+)</li>', page))
print(re.findall(r'<li>(Buy [^<]+|Sell [^<]+)</li>', page))
"
```

```text
The ranking for 2026-10
('Rank', 'Symbol', '12-1 return', 'From', 'To', 'Top 2')
('1', 'ALPHA', '+24.3%', '2025-09-28, $114.87', '2026-08-28, $142.82', 'yes')
('2', 'BETA', '+11.6%', '2025-09-28, $107.21', '2026-08-28, $119.61', 'yes')
('3', 'GAMMA', '-10.5%', '2025-09-28, $93.21', '2026-08-28, $83.45', 'no')
['DELTA: no close stored in 2025-09; the window needs a close in 2025-09 and in 2026-08.']
['Buy $50.00 of ALPHA', 'Buy $50.00 of BETA']
```

Your months are the ones before the month you run it in. Check one return by hand: 142.82 over 114.87 is 1.2433,
or +24.3%. September 2026 is in neither column: it is the excluded month. Now break a rule on purpose, buying GAMMA
instead of BETA, and read view B:

Listing 14-29, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -v 0 -c "
from django.contrib.auth.models import User
from django.test import Client
from invest_witus_site.holdings.models import Account
from tests.test_ch10 import tables_in, text
u = User.objects.get(is_superuser=True); a = Account.objects.get(owner=u, name='Momentum practice'); c = Client(); c.force_login(u)
for symbol, amount in (('ALPHA', '50'), ('GAMMA', '50')):
    c.post(f'/accounts/{a.pk}/method/log/', {'date': '2026-10-02', 'action': 'buy', 'symbol': symbol, 'amount': amount})
tables = tables_in(text(c.get(f'/accounts/{a.pk}/method/?view=b')))
checks = next(t for t in tables if t[0][0] == 'Rule')
for row in checks: print(row[0][:44], row[1], row[2], sep=' | ')
months = next(t for t in tables if t[0][0] == 'Month')
for row in months: print(row[0], row[2], row[6], row[7], sep=' | ')
findings = next(t for t in tables if t[0][:2] == ('Day', 'Rule'))
for row in findings[1:]: print(row[0], row[2], sep=' | ')
"
```

```text
Rule | Status | Evidence
Rank and buy only the candidates your plan n | pass | no findings
Rank the candidates by their 12-1 return: th | pass | no findings
Hold the top N: at each rebalance, buy every | fail | 2 findings: 2026-10
Split the month's amount equally across the  | pass | no findings
Sell the whole holding of a symbol at the fi | pass | no findings
Rebalance once in every month of the plan. | pass | no findings
Trade only at the monthly rebalance, within  | pass | no findings
Month | Status | Rules flagged | Top 2
2026-10 | done | hold-top-n | ALPHA, BETA
2026-10-01 | No buy of BETA in 2026-10; it ranked 2nd.
2026-10-02 | Bought GAMMA, ranked 3rd in 2026-10; the plan holds the top 2.
```

One trade, two findings of one rule: GAMMA was bought from below the line, and BETA, above it, was not. In a
browser, sign in, open **Momentum practice**, and the method page shows the bars above the view; the account page's
watch list shows the 12-1 column; click ALPHA and pick **All** to see the window shaded.

### 14.13 What the owner does outside the editor

The reference app's steps are task 25 in the owner's queue. A learner with a Vercel project of their own does the
same:

1. **Merge the chapter.** The push to `main` runs the migrate workflow in `docs/05-operations.md`; its summary
   lists `methods.0004_methodplan_top_n`. The new column is nullable, so the release before keeps working while
   it runs.
2. **Start a momentum plan** on a test account with a few candidates you already watch, a top N smaller than the
   list, and the first of this month as the start.
3. **Fetch the history** the window needs: the method page's **Get 5 years of history** for any candidate it lists
   as not ranked. Then read the ranking, the table and the review.

## Checkpoint

- `uv run pytest` prints `722 passed`; ruff and pyright pass.
- Listing 14-27 refuses a missing top N and a top N as large as the list, then starts the plan and names the
  symbols it put on the watch list.
- Listing 14-28 ranks ALPHA, BETA and GAMMA, lists DELTA as not ranked with the months it needs, and stages two
  buys of $50.00.
- Listing 14-29 fails `hold-top-n` with two findings and passes the other six rules.
- An index plan's pages are as they were: no ranking, no Top N column, no 12-1 column, no shading.
- Signed out, no page has a ranking, a symbol or a table; signed in as anyone but the owner, the method page is a
  404.
- Commit and push: `git add -A && git commit -m "Chapter 14: a second method, 12-1 momentum"`.

## Exercises

1. **Sell on paper.** Add a sell path for a holding that left the top N: read the position from Alpaca, close it
   with a deterministic id, book what it brought into the journal, and let the sync fix it. Show the wash-sale
   warning before Confirm when a buy follows a sale within 30 days. Write the decision first.
2. **Equal weight on the value held.** Today each month's new money is split equally. Add an option that also
   trims and tops up what you hold so each position is the same share of the total, using the stored closes, and
   a rule for how far off is too far.
3. **Rank changes.** Add a column to the ranking table with each candidate's place last month and an arrow for the
   move, from the same `rank` function run one month earlier (chapter 14a builds this).
4. **The rolling line.** On a candidate's history page, draw its 12-1 return for each of the last 24 months as a
   line, with the zero line marked.

## If you get stuck

- Browse: https://github.com/dapperAuteur/invest-witus/tree/v14
- Diff for this chapter: https://github.com/dapperAuteur/invest-witus/compare/e635e10...v14 (the diff from `v13`
  also holds the work between chapters that step 14.0 takes)
- Zip: https://github.com/dapperAuteur/invest-witus/archive/v14.zip
- Take the reference's files. Chapter 14 added `src/invest_witus/methods/momentum_12_1.toml`,
  `src/invest_witus/methods/momentum_12_1.py`, `src/invest_witus/adherence/momentum.py`,
  `src/invest_witus/adherence/rule_sets.py`, `src/invest_witus_site/methods/momentum.py`,
  `methods/migrations/0004_methodplan_top_n.py`, the templates `methods/_momentum.html` and
  `watchlist/_momentum_window.html`, and `tests/test_ch14.py`; and changed `methods/models.py`, `methods/engine.py`,
  `methods/forms.py`, `methods/views.py`, the method templates `method_page.html`, `_view_a.html`, `_view_b.html`,
  `_view_c.html`, `_versions.html` and `plan_change.html`, `paper/orders.py`, `prices/charts.py`, the template
  `prices/_chart.html`, `watchlist/views.py`, the templates `watchlist/_section.html` and `watchlist/history.html`,
  `holdings/views.py`, `holdings/templatetags/holdings_extras.py`, `pages/static/pages/site.css`,
  `pages/templates/pages/home.html` and one line of `tests/test_ch10.py`. No package changed, no environment
  variable was added, nothing moved:
  `git fetch reference --tags && git checkout v14 -- src tests`.
- `test_the_package_lists_its_methods_and_the_rules_file_still_matches_the_checks` (chapter 10) fails with
  `['index-dca', 'momentum-12-1'] == ['index-dca']`: change its first assertion as Listing 14-5 shows.
- `test_the_month_end_close_is_the_last_stored_day_of_the_month` gets 150: `month_ends` kept the first or the
  highest close of the month instead of the latest day.
- `test_the_ranking_is_highest_first_with_ties_in_symbol_order` puts GAMMA before ALPHA: the sort key is
  `-change` alone, so a tie keeps the input order.
- `test_a_month_with_nothing_ranked_is_not_judged_by_rank` finds rank findings: `review` checks ranks whenever a
  ranking exists, without `ranking.ranked`.
- `test_the_engine_ranks_each_month_from_stored_adjusted_closes` ranks BETA last: `price_series` reads `close`
  where `adj_close` is stored, so BETA's planted split reads as a fall.
- Chapter 10's view tests fail on the plan's sentence: an `else` branch in a view template is not byte for byte
  the old text (a space or a line break around `{% endif %}`).
- `test_the_change_form_carries_the_top_n_for_momentum_only` finds `top_n` in an index plan's form: the field is
  declared on the class and `__init__` did not delete it.
- `test_confirm_buys_the_top_n_in_equal_parts_once` finds "The plan names 2 symbols": chapter 11's refusal ran for
  a momentum plan; guard it with `not plan.is_momentum`.
- On Vercel after the merge, a page answers 500 with `no such column: top_n` or `column ... top_n does not
  exist` for about a minute: the migrate workflow is still running. Longer than that, open GitHub Actions and read
  the run.

## What we learned

- A window defined in calendar months needs month arithmetic and a rule for which day stands for the month; write
  both down before the code.
- A ranking should give the same order for the same inputs. Break ties on purpose.
- A result type that can say "not ranked, and here is why" is worth more on the page than a `None`.
- A second rule set in the first one's shape lets the engine branch once, and a registry with a test keeps every
  rules file matched to its checks.
- When an earlier test pinned a whole list, the honest fix is to say in the chapter what changed and why.
- A chart is readable when the shape, the sign and the words carry the meaning, and a table under it carries the
  numbers.

## Next

Chapter 14a adds two more pictures of momentum: how each candidate's rank moved since last month, and the 12-1
return as a line over time on each symbol's history page.

## References

Gray, W. R., & Vogel, J. R. (2016). *Quantitative momentum: A practitioner's guide to building a momentum-based
stock selection system*. Wiley.

Internal Revenue Service. (2026). *Publication 550 (2025): Investment income and expenses (including capital gains
and losses)*. Retrieved October 29, 2026, from https://www.irs.gov/publications/p550
