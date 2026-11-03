"""Alpaca key slots (2026-11-02, decision 159): one Alpaca paper account per Invest account.

Any number of key pairs in the environment, found at startup; the unsuffixed pair is DEFAULT, so
chapter 11's link keeps working. An account stores only its slot's name and the Alpaca account
number its link check read back. Every call for an account goes out with that account's keys, a
slot that is gone blocks with its name and never falls back, the link page refuses a second
Invest account on one Alpaca account, only the site owner's superuser sees any of it, and no page
shows a secret or a whole key id.

Each Alpaca paper account is a fake behind httpx's `MockTransport`, chosen by the key id header
the request carries; no request leaves the process, and every key is made up."""

import ast
import re
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path
from typing import Any

import httpx
import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client
from pytest_django.fixtures import Settings

from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.models import MethodPlan
from invest_witus_site.paper import alpaca, orders, slots
from invest_witus_site.paper.alpaca import AlpacaNotConfigured, client_for, credentials_for
from invest_witus_site.paper.models import PaperOrder
from invest_witus_site.paper.slots import SlotKeys, discover
from tests.test_ch10 import text
from tests.test_ch11 import DAY, KEY_ID, SECRET, fresh_settings
from tests.test_plan_edit_delete import CancellingAlpaca

D = Decimal
SRC = Path(__file__).resolve().parent.parent / "src" / "invest_witus_site"
# Made up, and shaped like nothing real. The last four characters are what a page may show.
MOMENTUM_KEY, MOMENTUM_SECRET = "MOMENTUMKEYID01A2B", "momentum-secret-not-a-real-key"
DCA_KEY, DCA_SECRET = "DCAKEYID00000C3D4", "dca-secret-not-a-real-key"
TWIN_KEY, TWIN_SECRET = "TWINKEYID0000E5F6", "twin-secret-not-a-real-key"
SECRETS = (SECRET, MOMENTUM_SECRET, DCA_SECRET, TWIN_SECRET)
KEY_IDS = (KEY_ID, MOMENTUM_KEY, DCA_KEY, TWIN_KEY)


class PaperAccountFake(CancellingAlpaca):
    """One Alpaca paper account: the cancelling fake, with its own account number."""

    def __init__(self, number: str) -> None:
        super().__init__()
        self.number = number

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/account":
            self.requests.append(request)
            body = {
                "account_number": self.number,
                "cash": "100000",
                "buying_power": "200000",
                "equity": "100000",
                "status": "ACTIVE",
                "trading_blocked": False,
            }
            return httpx.Response(200, json=body)
        return super().handle(request)


class AlpacaAccounts:
    """Alpaca with several paper accounts: a request reaches the one its key id belongs to, and a
    key id Alpaca does not know is a 401, as Alpaca answers a bad key."""

    def __init__(self) -> None:
        self.by_key: dict[str, PaperAccountFake] = {}

    def add(self, key_id: str, number: str) -> PaperAccountFake:
        fake = self.by_key.get(key_id) or PaperAccountFake(number)
        self.by_key[key_id] = fake
        return fake

    def handle(self, request: httpx.Request) -> httpx.Response:
        found = self.by_key.get(request.headers.get("APCA-API-KEY-ID", ""))
        if found is None:
            return httpx.Response(401, json={"code": 40110000, "message": "unauthorized."})
        return found.handle(request)


