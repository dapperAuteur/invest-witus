# Chapter 09: The watch list

**Starts from:** tag `v08`. **Ends at:** tag `v09`.
**Written against:** Python 3.14.10, uv 0.13.6, Django 5.2.18, and the Django 5.2 and Python 3 documentation
pages as read on October 28, 2026.
**Goal:** symbols the signed-in owner follows in an account without holding them, typed on the account page
one or many at a time, each checked against one rule before it is stored, each fetched by the nightly pull from
chapter 08, and each shown with the latest stored close and its date. Another owner's account is a 404 for
every action, no public page shows a symbol or a price, and there is no buy button.
**Time:** 2 to 3 hours for the code and tests. The owner's step (the migration and the first symbols on the
live site) takes 10 minutes.

The listings in this chapter are not typed in by hand. `scripts/render_chapter.py` pastes the real files from
tag `v09` into the chapter text, so what you read and what the tests run are the same bytes.

## What you will learn

- **One rule at the boundary:** a function that trims, upper-cases and refuses with a reason, used by a model
  validator, by the form that parses a list, and in `save()`, so a bad symbol is refused everywhere and stored
  nowhere, and the refusal is a message beside the box, never a 500.
- **A form field that returns a parsed value:** `clean_<fieldname>()` turning one text box into a list of
  symbols and a list of refusals, and the line between "a form error" and "a line in the report".
- **`get_or_create` as the add:** one row per account and symbol by constraint, and an add path that reports
  what already existed instead of failing on it.
- **Django's messages framework:** a report that survives the redirect after a POST and is printed once by the
  base template, on whatever page the redirect lands on.
- **`require_POST` with `login_required`,** an ownership check that answers 404, and a remove that is a form,
  not a link.
- **A second app on another app's page:** a template include, a context builder the add view can call back
  into, and an app graph with no cycle in it.
- **Two tables on one page,** told apart by the test's reader.

## Before the code: what the PRD asks, and five decisions

**What the PRD asks.** Section 7.5: each account can have symbols the user wants to follow; the list shows the
latest stored close with its date; there is no buy button, because "A symbol reaches a plan only by the user
adding it to the plan's universe." The acceptance list: watch lists are private to their owner; a symbol the
price provider does not know shows a clear message, not a zero; removing a symbol keeps its history. Chapter 08
left the hook, `watch_symbols()` in the pull, returning nothing.

**Decision 1: a `watchlist` app, not more rows in `holdings`.** The chapter is one folder: a model, its
validator and parser, a form, two views, two URL names, an admin registration, a migration and one template
partial. The holdings app keeps what chapter 05 named it, accounts and statements, and changes in one place:
its account view hands the page a watch list and a form, the way chapter 08 handed it a valuation. The import
graph stays a line, not a loop: `watchlist.models` knows `holdings.models`; `prices.portfolio` and
`prices.pull` know `watchlist.models`; `holdings.views` knows `prices.portfolio` and `watchlist.forms`; and
`watchlist.views` knows `holdings.views`. Nothing in `watchlist.models` imports the prices app, so the pull can
import it without a cycle. Decisions log, row 79.

**Decision 2: one list per account, and no "change since added" yet.** The PRD sketches `WatchList` and
`WatchItem` with a name per list and an added price per item. This chapter builds `WatchItem(account, symbol,
note, added_at)`, unique on the account and the symbol: one list per account, which is what one owner with a
few accounts uses, and a `name` column is a one-line addition when a second list is wanted. The change since
the symbol was added needs the close on the day it was added, which for a new symbol does not exist until the
next nightly run; it is derivable later from the prices table and `added_at` with no new column, so no column
is added now. Row 80.

**Decision 3: the symbol rule.** A symbol is user text. After trimming and upper-casing: letters, digits, a dot
and a hyphen only, one to twelve characters. The dot and the hyphen are for share classes, which one vendor
writes with a dot and another with a hyphen; twelve is longer than any US ticker and short enough that a pasted
sentence is refused rather than stored. A mutual fund ticker is five letters ending in X and fits. `AB CD` has a
space and is refused; a thirteen-character string is refused; `index` becomes `INDEX`. The column stays twenty
characters wide, as the two other symbol columns are, so a join never truncates: the rule belongs to the
boundary, not the database. Row 81.

