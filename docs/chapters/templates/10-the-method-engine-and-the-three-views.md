# Chapter 10: The method engine and the three views

**Starts from:** tag `v09`. **Ends at:** tag `v10`.
**Written against:** Python 3.14.10, uv 0.13.6, Django 5.2.18, and the Django 5.2 documentation pages as read on
October 28, 2026.
**Goal:** the product's core on the web. The signed-in owner picks a method the package ships, writes down the
plan's numbers for one account, logs what they bought, and reads chapter 03's review of the journal against the
method's rules, with every rule and every finding linking the lesson that explains it, or saying "lesson coming"
when the rules file has no link yet. The same plan, rules, review and journal render three ways, A, B and C, as
the research named them, through one switch the session remembers. Another owner's account is a 404 for every
view and every action; no public page shows a rule, a table or a link to the page; nothing on the page is a
price.
**Time:** 4 to 5 hours for the code and tests. The owner's step (the migration and the first method on the live
site) takes 15 minutes.

The listings in this chapter are not typed in by hand. `scripts/render_chapter.py` pastes the real files from
tag `v10` into the chapter text, so what you read and what the tests run are the same bytes.

## What you will learn

- **A row that is a value:** two models whose only job is to round-trip to chapter 03's `Plan` and `Entry`, so
  the review written for the command line runs on the web without a line changed.
- **Rules read from the package, not copied into rows:** the plan stores the method's id, and `load_method`
  reads the TOML file at request time, so a lesson link added to the file reaches every page at once and a
  rule with no link reads "lesson coming" because the file says so.
- **A partial unique constraint:** `UniqueConstraint` with a `condition`, which lets one account keep an ended
  plan as history while the database refuses a second active one.
- **A `ModelForm`:** the journal's add form built from the model, with the model's validators running as part
  of the form's own validation.
- **A context built once and rendered three ways:** a service module that arranges the review (per rule, per
  month, the next action), and `{% include %}` with a template name that is a variable.
- **The session as a per-visitor memory:** `request.session` holding the view the person chose, and why that
  choice ends with the sign-out.
- **A `Protocol` in a test,** the smallest type that says "this has `content`".

## Before the code: what the PRD and the research ask, and seven decisions

**What the PRD asks.** Section 7.1: a method is a rule block, each rule with text and a `lesson` field that is
the lesson's URL or empty, shown as "lesson coming"; the user's plan is separate, the method plus their own
numbers; every evaluation shows each rule's status as text, the evidence, and the lesson link; the app never
proposes a security outside the user's plan. Section 7.2: three views over the same data, all built, with a
toggle that is keyboard operable and announces the current view; A as the everyday home, C to start a method,
B behind an "Operator" label; every table captioned with header `scope`; the environment printed as text on
every signed-in page. The research (`docs/research/01-ux-benchmarks-and-three-directions.md`, section 5) names
the three: A, "The Plan and the Logbook", a written plan with one next action and a logbook beside it; B,
"Method Console", a control room with rule checks, evidence and a lesson column; C, "The Lesson Lab", where the
lesson is the screen and the paper account is the lab. The mockup in `docs/research/mockups/` draws each one
with 12-1 momentum as its example; this chapter builds them with the method the package ships, and the mockup
is a guide for what each view puts first, not a contract for its layout.

**Decision 1: a `methods` app beside the library's `methods` package, and the rules stay in the file.** The
library has had the engine since chapter 03: `methods/index_dca.toml`, `rulebook.py`, `adherence/plan.py`,
`adherence/journal.py` and `adherence/review.py`. The web layer wraps them; it does not rewrite them. A
`MethodPlan` row holds the method's id and the person's numbers, never a rule, and `load_method(method_id)`
reads the TOML file whenever a page needs the rules, so a lesson URL added to the file tomorrow reaches every
plan at once and no row goes stale. One function joins the library, `available_methods()`, which lists the
rules files the package ships so the start form reads the list instead of hardcoding it; the no-move rule
holds, nothing from chapters 01 to 09 moved. The import graph stays a line: `methods.models` imports
`holdings.models` and chapter 09's symbol rule from `watchlist.models`; `holdings.views` imports
`methods.models` for one line on the account page; `methods.views` imports `holdings.models` for the ownership
query and nothing from `holdings.views`. Decisions log, row 86.

**Decision 2: the plan row mirrors chapter 03's `Plan`, with symbols as text and one active plan per
account.** `MethodPlan(account, method_id, amount, buy_window_days, symbols, started_on, active)`: the five
fields of the `Plan` value plus the account and a flag. `symbols` is a text column, the symbols separated by
spaces, each through chapter 09's rule on the way in, because the review wants a `frozenset` and a text column
becomes one in a single `split()`; a JSON column or a table of symbols would be more machinery for the same
five characters. A `UniqueConstraint` on the account with `condition=Q(active=True)` lets an ended plan stay as
history, `active` off, while the database refuses a second active one; the form says the same in words before
the database has to. Ending a plan is an admin step in this chapter. The PRD's plan versions with a dated note
are chapter 12's, with the change-of-plan reason the journal needs. Row 87.

