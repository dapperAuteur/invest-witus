# Chapter 11: Alpaca paper trading and the monthly review

**Starts from:** tag `v10`. **Ends at:** tag `v11`.
**Written against:** Python 3.14.10, uv 0.13.6, Django 5.2.18, httpx 0.28.1, and Alpaca's documentation pages as
read on October 29, 2026.
**Goal:** the method page places the month's buys. On an account linked to Alpaca's paper environment, the
method page shows "This month's buys", computed from the plan, with the practice budget the app keeps beside
it, and a Confirm button. One click sends one market order per symbol for the dollar amount to Alpaca paper,
with an order id built from the account, the plan, the month and the symbol, so a second click or a retry never
buys twice, and writes each order into the journal. A closed market is said in words and the order is queued for
the open. A nightly step reads the orders back and fills in the shares. The client talks to the paper host only
and refuses the live one; every Alpaca failure is a message on the page, never a 500; only the site owner sees
any of it.
**Time:** 5 to 6 hours for the code and tests. Your own Alpaca paper keys and a first order take 20 minutes.

The listings in this chapter are not typed in by hand. `scripts/render_chapter.py` pastes the real files from
tag `v11` into the chapter text, so what you read and what the tests run are the same bytes.

## What you will learn

- **A broker client written out:** httpx, two headers, a timeout on every call, and a short list of exceptions
  that say what went wrong in the vendor's own words, so a page can print them and nothing becomes a 500.
- **Refusing a host:** a client that can only be built for one URL, and settings that refuse to start when the
  environment points at another.
- **Idempotency you can test:** an id made from the facts of the order, a unique column, a row lock, and the
  vendor's own duplicate refusal, which together make "click twice" and "retry after a timeout" the same order.
- **A transaction around a network call,** and why the error is raised after the block rather than inside it.
- **Constraints with their own words:** `violation_error_message` on a `CheckConstraint` and on a partial
  `UniqueConstraint`, so the admin says why a row is refused.
- **A fake vendor:** a class that answers the routes the app calls, behind httpx's `MockTransport`, so the whole
  confirm, retry and sync story runs in the test suite with no network and no keys.
- **Reading money at the boundary:** strings and JSON numbers from a vendor turned into `Decimal`, `true`
  refused as a number, timestamps parsed with their offsets.

## Before the code: what the PRD asks, what Alpaca's pages say, and eight decisions

**What the PRD asks.** Section 7.7: paper by default, with the paper host printed beside the environment;
orders the rules produce are staged and placed only when the user confirms; the app keeps its own practice
budget per plan, refuses orders beyond what is left, and ignores Alpaca's balance; Alpaca's paper limits are
stated wherever paper results appear; live trading stays behind a checklist with separate keys. Acceptance: a
paper key can never be sent to the live host, and a test asserts it; keys are read on the server only, never
rendered, logged or committed; the daily job copies orders and fills into the app. Research 05 adds the reason
for the budget: Alpaca's paper account starts at a default balance that cannot be set, so the app keeps the
number.

**What Alpaca's pages say (read October 29, 2026).** The paper and live Trading APIs are two hosts,
`https://paper-api.alpaca.markets` and `https://api.alpaca.markets`, and "Paper and live trading use separate
API domains and separate credentials" (Alpaca, 2026b). The key pair travels as the headers `APCA-API-KEY-ID`
and `APCA-API-SECRET-KEY` (Alpaca, 2026b). An order is `POST /v2/orders`; `notional` is the "dollar amount to
trade. Cannot work with `qty`. Can only work for market order types and day for time in force", and
`client_order_id` is "A unique identifier for the order", at most 128 characters (Alpaca, n.d.-d). A day order
"If submitted after the close, it is queued and submitted the following trading day" (Alpaca, n.d.-e). Alpaca
refuses a repeated id with 422 "client_order_id must be unique", and a short account with 403 "insufficient
buying power" (Alpaca, 2026a). `GET /v2/orders/{order_id}` and `GET /v2/orders:by_client_order_id` read an
order back (Alpaca, n.d.-b, n.d.-c); `GET /v2/account` has `cash`, `buying_power` and `equity` (Alpaca,
n.d.-a); `GET /v2/clock` has `is_open` and `next_open` (Alpaca, n.d.-f). On paper, orders "will receive partial
fills for a random size 10% of the time", and dividends, slippage, market impact and regulatory fees are not
simulated (Alpaca, n.d.-g). Two things no page read that day said: a per-minute limit for the Trading API, and
whether an id may be reused once its order is final. The code assumes neither. Decisions log, row 94, has
every URL with its date.

