"""Alpaca key slots (2026-11-02, decision 159): one pair of paper keys per Alpaca paper account,
any number of them, named in the environment.

Alpaca's paper-trading page says each newly created paper account needs its own newly generated
API keys (https://docs.alpaca.markets/docs/paper-trading, read 2026-11-02). One plan runs in one
Invest account, and each Invest account that trades on paper is linked to its own Alpaca paper
account, so the server holds one key pair per Alpaca account:

- `ALPACA_PAPER_KEY_ID` and `ALPACA_PAPER_SECRET_KEY`, unsuffixed, are the `DEFAULT` slot: the
  pair chapter 11 read, so an account linked before slots existed keeps working unchanged.
- `ALPACA_PAPER_KEY_ID__<SLOT>` and `ALPACA_PAPER_SECRET_KEY__<SLOT>` are the slot `<SLOT>`, where
  the name is 1 to 40 of `A-Z`, `0-9` and `_`, not starting with `_` (`MOMENTUM`, `DCA`,
  `QUALITY_MOMENTUM`). The settings find every such name in the environment at startup, so there
  is no list to edit and no limit.

Since 2026-11-03 (decision 166) the single-underscore form `ALPACA_PAPER_KEY_ID_<SLOT>` /
`ALPACA_PAPER_SECRET_KEY_<SLOT>` is read too, for the same slot `<SLOT>`, because a pair added that
way was silently ignored. When both forms of one half are set with different values, the slot is
**conflicting**: never used, and shown as such, because picking one silently could trade in the
wrong Alpaca account. Both forms with the same value are one value.

A slot with one half set is incomplete and never used. Every variable starting `ALPACA_PAPER_` that
the app cannot use (a bad slot name, an empty suffix, `DEFAULT` as a suffix, one half of a pair, a
conflicting slot, an unknown prefix) is listed by its variable name with the reason, never a value.
An Invest account stores only its slot's name (`Account.alpaca_slot`, blank for `DEFAULT`), never a
key; a slot that is gone from the environment blocks that account's trading with "Keys for slot X
are not set on the server" and never falls back to `DEFAULT`.

Nothing here prints, logs or renders a secret or a whole key id: the pages get the slot's name,
whether it is complete, and the last four characters of its key id.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import NamedTuple

from django.conf import settings

DEFAULT_SLOT = "DEFAULT"
KEY_ID_NAME = "ALPACA_PAPER_KEY_ID"
SECRET_NAME = "ALPACA_PAPER_SECRET_KEY"
SEPARATOR = "__"
# The near miss read as well (decision 166): one underscore before the slot's name.
SHORT_SEPARATOR = "_"
# Every variable with this prefix is either used or listed on the key slots page with a reason.
FAMILY_PREFIX = "ALPACA_PAPER_"
SLOT_NAME = re.compile(r"[A-Z0-9_]{1,40}")
# How much of a key id a page may show: its last four characters, and only of an id at least this
# long, so a short made-up id is never shown whole. Alpaca's key ids are 20 characters.
HINT_LENGTH = 4
HINT_MIN_KEY_LENGTH = 8


@dataclass(frozen=True, slots=True)
class SlotKeys:
    """One slot's pair, either half possibly empty. `repr=False` keeps both out of any traceback
    and any log line that prints the object."""

    name: str
    key_id: str = field(repr=False)
    secret_key: str = field(repr=False)
    # Both forms of a half set with different values (decision 166): never used, keys left empty.
    conflicting: bool = False

    @property
    def complete(self) -> bool:
        return bool(self.key_id and self.secret_key) and not self.conflicting

    @property
    def conflict_message(self) -> str:
        """Why a conflicting slot is refused, by variable names only."""
        if not self.conflicting:
            return ""
        return (
            f"Keys for slot {self.name} conflict on the server: both the {SEPARATOR}{self.name} "
            f"and the {SHORT_SEPARATOR}{self.name} form are set with different values. Delete one "
            "form and redeploy."
        )

    @property
    def missing(self) -> list[str]:
        """The variable names still to set on the server, for the page and the error. A
        conflicting slot misses nothing: it has too much."""
        if self.conflicting:
            return []
        key_name, secret_name = env_names(self.name)
        return [
            name
            for name, value in ((key_name, self.key_id), (secret_name, self.secret_key))
            if not value
        ]

    @property
    def key_hint(self) -> str:
        """The key id's last four characters, the only part of a key a page shows."""
        if len(self.key_id) < HINT_MIN_KEY_LENGTH:
            return ""
        return self.key_id[-HINT_LENGTH:]


