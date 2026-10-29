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

```python
"""Chapter 09 checkpoint: the watch list. A symbol the owner types is trimmed, upper-cased and
refused at the boundary; one row per account and symbol; added one or many at a time and removed
one at a time, from the account page, by the signed-in owner only; every watched symbol fetched by
the nightly pull; the latest close and its date beside each one, or the line that says prices
arrive after the pull; and public pages that still show no table and no link."""

from datetime import date, timedelta
from decimal import Decimal
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client
from django.utils import timezone
from pytest_django.fixtures import Settings

from invest_witus.prices.csv_file import PricePoint
from invest_witus.valuation import STALE_AFTER_DAYS
from invest_witus_site.holdings.models import Account, Holding, Snapshot, SnapshotLine
from invest_witus_site.prices import pull as pull_module
from invest_witus_site.prices.models import DailyClose
from invest_witus_site.prices.pull import symbol_universe, watch_symbols
from invest_witus_site.watchlist.models import (
    SYMBOL_MAX_LENGTH,
    ParsedSymbols,
    WatchItem,
    normalize_symbol,
    parse_symbols,
)

# Placeholder symbols only, as every chapter: INDEX and OTHER from chapter 02, FUNDX in the
# shape of a mutual fund ticker (five letters, the last an X), NONE for a symbol no source knows.
CHARACTER_RULE = "only letters, digits, a dot and a hyphen are allowed"
TOO_LONG = "TOOLONGSYMBOLX"  # fourteen characters
PUBLIC_PATHS = [
    "/",
    "/faq/",
    "/privacy/",
    "/terms/",
    "/contact/",
    "/waitlist/",
    "/waitlist/thanks/",
    "/auth/witus/login/",
]


# --- Fixtures: an owner, an account, a CSV folder ------------------------------------------


@pytest.fixture(autouse=True)
def no_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pull_module, "PAUSE_SECONDS", 0.0)


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("owner", email="owner@example.com")


@pytest.fixture
def someone(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("someone")


@pytest.fixture
def account(owner: User) -> Account:
    """An account with no statement yet: a watch list can start before the first statement."""
    return Account.objects.create(
        name="Practice", broker="Example Broker", kind="paper", owner=owner
    )


@pytest.fixture
def account_with_statement(account: Account) -> Account:
    """The same account holding one symbol and cash, as chapter 08's tests built it."""
    snapshot = Snapshot.objects.create(account=account, as_of=date(2026, 10, 25), source="test")
    for symbol, shares in (("INDEX", "2.5"), ("CASH", "500")):
        SnapshotLine.objects.create(snapshot=snapshot, symbol=symbol, shares=Decimal(shares))
    Holding.objects.filter(account=account, symbol="CASH").update(kind=Holding.Kind.CASH)
    return account


def write_csv(path: Path, rows: list[tuple[date, str]]) -> None:
    lines = ["date,close"] + [f"{day.isoformat()},{close}" for day, close in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture
def csv_folder(tmp_path: Path, settings: Settings) -> Path:
    """One file, for the fund-style symbol, dated yesterday so the pull's window finds it."""
    write_csv(tmp_path / "FUNDX.csv", [(timezone.localdate() - timedelta(days=1), "12.34")])
    settings.TIINGO_API_KEY = ""
    settings.PRICES_CSV_DIR = tmp_path
    return tmp_path


def page_url(account: Account) -> str:
    return f"/accounts/{account.pk}/"


def add_url(account: Account) -> str:
    return f"/accounts/{account.pk}/watch/add/"


def remove_url(account: Account, item: WatchItem) -> str:
    return f"/accounts/{account.pk}/watch/{item.pk}/remove/"


def watched(account: Account) -> list[str]:
    return list(WatchItem.objects.filter(account=account).values_list("symbol", flat=True))


class Tables(HTMLParser):
    """Every table on a page as its rows, each row a tuple of its cells' text; chapter 08's
    reader, with the tables kept apart so the holdings table and the watch list can be told
    from each other."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[tuple[str, ...]]] = []
        self._cells: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self.tables.append([])
        elif tag == "tr":
            self._cells = []
        elif tag in ("td", "th") and self._cells is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._cell is not None and self._cells is not None:
            self._cells.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._cells is not None:
            self.tables[-1].append(tuple(self._cells))
            self._cells = None


def tables_in(html: str) -> list[list[tuple[str, ...]]]:
    parser = Tables()
    parser.feed(html)
    return parser.tables


# --- The symbol rule ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("typed", "stored"),
    [("index", "INDEX"), (" fundx ", "FUNDX"), ("ab.c-d", "AB.C-D"), ("a" * 12, "A" * 12)],
)
def test_a_symbol_is_trimmed_and_upper_cased(typed: str, stored: str) -> None:
    assert normalize_symbol(typed) == stored


@pytest.mark.parametrize(
    ("typed", "reason"),
    [
        ("AB CD", CHARACTER_RULE),
        ("a$b", CHARACTER_RULE),
        ("INDEX!", CHARACTER_RULE),
        ("A" * 13, f"13 characters, the most is {SYMBOL_MAX_LENGTH}"),
        ("   ", "empty"),
    ],
)
def test_a_symbol_outside_the_rule_is_refused_with_the_reason(typed: str, reason: str) -> None:
    with pytest.raises(ValueError, match=reason):
        normalize_symbol(typed)
    assert SYMBOL_MAX_LENGTH == 12


@pytest.mark.django_db
def test_a_mutual_fund_style_ticker_is_a_symbol(account: Account) -> None:
    item = WatchItem(account=account, symbol="fundx", note="from the lesson")
    item.full_clean()  # the field's validator, as the admin form runs it
    item.save()
    assert watched(account) == ["FUNDX"]
    assert item.added_at is not None and str(item) == "FUNDX on Practice (Example Broker)"


@pytest.mark.django_db
def test_the_model_refuses_a_bad_symbol_before_the_row_is_written(account: Account) -> None:
    item = WatchItem(account=account, symbol="AB CD")
    with pytest.raises(ValidationError) as refused:
        item.full_clean()
    assert refused.value.message_dict == {"symbol": [CHARACTER_RULE]}
    with pytest.raises(ValueError, match=CHARACTER_RULE):
        item.save()
    assert WatchItem.objects.count() == 0


@pytest.mark.django_db
def test_a_symbol_is_on_an_accounts_list_once(account: Account, owner: User) -> None:
    WatchItem.objects.create(account=account, symbol="index")
    with pytest.raises(IntegrityError), transaction.atomic():
        WatchItem.objects.create(account=account, symbol="INDEX ")
    second = Account.objects.create(
        name="Retirement", broker="Other Broker", kind="retirement", owner=owner
    )
    WatchItem.objects.create(account=second, symbol="INDEX")
    assert list(WatchItem.objects.values_list("account__name", "symbol")) == [
        ("Practice", "INDEX"),
        ("Retirement", "INDEX"),
    ]


def test_typed_symbols_split_on_commas_and_spaces_each_once_with_the_refusals() -> None:
    parsed = parse_symbols(f"index, other FUNDX,,index\n a$b {TOO_LONG}")
    assert parsed.symbols == ["INDEX", "OTHER", "FUNDX"]
    assert parsed.refused == [
        ("A$B", CHARACTER_RULE),
        (TOO_LONG, f"14 characters, the most is {SYMBOL_MAX_LENGTH}"),
    ]
    assert parse_symbols(" , ,") == ParsedSymbols([], [])


@pytest.mark.django_db
def test_add_many_creates_the_new_ones_and_reports_the_rest(account: Account) -> None:
    WatchItem.objects.create(account=account, symbol="INDEX")
    report = WatchItem.add_many(account, ["OTHER", "INDEX", "FUNDX"], note="from the lesson")
    assert (report.added, report.existing) == (["OTHER", "FUNDX"], ["INDEX"])
    assert watched(account) == ["FUNDX", "INDEX", "OTHER"]
    assert WatchItem.objects.get(symbol="OTHER").note == "from the lesson"
    assert WatchItem.objects.get(symbol="INDEX").note == ""
    again = WatchItem.add_many(account, ["OTHER"])
    assert (again.added, again.existing) == ([], ["OTHER"])


# --- The owner adds and removes, on the page ---------------------------------------------


@pytest.mark.django_db
def test_the_owner_adds_one_symbol_from_the_account_page(
    client: Client, owner: User, account: Account
) -> None:
    client.force_login(owner)
    response = client.post(add_url(account), {"symbols": "index", "note": ""}, follow=True)
    assert response.redirect_chain == [(page_url(account), 302)]
    html = response.content.decode()
    assert "Added to the watch list: INDEX." in html
    assert watched(account) == ["INDEX"]
    assert "no price yet" in html and "Prices arrive after the nightly pull" in html


@pytest.mark.django_db
def test_adding_many_reports_added_existing_and_refused_in_one_submission(
    client: Client, owner: User, account: Account
) -> None:
    WatchItem.objects.create(account=account, symbol="INDEX")
    client.force_login(owner)
    data = {"symbols": f"INDEX, other FUNDX a$b {TOO_LONG}", "note": "from the lesson"}
    html = client.post(add_url(account), data, follow=True).content.decode()
    assert "Added to the watch list: OTHER, FUNDX." in html
    assert "Already on the watch list: INDEX." in html
    assert f"Refused: A$B ({CHARACTER_RULE}); {TOO_LONG} (14 characters, the most is 12)." in html
    assert watched(account) == ["FUNDX", "INDEX", "OTHER"]
    notes = dict(WatchItem.objects.filter(account=account).values_list("symbol", "note"))
    assert notes == {"FUNDX": "from the lesson", "INDEX": "", "OTHER": "from the lesson"}


@pytest.mark.django_db
def test_a_submission_with_nothing_valid_is_a_form_error_not_a_500(
    client: Client, owner: User, account: Account
) -> None:
    client.force_login(owner)
    response = client.post(add_url(account), {"symbols": f"a$b, {TOO_LONG}"})
    assert response.status_code == 200
    html = response.content.decode()
    assert (
        f"No symbol to add: A$B ({CHARACTER_RULE}); {TOO_LONG} (14 characters, the most is 12)."
        in html
    )
    assert "This field is required." in client.post(add_url(account), {}).content.decode()
    blank = client.post(add_url(account), {"symbols": " , "}).content.decode()
    assert "Enter at least one symbol." in blank
    assert WatchItem.objects.count() == 0


@pytest.mark.django_db
def test_the_owner_removes_a_symbol_and_its_closes_stay(
    client: Client, owner: User, account: Account
) -> None:
    item = WatchItem.objects.create(account=account, symbol="INDEX")
    DailyClose.upsert("INDEX", [PricePoint(date(2026, 10, 20), Decimal("100"))], "csv")
    client.force_login(owner)
    response = client.post(remove_url(account, item), follow=True)
    assert response.redirect_chain == [(page_url(account), 302)]
    assert "Removed INDEX from the watch list." in response.content.decode()
    assert watched(account) == []
    assert DailyClose.objects.filter(symbol="INDEX").count() == 1
    assert client.post(remove_url(account, item)).status_code == 404


@pytest.mark.django_db
def test_the_watch_routes_need_a_sign_in_and_a_post(
    client: Client, owner: User, account: Account
) -> None:
    item = WatchItem.objects.create(account=account, symbol="INDEX")
    for path in (add_url(account), remove_url(account, item)):
        response = client.post(path, {"symbols": "OTHER"})
        assert response.status_code == 302
        assert response["Location"] == f"/auth/witus/login/?next={path}"
    client.force_login(owner)
    assert client.get(add_url(account)).status_code == 405
    assert client.get(remove_url(account, item)).status_code == 405
    assert watched(account) == ["INDEX"]


@pytest.mark.django_db
def test_another_owner_gets_a_404_for_add_and_remove(
    client: Client, owner: User, someone: User, account: Account
) -> None:
    item = WatchItem.objects.create(account=account, symbol="INDEX")
    client.force_login(someone)
    assert client.post(add_url(account), {"symbols": "OTHER"}).status_code == 404
    assert client.post(remove_url(account, item)).status_code == 404
    # The owner's other account cannot reach this account's row either: the item is looked up
    # inside the account named in the URL.
    second = Account.objects.create(
        name="Retirement", broker="Other Broker", kind="retirement", owner=owner
    )
    client.force_login(owner)
    assert client.post(remove_url(second, item)).status_code == 404
    assert watched(account) == ["INDEX"]


@pytest.mark.django_db
def test_a_post_without_a_csrf_token_is_refused(owner: User, account: Account) -> None:
    strict = Client(enforce_csrf_checks=True)
    strict.force_login(owner)
    assert strict.post(add_url(account), {"symbols": "INDEX"}).status_code == 403
    assert watched(account) == []


# --- The pull picks them up ---------------------------------------------------------------


@pytest.mark.django_db
def test_watched_symbols_join_the_universe_and_cash_stays_out(
    account_with_statement: Account, owner: User
) -> None:
    WatchItem.add_many(account_with_statement, ["FUNDX", "INDEX"])
    second = Account.objects.create(
        name="Retirement", broker="Other Broker", kind="retirement", owner=owner
    )
    WatchItem.objects.create(account=second, symbol="OTHER")
    assert watch_symbols() == {"FUNDX", "INDEX", "OTHER"}
    assert symbol_universe() == ["FUNDX", "INDEX", "OTHER"]


@pytest.mark.django_db
def test_the_pull_fetches_a_watched_symbol_and_the_page_shows_its_close(
    client: Client, owner: User, account: Account, csv_folder: Path
) -> None:
    WatchItem.objects.create(account=account, symbol="FUNDX")
    out, err = StringIO(), StringIO()
    call_command("pull_prices", stdout=out, stderr=err)
    assert "1 symbol(s), 1 request(s)" in out.getvalue()
    assert "Inserted 1, updated 0, unchanged 0." in out.getvalue() and err.getvalue() == ""
    client.force_login(owner)
    html = client.get(page_url(account)).content.decode()
    yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
    assert tables_in(html) == [
        [
            ("Symbol", "Note", "Close", "As of", "Source", "Remove"),
            ("FUNDX", "", "12.34", yesterday, "csv", "Remove FUNDX"),
        ]
    ]
    assert "Prices arrive after the nightly pull" not in html


@pytest.mark.django_db
def test_the_command_says_when_nothing_is_held_or_watched(csv_folder: Path) -> None:
    out = StringIO()
    call_command("pull_prices", stdout=out)
    assert "Nothing to pull: no account holds or watches a symbol yet." in out.getvalue()


# --- The page -------------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_page_shows_each_close_with_its_date_or_says_prices_arrive_after_the_pull(
    client: Client, owner: User, account: Account
) -> None:
    today = timezone.localdate()
    WatchItem.add_many(account, ["FUNDX", "NONE", "OTHER"], note="from the lesson")
    DailyClose.upsert("FUNDX", [PricePoint(today - timedelta(days=1), Decimal("12.34"))], "csv")
    old = today - timedelta(days=STALE_AFTER_DAYS + 3)
    DailyClose.upsert("OTHER", [PricePoint(old, Decimal("20.005"))], "tiingo")
    client.force_login(owner)
    response = client.get(page_url(account))
    assert response.status_code == 200
    html = response.content.decode()
    assert tables_in(html) == [
        [
            ("Symbol", "Note", "Close", "As of", "Source", "Remove"),
            (
                "FUNDX",
                "from the lesson",
                "12.34",
                (today - timedelta(days=1)).isoformat(),
                "csv",
                "Remove FUNDX",
            ),
            ("NONE", "from the lesson", "no price yet", "Remove NONE"),
            (
                "OTHER",
                "from the lesson",
                "20.005",
                f"{old.isoformat()} stale",
                "tiingo",
                "Remove OTHER",
            ),
        ]
    ]
    assert "Prices arrive after the nightly pull: no close is stored yet for NONE." in html
    assert "No statement yet." in html
    assert "Information, not advice." in html


@pytest.mark.django_db
def test_the_page_with_a_statement_shows_the_holdings_first_and_the_watch_list_after(
    client: Client, owner: User, account_with_statement: Account
) -> None:
    WatchItem.objects.create(account=account_with_statement, symbol="FUNDX")
    client.force_login(owner)
    html = client.get(page_url(account_with_statement)).content.decode()
    holdings, watch = tables_in(html)
    assert holdings[0] == ("Symbol", "Shares", "Close", "As of", "Source", "Value")
    assert [row[0] for row in holdings[1:-1]] == ["CASH", "INDEX"]
    assert [row[0] for row in watch[1:]] == ["FUNDX"]
    assert html.index("Watch list") > html.index("Statement as of 2026-10-25")


@pytest.mark.django_db
def test_an_empty_watch_list_shows_the_form_and_no_table(
    client: Client, owner: User, account: Account
) -> None:
    client.force_login(owner)
    html = client.get(page_url(account)).content.decode()
    assert "Nothing on the watch list yet." in html
    assert tables_in(html) == []
    assert f'action="{add_url(account)}"' in html and 'name="symbols"' in html


@pytest.mark.django_db
@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_public_pages_show_no_table_and_do_not_link_the_account_pages(
    client: Client, account: Account, path: str
) -> None:
    WatchItem.objects.create(account=account, symbol="FUNDX")
    html = client.get(path).content.decode()
    assert "<table" not in html.lower()
    assert "/accounts/" not in html and "FUNDX" not in html


# --- The admin, for completeness ---------------------------------------------------------


@pytest.mark.django_db
def test_the_admin_lists_the_watch_list_and_refuses_a_bad_symbol_with_a_form_error(
    admin_client: Client, account: Account
) -> None:
    assert admin_client.get("/admin/watchlist/watchitem/").status_code == 200
    data = {"account": account.pk, "symbol": "AB CD", "note": ""}
    response = admin_client.post("/admin/watchlist/watchitem/add/", data)
    assert response.status_code == 200 and CHARACTER_RULE in response.content.decode()
    assert WatchItem.objects.count() == 0
    saved = admin_client.post("/admin/watchlist/watchitem/add/", {**data, "symbol": "fundx"})
    assert saved.status_code == 302
    assert watched(account) == ["FUNDX"]
```

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