**Decision 3: the journal row mirrors `Entry`, plus shares and a note.** `JournalEntry(account, date, action,
symbol, amount, shares, note)`. The action's choices are built from chapter 03's `Action` enum, so a value the
review does not know cannot be stored and the two cannot drift. Shares are optional: a confirmation shows them,
a statement shows them later, and a person logging from memory may not have them; a month whose buys lack them
prints "not recorded" instead of a partial total. This is the minimum the review needs. Chapter 12 builds the
logbook on this table: automatic entries, tags, skips and exceptions with reasons, the rule-following rate, the
export. Row 88.

**Decision 4: `review()` runs unchanged; the engine module arranges.** Two converters, `to_plan()` and
`to_entry()`, and one call, the same as `run_review` made in chapter 03. Everything else in
`methods/engine.py` is arrangement of what comes back: each rule as a line with its lesson URL or `None`,
which the template prints as "lesson coming"; each rule as a check with its status in words and its evidence
in words, "1 finding: 2026-02"; each month of the plan as a row that is done, missed or open, with the buys,
the amount and the shares; and the next action, the next buy window, due now or upcoming. The page reviews
through today unless `?through=YYYY-MM-DD` says otherwise, as chapter 03's `--through` did, and says which day
it reviewed through. Row 89.

**Decision 5: three templates, one context, a switch of plain links remembered in the session.** The page
builds its context once and renders it through `methods/_view_a.html`, `_view_b.html` or `_view_c.html`,
picked by `?view=a|b|c`; the view handling the request writes the choice into `request.session`, and the
next request without `?view=` reads it back. With no choice made, the page opens on A when a method runs and
on C when none does, which is PRD 7.2's "starting a new method opens C; the everyday home is A". The switch is
three links with `aria-current="page"` on the current one, which a screen reader announces, and no script. The
PRD asked for the choice to be saved per user and restored at the next sign-in; the session is what this
chapter has, and `logout()` flushes it, so the choice lasts a sign-in; a preference column on the person is
exercise 1. The PRD also put the toggle in the header; it lives on the method page because the page is per
account. Row 90.

**Decision 6: what each view leaves out, on purpose.** The three views show the same plan, rules, findings,
months and journal; none shows a figure the others hide. B is read-only tables and the same log form the
others carry: no order queue, no envelope chart, no promotion checklist, because there is no broker until
chapter 11 and this method has no backtest range to draw. A's next action is a sentence and the log form is
its "Confirm"; a "Skip" that asks why is a journal entry with a reason, chapter 12's. C's rules do not switch
on one at a time: the package ships one method whose five rules come from one lesson set, and until the
course content exists the plan names the method and all five rules are on. Row 91.

**Decision 7: no price on the method page.** Adherence is about what you did, not what it is worth. The
account page (chapter 08) values the statement; the method page shows amounts and shares from the journal and
nothing from the prices table, so a test can plant a close and assert that no view prints it. The research's
"performance, deliberately small" at the bottom of A waits for the paper account in chapter 11, where a value
has a source the page can name. Row 92.

## Steps

### 10.1 The tests

Listing 10-1, Filename: `tests/test_ch10.py`:

{{file:tests/test_ch10.py}}

Things to notice:

- **Placeholder symbols only.** `INDEX` and `OTHER` from chapter 02 and one bad token. Never a real symbol, in
  a test or anywhere in the repository.
- **The `plan` and `journal` fixtures are the chapter's worked example.** A plan from January 1, 2026, 100.00
  into `INDEX` within the first seven days; a January buy on day 2 with the shares recorded; a February buy on
  day 12, outside the window. Reviewed through February 28 that is one finding, `buy-in-window`; reviewed
  through January 31 it is none. Most page tests pass `?through=` so they do not depend on the day they run.
- **The form test starts next month.** With `started_on` on the first of next month, no month is due yet
  whatever today's date, so the page reads "You are on plan" and names the coming window. A test that started
  the plan today would read differently on the 3rd and the 20th.
- **`text()` undoes Django's escaping.** The page prints a rule's apostrophe as `&#x27;` and a `&` in a link as
  `&amp;`; the helper runs the page through `html.unescape` so a test can compare the words the person reads.
  The table reader does the same on its own, through `HTMLParser`.
- **`Page` is a `Protocol`.** The test client's response is its own class in the type stubs, not
  `HttpResponse`; the helper asks for the one attribute it reads, `content`, and pyright is satisfied by any
  object that has it.
- **The engine tests build unsaved rows.** `month_rows` reads `JournalEntry` instances for their shares, and
  an instance that is never saved needs no database and no account, so those tests carry no `django_db` mark.
- **The constraint test wraps the second insert in `transaction.atomic()`,** as chapter 09's did, and then
  ends the first plan and saves the second to prove the constraint is on active plans only.
- **The no-price test plants a close.** `DailyClose.upsert` stores `123.456789` for `INDEX`; each view must
  print the plan's `INDEX` and must not print `123.45`.
- **The three headings.** Each view has one `<h2>` the other two never print, "My plan", "Rule checks" and
  "The rules, and what to re-read"; the view test asserts the one and the absence of the other two.

Run the tests:

Listing 10-2, Terminal:

```sh
uv run pytest tests/test_ch10.py
```

```text
tests/test_ch10.py:24: in <module>
    from invest_witus.methods.rulebook import Method, Rule, available_methods, load_method
E   ImportError: cannot import name 'available_methods' from 'invest_witus.methods.rulebook'
=========================== short test summary info ============================
ERROR tests/test_ch10.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.79s ===============================
```

