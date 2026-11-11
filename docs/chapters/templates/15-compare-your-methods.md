# Chapter 15: Compare your methods

**Starts from:** tag `v14a`, plus the reference's work between chapters (step 15.0). **Ends at:** tag `v15`.
**Written against:** Python 3.14.10, uv 0.13.6 and Django 5.2.18.
**Goal:** since decisions 159 and 160 each method can run in its own account, each linked to its own Alpaca paper
account. This chapter puts them side by side. **Compare methods** (`/compare/`) draws two to four of your accounts
on one chart, each line the account's value with the money you put in left out, rebased to 100, beside a
do-nothing line for an S&P 500 index fund from the app's own closes. A table under it says what each account put
in, what it holds now, its gain, its money-weighted and time-weighted returns, its worst drop, how many months the
plan has run and how often it was followed. Every number is rebuilt from the journal and the stored closes; where
one cannot be, the row says why.
**Time:** 3 to 4 hours for the code and tests. The laptop walk-through takes 10 minutes.

## What you will learn

- **Rebuilding a series from events:** a value for every day from a list of trades and a table of prices, with
  each trade counted from the first price day on or after it.
- **Two returns, two questions:** the time-weighted return leaves deposits out and judges the method; the
  money-weighted return (XIRR) counts when the money went in and judges the method and the timing together.
- **Finding a root by halving an interval,** in `Decimal`, with a clear "no answer" instead of a guess.
- **The worst drop** of a line, and why it is measured on the time-weighted line, not on a value that deposits keep
  lifting.
- **Refusing to stretch a short result:** three days are never turned into a yearly rate.
- **A fair test:** same cash, same monthly amount, same list of symbols; only the method differs.
- **A cross-check with a timeout,** read in threads so the page waits for the slowest answer, not the sum.

## Before the code: the arithmetic, and five decisions

**The value.** A buy of money `A` on a day whose price is `P` adds `A / P` units; with the shares `S` known
(Alpaca reports them), it adds `S x close / basis`, where the basis is the adjusted close. A day's value is every
unit held times that day's basis price, carried forward from the symbol's last stored day. The money put in is the
buys less the sells.

**The line.** Write `V(d)` for the value on day `d` and `F(d)` for the money put in that day. The level starts at
100 on the first day with a holding and moves as

```text
L(d) = L(d-1) x (V(d) - F(d)) / V(d-1)
```

so a deposit lifts `V` and `F` together and leaves `L` alone. `L(last) / 100 - 1` is the **time-weighted return**.

**XIRR.** The **money-weighted return** is the rate `r` that makes every flow, moved back to the first day, sum to
zero: each deposit negative, the last value positive,

```text
sum of  flow(i) / (1 + r) ^ (days(i) / unit)  = 0
```

where `unit` is 365 for a yearly rate. There is no formula for `r`; the code halves the interval from -99.9999% to
+100,000% until it is narrower than one ten-billionth.

**Decision 1: a chapter of its own, before the CentenarianOS events.** The page brings ideas a learner can use
anywhere (a value series, two returns, a root finder, a drawdown), so it is chapter 15 with its own checkpoint, and
the proposed CentenarianOS chapter becomes 16. No tag moved. Row 167.

**Decision 2: the yardstick is a symbol of your own.** The app names no real fund anywhere, so the page offers
every symbol you hold, watch or name in a plan, and starts on the first S&P 500 index fund it finds among them
(`SP500_FUNDS`). With no closes for it, the page says so and offers chapter 13's **Get history**, which returns to
the same comparison. Row 168.

**Decision 3: the journal and the closes, no cash ledger.** The app never kept the cash an account holds beside
its holdings, so the value is what the trades bought, and the page says so. A buy placed through Alpaca counts from
its fill's day with Alpaca's shares; an order still open is left out and counted. Alpaca's own equity is shown
beside it as a cross-check. Row 169.

**Decision 4: never stretch a short stretch to a year.** A loss of 14% over three days is a yearly rate of about
-99.99999998%: too close to -100% to find reliably and too large to mean anything. Under a year, XIRR is solved per
the stretch's own length and both returns read "over N days". Row 170.

**Decision 5: say why, never invent.** No trades, a symbol with no price by its trade day, or a sell of more than
was bought: the row prints the reason across its number columns. Row 171.

## Steps

### 15.0 Take the work between chapters

Between `v14a` and this chapter the reference took twelve pieces of work that are not chapters (decisions 155 to
166): a default view saved per person and a Settings page, a plan edited or deleted before anything happens under
it, cancelling a paper order, Alpaca key slots (one Alpaca paper account per Invest account) and their near-miss
names, the plan's amount read as the month's total, striped tables, and the Help bubble keeping its draft. Take them
from the commit this chapter starts from, then migrate:

Listing 15-1, Terminal:

```sh
git fetch reference --tags
git checkout c459ce7 -- src tests .env.example
uv run --env-file .env python manage.py migrate
uv run pytest -q
```

