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


def history_cell(symbol: str) -> str:
    """The text of a row's History cell: 2026-10-29's Get history form (decision 116), after the
    row's checkbox for Fetch history for selected (decision 125)."""
    choices = "1 year5 years10 yearsAll available"
    select = f"Select {symbol} for Fetch history for selected"
    return f"{select} How far back to fetch {symbol} {choices} Get history for {symbol}"


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
            # The History column is 2026-10-29's Get history form, decision 116.
            ("Symbol", "Note", "Close", "As of", "Source", "History", "Remove"),
            ("FUNDX", "", "$12.34", yesterday, "csv", history_cell("FUNDX"), "Remove FUNDX"),
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
            ("Symbol", "Note", "Close", "As of", "Source", "History", "Remove"),
            (
                "FUNDX",
                "from the lesson",
                "$12.34",
                (today - timedelta(days=1)).isoformat(),
                "csv",
                history_cell("FUNDX"),
                "Remove FUNDX",
            ),
            ("NONE", "from the lesson", "no price yet", history_cell("NONE"), "Remove NONE"),
            (
                "OTHER",
                "from the lesson",
                "$20.01",
                f"{old.isoformat()} stale",
                "tiingo",
                history_cell("OTHER"),
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