@pytest.fixture
def accounts(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> AlpacaAccounts:
    """Three Alpaca paper accounts: DEFAULT's (chapter 11's pair), MOMENTUM's and DCA's."""
    router = AlpacaAccounts()
    router.add(KEY_ID, "PA0DEFAULT01")
    router.add(MOMENTUM_KEY, "PA0MOMENTUM1")
    router.add(DCA_KEY, "PA0DCA000001")
    monkeypatch.setattr(alpaca, "transport", httpx.MockTransport(router.handle))
    monkeypatch.setattr(orders, "today", lambda: DAY)
    settings.ALPACA_PAPER_KEY_ID = KEY_ID
    settings.ALPACA_PAPER_SECRET_KEY = SECRET
    settings.ALPACA_PAPER_KEY_SLOTS = {
        "MOMENTUM": (MOMENTUM_KEY, MOMENTUM_SECRET),
        "DCA": (DCA_KEY, DCA_SECRET),
        "HALF": ("HALFKEYID0000G7H8", ""),
    }
    return router


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_superuser("owner", "owner@example.com", "pw")


@pytest.fixture
def owner_client(client: Client, owner: User) -> Client:
    client.force_login(owner)
    return client


def paper(owner: User, name: str, slot: str | None = None, number: str = "") -> Account:
    """A paper account; linked through `slot` when one is given ("" is DEFAULT)."""
    linked = slot is not None
    return Account.objects.create(
        name=name,
        broker="Alpaca",
        kind="paper",
        owner=owner,
        alpaca="paper" if linked else "",
        alpaca_slot=slot or "",
        alpaca_account_number=number,
    )


def plan_for(account: Account) -> MethodPlan:
    return MethodPlan.objects.create(
        account=account,
        method_id="index-dca",
        amount=D("100.00"),
        buy_window_days=7,
        symbols="INDEX",
        started_on=date(2026, 11, 1),
        practice_budget=D("1000.00"),
    )


def keys_sent(fake: PaperAccountFake) -> set[str]:
    return {request.headers["APCA-API-KEY-ID"] for request in fake.requests}


def words(response: Any) -> str:
    """The page's text with the tags taken out, so a sentence with a <strong> in it reads whole."""
    return " ".join(re.sub(r"<[^>]+>", "", text(response)).split())


def link_url(account: Account) -> str:
    return f"/accounts/{account.pk}/paper/link/"


# --- Discovery ------------------------------------------------------------------------------------


def test_discovery_finds_any_number_of_slots_and_reports_bad_names() -> None:
    environ = {f"ALPACA_PAPER_KEY_ID__METHOD_{n}": f"KEY{n}" for n in range(25)}
    environ |= {f"ALPACA_PAPER_SECRET_KEY__METHOD_{n}": f"SECRET{n}" for n in range(25)}
    environ |= {
        "ALPACA_PAPER_KEY_ID__QUALITY_MOMENTUM": "QKEY",
        "ALPACA_PAPER_SECRET_KEY__QUALITY_MOMENTUM": "QSECRET",
        "ALPACA_PAPER_KEY_ID__ONLYKEY": "OKEY",  # no secret: incomplete
        "ALPACA_PAPER_SECRET_KEY__ONLYSECRET": "OSECRET",  # no key id: incomplete
        "ALPACA_PAPER_KEY_ID__EMPTY": "",  # set but empty counts as not set
        "ALPACA_PAPER_KEY_ID__momentum": "x",  # lower case
        "ALPACA_PAPER_SECRET_KEY__DASH-NAME": "x",  # a dash
        "ALPACA_PAPER_KEY_ID__" + "L" * 41: "x",  # too long
        "ALPACA_PAPER_KEY_ID__DEFAULT": "x",  # DEFAULT is the pair with no suffix
        "ALPACA_PAPER_KEY_ID__": "x",  # no name at all
        "ALPACA_PAPER_KEY_ID": "unsuffixed, not a slot here",
        "ALPACA_PAPER_KEY_IDX__NOPE": "a different prefix",
        "PATH": "/usr/bin",
    }
    found, ignored = discover(environ)
    assert len([name for name in found if name.startswith("METHOD_")]) == 25
    assert found["METHOD_7"] == ("KEY7", "SECRET7")
    assert found["QUALITY_MOMENTUM"] == ("QKEY", "QSECRET")
    assert found["ONLYKEY"] == ("OKEY", "") and found["ONLYSECRET"] == ("", "OSECRET")
    assert found["EMPTY"] == ("", "")
    assert set(ignored) == {
        "ALPACA_PAPER_KEY_ID__momentum",
        "ALPACA_PAPER_SECRET_KEY__DASH-NAME",
        "ALPACA_PAPER_KEY_ID__" + "L" * 41,
        "ALPACA_PAPER_KEY_ID__DEFAULT",
        "ALPACA_PAPER_KEY_ID__",
    }
    assert "x" not in ignored, "names only, never a value"
    assert SlotKeys("L" * 40, "a", "b").name in {"L" * 40}, "forty characters is allowed"
    assert discover({"ALPACA_PAPER_KEY_ID__" + "L" * 40: "k"})[0] == {"L" * 40: ("k", "")}


def test_the_settings_discover_slots_from_the_environment_at_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = fresh_settings(
        monkeypatch,
        {
            "DJANGO_DEBUG": "1",
            "ALPACA_PAPER_KEY_ID__MOMENTUM": MOMENTUM_KEY,
            "ALPACA_PAPER_SECRET_KEY__MOMENTUM": MOMENTUM_SECRET,
            "ALPACA_PAPER_KEY_ID__DCA": DCA_KEY,
            "ALPACA_PAPER_KEY_ID__bad": "x",
        },
    )
    assert loaded.ALPACA_PAPER_KEY_SLOTS == {
        "DCA": (DCA_KEY, ""),
        "MOMENTUM": (MOMENTUM_KEY, MOMENTUM_SECRET),
    }
    assert loaded.ALPACA_PAPER_KEY_SLOT_IGNORED == ("ALPACA_PAPER_KEY_ID__bad",)
    assert (loaded.ALPACA_PAPER_KEY_ID, loaded.ALPACA_PAPER_SECRET_KEY) == ("", "")


def test_a_slot_shows_only_the_last_four_of_its_key_id_and_never_prints_a_key() -> None:
    keys = SlotKeys("MOMENTUM", MOMENTUM_KEY, MOMENTUM_SECRET)
    assert keys.key_hint == "1A2B"
    assert MOMENTUM_KEY not in repr(keys) and MOMENTUM_SECRET not in repr(keys)
    assert SlotKeys("SHORT", "ABC1234", "s").key_hint == "", "a short id is never shown"
    assert SlotKeys("HALF", "HALFKEYID0000G7H8", "").missing == ["ALPACA_PAPER_SECRET_KEY__HALF"]
    assert SlotKeys("DEFAULT", "", "").missing == [
        "ALPACA_PAPER_KEY_ID",
        "ALPACA_PAPER_SECRET_KEY",
    ]


# --- The client per account -----------------------------------------------------------------------


@pytest.mark.django_db
def test_the_unsuffixed_pair_is_default_so_an_account_linked_before_slots_is_unchanged(
    accounts: AlpacaAccounts, owner: User
) -> None:
    legacy = paper(owner, "Practice", slot="")
    assert legacy.alpaca_slot_name == "DEFAULT"
    assert credentials_for("") == credentials_for("DEFAULT") == credentials_for("default")
    assert client_for(legacy).account().account_number == "PA0DEFAULT01"
    assert keys_sent(accounts.by_key[KEY_ID]) == {KEY_ID}
    assert alpaca.keys_configured() and slots.any_configured()


@pytest.mark.django_db
def test_each_account_trades_with_its_own_slots_keys(accounts: AlpacaAccounts, owner: User) -> None:
    momentum = paper(owner, "Momentum", slot="MOMENTUM", number="PA0MOMENTUM1")
    dca = paper(owner, "DCA", slot="DCA", number="PA0DCA000001")
    momentum_plan = plan_for(momentum)
    orders.confirm(momentum_plan, DAY, client_for(momentum))
    orders.confirm(plan_for(dca), DAY, client_for(dca))
    momentum_fake, dca_fake = accounts.by_key[MOMENTUM_KEY], accounts.by_key[DCA_KEY]
    assert keys_sent(momentum_fake) == {MOMENTUM_KEY} and keys_sent(dca_fake) == {DCA_KEY}
    assert [o["client_order_id"] for o in momentum_fake.posted] == [
        f"iw-{momentum.pk}-{momentum_plan.pk}-2026-11-INDEX"
    ]
    assert len(dca_fake.posted) == 1 and accounts.by_key[KEY_ID].requests == []
    momentum_secret = {r.headers["APCA-API-SECRET-KEY"] for r in momentum_fake.requests}
    assert momentum_secret == {MOMENTUM_SECRET}


@pytest.mark.django_db
def test_a_slot_gone_from_the_server_blocks_trading_and_never_falls_back(
    accounts: AlpacaAccounts, owner_client: Client, owner: User
) -> None:
    gone = paper(owner, "Gone", slot="GONE", number="PA0GONE00001")
    plan_for(gone)
    with pytest.raises(AlpacaNotConfigured, match="Keys for slot GONE are not set on the server"):
        client_for(gone)
    page = text(owner_client.get(f"/accounts/{gone.pk}/method/"))
    assert "Keys for slot GONE are not set on the server." in page
    assert "Alpaca did not answer" not in page, "the server's gap, not Alpaca's silence"
    assert "queue for the open" not in page and ">Confirm<" not in page
    response = owner_client.post(f"/accounts/{gone.pk}/paper/confirm/", follow=True)
    assert "Nothing was placed. Keys for slot GONE are not set on the server." in text(response)
    assert "Keys for slot GONE are not set" in text(owner_client.get(f"/accounts/{gone.pk}/paper/"))
    assert all(fake.requests == [] for fake in accounts.by_key.values()), "no fallback"
    assert PaperOrder.objects.count() == 0
    half = paper(owner, "Half", slot="HALF")
    with pytest.raises(AlpacaNotConfigured, match="ALPACA_PAPER_SECRET_KEY__HALF is not set"):
        client_for(half)


@pytest.mark.django_db
def test_the_nightly_check_reads_each_accounts_orders_with_its_own_keys(
    accounts: AlpacaAccounts,
    owner: User,
    client: Client,
    settings: Settings,
    tmp_path: Path,
) -> None:
    momentum = paper(owner, "Momentum", slot="MOMENTUM", number="PA0MOMENTUM1")
    dca = paper(owner, "DCA", slot="DCA", number="PA0DCA000001")
    for account in (momentum, dca):
        orders.confirm(plan_for(account), DAY, client_for(account))
    accounts.by_key[MOMENTUM_KEY].fill("order-1", qty="0.5", price="200")
    # DCA's keys leave the server: its order is reported, MOMENTUM's still syncs.
    settings.ALPACA_PAPER_KEY_SLOTS = {"MOMENTUM": (MOMENTUM_KEY, MOMENTUM_SECRET)}
    settings.CRON_SECRET = "cron-secret-for-tests-only"
    settings.TIINGO_API_KEY = ""
    settings.PRICES_CSV_DIR = tmp_path
    headers = {"Authorization": "Bearer cron-secret-for-tests-only"}
    body: dict[str, Any] = client.get("/api/cron/pull-prices/", headers=headers).json()
    dca_order = PaperOrder.objects.get(account=dca)
    assert body["orders"]["checked"] == 1 and body["orders"]["filled"] == 1
    assert body["orders"]["failed"] == {
        dca_order.client_order_id: "Keys for slot DCA are not set on the server."
    }
    assert PaperOrder.objects.get(account=momentum).status == "filled"
    assert keys_sent(accounts.by_key[MOMENTUM_KEY]) == {MOMENTUM_KEY}
    assert accounts.by_key[KEY_ID].requests == [], "DCA's order never went out on DEFAULT"
    out, err = StringIO(), StringIO()
    call_command("sync_paper_orders", stdout=out, stderr=err)
    assert out.getvalue().startswith("Checked 0, changed 0")
    assert "Keys for slot DCA are not set on the server." in err.getvalue()


@pytest.mark.django_db
def test_confirm_stops_when_the_slots_keys_now_reach_another_alpaca_account(
    accounts: AlpacaAccounts, owner_client: Client, owner: User
) -> None:
    moved = paper(owner, "Momentum", slot="MOMENTUM", number="PA0SOMEOTHER")
    plan_for(moved)
    response = owner_client.post(f"/accounts/{moved.pk}/paper/confirm/", follow=True)
    assert "now reach Alpaca paper account PA0MOMENTUM1, not PA0SOMEOTHER" in text(response)
    assert accounts.by_key[MOMENTUM_KEY].posted == []
    page = words(owner_client.get(f"/accounts/{moved.pk}/paper/"))
    assert "Confirm places nothing until you link the account again" in page


# --- The link page --------------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_link_page_lists_slots_checks_and_links(
    accounts: AlpacaAccounts, owner_client: Client, owner: User
) -> None:
    fresh = paper(owner, "Momentum")
    page = text(owner_client.get(link_url(fresh)))
    assert "DEFAULT (key id ending 0000)" in page
    assert "MOMENTUM (key id ending 1A2B)" in page and "DCA (key id ending C3D4)" in page
    assert "HALF (keys incomplete: ALPACA_PAPER_SECRET_KEY__HALF not set)" in page
    checked = words(owner_client.post(link_url(fresh), {"slot": "MOMENTUM", "action": "check"}))
    assert "Slot MOMENTUM reaches Alpaca paper account PA0MOMENTUM1" in checked
    fresh.refresh_from_db()
    assert not fresh.is_alpaca_paper, "a check saves nothing"
    response = owner_client.post(link_url(fresh), {"slot": "MOMENTUM", "action": "link"})
    assert response.status_code == 302
    fresh.refresh_from_db()
    assert (fresh.alpaca, fresh.alpaca_slot, fresh.alpaca_account_number) == (
        "paper",
        "MOMENTUM",
        "PA0MOMENTUM1",
    )
    refused = text(owner_client.post(link_url(fresh), {"slot": "HALF", "action": "link"}))
    assert "Slot HALF's keys are incomplete on the server" in refused
    fresh.refresh_from_db()
    assert fresh.alpaca_slot == "MOMENTUM"


