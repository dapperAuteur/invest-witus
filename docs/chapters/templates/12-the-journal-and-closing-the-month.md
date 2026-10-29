# Chapter 12: The journal and closing the month

**Starts from:** tag `v11`. **Ends at:** tag `v12`.
**Written against:** Python 3.14.10, uv 0.13.6, Django 5.2.18, and the documentation pages named in the
references as read on October 29, 2026.
**Goal:** the journal becomes a logbook, and every month gets a close. An entry can be a hold or a skip as well
as a trade, each with a reason it cannot be saved without, and any entry may carry your state of mind and a few
tags of your own. A skip with its reason explains a month with no buy: the review still lists the miss, says
why beside it, and marks the rule "explained" instead of "fail". Each month whose buy window has closed gets a
review you close with three short answers; once closed, that month's entries are read-only until you reopen it
with a reason, and every close and reopen is kept. A plan changes through a form that keeps the old numbers as
a dated version, and each month is judged by the version in force that month. On a paper account, a month whose
order ended with nothing filled offers "Place again". The logbook page filters by month, kind and tag, and
exports CSV.
**Time:** 5 to 6 hours for the code and tests. Closing your first three months on the laptop takes 15 minutes.

The listings in this chapter are not typed in by hand. `scripts/render_chapter.py` pastes the real files from
tag `v12` into the chapter text, so what you read and what the tests run are the same bytes.

## What you will learn

- **Additive migrations, for real:** `db_default` beside `default`, so the code from the last release can still
  write rows while the migration that added the columns runs.
- **Rules that span fields:** a model's `clean()` that knows a hold needs a reason and a trade needs an amount,
  run by every `ModelForm` and by the admin before anything is saved.
- **History as rows:** a plan that changes becomes a chain of versions, each pointing at the one it replaced,
  and a function that turns the chain into the span of days each version judges.
- **An audit trail:** a table that is only ever added to, and an admin that cannot edit or delete it.
- **Read-only by state:** a closed month refuses changes in the model, in the forms and in the admin, from one
  check.
- **A CSV export that is safe to open:** Python's `csv` module, a download response, and the formula guard a
  spreadsheet needs.

## Before the code: what the PRD asks, and nine decisions

