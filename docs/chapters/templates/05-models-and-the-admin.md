# Chapter 05: Models and the admin: accounts, statements and the owner's back office

**Starts from:** tag `v04`. **Ends at:** tag `v05`.
**Written against:** Python 3.14.10, uv 0.13.6, Django 5.2.18, django-stubs 6.1.2, django-stubs-ext 6.1.2,
pytest-django 4.14.0 (October 28, 2026).
**Goal:** the owner signs in at `/admin/`, enters a brokerage statement as a dated snapshot with one line per
symbol, and reads the change between any two statements, symbol by symbol, in exact decimals. The waitlist
from chapter 04 becomes a list the owner can search and approve.
**Time:** 3 hours. Four tables, one admin page of our own, and the first tests that log in.

The listings in this chapter are not typed in by hand. `scripts/render_chapter.py` pastes the real files from
tag `v05` into the chapter text, so what you read and what the tests run are the same bytes.

## What you will learn

- **The admin and what it stands on:** Django's generated back office, and the four contrib apps it needs
  (users and permissions, the table of tables, sessions, one-time messages). They arrive together because the
  admin does not start without them.
- **A superuser and a login:** `createsuperuser`, password validators, and the redirect a stranger gets.
- **Choices, decimals, keys and constraints:** `TextChoices` for a status, `DecimalField` for money and shares,
  `ForeignKey` with `PROTECT` and `CASCADE`, and `UniqueConstraint` for "one per".
- **Normalizing in `save()`:** the chapter 01 rounding rules applied before the database applies its own, and a
  guard that refuses a float.
- **Admin options:** list columns, filters, search, inline rows, an action with a message, and a page of your own
  behind the admin's login.
- **A template filter** and a template that extends the admin's.
- **Tests that log in:** pytest-django's `admin_client`, `django_user_model` and `settings` fixtures, a
  `conftest.py`, and `makemigrations --check` as a test.

## Before the code: a statement, kept as history

A broker's statement is a list of what you held on one date: each symbol, how many shares, what they cost. The
PRD (section 7.3) says the app keeps that as **dated snapshots**: a new statement is a new snapshot, and nothing
is ever overwritten. The change between two dates is then arithmetic over two lists, which chapter 01 taught
us to do in `Decimal`.

Four tables carry it:

| Table | One row is | What it holds | What it never holds |
|---|---|---|---|
| `Account` | One account at one broker | Whose it is, its name, the broker's name, its kind (brokerage, retirement, paper), its currency | Balances or values |
| `Holding` | One symbol in one account | The symbol, its kind (stock, ETF, mutual fund, cash) and a name | Any number; those change from statement to statement |
| `Snapshot` | One statement | The account, the statement's as-of date, where it came from | Prices |
| `SnapshotLine` | One symbol on one statement | Shares, cost basis, the market value the statement printed, a note | A price the app fetched |

What stays out, on purpose:

- **No prices and no portfolio value.** Chapter 08 pulls end-of-day closes; until then the app shows shares and
  cost basis only. A line may record the market value a statement printed, as data entry, but the app computes
  nothing from it.
- **No CSV import.** Entering a statement means typing its lines into the admin. The PRD puts a column-mapped
  import in a later phase, and the library function written here will serve it.
- **Nothing public.** Every page in this chapter is behind the admin's login. The public site from chapter 04 is
  unchanged, and its tests still run.
- **No Sign in with WitUS yet.** The admin is the owner's whole back office until chapter 07. The owner is one
  Django superuser; each account carries an empty `witus_user_id` that chapter 07 fills with the WitUS user id
  (the `sub` claim), so the row will match the person who signs in, not an email.

Django's admin is a back office generated from the models: list, add, change and delete pages for every table
you register, with login, permissions and an audit log included (Django Software Foundation, n.d.-d). For this
phase it *is* the app's private side, which is why the chapter spends its time on models and spends little on
views.

## Steps

### 05.1 One package, then the tests

Listing 05-1, Terminal:

```sh
uv add "django-stubs-ext>=6.1"
```