@pytest.mark.django_db
def test_two_invest_accounts_never_share_one_alpaca_account(
    accounts: AlpacaAccounts, owner_client: Client, owner: User, settings: Settings
) -> None:
    first = paper(owner, "Momentum", slot="MOMENTUM", number="PA0MOMENTUM1")
    second = paper(owner, "Second")
    # TWIN's keys are a second pair for MOMENTUM's Alpaca account.
    accounts.by_key[TWIN_KEY] = accounts.by_key[MOMENTUM_KEY]
    settings.ALPACA_PAPER_KEY_SLOTS = {
        **settings.ALPACA_PAPER_KEY_SLOTS,
        "TWIN": (TWIN_KEY, TWIN_SECRET),
    }
    for slot in ("TWIN", "MOMENTUM"):
        page = text(owner_client.post(link_url(second), {"slot": slot, "action": "link"}))
        assert (
            "Alpaca paper account PA0MOMENTUM1 is already linked to your account Momentum" in page
        )
        second.refresh_from_db()
        assert not second.is_alpaca_paper
    assert first.alpaca_slot == "MOMENTUM"


@pytest.mark.django_db
def test_an_account_linked_before_slots_has_its_number_read_and_counted(
    accounts: AlpacaAccounts, owner_client: Client, owner: User, settings: Settings
) -> None:
    legacy = paper(owner, "Practice", slot="")  # chapter 11's link: DEFAULT, no number
    newcomer = paper(owner, "Newcomer")
    accounts.by_key[TWIN_KEY] = accounts.by_key[KEY_ID]  # a second pair for DEFAULT's account
    settings.ALPACA_PAPER_KEY_SLOTS = {"TWIN": (TWIN_KEY, TWIN_SECRET)}
    page = text(owner_client.post(link_url(newcomer), {"slot": "TWIN", "action": "link"}))
    assert "PA0DEFAULT01 is already linked to your account Practice" in page
    legacy.refresh_from_db()
    assert legacy.alpaca_account_number == "PA0DEFAULT01", "recorded on the way"