Red at import, and the first missing name is the library's. No package is added this chapter, and no
environment variable.

### 10.2 One function in the library

Listing 10-3, Filename: `src/invest_witus/methods/rulebook.py`:

{{file:src/invest_witus/methods/rulebook.py}}

`available_methods` is the only change to chapter 03's file: the package's `.toml` files, by id, each loaded
through the function that was already there. `files("invest_witus.methods")` is the package as a folder-like
object, and `iterdir()` lists what ships in it, so a second rules file is a second method with no code change.
The test asks for `["index-dca"]` today and reasserts chapter 03's rule, that the file's rule ids equal
`CHECKED_RULES`, because the web layer rests on it.

### 10.3 The app, its settings line and its URLs

Make the folder `src/invest_witus_site/methods/` with an empty `__init__.py`, an empty `migrations/__init__.py`,
and a `templates/methods/` folder for the page and its partials.

Listing 10-4, Filename: `src/invest_witus_site/methods/apps.py`:

{{file:src/invest_witus_site/methods/apps.py}}

Listing 10-5, Filename: `src/invest_witus_site/settings.py`:

{{file:src/invest_witus_site/settings.py}}

One line in `INSTALLED_APPS` and one word in the docstring. Everything else is as chapter 09 left it.

Listing 10-6, Filename: `src/invest_witus_site/urls.py`:

{{file:src/invest_witus_site/urls.py}}

Listing 10-7, Filename: `src/invest_witus_site/methods/urls.py`:

{{file:src/invest_witus_site/methods/urls.py}}

The include sits at `accounts/<int:pk>/method/`, beside chapter 09's `watch/`, and the `pk` captured there
reaches the page and both actions. Three names: `method-page`, `method-start`, `method-log`.

### 10.4 The two rows

Listing 10-8, Filename: `src/invest_witus_site/methods/models.py`:

{{file:src/invest_witus_site/methods/models.py}}

- **Every field of `MethodPlan` has a chapter 03 twin.** `to_plan()` is the row as the value, five fields in
  the same order the `Plan` dataclass names them, and the review never sees the row. `method()` is the rules,
  read from the package now.
- **Three validators, so the admin's form refuses with a message beside the box.** `validate_method_id` asks
  `load_method` and turns its `UnknownMethodError` into a `ValidationError`; `validate_symbol_list` runs
  chapter 09's `parse_symbols` and names each refused token; the field's `MinValueValidator` keeps an amount
  at a cent or more. `save()` runs the first two again, so no caller that skipped the form can store a plan for
  a method that has no rules or a symbol outside the rule, and it raises a `TypeError` for a float, as every
  money column in this app does.
- **The partial unique constraint.** The constraints reference describes `condition` as "A `Q` object that
  specifies the condition you want the constraint to enforce", with the example
  `UniqueConstraint(fields=["user"], condition=Q(status="DRAFT"), name="unique_draft_user")`, which "ensures
  that each user only has one draft" (Django Software Foundation, n.d.-a). Here the field is the account and
  the condition is `active=True`: one active plan, any number of ended ones. The `CheckConstraint` beside it
  keeps the buy window between 1 and 28 in the database as well as in the form, and "Constraints are checked
  during the model validation" (Django Software Foundation, n.d.-a), so `full_clean()` reports a window of 40
  the way it reports a bad symbol.
- **`ACTION_CHOICES` is built from the enum.** A list comprehension over chapter 03's `Action`, so the column
  accepts exactly `buy` and `sell` and `to_entry()`'s `Action(self.action)` can never fail on a stored value.
- **Shares are nullable.** `null=True, blank=True`, rounded down to six places with chapter 01's `to_shares`
  when present, and the page prints "not recorded" when absent.

Make the migration. The generated file imports the validators from two apps, and ruff wants the imports
grouped, so the fix command runs too:

Listing 10-9, Terminal:

```sh
uv run --env-file .env python manage.py makemigrations methods
uv run ruff format src/invest_witus_site/methods/migrations/
uv run ruff check --fix src/invest_witus_site/methods/migrations/
```

```text
Migrations for 'methods':
  src/invest_witus_site/methods/migrations/0001_initial.py
    + Create model JournalEntry
    + Create model MethodPlan
1 file reformatted, 1 file left unchanged
Found 1 error (1 fixed, 0 remaining).
```

Listing 10-10, Filename: `src/invest_witus_site/methods/migrations/0001_initial.py`:

{{file:src/invest_witus_site/methods/migrations/0001_initial.py}}

Both tables depend on the holdings app's first migration, because of the foreign keys, and the two
constraints are written into the migration as the model wrote them, condition included.

Listing 10-11, Filename: `src/invest_witus_site/methods/admin.py`:

{{file:src/invest_witus_site/methods/admin.py}}

The admin is where a plan is ended in this chapter: `active` is editable in the list. Everything else about a
plan and a journal happens on the owner's page.

### 10.5 The engine

Listing 10-12, Filename: `src/invest_witus_site/methods/engine.py`:

{{file:src/invest_witus_site/methods/engine.py}}

- **`build_review` is the whole page's context.** The row becomes the value, the rows become the values,
  `review` runs as chapter 03 wrote it, and the rest of the function arranges what it returned. Nothing here
  decides whether a rule was broken; chapter 03 did.