**Decision 1: a `paper` app, a client written out, no pydantic and no `Protocol`.** The roadmap proposed a
broker client behind a `Protocol` with pydantic models at the boundary. The boundary is five small objects, and
chapter 08's Tiingo parser already showed how to read them: check each field, make every number a `Decimal`,
turn anything missing into one exception. A `Protocol` would have one implementation, and the tests replace the
network, not the class, through the same `transport` seam chapters 07 and 08 used. Decisions log, row 95.

**Decision 2: the host is a constant, and the live host is refused twice.** `check_host` accepts
`https://paper-api.alpaca.markets` and nothing else; for `api.alpaca.markets` the refusal says "live host". There
is no base-URL setting to get wrong. Alpaca's own tools read `APCA_API_BASE_URL`; this app does not, but if that
variable names any other host the settings refuse to start, because someone expected live trading here. Row 95.

**Decision 3: one field links an account, one owner holds the keys.** `Account.alpaca` is "" or `paper`; there
is no live choice. A `CheckConstraint` allows it on a paper account only and a partial `UniqueConstraint` allows
one per owner, because the server holds one pair of keys. On top of chapter 08's ownership query, every Alpaca
route requires a superuser: the keys are the site owner's, and a learner who somehow owned a linked row still
gets a 404. Row 96.

**Decision 4: the practice budget is the plan's, and spent comes from the journal.**
`MethodPlan.practice_budget` is optional, set on the start form or in the admin. Spent is every buy in the
account's journal since the plan started, placed or logged by hand; a pending order counts the moment it is
placed. Alpaca's cash is shown beside it and is not the plan's. Row 97.

**Decision 5: this month's buys, and Confirm for a one-symbol plan.** The amount is split across the plan's
symbols to the cent, with the left-over cents going one each to the first symbols, so the parts always add up.
Chapter 03's rules count one buy of the plan's amount each month, so two split orders would be two findings the
app caused itself; Confirm is offered for a one-symbol plan, and a two-symbol plan shows the split and says why.
Confirm is also refused, in a sentence, before the plan starts, after this month's window, when a buy for the
month is already logged by hand, with no budget, and over the budget, and every check runs again on the server
when the button is pressed. The box sits above the view switch, on all three views, so no view hides it.
Row 98.

**Decision 6: placed once.** The id is `iw-<account>-<plan>-<YYYY-MM>-<symbol>`. The table's column is
unique; the row is created or found and locked inside a transaction; a row that already existed without
Alpaca's id means an earlier try may have reached Alpaca, so Alpaca is asked for that id before anything is
sent; and Alpaca's 422 for a repeated id means the order exists, so it is read back. A refusal is stored on the
row and committed, and the next Confirm retries it. Row 99.