```text
Operations to perform:
  Apply all migrations: accounts, admin, auth, contenttypes, holdings, methods, outbox, pages, paper, prices, reports, sessions, watchlist
Running migrations:
  Applying holdings.0003_account_alpaca_slot_and_number... OK
  Applying methods.0005_view_preference... OK
933 passed
```

Commit that as its own step (`git commit -am "Take the reference's work between chapters 14a and 15"`).

### 15.1 The tests

Start red. The first half of the file checks the math on numbers small enough to work out by hand; the second half
plants closes and journal lines for two accounts and reads the page.

Listing 15-2, Filename: `tests/test_ch15.py`:

{{file:tests/test_ch15.py}}

Run them: every test fails on the first import, `invest_witus.compare`.

### 15.2 The math, with no Django

One module, plain values in and out. `value_series` walks the price days once, applying each day's trades and
pricing what is held; `period` cuts a stretch and works out what was carried into it; `time_weighted_line`,
`xirr` and `max_drawdown` are the three numbers. Read `xirr` closely: the two early `return None` lines are the
cases with no answer, and the loop stops on a tolerance or after 200 halvings, so it always ends.

Listing 15-3, Filename: `src/invest_witus/compare.py`:

{{file:src/invest_witus/compare.py}}

Try it before any page exists. The numbers are the tests' two buys of a placeholder fund, `INDEX`:

Listing 15-4, Terminal:

```sh
uv run python - <<'EOF'
from datetime import date
from decimal import Decimal as D

from invest_witus.compare import (
    DayPrice, Trade, cash_flows, line_return, max_drawdown, period,
    time_weighted_line, value_series, xirr,
)

days = [date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 7), date(2026, 1, 8)]
index = {"INDEX": [(d, DayPrice(D(p), D(p))) for d, p in zip(days, ["10", "11", "12", "9"])]}
trades = [Trade(days[0], "INDEX", D("100")), Trade(days[1], "INDEX", D("110"))]

series = value_series(trades, index, days[-1])
for day in series.days:
    print(day.day, day.value, day.flow, day.put_in)
line = time_weighted_line(series.days)
print([f"{level:.2f}" for _, level in line])
stretch = period(series.days, date(2026, 1, 1), days[-1])
assert stretch is not None
print("put in", stretch.put_in, "gain", stretch.gain)
print("time-weighted", f"{line_return(line):.4f}")
rate = xirr(cash_flows(stretch), days_per_unit=stretch.length)
print("money-weighted over", stretch.length, "days", f"{rate:.4f}")
drop = max_drawdown(line)
assert drop is not None
print("worst drop", f"{drop.fraction:.4f}", drop.peak_day, drop.trough_day)
EOF
```

```text
2026-01-05 100 100 100
2026-01-06 220 110 210
2026-01-07 240 0 210
2026-01-08 180 0 210
['100.00', '110.00', '120.00', '90.00']
put in 210 gain -30
time-weighted -0.1000
money-weighted over 3 days -0.1708
worst drop -0.2500 2026-01-07 2026-01-08
```

The line moves exactly with the price (10, 11, 12, 9): the $110 deposit on Tuesday did not lift it. The
time-weighted return is the price's -10%; the money-weighted return is worse, -17.08% over the three days, because
more money was in when the price fell.

### 15.3 From the app's records to the library's values

`records.py` reads the journal, the paper orders and the closes, and turns the library's numbers into the words
the table prints. Notice what it leaves out and says: an open order, a symbol on closes only, a trade after the
newest close. `followed` reuses chapter 12's review engine, so "followed" here means what "months followed" means
on the method page.

Listing 15-5, Filename: `src/invest_witus_site/compare/records.py`:

{{file:src/invest_witus_site/compare/records.py}}

### 15.4 The view, the chart and the page

The chart is chapter 13's. Its layout moved out of `build_plot` into `lay_out` in `prices/charts.py`, so lines that
are not stored closes can use it; a `Line` may carry its own hover text (`readout`), which `chart.js` prints instead
of a close, and a `Plot` its own caption and description. `build_plot` calls `lay_out`, so the history and Compare
symbols pages draw exactly as before.

Listing 15-6, Filename: `src/invest_witus_site/compare/views.py`:

{{file:src/invest_witus_site/compare/views.py}}

Listing 15-7, Filename: `src/invest_witus_site/compare/templates/compare/compare_methods.html`:

{{file:src/invest_witus_site/compare/templates/compare/compare_methods.html}}

Then the small changes: the app in `INSTALLED_APPS` and `path("compare/", ...)` in `urls.py`; **Compare methods**
in the header, the account list and under an account's method line; an optional `timeout` on `AlpacaPaper`,
`client_for_slot` and `client_for`; `return_to=compare-methods` in `owner_views.fetch_history` with
`compare_methods_url`, and the hidden `return_query` in `prices/_history_form.html`; and in `site.css`, a checkbox
in a `.choice-list` keeping its own size. Take them from the tag if you prefer:
`git checkout v15 -- src/invest_witus_site/prices src/invest_witus_site/paper/alpaca.py`.