- **`rule_lines` resolves the lesson once.** `Method.lesson_for` returns the rule's lesson, else the method's,
  else the words `LESSON_COMING`; the line keeps a URL or `None`, and the template prints "lesson coming" for
  `None`. No template, no view and no test carries a lesson URL: the only place one can come from is the
  TOML file, which is the authoritative-values rule applied to lessons.
- **`RuleCheck.evidence` is a sentence.** PRD 7.1 asks for the fact that decided each check; for this method
  the fact is the count of findings and the months they fall in, "1 finding: 2026-02", or "no findings".
  Status is the word `pass` or `fail`, never a color.
- **`month_rows` adds the open month.** Chapter 03's `months_due` lists the months whose window has closed.
  The page also shows the month the review date falls in when its window is still open, marked `open`, so the
  operator sees this month's row before it can be missed. A month is `done` when it has a buy, whatever the
  review found about that buy; the "Rules flagged" column carries the findings.
- **`next_action` is one rule.** Before the start, the start month's window; in a month with no buy and the
  window open, that window, due now; otherwise the next month's window, because this month is done or its
  window has closed and the method has no catching up. The date it reasons from is the review date, so
  `?through=` moves the next action with the findings.

### 10.6 The forms

Listing 10-13, Filename: `src/invest_witus_site/methods/forms.py`:

{{file:src/invest_witus_site/methods/forms.py}}

- **The method is a `ChoiceField` whose choices are a function.** The fields reference allows "a callable
  that returns such an iterable" and says "If the argument is a callable, it is evaluated each time the
  field's form is initialized, in addition to during rendering" (Django Software Foundation, n.d.-b), so the
  form reads the package's list when it is built. A method id typed by hand, `get-rich-quick`, is "Select a
  valid choice."
- **The amount is a `DecimalField`,** which "Normalizes to: A Python `decimal`" (Django Software Foundation,
  n.d.-b): the form hands the model a `Decimal`, never a float, which is what `save()`'s guard is for.
- **`clean_symbols` returns the stored string,** the way chapter 09's returned a parsed value: the list
  validated by the model's own validator, then joined. A refused token is a form error naming it; a plan with
  a typo in its universe would flag every buy.
- **`clean()` refuses a second active plan in words,** before the constraint has to. The account comes in
  through `__init__`, not a field, so no request can name another account than the one in the URL.
- **`JournalEntryForm` is a `ModelForm`.** "If you're building a database-driven app, chances are you'll have
  forms that map closely to Django models", and then "it would be redundant to define the field types in your
  form, because you've already defined the fields in your model" (Django Software Foundation, n.d.-c). The
  fields, labels, help text, choices and validators are the model's; "`Model` validation (`Model.full_clean()`)
  is triggered from within the form validation step, right after the form's `clean()` method is called"
  (Django Software Foundation, n.d.-c), which is how `AB CD` and an amount of zero become messages beside their
  boxes. The two widgets are the only things the form adds.

### 10.7 The views and the switch

Listing 10-14, Filename: `src/invest_witus_site/methods/views.py`:

{{file:src/invest_witus_site/methods/views.py}}

- **`VIEWS` is the only place the three are named,** by letter, with the label the switch prints and the
  template the page includes. The research's names are the labels.
- **`chosen_view` reads the session.** "The session framework lets you store and retrieve arbitrary data on a
  per-site-visitor basis. It stores data on the server side and abstracts the sending and receiving of
  cookies" (Django Software Foundation, n.d.-d); with the middleware on since chapter 05, `request.session` is
  "a dictionary-like object" (Django Software Foundation, n.d.-d) and the view writes one key into it. The
  `isinstance` check before `in VIEWS` is for pyright: a session value is typed as anything. Sign-out ends it:
  `django.contrib.auth.logout()` "calls the `flush()` method of `request.session`" (Django Software Foundation,
  n.d.-d), so the next sign-in starts from the default again, which decision 5 wrote down.
- **`render_method_page` is the context builder the two actions call back into,** as chapter 09's
  `account_page` was. `force_view="c"` draws the start form again with its errors whichever view the session
  holds; a refused log entry comes back in the view the person was in.
- **`through_query` keeps the review date in the switch.** The three links carry `&through=` only when a date
  was given, so flipping views does not lose it.
- **`start_method` sets the view to A** after a plan is written, the everyday home, and `log_entry` leaves
  the view alone. Both are `login_required` then `require_POST`, in that order, for the reason chapter 09 gave.
- **The ownership query is chapter 08's,** `get_object_or_404(Account, pk=pk, owner=request.user)`, in all
  three views, so another owner's account is a 404 for the page and for both actions.

### 10.8 The templates: one page, three arrangements

Listing 10-15, Filename: `src/invest_witus_site/methods/templates/methods/method_page.html`:

{{file:src/invest_witus_site/methods/templates/methods/method_page.html}}

The page prints the environment as text under the heading, the band PRD 7.2 asks for, from the account's kind;
then the switch; then `{% include view_template %}`, where "The template name can either be a variable or a
hard-coded (quoted) string" and "An included template is rendered within the context of the template that
includes it" (Django Software Foundation, n.d.-e). One context, three templates.

Listing 10-16, Filename: `src/invest_witus_site/methods/templates/methods/_switch.html`:

{{file:src/invest_witus_site/methods/templates/methods/_switch.html}}