def env_names(slot: str) -> tuple[str, str]:
    """The two variable names a slot reads: unsuffixed for `DEFAULT`, `__<SLOT>` otherwise."""
    if slot == DEFAULT_SLOT:
        return KEY_ID_NAME, SECRET_NAME
    return f"{KEY_ID_NAME}{SEPARATOR}{slot}", f"{SECRET_NAME}{SEPARATOR}{slot}"


def normalize(slot: str) -> str:
    """The name an account stores, upper case and trimmed, with `DEFAULT` stored as blank."""
    name = slot.strip().upper()
    return "" if name == DEFAULT_SLOT else name


def display_name(stored: str) -> str:
    """An account's stored slot as the page names it: blank is `DEFAULT`."""
    return stored or DEFAULT_SLOT


def valid_name(slot: str) -> bool:
    return name_problem(slot) == ""


def name_problem(slot: str) -> str:
    """Why a suffix is not a slot name, in words for the page; empty when it is one."""
    if not slot:
        return "empty suffix: nothing after the prefix"
    if slot == DEFAULT_SLOT:
        return (
            f"DEFAULT as a suffix: the DEFAULT slot is the pair with no suffix, {KEY_ID_NAME} and "
            f"{SECRET_NAME}"
        )
    if slot.startswith("_"):
        return "one underscore too many: the slot's name may not start with _"
    if len(slot) > 40:
        return "slot name longer than 40 characters"
    if SLOT_NAME.fullmatch(slot) is None:
        return "bad characters in the slot name: only A to Z, 0 to 9 and _ (no lower case, no dash)"
    return ""


class Unusable(NamedTuple):
    """A variable the app read past: its name and why, never its value."""

    name: str
    reason: str


@dataclass(frozen=True, slots=True)
class Discovery:
    """What the settings keep from the environment at startup.

    `found` is `{slot: (key_id, secret_key)}`, either half possibly empty (incomplete); a
    conflicting slot is not in it. `unusable` lists, by name, every `ALPACA_PAPER_` variable the
    app cannot use, A to Z. `conflicts` names the conflicting slots."""

    found: dict[str, tuple[str, str]]
    unusable: tuple[Unusable, ...]
    conflicts: frozenset[str]


def _slot_variable(name: str) -> tuple[str, int] | Unusable | None:
    """`(slot, half)` for a slot variable in either form, `Unusable` for a name in the family the
    app cannot read, `None` for the two DEFAULT names. Half 0 is the key id, 1 the secret."""
    for base, half in ((KEY_ID_NAME, 0), (SECRET_NAME, 1)):
        if name == base:
            return None
        # The double underscore first, so `__MOMENTUM` is MOMENTUM and not `_MOMENTUM`.
        for separator in (SEPARATOR, SHORT_SEPARATOR):
            prefix = f"{base}{separator}"
            if name.startswith(prefix):
                slot = name.removeprefix(prefix)
                problem = name_problem(slot)
                return Unusable(name, problem) if problem else (slot, half)
    return Unusable(
        name,
        f"unknown prefix: a slot's two names start {KEY_ID_NAME}_ and {SECRET_NAME}_",
    )