```python
from django.apps import AppConfig


class WatchlistConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "invest_witus_site.watchlist"
    verbose_name = "Watch list"
```

Listing 09-4, Filename: `src/invest_witus_site/settings.py`:

```python
"""Django settings for Invest.WitUS.

Anything that differs between your laptop and a server comes from an environment variable, with a
safe default for the laptop. The names are listed in `.env.example`; values never go in git.
Chapter 06 added the server's side: the database from `DATABASE_URL`, a secret key the server
must set, the HTTPS cookie and proxy settings, the folder `collectstatic` fills, and logging a
server can show. Chapter 07 added the four names of Sign in with WitUS; chapter 08 the price
source and the cron secret, at the end. Chapter 09 adds one app and no names.
"""

import contextlib
import os
from pathlib import Path

import django_stubs_ext
from django.core.exceptions import ImproperlyConfigured

from invest_witus_site.database import database_from_url

# django-stubs describes Django's classes as generics (`ModelAdmin[WaitlistEntry]`) so pyright can
# check them, but Django itself does not accept `[...]` on those classes at runtime. This one call
# teaches them to, so the admin code can be written the way the type checker reads it.
django_stubs_ext.monkeypatch()

# The repository root. This file is src/invest_witus_site/settings.py, three levels down.
BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env_list(name: str) -> list[str]:
    """A comma-separated variable as a list, blanks dropped: "a, b," becomes ["a", "b"]."""
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


# Off unless DJANGO_DEBUG=1. Debug pages show settings and source code; never on a server.
DEBUG = os.environ.get("DJANGO_DEBUG") == "1"

# Vercel sets VERCEL=1 on its build machine and inside the function (its system environment
# variables). It is read for one question only: does a proxy that ends HTTPS sit in front?
ON_VERCEL = os.environ.get("VERCEL") == "1"
if DEBUG and ON_VERCEL:
    raise ImproperlyConfigured(
        "DJANGO_DEBUG=1 on Vercel: debug pages would show settings and code to anyone. Unset it."
    )


def secret_key(debug: bool) -> str:
    """DJANGO_SECRET_KEY, which a server must set. With debug off and no key, Django refuses to
    start here, with a message that says what to do, rather than sign sessions with a key anyone
    can read in git."""
    key = os.environ.get("DJANGO_SECRET_KEY", "")
    if key:
        return key
    if not debug:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY is not set and DJANGO_DEBUG is not 1. A server needs a secret key. "
            "Make one with: uv run python -c "
            '"from django.core.management.utils import get_random_secret_key as k; print(k())"'
        )
    # DEV-ONLY FALLBACK, reachable only with DJANGO_DEBUG=1 on a laptop. `check --deploy` warns
    # about the `django-insecure-` prefix, which is the point.
    return "django-insecure-dev-only-set-DJANGO_SECRET_KEY"


SECRET_KEY = secret_key(DEBUG)

# Host names the site answers to. The default answers a laptop and nothing else; production sets
# DJANGO_ALLOWED_HOSTS=invest.witus.online. The host names Vercel gives a deployment (its
# *.vercel.app URLs, and the production domain once one is added) come from Vercel's own
# variables, so a preview deployment answers without anyone listing its URL by hand.
VERCEL_HOSTS = [
    host
    for name in ("VERCEL_URL", "VERCEL_BRANCH_URL", "VERCEL_PROJECT_PRODUCTION_URL")
    if (host := os.environ.get(name))
]
# (dict.fromkeys keeps the order and drops a name listed twice.)
ALLOWED_HOSTS = list(
    dict.fromkeys((env_list("DJANGO_ALLOWED_HOSTS") or ["localhost", "127.0.0.1"]) + VERCEL_HOSTS)
)

# Origins (scheme and host) a form may be posted from. Django compares a POST's Origin header with
# the request's own origin; listing the site's HTTPS origin keeps that check passing even if the
# proxy header below were ever missing. Production sets https://invest.witus.online.
CSRF_TRUSTED_ORIGINS = list(
    dict.fromkeys(
        env_list("DJANGO_CSRF_TRUSTED_ORIGINS") + [f"https://{host}" for host in VERCEL_HOSTS]
    )
)

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
    "invest_witus_site.accounts",
    "invest_witus_site.prices",
    # The watch list (chapter 09): symbols the owner follows, kept per account, pulled nightly.
    "invest_witus_site.watchlist",
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
                "invest_witus_site.accounts.context_processors.identity",
            ],
        },
    },
]

# The WSGI application `runserver` loads. It names the bridge file at the repository root, not
# `invest_witus_site.wsgi`, because Vercel turns this value into a file path beside `manage.py`,
# and the bridge is what puts `src/` on the import path there (chapter 06).
WSGI_APPLICATION = "wsgi.application"


# The database. With no DATABASE_URL: SQLite in the folder git ignores, as in chapter 04. On
# Vercel the Neon integration sets DATABASE_URL (the pooled connection, for the app) and
# DATABASE_URL_UNPOOLED (the direct one, for migrations). `database_from_url` reads either shape.
# Vercel's connect dialog can put a prefix on every name the integration writes; the production
# project was connected with the prefix STORAGE (read from its variable list, 2026-10-28), so the
# prefixed names are accepted as well. An unprefixed name wins when both exist.
def first_env(*names: str) -> str | None:
    """The first of `names` that is set and not empty, or None."""
    for name in names:
        if value := os.environ.get(name):
            return value
    return None


DATA_DIR = BASE_DIR / "data" / "private"
POOLED_URL = first_env("DATABASE_URL", "STORAGE_DATABASE_URL")
DATABASE_URL = POOLED_URL or "sqlite:///data/private/invest-witus.sqlite3"
if not POOLED_URL:
    # A server's filesystem may be read-only; then /healthz/ reports the database as missing.
    with contextlib.suppress(OSError):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASES = {"default": database_from_url(DATABASE_URL, BASE_DIR)}
if unpooled := first_env("DATABASE_URL_UNPOOLED", "STORAGE_DATABASE_URL_UNPOOLED"):
    # Neon: schema changes take the direct connection, not the pooler. The owner runs
    # `manage.py migrate --database direct` and `createsuperuser --database direct` against it.
    DATABASES["direct"] = database_from_url(unpooled, BASE_DIR)

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
# Where `collectstatic` copies every app's static files into one folder (gitignored). Vercel sees
# STATIC_ROOT, runs collectstatic itself during the build, and serves that folder from its CDN at
# STATIC_URL; the function never serves a static file.
STATIC_ROOT = BASE_DIR / "staticfiles"

# HTTPS. Vercel ends TLS at its CDN and calls the function over plain HTTP with the header
# X-Forwarded-Proto: https. Django is told to trust that header only on Vercel, where the proxy
# sets it on every request (Django's warning: never where a client could send it to Django
# directly). Vercel also answers every plain-HTTP request with a 308 to HTTPS before Django sees
# it, and sends Strict-Transport-Security on custom domains, so the redirect below is a second
# line and the HSTS check (security.W004) is silenced on purpose.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if ON_VERCEL else None
SECURE_SSL_REDIRECT = ON_VERCEL
SILENCED_SYSTEM_CHECKS = ["security.W004"]
# Cookies marked Secure travel only over HTTPS. On whenever debug is off, so a server never sends
# the admin's session over plain HTTP. It is also why `runserver` with debug off cannot sign you
# in at http://127.0.0.1:8000/admin/: the browser keeps a Secure cookie off a plain connection.
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# Django's default logging prints to the console only while debug is on, so a server would show
# nothing. This sends warnings and errors (a 500's traceback, a refused host) to stderr, which
# Vercel collects as the function's logs. Nothing here logs a request body or a setting.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"stderr": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["stderr"], "level": "WARNING"},
}

# The FAQ, privacy and terms pages are Markdown files in the repo, so a wording change is a normal
# commit with a diff anyone can read.
SITE_PAGES_DIR = BASE_DIR / "docs" / "site"

# Vercel Web Analytics (chapter 06a): two script tags in the base template, rendered only when
# both hold: the app runs on Vercel, and the owner set VERCEL_ANALYTICS=1 on that environment. So
# production and preview can differ, and `runserver` never emits the tags (debug on Vercel is
# refused above, so a debug server never does either). The script's path belongs to the project:
# once Analytics is enabled, the project's Analytics page shows it, and that value goes in
# VERCEL_ANALYTICS_SCRIPT_PATH. FALLBACK, not a value read from any dashboard: the shared
# `/_vercel/insights/` route the quickstart names, with the file name from its snippet.
VERCEL_ANALYTICS_ENABLED = ON_VERCEL and os.environ.get("VERCEL_ANALYTICS") == "1"
VERCEL_ANALYTICS_SCRIPT_PATH = (
    os.environ.get("VERCEL_ANALYTICS_SCRIPT_PATH") or "/_vercel/insights/script.js"
)
if not VERCEL_ANALYTICS_SCRIPT_PATH.startswith("/"):
    raise ImproperlyConfigured(
        "VERCEL_ANALYTICS_SCRIPT_PATH must be a path on this site, starting with /, such as "
        "/<unique-path>/script.js from the Analytics page of the Vercel project."
    )

# Sign in with WitUS (chapter 07): OpenID Connect against the ecosystem's identity provider. The
# client is ON only when the secret is set; without it the sign-in route shows chapter 04's stub
# page and the site deploys as before. The issuer is what the provider asserts in its discovery
# document; the default is the ecosystem's accounts host as read on October 28, 2026, copied from
# that document, and the client refuses a document whose issuer differs. The client id follows the
# registry's `witus-<slug>` form. The secret is minted in the witus repo (task 07) and never
# written anywhere but the two Vercel projects' Environment Variables pages.
WITUS_OIDC_ISSUER = (os.environ.get("WITUS_OIDC_ISSUER") or "https://accounts.witus.online").rstrip(
    "/"
)
WITUS_OIDC_CLIENT_ID = os.environ.get("WITUS_OIDC_CLIENT_ID") or "witus-invest"
WITUS_OIDC_CLIENT_SECRET = os.environ.get("WITUS_OIDC_CLIENT_SECRET", "")
WITUS_OIDC_SCOPES = os.environ.get("WITUS_OIDC_SCOPES") or "openid email profile"
if not WITUS_OIDC_ISSUER.startswith("https://"):
    raise ImproperlyConfigured(
        "WITUS_OIDC_ISSUER must be the provider's https:// issuer, as its discovery document "
        "states it, such as https://accounts.witus.online"
    )
if "openid" not in WITUS_OIDC_SCOPES.split():
    raise ImproperlyConfigured(
        "WITUS_OIDC_SCOPES must include openid, such as: openid email profile"
    )

# Where `login_required` sends a visitor who is not signed in: the WitUS sign-in route, by name.
LOGIN_URL = "sign-in"

# Prices (chapter 08). The nightly pull writes one close per symbol per day into the app's own
# table. With TIINGO_API_KEY set, the closes come from Tiingo's end-of-day endpoint with the
# owner's own key; the free plan's license is "Internal Use Only" (its pricing page, read October
# 28, 2026), and the values are shown to the signed-in owner and to no one else. Without a key the
# pull reads `<SYMBOL>.csv` files from PRICES_CSV_DIR, chapter 02's format, which is what a laptop
# and a learner's copy use.
TIINGO_API_KEY = os.environ.get("TIINGO_API_KEY", "")
PRICES_CSV_DIR = Path(os.environ.get("PRICES_CSV_DIR") or DATA_DIR / "prices")
# What Vercel sends as `Authorization: Bearer <value>` when it calls the cron route (its docs,
# read October 28, 2026; at least 16 random characters). Empty means the route answers 503 and
# runs nothing: a deploy that forgot the variable fails closed.
CRON_SECRET = os.environ.get("CRON_SECRET", "")
```