Three links in a `<nav aria-label="View">`; the current one has `aria-current="page"`, which the stylesheet
draws and a screen reader reads. A link is the right control: it is keyboard operable by nature, it needs no
script, and the choice is a GET with no side effect beyond a session key.

Listing 10-17, Filename: `src/invest_witus_site/methods/templates/methods/_rules.html`:

{{file:src/invest_witus_site/methods/templates/methods/_rules.html}}

Listing 10-18, Filename: `src/invest_witus_site/methods/templates/methods/_findings.html`:

{{file:src/invest_witus_site/methods/templates/methods/_findings.html}}

Listing 10-19, Filename: `src/invest_witus_site/methods/templates/methods/_entries.html`:

{{file:src/invest_witus_site/methods/templates/methods/_entries.html}}

Listing 10-20, Filename: `src/invest_witus_site/methods/templates/methods/_log_form.html`:

{{file:src/invest_witus_site/methods/templates/methods/_log_form.html}}

Listing 10-21, Filename: `src/invest_witus_site/methods/templates/methods/_start_form.html`:

{{file:src/invest_witus_site/methods/templates/methods/_start_form.html}}

Five partials the views share, so a rule, a finding, a journal row and the two forms are written once. The
rules list and the entries table are included "using keyword arguments" after `with` (Django Software
Foundation, n.d.-e), `rules=` for the list and `caption=` for the table. "No findings" is a sentence in
`_findings.html`, never an empty list; "lesson coming" is the words, never an empty link.

Listing 10-22, Filename: `src/invest_witus_site/methods/templates/methods/_view_a.html`:

{{file:src/invest_witus_site/methods/templates/methods/_view_a.html}}

A, the home: one next action in a card, the on-plan status with the findings as its fix list, the plan with its
rules and their lessons, the logbook with the form under it. The order is the research's: the one thing to do
next comes before everything else.

Listing 10-23, Filename: `src/invest_witus_site/methods/templates/methods/_view_b.html`:

{{file:src/invest_witus_site/methods/templates/methods/_view_b.html}}

B, the console: a status list, then four tables, rule checks with status, evidence and a lesson column, every
month of the plan with its window, its buys, the amount and the shares, the findings by day, and the journal.
Each table has a caption for screen readers, header `scope` on every heading cell, and right-aligned tabular
numbers through chapter 08's `.num` class.

Listing 10-24, Filename: `src/invest_witus_site/methods/templates/methods/_view_c.html`:

{{file:src/invest_witus_site/methods/templates/methods/_view_c.html}}

C, the lab: with no method running, each method the package ships, its summary, its rules with their lessons,
and the start form under them, so the rules are read before the plan is written; with one running, the rules
again, each saying "Followed so far" or how often it was flagged and in which months, this month's lab (the next
window), the findings, and the journal as the lab notebook. A start submitted while a method runs lands in this
branch with its reason printed, since the form itself is not shown.

### 10.9 The account page's line

Listing 10-25, Filename: `src/invest_witus_site/holdings/views.py`:

{{file:src/invest_witus_site/holdings/views.py}}

Listing 10-26, Filename: `src/invest_witus_site/holdings/templates/holdings/account_detail.html`:

{{file:src/invest_witus_site/holdings/templates/holdings/account_detail.html}}

One key in the context, `method_plan`, and one section on the page between the statement and the watch list:
the method's name as a link to the method page with the plan's numbers, or the invitation to read the rules and
start one, which opens view C. The header is untouched: the way to the method page is through the account, and
no public page links it.

Thirteen rules go at the end of `site.css`: `.views-list` and its links draw the switch as a row of boxes with
the current one filled; `.band` is the dashed environment line; `.card` is the next-action box; `.status` is a
two-column definition list; `.rules li` and `.findings li` space the lists; `.method-form`, its inputs and
selects, and `.helptext` style the two forms the way chapter 04's waitlist form was styled.

### 10.10 Green, and your first method on your laptop

Listing 10-27, Terminal:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

```text
309 passed in 9.77s
All checks passed!
146 files already formatted
0 errors, 0 warnings, 0 informations
```

Thirty new tests. Now migrate the laptop database:

Listing 10-28, Terminal:

```sh
uv run --env-file .env python manage.py migrate
```

```text
Operations to perform:
  Apply all migrations: accounts, admin, auth, contenttypes, holdings, methods, pages, prices, sessions, watchlist
Running migrations:
  Applying methods.0001_initial... OK
```

Then use it as the owner. Under `runserver`, sign in at `/admin/` with your chapter 05 superuser, open
`/accounts/`, then an account. Under the statement, or under "No statement yet.", the Method section reads "No
method yet on this account" with a link; it opens the method page on view C, with the one method the package
ships, its five rules each reading "lesson coming", and the start form. Pick the method, type `100` as the
amount, `7` as the window, `INDEX` as the symbols and `2026-01-01` as the start, and submit. The page comes back
on view A with a green notice, "Started Index investing with a fixed monthly contribution on Practice.", the
next window, and the on-plan status, which on a plan from January reviewed through today is off plan: every
month since January with no buy is a finding. Log a buy on January 2 and one on February 12, and read the
findings change. Press the three links to flip the views.

Without a browser, the same through the test client, the way chapter 09 looked at the watch list. Start the
method:

Listing 10-29, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -c "from django.contrib.auth.models import User; from django.test import Client; from invest_witus_site.holdings.models import Account; from invest_witus_site.methods.models import MethodPlan; u = User.objects.get(is_superuser=True); a = Account.objects.filter(owner=u).first(); c = Client(); c.force_login(u); r = c.post(f'/accounts/{a.pk}/method/start/', {'method_id': 'index-dca', 'amount': '100', 'buy_window_days': '7', 'symbols': 'INDEX', 'started_on': '2026-01-01'}, follow=True); print(r.redirect_chain); [print(line.strip()) for line in r.content.decode().splitlines() if 'class=\"message ' in line]; print(MethodPlan.active_for(a).to_plan())"
```

```text
[('/accounts/1/method/', 302)]
<li class="message success">Started Index investing with a fixed monthly contribution on Practice.</li>
Plan(method='index-dca', start=datetime.date(2026, 1, 1), amount=Decimal('100.00'), symbols=frozenset({'INDEX'}), buy_window_days=7)
```

(The account id is whichever account is first in your database. Run it twice and the second answer is the page
again, status 200, with "This account already runs a method." in it and still one plan.) The last line is the
row as chapter 03's value, which is what the review will read. Log two entries, the second outside the window:

Listing 10-30, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -c "from django.contrib.auth.models import User; from django.test import Client; from invest_witus_site.holdings.models import Account; from invest_witus_site.methods.models import JournalEntry; u = User.objects.get(is_superuser=True); a = Account.objects.filter(owner=u).first(); c = Client(); c.force_login(u); [print([line.strip() for line in c.post(f'/accounts/{a.pk}/method/log/', row, follow=True).content.decode().splitlines() if 'class=\"message ' in line][0]) for row in ({'date': '2026-01-02', 'action': 'buy', 'symbol': 'INDEX', 'amount': '100', 'shares': '0.5', 'note': 'first buy'}, {'date': '2026-02-12', 'action': 'buy', 'symbol': 'index', 'amount': '100', 'shares': '', 'note': ''})]; print([e.to_entry() for e in JournalEntry.entries_for(a)])"
```

```text
<li class="message success">Logged: 2026-01-02 buy 100.00 of INDEX.</li>
<li class="message success">Logged: 2026-02-12 buy 100.00 of INDEX.</li>
[Entry(day=datetime.date(2026, 1, 2), action=<Action.BUY: 'buy'>, symbol='INDEX', amount=Decimal('100.00')), Entry(day=datetime.date(2026, 2, 12), action=<Action.BUY: 'buy'>, symbol='INDEX', amount=Decimal('100.00'))]
```

The lower-case `index` was stored as `INDEX`, the empty shares as none, and the two rows read back as chapter
03's values. Now the review, through February 28, as view B's tables, read with the test file's own reader:

Listing 10-31, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -c "from django.contrib.auth.models import User; from django.test import Client; from invest_witus_site.holdings.models import Account; from tests.test_ch10 import tables_in, text; u = User.objects.get(is_superuser=True); a = Account.objects.filter(owner=u).first(); c = Client(); c.force_login(u); html = text(c.get(f'/accounts/{a.pk}/method/?view=b&through=2026-02-28')); [print(row) for table in tables_in(html)[:3] for row in table]"
```

```text
('Rule', 'Status', 'Evidence', 'Lesson')
('Buy once in every month of the plan.', 'pass', 'no findings', 'lesson coming')
("Buy within the plan's buy window at the start of the month, not when the news makes you feel ready.", 'fail', '1 finding: 2026-02', 'lesson coming')
("Buy the plan's amount every time: no more after a good month, no less after a bad one.", 'pass', 'no findings', 'lesson coming')
('Buy only the fund or funds named in your plan.', 'pass', 'no findings', 'lesson coming')
('This method has no sell rule. A sale is a change of plan and needs a written reason.', 'pass', 'no findings', 'lesson coming')
('Month', 'Window closes', 'Status', 'Buys', 'Amount', 'Shares', 'Rules flagged')
('2026-01', '2026-01-07', 'done', '1', '100.00', '0.50', 'none')
('2026-02', '2026-02-07', 'done', '1', '100.00', 'not recorded', 'buy-in-window')
('Day', 'Rule', 'What happened', 'Lesson')
('2026-02-12', "Buy within the plan's buy window at the start of the month, not when the news makes you feel ready.", 'Bought on day 12; the window is days 1 to 7.', 'lesson coming')
```

Three tables: every rule with its status and evidence, every month with its buys, amount and shares (February's
"not recorded", because that entry had none), and the one finding with the rule's text and the words "lesson
coming", which is what the TOML file says until a lesson is published. Change `through=2026-02-28` to
`2026-01-31` and the third table is replaced by the sentence "No findings through 2026-01-31: every rule
passed." Last, flip the views:

Listing 10-32, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:///data/private/invest-witus.sqlite3 \
uv run python manage.py shell -c "
import re
from django.contrib.auth.models import User
from django.test import Client
from invest_witus_site.holdings.models import Account
from tests.test_ch10 import text
u = User.objects.get(is_superuser=True); a = Account.objects.filter(owner=u).first(); c = Client(); c.force_login(u)
for view in 'abc':
    html = text(c.get(f'/accounts/{a.pk}/method/?view={view}&through=2026-02-28'))
    print(view, c.session['method_view'], re.findall(r'<h2[^>]*>([^<]+)</h2>', html))
html = text(c.get(f'/accounts/{a.pk}/method/'))
print('plain', re.search(r'aria-current=\"page\">([^<]+)<', html).group(1))
"
```

