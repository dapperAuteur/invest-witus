# Chapter 14a: Momentum over time: rank changes and the rolling 12-1 line

**Starts from:** tag `v14`, plus the reference's work between chapters (step 14a.0). **Ends at:** tag `v14a`.
**Written against:** Python 3.14.10, uv 0.13.6, Django 5.2.18, and the Kenneth R. French Data Library's page on
the momentum factor as read on November 1, 2026.
**Goal:** chapter 14 showed this month's ranking. This addendum shows how it got there. The method page of a
momentum account gains **Rank changes**: where each candidate ranked this month and last month, how far it moved,
whether it crossed the top-N line, and its place in each of the last twelve months. A watched symbol's history page
gains **12-1 return, month by month**: the number the ranking reads, computed for each of the last 24 months and
drawn as a line with a zero line, a table under it, and "not enough history" wherever a month's window is missing
a close. No new math: both pictures call chapter 14's `score` and `rank` once per month.
**Time:** 2 to 3 hours for the code and tests. The laptop walk-through takes 5 minutes.

This is an addendum to chapter 14, numbered `14a` so that it sorts after the chapter it extends and before chapter
15, which it does not change. The listings are generated from tag `v14a` by `scripts/render_chapter.py`.

## What you will learn

- **Reusing a function instead of writing new math:** a series of results is a loop over months around the
  function that already computes one month, so the page and the ranking can never disagree.
- **A result that can be "not enough history":** a month without both closes keeps its reason all the way to the
  table, and the chart leaves a gap instead of drawing a number nobody computed.
- **Breaking a line at a gap:** grouping consecutive points into runs, one polyline per run.
- **Comparing like with like:** ranking today's candidates in every month, so a column of places means the same
  thing in each month, and saying so on the page.
- **A chart with a zero line and a table:** a shared scale that always includes zero, and the table as the text
  alternative.

## Before the code: the formula, and four decisions

**The formula.** Write `P(m)` for the last stored adjusted close in calendar month `m`. A rebalance in month `M`
reads the 12-1 return

```text
R(M) = P(M-13) to P(M-2):   R(M) = P(M-2) / P(M-13) - 1
```

twelve months back from the start of `M`, less the latest full month, `M-1`, which is left out. This is chapter
14's window, unchanged. It is also the window of the momentum factor in Kenneth French's data library, whose stocks
need "a price for the end of month t-13 and a good return for t-2" (French, n.d.). The idea of buying the stocks
that rose the most over the past months is the one Jegadeesh and Titman (1993) tested: "strategies which buy stocks that have performed well in the past and sell stocks that have performed
poorly" earned significant positive returns over 3- to 12-month holding periods in their sample. That is a
finding about a past sample, not a promise about the next month, and the pages say so.

The **rolling 12-1 line** is `R(M-23), R(M-22), ..., R(M)`: one number per month for the last 24 months, each placed
at the month it is used in. The **rank change** of a candidate is `rank(M-1) - rank(M)`, where `rank` is its place
among the plan's candidates by `R`, 1 the highest: a positive number is a rise.

**Decision 1: today's candidates in every month.** A plan can change its list (chapter 12's versions). Ranking
each past month with the list it had would make the columns of the history table compare different lists. The
history ranks the list the plan names today in every month, and the page says "a month before you changed the list
shows how today's list would have ranked then". Row 153.

**Decision 2: no number where the window is not complete.** A month whose window lacks a close at either end has no
rank and no point. A candidate ranked in only one of the two months has no move in places: it is "new in the
ranking" or "not ranked this month". The line breaks at such a month instead of joining its neighbors. A month
missing *inside* a window changes nothing, because the return reads only its two ends. Rows 153 and 154.

**Decision 3: the point sits at the month it is used in.** The value plotted at November 2026 is the number a
November rebalance reads, from the end of October 2025 to the end of September 2026. The newest point is the same
number as this month's shaded window and badge from chapter 14. Row 154.

**Decision 4: tables first, one small chart.** The rank changes are two tables with arrows and words (`▲ up 2
places`), readable without color or script; a bump chart is left as an exercise. The rolling line is an SVG drawn
on the server in the style of the price chart, with a dashed zero line, one dot per month, and the table of every
month under it. Rows 153 and 154.

## Steps

### 14a.0 Take the work between chapters

Between `v14` and this chapter the reference took four pieces of work that are not chapters: a new symbol's first
fetch asks for two years (decision 149), the symbol profile (150), the Help bubble (151) and the two sign-out
buttons (152), plus a fix to a chapter 08 test whose statement date made it fail after October 30, 2026. Take them
from the commit this chapter starts from, then migrate:

Listing 14a-1, Terminal:

```sh
git fetch reference --tags
git checkout 17335d2 -- src tests .env.example
uv run --env-file .env python manage.py migrate
uv run pytest -q
```