**Decision 4: what a refusal is.** The box takes one symbol or many, separated by commas or spaces. A refused
token beside a valid one does not block the valid one: the valid ones are added and the page reports three
things, what was added, what was already there, and what was refused with the reason. A submission in which
nothing is valid is a form error, beside the box, with the same reasons. So a typo costs one line of the
report, never the whole submission, and nothing a person types can reach the database or raise past the view.
Row 82.

**Decision 5: plain forms, a redirect, and messages; no htmx.** The roadmap had proposed django-htmx partials
for this chapter. A watch list of a dozen rows does not need a partial update: the add and the remove are a
POST, a redirect and a page, which chapter 04 taught, and the report rides on Django's messages framework,
which "allows you to temporarily store messages in one request and retrieve them for display in a subsequent
request (usually the next one)" (Django Software Foundation, n.d.-a). A package and a script tag would be the
chapter's largest listing for nothing a test could check. A later chapter that has a reason, such as the
operator console, can add it then. Row 83.

## Steps

### 09.1 The tests

Listing 09-1, Filename: `tests/test_ch09.py`:

{{file:tests/test_ch09.py}}

Things to notice:

- **Placeholder symbols only.** `INDEX` and `OTHER` from chapter 02, `FUNDX` in the shape of a fund ticker,
  `NONE` for a symbol no source knows, and two bad tokens. Never a real symbol, in a test or anywhere in the
  repository.
- **The `account` fixture has no statement.** A watch list can start before the first statement is entered,
  and most tests want one table on the page, not two. `account_with_statement` adds chapter 08's shape when a
  test needs both.
- **`Tables` keeps the tables apart.** Chapter 08's reader collected every row on the page into one list; this
  one starts a new list at each `<table>`, so the test can say which rows are the holdings and which the watch
  list, and that the holdings come first.
- **The constraint test wraps the second insert in `transaction.atomic()`.** After an `IntegrityError` the
  database connection is inside a broken transaction and refuses every query until it is rolled back; the
  `atomic` block gives the test a savepoint to roll back to, so the next line can go on and read the table.
- **The ownership tests try the owner's other account too.** Another owner is a 404 for add and remove, and so
  is a remove URL that names the right item under the wrong account of the same owner.
- **`strict` is a client with CSRF checks on.** The test client skips them by default, which is what every
  other test wants; this one proves the form is protected.
- **The admin test is the one place the validator matters.** The owner's page goes through the form, which
  parses first; the admin's own form does not, and the validator on the field is what turns `AB CD` into a
  message beside the box there instead of an error page.

Run the tests:

Listing 09-2, Terminal:

```sh
uv run pytest tests/test_ch09.py
```

```text
tests/test_ch09.py:28: in <module>
    from invest_witus_site.watchlist.models import (
E   ModuleNotFoundError: No module named 'invest_witus_site.watchlist'
=========================== short test summary info ============================
ERROR tests/test_ch09.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.53s ===============================
```

Red at import. No package is added this chapter, and no environment variable.

### 09.2 The app, its settings line and its URLs

Make the folder `src/invest_witus_site/watchlist/` with an empty `__init__.py`, an empty `migrations/__init__.py`,
and a `templates/watchlist/` folder for the partial.

Listing 09-3, Filename: `src/invest_witus_site/watchlist/apps.py`:

{{file:src/invest_witus_site/watchlist/apps.py}}

Listing 09-4, Filename: `src/invest_witus_site/settings.py`:

{{file:src/invest_witus_site/settings.py}}

One line in `INSTALLED_APPS`. Everything else is as chapter 08 left it; the docstring's last sentence says so.

Listing 09-5, Filename: `src/invest_witus_site/urls.py`:

{{file:src/invest_witus_site/urls.py}}