Chapter 04 wrote `models.CharField[str, str]` so pyright could check fields. The admin's classes are generic
the same way (`admin.ModelAdmin[WaitlistEntry]`), but Django itself does not accept `[...]` on those classes
at runtime: `TypeError: type 'ModelAdmin' is not subscriptable`. django-stubs ships a small runtime package
whose one call teaches Django's classes to accept it; its README asks for it as a production dependency,
called from the settings module (typeddjango, n.d.). The call is in the next listing but one.

Two test files this time. The first is new in kind:

Listing 05-2, Filename: `tests/conftest.py`:

{{file:tests/conftest.py}}

pytest loads a `conftest.py` on its own and makes its fixtures available to every test file beside it. This
one has a single job. Django's default password hasher is slow on purpose, so that guessing passwords is
expensive (Django Software Foundation, n.d.-j); in tests that cost lands on every user created, and the testing
guide's answer is a faster hasher for tests only (Django Software Foundation, n.d.-l). `autouse=True` applies
the fixture to every test without naming it, and pytest-django's `settings` fixture restores the setting when
each test ends (pytest-dev, n.d.).

Listing 05-3, Filename: `tests/test_ch05.py`:

{{file:tests/test_ch05.py}}

Read it before you run it. Things to notice:

- **`admin_client`** is pytest-django's test client already logged in as a throw-away superuser, and
  **`django_user_model`** is whatever user model the project uses (pytest-dev, n.d.). The `account` fixture
  makes a user with no password; it never logs in.
- **`statement(...)`** builds a snapshot and its lines from strings, so a test reads like the statement it
  describes.
- **`test_a_float_never_reaches_a_money_field`** switches pyright off for one line. pyright would refuse
  `line.cost_basis = 1234.56` on its own; the test proves the model refuses it too, for code that skips the type
  checker.
- **`test_models_and_migrations_agree`** runs `makemigrations --check`, which exits non-zero when a model changed
  and no migration says so (Django Software Foundation, n.d.-c). Forget a migration and this test is the one
  that tells you.
- **`test_entering_a_statement_in_the_admin`** posts what the browser posts: the snapshot's fields plus the
  inline's *management form*, the two counters a formset refuses to work without (Django Software Foundation,
  n.d.-e).
- **`RowCollector`** reads a table into tuples, so a test can ask for a whole row of the comparison at once.

Run it:

Listing 05-4, Terminal:

```sh
uv run pytest tests/test_ch05.py
```

```text
RuntimeError: Model class django.contrib.contenttypes.models.ContentType doesn't declare an explicit
app_label and isn't in an application in INSTALLED_APPS.
```

Red first, and the message is Django's way of saying "a model from an app you have not installed". The test
file imports `django.contrib.auth.models.User`; the user model imports permissions, which point at
`ContentType`; and `settings.py` installs none of them yet.

### 05.2 Turn on the admin

Listing 05-5, Filename: `src/invest_witus_site/settings.py`:

{{file:src/invest_witus_site/settings.py}}

Five lines changed meaning:

- **`django_stubs_ext.monkeypatch()`** at the top, before any model or admin class is defined.
- **Five contrib apps.** `admin` is the back office; `auth` holds users, groups and the four permissions (add,
  change, delete, view) that `migrate` creates for every model (Django Software Foundation, n.d.-k);
  `contenttypes` is the table those permissions point at; `sessions` is how a login is remembered between
  requests; `messages` carries one-time notes such as "2 entries approved" from one request to the next
  (Django Software Foundation, n.d.-g). Chapter 04 guessed that sessions would wait for chapter 07; the admin
  needs them now.
- **Middleware order.** `AuthenticationMiddleware` reads the session, so it comes after `SessionMiddleware`;
  `MessageMiddleware` stores in the session, so it comes after it too (Django Software Foundation, n.d.-h).
- **Two context processors** the admin's templates expect: `auth` and `messages`.
- **Password validators.** The four from the `startproject` template, in force for `createsuperuser` and every
  password form (Django Software Foundation, n.d.-j). The only password in this app is the owner's.

