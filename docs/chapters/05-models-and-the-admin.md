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

```python
"""Fixtures every test file shares. pytest loads this file on its own; nothing imports it.

Added in chapter 05, when tests started creating users: Django's default password hasher is slow
on purpose (it is meant to make guessing expensive), which turns every `admin_client` into half a
second of setup. Tests use the fast hasher instead; the real one still guards real logins.
"""

import pytest
from pytest_django.fixtures import Settings


@pytest.fixture(autouse=True)
def fast_password_hashing(settings: Settings) -> None:
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
```

pytest loads a `conftest.py` on its own and makes its fixtures available to every test file beside it. This
one has a single job. Django's default password hasher is slow on purpose, so that guessing passwords is
expensive (Django Software Foundation, n.d.-j); in tests that cost lands on every user created, and the testing
guide's answer is a faster hasher for tests only (Django Software Foundation, n.d.-l). `autouse=True` applies
the fixture to every test without naming it, and pytest-django's `settings` fixture restores the setting when
each test ends (pytest-dev, n.d.).

Listing 05-3, Filename: `tests/test_ch05.py`:

```python
"""Chapter 05 checkpoint: the admin as the owner's back office, the waitlist list, accounts and
statement snapshots in exact decimals."""

from datetime import date
from decimal import Decimal
from html.parser import HTMLParser

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import IntegrityError
from django.test import Client

from invest_witus.holdings import Position, compare
from invest_witus_site.holdings.models import Account, Holding, Snapshot, SnapshotLine
from invest_witus_site.pages.models import WaitlistEntry

ADMIN_LOGIN = "/admin/login/"


@pytest.mark.django_db
def test_models_and_migrations_agree() -> None:
    """`makemigrations --check` exits 1 when a model changed and no migration says so."""
    try:
        call_command("makemigrations", check=True, dry_run=True, verbosity=0)
    except SystemExit:
        pytest.fail("a model changed without a migration: run manage.py makemigrations")


def test_the_admin_and_what_it_needs_are_installed() -> None:
    for app in ("admin", "auth", "contenttypes", "sessions", "messages"):
        assert f"django.contrib.{app}" in settings.INSTALLED_APPS
    assert len(settings.AUTH_PASSWORD_VALIDATORS) == 4


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/admin/", "/admin/pages/waitlistentry/"])
def test_the_admin_sends_a_stranger_to_the_login_page(client: Client, path: str) -> None:
    """Anonymous visitors get a redirect to the login form, never an admin page."""
    response = client.get(path)
    assert response.status_code == 302
    assert response["Location"] == f"{ADMIN_LOGIN}?next={path}"


@pytest.mark.django_db
def test_the_admin_login_page_is_a_page_not_the_public_sign_in(client: Client) -> None:
    html = client.get(ADMIN_LOGIN).content.decode()
    assert 'name="username"' in html and 'name="password"' in html


@pytest.mark.django_db
def test_the_owner_sees_the_waitlist_in_the_admin(admin_client: Client) -> None:
    """`admin_client` is pytest-django's test client logged in as a throw-away superuser."""
    html = admin_client.get("/admin/").content.decode()
    assert "Waitlist entries" in html
    WaitlistEntry.join("Ada", "ada@example.com")
    html = admin_client.get("/admin/pages/waitlistentry/").content.decode()
    assert "ada@example.com" in html
    assert "Approve the selected entries" in html  # the action menu renders only with rows


@pytest.mark.django_db
def test_the_public_form_still_adds_people_as_waiting(client: Client) -> None:
    """The form from chapter 04 is unchanged; it never sets a status, so the default applies."""
    client.post("/waitlist/", {"name": "Ada", "email": "ada@example.com"})
    assert WaitlistEntry.objects.get().status == WaitlistEntry.Status.WAITING


@pytest.mark.django_db
def test_the_approve_action_marks_only_the_selected_entries(admin_client: Client) -> None:
    ada, _ = WaitlistEntry.join("Ada", "ada@example.com")
    bob, _ = WaitlistEntry.join("Bob", "bob@example.com")
    cy, _ = WaitlistEntry.join("Cy", "cy@example.com")
    response = admin_client.post(
        "/admin/pages/waitlistentry/",
        {"action": "approve", "_selected_action": [str(ada.pk), str(bob.pk)]},
        follow=True,
    )
    assert "2 waitlist entries approved." in response.content.decode()
    approved = {e.email for e in WaitlistEntry.objects.filter(status="approved")}
    assert approved == {"ada@example.com", "bob@example.com"}
    assert WaitlistEntry.objects.get(pk=cy.pk).status == "waiting"


# --- Accounts, statements and exact decimals -------------------------------------------------


@pytest.fixture
def account(django_user_model: type[User]) -> Account:
    owner = django_user_model.objects.create_user("owner")  # no password: never logs in here
    return Account.objects.create(
        name="Practice", broker="Example Broker", kind="paper", owner=owner
    )


def statement(account: Account, as_of: date, *lines: tuple[str, str, str | None]) -> Snapshot:
    """A snapshot with its lines, from (symbol, shares, cost_basis) strings. None: no cost shown."""
    snapshot = Snapshot.objects.create(account=account, as_of=as_of, source="test")
    for symbol, shares, cost in lines:
        SnapshotLine.objects.create(
            snapshot=snapshot,
            symbol=symbol,
            shares=Decimal(shares),
            cost_basis=None if cost is None else Decimal(cost),
        )
    return snapshot


@pytest.mark.django_db
def test_decimals_round_trip_exactly(account: Account) -> None:
    """What goes into a DecimalField comes back as the same Decimal, never a float."""
    snapshot = statement(account, date(2026, 9, 30), ("INDEX", "12.345678", "1234.56"))
    line = SnapshotLine.objects.get(snapshot=snapshot)
    assert isinstance(line.shares, Decimal) and isinstance(line.cost_basis, Decimal)
    assert line.shares == Decimal("12.345678")
    assert line.cost_basis == Decimal("1234.56")
    assert str(line.shares) == "12.345678"
    assert line.market_value is None


@pytest.mark.django_db
def test_shares_round_down_and_money_rounds_half_up(account: Account) -> None:
    """The chapter 01 rules apply before the database rounds its own way."""
    snapshot = statement(account, date(2026, 9, 30), ("INDEX", "1.0000019", "10.005"))
    line = SnapshotLine.objects.get(snapshot=snapshot)
    assert line.shares == Decimal("1.000001")
    assert line.cost_basis == Decimal("10.01")


@pytest.mark.django_db
def test_a_float_never_reaches_a_money_field(account: Account) -> None:
    """pyright already refuses `shares=1.5`. This switches that check off for one line to show
    the runtime guard refuses it too, for code that skips the type checker (a CSV import)."""
    snapshot = Snapshot.objects.create(account=account, as_of=date(2026, 9, 30))
    line = SnapshotLine(snapshot=snapshot, symbol="INDEX", shares=Decimal("1"))
    line.cost_basis = 1234.56  # pyright: ignore[reportAttributeAccessIssue]
    with pytest.raises(TypeError, match="cost_basis must be a Decimal"):
        line.save()
    assert SnapshotLine.objects.count() == 0


@pytest.mark.django_db
def test_a_line_normalizes_its_symbol_and_catalogs_the_holding(account: Account) -> None:
    statement(account, date(2026, 9, 30), (" index ", "1", None))
    line = SnapshotLine.objects.get()
    assert line.symbol == "INDEX"
    holding = Holding.objects.get(account=account, symbol="INDEX")
    assert holding.kind == "", "the app never guesses a security's kind; the owner sets it"
    statement(account, date(2026, 10, 31), ("INDEX", "2", None))
    assert Holding.objects.filter(account=account).count() == 1, "one holding per symbol"


@pytest.mark.django_db
def test_a_symbol_appears_once_per_statement(account: Account) -> None:
    snapshot = statement(account, date(2026, 9, 30), ("INDEX", "1", None))
    with pytest.raises(IntegrityError):
        SnapshotLine.objects.create(snapshot=snapshot, symbol="index", shares=Decimal("2"))


@pytest.mark.django_db
def test_an_account_has_one_statement_per_date(account: Account) -> None:
    statement(account, date(2026, 9, 30))
    with pytest.raises(IntegrityError):
        Snapshot.objects.create(account=account, as_of=date(2026, 9, 30))


# --- The change between two statements --------------------------------------------------------


def test_compare_pairs_every_symbol_from_either_statement() -> None:
    before = [Position("OTHER", Decimal("5"), Decimal("500")), Position("INDEX", Decimal("10"))]
    after = [Position("INDEX", Decimal("11.5"), Decimal("1150")), Position("THIRD", Decimal("2"))]
    changes = compare(before, after)
    assert [c.symbol for c in changes] == ["INDEX", "OTHER", "THIRD"], "symbol order"
    index, other, third = changes
    assert (index.shares_change, index.cost_change) == (Decimal("1.500000"), None)
    assert (other.shares_before, other.shares_after) == (Decimal("5"), Decimal("0"))
    assert (other.cost_before, other.cost_after) == (Decimal("500.00"), Decimal("0"))
    assert other.cost_change == Decimal("-500.00")
    assert (third.shares_change, third.cost_change) == (Decimal("2.000000"), None)
    assert third.cost_before == Decimal("0"), "a symbol missing from a statement was not held"


def test_compare_refuses_a_symbol_listed_twice() -> None:
    twice = [Position("INDEX", Decimal("1")), Position("INDEX", Decimal("2"))]
    with pytest.raises(ValueError, match="INDEX appears twice"):
        compare(twice, [])


def test_an_unchanged_symbol_says_so() -> None:
    same = [Position("INDEX", Decimal("10"), Decimal("1000"))]
    (change,) = compare(same, same)
    assert not change.changed
    assert change.shares_change == Decimal("0") and change.cost_change == Decimal("0.00")


@pytest.mark.django_db
def test_the_change_between_two_snapshots_through_the_models(account: Account) -> None:
    """A planted change: one more purchase of INDEX, OTHER sold out, THIRD new."""
    september = statement(
        account, date(2026, 9, 30), ("INDEX", "10", "1000.00"), ("OTHER", "5", "500.00")
    )
    october = statement(
        account, date(2026, 10, 31), ("INDEX", "11.5", "1150.00"), ("THIRD", "2", "200.00")
    )
    changes = {c.symbol: c for c in october.changes_since(september)}
    assert changes["INDEX"].shares_change == Decimal("1.500000")
    assert changes["INDEX"].cost_change == Decimal("150.00")
    assert changes["OTHER"].shares_change == Decimal("-5.000000")
    assert changes["OTHER"].cost_change == Decimal("-500.00")
    assert changes["THIRD"].shares_change == Decimal("2.000000")
    assert changes["THIRD"].cost_change == Decimal("200.00")
    assert account.latest_snapshot() == october
    assert [s.as_of for s in account.snapshots()] == [date(2026, 10, 31), date(2026, 9, 30)]


@pytest.mark.django_db
def test_entering_a_statement_in_the_admin(admin_client: Client, account: Account) -> None:
    """The owner's way in: the snapshot form and its inline rows, posted as a browser would."""
    form = {
        "account": str(account.pk),
        "as_of": "2026-09-30",
        "source": "September statement",
        # The inline's management form: how many rows were sent, how many already existed.
        "snapshotline_set-TOTAL_FORMS": "2",
        "snapshotline_set-INITIAL_FORMS": "0",
        "snapshotline_set-0-symbol": "index",
        "snapshotline_set-0-shares": "10",
        "snapshotline_set-0-cost_basis": "1000.00",
        "snapshotline_set-1-symbol": "OTHER",
        "snapshotline_set-1-shares": "5",
        "snapshotline_set-1-cost_basis": "",
    }
    response = admin_client.post("/admin/holdings/snapshot/add/", form, follow=True)
    assert response.status_code == 200
    snapshot = Snapshot.objects.get(account=account, as_of=date(2026, 9, 30))
    assert [(line.symbol, line.shares) for line in snapshot.lines()] == [
        ("INDEX", Decimal("10.000000")),
        ("OTHER", Decimal("5.000000")),
    ]
    assert snapshot.lines().get(symbol="OTHER").cost_basis is None
    assert set(Holding.objects.filter(account=account).values_list("symbol", flat=True)) == {
        "INDEX",
        "OTHER",
    }


# --- The statements page in the admin ---------------------------------------------------------


class RowCollector(HTMLParser):
    """Every table row as a tuple of its cells' text, so a test can ask for a whole row at once."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[tuple[str, ...]] = []
        self._cells: list[str] | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._cells = []
        elif tag in ("td", "th") and self._cells is not None:
            self._text = []

    def handle_data(self, data: str) -> None:
        self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._cells is not None:
            self._cells.append(" ".join("".join(self._text).split()))
        elif tag == "tr" and self._cells is not None:
            self.rows.append(tuple(self._cells))
            self._cells = None


def rows_in(html: str) -> list[tuple[str, ...]]:
    collector = RowCollector()
    collector.feed(html)
    return collector.rows


def statements_path(account: Account) -> str:
    return f"/admin/holdings/account/{account.pk}/statements/"


@pytest.mark.django_db
def test_the_statements_page_needs_a_login(client: Client, account: Account) -> None:
    response = client.get(statements_path(account))
    assert response.status_code == 302
    assert response["Location"] == f"{ADMIN_LOGIN}?next={statements_path(account)}"


@pytest.mark.django_db
def test_the_statements_page_before_any_statement(admin_client: Client, account: Account) -> None:
    html = admin_client.get(statements_path(account)).content.decode()
    assert "No statements yet." in html
    assert f"/admin/holdings/snapshot/add/?account={account.pk}" in html
    assert "Change between two statements" not in html, "nothing to compare yet"


@pytest.mark.django_db
def test_the_statements_page_lists_them_and_compares_the_two_newest(
    admin_client: Client, account: Account
) -> None:
    statement(account, date(2026, 9, 30), ("INDEX", "10", "1000.00"), ("OTHER", "5", "500.00"))
    statement(account, date(2026, 10, 31), ("INDEX", "11.5", "1150.00"), ("THIRD", "2", None))
    html = admin_client.get(statements_path(account)).content.decode()
    assert "From 2026-09-30 to 2026-10-31." in html
    rows = rows_in(html)
    assert ("INDEX", "10.000000", "11.500000", "+1.500000", "1000.00", "1150.00", "+150.00") in rows
    assert ("OTHER", "5.000000", "0.000000", "-5.000000", "500.00", "0.00", "-500.00") in rows
    assert ("THIRD", "0.000000", "2.000000", "+2.000000", "0.00", "not shown", "not shown") in rows
    accounts = admin_client.get("/admin/holdings/account/").content.decode()
    assert f'href="{statements_path(account)}">2 statements</a>' in accounts


@pytest.mark.django_db
def test_any_two_statements_can_be_chosen_in_either_order(
    admin_client: Client, account: Account
) -> None:
    september = statement(account, date(2026, 9, 30), ("INDEX", "10", "1000.00"))
    statement(account, date(2026, 10, 31), ("INDEX", "11", "1100.00"))
    november = statement(account, date(2026, 11, 30), ("INDEX", "12", "1200.00"))
    chosen = f"?earlier={november.pk}&later={september.pk}"
    html = admin_client.get(statements_path(account) + chosen).content.decode()
    assert "From 2026-09-30 to 2026-11-30." in html, "the earlier date is always 'from'"
    assert (
        "INDEX",
        "10.000000",
        "12.000000",
        "+2.000000",
        "1000.00",
        "1200.00",
        "+200.00",
    ) in rows_in(html)
```

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

