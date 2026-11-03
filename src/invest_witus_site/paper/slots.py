"""Alpaca key slots (2026-11-02, decision 159): one pair of paper keys per Alpaca paper account,
any number of them, named in the environment.

Alpaca's paper-trading page says each newly created paper account needs its own newly generated
API keys (https://docs.alpaca.markets/docs/paper-trading, read 2026-11-02). One plan runs in one
Invest account, and each Invest account that trades on paper is linked to its own Alpaca paper
account, so the server holds one key pair per Alpaca account:

- `ALPACA_PAPER_KEY_ID` and `ALPACA_PAPER_SECRET_KEY`, unsuffixed, are the `DEFAULT` slot: the
  pair chapter 11 read, so an account linked before slots existed keeps working unchanged.
- `ALPACA_PAPER_KEY_ID__<SLOT>` and `ALPACA_PAPER_SECRET_KEY__<SLOT>` are the slot `<SLOT>`, where
  the name is 1 to 40 of `A-Z`, `0-9` and `_` (`MOMENTUM`, `DCA`, `QUALITY_MOMENTUM`). The settings
  find every such name in the environment at startup, so there is no list to edit and no limit.

A slot with one half set is incomplete and never used. A name that breaks the rule (lower case, a
dash, too long, `DEFAULT` spelled as a suffix) is ignored and reported by its variable name. An
Invest account stores only its slot's name (`Account.alpaca_slot`, blank for `DEFAULT`), never a
key; a slot that is gone from the environment blocks that account's trading with "Keys for slot X
are not set on the server" and never falls back to `DEFAULT`.

Nothing here prints, logs or renders a secret or a whole key id: the pages get the slot's name,
whether it is complete, and the last four characters of its key id.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from django.conf import settings

DEFAULT_SLOT = "DEFAULT"
KEY_ID_NAME = "ALPACA_PAPER_KEY_ID"
SECRET_NAME = "ALPACA_PAPER_SECRET_KEY"
SEPARATOR = "__"
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

    @property
    def complete(self) -> bool:
        return bool(self.key_id and self.secret_key)

    @property
    def missing(self) -> list[str]:
        """The variable names still to set on the server, for the page and the error."""
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
    return slot != DEFAULT_SLOT and SLOT_NAME.fullmatch(slot) is not None


def discover(environ: Mapping[str, str]) -> tuple[dict[str, tuple[str, str]], tuple[str, ...]]:
    """Every suffixed slot in `environ`, as `{slot: (key_id, secret_key)}` with either half
    possibly empty, and the names of the variables ignored for a bad slot name. Called once by
    the settings at startup; a test passes its own mapping. An empty value counts as not set."""
    found: dict[str, tuple[str, str]] = {}
    ignored: list[str] = []
    prefixes = ((f"{KEY_ID_NAME}{SEPARATOR}", 0), (f"{SECRET_NAME}{SEPARATOR}", 1))
    for name in sorted(environ):
        for prefix, half in prefixes:
            if not name.startswith(prefix):
                continue
            slot = name.removeprefix(prefix)
            if not valid_name(slot):
                ignored.append(name)
                break
            pair = list(found.get(slot, ("", "")))
            pair[half] = environ[name].strip()
            found[slot] = (pair[0], pair[1])
            break
    return found, tuple(ignored)


def all_slots() -> list[SlotKeys]:
    """`DEFAULT` first when either of its halves is set, then every discovered slot A to Z."""
    slots: list[SlotKeys] = []
    default = SlotKeys(DEFAULT_SLOT, settings.ALPACA_PAPER_KEY_ID, settings.ALPACA_PAPER_SECRET_KEY)
    if default.key_id or default.secret_key:
        slots.append(default)
    found: dict[str, tuple[str, str]] = settings.ALPACA_PAPER_KEY_SLOTS
    for name in sorted(found):
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


def ignored_names() -> tuple[str, ...]:
    return settings.ALPACA_PAPER_KEY_SLOT_IGNORED