`INSTALLED_APPS` also names `invest_witus_site.holdings`, the app written in 05.5. Until it exists, Django will
stop at startup with `ModuleNotFoundError: No module named 'invest_witus_site.holdings'`; that is the next red.

Listing 05-6, Filename: `src/invest_witus_site/urls.py`:

{{file:src/invest_witus_site/urls.py}}

`admin.site.urls` is the whole back office at one prefix (Django Software Foundation, n.d.-d). Every path under
it checks for a logged-in staff user; a stranger is sent to `/admin/login/?next=...`, which the tests check for
the index, the waitlist and the statements page.

### 05.3 The waitlist gets a status

Listing 05-7, Filename: `src/invest_witus_site/pages/models.py`:

{{file:src/invest_witus_site/pages/models.py}}

`TextChoices` is an enum with two extras: `.choices`, the list the field needs, and a `.label` on every member
for display (Django Software Foundation, n.d.-i). With `choices` on a field, model validation refuses any other
value and the admin draws a select. The public form from chapter 04 never mentions `status`, so every signup
gets the default, `waiting`; a test checks that the form still behaves.

Let Django write the migration that adds the column:

Listing 05-8, Terminal:

```sh
uv run python manage.py makemigrations pages
uv run ruff format src/invest_witus_site/pages/migrations
```

```text
Migrations for 'pages':
  src/invest_witus_site/pages/migrations/0002_waitlistentry_status.py
    + Add field status to waitlistentry
```

Listing 05-9, Filename: `src/invest_witus_site/pages/migrations/0002_waitlistentry_status.py`:

{{file:src/invest_witus_site/pages/migrations/0002_waitlistentry_status.py}}

A second migration depends on the first, and `AddField` carries the default so rows that already exist get
`waiting` when it runs. Your timestamp will differ; keep yours.

Listing 05-10, Filename: `src/invest_witus_site/pages/admin.py`:

{{file:src/invest_witus_site/pages/admin.py}}

The admin finds `admin.py` in every installed app on its own. `@admin.register` ties the class to the model;
the options are the ones the reference lists: `list_display` for the columns, `list_filter` for the sidebar,
`search_fields` for the search box, `readonly_fields` for a value shown but not edited (Django Software
Foundation, n.d.-d). The action is a method that takes the request and the selected rows; `@admin.action` gives
it the name shown in the menu, and `actions` lists it (Django Software Foundation, n.d.-a). One `update()`
changes every selected row in one statement, and `message_user` is how an action reports back. The action
menu renders only when the list has rows, which is why the test plants one.

### 05.4 Positions, and what changed, in the library

The arithmetic goes in `src/invest_witus/`, beside the chapter 01 money helpers, with no database in sight. The
models hand it plain values; a CSV import in a later chapter will hand it the same.

Listing 05-11, Filename: `src/invest_witus/holdings.py`:

{{file:src/invest_witus/holdings.py}}

Two decisions to read closely:

- **None is not zero.** A line's `cost_basis` is `None` when the statement did not print one, and a change
  that would need it is `None` too: no number beats a wrong number. A symbol *missing* from a statement is a
  different case: it was not held, so it counts as zero shares at zero cost, which is what makes "sold out"
  and "new" show as real changes.
- **Rounding is the library's.** Every number passes through `to_shares` or `to_money` on the way in, so two
  statements typed with different precision compare like for like, and so a missing symbol's zero prints with
  the same places as its neighbors.

`_by_symbol` refuses a symbol listed twice; the database will refuse it too (05.5), but the function should
not depend on that.

### 05.5 The holdings app and its four tables

Listing 05-12, Filename: `src/invest_witus_site/holdings/apps.py`:

{{file:src/invest_witus_site/holdings/apps.py}}

Make the package the same way chapter 04 did: `src/invest_witus_site/holdings/__init__.py` (empty) and
`src/invest_witus_site/holdings/migrations/__init__.py` (empty).

Listing 05-13, Filename: `src/invest_witus_site/holdings/models.py`:

{{file:src/invest_witus_site/holdings/models.py}}

Table by table:

- **`Account.owner`** is a `ForeignKey` to the user model, named through `settings.AUTH_USER_MODEL` rather than
  imported, which is the convention. `on_delete=PROTECT` means deleting a user who owns accounts raises an error
  instead of taking the accounts with them; the other three keys use `CASCADE`, because a statement's lines
  mean nothing without the statement (Django Software Foundation, n.d.-i). `witus_user_id` is nullable text for
  now; the admin's help text says who fills it.
- **`UniqueConstraint`** in `Meta.constraints`, each with a name, says "one per": one account name per owner,
  one holding per symbol per account, one statement per account per date, one line per symbol per statement
  (Django Software Foundation, n.d.-b). The database enforces these, so two tests expect `IntegrityError`.
- **`Account.snapshots()`** is a query, not `self.snapshot_set`. Django adds that reverse manager at runtime,
  but django-stubs leaves reverse relations to its mypy plugin, and pyright does not run plugins (typeddjango,
  n.d.). Writing the query is one line and the checker can read it.
- **`Holding.kind`** is blank until the owner sets it in the admin. The app never guesses whether a symbol is a
  stock or a fund; a blank it can show is better than a wrong label it cannot.
- **`DecimalField`** holds a `Decimal` and takes `max_digits` (both sides of the point) and `decimal_places`
  (Django Software Foundation, n.d.-i). Shares get six places, the share step from chapter 01; money gets two.
  When a value has more places than the column, Django rounds it with its own rule on the way to the database.
  `SnapshotLine.save()` rounds first, with ours: shares down, money half up.
- **The float guard.** `getattr` with a field name returns whatever is there, so `isinstance(value, float)`
  is a real check, not one pyright would flag as pointless. The PRD's acceptance line for this section is that a
  test fails if a float reaches a money field; this is where it fails.
- **`get_or_create` after `super().save()`** keeps the account's catalog of symbols current without the owner
  doing anything. The holding's kind stays blank; only the owner sets it.

Listing 05-14, Terminal:

```sh
uv run python manage.py makemigrations holdings
uv run ruff format src/invest_witus_site/holdings/migrations
```

```text
Migrations for 'holdings':
  src/invest_witus_site/holdings/migrations/0001_initial.py
    + Create model Account
    + Create model Holding
    + Create model Snapshot
    + Create model SnapshotLine
    + Create constraint account_name_once_per_owner on model account
    + Create constraint holding_symbol_once on model holding
    + Create constraint snapshot_date_once on model snapshot
    + Create constraint line_symbol_once on model snapshotline
```

Listing 05-15, Filename: `src/invest_witus_site/holdings/migrations/0001_initial.py`:

{{file:src/invest_witus_site/holdings/migrations/0001_initial.py}}

`swappable_dependency(settings.AUTH_USER_MODEL)` is how a migration depends on "whatever the user model is"; the
rest is the models, written out. Help texts and choices are part of a migration, so a wording change to either
makes a new one; `makemigrations --check` in the tests will say so.

### 05.6 The admin for accounts and statements

Listing 05-16, Filename: `src/invest_witus_site/holdings/admin.py`:

{{file:src/invest_witus_site/holdings/admin.py}}

Three registrations and one page of our own:

- **`SnapshotAdmin`** carries the inline. `TabularInline` draws the lines as a grid on the snapshot's page, and
  `extra = 3` starts with three empty rows (Django Software Foundation, n.d.-d). This grid is how a statement is
  entered. `date_hierarchy` adds a year, month, day drill-down above the list.
- **`HoldingAdmin`** uses `list_editable`, so the owner sets kinds and names in the list without opening each
  row.
- **`AccountAdmin.get_urls`** adds `<pk>/statements/` to the account's admin URLs. The reference says to wrap a
  custom view in `admin_site.admin_view()`, which runs the same login and staff checks every built-in page gets
  (Django Software Foundation, n.d.-d); the view then checks `has_view_permission` for this account, which a
  superuser passes. Our pattern goes *before* the admin's own, because the admin's `<path:object_id>/` would
  otherwise match `1/statements/` and redirect it.