```python
"""Django settings for Invest.WitUS.

Anything that differs between your laptop and a server comes from an environment variable, with a
safe default for the laptop. The names are listed in `.env.example`; values never go in git.
"""

import os
from pathlib import Path

import django_stubs_ext

# django-stubs describes Django's classes as generics (`ModelAdmin[WaitlistEntry]`) so pyright can
# check them, but Django itself does not accept `[...]` on those classes at runtime. This one call
# teaches them to, so the admin code can be written the way the type checker reads it.
django_stubs_ext.monkeypatch()

# The repository root. This file is src/invest_witus_site/settings.py, three levels down.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# DEV-ONLY FALLBACK. Django's `check --deploy` warns about the `django-insecure-` prefix, which is
# the point: a server must set DJANGO_SECRET_KEY (chapter 06), and this value must never reach one.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or "django-insecure-dev-only-set-DJANGO_SECRET_KEY"

# Off unless DJANGO_DEBUG=1. Debug pages show settings and source code; never on a server.
DEBUG = os.environ.get("DJANGO_DEBUG") == "1"

# Comma-separated host names. The default answers a laptop and nothing else.
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

# Chapter 04 installed only staticfiles and the pages app. The admin (chapter 05) needs the four
# contrib apps it is built on: auth (users and permissions), contenttypes (the table of tables that
# permissions point at), sessions (how a login is remembered) and messages (the "2 entries approved"
# notes after an action). They arrive together because the admin does not start without them.
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "invest_witus_site.pages",
    "invest_witus_site.holdings",
]

# Order matters: a middleware sees the request top to bottom and the response bottom to top.
# Sessions must load before authentication can read the session, and messages after that.
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "invest_witus_site.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Templates live in each app's templates/ folder; nothing outside an app.
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "invest_witus_site.pages.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "invest_witus_site.wsgi.application"

# SQLite, in the folder git ignores. Chapter 06 switches to Postgres through DATABASE_URL.
DATA_DIR = BASE_DIR / "data" / "private"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "invest-witus.sqlite3",
    }
}

# The only password in this app is the owner's admin login (chapter 05). Sign in with WitUS
# (chapter 07) adds no passwords. `createsuperuser` refuses a password these validators reject.
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

# The FAQ, privacy and terms pages are Markdown files in the repo, so a wording change is a normal
# commit with a diff anyone can read.
SITE_PAGES_DIR = BASE_DIR / "docs" / "site"
```

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