One line in `INSTALLED_APPS`. Everything else is as chapter 08 left it; the docstring's last sentence says so.

Listing 09-5, Filename: `src/invest_witus_site/urls.py`:

```python
"""Where every URL of the site starts. Each app lists its own paths; this file includes them."""

from django.contrib import admin
from django.urls import include, path

from invest_witus_site import health

urlpatterns = [
    # The owner's back office. Every page under it requires a staff login (chapter 05).
    path("admin/", admin.site.urls),
    # Up, version, database: what a monitor asks after a deploy (chapter 06).
    path("healthz/", health.healthz, name="healthz"),
    # Sign in with WitUS: login, callback and logout (chapter 07).
    path("auth/witus/", include("invest_witus_site.accounts.urls")),
    # The signed-in owner's accounts, valued at the latest stored closes (chapter 08).
    path("accounts/", include("invest_witus_site.holdings.urls")),
    # The watch list's add and remove actions on an account page (chapter 09). The `pk` captured
    # here is passed on to the included views.
    path("accounts/<int:pk>/watch/", include("invest_witus_site.watchlist.urls")),
    # The nightly price pull, called by Vercel's cron with the bearer secret (chapter 08).
    path("api/cron/", include("invest_witus_site.prices.urls")),
    path("", include("invest_witus_site.pages.urls")),
]
```