Listing 09-6, Filename: `src/invest_witus_site/watchlist/urls.py`:

{{file:src/invest_witus_site/watchlist/urls.py}}

The include sits at `accounts/<int:pk>/watch/`, and Django passes the `pk` it captures there on to the included
views along with whatever they capture themselves, so `remove` receives both the account's `pk` and the item's.
The two names, `watch-add` and `watch-remove`, are what the template uses.

### 09.3 The model and the rule

Listing 09-7, Filename: `src/invest_witus_site/watchlist/models.py`:

{{file:src/invest_witus_site/watchlist/models.py}}

- **`normalize_symbol` is the rule, written once.** It returns the symbol as it will be stored or raises a
  `ValueError` whose message is the reason, and nothing else in the chapter knows the rule. `re.fullmatch`
  returns a match only "If the whole string matches the regular expression pattern" and "`None` if the string
  does not match" (Python Software Foundation, n.d.), which is why the pattern needs no `^` or `$`. Inside the
  square brackets "Special characters except backslash lose their special meaning", so the dot is a dot, and a
  hyphen "placed as the first or last character" matches "a literal `'-'`" (Python Software Foundation, n.d.).
- **`validate_symbol` is the same rule as a validator.** "A validator is a callable that takes a value and
  raises a `ValidationError` if it doesn't meet some criteria" (Django Software Foundation, n.d.-b). It is on
  the field, so the admin's form, which is a `ModelForm`, runs it: "validators will not be run automatically
  when you save a model, but if you are using a `ModelForm`, it will run your validators on any fields that are
  included in your form" (Django Software Foundation, n.d.-b). The test calls `full_clean()` for the same
  effect, which "will not be called automatically when you call your model's `save()` method" (Django Software
  Foundation, n.d.-d), so `save()` applies the rule itself, as the next point says.
- **`save()` normalizes and refuses.** The same shape as chapter 05's statement line and chapter 08's close: the
  stored value is the normalized one whatever the caller passed, and a caller that skipped the form and the
  validator gets a `ValueError`, not a row.
- **`parse_symbols` is the box as a list.** Commas become spaces, `split()` with no argument splits on any run
  of whitespace including newlines, each token goes through the rule, a duplicate is kept once in the order
  typed, and a refused token is kept with its reason. It is a pure function, tested without a database.
- **`add_many` is one `get_or_create` per symbol.** The constraint says a symbol is on an account's list once;
  `get_or_create` is the add path that agrees with it, reporting `created` false instead of raising when two
  submissions race, and it goes through `save()`, so the rule runs once more. The note goes on new rows only: a
  symbol already on the list keeps the note it had.

Make the migration. The generated file imports the validator from this app, and ruff wants that import
grouped after Django's, so the fix command runs too:

Listing 09-8, Terminal:

```sh
uv run --env-file .env python manage.py makemigrations watchlist
uv run ruff format src/invest_witus_site/watchlist/migrations/
uv run ruff check --fix src/invest_witus_site/watchlist/migrations/
```

```text
Migrations for 'watchlist':
  src/invest_witus_site/watchlist/migrations/0001_initial.py
    + Create model WatchItem
1 file reformatted, 1 file left unchanged
Found 1 error (1 fixed, 0 remaining).
```

Listing 09-9, Filename: `src/invest_witus_site/watchlist/migrations/0001_initial.py`:

{{file:src/invest_witus_site/watchlist/migrations/0001_initial.py}}

The migration depends on the holdings app's first, because of the foreign key, and it records the validator by
its import path: the database never runs it, but a migration that adds the same field later must know it.

Listing 09-10, Filename: `src/invest_witus_site/watchlist/admin.py`:

{{file:src/invest_witus_site/watchlist/admin.py}}

The admin page exists for completeness. The watch list is the owner's to keep on the account page; the admin is
where the owner can see every account's list at once, filter by account, and fix a row.

### 09.4 The form

Listing 09-11, Filename: `src/invest_witus_site/watchlist/forms.py`:

{{file:src/invest_witus_site/watchlist/forms.py}}