```python
"""Where every URL of the site starts. Each app lists its own paths; this file includes them."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # The owner's back office. Every page under it requires a staff login (chapter 05).
    path("admin/", admin.site.urls),
    path("", include("invest_witus_site.pages.urls")),
]
```

`admin.site.urls` is the whole back office at one prefix (Django Software Foundation, n.d.-d). Every path under
it checks for a logged-in staff user; a stranger is sent to `/admin/login/?next=...`, which the tests check for
the index, the waitlist and the statements page.

### 05.3 The waitlist gets a status

Listing 05-7, Filename: `src/invest_witus_site/pages/models.py`:

```python
"""Database tables for the public pages. This chapter has one: the waitlist."""

from datetime import datetime

from django.db import models


class WaitlistEntry(models.Model):
    """One person who asked to hear when the app opens. One row per email address.

    The `[str, str]` after each field type is for pyright: the type you may assign, and the type
    you read back. django-stubs leaves those two for its mypy plugin to fill in, so with pyright we
    write them ourselves (the way you would write `Field<string, string>` in TypeScript).
    """

    class Status(models.TextChoices):
        """Where a person stands. The public form only ever creates `waiting`; the owner
        approves in the admin (chapter 05). An approved person is told when the app opens."""

        WAITING = "waiting", "Waiting"
        APPROVED = "approved", "Approved"

    name: models.CharField[str, str] = models.CharField(max_length=120)
    email: models.EmailField[str, str] = models.EmailField(max_length=254, unique=True)
    created_at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now_add=True)
    status: models.CharField[str, str] = models.CharField(
        max_length=10, choices=Status.choices, default=Status.WAITING
    )

    class Meta:
        ordering = ["created_at"]
        verbose_name_plural = "waitlist entries"

    def __str__(self) -> str:
        return self.email

    @classmethod
    def join(cls, name: str, email: str) -> tuple[WaitlistEntry, bool]:
        """Add a person once. The same address in any case or spacing keeps the first row.

        Returns the row and whether it was created now, the way `get_or_create` does.
        """
        return cls.objects.get_or_create(
            email=email.strip().lower(), defaults={"name": name.strip()}
        )
```

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