Listing 09-6, Filename: `src/invest_witus_site/watchlist/urls.py`:

```python
"""The watch list's two actions. `invest_witus_site/urls.py` mounts this file under
`accounts/<int:pk>/watch/`, and the `pk` captured there reaches both views."""

from django.urls import path

from invest_witus_site.watchlist import views

urlpatterns = [
    path("add/", views.add, name="watch-add"),
    path("<int:item_pk>/remove/", views.remove, name="watch-remove"),
]
```

The include sits at `accounts/<int:pk>/watch/`, and Django passes the `pk` it captures there on to the included
views along with whatever they capture themselves, so `remove` receives both the account's `pk` and the item's.
The two names, `watch-add` and `watch-remove`, are what the template uses.

### 09.3 The model and the rule

Listing 09-7, Filename: `src/invest_witus_site/watchlist/models.py`:

```python
"""Symbols the owner follows in an account without holding them, one row per account and symbol.

A symbol here is user text: whatever was typed in the form or the admin. It is normalized
(trimmed, upper-cased) and checked against one rule before a row is written, and a symbol that
breaks the rule is refused with a reason, never stored and never a 500. The nightly pull
(`prices/pull.py`) fetches every watched symbol the way it fetches every held one, so the account
page can show the latest close beside each. There is no buy button here: a symbol reaches a plan
only when the owner adds it to the plan's universe (PRD, section 7.5).
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models

from invest_witus_site.holdings.models import Account

# The rule for a symbol, as the form and the admin apply it: after trimming and upper-casing,
# letters, digits, a dot and a hyphen only (a share class reads `AB.C` at one vendor and `AB-C`
# at another), one to twelve characters. A mutual fund ticker is five letters ending in X and
# fits. The column itself is as wide as the other symbol columns (chapters 05 and 08), so a
# join never truncates; the rule is the boundary's, not the database's.
SYMBOL_MAX_LENGTH = 12
SYMBOL = re.compile(r"[A-Z0-9.-]+")
CHARACTER_RULE = "only letters, digits, a dot and a hyphen are allowed"


def normalize_symbol(text: str) -> str:
    """The symbol as it is stored, or a `ValueError` whose message is the reason it is not one."""
    symbol = text.strip().upper()
    if not symbol:
        raise ValueError("empty")
    if len(symbol) > SYMBOL_MAX_LENGTH:
        raise ValueError(f"{len(symbol)} characters, the most is {SYMBOL_MAX_LENGTH}")
    if SYMBOL.fullmatch(symbol) is None:
        raise ValueError(CHARACTER_RULE)
    return symbol


def validate_symbol(value: str) -> None:
    """The same rule as a Django validator, so the admin form refuses a bad symbol with a
    message beside the field instead of an error page."""
    try:
        normalize_symbol(value)
    except ValueError as error:
        raise ValidationError(str(error)) from None


@dataclass(frozen=True, slots=True)
class ParsedSymbols:
    """What a typed list came to: each valid symbol once, in the order typed, and each refusal
    with its reason, so the page can report both."""

    symbols: list[str]
    refused: list[tuple[str, str]]


def parse_symbols(text: str) -> ParsedSymbols:
    """`"index, other FUNDX"` becomes `["INDEX", "OTHER", "FUNDX"]`. Commas and any whitespace
    separate; a symbol typed twice is kept once; a token outside the rule goes to `refused`."""
    symbols: list[str] = []
    refused: list[tuple[str, str]] = []
    for token in text.replace(",", " ").split():
        try:
            symbol = normalize_symbol(token)
        except ValueError as error:
            refused.append((token.upper(), str(error)))
            continue
        if symbol not in symbols:
            symbols.append(symbol)
    return ParsedSymbols(symbols, refused)


@dataclass(frozen=True, slots=True)
class AddReport:
    """What `WatchItem.add_many` did: the symbols it added, and the ones already on the list."""

    added: list[str]
    existing: list[str]


class WatchItem(models.Model):
    """One symbol on one account's watch list, with an optional note on why it is there."""

    account: models.ForeignKey[Account, Account] = models.ForeignKey(
        Account, on_delete=models.CASCADE
    )
    symbol: models.CharField[str, str] = models.CharField(
        max_length=20,
        validators=[validate_symbol],
        help_text="Letters, digits, a dot and a hyphen; up to twelve characters.",
    )
    note: models.CharField[str, str] = models.CharField(
        max_length=200, blank=True, default="", help_text="Why you are watching it. Optional."
    )
    added_at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["account", "symbol"]
        constraints = [
            models.UniqueConstraint(
                fields=["account", "symbol"], name="watch_symbol_once_per_account"
            ),
        ]
        verbose_name = "watch list item"
        verbose_name_plural = "watch list items"

    def __str__(self) -> str:
        return f"{self.symbol} on {self.account}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Normalize before the row is written. A symbol outside the rule raises here, so a
        caller that skipped the form or the validator cannot store one."""
        self.symbol = normalize_symbol(self.symbol)
        super().save(*args, **kwargs)

    @classmethod
    def add_many(cls, account: Account, symbols: list[str], note: str = "") -> AddReport:
        """Add each symbol that is not on the list yet; report the rest as existing. Each symbol
        goes through `get_or_create`, so two submissions of the same symbol at the same moment
        cannot both insert it. The note goes on the new rows only."""
        added: list[str] = []
        existing: list[str] = []
        for symbol in symbols:
            _, created = cls.objects.get_or_create(
                account=account, symbol=normalize_symbol(symbol), defaults={"note": note}
            )
            (added if created else existing).append(symbol)
        return AddReport(added, existing)
```

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