### 15.5 Green, and the page on your laptop

Listing 15-8, Terminal:

```sh
uv run pytest -q
uv run ruff check . && uv run ruff format --check . && uv run pyright
uv run --env-file .env python manage.py makemigrations --check --dry-run
```

```text
969 passed
All checks passed!
262 files already formatted
0 errors, 0 warnings, 0 informations
No changes detected
```

On your laptop: give two paper accounts a plan each (the method page's start form), log a few buys in each
account's logbook over a month of stored closes (CSV files from chapter 02 work), put an index fund's placeholder
on a watch list with its closes, and open **Compare methods**. Point at the chart: each account's line shows its
level, its value and the money put in so far. Change **From** to a day after the first buy: the table's "Money put
in" now starts with "held at the start".

### 15.6 What the owner does outside the editor

Nothing to set up: no variable, no package, no migration. Merge the chapter and open **Compare methods**. If the
yardstick says it has no closes, press its **Get history**. On accounts linked to Alpaca paper, compare "Alpaca:
holdings now" with "Value here".

## Checkpoint

- `uv run pytest` prints `969 passed`; ruff, pyright and `makemigrations --check` pass.
- Listing 15-4 prints the four days, the line 100, 110, 120, 90, a gain of -30, -10% time-weighted, -17.08%
  money-weighted over 3 days, and a worst drop of 25%.
- Another person's account never appears on your page, even by its id.
- The history and Compare symbols pages draw as they did in chapter 13.
- Commit and push: `git add -A && git commit -m "Chapter 15: compare your methods"`.

## Exercises

1. **The same money in the yardstick.** Add a row: the yardstick bought with each account's own deposits on the
   same days, with its value and money-weighted return. Which question does it answer that the rebased line does
   not?
   *(The reference built this after the tag, on 2026-11-10, decision 185: `same_money` in `compare.py` buys the
   yardstick with each trade's money on the trade's own day at that day's stored adjusted close and names a day
   with no stored price instead of guessing; the page adds a "Same money into SPY" row under each account and its
   line on the chart while there is room for it. Try it yourself before you read `git diff v15 main -- src/invest_witus/compare.py`.)*
2. **A cash ledger.** Store each account's starting cash and every fill's cost, and show the whole account's value
   (holdings plus cash). Write the decision first: what does "money put in" mean once the cash was there from day
   one?
3. **Monthly returns.** Under the table, a grid of each account's time-weighted return per calendar month, with
   the best and worst month marked. Keep the reason where a month has no value.
4. **The worst drop's recovery.** Add how many days the line took to get back above its old high, or "not yet".

## If you get stuck

- Browse: https://github.com/dapperAuteur/invest-witus/tree/v15
- Diff for this chapter: https://github.com/dapperAuteur/invest-witus/compare/c459ce7...v15 (the diff from `v14a`
  also holds the work between chapters that step 15.0 takes)
- Zip: https://github.com/dapperAuteur/invest-witus/archive/v15.zip
- Take the reference's files. Chapter 15 added `src/invest_witus/compare.py`, the `src/invest_witus_site/compare/`
  app (`__init__.py`, `apps.py`, `records.py`, `views.py` and `templates/compare/compare_methods.html`) and
  `tests/test_ch15.py`; and changed `settings.py`, `urls.py`, `prices/charts.py`, `prices/owner_views.py`,
  `prices/static/prices/chart.js`, `prices/templates/prices/_chart.html` and `_history_form.html`,
  `paper/alpaca.py`, `pages/templates/pages/_header.html`, `holdings/templates/holdings/account_list.html` and
  `account_detail.html`, and `pages/static/pages/site.css`. Nothing moved:
  `git fetch reference --tags && git checkout v15 -- src tests`.
- `test_xirr_finds_the_yearly_rate_worked_out_by_hand` returns `None`: your present value used `days / 365` with
  integer division, or started the clock at the last flow instead of the first.
- `test_a_stretch_from_the_start_has_nothing_carried_in` finds an opening of 0 on day one but a gain off by the
  first day's move: you set the opening to the first day's value less its deposit when nothing was held before. Only
  carry a value in when the day before the range held something.
- The money-weighted return reads "not worked out" for a short losing stretch: you solved per year. Solve per the
  stretch's own length under a year (`days_per_unit`).
- Every account line is flat at 100: `time_weighted_line` divided by today's value instead of yesterday's.

## What we learned

- A value over time is a fold over days: apply the day's events, then price what is held.
- Leave the deposits out to judge a method; put them in to judge what happened to your money. Both are true; they
  answer different questions, and the page says which is which.
- A number found by search needs a stated interval, a tolerance, a step limit and an honest "no answer".
- Three days are three days. A yearly rate from them is noise multiplied.
- A comparison is fair only when everything but the method is the same, and even then a few months prove nothing.

## Next

Chapter 16 reads what a company reports to the SEC: its recent filings and its key numbers from SEC EDGAR. The
CentenarianOS events are chapter 17 (decision 184).