**Decision 7: the journal entry is written at Confirm and corrected by the sync.** One entry per order,
dated the day you confirmed (the window rule is about what you did; the fill's day goes in the note), for the
notional, shares empty until the order is final. A full fill keeps the notional and gets the shares; an order
that ended part filled is booked at shares times the average price; an order that ended with nothing filled was
never a trade, so its entry is removed and the order row keeps the history. When the market is closed the box
says so, the button reads "Confirm: queue for the open", and the order is the same day order Alpaca queues.
Row 100.

**Decision 8: the sync runs three ways, and chapter 08's cron keeps its shape.** `manage.py
sync_paper_orders`, a "Check orders now" button on the paper page, and a step in chapter 08's cron route after
the pull. The cron step runs only when both keys are set and adds an `orders` object to the JSON; without keys
the body is chapter 08's exactly, and `vercel.json` keeps its one cron. A 429 stops the run; any other refusal
is recorded for that order and the rest go on. Row 101.

## Steps

### 11.1 The tests

Listing 11-1, Filename: `tests/test_ch11.py`:

{{file:tests/test_ch11.py}}

Things to notice:

- **`FakeAlpaca` is the vendor.** It answers the six routes the app calls, keeps orders by id, and refuses a
  second order with an id it already has, with Alpaca's 422 and Alpaca's words. `fail` makes any route answer
  with a status and a body of your choice, which is how the refusal, timeout and 5xx tests are written.
- **The keys are made up and checked for.** `KEY_ID` and `SECRET` look like nothing real. Several tests assert
  that neither appears in a page, a URL or an error message.
- **The day is fixed.** `orders.today` is a function so the `fake` fixture can pin it to November 3, 2026,
  inside a seven-day window that opened on the 1st. A test that ran on the 20th would otherwise see "window
  closed".
- **Placeholder symbols only.** `INDEX` and `OTHER`, as in every chapter. The fake fills at made-up prices.
- **The owner is a superuser.** `create_superuser`, because Alpaca is the site owner's. The ownership test makes
  a plain user who owns a linked account and expects a 404.
- **The retry and the duplicate are separate tests.** One plants a row with no Alpaca id and an order Alpaca
  already has, and expects no POST at all; the other plants only Alpaca's order and expects one POST, Alpaca's
  422, and the order read back.
- **`fresh_settings` is chapter 06's helper** with the Alpaca names added to the ones it clears, and
  `raising=False`, because after a refused import the settings module is not in `sys.modules` to delete.

Run the tests:

Listing 11-2, Terminal:

```sh
uv run pytest tests/test_ch11.py
```

```text
tests/test_ch11.py:33: in <module>
    from invest_witus_site.paper import alpaca, orders
E   ModuleNotFoundError: No module named 'invest_witus_site.paper'
=========================== short test summary info ============================
ERROR tests/test_ch11.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.51s ===============================
```

Red at import. No package is added this chapter: httpx has been a dependency since chapter 07.

### 11.2 The settings, the app and its URLs

Two names join the settings, read from the environment like every other value, and one check refuses a live
host before Django finishes starting:

Listing 11-3, Filename: `src/invest_witus_site/settings.py`:

{{file:src/invest_witus_site/settings.py}}

The new lines are the last block and one entry in `INSTALLED_APPS`. The check compares the whole URL with the
paper host, so a trailing slash is fine and `https://api.alpaca.markets` is not.

Make the folder `src/invest_witus_site/paper/` with an empty `__init__.py`, an empty `migrations/__init__.py`,
`management/__init__.py` and `management/commands/__init__.py`, then the app's config:

Listing 11-4, Filename: `src/invest_witus_site/paper/apps.py`:

{{file:src/invest_witus_site/paper/apps.py}}

Listing 11-5, Filename: `src/invest_witus_site/urls.py`:

{{file:src/invest_witus_site/urls.py}}

Listing 11-6, Filename: `src/invest_witus_site/paper/urls.py`:

{{file:src/invest_witus_site/paper/urls.py}}

The paper routes hang under the account, as the method page's do, so the `pk` captured in the root file reaches
every view.

### 11.3 The client

Listing 11-7, Filename: `src/invest_witus_site/paper/alpaca.py`:

{{file:src/invest_witus_site/paper/alpaca.py}}

Things to notice:

- **The host is checked in `__init__`, before the keys.** `AlpacaPaper(key, secret, base_url=...)` with the live
  host raises `LiveHostRefused` whether or not keys are present, so no code path builds a client that could
  send a paper key to the live host.
- **`__repr__` is written by hand.** The headers hold the keys; a default `repr` in a traceback would print
  them.
- **One `_request` does all the talking.** A timeout becomes `AlpacaUnavailable`, any other httpx error too,
  each with `from None` so the chained exception (which can carry the request) is not printed; a 4xx or 5xx goes
  through `refusal`, which reads Alpaca's `message` and picks the exception by status.
- **The parsers are chapter 08's idea.** `json.loads(parse_float=Decimal)` so a JSON number is never a float;
  `optional_number` takes a string, an int or a Decimal and refuses `bool`, because `True` is an `int` in Python;
  `moment` uses `datetime.fromisoformat`, which reads Alpaca's `Z` and offsets and drops digits past the
  microsecond.
- **`buy_notional` takes no time in force.** Alpaca allows a dollar amount only on a market day order, so the
  client sends `market` and `day` and nothing else is possible.

### 11.4 The rows

Two fields join chapter 05's and chapter 10's tables, and one table is new. The account first:

Listing 11-8, Filename: `src/invest_witus_site/holdings/models.py`:

{{file:src/invest_witus_site/holdings/models.py}}

`Alpaca` is a `TextChoices` with no live member. The two new constraints carry `violation_error_message`, so
when the admin's form validates them it prints "Only a paper account can be linked to Alpaca paper." instead of
the default, "Constraint “%(name)s” is violated." (Django Software Foundation, n.d.). `is_alpaca_paper` compares with the string
`"paper"`: pyright reads `Account.Alpaca.PAPER` as the `(value, label)` pair it is declared with.

The plan's budget:

Listing 11-9, Filename: `src/invest_witus_site/methods/models.py`:

{{file:src/invest_witus_site/methods/models.py}}

`practice_budget` gets the same float guard and rounding as `amount`. It is nullable, so every plan from
chapter 10 stays valid.

The orders:

Listing 11-10, Filename: `src/invest_witus_site/paper/models.py`:

{{file:src/invest_witus_site/paper/models.py}}

- **`client_order_id` is unique in the table,** which is the app's half of the idempotency; Alpaca's 422 is the
  other half.
- **`filled_qty` keeps nine places,** Alpaca's precision; the journal keeps six, rounded down, as every share
  count in the app since chapter 01.
- **`plan` is `PROTECT`.** An order the app placed under a plan is history; deleting the plan should fail
  rather than lose it.
- **`journal_entry` is `SET_NULL`.** An order that ended unfilled loses its entry and keeps its row.

Make the three migrations, in this order (the paper table depends on the other two), then let ruff tidy them:

Listing 11-11, Terminal:

```sh
uv run --env-file .env python manage.py makemigrations holdings --name account_alpaca
uv run --env-file .env python manage.py makemigrations methods
uv run --env-file .env python manage.py makemigrations paper
uv run ruff format src/invest_witus_site/*/migrations/
uv run ruff check --fix src/invest_witus_site/*/migrations/
```

```text
Migrations for 'holdings':
  src/invest_witus_site/holdings/migrations/0002_account_alpaca.py
    + Add field alpaca to account
    + Create constraint alpaca_link_on_paper_accounts_only on model account
    + Create constraint one_alpaca_paper_account_per_owner on model account
Migrations for 'methods':
  src/invest_witus_site/methods/migrations/0002_methodplan_practice_budget.py
    + Add field practice_budget to methodplan
Migrations for 'paper':
  src/invest_witus_site/paper/migrations/0001_initial.py
    + Create model PaperOrder
3 files reformatted, 14 files left unchanged
Found 2 errors (2 fixed, 0 remaining).
```

Listing 11-12, Filename: `src/invest_witus_site/holdings/migrations/0002_account_alpaca.py`:

{{file:src/invest_witus_site/holdings/migrations/0002_account_alpaca.py}}

Listing 11-13, Filename: `src/invest_witus_site/methods/migrations/0002_methodplan_practice_budget.py`:

{{file:src/invest_witus_site/methods/migrations/0002_methodplan_practice_budget.py}}

Listing 11-14, Filename: `src/invest_witus_site/paper/migrations/0001_initial.py`:

{{file:src/invest_witus_site/paper/migrations/0001_initial.py}}

All three only add: a column with a default, a nullable column, a new table. The production workflow from the
last chapter applies them after the merge, and the old code keeps working on the new schema while it runs.

### 11.5 Stage, confirm, sync

Listing 11-15, Filename: `src/invest_witus_site/paper/orders.py`:

{{file:src/invest_witus_site/paper/orders.py}}

Things to notice:

- **`split_amount` works in whole cents.** `int(to_money(amount) / CENT)` is the amount in cents, `divmod`
  gives each part and the remainder, and the remainder goes one cent at a time to the first symbols. 100.00
  over three symbols is 33.34, 33.33 and 33.33, which add up to 100.00; a split in `Decimal` division would not.
- **`refusal_for` is a list of sentences in order.** The first that applies is the one the page prints. "All
  placed" is not a refusal: it is the state after a successful Confirm, and the page says so in its own words.
- **`place_one` raises after the `with` block.** An exception raised inside `transaction.atomic()` rolls the
  block back, and with it the message the row should keep. So the error is caught, the message saved, and the
  exception raised once the block has committed.
- **`select_for_update()` locks the row on Postgres** until the transaction ends, so a second request for the
  same buy waits for the first and then finds the order placed. SQLite ignores it, and has only one writer.
- **`submit` looks first only for an old row.** A row created by this request cannot have been sent before, so
  it is sent directly; Alpaca's 422 still catches two requests that raced past each other.
- **`reconcile_journal` is the one place the journal is written.** Confirm calls it with the day; the sync calls
  it with no day, so a new entry (rare: an order that had none) uses today.
- **`sync_orders` writes only what changed.** A status and fill that match the row skip the save, so a second
  run is quiet.
- **`PaperSection` is what the method page needs:** the staged buys, the clock, and one error string. It lives
  here, not in the views, so the method app imports the paper app's service module and never its views.

### 11.6 The pages

The paper app's views:

Listing 11-16, Filename: `src/invest_witus_site/paper/views.py`:

{{file:src/invest_witus_site/paper/views.py}}

`linked_account_or_404` is chapter 08's ownership query plus `alpaca_allowed`. Confirm and the sync are POST
only, behind `login_required` on top so a visitor is sent to the sign-in rather than told the method is not
allowed. Every `AlpacaError` becomes a message through Django's messages framework, as chapter 09's watch list
reported its refusals.

The paper account page:

Listing 11-17, Filename: `src/invest_witus_site/paper/templates/paper/paper_account.html`:

{{file:src/invest_witus_site/paper/templates/paper/paper_account.html}}

The band at the top is the line the PRD asks for, with the host printed beside the environment: "Paper money.
Live trading needs the checklist in a later chapter and separate keys." The practice budget comes before
Alpaca's account, and the paragraph between them says which number is the plan's.

The box on the method page:

Listing 11-18, Filename: `src/invest_witus_site/paper/templates/paper/_month_buys.html`:

{{file:src/invest_witus_site/paper/templates/paper/_month_buys.html}}

The button's label is the market's state. `|date:"Y-m-d H:i e"` prints the next open in the site's time zone,
UTC, with its name, so "2026-11-04 14:30 UTC" is the 09:30 Eastern open Alpaca sent as `-05:00`.

Three files from chapter 10 change by a few lines each. The method page's view builds the box when the account
is linked:

Listing 11-19, Filename: `src/invest_witus_site/methods/views.py`:

{{file:src/invest_witus_site/methods/views.py}}

Listing 11-20, Filename: `src/invest_witus_site/methods/templates/methods/method_page.html`:

{{file:src/invest_witus_site/methods/templates/methods/method_page.html}}

Listing 11-21, Filename: `src/invest_witus_site/methods/forms.py`:

{{file:src/invest_witus_site/methods/forms.py}}

The start form gains one optional field, the practice budget; chapter 10's tests post the form without it and
still pass. The account page links the paper page for the site owner:

Listing 11-22, Filename: `src/invest_witus_site/holdings/templates/holdings/account_detail.html`:

{{file:src/invest_witus_site/holdings/templates/holdings/account_detail.html}}

And the admin: the orders read-only, the new columns in two lists.

Listing 11-23, Filename: `src/invest_witus_site/paper/admin.py`:

{{file:src/invest_witus_site/paper/admin.py}}

Listing 11-24, Filename: `src/invest_witus_site/methods/admin.py`:

{{file:src/invest_witus_site/methods/admin.py}}

In `src/invest_witus_site/holdings/admin.py`, chapter 05's `AccountAdmin.list_display` gains `"alpaca"` after
`"kind"`; nothing else in that file changes.

### 11.7 The nightly step and the command

Listing 11-25, Filename: `src/invest_witus_site/prices/views.py`:

{{file:src/invest_witus_site/prices/views.py}}

Listing 11-26, Filename: `src/invest_witus_site/paper/management/commands/sync_paper_orders.py`:

{{file:src/invest_witus_site/paper/management/commands/sync_paper_orders.py}}

The cron step sits after the pull and inside `if keys_configured()`, so chapter 08's test of the exact JSON body
still passes on a copy with no keys. A failure reading orders goes into the body as `{"error": ...}` and the
prices stay stored.

### 11.8 The two names in `.env.example`

Listing 11-27, Filename: `.env.example`:

{{file:.env.example}}

The comment gives the dashboard path from Alpaca's own article, says the secret is shown once, and says what an
empty value does.

### 11.9 Green, and a confirm on your laptop against the fake

Listing 11-28, Terminal:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

```text
366 passed in 8.82s
All checks passed!
166 files already formatted
0 errors, 0 warnings, 0 informations
```

Fifty-four new tests. Migrate the laptop database:

Listing 11-29, Terminal:

```sh
uv run --env-file .env python manage.py migrate
```

```text
Operations to perform:
  Apply all migrations: accounts, admin, auth, contenttypes, holdings, methods, pages, paper, prices, sessions, watchlist
Running migrations:
  Applying holdings.0002_account_alpaca... OK
  Applying methods.0002_methodplan_practice_budget... OK
  Applying paper.0001_initial... OK
```

Link the account from chapter 10 and give its plan a budget. In the admin that is the account's **Kind**, set to
Paper (practice) if it is not already, its new **Alpaca** field, set to Alpaca paper, and the plan's **Practice
budget**. The same through the shell, for an account named `Practice` (use yours):

Listing 11-30, Terminal:

```sh
DJANGO_DEBUG=1 DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -v 0 -c "from decimal import Decimal; from invest_witus_site.holdings.models import Account; from invest_witus_site.methods.models import MethodPlan; a = Account.objects.get(name='Practice'); a.kind = 'paper'; a.alpaca = 'paper'; a.full_clean(); a.save(); p = MethodPlan.active_for(a); p.practice_budget = Decimal('1200'); p.full_clean(); p.save(); print(a.get_kind_display(), '/', a.get_alpaca_display(), '/', p.practice_budget)"
```

```text
Paper (practice) / Alpaca paper / 1200.00
```

`-v 0` keeps Django 5.2's shell from printing the list of names it imports for you. Now the whole confirm,
against the test file's fake Alpaca and with made-up keys, so nothing leaves your machine. The day is pinned to
November 3, 2026, inside the window of chapter 10's plan (days 1 to 7):

Listing 11-31, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
ALPACA_PAPER_KEY_ID=made-up-id ALPACA_PAPER_SECRET_KEY=made-up-secret \
uv run python manage.py shell -v 0 -c "
import re
from datetime import date
import httpx
from django.contrib.auth.models import User
from django.test import Client
from invest_witus_site.holdings.models import Account
from invest_witus_site.paper import alpaca, orders
from tests.test_ch11 import FakeAlpaca, text
fake = FakeAlpaca(); alpaca.transport = httpx.MockTransport(fake.handle); orders.today = lambda: date(2026, 11, 3)
u = User.objects.get(is_superuser=True); a = Account.objects.get(owner=u, alpaca='paper'); c = Client(); c.force_login(u)
box = text(c.get(f'/accounts/{a.pk}/method/')).split('<h2 id=\"buys-heading\">')[1].split('</section>')[0]
print('\n'.join(re.sub(r'<[^>]+>', '', line).strip() for line in box.splitlines() if re.sub(r'<[^>]+>', '', line).strip()))
for click in (1, 2):
    page = text(c.post(f'/accounts/{a.pk}/paper/confirm/', follow=True))
    print(click, re.findall(r'class=\"message \w+\">([^<]+)<', page))
print(len(fake.posted), 'order sent:', fake.posted[0])
"
```

```text
This month's buys
Alpaca paper (paper-api.alpaca.markets). Paper money. Live trading needs the checklist in a later chapter and separate keys.
Buy 100.00 of INDEX
Practice budget, the app's own number: 1200.00, spent 200.00, left 1000.00.
Confirm
One market order per symbol for the dollar amount, good for the day, on Alpaca's paper account. Each order goes in the journal at once; the nightly check fills in the shares.
1 ['Placed: buy 100.00 of INDEX, accepted.']
2 ['Already placed: INDEX, accepted. Nothing new sent.']
1 order sent: {'symbol': 'INDEX', 'side': 'buy', 'type': 'market', 'time_in_force': 'day', 'notional': '100.00', 'client_order_id': 'iw-1-1-2026-11-INDEX'}
```

Spent is 200.00 because chapter 10's two logged buys count against the plan's budget. Two clicks, one order
sent, and its id is made of the account, the plan, the month and the symbol (your ids may differ). Then the
sync, against a fresh fake that has the order and has filled it:

Listing 11-32, Terminal:

```sh
DJANGO_DEBUG=1 DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
ALPACA_PAPER_KEY_ID=made-up-id ALPACA_PAPER_SECRET_KEY=made-up-secret \
uv run python manage.py shell -v 0 -c "
import httpx
from django.core.management import call_command
from invest_witus_site.paper import alpaca
from invest_witus_site.paper.models import PaperOrder
from tests.test_ch11 import FakeAlpaca
order = PaperOrder.objects.get()
fake = FakeAlpaca(); alpaca.transport = httpx.MockTransport(fake.handle)
fake.fill(fake.add_order(order.client_order_id), qty='0.496277915', price='201.5')
print(order.client_order_id, order.status, order.journal_entry)
call_command('sync_paper_orders')
call_command('sync_paper_orders')
order.refresh_from_db(); entry = order.journal_entry
print(order.status, order.filled_qty, '|', entry, '|', entry.shares, '|', entry.note)
"
```

```text
iw-1-1-2026-11-INDEX accepted 2026-11-03 buy 100.00 of INDEX
Checked 1, changed 1: 1 filled, 0 ended part filled, 0 ended unfilled, 0 still open.
Checked 0, changed 0: 0 filled, 0 ended part filled, 0 ended unfilled, 0 still open.
filled 0.496277915 | 2026-11-03 buy 100.00 of INDEX | 0.496277 | Alpaca paper order order-1: filled, 0.496277 shares at 201.5 on 2026-11-04
```

The first run fills the row and the entry; the second finds nothing open. Nine places on the order, six on the
journal, rounded down. Open view B of the method page under `runserver` and November reads done, with shares.

### 11.10 Your own Alpaca paper keys

This step talks to Alpaca for real, with your keys, on paper.

1. Sign in at https://app.alpaca.markets. In the top bar, make sure the environment is **paper**.
2. On the dashboard, the **API Keys** module is on the right. Press **Generate New Key** (Alpaca, 2026b). The
   modal shows the key id and the secret; the secret is shown once, so copy both now.
3. Put them in your `.env` as `ALPACA_PAPER_KEY_ID=` and `ALPACA_PAPER_SECRET_KEY=`. Never in a chat, a
   commit or a screenshot. If one leaks, generate a new pair, which replaces the old one.
4. Run `uv run --env-file .env python manage.py runserver`, sign in, and open the paper page from the account
   page's "Alpaca paper" section. It shows Alpaca's cash, buying power and equity, and no positions yet.
5. On the method page, inside your plan's window, press Confirm. `INDEX` is a placeholder, not a symbol you
   chose; if Alpaca refuses it, the box says "not placed" with Alpaca's reason in its own words, which is the
   vendor-error path, live. To place an order that fills, start a plan on this account with the fund your
   lesson names; this repository never names one.
6. Check the order in Alpaca's paper dashboard, then press **Check orders now** on the paper page, or run `uv
   run --env-file .env python manage.py sync_paper_orders`, after it fills.

Outside market hours the button reads "Confirm: queue for the open" and the order waits for the next open, as
Alpaca's day order does.

### 11.11 What the owner does outside the editor

The reference app's steps are task 16 in the owner's queue. A learner with a Vercel project of their own does
the same:

1. **Set the two keys on Vercel** (Settings, Environment Variables, Production, Sensitive) if they are not there
   yet, and redeploy once.
2. **Merge the chapter.** The migrate workflow from `docs/05-operations.md` applies the three migrations after the
   push to `main`; until it finishes, about a minute, pages that read accounts or plans answer 500.
3. **Link the paper account** in the admin: Kind, Paper (practice); Alpaca, Alpaca paper.
4. **Give the plan a budget,** or start one on that account with it: the method page's start form has the field.
5. **Press Confirm** in the next buy window, then check the order in Alpaca's paper dashboard and on the paper
   page. The nightly cron fills in the shares; "Check orders now" does it at once.

## Checkpoint

- `uv run pytest` prints `366 passed`; ruff and pyright pass.
- Listing 11-30 prints the paper kind, the Alpaca link and the budget.
- Listing 11-31 prints the box, one "Placed" message, one "Already placed" message and one order sent with
  `time_in_force` `day`.
- Listing 11-32 fills the order once and prints the shares on the journal entry.
- `AlpacaPaper("id", "secret", base_url="https://api.alpaca.markets")` raises `LiveHostRefused`.
- Signed out, every public page has no `<table`, no link to `/accounts/` or `/paper/`, and no "This month's
  buys"; signed in as anyone but the site owner, every paper route is a 404.
- Commit and push: `git add -A && git commit -m "Chapter 11: Alpaca paper trading and the monthly review"`.

## Exercises

1. Hold with a reason. Add a POST route `paper-hold` with a required reason that writes a journal note for the
   month instead of an order, and make `refusal_for` treat a held month as done. Write the test first.
2. Plan value from the app's own fills. On the paper page, add a line that values the plan's journal shares at
   chapter 08's latest stored close, with the close's date, and compare it with Alpaca's `market_value`. Decide,
   and write down, which number the page calls the plan's.
3. Cancel an order from the app. Alpaca documents `DELETE /v2/orders/{order_id}`; read its page, add
   `cancel(order_id)` to the client, a button on the paper page for an order that is not final, and a test with
   the fake. What should the journal entry do?
4. A second linked account. The partial unique constraint allows one per owner. Lift it, add an
   `alpaca_account_number` column checked against `GET /v2/account`'s `account_number`, and refuse an order when
   they differ. What does a second pair of keys need?

## If you get stuck

- Browse: https://github.com/dapperAuteur/invest-witus/tree/v11
- Diff for this chapter: https://github.com/dapperAuteur/invest-witus/compare/v10...v11
- Zip: https://github.com/dapperAuteur/invest-witus/archive/v11.zip
- Take the reference's files. Chapter 11 changed `src/invest_witus_site/settings.py`,
  `src/invest_witus_site/urls.py`, `holdings/models.py`, `holdings/admin.py`, the template
  `holdings/account_detail.html`, `methods/models.py`, `methods/forms.py`, `methods/views.py`, `methods/admin.py`,
  the template `methods/method_page.html`, `prices/views.py`, `.env.example` and `docs/site/privacy.md`, and
  added `src/invest_witus_site/paper/` (the whole app), `holdings/migrations/0002_account_alpaca.py`,
  `methods/migrations/0002_methodplan_practice_budget.py` and `tests/test_ch11.py`. No package changed, two
  environment variables were added, nothing moved:
  `git fetch reference --tags && git checkout v11 -- src tests .env.example docs/site/privacy.md`.
- `ModuleNotFoundError: No module named 'invest_witus_site.paper'` after 11.2: the folder is missing its
  `__init__.py`, or it was made inside another app.
- `test_the_settings_refuse_to_start_when_anything_points_at_the_live_host` raises `KeyError:
  'invest_witus_site.settings'`: the helper's `delitem` lacks `raising=False`.
- `test_the_client_refuses_the_live_host_and_any_other` builds a client for `http://paper-api...`: `check_host`
  compares the host and forgets the scheme.
- A test finds the secret in `repr(client)`: `__repr__` is missing, and the default prints the attributes.
- `test_vendor_errors_become_typed_exceptions_with_alpacas_words` gets `AlpacaRefused` for the 500: `refusal`
  checks `>= 400` before `>= 500`. The order is 404, 429, 5xx, then the rest.
- `test_no_answer_and_a_bad_body_are_unavailable` sees `cash` accepted as `True`: `optional_number` tests
  `isinstance(value, int)` before refusing `bool`.
- `test_every_paper_route_is_the_owners_alone` raises `IntegrityError` while creating the unlinked account: the
  partial unique constraint lacks its `condition`, so it is a plain unique on `owner`.
- `test_confirm_places_each_buy_once_and_writes_one_journal_entry` sends two orders: `month_buys` builds
  `existing` from another month, or `StagedBuy.placed` checks the row instead of its Alpaca id.
- `test_a_retry_finds_the_order_alpaca_already_has` sends a POST: `submit` was called with `look_first=created`
  instead of `not created`.
- `test_a_vendor_refusal_is_a_message_and_buys_nothing` finds no row: the message is saved inside the
  `with` block and the exception raised there too, which rolls the save back.
- `test_the_sync_fills_a_pending_order_and_fixes_its_journal_entry` prints `0.496278` shares: the journal used
  `to_money` or `round`; shares round down through `to_shares`.
- `test_an_order_that_ends_unfilled_leaves_no_journal_entry` raises on `entry.delete()`: the order still points
  at the entry. Clear `order.journal_entry` and save the order first.
- `test_the_cron_route_pulls_the_last_seven_days_and_answers_counts` (chapter 08) fails with an extra `orders`
  key: the cron step runs without checking `keys_configured()`.
- `test_every_paper_route_is_the_owners_alone` gets 200 for the plain user: `alpaca_allowed` does not check
  `is_superuser`.
- `test_a_two_symbol_plan_shows_the_split_without_a_confirm_button` finds "Confirm": `refusal_for` has no
  symbol-count check, so a two-symbol plan with a budget is offered the button.
- A circular import at startup naming `methods.views` and `paper.views`: `methods/views.py` imports from
  `paper/views.py`. `paper_section` lives in `paper/orders.py`.
- On Vercel after the merge, the method page answers 500 with `no such column: practice_budget` or `relation
  "paper_paperorder" does not exist` for about a minute: the migrate workflow is still running. Longer than
  that, open GitHub Actions and read the run.

## What we learned

- A broker client is a few dozen lines of httpx when every call has a timeout, every failure is one of a short
  list of exceptions with the vendor's words, and every number is read into `Decimal` at the boundary.
- A safety rule is strongest as a constructor that cannot build the unsafe thing: no setting chooses the host,
  and the settings refuse a variable that suggests otherwise.
- "Click twice" and "retry after a timeout" are the same problem. An id made from the order's facts, a unique
  column, a row lock and the vendor's own duplicate refusal turn both into "the order you already have".
- A transaction rolls back what an exception passes through, so a failure that must be remembered is saved,
  committed, and raised afterwards.
- A constraint can carry its own message, and the admin prints it.
- A fake vendor behind the transport tests the whole story, including the parts that are hard to make happen
  for real: a race, a timeout, a 422, a partial fill.
- The app keeps its own budget and its own copy of every order, because the broker's balance cannot be set and
  its history can be deleted.

## Next

Chapter 12 is the journal: the logbook with automatic entries (this chapter's orders are the first), tags,
skips and holds with reasons, the rule-following rate, and a CSV export. The monthly review gains a close: a
journal entry that says the month is done.

## References

Alpaca. (n.d.-a). *Get account* [API reference]. Retrieved October 29, 2026, from
https://docs.alpaca.markets/reference/getaccount-1

Alpaca. (n.d.-b). *Get order by client order ID* [API reference]. Retrieved October 29, 2026, from
https://docs.alpaca.markets/reference/getorderbyclientorderid

Alpaca. (n.d.-c). *Get order by ID* [API reference]. Retrieved October 29, 2026, from
https://docs.alpaca.markets/reference/getorderbyorderid-1

Alpaca. (n.d.-d). *Create an order* [API reference]. Retrieved October 29, 2026, from
https://docs.alpaca.markets/reference/postorder

Alpaca. (n.d.-e). *Orders at Alpaca*. Retrieved October 29, 2026, from
https://docs.alpaca.markets/docs/orders-at-alpaca

Alpaca. (n.d.-f). *Get US market clock* [API reference]. Retrieved October 29, 2026, from
https://docs.alpaca.markets/us/reference/legacyclock

Alpaca. (n.d.-g). *Paper trading*. Retrieved October 29, 2026, from
https://docs.alpaca.markets/docs/paper-trading

Alpaca. (2026a, March 4). *How to fix common trading API errors at Alpaca*. Alpaca Learn.
https://alpaca.markets/learn/how-to-fix-common-trading-api-errors-at-alpaca

Alpaca. (2026b, September 14). *API key security best practices for Alpaca builders*. Alpaca Learn.
https://alpaca.markets/learn/api-key-security-best-practices-for-alpaca-builders

Django Software Foundation. (n.d.). *Constraints reference*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/ref/models/constraints/ (retrieved October 29, 2026)