```text
a a ['Next', 'Off plan: 1 thing to look at', 'My plan', 'Logbook', 'Rise Wellness of Indiana']
b b ['Rule checks', 'Months', 'Findings', 'Journal', 'Rise Wellness of Indiana']
c c ['The rules, and what to re-read', "This month's lab", 'Lab notebook', 'Rise Wellness of Indiana']
plain C: The Lesson Lab
```

Each request names a view, the session keeps it, and the request with no `?view=` lands on the last one chosen.
The last heading on each line is the footer's, which every page carries. The same plan, the same finding and the
same two entries are behind all three lists of headings; what differs is what comes first.

### 10.11 What the owner does outside the editor

The reference app's steps are task 13 in the owner's queue. A learner with a Vercel project of their own does
the same:

1. **Merge the chapter** and let Vercel deploy `main`.
2. **Migrate,** from your machine against the direct connection, with chapter 06's recipe as task 04 corrected
   it: one line, `STORAGE_DATABASE_URL_UNPOOLED=<the direct string from the Neon console>`, in a throwaway
   `.env.migrate` (git ignores `.env.*`), then `DJANGO_SECRET_KEY=only-for-this-shell-not-the-real-one VERCEL=
   uv run --env-file .env.migrate python manage.py migrate --database direct`, then delete the file. Expect
   `Applying methods.0001_initial... OK`. Between the merge and the migration every account page answers 500,
   because the page asks the new table for the account's plan, so do the two in one sitting.
3. **Start the method,** signed in with WitUS, from an account's page: the Method section's link opens view C;
   read the rules, type the amount, the window, the symbols and the start, and submit.
4. **Log the first purchase** from the form under the logbook, as the confirmation shows it.
5. **Read the review** in view A, then flip to B and C. Every rule says "lesson coming" until the lesson exists.

## Checkpoint

- `uv run pytest` prints `309 passed`; ruff and pyright pass.
- Listing 10-29 answers with the notice and the plan as chapter 03's value; a second run is a 200 with "This
  account already runs a method."
- Listing 10-30 logs two entries and reads them back as chapter 03's values.
- Listing 10-31 prints the three tables with the one finding, its rule's text and "lesson coming"; with
  `through=2026-01-31` it prints the no-findings sentence instead of the third table.
- Listing 10-32 prints a different list of headings per view and the session's choice after each request.
- Signed out, every public page has no `<table`, no link to `/accounts/` or `/method/` and no rule; a GET of
  `/accounts/<id>/method/` redirects to the sign-in.
- Signed in as someone who does not own the account, the page and both actions are 404.
- Commit and push: `git add -A && git commit -m "Chapter 10: The method engine and the three views"`.

## Exercises

1. The PRD wants the view saved per user and restored at the next sign-in. Add a `preferred_view` to chapter
   07's `WitusIdentity` (one field, one migration), write it when `?view=` is handled, and read it in
   `chosen_view` when the session has no choice. Write the test first: sign out, sign in, the view is still B.
2. End a plan from the page. Add a POST view `method-end` that sets `active` off and writes a journal note with
   the reason the form requires, and show "Ended on <date>: <reason>" above the start form in view C. Decide,
   and write down, what the review shows for an ended plan.
3. The months table prints "not recorded" when any buy in the month lacks shares. Change `month_rows` so a
   month with two buys, one with shares and one without, prints the known total with an asterisk and a footnote,
   and change the test that pins the current behavior.
4. A second rules file. Copy `index_dca.toml` to `index_dca_quarterly.toml` with a new id and name and a
   `buy_every_months = 3` setting, and see what breaks: `available_methods` lists it at once, the start form
   offers it, and chapter 03's test that the rule ids equal `CHECKED_RULES` tells you the review has no check
   for a quarter. That test is the point of this exercise; chapter 14 adds the second method properly.

## If you get stuck

- Browse: https://github.com/dapperAuteur/invest-witus/tree/v10
- Diff for this chapter: https://github.com/dapperAuteur/invest-witus/compare/v09...v10
- Zip: https://github.com/dapperAuteur/invest-witus/archive/v10.zip
- Take the reference's files. Chapter 10 changed `src/invest_witus/methods/rulebook.py`,
  `src/invest_witus_site/settings.py`, `src/invest_witus_site/urls.py`, `holdings/views.py`, the template
  `holdings/account_detail.html`, `pages/static/pages/site.css` and `docs/site/privacy.md`, and added
  `src/invest_witus_site/methods/` (the whole app) and `tests/test_ch10.py`. No package changed, no
  environment variable was added, nothing moved:
  `git fetch reference --tags && git checkout v10 -- src tests docs/site/privacy.md`.
- `ImportError: cannot import name 'available_methods'` after 10.2: the function is in a different module, or
  the name differs. It lives in `rulebook.py` beside `load_method`.
- `No module named 'invest_witus_site.methods'` after 10.3: the folder has no `__init__.py`, or it was made
  under `holdings/` or inside the library's `invest_witus/methods/` instead of beside the other apps.
- A circular import at startup naming `holdings.views` and `methods.views`: `methods/views.py` imports from
  `holdings/views.py`. It imports `holdings.models` only.