- **`statements_view`** collects the account's snapshots newest first, picks the two newest unless the query
  string chose others, orders the pair by date, and renders. `each_context` supplies what the admin's template
  needs for its header and sidebar, so the page looks like the rest of the admin.
- **`statements`** is a column that links to the page. `format_html` escapes its arguments and marks the result
  safe, which is the right way to put HTML in a column.

The page prints a change with its sign, and "not shown" where a statement left the cost basis out. That is a
template filter: a Python function in a `templatetags` package inside the app, registered on a `Library`, and
loaded by module name in the template (Django Software Foundation, n.d.-f).

Listing 05-17, Filename: `src/invest_witus_site/holdings/templatetags/holdings_extras.py`:

{{file:src/invest_witus_site/holdings/templatetags/holdings_extras.py}}

Make `src/invest_witus_site/holdings/templatetags/__init__.py` (empty) beside it, or Django will not see the
package. If the development server is already running, restart it after adding a templatetags module; it does
not pick one up on its own (Django Software Foundation, n.d.-f).

Listing 05-18, Filename: `src/invest_witus_site/holdings/templates/admin/holdings/account/snapshots.html`:

{{file:src/invest_witus_site/holdings/templates/admin/holdings/account/snapshots.html}}

It extends `admin/base_site.html`, so it gets the admin's header, sidebar and stylesheet, and fills the
`breadcrumbs` and `content` blocks. The compare form is a plain GET with two selects, so a comparison has a
URL you can bookmark; the two `selected` checks keep the chosen pair shown after the page reloads. `|date:"Y-m-d"`
prints every date the same way, and `|default_if_none` prints "not shown" for a cost basis a statement left out.
The table is an admin page, not a public one, so the chapter 04 rule against tables does not apply; the
`scope` attributes and the caption are what make it read well in a screen reader.

### 05.7 Migrate, create the owner, enter a statement

Listing 05-19, Terminal:

```sh
uv run python manage.py migrate
```

```text
Operations to perform:
  Apply all migrations: admin, auth, contenttypes, holdings, pages, sessions
Running migrations:
  Applying contenttypes.0001_initial... OK
  Applying auth.0001_initial... OK
  Applying admin.0001_initial... OK
  Applying admin.0002_logentry_remove_auto_add... OK
  Applying admin.0003_logentry_add_action_flag_choices... OK
  Applying contenttypes.0002_remove_content_type_name... OK
  Applying auth.0002_alter_permission_name_max_length... OK
  Applying auth.0003_alter_user_email_max_length... OK
  Applying auth.0004_alter_user_username_opts... OK
  Applying auth.0005_alter_user_last_login_null... OK
  Applying auth.0006_require_contenttypes_0002... OK
  Applying auth.0007_alter_validators_add_error_messages... OK
  Applying auth.0008_alter_user_username_max_length... OK
  Applying auth.0009_alter_user_last_name_max_length... OK
  Applying auth.0010_alter_user_group_name_max_length... OK
  Applying auth.0011_update_proxy_permissions... OK
  Applying auth.0012_alter_user_first_name_max_length... OK
  Applying holdings.0001_initial... OK
  Applying pages.0001_initial... OK
  Applying pages.0002_waitlistentry_status... OK
  Applying sessions.0001_initial... OK
```

That is the output on an empty database. If you ran chapter 04's `migrate`, `pages.0001_initial` is already
applied and the list is shorter. The contrib apps bring their own migrations; they are Django's, not yours, and
they live in Django's package, not in your repository.

Now the owner. `createsuperuser` asks for a username, an email address and a password, twice; the validators
from `settings.py` refuse a short, common or all-numeric one (Django Software Foundation, n.d.-c, n.d.-k):

Listing 05-20, Terminal:

```sh
uv run --env-file .env python manage.py createsuperuser
```

```text
Username: owner
Email address: owner@example.com
Password:
Password (again):
Superuser created successfully.
```

