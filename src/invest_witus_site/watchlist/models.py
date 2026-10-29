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