@pytest.mark.django_db
def test_relinking_or_unlinking_waits_for_open_orders(
    accounts: AlpacaAccounts, owner_client: Client, owner: User
) -> None:
    linked = paper(owner, "Practice", slot="", number="PA0DEFAULT01")
    orders.confirm(plan_for(linked), DAY, client_for(linked))
    page = text(owner_client.post(link_url(linked), {"slot": "DCA", "action": "link"}))
    assert "1 order of this account is still open at Alpaca under slot DEFAULT" in page
    unlink = owner_client.post(link_url(linked), {"action": "unlink"}, follow=True)
    assert "still open at Alpaca. Unlinking now would lose track of it" in text(unlink)
    linked.refresh_from_db()
    assert (linked.alpaca, linked.alpaca_slot) == ("paper", "")
    accounts.by_key[KEY_ID].fill("order-1", qty="0.5", price="200")
    orders.sync_orders(client_for(linked), linked)
    owner_client.post(link_url(linked), {"action": "unlink"})
    linked.refresh_from_db()
    assert (linked.alpaca, linked.alpaca_slot, linked.alpaca_account_number) == ("", "", "")
    assert PaperOrder.objects.filter(account=linked).count() == 1, "the history stays"


# --- Who may see it, and what it shows ------------------------------------------------------------