```python
# Generated by Django 5.2.18 on 2026-10-29 00:39

import django.db.models.deletion
from django.db import migrations, models

import invest_witus_site.watchlist.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("holdings", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="WatchItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "symbol",
                    models.CharField(
                        help_text="Letters, digits, a dot and a hyphen; up to twelve characters.",
                        max_length=20,
                        validators=[invest_witus_site.watchlist.models.validate_symbol],
                    ),
                ),
                (
                    "note",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Why you are watching it. Optional.",
                        max_length=200,
                    ),
                ),
                ("added_at", models.DateTimeField(auto_now_add=True)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="holdings.account"
                    ),
                ),
            ],
            options={
                "verbose_name": "watch list item",
                "verbose_name_plural": "watch list items",
                "ordering": ["account", "symbol"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("account", "symbol"), name="watch_symbol_once_per_account"
                    )
                ],
            },
        ),
    ]
```

The migration depends on the holdings app's first, because of the foreign key, and it records the validator by
its import path: the database never runs it, but a migration that adds the same field later must know it.

Listing 09-10, Filename: `src/invest_witus_site/watchlist/admin.py`:

```python
"""The watch lists in the admin, for completeness: the owner's page is where they are kept."""

from django.contrib import admin

from invest_witus_site.watchlist.models import WatchItem


@admin.register(WatchItem)
class WatchItemAdmin(admin.ModelAdmin[WatchItem]):
    list_display = ("symbol", "account", "note", "added_at")
    list_filter = ("account",)
    search_fields = ("symbol", "note")
    readonly_fields = ("added_at",)
```

The admin page exists for completeness. The watch list is the owner's to keep on the account page; the admin is
where the owner can see every account's list at once, filter by account, and fix a row.

### 09.4 The form

Listing 09-11, Filename: `src/invest_witus_site/watchlist/forms.py`:

```python
"""The add form: one or many symbols in one box, and an optional note for all of them."""

from django import forms
from django.core.exceptions import ValidationError

from invest_witus_site.watchlist.models import ParsedSymbols, parse_symbols


class WatchForm(forms.Form):
    symbols = forms.CharField(
        label="Symbols",
        max_length=400,
        widget=forms.TextInput(
            attrs={"autocomplete": "off", "autocapitalize": "characters", "spellcheck": "false"}
        ),
    )
    note = forms.CharField(label="Note", required=False, max_length=200)

    def clean_symbols(self) -> ParsedSymbols:
        """The box as a parsed list. It is a form error only when nothing in it can be added;
        a refused token beside a valid one is reported after the valid one is added."""
        parsed = parse_symbols(self.cleaned_data["symbols"])
        if parsed.symbols:
            return parsed
        if parsed.refused:
            reasons = "; ".join(f"{token} ({reason})" for token, reason in parsed.refused)
            raise ValidationError(f"No symbol to add: {reasons}.")
        raise ValidationError("Enter at least one symbol.")
```

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

