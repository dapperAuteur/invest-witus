"""Linking an Invest account to an Alpaca paper account through a key slot (decision 159).

BAM's decision of 2026-11-02: one plan per Alpaca paper account. An Invest account keeps one active
plan, so each Invest account that trades on paper needs an Alpaca paper account of its own, and
each Alpaca paper account has its own keys (`paper/slots.py`). Linking chooses the slot; the check
reads Alpaca's account with that slot's keys, so the owner sees the account number the slot
reaches, and the link is refused when another Invest account already trades there: two plans in
one Alpaca account would buy from one pool of cash, which is what the decision avoids.

Only the slot's name and the account number are stored. Nothing here shows a key.
"""

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from invest_witus_site.holdings.models import Account
from invest_witus_site.paper import slots
from invest_witus_site.paper.alpaca import AlpacaError, PaperAccount, client_for, client_for_slot
from invest_witus_site.paper.models import PaperOrder


@dataclass(frozen=True, slots=True)
class LinkCheck:
    """What the chosen slot's keys reach, and the one reason, if any, it cannot be linked."""

    slot: str
    reached: PaperAccount | None
    refusal: str

    @property
    def ok(self) -> bool:
        return self.reached is not None and not self.refusal


def linked_elsewhere(account: Account, slot: str, number: str) -> Account | None:
    """Another Invest account, of any owner, that already trades in the Alpaca paper account
    `number`: one linked through the same slot (the same keys reach the same account), one whose
    recorded number is the same, or one linked before decision 159 with no number recorded, whose
    number is read now with its own slot's keys and recorded on the way."""
    others = Account.objects.filter(alpaca=Account.Alpaca.PAPER).exclude(pk=account.pk)
    stored = slots.normalize(slot)
    same = (
        others.filter(alpaca_slot=stored).first()
        or others.filter(alpaca_account_number=number).first()
    )
    if same is not None:
        return same
    for other in others.filter(alpaca_account_number=""):
        try:
            other_number = client_for(other).account().account_number
        except AlpacaError:
            # Its slot is not set or Alpaca did not answer: nothing to compare with. Its trading
            # is blocked by the same error, and its own link check will record its number.
            continue
        if not other_number:
            continue
        try:
            with transaction.atomic():
                Account.objects.filter(pk=other.pk).update(alpaca_account_number=other_number)
        except IntegrityError:
            pass
        if other_number == number:
            return other
    return None


def check_slot(account: Account, slot: str) -> LinkCheck:
    """Read Alpaca's account with the slot's keys. One request, plus one for each other linked
    account that has no number recorded yet."""
    name = slots.display_name(slots.normalize(slot))
    try:
        reached = client_for_slot(name).account()
    except AlpacaError as error:
        return LinkCheck(name, None, error.message)
    number = reached.account_number
    if not number:
        return LinkCheck(
            name,
            reached,
            "Alpaca's answer had no account number, so the app cannot tell this paper account "
            "from another. Not linked.",
        )
    other = linked_elsewhere(account, name, number)
    if other is not None:
        whose = "your account" if other.owner_id == account.owner_id else "another owner's account"
        label = f"{whose} {other.name}" if other.owner_id == account.owner_id else whose
        return LinkCheck(
            name,
            reached,
            f"Alpaca paper account {number} is already linked to {label}. One Alpaca paper "
            "account runs one plan, so two plans never share its cash: create another paper "
            "account in Alpaca, give it its own keys and slot, and link this account to that.",
        )
    return LinkCheck(name, reached, "")


def open_orders_block(account: Account, slot: str) -> str:
    """Moving a linked account to another slot while Alpaca still has its orders would lose track
    of them: the new keys cannot read them. The sentence, or "" when nothing is open."""
    if not account.is_alpaca_paper or slots.normalize(slot) == account.alpaca_slot:
        return ""
    count = PaperOrder.open_orders(account).count()
    if not count:
        return ""
    return (
        f"{count} order{'' if count == 1 else 's'} of this account {'is' if count == 1 else 'are'} "
        f"still open at Alpaca under slot {account.alpaca_slot_name}. Wait until "
        f"{'it ends' if count == 1 else 'they end'} (Check orders now on the paper page), or "
        "cancel by editing the plan, then link again."
    )


def link(account: Account, slot: str) -> LinkCheck:
    """Check the slot and, when nothing refuses it, save the link: the slot's name and the number
    Alpaca reported. The database's constraints are the last word on a race."""
    blocked = open_orders_block(account, slot)
    if blocked:
        return LinkCheck(slots.display_name(slots.normalize(slot)), None, blocked)
    check = check_slot(account, slot)
    if not check.ok or check.reached is None:
        return check
    account.alpaca = Account.Alpaca.PAPER
    account.alpaca_slot = slots.normalize(slot)
    account.alpaca_account_number = check.reached.account_number
    try:
        account.validate_constraints()
        with transaction.atomic():
            account.save(update_fields=["alpaca", "alpaca_slot", "alpaca_account_number"])
    except (ValidationError, IntegrityError) as error:
        account.refresh_from_db()
        reason = "; ".join(error.messages) if isinstance(error, ValidationError) else str(error)
        return LinkCheck(check.slot, check.reached, f"Not linked. {reason}")
    return check


def unlink_block(account: Account) -> str:
    count = PaperOrder.open_orders(account).count()
    if not count:
        return ""
    return (
        f"{count} order{'' if count == 1 else 's'} of this account {'is' if count == 1 else 'are'} "
        "still open at Alpaca. Unlinking now would lose track of "
        f"{'it' if count == 1 else 'them'}; wait until they end, or cancel by editing the plan."
    )


def unlink(account: Account) -> None:
    """Back to not linked. The app's order rows and the journal stay: they are the history."""
    account.alpaca = Account.Alpaca.NONE
    account.alpaca_slot = ""
    account.alpaca_account_number = ""
    account.save(update_fields=["alpaca", "alpaca_slot", "alpaca_account_number"])


@dataclass(frozen=True, slots=True)
class SlotRow:
    """One line of the key slot list: never a key, only the last four of the key id."""

    name: str
    key_hint: str
    complete: bool
    missing: list[str]
    on_server: bool
    accounts: list[Account]
    # Set in both name forms with different values (decision 166): shown, never used.
    conflicting: bool = False


def slot_rows() -> list[SlotRow]:
    """Every slot the server has, then every slot an account is linked through that the server
    does not have, each with the Invest accounts linked through it."""
    linked = list(
        Account.objects.filter(alpaca=Account.Alpaca.PAPER)
        .select_related("owner")
        .order_by("name", "pk")
    )
    rows: list[SlotRow] = []
    seen: set[str] = set()
    for keys in slots.all_slots():
        seen.add(keys.name)
        users = [a for a in linked if a.alpaca_slot_name == keys.name]
        rows.append(
            SlotRow(
                keys.name,
                keys.key_hint,
                keys.complete,
                keys.missing,
                True,
                users,
                keys.conflicting,
            )
        )
    for name in sorted({a.alpaca_slot_name for a in linked} - seen):
        users = [a for a in linked if a.alpaca_slot_name == name]
        missing = list(slots.env_names(name))
        rows.append(SlotRow(name, "", False, missing, False, users))
    return rows
