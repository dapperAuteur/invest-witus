"""Your journal: what you actually bought and sold, one row per trade."""

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path

REQUIRED_COLUMNS = ("date", "action", "symbol", "amount")


class Action(StrEnum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True, slots=True)
class Entry:
    day: date
    action: Action
    symbol: str
    amount: Decimal


class JournalFileError(ValueError):
    def __init__(self, path: Path, line: int, problem: str) -> None:
        super().__init__(f"{path}, line {line}: {problem}")
        self.line = line


def load_journal(path: Path) -> list[Entry]:
    entries: list[Entry] = []
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        missing = [name for name in REQUIRED_COLUMNS if name not in (reader.fieldnames or [])]
        if missing:
            raise JournalFileError(path, 1, f"missing column(s): {', '.join(missing)}")
        for row in reader:
            line = reader.line_num
            try:
                day = date.fromisoformat(row["date"])
                action = Action(row["action"].strip().lower())
                amount = Decimal(row["amount"])
            except ValueError as error:
                raise JournalFileError(path, line, str(error)) from None
            except InvalidOperation:
                raise JournalFileError(path, line, f"not an amount: {row['amount']!r}") from None
            symbol = row["symbol"].strip().upper()
            if not symbol:
                raise JournalFileError(path, line, "symbol is empty")
            if amount <= 0:
                raise JournalFileError(path, line, "amount must be positive")
            entries.append(Entry(day=day, action=action, symbol=symbol, amount=amount))
    return sorted(entries, key=lambda entry: entry.day)