Pick a password you will not reuse anywhere. It is stored hashed in the SQLite file under `data/private/`,
which git ignores. (A server with no keyboard sets `DJANGO_SUPERUSER_PASSWORD` and passes `--noinput`; that is
chapter 06's problem, not yours today.)

Listing 05-21, Terminal:

```sh
uv run --env-file .env python manage.py runserver
```

Open http://127.0.0.1:8000/admin/ and sign in. Then walk the whole path once, in this order:

1. **Accounts, Add account.** Name it (for example "Practice"), type the broker's name, pick a kind, pick
   yourself as owner. Leave the WitUS user id empty. Save.
2. **Snapshots, Add snapshot.** Pick the account, type the statement's as-of date (the date printed on the
   statement, not today), and a source such as "September statement". In the grid, one line per symbol: the
   symbol in any case, the shares, the cost basis if the statement shows it. Save. The symbol comes back in
   capitals.
3. **Holdings.** A row per symbol appeared on its own, with a blank kind. Set each kind in the list and save.
4. **Accounts.** The Statements column reads "1 statement". Enter a second statement for a later date with one
   number changed, one symbol gone and one symbol new, the way the planted test does, then open the Statements
   link: the two statements, newest first, and the table of what changed between them.
5. **Waitlist entries.** The people who joined through the public form, each "Waiting". Tick one, choose
   "Approve the selected entries", press Go: the status changes and a message reports the count.

Open http://127.0.0.1:8000/ in the same browser. The public site is as it was, and the header still says
"Sign in": the admin session is the back office's, and the public "Sign in" is Sign in with WitUS, which is
chapter 07.

### 05.8 Green

Listing 05-22, Terminal:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

```text
113 passed in 1.32s
All checks passed!
72 files already formatted
0 errors, 0 warnings, 0 informations
```

Twenty-three new tests and the ninety from before. The whole run still takes about a second, which is what
`conftest.py` bought.

## Checkpoint

- `uv run pytest` prints `113 passed`; ruff and pyright pass.
- `uv run --env-file .env python manage.py runserver` sends a signed-out visitor from `/admin/` to
  `/admin/login/?next=/admin/`, and signs the owner in.
- An account with two statements shows both on its Statements page, with the per-symbol change between them.
- The waitlist's approve action changes the selected rows and reports the count.
- `git status` shows neither `.env` nor anything under `data/private/`; the SQLite file now holds a password
  hash and is never committed.
- Commit and push: `git add -A && git commit -m "Chapter 05: models and the admin"`.

## Exercises

1. The planted test compares shares and cost basis. Add the line's `notes` to the statements page as a last
   column, showing the note from the later statement. Which listing changes, and does any test need to?
2. The PRD's statement flow says "pre-fills the previous snapshot". Write an admin action on `Snapshot`,
   "Copy as a new statement", that creates a snapshot dated today with the same lines, and a test for it. What
   should happen if a statement for today already exists?
3. Replace the two hand-written selects with a Django `Form` holding two `ModelChoiceField`s limited to the
   account's snapshots. Keep every chapter 05 test green; the tests do not care how the selects are drawn.

## If you get stuck