```python
"""Two POST views on the signed-in owner's account page: add one or many symbols, remove one.

Both check ownership the way chapter 08's pages do: the account comes from
`get_object_or_404(Account, pk=pk, owner=request.user)`, so another owner's account is a 404.
Both finish with a redirect to the account page (Post/Redirect/Get, as chapter 04's waitlist),
carrying their report in Django's messages, which the base template prints once.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from invest_witus_site.holdings.models import Account
from invest_witus_site.holdings.views import account_page
from invest_witus_site.watchlist.forms import WatchForm
from invest_witus_site.watchlist.models import WatchItem


@login_required
@require_POST
def add(request: HttpRequest, pk: int) -> HttpResponse:
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    form = WatchForm(request.POST)
    if not form.is_valid():
        # Nothing could be added: the account page again, with the reason beside the box.
        return account_page(request, account, form)
    parsed = form.cleaned_data["symbols"]
    report = WatchItem.add_many(account, parsed.symbols, form.cleaned_data["note"])
    if report.added:
        messages.success(request, f"Added to the watch list: {', '.join(report.added)}.")
    if report.existing:
        messages.info(request, f"Already on the watch list: {', '.join(report.existing)}.")
    if parsed.refused:
        reasons = "; ".join(f"{token} ({reason})" for token, reason in parsed.refused)
        messages.error(request, f"Refused: {reasons}.")
    return redirect("account-detail", pk=account.pk)


@login_required
@require_POST
def remove(request: HttpRequest, pk: int, item_pk: int) -> HttpResponse:
    """The row is looked up inside the account named in the URL, so an id from another
    account, the owner's own or anyone else's, is a 404. Stored closes are not touched: the
    table of prices is the pull's, and a symbol may be watched again or held tomorrow."""
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    item = get_object_or_404(WatchItem, pk=item_pk, account=account)
    item.delete()
    messages.success(request, f"Removed {item.symbol} from the watch list.")
    return redirect("account-detail", pk=account.pk)
```

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

```python
"""The nightly pull: which symbols, which days, one request per symbol, and the counts.

Written to be run twice without harm, because Vercel's Hobby cron may fire anywhere inside its
hour, does not retry a failed run, and can occasionally deliver a run twice or not at all
(Vercel's cron docs, read October 28, 2026). Asking for the last `DAYS_BACK` days every night
means one missed night is filled in by the next, and `DailyClose.upsert` means a repeated night
writes nothing.
"""

import logging
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

from invest_witus_site.holdings.models import Holding
from invest_witus_site.prices.models import DailyClose, UpsertCount
from invest_witus_site.prices.sources import PriceSource, PriceSourceError
from invest_witus_site.watchlist.models import WatchItem

log = logging.getLogger(__name__)

# How many days back a run asks for. A week of closes is seven small rows per symbol, and it
# makes any single missed night harmless.
DAYS_BACK = 7
# The free plan's hourly limit, from Tiingo's pricing page (read October 28, 2026): 50 requests
# an hour, 1,000 a day, 500 unique symbols a month. One request per symbol per run, and a run
# never makes more than this many; what is left is listed as skipped for the next run.
REQUESTS_PER_RUN = 50
# The pause between two symbols. Tiingo's overview (read the same day) counts requests per hour
# and per day and says "We do not rate limit to minute or second", so this is a courtesy to the
# vendor, not a documented requirement; the budget above is the real guard.
PAUSE_SECONDS = 1.0


def watch_symbols() -> set[str]:
    """Every symbol on any account's watch list (chapter 09). A watched symbol with no close yet
    is exactly what the next run should fetch, so there is no filter here."""
    return set(WatchItem.objects.values_list("symbol", flat=True))


def symbol_universe() -> list[str]:
    """Every symbol an account holds (cash has no price), plus the watch list's, each once."""
    held = Holding.objects.exclude(kind=Holding.Kind.CASH).values_list("symbol", flat=True)
    return sorted(set(held) | watch_symbols())


@dataclass
class PullResult:
    """What one run did, for the command's output and the cron route's JSON."""

    source: str
    since: date
    until: date
    symbols: list[str]
    requests: int = 0
    counts: UpsertCount = UpsertCount()
    failed: dict[str, str] = field(default_factory=dict[str, str])
    skipped: list[str] = field(default_factory=list[str])

    def as_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "since": self.since.isoformat(),
            "until": self.until.isoformat(),
            "symbols": self.symbols,
            "requests": self.requests,
            "inserted": self.counts.inserted,
            "updated": self.counts.updated,
            "unchanged": self.counts.unchanged,
            "failed": self.failed,
            "skipped": self.skipped,
        }


def pull(
    source: PriceSource,
    symbols: Iterable[str],
    since: date,
    until: date,
    pause: float | None = None,
    budget: int = REQUESTS_PER_RUN,
) -> PullResult:
    """One request per symbol, in order; a refusal is recorded and the next symbol is tried. A
    rate limit stops the run, and the symbols not reached are listed as skipped."""
    if pause is None:
        pause = PAUSE_SECONDS
    result = PullResult(source.name, since, until, list(symbols))
    for index, symbol in enumerate(result.symbols):
        if result.requests >= budget:
            result.skipped.append(symbol)
            continue
        if result.requests > 0 and pause > 0:
            time.sleep(pause)
        result.requests += 1
        try:
            points = source.closes(symbol, since, until)
        except PriceSourceError as error:
            result.failed[symbol] = error.problem
            log.warning("pull_prices: %s", error)
            if error.retry_later:
                result.skipped.extend(result.symbols[index + 1 :])
                break
            continue
        counts = DailyClose.upsert(symbol, points, source.name)
        result.counts = result.counts + counts
        log.info("pull_prices: %s, %d day(s) from %s: %s", symbol, len(points), source.name, counts)
    return result
```

`watch_symbols()` is the hook chapter 08 left, filled in: every symbol on any account's list, as a set, and
`symbol_universe()` unions it with the held symbols as it already did. Nothing about the budget, the pause or
the 429 changes: a watched symbol is one more request in the same run, inside the same fifty. A watched symbol
the vendor does not know is recorded in `failed` and reads "no price yet" on the page, which is the PRD's
"clear message instead of a zero price".

Listing 09-14, Filename: `src/invest_witus_site/prices/portfolio.py`:

```python
"""What the account page shows, priced: a statement valued at the latest stored closes, and
(chapter 09) the watch list with the latest close beside each symbol. The joins between the
account's symbols and the prices table live here, so the holdings views stay thin."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from invest_witus.valuation import Quote, Valuation, is_stale, value_positions
from invest_witus_site.holdings.models import Account, Holding, Snapshot
from invest_witus_site.prices.models import DailyClose
from invest_witus_site.watchlist.models import WatchItem

# A cash line is worth its amount. It is never pulled: no vendor has a close for "CASH".
CASH_CLOSE = Decimal("1")


def value_snapshot(snapshot: Snapshot, today: date) -> Valuation:
    """Each line of the statement at its symbol's newest close; cash at face, dated by the
    statement; a symbol with no close yet is listed, not valued."""
    positions = snapshot.positions()
    kinds: dict[str, str] = dict(
        Holding.objects.filter(account=snapshot.account).values_list("symbol", "kind")
    )
    cash = {position.symbol for position in positions if kinds.get(position.symbol) == "cash"}
    quotes = DailyClose.latest_for(
        position.symbol for position in positions if position.symbol not in cash
    )
    for symbol in cash:
        quotes[symbol] = Quote(close=CASH_CLOSE, as_of=snapshot.as_of, source="statement")
    return value_positions(positions, quotes, today)


@dataclass(frozen=True, slots=True)
class WatchedSymbol:
    """One watch list row with its newest close, or `None` while the pull has not stored one."""

    item: WatchItem
    quote: Quote | None
    stale: bool


@dataclass(frozen=True, slots=True)
class WatchList:
    """The account's rows, by symbol, and the symbols that have no close yet."""

    rows: list[WatchedSymbol]
    unpriced: list[str]


def watch_list(account: Account, today: date) -> WatchList:
    """Each watched symbol with the newest close the app has stored for it. A watched symbol is
    never valued: there are no shares to multiply, so the close and its date are the whole row."""
    items = list(WatchItem.objects.filter(account=account))
    quotes = DailyClose.latest_for(item.symbol for item in items)
    rows: list[WatchedSymbol] = []
    for item in items:
        quote = quotes.get(item.symbol)
        rows.append(WatchedSymbol(item, quote, quote is not None and is_stale(quote, today)))
    return WatchList(rows, [row.item.symbol for row in rows if row.quote is None])
```