- **`clean_symbols` returns a `ParsedSymbols`, not a string.** A `clean_<fieldname>()` method's return value
  "replaces the existing value in `cleaned_data`, so it must be the field's value from `cleaned_data` (even if
  this method didn't change it) or a new cleaned value" (Django Software Foundation, n.d.-f). Here it is a new
  value: the view reads `form.cleaned_data["symbols"].symbols` and `.refused`, "nicely converted into Python
  types" as the forms guide puts it (Django Software Foundation, n.d.-e).
- **The form is invalid only when nothing can be added.** Decision 4 in code: with one valid symbol the method
  returns, refusals and all; with none it raises, and the message carries the reasons so the person can fix the
  box. An empty box never reaches this method, because `CharField` is required and says so first.
- **`autocapitalize="characters"`** is for a phone's keyboard; the rule upper-cases anyway.

### 09.5 The two views

Listing 09-12, Filename: `src/invest_witus_site/watchlist/views.py`:

{{file:src/invest_witus_site/watchlist/views.py}}

- **Two decorators, in this order.** `login_required` is the outer one, so an anonymous request of any method
  goes to the sign-in with `?next=`; then `require_POST`, the "Decorator to require that a view only accepts the
  POST method", which answers with "a `django.http.HttpResponseNotAllowed`" (Django Software Foundation,
  n.d.-c), the 405 the test asks for. The other order would answer 405 to a signed-out GET and say nothing
  about signing in.
- **Ownership is the same query as chapter 08's,** `get_object_or_404(Account, pk=pk, owner=request.user)`, and
  the remove looks the item up inside that account, so no id from anywhere else matches.
- **The refused submission renders the page; the good one redirects.** With nothing to add, `account_page` from
  the holdings app draws the account page again with the bound form, and the reason appears beside the box,
  which is what chapter 04's waitlist did with a bad email. With something to add, the view adds it, writes up to
  three messages, and redirects to the account page, so a refresh repeats a GET.
- **Three levels, three lines.** `success` for what was added, `info` for what was already there, `error` for
  what was refused; the base template prints each with its level as a class, so the stylesheet can color them.
- **Removing deletes the row and nothing else.** The closes stay in the prices table: they are the pull's, a
  symbol may be watched again tomorrow, and the PRD's acceptance says removal keeps history.

### 09.6 The pull picks them up

Listing 09-13, Filename: `src/invest_witus_site/prices/pull.py`:

{{file:src/invest_witus_site/prices/pull.py}}

`watch_symbols()` is the hook chapter 08 left, filled in: every symbol on any account's list, as a set, and
`symbol_universe()` unions it with the held symbols as it already did. Nothing about the budget, the pause or
the 429 changes: a watched symbol is one more request in the same run, inside the same fifty. A watched symbol
the vendor does not know is recorded in `failed` and reads "no price yet" on the page, which is the PRD's
"clear message instead of a zero price".

Listing 09-14, Filename: `src/invest_witus_site/prices/portfolio.py`:

{{file:src/invest_witus_site/prices/portfolio.py}}

`watch_list` is the join for the new section, beside `value_snapshot`: the account's items in symbol order, the
newest close per symbol in chapter 08's two queries, and a row per item with its quote or `None`. A watched
symbol is never valued, since there are no shares to multiply; the close and its date are the row.

Listing 09-15, Filename: `src/invest_witus/valuation.py`:

{{file:src/invest_witus/valuation.py}}

One function pulled out, `is_stale`, so the statement line and the watch row share one definition of "too
old". The arithmetic is unchanged and chapter 08's tests still pass against it.

Listing 09-16, Filename: `src/invest_witus_site/prices/management/commands/pull_prices.py`:

{{file:src/invest_witus_site/prices/management/commands/pull_prices.py}}

Two strings changed in the command, the help line and the "Nothing to pull" sentence, because the universe now
has two sources.

### 09.7 The page

Listing 09-17, Filename: `src/invest_witus_site/holdings/views.py`:

{{file:src/invest_witus_site/holdings/views.py}}