def discover(environ: Mapping[str, str]) -> Discovery:
    """Every suffixed slot in `environ`, in either form, and every `ALPACA_PAPER_` variable the
    app cannot use with the reason. Called once by the settings at startup; a test passes its
    own mapping. An empty value counts as not set and is not listed. No value leaves here except
    inside `found`."""
    # slot -> half -> [(variable name, value)], values stripped and not empty
    seen: dict[str, tuple[list[tuple[str, str]], list[tuple[str, str]]]] = {}
    unusable: list[Unusable] = []
    for name in sorted(environ):
        if not name.startswith(FAMILY_PREFIX):
            continue
        parsed = _slot_variable(name)
        if isinstance(parsed, Unusable):
            unusable.append(parsed)
            continue
        if parsed is None:
            continue
        slot, half = parsed
        halves = seen.setdefault(slot, ([], []))
        value = environ[name].strip()
        if value:
            halves[half].append((name, value))

    found: dict[str, tuple[str, str]] = {}
    conflicts: set[str] = set()
    for slot, halves in seen.items():
        if any(len({value for _, value in half}) > 1 for half in halves):
            conflicts.add(slot)
            reason = (
                f"conflicting forms: slot {slot} is set as both {SEPARATOR}{slot} and "
                f"{SHORT_SEPARATOR}{slot} with different values, so it is not used; delete one form"
            )
            unusable.extend(Unusable(name, reason) for half in halves for name, _ in half)
            continue
        key_id = halves[0][0][1] if halves[0] else ""
        secret_key = halves[1][0][1] if halves[1] else ""
        found[slot] = (key_id, secret_key)
        unusable.extend(_one_half(slot, halves[0], halves[1]))

    default_key = environ.get(KEY_ID_NAME, "").strip()
    default_secret = environ.get(SECRET_NAME, "").strip()
    default_halves = (
        [(KEY_ID_NAME, default_key)] if default_key else [],
        [(SECRET_NAME, default_secret)] if default_secret else [],
    )
    unusable.extend(_one_half(DEFAULT_SLOT, *default_halves))
    return Discovery(found, tuple(sorted(unusable)), frozenset(conflicts))


def _one_half(
    slot: str, key_half: list[tuple[str, str]], secret_half: list[tuple[str, str]]
) -> list[Unusable]:
    """The variables of a slot with only one half set, each naming the variable still missing."""
    if bool(key_half) == bool(secret_half):
        return []
    present, missing_name = (
        (key_half, env_names(slot)[1]) if key_half else (secret_half, env_names(slot)[0])
    )
    reason = f"only one half of the pair: {missing_name} is not set"
    return [Unusable(name, reason) for name, _ in present]


def example_names(slot: str = "MOMENTUM") -> tuple[str, str]:
    """The two names to add for a new slot, for the page's one line on adding one."""
    return env_names(slot)


def all_slots() -> list[SlotKeys]:
    """`DEFAULT` first when either of its halves is set, then every discovered slot A to Z,
    conflicting ones among them with no keys."""
    slots: list[SlotKeys] = []
    default = SlotKeys(DEFAULT_SLOT, settings.ALPACA_PAPER_KEY_ID, settings.ALPACA_PAPER_SECRET_KEY)
    if default.key_id or default.secret_key:
        slots.append(default)
    found: dict[str, tuple[str, str]] = settings.ALPACA_PAPER_KEY_SLOTS
    conflicts: frozenset[str] = settings.ALPACA_PAPER_KEY_SLOT_CONFLICTS
    for name in sorted(set(found) | conflicts):
        if name in conflicts:
            slots.append(SlotKeys(name, "", "", conflicting=True))
            continue
        key_id, secret_key = found[name]
        slots.append(SlotKeys(name, key_id, secret_key))
    return slots


def find(slot: str) -> SlotKeys | None:
    """The slot by its display or stored name (blank is `DEFAULT`); `None` when the server has
    neither of its variables."""
    name = display_name(normalize(slot))
    return next((keys for keys in all_slots() if keys.name == name), None)


def any_configured() -> bool:
    """At least one complete slot: the nightly check has something to read with."""
    return any(keys.complete for keys in all_slots())


def unusable() -> tuple[Unusable, ...]:
    """Every `ALPACA_PAPER_` variable found at startup that the app cannot use, with the reason."""
    return settings.ALPACA_PAPER_KEY_SLOT_IGNORED