`watch_list` is the join for the new section, beside `value_snapshot`: the account's items in symbol order, the
newest close per symbol in chapter 08's two queries, and a row per item with its quote or `None`. A watched
symbol is never valued, since there are no shares to multiply; the close and its date are the row.

Listing 09-15, Filename: `src/invest_witus/valuation.py`:

```python
"""What a statement's lines are worth at the latest stored close, and when a close is too old.

Pure functions over plain values, like `holdings.py`: no database and no vendor. The Django view
(chapter 08) hands in the lines as `Position`s and one `Quote` per symbol, and prints what comes
back. A symbol with no quote is not valued and is listed, never shown as zero.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from invest_witus.holdings import Position
from invest_witus.money import to_money

# A close older than this many calendar days is marked stale. Five covers a weekend, a market
# holiday and one missed nightly run; anything older deserves a look at the cron's log.
STALE_AFTER_DAYS = 5
ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class Quote:
    """One close for one symbol: the number, the day it is for, and where it came from."""

    close: Decimal
    as_of: date
    source: str


@dataclass(frozen=True, slots=True)
class ValuedLine:
    """One statement line with the quote used, or `None` and no value when there is no close."""

    symbol: str
    shares: Decimal
    quote: Quote | None
    value: Decimal | None
    stale: bool


@dataclass(frozen=True, slots=True)
class Valuation:
    """Every line, the total of the priced ones, and the symbols that have no close yet."""

    lines: list[ValuedLine]
    total: Decimal
    unpriced: list[str]


def is_stale(quote: Quote, today: date) -> bool:
    """A calendar test: more than `STALE_AFTER_DAYS` days between the close and today. Shared by
    the valued statement line and, from chapter 09, the watch list."""
    return (today - quote.as_of).days > STALE_AFTER_DAYS


def value_line(position: Position, quote: Quote | None, today: date) -> ValuedLine:
    """Shares times close, rounded to cents half up (chapter 01's `to_money`). Both factors are
    Decimals; a float in either place fails here with a TypeError instead of a wrong number."""
    if quote is None:
        return ValuedLine(position.symbol, position.shares, None, None, False)
    value = to_money(position.shares * quote.close)
    return ValuedLine(position.symbol, position.shares, quote, value, is_stale(quote, today))


def value_positions(
    positions: Iterable[Position], quotes: Mapping[str, Quote], today: date
) -> Valuation:
    """Value each position with its symbol's quote. The total adds the priced lines only."""
    lines = [value_line(position, quotes.get(position.symbol), today) for position in positions]
    total = to_money(sum((line.value for line in lines if line.value is not None), ZERO))
    unpriced = [line.symbol for line in lines if line.quote is None]
    return Valuation(lines, total, unpriced)
```

One function pulled out, `is_stale`, so the statement line and the watch row share one definition of "too
old". The arithmetic is unchanged and chapter 08's tests still pass against it.

Listing 09-16, Filename: `src/invest_witus_site/prices/management/commands/pull_prices.py`:

```python
"""`manage.py pull_prices [--since YYYY-MM-DD] [--symbols A,B]`: the nightly pull, by hand.

The same code the cron route runs, for a laptop (against the CSV folder) and for the owner's
shell (against Tiingo, with the key in the environment). Running it twice writes nothing twice.
"""

from datetime import date, timedelta
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.utils import timezone

from invest_witus_site.prices.pull import DAYS_BACK, pull, symbol_universe
from invest_witus_site.prices.sources import source_from_settings


def parse_symbols(text: str) -> list[str]:
    """`"index, other"` becomes `["INDEX", "OTHER"]`, each once, in the order given."""
    return list(dict.fromkeys(part.strip().upper() for part in text.split(",") if part.strip()))


class Command(BaseCommand):
    help = (
        "Store end-of-day closes for every held or watched symbol, or for --symbols, since a date."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--since",
            type=date.fromisoformat,
            help=f"First day to ask for, YYYY-MM-DD. Default: {DAYS_BACK} days ago.",
        )
        parser.add_argument(
            "--symbols",
            help="Comma-separated symbols instead of every held symbol, such as INDEX,OTHER.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        today = timezone.localdate()
        since: date = options["since"] or today - timedelta(days=DAYS_BACK)
        if since > today:
            raise CommandError(f"--since {since} is after today ({today})")
        symbols = parse_symbols(options["symbols"]) if options["symbols"] else symbol_universe()
        if not symbols:
            self.stdout.write("Nothing to pull: no account holds or watches a symbol yet.")
            return
        result = pull(source_from_settings(), symbols, since, today)
        self.stdout.write(
            f"Source {result.source}, {result.since} to {result.until}, "
            f"{len(result.symbols)} symbol(s), {result.requests} request(s)."
        )
        self.stdout.write(f"{result.counts}.".capitalize())
        for symbol, problem in result.failed.items():
            self.stderr.write(f"Failed {symbol}: {problem}")
        if result.skipped:
            self.stderr.write(f"Skipped, for the next run: {', '.join(result.skipped)}")
```

Two strings changed in the command, the help line and the "Nothing to pull" sentence, because the universe now
has two sources.

### 09.7 The page

Listing 09-17, Filename: `src/invest_witus_site/holdings/views.py`:

```python
"""The owner's accounts, outside the admin: a list, and one account valued at the latest closes
with its watch list underneath (chapter 09).

Both views sit behind `login_required`, which sends a visitor to `LOGIN_URL` (the WitUS sign-in,
chapter 07), and both read only the accounts the signed-in user owns. Someone else's account is a
404, not a 403: the page does not say whether the id exists.
"""

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from invest_witus_site.holdings.models import Account
from invest_witus_site.prices.portfolio import value_snapshot, watch_list
from invest_witus_site.watchlist.forms import WatchForm


@login_required
def account_list(request: HttpRequest) -> HttpResponse:
    accounts = Account.objects.filter(owner=request.user)
    return render(request, "holdings/account_list.html", {"accounts": accounts})


@login_required
def account_detail(request: HttpRequest, pk: int) -> HttpResponse:
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    return account_page(request, account)


def account_page(
    request: HttpRequest, account: Account, watch_form: WatchForm | None = None
) -> HttpResponse:
    """The account page: the latest statement valued, then the watch list with its add form.
    The ownership check is the caller's. Chapter 09's add view renders the page again through
    this function, with the bound form, when nothing in a submission could be added."""
    today = timezone.localdate()
    snapshot = account.latest_snapshot()
    valuation = value_snapshot(snapshot, today) if snapshot is not None else None
    context = {
        "account": account,
        "snapshot": snapshot,
        "valuation": valuation,
        "watch": watch_list(account, today),
        "watch_form": watch_form or WatchForm(),
    }
    return render(request, "holdings/account_detail.html", context)
```

`account_detail` became two functions. `account_page` builds the context and renders, with an optional bound
form, and does no ownership check of its own: that stays with the two callers that have the request's user, the
detail view here and the add view in the watchlist app. The holdings app imports the form; the watchlist app
imports this function; the line in decision 1 holds.