`account_detail` became two functions. `account_page` builds the context and renders, with an optional bound
form, and does no ownership check of its own: that stays with the two callers that have the request's user, the
detail view here and the add view in the watchlist app. The holdings app imports the form; the watchlist app
imports this function; the line in decision 1 holds.

Listing 09-18, Filename: `src/invest_witus_site/holdings/templates/holdings/account_detail.html`:

{{file:src/invest_witus_site/holdings/templates/holdings/account_detail.html}}

Listing 09-19, Filename: `src/invest_witus_site/watchlist/templates/watchlist/_section.html`:

{{file:src/invest_witus_site/watchlist/templates/watchlist/_section.html}}

- **The include sits outside the `{% if snapshot %}` branch,** so an account with no statement yet still has its
  watch list and its form, and the holdings table, when there is one, comes first.
- **The same table class, one more column.** The last header cell holds the word "Remove" for screen readers
  only; each row's remove control is a form with one button whose accessible name is "Remove" plus the symbol,
  read by the test as `Remove FUNDX`. A link would let a prefetch or a crawler remove a row, which is the reason
  chapter 07 gave for making sign-out a form.
- **"no price yet" spans the three cells it cannot fill,** and under the table one line names the symbols with
  no close and says when it arrives: "Prices arrive after the nightly pull". The holdings table says the same
  thing in its own words from chapter 08.
- **The footer line says what the section is not.** Watching places no order and recommends nothing.

Listing 09-20, Filename: `src/invest_witus_site/pages/templates/pages/base.html`:

{{file:src/invest_witus_site/pages/templates/pages/base.html}}

The messages block is printed inside `<main>` on every page, and renders nothing when there are none, which is
every public page: the last page test in this chapter still finds no table, no `/accounts/` link and no symbol
on any of them. The loop is not optional: "Even if you know there is only one message, you should still iterate
over the `messages` sequence, because otherwise the message storage will not be cleared for the next request"
(Django Software Foundation, n.d.-a). The default storage "first uses `CookieStorage`, and falls back to using
`SessionStorage` for the messages that could not fit in a single cookie" (Django Software Foundation, n.d.-a);
the messages app and its middleware have been installed since chapter 05, for the admin, so nothing in the
settings changes.

Eight rules go at the end of `site.css`: `.watch-form` narrows the form as the waitlist's is narrowed,
`.holdings form`, `.holdings .link-button` and its `:hover` make the remove button read as a link inside its
cell, and `.messages`, `.message`, `.message.success` and `.message.error` draw the notices as boxes with the
accent color on a success and the danger color on a refusal.

### 09.8 Green, and the watch list on your laptop

Listing 09-21, Terminal:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

```text
276 passed in 6.07s
All checks passed!
126 files already formatted
0 errors, 0 warnings, 0 informations
```

Thirty-six new tests. Now migrate the laptop database:

Listing 09-22, Terminal:

```sh
uv run --env-file .env python manage.py migrate
```

```text
Operations to perform:
  Apply all migrations: accounts, admin, auth, contenttypes, holdings, pages, prices, sessions, watchlist
Running migrations:
  Applying watchlist.0001_initial... OK
```

Then use it as the owner. Under `runserver`, sign in at `/admin/` with your chapter 05 superuser (a login is a
login, as chapter 07 noted), open `/accounts/`, then an account. Below the statement, or below "No statement
yet.", is the Watch list section with its box. Type `index, fundx a$b` and submit. The page comes back with a
green notice, "Added to the watch list: INDEX, FUNDX.", a red one, "Refused: A$B (only letters, digits, a dot
and a hyphen are allowed).", two rows reading "no price yet", and the line that says prices arrive after the
nightly pull. Submit `index` again and the notice is "Already on the watch list: INDEX." Press a row's Remove
and the row goes, with a notice.

Without a browser, the same through the test client, the way chapter 08 looked at the cron route:

Listing 09-23, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -c "from django.contrib.auth.models import User; from django.test import Client; from invest_witus_site.holdings.models import Account; from invest_witus_site.prices.pull import symbol_universe; u = User.objects.get(is_superuser=True); a = Account.objects.filter(owner=u).first(); c = Client(); c.force_login(u); r = c.post(f'/accounts/{a.pk}/watch/add/', {'symbols': 'index, fundx a\$b'}, follow=True); print(r.redirect_chain); [print(line.strip()) for line in r.content.decode().splitlines() if 'class=\"message ' in line]; print(symbol_universe())"
```

```text
[('/accounts/1/', 302)]
<li class="message success">Added to the watch list: INDEX, FUNDX.</li>
<li class="message error">Refused: A$B (only letters, digits, a dot and a hyphen are allowed).</li>
['FUNDX', 'INDEX']
```

(The account id is whichever account is first in your database, and the universe also lists whatever your
statements hold.) The two watched symbols are now in the pull's universe. Give the CSV source a file for the
fund-style symbol, from chapter 02's sample as chapter 08 did for `INDEX`, and pull:

Listing 09-24, Terminal:

```sh
mkdir -p data/private/prices
cp data/sample/illustrative-daily-prices.csv data/private/prices/FUNDX.csv
uv run --env-file .env python manage.py pull_prices --since 2026-09-22
uv run --env-file .env python manage.py pull_prices --since 2026-09-22
```

```text
Source csv, 2026-09-22 to 2026-10-29, 2 symbol(s), 2 request(s).
Inserted 14, updated 0, unchanged 0.
Source csv, 2026-09-22 to 2026-10-29, 2 symbol(s), 2 request(s).
Inserted 0, updated 0, unchanged 14.
```

(The second date is today's, whatever day you run it. On a database that already holds chapter 08's seven
`INDEX` days, the first line reads `Inserted 7, updated 0, unchanged 7`; on one whose statements hold other
symbols, those are in the count too.) The symbols came from the watch list, not from `--symbols`; the budget,
the pause and the refusal rules are chapter 08's. Read the page again, through the test file's own table reader:

Listing 09-25, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -c "from django.contrib.auth.models import User; from django.test import Client; from invest_witus_site.holdings.models import Account; from tests.test_ch09 import tables_in; u = User.objects.get(is_superuser=True); a = Account.objects.filter(owner=u).first(); c = Client(); c.force_login(u); html = c.get(f'/accounts/{a.pk}/').content.decode(); [print(row) for table in tables_in(html) for row in table]"
```

```text
('Symbol', 'Note', 'Close', 'As of', 'Source', 'Remove')
('FUNDX', '', '110.10', '2026-09-30 stale', 'csv', 'Remove FUNDX')
('INDEX', '', '110.10', '2026-09-30 stale', 'csv', 'Remove INDEX')
```

Before the pull the same command printed `no price yet` in each row; now each has the sample file's last close
and its date, and the word `stale`, because the sample ends on September 30, 2026 and today is weeks later.
That word is the point of showing the date: a number without its day is a number you cannot judge. On the
reference app the source is `tiingo` and the date is the last trading day. On a database with a statement, the
holdings table prints first and the watch list after it.

### 09.9 What the owner does outside the editor

The reference app's steps are task 10 in the owner's queue. A learner with a Vercel project of their own does
the same:

1. **Merge the chapter** and let Vercel deploy `main`.
2. **Migrate,** from your machine against the direct connection, with chapter 06's recipe as task 04 corrected
   it for a project whose variables are all marked Sensitive: one line, `STORAGE_DATABASE_URL_UNPOOLED=<the direct
   string from the Neon console>`, in a throwaway `.env.migrate` (git ignores `.env.*`), then
   `DJANGO_SECRET_KEY=only-for-this-shell-not-the-real-one VERCEL= uv run --env-file .env.migrate python manage.py
   migrate --database direct`, then delete the file. Expect `Applying watchlist.0001_initial... OK`.
3. **Add the symbols you want to follow,** signed in with WitUS, on each account's page. Each row reads "no
   price yet" until the next run.