**What the PRD asks.** Section 7.6, the logbook: manual entries including a skip with a reason, tags for mental
state and mistakes, the rule-following rate as the headline number, months marked by whether the rules were
followed and not by profit or loss, and export to CSV. Section 7.7: "Hold requires a reason", the monthly review
opens when the review day arrives and closing it is the owner's act, and "A review cannot be closed with an
unexplained skip." Section 7.1: "A deviation (a skip, an off-schedule order, drift past the method's band)
cannot be recorded without a reason", and "Changing a running plan's method or parameters creates a new plan
version with a dated note; old reviews keep pointing at the version they judged." Chapter 11's decisions log,
row 102, lists what it left for this chapter: Hold and Skip with a reason, closing the monthly review, ending or
changing a plan with a reason, and placing a month again after its order ended unfilled.

**Decision 1: a kind column, beside the action.** The obvious design adds `hold` and `skip` to the action's
choices. Chapter 10's tests use `hold` as the example of an action the review does not know, and those tests
must keep passing, because a tag never moves. So `JournalEntry` gains `kind`: `trade` (the default, every row
until now), `hold` or `skip`. A trade has an action, a symbol and an amount, as before; a hold or a skip has a
reason and no money, and a symbol is optional. The review only ever sees trades. Decisions log, row 103.

**Decision 2: a short fixed list of states, and free tags.** The state of mind is one of six words: calm,
focused, confident, unsure, stressed, rushed, or empty for not recorded. Each describes you at the moment of the
entry, never the market. Tags are your own: up to five, lower case, letters, digits and hyphens, at most 24
characters each, stored as one space-separated column. Renaming and merging tags, which the PRD lists, waits for
a tag table. Row 104.

**Decision 3: an explained miss is arrangement, not a new rule.** Chapter 03's review is unchanged, and so is
`CHECKED_RULES`: a month with no buy is still a finding of "Buy once in every month of the plan." The engine
attaches the reason of a skip logged in that month to that finding, the month reads "skipped" instead of
"missed", and the rule's status reads "explained" when every finding it has is explained. A skip explains only
a month with no buy; it does not excuse a sale, a late buy or a second buy. The next action treats a skipped
month as decided, and the paper box refuses to place an order for it. Row 105.

**Decision 4: a review row per month, opened when the window closes.** `MonthlyReview` holds the plan version,
the month, `opened_on` (the day the month's window closed), the three answers and `closed_at`. Nothing runs at
the end of a window, so the row is written the first time a page that shows the plan is drawn after that day;
`opened_on` is still the window's last day, whatever day you looked. Closing asks what you did, what the rules
said (started for you from the month's findings) and what you'll do next month, and it is refused while the
month has a missed buy with no skip. Closing writes no journal entry: the review row is the record, and an entry
would sit in the month it just made read-only. Row 106.

**Decision 5: a closed month is read-only, from one check.** `JournalEntry.clean()` refuses a line dated in a
closed month, and a change to a line that was dated in one. The method page's log form, the logbook's edit form
and the admin all run `clean()`, so the rule is written once; the admin also hides Delete for such a line.
Reopening needs a reason, and `ReviewEvent` keeps every close (with the three answers) and every reopen (with the
reason), who did it and when; its admin is read-only. The nightly sync of paper orders is not an edit: it copies
the broker's facts, and its writes go through `save()` without `clean()`. Row 107.

**Decision 6: a plan version is a row.** A change writes a new `MethodPlan` that points at the old one through
`previous`, with one more in `version` and the reason in `change_reason`; the old row gets `ended_on`, the day
before the new one starts, and stays. A change starts on the first day of next month, or of this month while
this month's window is open and nothing is logged in it. The method is not changed here; a different method is
a new plan. Ending a plan sets `ended_on` to today and `end_reason`. `version_spans` turns the chain into the
days each version judges, the engine runs chapter 03's review once per span with that span's numbers, and the
practice budget counts from the first version's start. A paper Confirm uses the version in force on the day.
Row 108.

**Decision 7: Place again, with a new id.** Chapter 11 kept a month whose order ended unfilled from being placed
again. Now the next attempt is staged with the same id plus `-r2` (then `-r3`), and the button reads "Place
again". The attempt number comes from the rows, so two clicks compute the same id and the unique column keeps
it to one order. Every other refusal still applies, the window first: the method has no catching up. Row 109.

**Decision 8: the logbook is its own page, and the export is the page.** `/accounts/<id>/logbook/` lists every
entry with every column, filtered by `?month=`, `?kind=` and `?tag=`; the export takes the same parameters. A line
a paper order wrote is not edited by hand (the sync keeps it in step with Alpaca), and the others are edited on
the logbook's edit page. To add a line you use the method page's log form, as before. Row 110.

**Decision 9: the CSV.** Eleven columns, in this order: `date` (YYYY-MM-DD), `kind` (buy, sell, hold or skip),
`symbol`, `amount` and `shares` (plain decimals, empty when there is none), `state`, `tags` (space-separated),
`reason`, `note`, `source` (`hand` or `alpaca-paper:<client_order_id>`), `month_closed` (yes or no). UTF-8, a
header row, Python's default dialect: lines end with `\r\n` and a field is quoted only when it holds a comma, a
quote or a line break (Python Software Foundation, n.d.). A reason or a note that starts with a character a
spreadsheet reads as a formula is written with a leading apostrophe (OWASP Foundation, n.d.). The response is an
attachment named `logbook-account-<id>.csv` with `Cache-Control: no-store`. Row 110.

## Steps

### 12.1 The tests

Listing 12-1, Filename: `tests/test_ch12.py`:

{{file:tests/test_ch12.py}}

Things to notice:

- **The old tests are the first test.** Nothing in `test_ch10.py` or `test_ch11.py` changes. A form posted
  without a kind, as chapter 10's is, is a trade; chapter 10's `hold` is still refused as an action.
- **Real months, past and fixed.** The plan starts on January 1, 2026, so January to March are always in the
  past and their windows closed. Where a test needs "today", it passes a date to the function (`open_due_reviews`,
  `PlanChangeForm`) instead of reading the clock.
- **Chapter 11's fake is imported, not copied.** `FakeAlpaca`, the keys and the pinned day come from
  `tests/test_ch11.py`; the `fake` fixture is the same three lines.
- **Place again counts what Alpaca received.** Two clicks after an unfilled order make exactly one more POST,
  with the `-r2` id, and never a third.
- **The CSV is read back with `csv.reader`,** so the test checks the columns and the quoting the way a
  spreadsheet would see them, and a note that starts with a minus comes back with its apostrophe.

Run the tests:

Listing 12-2, Terminal:

```sh
uv run pytest tests/test_ch12.py
```

```text
tests/test_ch12.py:27: in <module>
    from invest_witus_site.methods.forms import PlanChangeForm, first_of_next_month
E   ImportError: cannot import name 'PlanChangeForm' from 'invest_witus_site.methods.forms' (.../src/invest_witus_site/methods/forms.py)
=========================== short test summary info ============================
ERROR tests/test_ch12.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.90s ===============================
```

Red at import. No package is added this chapter.

### 12.2 The rows

Listing 12-3, Filename: `src/invest_witus_site/methods/models.py`:

{{file:src/invest_witus_site/methods/models.py}}

Things to notice:

- **Every new column on an old table has `db_default` as well as `default`.** Django's `default` is applied in
  Python when the ORM makes a row. `db_default` is "set at the database level and will be used when inserting
  rows outside of the ORM or when adding a new field in a migration" (Django Software Foundation, n.d.-b). Chapter
  11's `default=""` alone made the migration fill the old rows and then drop the database default, so the
  previous release, still serving while the migration workflow ran, would have failed to insert a row. With
  both, `default` still "take[s] precedence when creating instances in Python code" (Django Software Foundation,
  n.d.-b), so `entry.reason` is a string before the first save.
- **`amount` became nullable.** A skip moves no money. Dropping a `NOT NULL` is additive too: the old code always
  wrote an amount.
- **`clean()` holds the rules between fields,** and returns a dictionary keyed by field, so each message lands
  beside its box. `save()` refuses a hold or a skip with no reason as well, whatever path wrote it.
- **`refuse_closed_month()` checks two dates** on an edit: the one the line has now and the one it had, so a
  line cannot be moved into a closed month, or out of one.
- **`TextField(max_length=...)` limits the form, not the database** (Django Software Foundation, n.d.-b). That is
  enough here: every reason arrives through a form.
- **`account_id: int | None` is a declaration only,** so pyright can read the column Django adds for the foreign
  key.
- **`version_spans` is a pure function** of the chain. A version replaced before it started has no days and is
  left out, which is how a scheduled change that is changed again disappears from the review but stays in the
  table.

The paper order gains its attempt number, and the order id its suffix:

Listing 12-4, Filename: `src/invest_witus_site/paper/models.py`:

{{file:src/invest_witus_site/paper/models.py}}

Attempt 1 keeps chapter 11's id with no suffix, so every order already placed keeps the id Alpaca knows it by.
With both models changed, make the two migrations, then let ruff tidy them:

Listing 12-5, Terminal:

```sh
uv run --env-file .env python manage.py makemigrations methods --name journal_kinds_plan_versions_and_reviews
uv run --env-file .env python manage.py makemigrations paper --name paperorder_attempt
uv run ruff format src/invest_witus_site/*/migrations/
uv run ruff check --fix src/invest_witus_site/*/migrations/
```

```text
Migrations for 'methods':
  src/invest_witus_site/methods/migrations/0003_journal_kinds_plan_versions_and_reviews.py
    + Add field kind to journalentry
    + Add field reason to journalentry
    + Add field state to journalentry
    + Add field tags to journalentry
    + Add field change_reason to methodplan
    + Add field end_reason to methodplan
    + Add field ended_on to methodplan
    + Add field previous to methodplan
    + Add field version to methodplan
    ~ Alter field action on journalentry
    ~ Alter field amount on journalentry
    ~ Alter field date on journalentry
    ~ Alter field symbol on journalentry
    + Create model MonthlyReview
    + Create model ReviewEvent
    + Create constraint one_review_per_plan_month on model monthlyreview
Migrations for 'paper':
  src/invest_witus_site/paper/migrations/0002_paperorder_attempt.py
    ~ Change Meta options on paperorder
    + Add field attempt to paperorder
```

Listing 12-6, Filename: `src/invest_witus_site/methods/migrations/0003_journal_kinds_plan_versions_and_reviews.py`:

{{file:src/invest_witus_site/methods/migrations/0003_journal_kinds_plan_versions_and_reviews.py}}

The four `Alter field` lines change no data: `action`, `symbol` and `date` changed only their `blank` flag or help
text, which Django records in the migration and the database ignores; `amount` drops its `NOT NULL`.

Listing 12-7, Filename: `src/invest_witus_site/paper/migrations/0002_paperorder_attempt.py`:

{{file:src/invest_witus_site/paper/migrations/0002_paperorder_attempt.py}}

### 12.3 The engine

Listing 12-8, Filename: `src/invest_witus_site/methods/engine.py`:

{{file:src/invest_witus_site/methods/engine.py}}

Things to notice:

- **`review()` is still called as chapter 03 called it,** once per span, with that version's `Plan` and the
  trades only. The loop joins the findings and the months.
- **`explain` uses `dataclasses.replace`.** A `FindingLine` is frozen; the explained one is a new value with the
  reason filled in.
- **New fields have defaults** (`explanation`, `version`, `skip_reason`, `spans`), so chapter 10's tests, which
  build and read these values, still pass.
- **The next action checks the version once more.** While a change is scheduled for next month, this month
  belongs to the old version, and next month's window to the new one.

### 12.4 The monthly review

Listing 12-9, Filename: `src/invest_witus_site/methods/reviews.py`:

{{file:src/invest_witus_site/methods/reviews.py}}

`open_due_reviews` reads the rows that exist once and writes the missing ones in one `bulk_create` with
`ignore_conflicts=True`, so two pages drawn at once cannot make the same month twice; the unique constraint has
the last word. `close_review` and `reopen_review` change the row and add the event in one transaction, so there is
never a closed month without its record.

### 12.5 The forms

Listing 12-10, Filename: `src/invest_witus_site/methods/forms.py`:

{{file:src/invest_witus_site/methods/forms.py}}

- **The log form's `kind` is not required,** and `clean_kind` turns nothing into `trade`. That keeps chapter 10's
  form, and any script that posts it, working.
- **`PlanChangeForm.apply` saves the old row first,** inactive, then creates the new one, inside one transaction:
  the partial unique constraint from chapter 10 allows one active plan per account, and never sees two.
- **`first_of_next_month`** adds four days to the 28th, which is always in the next month, then goes to its first
  day. No calendar arithmetic to get wrong.

### 12.6 The views and the routes

Listing 12-11, Filename: `src/invest_witus_site/methods/views.py`:

{{file:src/invest_witus_site/methods/views.py}}

The method page opens the due reviews against today, never against `?through=`, so a page drawn for an old date
does not open a month early or late. The log view passes `instance=JournalEntry(account=account)`, so the model's
`clean()` knows the account when it checks for a closed month.

Listing 12-12, Filename: `src/invest_witus_site/methods/urls.py`:

{{file:src/invest_witus_site/methods/urls.py}}

`re_path` with `\d{4}-\d{2}` makes `/review/2026-1/` a 404 before any view runs.

The logbook lives beside the method page, not inside it, because it outlives a plan:

Listing 12-13, Filename: `src/invest_witus_site/methods/logbook.py`:

{{file:src/invest_witus_site/methods/logbook.py}}

Listing 12-14, Filename: `src/invest_witus_site/methods/logbook_urls.py`:

{{file:src/invest_witus_site/methods/logbook_urls.py}}

Listing 12-15, Filename: `src/invest_witus_site/urls.py`:

{{file:src/invest_witus_site/urls.py}}

- **The filters never raise.** A month that is not `YYYY-MM`, a kind not in the list or a tag outside the tag
  rule is dropped, and the list widens.
- **`csv.writer` writes straight into the response,** which is file-like. The apostrophe guard runs on the two
  columns you type freely; OWASP notes that Excel may still evaluate a guarded cell after the file is saved and
  opened again (OWASP Foundation, n.d.), so treat an exported journal as data, not as a sheet to edit and keep.
- **`no-store`** asks every cache to keep no copy of a personal journal.

### 12.7 Place again

Listing 12-16, Filename: `src/invest_witus_site/paper/orders.py`:

{{file:src/invest_witus_site/paper/orders.py}}

`staged()` is the new piece: the newest attempt's row for the symbol, or, when that attempt ended with nothing
filled, a new attempt with the `-r` id and the old row in `previous`. `confirm` and `paper_section` take the
version in force on the day, and `practice_spent` counts from the chain's start.

Listing 12-17, Filename: `src/invest_witus_site/paper/templates/paper/_month_buys.html`:

{{file:src/invest_witus_site/paper/templates/paper/_month_buys.html}}

### 12.8 The pages

The method page gains one line under the switch, the same in every view:

Listing 12-18, Filename: `src/invest_witus_site/methods/templates/methods/method_page.html`:

{{file:src/invest_witus_site/methods/templates/methods/method_page.html}}

View A offers "Close last month", and shows the versions under the plan:

Listing 12-19, Filename: `src/invest_witus_site/methods/templates/methods/_view_a.html`:

{{file:src/invest_witus_site/methods/templates/methods/_view_a.html}}

View B lists every month's review state. It is a list, not a fifth table: chapter 10's test reads view B's four
tables by position.

Listing 12-20, Filename: `src/invest_witus_site/methods/templates/methods/_view_b.html`:

{{file:src/invest_witus_site/methods/templates/methods/_view_b.html}}

Listing 12-21, Filename: `src/invest_witus_site/methods/templates/methods/_view_c.html`:

{{file:src/invest_witus_site/methods/templates/methods/_view_c.html}}

The shared pieces: the journal table (the word for each kind, and the reason, state and tags in the note
column), the findings (with a skip's reason), and the log form's closing line.

Listing 12-22, Filename: `src/invest_witus_site/methods/templates/methods/_entries.html`:

{{file:src/invest_witus_site/methods/templates/methods/_entries.html}}

Listing 12-23, Filename: `src/invest_witus_site/methods/templates/methods/_findings.html`:

{{file:src/invest_witus_site/methods/templates/methods/_findings.html}}

Listing 12-24, Filename: `src/invest_witus_site/methods/templates/methods/_log_form.html`:

{{file:src/invest_witus_site/methods/templates/methods/_log_form.html}}

Four new partials:

Listing 12-25, Filename: `src/invest_witus_site/methods/templates/methods/_close_month.html`:

{{file:src/invest_witus_site/methods/templates/methods/_close_month.html}}

Listing 12-26, Filename: `src/invest_witus_site/methods/templates/methods/_reviews.html`:

{{file:src/invest_witus_site/methods/templates/methods/_reviews.html}}

Listing 12-27, Filename: `src/invest_witus_site/methods/templates/methods/_versions.html`:

{{file:src/invest_witus_site/methods/templates/methods/_versions.html}}

Listing 12-28, Filename: `src/invest_witus_site/methods/templates/methods/_form_fields.html`:

{{file:src/invest_witus_site/methods/templates/methods/_form_fields.html}}

`field.use_fieldset` is Django's flag for a widget that is a group, such as radio buttons; the group gets a
`<fieldset>` and a `<legend>`, so a screen reader names it (Django Software Foundation, n.d.-a).

And four new pages:

Listing 12-29, Filename: `src/invest_witus_site/methods/templates/methods/plan_change.html`:

{{file:src/invest_witus_site/methods/templates/methods/plan_change.html}}

Listing 12-30, Filename: `src/invest_witus_site/methods/templates/methods/review_month.html`:

{{file:src/invest_witus_site/methods/templates/methods/review_month.html}}

Listing 12-31, Filename: `src/invest_witus_site/methods/templates/methods/logbook.html`:

{{file:src/invest_witus_site/methods/templates/methods/logbook.html}}

Listing 12-32, Filename: `src/invest_witus_site/methods/templates/methods/entry_edit.html`:

{{file:src/invest_witus_site/methods/templates/methods/entry_edit.html}}

The stylesheet gains nine rules at the end, for text boxes, radio buttons, the filter row, the fieldset and the
three lists:

Listing 12-33, Filename: `src/invest_witus_site/pages/static/pages/site.css`:

{{file:src/invest_witus_site/pages/static/pages/site.css}}

### 12.9 The admin

Listing 12-34, Filename: `src/invest_witus_site/methods/admin.py`:

{{file:src/invest_witus_site/methods/admin.py}}

The plan's history columns are read-only, a closed month's line has no Delete, and the reviews have no Add, no
change and no Delete; their events show inline, read-only.

### 12.10 Green, and three months closed on your laptop

Listing 12-35, Terminal:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

```text
395 passed in 12.29s
All checks passed!
174 files already formatted
0 errors, 0 warnings, 0 informations
```

Twenty-nine new tests. Migrate the laptop database:

Listing 12-36, Terminal:

```sh
uv run --env-file .env python manage.py migrate
```

```text
Operations to perform:
  Apply all migrations: accounts, admin, auth, contenttypes, holdings, methods, pages, paper, prices, sessions, watchlist
Running migrations:
  Applying methods.0003_journal_kinds_plan_versions_and_reviews... OK
  Applying paper.0002_paperorder_attempt... OK
```

Your journal from chapters 10 and 11 has a buy on January 2 and a late buy on February 12, and March has nothing.
Log a skip for March, first without its reason, then with it, and read view B through March 31:

Listing 12-37, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -v 0 -c "
import re
from django.contrib.auth.models import User
from django.test import Client
from invest_witus_site.holdings.models import Account
from tests.test_ch10 import tables_in, text
u = User.objects.get(is_superuser=True); a = Account.objects.get(owner=u, name='Practice'); c = Client(); c.force_login(u)
skip = {'date': '2026-03-04', 'kind': 'skip', 'reason': 'Practice month: I read the lesson again instead.', 'state': 'unsure', 'tags': 'practice'}
for row in ({**skip, 'reason': ''}, skip):
    page = text(c.post(f'/accounts/{a.pk}/method/log/', row, follow=True))
    print(re.findall(r'class=\"message \w+\">([^<]+)<', page) or re.findall(r'class=\"errorlist\"[^>]*><li>([^<]+)<', page))
checks, months, *rest = tables_in(text(c.get(f'/accounts/{a.pk}/method/?view=b&through=2026-03-31')))
for row in checks[:2] + months: print(row)
"
```

```text
['A skip needs a reason: write why, in a sentence.']
['Logged: 2026-03-04 skip.']
('Rule', 'Status', 'Evidence', 'Lesson')
('Buy once in every month of the plan.', 'explained', '1 finding: 2026-03 (1 explained)', 'lesson coming')
('Month', 'Window closes', 'Status', 'Buys', 'Amount', 'Shares', 'Rules flagged')
('2026-01', '2026-01-07', 'done', '1', '100.00', '0.50', 'none')
('2026-02', '2026-02-07', 'done', '1', '100.00', 'not recorded', 'buy-in-window')
('2026-03', '2026-03-07', 'skipped', '0', '0.00', '', 'one-buy-each-month')
```

March is still flagged under its rule, and the rule reads "explained". Now close the three months with the
answer the page drafts for "What the rules said", try to log a buy into closed March, and reopen it:

Listing 12-38, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -v 0 -c "
import re
from django.contrib.auth.models import User
from django.test import Client
from invest_witus_site.holdings.models import Account
from tests.test_ch10 import text
u = User.objects.get(is_superuser=True); a = Account.objects.get(owner=u, name='Practice'); c = Client(); c.force_login(u)
said = lambda page: re.findall(r'class=\"message \w+\">([^<]+)<', page) or re.findall(r'class=\"errorlist[^\"]*\"[^>]*><li>([^<]+)<', page)
did = {'2026-01': 'Bought on day 2.', '2026-02': 'Bought on day 12, late.', '2026-03': 'Skipped, and wrote why.'}
for month, done in did.items():
    draft = re.search(r'name=\"rules_said\"[^>]*>\s*([^<]*)<', text(c.get(f'/accounts/{a.pk}/method/review/{month}/'))).group(1).strip()
    answers = {'did': done, 'rules_said': draft, 'next_month': 'Buy in the first week.'}
    print(month, '|', draft, '|', said(text(c.post(f'/accounts/{a.pk}/method/review/{month}/close/', answers, follow=True))))
late = {'date': '2026-03-20', 'action': 'buy', 'symbol': 'INDEX', 'amount': '100'}
print(said(text(c.post(f'/accounts/{a.pk}/method/log/', late, follow=True))))
print(said(text(c.post(f'/accounts/{a.pk}/method/review/2026-03/reopen/', {'reason': ''}, follow=True))))
print(said(text(c.post(f'/accounts/{a.pk}/method/review/2026-03/reopen/', {'reason': 'The skip was logged on the wrong day.'}, follow=True))))
history = text(c.get(f'/accounts/{a.pk}/method/review/2026-03/')).split('<ol class=\"events\">')[1].split('</ol>')[0]
for item in history.split('<li>')[1:]: print(' '.join(re.sub(r'<[^>]+>', ' ', item).split()))
"
```

```text
2026-01 | Every rule passed this month. | ['Closed 2026-01. Its entries are read-only now.']
2026-02 | Bought on day 12; the window is days 1 to 7. | ['Closed 2026-02. Its entries are read-only now.']
2026-03 | No buy in 2026-03. (skipped: Practice month: I read the lesson again instead.) | ['Closed 2026-03. Its entries are read-only now.']
['2026-03 is closed. Reopen its review, with a reason, to change it.']
['This field is required.']
['Reopened 2026-03. Its entries can change again.']
2026-10-29 16:08: Closed by owner. What I did: Skipped, and wrote why. What the rules said: No buy in 2026-03. (skipped: Practice month: I read the lesson again instead.) What I'll do next month: Buy in the first week.
2026-10-29 16:08: Reopened by owner. The skip was logged on the wrong day.
```

Your times are the time you ran it, in UTC, and the name is your superuser's. Last, the export:

Listing 12-39, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -v 0 -c "
from django.contrib.auth.models import User
from django.test import Client
from invest_witus_site.holdings.models import Account
u = User.objects.get(is_superuser=True); a = Account.objects.get(owner=u, name='Practice'); c = Client(); c.force_login(u)
response = c.get(f'/accounts/{a.pk}/logbook/export.csv')
print(response['Content-Disposition'])
print(response.content.decode(), end='')
"
```

```text
attachment; filename="logbook-account-1.csv"
date,kind,symbol,amount,shares,state,tags,reason,note,source,month_closed
2026-01-02,buy,INDEX,100.00,0.500000,,,,first buy,hand,yes
2026-02-12,buy,INDEX,100.00,,,,,,hand,yes
2026-03-04,skip,,,,unsure,practice,Practice month: I read the lesson again instead.,,hand,no
2026-11-03,buy,INDEX,100.00,0.496277,,,,"Alpaca paper order order-1: filled, 0.496277 shares at 201.5 on 2026-11-04",alpaca-paper:iw-1-1-2026-11-INDEX,no
```

March reads `no` because you reopened it. The November note is quoted because it holds a comma. In a browser,
the same file is **Download these as CSV** on the logbook page, which you reach from **Open the logbook** under
the view switch.

To try a change of plan, open **Change or end this plan** under the view switch, pick **Change the numbers**, set
the amount, leave **Starting** on next month, write why, and save. View A then lists both versions with their
dates and your reason. Put the plan back the same way if you do not mean to keep it; each change is a version.

### 12.11 What the owner does outside the editor

The reference app's steps are task 17 in the owner's queue. A learner with a Vercel project of their own does
the same:

1. **Merge the chapter.** The push to `main` runs the migrate workflow described in `docs/05-operations.md`.
   Every new column has a database default, so the release before this one keeps working while it runs.
2. **Check the run.** GitHub, the repository, **Actions**, **Migrate production database**: the run for the merge
   must be green, and its summary lists `methods.0003` and `paper.0002`.
3. **Close your first month.** On the method page, view A shows **Close last month**. If a month had no buy, log
   a skip that says why before you close it.

## Checkpoint

- `uv run pytest` prints `395 passed`; ruff and pyright pass.
- Listing 12-37 refuses the skip without a reason, logs it with one, and prints March as `skipped` and the rule
  as `explained`.
- Listing 12-38 closes three months, refuses a buy dated in closed March, refuses a reopen without a reason, and
  prints the close and the reopen in the history.
- Listing 12-39 prints the eleven columns and one line per entry.
- Signed out, every public page has no `<table`, no link to `/accounts/` or `/logbook/`, and no "Close last
  month"; signed in as anyone but the owner, every new route is a 404.
- Commit and push: `git add -A && git commit -m "Chapter 12: the journal and closing the month"`.

## Exercises

1. **The rule-following rate as a number.** View B prints "N followed every rule". Add the share of due months
   followed, computed from the month rows, to view B and the logbook, and a test that reproduces it from journal
   rows (PRD 7.6's acceptance line). Decide whether an explained skip counts as followed, and write the reason
   in the decisions log.
2. **A tag table.** Move tags into a `Tag` model per owner with a group (mental state or mistake), and add rename
   and merge in the owner's pages. Keep the CSV's `tags` column the same.
3. **Soft delete.** PRD 7.6 asks for deleting an entry "with a reason". Add a `deleted_reason` column, a Delete
   button on the edit page that requires it, hide deleted lines from the review and the logbook by default, and
   list them behind a filter.
4. **An event on close.** Write the closed review as a JSON event in an `OutboundEvent` table with a
   deterministic id (`review-<plan>-<month>-<close number>`), ready for chapter 15 to send.

## If you get stuck

- Browse: https://github.com/dapperAuteur/invest-witus/tree/v12
- Diff for this chapter: https://github.com/dapperAuteur/invest-witus/compare/v11...v12
- Zip: https://github.com/dapperAuteur/invest-witus/archive/v12.zip
- Take the reference's files. Chapter 12 changed `src/invest_witus_site/urls.py`, `methods/models.py`,
  `methods/engine.py`, `methods/forms.py`, `methods/views.py`, `methods/urls.py`, `methods/admin.py`, the method
  templates `method_page.html`, `_view_a.html`, `_view_b.html`, `_view_c.html`, `_entries.html`, `_findings.html`
  and `_log_form.html`, `paper/models.py`, `paper/orders.py`, the template `paper/_month_buys.html` and
  `pages/static/pages/site.css` and `docs/site/privacy.md` (the journal's new fields and the CSV download), and
  added `methods/reviews.py`, `methods/logbook.py`, `methods/logbook_urls.py`,
  the templates `_close_month.html`, `_reviews.html`, `_versions.html`, `_form_fields.html`, `plan_change.html`,
  `review_month.html`, `logbook.html` and `entry_edit.html`,
  `methods/migrations/0003_journal_kinds_plan_versions_and_reviews.py`,
  `paper/migrations/0002_paperorder_attempt.py` and `tests/test_ch12.py`. No package changed, no environment
  variable was added, nothing moved:
  `git fetch reference --tags && git checkout v12 -- src tests docs/site/privacy.md`.
- `test_an_entry_refuses_a_float_a_bad_symbol_a_zero_amount_and_an_unknown_action` (chapter 10) passes `hold`
  and expects it refused: you added `hold` to the action's choices instead of a `kind` column.
- `test_the_owner_logs_an_entry_from_the_form` (chapter 10) answers "This field is required." for the kind: the
  form's `kind` field is required. Set `required = False` in `__init__` and default it in `clean_kind`.
- `test_view_b_tables_every_month_with_amounts_and_shares` (chapter 10) fails to unpack: view B has a fifth table.
  The month reviews are a list.
- `test_a_two_symbol_plan_shows_the_split_without_a_confirm_button` (chapter 11) finds "Confirm": a new sentence
  on the method page uses the word.
- A form for a closed month saves anyway: the view built the form without `instance=JournalEntry(account=account)`,
  so `clean()` had no account to check.
- `test_closing_needs_three_answers_and_no_unexplained_miss` gets a 404 for the review page: `review_or_404` does
  not call `open_due_reviews` before it looks.
- `test_a_change_is_a_new_version_and_each_month_is_judged_by_its_own` raises `IntegrityError` on
  `one_active_plan_per_account`: `apply` creates the new row before it saves the old one inactive.
- `test_place_again_is_a_new_id_once_after_an_order_ended_unfilled` sends a third order: `staged` takes the first
  attempt instead of the newest, so it keeps seeing the unfilled one.
- `test_the_csv_export_has_the_documented_columns` finds `=SUM(1)` without its apostrophe: the guard runs on
  `note` only, or `cell` checks `text[0] == "="` and misses the others.
- `ruff check` reports `E501` in a migration: run the format step of Listing 12-5 before the check.
- On Vercel after the merge, a page answers 500 with `no such column: kind` or `relation
  "methods_monthlyreview" does not exist` for about a minute: the migrate workflow is still running. Longer than
  that, open GitHub Actions and read the run.

## What we learned

- A migration is additive only when the old code can still write rows: a new `NOT NULL` column needs a database
  default, not just a Python one.
- Rules between fields belong in the model's `clean()`, where every form and the admin run them, and a rule that
  depends on state (a closed month) can sit there too.
- History is cheapest as rows that point back: a changed plan is a new version, and the old one keeps judging
  its own months.
- An audit trail is a table nobody can edit, written in the same transaction as the change it records.
- An explanation is not an excuse. The miss stays a finding; the reason sits beside it, and the person reading
  the review decides.
- An export is part of the product: documented columns, a predictable format, and a guard for the program that
  will open it.

## Next

Chapter 13 is the in-app reporter: a bug, a feature request or a question, stored in the app and mirrored to
WitUS Inbox with a signed request, retried by the daily job.

## References

Django Software Foundation. (n.d.-a). *Working with forms*. Django 5.2 documentation. Retrieved October 29, 2026,
from https://docs.djangoproject.com/en/5.2/topics/forms/

Django Software Foundation. (n.d.-b). *Model field reference*. Django 5.2 documentation. Retrieved October 29,
2026, from https://docs.djangoproject.com/en/5.2/ref/models/fields/

OWASP Foundation. (n.d.). *CSV injection*. Retrieved October 29, 2026, from
https://community.owasp.org/attacks/CSV_Injection

Python Software Foundation. (n.d.). *csv: CSV file reading and writing*. Python documentation. Retrieved October
29, 2026, from https://docs.python.org/3/library/csv.html