@pytest.mark.django_db
def test_linking_and_the_slot_list_are_the_site_owners_only(
    accounts: AlpacaAccounts, client: Client, owner: User, django_user_model: type[User]
) -> None:
    mine = paper(owner, "Momentum")
    brokerage = Account.objects.create(
        name="Taxable", broker="Example", kind="brokerage", owner=owner
    )
    assert client.get(link_url(mine)).status_code == 302, "signed out: to the sign-in"
    assert client.get("/accounts/alpaca-slots/").status_code == 302
    plain = django_user_model.objects.create_user("plain")
    theirs = paper(plain, "Theirs")
    client.force_login(plain)
    assert client.get(link_url(theirs)).status_code == 404, "not a superuser"
    assert client.post(link_url(theirs), {"slot": "DCA", "action": "link"}).status_code == 404
    assert client.get("/accounts/alpaca-slots/").status_code == 404
    assert client.get(link_url(mine)).status_code == 404, "another owner's account"
    client.force_login(owner)
    assert client.get(link_url(theirs)).status_code == 404, "the superuser's, not another's"
    assert client.get(link_url(brokerage)).status_code == 404, "paper accounts only"
    assert client.get(link_url(mine)).status_code == 200
    theirs.refresh_from_db()
    assert not theirs.is_alpaca_paper
    assert all(fake.requests == [] for fake in accounts.by_key.values())