4. **Run the cron once,** the way chapter 08 did (the Cron Jobs page's run button, or `curl` with the secret in
   the shell for one command). The response's `symbols` now lists the watched ones with the held ones; a symbol
   Tiingo did not know is in `failed`.
5. **Open the account page again:** every watched row has a close, its date and `tiingo` as the source.

## Checkpoint

- `uv run pytest` prints `276 passed`; ruff and pyright pass.
- Listing 09-23 answers with the two notices and the universe that lists the watched symbols.
- Listing 09-24 inserts the watched symbols' days the first time and changes nothing the second time.
- Listing 09-25 shows a close and a date in each watched row; before the pull it showed `no price yet`.
- Signed out, every public page has no `<table`, no link to `/accounts/` and no symbol; a POST to
  `/accounts/<id>/watch/add/` redirects to the sign-in.
- Signed in as someone who does not own the account, add and remove are 404.
- Commit and push: `git add -A && git commit -m "Chapter 09: The watch list"`.

## Exercises

1. The PRD wants the change since a symbol was added. Add a `since_added` to `WatchedSymbol`: the newest
   close minus the first stored close on or after `added_at`'s date, or `None` while either is missing. Write
   the test first, with two closes planted around the `added_at` you set by hand, and show the figure in a
   column with its sign, using chapter 05's `signed` filter.
2. A second list per account. Add a `name` to `WatchItem` with a default of `"Watch list"`, move the unique
   constraint to the account, the name and the symbol, and let the form take a list name. Decide, and write
   down, what happens to the rows that already exist when the migration runs.
3. The remove button is a form inside a table cell. Replace the stylesheet rules that make it read as a
   link with one rule that makes it a small button, and check the result at a phone's width: nothing should
   scroll sideways.

## If you get stuck

- Browse: https://github.com/dapperAuteur/invest-witus/tree/v09
- Diff for this chapter: https://github.com/dapperAuteur/invest-witus/compare/v08...v09
- Zip: https://github.com/dapperAuteur/invest-witus/archive/v09.zip
- Take the reference's files. Chapter 09 changed `src/invest_witus/valuation.py`,
  `src/invest_witus_site/settings.py`, `src/invest_witus_site/urls.py`, `holdings/views.py`, the template
  `holdings/account_detail.html`, `pages/templates/pages/base.html`, `pages/static/pages/site.css`,
  `prices/pull.py`, `prices/portfolio.py`, `prices/management/commands/pull_prices.py` and
  `docs/site/privacy.md`, and added `src/invest_witus_site/watchlist/` (the whole app) and
  `tests/test_ch09.py`. No package changed, no environment variable was added, nothing moved:
  `git fetch reference --tags && git checkout v09 -- src tests docs/site/privacy.md`.
- `No module named 'invest_witus_site.watchlist'` after 09.2: the folder has no `__init__.py`, or it was made
  under `holdings/` instead of beside it.
- `ImportError: cannot import name 'account_page'` or a circular import at startup: `holdings/views.py` imports
  from `watchlist/views.py`. It must import the form only; the views import the other way.
- `test_the_model_refuses_a_bad_symbol_before_the_row_is_written` fails on `message_dict`: the validator wraps
  the reason in other words. It must raise `ValidationError(str(error))` and nothing more.
- `test_a_symbol_is_on_an_accounts_list_once` raises no `IntegrityError`: the `UniqueConstraint` is missing
  from `Meta`, or names other fields. A `django.db.utils.ProgrammingError` on the lines after it: the second
  insert was not inside `transaction.atomic()`.
- `test_typed_symbols_split_on_commas_and_spaces_each_once_with_the_refusals` keeps a newline-joined token:
  `split(" ")` splits on one space only; call `split()` with no argument.
- `test_adding_many_reports_added_existing_and_refused_in_one_submission` has no "Refused" line: the form
  raised on the refusals. It raises only when `parsed.symbols` is empty.
- `test_a_submission_with_nothing_valid_is_a_form_error_not_a_500` gets 302: the view redirected on an invalid
  form. It renders the page again with the bound form.