```python
# Generated by Django 5.2.18 on 2026-10-28 04:12

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pages", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="waitlistentry",
            name="status",
            field=models.CharField(
                choices=[("waiting", "Waiting"), ("approved", "Approved")],
                default="waiting",
                max_length=10,
            ),
        ),
    ]
```

A second migration depends on the first, and `AddField` carries the default so rows that already exist get
`waiting` when it runs. Your timestamp will differ; keep yours.

Listing 05-10, Filename: `src/invest_witus_site/pages/admin.py`:

```python
"""The waitlist in the admin: a list to read, search and approve from. Owner only."""

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from invest_witus_site.pages.models import WaitlistEntry


@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(admin.ModelAdmin[WaitlistEntry]):
    list_display = ("email", "name", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("email", "name")
    ordering = ("created_at",)
    # `created_at` is set on insert (auto_now_add); the form shows it and never edits it.
    readonly_fields = ("created_at",)
    actions = ("approve",)

    @admin.action(description="Approve the selected entries")
    def approve(self, request: HttpRequest, queryset: QuerySet[WaitlistEntry]) -> None:
        """One UPDATE for every selected row, then a note at the top of the list."""
        count = queryset.update(status=WaitlistEntry.Status.APPROVED)
        noun = "entry" if count == 1 else "entries"
        self.message_user(request, f"{count} waitlist {noun} approved.")
```

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