@pytest.mark.django_db
def test_no_page_shows_a_secret_or_a_whole_key_id(
    accounts: AlpacaAccounts, owner_client: Client, owner: User
) -> None:
    momentum = paper(owner, "Momentum", slot="MOMENTUM", number="PA0MOMENTUM1")
    paper(owner, "DCA", slot="DCA", number="PA0DCA000001")
    gone = paper(owner, "Gone", slot="GONE")
    unlinked = paper(owner, "Unlinked")
    plan_for(momentum)
    pages = {
        "/accounts/",
        "/accounts/alpaca-slots/",
        link_url(momentum),
        link_url(unlinked),
        f"/accounts/{momentum.pk}/",
        f"/accounts/{unlinked.pk}/",
        f"/accounts/{momentum.pk}/paper/",
        f"/accounts/{momentum.pk}/method/",
        f"/accounts/{gone.pk}/paper/",
    }
    seen = ""
    for path in sorted(pages):
        response = owner_client.get(path)
        assert response.status_code == 200, path
        html = text(response)
        for value in (*SECRETS, *KEY_IDS):
            assert value not in html, (path, "a key or secret reached the page")
        seen += html
    slot_list = text(owner_client.get("/accounts/alpaca-slots/"))
    for hint in ("1A2B", "C3D4", "0000"):
        assert f"<td>{hint}</td>" in slot_list
    assert "not set on the server" in slot_list and "keys incomplete" in slot_list
    assert ">Momentum</a> (Alpaca PA0MOMENTUM1)" in slot_list
    assert "Paper accounts" in seen, "the header links the slot list when several are linked"
    assert "Link to Alpaca paper" in text(owner_client.get(f"/accounts/{unlinked.pk}/"))


# --- Nothing uses one global pair any more --------------------------------------------------------


def test_no_app_code_builds_a_client_from_the_global_pair() -> None:
    """Every client for an account comes from `client_for`. `paper_client()` (the DEFAULT slot,
    named) stays for chapter 11's tests only, and the settings' key names are read by the slot
    module and the settings alone."""
    allowed_reads = {SRC / "settings.py", SRC / "paper" / "slots.py"}
    for path in SRC.rglob("*.py"):
        if "migrations" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "paper_client":
                pytest.fail(f"{path} calls paper_client()")
            if isinstance(node, ast.Attribute) and node.attr == "paper_client":
                pytest.fail(f"{path} uses paper_client")
            if (
                isinstance(node, ast.Attribute)
                and node.attr.startswith("ALPACA_PAPER_")
                and path not in allowed_reads
            ):
                pytest.fail(f"{path} reads settings.{node.attr}")