- `test_the_watch_routes_need_a_sign_in_and_a_post` sees 405 for the anonymous POST: the decorators are in the
  other order; `login_required` goes on top.
- `test_another_owner_gets_a_404_for_add_and_remove` gets 200 on the owner's other account: the item lookup
  lacks `account=account`.
- `test_watched_symbols_join_the_universe_and_cash_stays_out` sees `set()`: chapter 08's placeholder body is
  still there. A `list` where a `set` is expected: `values_list(..., flat=True)` is a queryset; wrap it in
  `set(...)`.
- `test_the_pull_fetches_a_watched_symbol_and_the_page_shows_its_close` prints "Nothing to pull": the
  `symbol_universe` union was lost when `watch_symbols` was edited.
- `test_the_command_says_when_nothing_is_held_or_watched` fails: the command's old sentence.
- `test_the_page_shows_each_close_with_its_date_or_says_prices_arrive_after_the_pull` differs in the header
  row: the last header cell is empty; it holds "Remove" in a `sr-only` span. Rows in the wrong order: `Meta.ordering`.
- `test_the_page_with_a_statement_shows_the_holdings_first_and_the_watch_list_after` fails to unpack: the
  include is inside the `{% if snapshot %}` branch, or sits above the holdings table.
- `test_an_empty_watch_list_shows_the_form_and_no_table` finds a table: the `{% if watch.rows %}` guard is
  missing, so an empty `<table>` renders.
- `test_the_admin_lists_the_watch_list_and_refuses_a_bad_symbol_with_a_form_error` gets 404: `admin.py` does
  not register the model, or the app's `name` in `apps.py` is not `invest_witus_site.watchlist`. An
  `IntegrityError` or a 500 instead of the message: `validators=[validate_symbol]` is missing from the field.
- `ruff check` reports an import-order error in the migration: Listing 09-8's third command.
- In the browser the form submits but no notice appears: the `{% if messages %}` block is not in `base.html`,
  or the `messages` context processor was removed from the settings.
- On Vercel after the merge, the account page answers 500 and the log says `no such table` or `relation
  "watchlist_watchitem" does not exist`: step 2 of 09.9 has not run.

## What we learned

- A rule for user text lives in one function that normalizes and refuses with a reason; the validator, the
  form, the admin and `save()` all call it, so there is one place to change it and no path around it.
- A form field's `clean` method can return a parsed value, and the line between a form error and a line in the
  report is a decision to write down: here, a refusal costs one line, a submission with nothing valid is an
  error, and nothing typed can raise past the view.
- `get_or_create` is the add that agrees with a unique constraint: it reports instead of failing, it survives a
  race, and it runs `save()`.
- The messages framework carries a report across a redirect; the base template prints it once, on whatever
  page comes next, and a page with no messages prints nothing.
- A POST-only view behind `login_required`, with ownership in the query, answers 302, 405 and 404 in that
  order of questions: who are you, what are you doing, is it yours.
- A second app can own a section of another app's page through an include and a context builder, and the
  import graph stays a line when the page's app imports the form and the acting app imports the builder.
- The pull did not change: a watched symbol is one more request inside the same budget, and a symbol the vendor
  does not know is a line in `failed` and "no price yet" on the page.

## Next

Chapter 10 brings the method engine into the app: chapter 03's rule blocks loaded from the database, daily
rule checks with evidence and lesson links, and the three views over the same data. The watch list is one of
its inputs; nothing here changes for it.

## References

Django Software Foundation. (n.d.-a). *The messages framework*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/ref/contrib/messages/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-b). *Validators*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/ref/validators/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-c). *View decorators*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/http/decorators/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-d). *Model instance reference*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/ref/models/instances/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-e). *Working with forms*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/forms/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-f). *Form and field validation*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/ref/forms/validation/ (retrieved October 28, 2026)

Python Software Foundation. (n.d.). *re: Regular expression operations*. Python 3 documentation.
https://docs.python.org/3/library/re.html (retrieved October 28, 2026)