```text
Operations to perform:
  Apply all migrations: accounts, admin, auth, contenttypes, holdings, methods, outbox, pages, paper, prices, reports, sessions, watchlist
Running migrations:
  Applying prices.0005_symbol_profile... OK
778 passed in 21.46s
```

Commit that as its own step (`git commit -am "Take the reference's work between chapters 14 and 14a"`).

### 14a.1 The tests

Listing 14a-2, Filename: `tests/test_ch14a.py`:

{{file:tests/test_ch14a.py}}

Things to notice:

- **The answers are worked out by hand.** `linear` closes month `i` at `100 + i`, so the December 2025 point is
  121 over 110, exactly `0.1`, and the comment says which two closes those are.
- **Eleven and twelve.** Eleven month-ends score nothing; twelve score exactly one month. A window spans eleven
  monthly returns and needs twelve month-end closes, the first one 13 months before the rebalance month. The test
  pins that boundary so nobody "fixes" it to thirteen.
- **The crossing candidates** are flat at 100 except for one or two months, so each one's return in each month is
  a number you can read off the docstring, and every kind of move appears once.
- **The split test runs twice:** once in the library, on two lists, and once through the stored rows, with a
  plain close that halves and an adjusted close that does not.
- **Dates relative to today, where the page reads today,** as in chapter 14.

Run them:

Listing 14a-3, Terminal:

```sh
uv run pytest tests/test_ch14a.py
```

```text
tests/test_ch14a.py:17: in <module>
    from invest_witus.methods.momentum_history import (
E   ModuleNotFoundError: No module named 'invest_witus.methods.momentum_history'
```

Red at import.

### 14a.2 The months, the line and the moves

Listing 14a-4, Filename: `src/invest_witus/methods/momentum_history.py`:

{{file:src/invest_witus/methods/momentum_history.py}}

Things to notice:

- **`rolling` calls chapter 14's `score` once per month.** The window, the month-end close and the "no close
  stored in" reason are chapter 14's. `month_end_series` only shrinks the input to one close per month first, so
  24 months read about 36 numbers instead of every daily close 24 times.
- **`segments` splits the points into runs** at every month without a number. A run of one is a lone dot, with no
  line to draw.
- **`Move.places` is `None`, not 0,** when either month has no place: zero would claim "same place", which is a
  fact nobody computed. `text` turns each case into words with an arrow.
- **`rank_history` calls chapter 14's `rank` once per month,** so the ties are placed A to Z, as on the method
  page, and the top N is the first N places.

### 14a.3 What the pages print

Listing 14a-5, Filename: `src/invest_witus_site/methods/momentum_history.py`:

{{file:src/invest_witus_site/methods/momentum_history.py}}

Things to notice:

- **One query per picture,** through chapter 14's `price_series`, from `first_day_needed`: the start of the oldest
  month's `M-13`. The adjusted close where the row has one, and the count of rows without.
- **The y scale includes zero** whatever the numbers are, so the dashed zero line is always on the chart. It reuses
  the price chart's `y_scale` and `y_ticks`, with a `%` added to each label.
- **The month labels count back from the newest month,** so this month is always labelled, and every other label
  is hidden on a narrow screen, the price chart's rule.

The method page passes one more value, on a momentum plan only. In `methods/views.py`, add the import and one entry
to the context of `render_method_page`:

Listing 14a-6, Filename: `src/invest_witus_site/methods/views.py` (two additions):

```python
from invest_witus_site.methods.momentum_history import rank_changes
```

```python
        # Chapter 14a: how each candidate's rank moved since last month, and its last twelve
        # places, on a 12-1 momentum plan only. One more query, for the closes those months read.
        "rank_changes": (
            rank_changes(plan, through) if plan is not None and plan.is_momentum else None
        ),
```

and include the partial in `method_page.html`, under chapter 14's:

```html
  {% if rank_changes %}{% include "methods/_rank_changes.html" with changes=rank_changes %}{% endif %}
```

Listing 14a-7, Filename: `src/invest_witus_site/methods/templates/methods/_rank_changes.html`:

{{file:src/invest_witus_site/methods/templates/methods/_rank_changes.html}}

The history page does the same on the account chapter 14 shades the window for. In `watchlist/views.py`, import
`rolling_line` and add to the context of `history`:

Listing 14a-8, Filename: `src/invest_witus_site/watchlist/views.py` (one addition):

```python
        "rolling": rolling_line(item.symbol, today) if window is not None else None,
```

and include the partial in `history.html`, under the window's:

```html
  {% if rolling %}{% include "watchlist/_rolling_12_1.html" %}{% endif %}
```

Listing 14a-9, Filename: `src/invest_witus_site/watchlist/templates/watchlist/_rolling_12_1.html`:

{{file:src/invest_witus_site/watchlist/templates/watchlist/_rolling_12_1.html}}

Things to notice:

- **The dots are HTML, the line is SVG.** The SVG is stretched to its box, so a circle in it would draw as an
  ellipse; a `span` placed by the same percentages stays round.
- **`n/r` is an `abbr`,** and a bold place carries " (top 2)" in a `sr-only` span, so a screen reader hears what
  sighted readers see in bold.
- **The table lists every month,** with "not enough history" and the months a window needs, newest first.

`site.css` gets a short block: the move colors, the rank tables kept on one line, the zero line, the run and the dot.

### 14a.4 Green, and both pictures on your laptop

Listing 14a-10, Terminal:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run --env-file .env python manage.py makemigrations --check --dry-run
```

```text
793 passed in 26.32s
All checks passed!
240 files already formatted
0 errors, 0 warnings, 0 informations
No changes detected
```

Fifteen new tests, and no migration: nothing is stored that was not stored before. Start a momentum plan on a new
account with the six crossing candidates, plant their closes with the test's own helper, and read the moves:

Listing 14a-11, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -v 0 -c "
import re
from django.contrib.auth.models import User
from django.test import Client
from invest_witus_site.holdings.models import Account
from tests.test_ch10 import tables_in, text
from tests.test_ch14a import crossing, plant_all, this_month
u = User.objects.get(is_superuser=True); c = Client(); c.force_login(u)
a, _ = Account.objects.get_or_create(owner=u, name='Crossing practice', defaults={'broker': 'Example Brokerage', 'kind': 'paper'})
m = this_month()
c.post(f'/accounts/{a.pk}/method/start/', {'method_id': 'momentum-12-1', 'amount': '100', 'buy_window_days': '7', 'symbols': 'ALPHA BETA GAMMA EPSILON ZETA DELTA', 'started_on': f'{m[0]}-{m[1]:02d}-01', 'top_n': '2'})
plant_all(crossing(m))
page = text(c.get(f'/accounts/{a.pk}/method/?view=a'))
print(re.search(r'<h2 id=\"rank-changes-heading\">([^<]+)<', page).group(1))
tables = tables_in(page)
for row in next(t for t in tables if 'Move' in t[0]): print(row)
places = next(t for t in tables if t[0][0] == 'Symbol' and len(t[0]) == 13)
for row in places: print(row[0], *row[-4:], sep=' | ')
"
```

```text
Rank changes since 2026-10
('Symbol', '2026-11', '2026-10', 'Move', 'Top 2')
('BETA', '1', '3', '▲ up 2 places', 'joined the top 2')
('GAMMA', '2', '2', '◆ same place', 'in')
('ALPHA', '3', '1', '▼ down 2 places', 'left the top 2')
('EPSILON', '4', 'not ranked', 'new in the ranking', 'out')
('DELTA', 'not ranked', 'not ranked', 'not ranked', 'out')
('ZETA', 'not ranked', '4', 'not ranked this month', 'out')
Symbol | 2026-08 | 2026-09 | 2026-10 | 2026-11
BETA | 2 (top 2) | 2 (top 2) | 3 | 1 (top 2)
GAMMA | 3 | 3 | 2 (top 2) | 2 (top 2)
ALPHA | 1 (top 2) | 1 (top 2) | 1 (top 2) | 3
EPSILON | n/r | n/r | n/r | 4
DELTA | n/r | n/r | n/r | n/r
ZETA | 4 | 4 | 4 | n/r
```

Your months are the month you run it in and the ones before. Check BETA by hand: last month its window ended at
100 (0%, third), this month it ends at 120 (+20%, first): up two places, into the top 2. In August and September
every flat candidate returned 0%, so the places there are the A to Z tie order. Now read ALPHA's line:

Listing 14a-12, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -v 0 -c "
import re
from django.contrib.auth.models import User
from django.test import Client
from invest_witus_site.holdings.models import Account
from tests.test_ch10 import tables_in, text
u = User.objects.get(is_superuser=True); a = Account.objects.get(owner=u, name='Crossing practice'); c = Client(); c.force_login(u)
page = text(c.get(f'/accounts/{a.pk}/watch/ALPHA/?days=all'))
print(re.search(r'(\d+ of \d+ months have enough history)', page).group(1))
table = next(t for t in tables_in(page) if t[0] == ('Month', '12-1 return', 'From', 'To'))
for row in table[:5]: print(row)
print(table[-1])
"
```

```text
10 of 24 months have enough history
('Month', '12-1 return', 'From', 'To')
('2026-11', '0.0%', '2025-10-28, $100.00', '2026-09-28, $100.00')
('2026-10', '+30.0%', '2025-09-28, $100.00', '2026-08-28, $130.00')
('2026-09', '0.0%', '2025-08-28, $100.00', '2026-07-28, $100.00')
('2026-08', '0.0%', '2025-07-28, $100.00', '2026-06-28, $100.00')
('2024-12', 'not enough history', 'no close stored in 2023-11 or 2024-10; the window needs a close in 2023-11 and in 2024-10')
```

ALPHA's planted closes start 22 months back, so only the newest ten months have both ends. In a browser, sign in,
open **Crossing practice**: the method page shows **Rank changes** under the ranking; click ALPHA on the account
page's watch list to see the line, its spike in the month whose window ended on the 130 close, and the gap where
the history runs out.

### 14a.5 What the owner does outside the editor

Nothing new to set up: no variable, no package, no migration. Merge the chapter, open a momentum account's method
page and a candidate's history page, and press **Get history** with 5 years for any candidate whose older months
say "not enough history".

## Checkpoint

- `uv run pytest` prints `793 passed`; ruff, pyright and `makemigrations --check` pass.
- Listing 14a-11 prints six moves, one of each kind, and twelve months of places with the top 2 marked.
- Listing 14a-12 prints ten months with a number and "not enough history" with the months it needs.
- An index plan's pages are as they were: no Rank changes, no rolling line.
- Commit and push: `git add -A && git commit -m "Chapter 14a: rank changes and the rolling 12-1 line"`.

## Exercises

1. **A bump chart.** Draw the rank history as lines, one per candidate, place 1 at the top, with a gap at each
   "n/r". Keep the table as its text alternative.
2. **The list each version named.** Rank each past month with the candidates the plan version active in that month
   named, and mark the month where the list changed. Write the decision first: what does a move mean across a
   change of list?
3. **Every candidate on one line chart.** On the method page, draw each candidate's rolling 12-1 line on one chart
   with the price chart's dash patterns, so no line is told apart by color alone.
4. **Quintiles.** Split the candidates into five groups by this month's 12-1 return and show which group the top N
   comes from (the momentum views backlog, item 5).

## If you get stuck

- Browse: https://github.com/dapperAuteur/invest-witus/tree/v14a
- Diff for this chapter: https://github.com/dapperAuteur/invest-witus/compare/17335d2...v14a (the diff from `v14`
  also holds the work between chapters that step 14a.0 takes)
- Zip: https://github.com/dapperAuteur/invest-witus/archive/v14a.zip
- Take the reference's files. Chapter 14a added `src/invest_witus/methods/momentum_history.py`,
  `src/invest_witus_site/methods/momentum_history.py`, the templates `methods/_rank_changes.html` and
  `watchlist/_rolling_12_1.html`, and `tests/test_ch14a.py`; and changed `methods/views.py`,
  `methods/templates/methods/method_page.html`, `watchlist/views.py`, `watchlist/templates/watchlist/history.html`
  and `pages/static/pages/site.css`. Nothing moved: `git fetch reference --tags && git checkout v14a -- src tests`.
- `test_too_little_history_says_not_enough_instead_of_a_number` finds no scored month with twelve closes: your
  window asks for thirteen month-ends. The start is `M-13` and the end `M-2`: twelve month-ends apart, not thirteen.
- `test_each_candidate_moves_from_its_place_last_month_to_its_place_this_month` finds EPSILON "◆ same place":
  `places` returned 0 where a month had no rank. Return `None`.
- `test_a_gap_at_a_windows_end_breaks_the_line_and_a_gap_inside_it_does_not_change_it` finds one run: `segments`
  skipped the months without a number instead of closing the run there.
- The rolling line's dots are ovals: they are drawn inside the stretched SVG. Draw them as HTML, as Listing 14a-9
  does.

## What we learned

- A series of a computed number is the same function in a loop; call it, do not copy its arithmetic.
- "Not enough history" is an answer. Keep the reason, show it in the table, and leave the gap in the chart.
- A move needs two places. When one is missing, say what happened in words instead of printing a zero.
- A history table means something only if every column compares the same thing; when the app chooses what that
  is, the page has to say so.
- A zero line turns a line chart of returns into a picture of rises and falls.

## Next

Chapter 15 compares your methods: two to four accounts on one chart beside an index fund, with what each put in,
holds and gained (decision 167 placed it before the CentenarianOS events, now chapter 16).

## References

French, K. R. (n.d.). *Detail for monthly momentum factor (Mom)*. Kenneth R. French Data Library, Tuck School of
Business at Dartmouth. Retrieved November 1, 2026, from
https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/det_mom_factor.html

Jegadeesh, N., & Titman, S. (1993). Returns to buying winners and selling losers: Implications for stock market
efficiency. *The Journal of Finance, 48*(1), 65-91. https://doi.org/10.1111/j.1540-6261.1993.tb04702.x