- `test_a_plan_round_trips_to_chapter_03s_plan` fails on `symbols`: `save()` does not call `join_symbols`, or
  the join uses a comma. The stored form is single spaces.
- `test_one_active_plan_per_account` raises no `IntegrityError`: the `UniqueConstraint` lacks its
  `condition`, or names other fields. It raises on the second row's `save()` too, after the first plan was
  ended: the condition is missing, so the constraint covers ended plans as well.
- `test_an_entry_refuses_a_float_a_bad_symbol_a_zero_amount_and_an_unknown_action` passes `hold`: the
  `choices` argument is missing from the `action` field, or was typed by hand with more values than the enum.
- `test_the_review_on_the_web_is_chapter_03s_review` has `shares` of `None` for January: `month_rows` reads
  chapter 03's `Entry` values, which have no shares. It reads the journal rows.
- `test_month_rows_mark_each_month_done_missed_or_open` lacks the `open` row: the current month is only
  appended when it is not already in `months_due` and not before the start.
- `test_the_next_action_is_the_next_window` returns `due` on January 20: the window test compares the wrong
  side. A day past `buy_window_days` moves to the next month.
- `test_the_owner_starts_a_method_from_the_form` gets 200 instead of a redirect: the form is invalid. Print
  `form.errors` in the view for a moment; a missing `started_on` initial or a `choices` list that is empty
  because `available_methods` found no file are the usual causes.
- `test_the_form_refuses_a_second_active_plan_and_bad_numbers` has no "already runs" message: the error is
  raised in `clean_method_id` or the view instead of `clean()`, or view C's running branch does not print
  `start_form.non_field_errors`.
- `test_the_page_shows_a_planted_break_with_its_rule_text_and_lesson_coming` cannot find the rule's text: the
  test compares escaped HTML. Every page assertion goes through `text()`.
- `test_view_b_tables_every_month_with_amounts_and_shares` cannot unpack four tables: the findings table is
  missing when there are findings, or the journal table rendered a `<table>` with no rows; `_entries.html`
  guards with `{% if entries %}`.
- `test_the_three_views_render_for_the_owner_and_404_for_another_owner` finds a heading from another view:
  two views share an `<h2>`. The three headings in `VIEW_HEADINGS` belong to one view each.
- `test_the_view_choice_persists_in_the_session` keeps `zzz`: `chosen_view` writes the session before checking
  the value is in `VIEWS`.
- `test_every_view_shows_the_same_plan_rules_findings_and_journal_and_no_price` fails on `2026-01-01` in C:
  the running branch of view C does not print the plan's numbers. Every view prints the plan, the rules, the
  findings and the journal.
- The same test finds `123.45`: a view prints a close. Nothing on the method page reads the prices table.
- `test_the_method_routes_need_a_sign_in_and_the_actions_a_post` sees 405 for the anonymous POST: the
  decorators are in the other order; `login_required` goes on top.
- `test_public_pages_show_no_table_no_method_link_and_no_rule` finds `/method/` on a public page: the header
  or the footer links the method page. The way in is the account page only.
- `test_the_admin_lists_plans_and_entries_and_refuses_an_unknown_method` gets a 500 instead of the message:
  `validators=[validate_method_id]` is missing from the field, so the admin's form reached `save()`.
- `pyright` reports the test client's response is not an `HttpResponse`: the `text()` helper's parameter is
  typed as `HttpResponse`. The `Page` protocol is the type.
- `ruff check` reports an import-order error in the migration: Listing 10-9's third command.
- On Vercel after the merge, the account page answers 500 and the log says `relation "methods_methodplan"
  does not exist`: step 2 of 10.11 has not run.

## What we learned

- A row can be a value in waiting: two models whose converters hand chapter 03's functions the values they
  were written for, so the review runs on the web without a rewrite, and a test can prove the round trip.
- Rules that live in a file reach every page through one loader; a row that copied them would be a second
  source of truth that goes stale the day the file changes.
- A unique constraint with a condition says "one of these at a time" without forbidding history; the form says
  the same in words so the person never meets the database's error.
- A `ModelForm` takes the fields, the choices and the validators from the model, and runs the model's
  validation inside its own, so the boundary rules are written once and the form inherits them.
- One context, three templates: a view can build everything once and let `{% include %}` with a variable name
  decide the arrangement, and a test can assert that nothing differs between the arrangements but the order.
- The session is a per-visitor dictionary on the server, written in one view and read in the next; a sign-out
  flushes it, so a preference that must outlive the sign-in belongs on the person, not the session.
- "Lesson coming" is a value the file produces, not a default the template invents; the page can print a
  lesson it was given and nothing it was not.

## Next

Chapter 11 brings the paper broker: Alpaca's paper account behind a `Protocol`, orders staged from the plan's
next action and placed on confirm, fills copied into the journal as automatic entries, and the practice budget.
View B gets its order queue then. The method page and its three views do not change for it; the next action
gains a button.

## References

Django Software Foundation. (n.d.-a). *Constraints reference*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/ref/models/constraints/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-b). *Form fields*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/ref/forms/fields/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-c). *Creating forms from models*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/forms/modelforms/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-d). *How to use sessions*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/http/sessions/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-e). *Built-in template tags and filters*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/ref/templates/builtins/ (retrieved October 28, 2026)