Listing 09-18, Filename: `src/invest_witus_site/holdings/templates/holdings/account_detail.html`:

```html
{% extends "pages/base.html" %}
{% load holdings_extras %}
{% block title %}{{ account.name }}: Invest.WitUS{% endblock %}
{% block content %}
<section class="container" aria-labelledby="account-heading">
  <p class="eyebrow">Your account</p>
  <h1 id="account-heading">{{ account.name }} <span class="muted">({{ account.broker }})</span></h1>
  {% if snapshot %}
  <p>Statement as of {{ snapshot.as_of|date:"Y-m-d" }}{% if snapshot.source %} ({{ snapshot.source }}){% endif %}. Each line is valued at the latest close the app has stored for its symbol, with that close's date and source beside it; a close older than five days is marked stale. Information, not advice.</p>
  <table class="holdings">
    <caption class="sr-only">Holdings on the latest statement, valued at the latest stored close</caption>
    <thead>
      <tr>
        <th scope="col">Symbol</th>
        <th scope="col" class="num">Shares</th>
        <th scope="col" class="num">Close</th>
        <th scope="col">As of</th>
        <th scope="col">Source</th>
        <th scope="col" class="num">Value</th>
      </tr>
    </thead>
    <tbody>
      {% for line in valuation.lines %}
      <tr>
        <th scope="row">{{ line.symbol }}</th>
        <td class="num">{{ line.shares|plain_number }}</td>
        {% if line.quote %}
        <td class="num">{{ line.quote.close|plain_number }}</td>
        <td>{{ line.quote.as_of|date:"Y-m-d" }}{% if line.stale %} <span class="stale">stale</span>{% endif %}</td>
        <td>{{ line.quote.source }}</td>
        <td class="num">{{ line.value|plain_number }}</td>
        {% else %}
        <td class="muted" colspan="4">no price yet</td>
        {% endif %}
      </tr>
      {% endfor %}
    </tbody>
    <tfoot>
      <tr>
        <th scope="row" colspan="5">Total of the priced lines</th>
        <td class="num">{{ valuation.total|plain_number }}</td>
      </tr>
    </tfoot>
  </table>
  {% if valuation.unpriced %}
  <p class="muted">No price yet for {{ valuation.unpriced|join:", " }}: the nightly pull has not stored a close for {{ valuation.unpriced|length|pluralize:"it,them" }}. A symbol the price source does not know stays unpriced; the pull's log names it.</p>
  {% endif %}
  {% else %}
  <p>No statement yet.{% if user.is_staff %} <a href="{% url 'admin:holdings_snapshot_add' %}?account={{ account.pk }}">Enter the first one in the admin.</a>{% endif %}</p>
  {% endif %}
  {# The watch list (chapter 09): the symbols followed here, the latest close beside each, the add form. #}
  {% include "watchlist/_section.html" %}
  <p><a href="{% url 'account-list' %}">All accounts</a></p>
</section>
{% endblock %}
```

Listing 09-19, Filename: `src/invest_witus_site/watchlist/templates/watchlist/_section.html`:

```html
{% load holdings_extras %}
{# The watch list section of the account page (chapter 09). Included by holdings/account_detail.html #}
{# with `account`, `watch` (the rows with their quotes) and `watch_form`. #}
<section class="watch" aria-labelledby="watch-heading">
  <h2 id="watch-heading">Watch list</h2>
  {% if watch.rows %}
  <table class="holdings">
    <caption class="sr-only">Symbols you follow in this account, with the latest stored close</caption>
    <thead>
      <tr>
        <th scope="col">Symbol</th>
        <th scope="col">Note</th>
        <th scope="col" class="num">Close</th>
        <th scope="col">As of</th>
        <th scope="col">Source</th>
        <th scope="col"><span class="sr-only">Remove</span></th>
      </tr>
    </thead>
    <tbody>
      {% for row in watch.rows %}
      <tr>
        <th scope="row">{{ row.item.symbol }}</th>
        <td>{{ row.item.note }}</td>
        {% if row.quote %}
        <td class="num">{{ row.quote.close|plain_number }}</td>
        <td>{{ row.quote.as_of|date:"Y-m-d" }}{% if row.stale %} <span class="stale">stale</span>{% endif %}</td>
        <td>{{ row.quote.source }}</td>
        {% else %}
        <td class="muted" colspan="3">no price yet</td>
        {% endif %}
        <td>
          <form method="post" action="{% url 'watch-remove' account.pk row.item.pk %}">
            {% csrf_token %}
            <button type="submit" class="link-button">Remove <span class="sr-only">{{ row.item.symbol }}</span></button>
          </form>
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% if watch.unpriced %}
  <p class="muted">Prices arrive after the nightly pull: no close is stored yet for {{ watch.unpriced|join:", " }}. A symbol the price source does not know stays unpriced; the pull's log names it.</p>
  {% endif %}
  {% else %}
  <p>Nothing on the watch list yet.</p>
  {% endif %}
  <form method="post" action="{% url 'watch-add' account.pk %}" class="watch-form" novalidate>
    {% csrf_token %}
    <div class="field">
      <label for="{{ watch_form.symbols.id_for_label }}">Symbols</label>
      {{ watch_form.symbols }}
      {{ watch_form.symbols.errors }}
      <p class="small muted">One or more, separated by commas or spaces. Letters, digits, a dot and a hyphen; up to twelve characters each.</p>
    </div>
    <div class="field">
      <label for="{{ watch_form.note.id_for_label }}">Note (optional)</label>
      {{ watch_form.note }}
      {{ watch_form.note.errors }}
    </div>
    <button type="submit">Add to the watch list</button>
  </form>
  <p class="small muted">Watching a symbol places no order and recommends nothing. A symbol reaches a plan only when you add it to the plan's universe. Information, not advice.</p>
</section>
```

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

```html
{% load static %}<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Invest.WitUS{% endblock %}</title>
  <meta name="description" content="Pick a taught investing method and stay with it, on paper first. A learning tool, not advice.">
  {# Favicons: gemini/witus/public/brand/04-orbit-type/, copied into static/brand/witus/. #}
  <link rel="icon" href="{% static 'brand/witus/favicon.svg' %}" type="image/svg+xml">
  <link rel="icon" href="{% static 'brand/witus/favicon-32.png' %}" sizes="32x32" type="image/png">
  <link rel="icon" href="{% static 'brand/witus/favicon-16.png' %}" sizes="16x16" type="image/png">
  <link rel="apple-touch-icon" href="{% static 'brand/witus/favicon-180.png' %}">
  <link rel="stylesheet" href="{% static 'pages/site.css' %}">
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
  {% include "pages/_header.html" %}
  <main id="main" tabindex="-1">
    {% if messages %}
    {# One-time notes from the view that handled a form, through Django's messages framework (chapter 09). #}
    {# Printed here, once, on whatever page the redirect lands on; iterating them is what clears them. #}
    <section class="container" aria-label="Notices">
      <ul class="messages">
        {% for message in messages %}
        <li class="message {{ message.tags }}">{{ message }}</li>
        {% endfor %}
      </ul>
    </section>
    {% endif %}
    {% block content %}{% endblock %}
  </main>
  {% include "pages/_footer.html" %}
  {% if vercel_analytics_enabled %}
  {# Vercel Web Analytics (chapter 06a): the snippet from Vercel's quickstart for plain HTML sites, read #}
  {# October 28, 2026. The first tag queues calls until the deferred script loads. The path is the setting #}
  {# VERCEL_ANALYTICS_SCRIPT_PATH; with it unset, the FALLBACK is the shared /_vercel/insights/ route the #}
  {# quickstart names, not a value read from the dashboard. Rendered only with VERCEL=1 and VERCEL_ANALYTICS=1. #}
  <script>
    window.va = window.va || function () { (window.vaq = window.vaq || []).push(arguments); };
  </script>
  <script defer src="{{ vercel_analytics_script_path }}"></script>
  {% endif %}
</body>
</html>
```

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