```python
"""What an account holds on one statement, and what changed between two statements.

Pure functions over plain values: no database here. The Django models (chapter 05) turn their
rows into `Position`s and hand them to `compare`, so the arithmetic can be tested without a
database and reused by a CSV import later.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from invest_witus.money import to_money, to_shares

ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class Position:
    """One line of a statement: how much of one symbol, and what it cost in total.

    `cost_basis` is None when the statement did not print one. That is different from zero:
    zero means "cost nothing", None means "the statement did not say".
    """

    symbol: str
    shares: Decimal
    cost_basis: Decimal | None = None


@dataclass(frozen=True, slots=True)
class Change:
    """One symbol, before and after. A symbol missing from a statement counts as not held:
    zero shares and zero cost."""

    symbol: str
    shares_before: Decimal
    shares_after: Decimal
    cost_before: Decimal | None
    cost_after: Decimal | None

    @property
    def shares_change(self) -> Decimal:
        return to_shares(self.shares_after - self.shares_before)

    @property
    def cost_change(self) -> Decimal | None:
        """None when either statement left the cost basis out: no number beats a wrong one."""
        if self.cost_before is None or self.cost_after is None:
            return None
        return to_money(self.cost_after - self.cost_before)

    @property
    def changed(self) -> bool:
        return self.shares_change != ZERO or self.cost_change not in (ZERO, None)


def _by_symbol(positions: Iterable[Position]) -> dict[str, Position]:
    table: dict[str, Position] = {}
    for position in positions:
        if position.symbol in table:
            raise ValueError(f"{position.symbol} appears twice on one statement")
        table[position.symbol] = position
    return table


def compare(before: Iterable[Position], after: Iterable[Position]) -> list[Change]:
    """Every symbol on either statement, in symbol order, with its shares and cost on each side.

    Shares are rounded down to the share step and money to the cent (chapter 01), so two
    statements typed with different precision still compare like for like.
    """
    earlier = _by_symbol(before)
    later = _by_symbol(after)
    changes: list[Change] = []
    for symbol in sorted(earlier.keys() | later.keys()):
        old = earlier.get(symbol)
        new = later.get(symbol)
        changes.append(
            Change(
                symbol=symbol,
                shares_before=to_shares(old.shares if old else ZERO),
                shares_after=to_shares(new.shares if new else ZERO),
                cost_before=_cost(old),
                cost_after=_cost(new),
            )
        )
    return changes


def _cost(position: Position | None) -> Decimal | None:
    if position is None:
        return to_money(ZERO)
    if position.cost_basis is None:
        return None
    return to_money(position.cost_basis)
```

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

```python
from django.apps import AppConfig


class HoldingsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "invest_witus_site.holdings"
```

Make the package the same way chapter 04 did: `src/invest_witus_site/holdings/__init__.py` (empty) and
`src/invest_witus_site/holdings/migrations/__init__.py` (empty).

Listing 05-13, Filename: `src/invest_witus_site/holdings/models.py`:

```python
"""Accounts, what they hold, and the dated statements that say so.

Four tables. An `Account` belongs to the owner. A `Snapshot` is one statement for one account on
one date; its `SnapshotLine`s are the numbers on it, one per symbol. A `Holding` is one row per
account and symbol: the symbol's kind and name, which do not change from statement to statement.
The numbers live on the lines, never on the holding, so history is kept and nothing is overwritten.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models

from invest_witus.holdings import Change, Position, compare
from invest_witus.money import to_money, to_shares

# Six decimal places for shares (the share step from chapter 01), two for money. `max_digits`
# counts both sides of the point: 18 and 6 allow up to 999,999,999,999 shares.
SHARE_PLACES = 6
MONEY_PLACES = 2


class Account(models.Model):
    """One account at one broker, entered by hand from its statements.

    `owner` is the Django user who manages the account in the admin: the owner's own login until
    Sign in with WitUS (chapter 07). `witus_user_id` is the WitUS user id (the `sub` claim) the
    account will be matched by after that chapter; it stays empty until then.
    """

    class Kind(models.TextChoices):
        BROKERAGE = "brokerage", "Brokerage (taxable)"
        RETIREMENT = "retirement", "Retirement"
        PAPER = "paper", "Paper (practice)"

    owner: models.ForeignKey[User, User] = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="accounts"
    )
    witus_user_id: models.CharField[str | None, str | None] = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text="Filled by Sign in with WitUS (chapter 07). Leave empty.",
    )
    name: models.CharField[str, str] = models.CharField(max_length=80)
    broker: models.CharField[str, str] = models.CharField(
        max_length=80, help_text="The broker's name as it appears on the statement."
    )
    kind: models.CharField[str, str] = models.CharField(max_length=10, choices=Kind.choices)
    currency: models.CharField[str, str] = models.CharField(
        max_length=3, default="USD", choices=[("USD", "US dollar")]
    )
    created_at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "name"], name="account_name_once_per_owner"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.broker})"

    def snapshots(self) -> models.QuerySet[Snapshot]:
        """Newest first. Written as a query, not `self.snapshot_set`, so pyright can read it."""
        return Snapshot.objects.filter(account=self).order_by("-as_of")

    def latest_snapshot(self) -> Snapshot | None:
        return self.snapshots().first()


class Holding(models.Model):
    """One symbol in one account: the parts of a holding that do not change between statements."""

    class Kind(models.TextChoices):
        STOCK = "stock", "Stock"
        ETF = "etf", "ETF"
        MUTUAL_FUND = "mutual_fund", "Mutual fund"
        CASH = "cash", "Cash"

    account: models.ForeignKey[Account, Account] = models.ForeignKey(
        Account, on_delete=models.CASCADE
    )
    symbol: models.CharField[str, str] = models.CharField(max_length=20)
    # Blank until the owner sets it in the admin. The app never guesses a security's kind.
    kind: models.CharField[str, str] = models.CharField(
        max_length=12, choices=Kind.choices, blank=True, default=""
    )
    name: models.CharField[str, str] = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        ordering = ["account", "symbol"]
        constraints = [
            models.UniqueConstraint(fields=["account", "symbol"], name="holding_symbol_once"),
        ]

    def __str__(self) -> str:
        return f"{self.symbol} in {self.account}"


class Snapshot(models.Model):
    """One statement: an account on an as-of date. Its lines are the numbers on it."""

    account: models.ForeignKey[Account, Account] = models.ForeignKey(
        Account, on_delete=models.CASCADE
    )
    as_of: models.DateField[date, date] = models.DateField(
        help_text="The statement's as-of date, not the day you typed it in."
    )
    source: models.CharField[str, str] = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="For example: October statement PDF.",
    )
    created_at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-as_of"]
        constraints = [
            models.UniqueConstraint(fields=["account", "as_of"], name="snapshot_date_once"),
        ]

    def __str__(self) -> str:
        return f"{self.account.name} as of {self.as_of:%Y-%m-%d}"

    def lines(self) -> models.QuerySet[SnapshotLine]:
        return SnapshotLine.objects.filter(snapshot=self).order_by("symbol")

    def positions(self) -> list[Position]:
        """The lines as the library's plain values, ready for `compare`."""
        return [Position(line.symbol, line.shares, line.cost_basis) for line in self.lines()]

    def changes_since(self, earlier: Snapshot) -> list[Change]:
        """Per symbol: shares and cost basis on `earlier`, on this snapshot, and the difference."""
        return compare(earlier.positions(), self.positions())


class SnapshotLine(models.Model):
    """One symbol on one statement. Shares and money are Decimals, rounded with the library's
    rules before the database applies its own."""

    snapshot: models.ForeignKey[Snapshot, Snapshot] = models.ForeignKey(
        Snapshot, on_delete=models.CASCADE
    )
    symbol: models.CharField[str, str] = models.CharField(max_length=20)
    shares: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=18, decimal_places=SHARE_PLACES
    )
    cost_basis: models.DecimalField[Decimal | None, Decimal | None] = models.DecimalField(
        max_digits=14,
        decimal_places=MONEY_PLACES,
        null=True,
        blank=True,
        help_text="Total cost as the statement prints it; empty if not shown.",
    )
    market_value: models.DecimalField[Decimal | None, Decimal | None] = models.DecimalField(
        max_digits=14,
        decimal_places=MONEY_PLACES,
        null=True,
        blank=True,
        help_text="Value as the statement prints it, if any. No prices yet.",
    )
    notes: models.CharField[str, str] = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["symbol"]
        constraints = [
            models.UniqueConstraint(fields=["snapshot", "symbol"], name="line_symbol_once"),
        ]

    def __str__(self) -> str:
        return f"{self.symbol}: {self.shares} shares"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Normalize before the row is written: the symbol's case and spacing, the decimals'
        rounding, and the rule that a float never reaches a money field."""
        for field in ("shares", "cost_basis", "market_value"):
            value = getattr(self, field)
            if isinstance(value, float):
                raise TypeError(f"{field} must be a Decimal, not a float ({value!r})")
        self.symbol = self.symbol.strip().upper()
        self.shares = to_shares(self.shares)
        if self.cost_basis is not None:
            self.cost_basis = to_money(self.cost_basis)
        if self.market_value is not None:
            self.market_value = to_money(self.market_value)
        super().save(*args, **kwargs)
        # The account's catalog of symbols. The kind stays blank until the owner sets it.
        Holding.objects.get_or_create(account=self.snapshot.account, symbol=self.symbol)
```

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

