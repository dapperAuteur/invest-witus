"""Chapter 05 checkpoint: the admin as the owner's back office, the waitlist list, accounts and
statement snapshots in exact decimals."""

from datetime import date
from decimal import Decimal

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