- Browse: https://github.com/dapperAuteur/invest-witus/tree/v05
- Diff for this chapter: https://github.com/dapperAuteur/invest-witus/compare/v04...v05
- Zip: https://github.com/dapperAuteur/invest-witus/archive/v05.zip
- Take the reference's files. Chapter 05 changed `pyproject.toml` and `uv.lock` (one package), added
  `src/invest_witus/holdings.py`, the whole of `src/invest_witus_site/holdings/`,
  `src/invest_witus_site/pages/admin.py`, `src/invest_witus_site/pages/migrations/0002_waitlistentry_status.py`,
  `tests/conftest.py` and `tests/test_ch05.py`, and edited `src/invest_witus_site/settings.py`,
  `src/invest_witus_site/urls.py`, `src/invest_witus_site/pages/models.py` and `scripts/render_chapter.py`
  (it now reads a published chapter's listings from that chapter's tag, so this chapter's edits to
  `settings.py` leave chapter 04's text as it was). Nothing moved:
  `git fetch reference --tags && git checkout v05 -- src tests scripts pyproject.toml uv.lock`, then `uv sync`.
- `RuntimeError: Model class django.contrib.contenttypes.models.ContentType doesn't declare an explicit
  app_label`: the contrib apps are missing from `INSTALLED_APPS`.
- `ModuleNotFoundError: No module named 'invest_witus_site.holdings'`: the app folder or its `__init__.py` is
  missing, or `INSTALLED_APPS` names it before you made it (05.5).
- `TypeError: type 'ModelAdmin' is not subscriptable`: `django_stubs_ext.monkeypatch()` is not called at the top
  of `settings.py`, or `uv add django-stubs-ext` did not run.
- `'holdings_extras' is not a registered tag library`: `templatetags/__init__.py` is missing, or the server was
  not restarted after the module was added.
- `no such table: holdings_account`: run `uv run python manage.py migrate`.
- `IntegrityError: UNIQUE constraint failed`: the same symbol twice on one statement, or a second statement for
  the same account and date. The constraint names in the message say which.
- The statements page is a 404: the custom pattern is listed after `super().get_urls()`, so the admin's
  `<path:object_id>/` pattern took the URL first.
- The login page says the password is too short or too common: that is the validators doing their job; pick
  another.
- "You don't have permission to view or edit anything": the user exists but is not staff. `createsuperuser` sets
  both flags; a user made another way may not.
- The test run takes six seconds instead of one: `tests/conftest.py` is missing or its fixture is not
  `autouse`.

## What we learned

- The admin is a back office generated from the models, and it stands on auth, contenttypes, sessions and
  messages; they are installed together.
- One superuser is the owner's login; validators guard its password; a stranger gets a redirect, not a page.
- `TextChoices` for a status, `DecimalField` with explicit places for money and shares, `ForeignKey` with the
  `on_delete` that matches what the rows mean, and named `UniqueConstraint`s for "one per".
- A model's `save()` is where the app's rules apply before the database's: symbols uppercased, shares rounded
  down, money rounded half up, floats refused.
- Statements are history: a new one is a new snapshot, and the change between two is a pure function over
  their lines, with "not shown" kept apart from zero.
- An admin page of your own: `get_urls` before the admin's own patterns, `admin_view` for the login check, a
  template that extends the admin's, a filter in `templatetags`.
- pytest-django's `admin_client` logs in for you; `conftest.py` is where every test file's fixtures live; and
  `makemigrations --check` catches the migration you forgot.

## Next

Chapter 06 starts from tag `v05` and puts the site on a server: Vercel's Python runtime, Neon Postgres through
`DATABASE_URL`, `collectstatic`, a real secret key, and the owner's login created without a keyboard.

## References

Django Software Foundation. (n.d.-a). *Admin actions*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/ref/contrib/admin/actions/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-b). *Constraints reference*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/ref/models/constraints/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-c). *django-admin and manage.py*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/ref/django-admin/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-d). *The Django admin site*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/ref/contrib/admin/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-e). *Formsets*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/forms/formsets/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-f). *How to create custom template tags and filters*. Django 5.2
documentation. https://docs.djangoproject.com/en/5.2/howto/custom-template-tags/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-g). *The messages framework*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/ref/contrib/messages/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-h). *Middleware*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/ref/middleware/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-i). *Model field reference*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/ref/models/fields/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-j). *Password management in Django*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/auth/passwords/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-k). *Using the Django authentication system*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/auth/default/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-l). *Writing and running tests*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/testing/overview/ (retrieved October 28, 2026)

pytest-dev. (n.d.). *Django helpers*. pytest-django documentation.
https://pytest-django.readthedocs.io/en/latest/helpers.html (retrieved October 28, 2026)

typeddjango. (n.d.). *django-stubs* [README]. GitHub. https://github.com/typeddjango/django-stubs (retrieved
October 28, 2026)