```python
# Generated by Django 5.2.18 on 2026-10-28 04:14

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Account",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "witus_user_id",
                    models.CharField(
                        blank=True,
                        help_text="Filled by Sign in with WitUS (chapter 07). Leave empty.",
                        max_length=64,
                        null=True,
                    ),
                ),
                ("name", models.CharField(max_length=80)),
                (
                    "broker",
                    models.CharField(
                        help_text="The broker's name as it appears on the statement.", max_length=80
                    ),
                ),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("brokerage", "Brokerage (taxable)"),
                            ("retirement", "Retirement"),
                            ("paper", "Paper (practice)"),
                        ],
                        max_length=10,
                    ),
                ),
                (
                    "currency",
                    models.CharField(choices=[("USD", "US dollar")], default="USD", max_length=3),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="accounts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="Holding",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("symbol", models.CharField(max_length=20)),
                (
                    "kind",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("stock", "Stock"),
                            ("etf", "ETF"),
                            ("mutual_fund", "Mutual fund"),
                            ("cash", "Cash"),
                        ],
                        default="",
                        max_length=12,
                    ),
                ),
                ("name", models.CharField(blank=True, default="", max_length=120)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="holdings.account"
                    ),
                ),
            ],
            options={
                "ordering": ["account", "symbol"],
            },
        ),
        migrations.CreateModel(
            name="Snapshot",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "as_of",
                    models.DateField(
                        help_text="The statement's as-of date, not the day you typed it in."
                    ),
                ),
                (
                    "source",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="For example: October statement PDF.",
                        max_length=120,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="holdings.account"
                    ),
                ),
            ],
            options={
                "ordering": ["-as_of"],
            },
        ),
        migrations.CreateModel(
            name="SnapshotLine",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("symbol", models.CharField(max_length=20)),
                ("shares", models.DecimalField(decimal_places=6, max_digits=18)),
                (
                    "cost_basis",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="Total cost as the statement prints it; empty if not shown.",
                        max_digits=14,
                        null=True,
                    ),
                ),
                (
                    "market_value",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="Value as the statement prints it, if any. No prices yet.",
                        max_digits=14,
                        null=True,
                    ),
                ),
                ("notes", models.CharField(blank=True, default="", max_length=200)),
                (
                    "snapshot",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="holdings.snapshot"
                    ),
                ),
            ],
            options={
                "ordering": ["symbol"],
            },
        ),
        migrations.AddConstraint(
            model_name="account",
            constraint=models.UniqueConstraint(
                fields=("owner", "name"), name="account_name_once_per_owner"
            ),
        ),
        migrations.AddConstraint(
            model_name="holding",
            constraint=models.UniqueConstraint(
                fields=("account", "symbol"), name="holding_symbol_once"
            ),
        ),
        migrations.AddConstraint(
            model_name="snapshot",
            constraint=models.UniqueConstraint(
                fields=("account", "as_of"), name="snapshot_date_once"
            ),
        ),
        migrations.AddConstraint(
            model_name="snapshotline",
            constraint=models.UniqueConstraint(
                fields=("snapshot", "symbol"), name="line_symbol_once"
            ),
        ),
    ]
```

`swappable_dependency(settings.AUTH_USER_MODEL)` is how a migration depends on "whatever the user model is"; the
rest is the models, written out. Help texts and choices are part of a migration, so a wording change to either
makes a new one; `makemigrations --check` in the tests will say so.

### 05.6 The admin for accounts and statements

Listing 05-16, Filename: `src/invest_witus_site/holdings/admin.py`:

```python
"""Accounts, holdings and statements in the admin. This is the owner's whole back office for
entering a statement: a snapshot with its lines, typed in by hand. A CSV import is a later chapter.
"""

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import URLPattern, path, reverse
from django.utils.html import format_html

from invest_witus_site.holdings.models import Account, Holding, Snapshot, SnapshotLine


def pick(
    snapshots: list[Snapshot], chosen: str | None, default: Snapshot | None
) -> Snapshot | None:
    """The snapshot whose id was chosen in the form, or the default when none (or nonsense) was."""
    for snapshot in snapshots:
        if str(snapshot.pk) == chosen:
            return snapshot
    return default


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin[Account]):
    list_display = ("name", "broker", "kind", "currency", "owner", "statements")
    list_filter = ("kind",)
    search_fields = ("name", "broker")
    readonly_fields = ("created_at",)

    def get_urls(self) -> list[URLPattern]:
        """One page of our own under the account's admin URLs. `admin_view` wraps it in the
        same login and staff checks every built-in admin page gets."""
        statements = path(
            "<int:pk>/statements/",
            self.admin_site.admin_view(self.statements_view),
            name="holdings_account_statements",
        )
        return [statements, *super().get_urls()]

    @admin.display(description="Statements")
    def statements(self, account: Account) -> str:
        url = reverse("admin:holdings_account_statements", args=[account.pk])
        count = account.snapshots().count()
        return format_html('<a href="{}">{} statement{}</a>', url, count, "" if count == 1 else "s")

    def statements_view(self, request: HttpRequest, pk: int) -> HttpResponse:
        """The account's statements by date, and the change between any two of them.

        With no choice made, the two newest are compared. Whichever two are chosen, the earlier
        date is "from" and the later is "to".
        """
        account = get_object_or_404(Account, pk=pk)
        if not self.has_view_permission(request, account):
            raise PermissionDenied
        snapshots = list(account.snapshots())  # newest first
        newest = snapshots[0] if snapshots else None
        second = snapshots[1] if len(snapshots) > 1 else None
        earlier = pick(snapshots, request.GET.get("earlier"), second)
        later = pick(snapshots, request.GET.get("later"), newest)
        pair: tuple[Snapshot, Snapshot] | None = None
        if earlier is not None and later is not None:
            pair = (earlier, later) if earlier.as_of <= later.as_of else (later, earlier)
        context = {
            **self.admin_site.each_context(request),
            "title": f"Statements for {account}",
            "account": account,
            "snapshots": snapshots,
            "pair": pair,
            "changes": pair[1].changes_since(pair[0]) if pair else [],
        }
        return TemplateResponse(request, "admin/holdings/account/snapshots.html", context)


@admin.register(Holding)
class HoldingAdmin(admin.ModelAdmin[Holding]):
    """Rows appear on their own when a statement line names a new symbol. The owner's job here
    is to set each one's kind (stock, ETF, mutual fund, cash) and, if wanted, a name."""

    list_display = ("symbol", "account", "kind", "name")
    list_editable = ("kind", "name")
    list_filter = ("kind", "account")
    search_fields = ("symbol", "name")


class SnapshotLineInline(admin.TabularInline[SnapshotLine, Snapshot]):
    """The statement's lines, edited on the snapshot's own page as a grid."""

    model = SnapshotLine
    fields = ("symbol", "shares", "cost_basis", "market_value", "notes")
    extra = 3  # three empty rows to start; the page adds more on demand


@admin.register(Snapshot)
class SnapshotAdmin(admin.ModelAdmin[Snapshot]):
    list_display = ("as_of", "account", "source", "line_count")
    list_filter = ("account",)
    date_hierarchy = "as_of"
    readonly_fields = ("created_at",)
    inlines = (SnapshotLineInline,)

    @admin.display(description="Lines")
    def line_count(self, snapshot: Snapshot) -> int:
        return snapshot.lines().count()
```

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

```python
"""Template filters for the holdings pages. `{% load holdings_extras %}` makes them available."""

from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def signed(value: Decimal | None) -> str:
    """A change with its sign: `+1.500000`, `-500.00`, or plain `0.00`. None: the statement
    did not show the number, so there is nothing to compare."""
    if value is None:
        return "not shown"
    if value == 0:
        return str(value)
    return f"{value:+}"
```

Make `src/invest_witus_site/holdings/templatetags/__init__.py` (empty) beside it, or Django will not see the
package. If the development server is already running, restart it after adding a templatetags module; it does
not pick one up on its own (Django Software Foundation, n.d.-f).

Listing 05-18, Filename: `src/invest_witus_site/holdings/templates/admin/holdings/account/snapshots.html`:

```html
{% extends "admin/base_site.html" %}
{% load holdings_extras %}

{% block breadcrumbs %}
<div class="breadcrumbs">
  <a href="{% url 'admin:index' %}">Home</a>
  &rsaquo; <a href="{% url 'admin:app_list' app_label='holdings' %}">Holdings</a>
  &rsaquo; <a href="{% url 'admin:holdings_account_changelist' %}">Accounts</a>
  &rsaquo; <a href="{% url 'admin:holdings_account_change' account.pk %}">{{ account }}</a>
  &rsaquo; Statements
</div>
{% endblock %}

{% block content %}
<div id="content-main">
  <h2>Statements, newest first</h2>
  {% if snapshots %}
  <ul>
    {% for snapshot in snapshots %}
    <li>
      <a href="{% url 'admin:holdings_snapshot_change' snapshot.pk %}">{{ snapshot.as_of|date:"Y-m-d" }}</a>
      {% if snapshot.source %}({{ snapshot.source }}){% endif %}
      {{ snapshot.lines.count }} line{{ snapshot.lines.count|pluralize }}
    </li>
    {% endfor %}
  </ul>
  {% else %}
  <p>No statements yet.
    <a href="{% url 'admin:holdings_snapshot_add' %}?account={{ account.pk }}">Enter the first one.</a></p>
  {% endif %}

  {% if snapshots|length > 1 %}
  <h2>Change between two statements</h2>
  <form method="get" class="aligned">
    <div class="form-row">
      <label for="earlier">From</label>
      <select id="earlier" name="earlier">
        {% for snapshot in snapshots %}
        <option value="{{ snapshot.pk }}"{% if snapshot == pair.0 %} selected{% endif %}>{{ snapshot.as_of|date:"Y-m-d" }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="form-row">
      <label for="later">To</label>
      <select id="later" name="later">
        {% for snapshot in snapshots %}
        <option value="{{ snapshot.pk }}"{% if snapshot == pair.1 %} selected{% endif %}>{{ snapshot.as_of|date:"Y-m-d" }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="submit-row"><input type="submit" value="Compare" class="default"></div>
  </form>

  <p>From {{ pair.0.as_of|date:"Y-m-d" }} to {{ pair.1.as_of|date:"Y-m-d" }}. Shares and cost basis
    only; the app fetches no prices yet (chapter 08).</p>
  <table>
    <caption class="sr-only">Change per symbol between the two statements</caption>
    <thead>
      <tr>
        <th scope="col">Symbol</th>
        <th scope="col">Shares before</th>
        <th scope="col">Shares after</th>
        <th scope="col">Shares change</th>
        <th scope="col">Cost basis before</th>
        <th scope="col">Cost basis after</th>
        <th scope="col">Cost basis change</th>
      </tr>
    </thead>
    <tbody>
      {% for change in changes %}
      <tr>
        <th scope="row">{{ change.symbol }}</th>
        <td>{{ change.shares_before }}</td>
        <td>{{ change.shares_after }}</td>
        <td>{{ change.shares_change|signed }}</td>
        <td>{{ change.cost_before|default_if_none:"not shown" }}</td>
        <td>{{ change.cost_after|default_if_none:"not shown" }}</td>
        <td>{{ change.cost_change|signed }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% endif %}
</div>
{% endblock %}
```

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
