"""Your plan: the personal numbers you chose for a method."""

import tomllib
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Plan:
    method: str
    start: date
    amount: Decimal
    symbols: frozenset[str]
    buy_window_days: int


class PlanFileError(ValueError):
    """A plan file with a missing or wrong setting."""


def load_plan(path: Path) -> Plan:
    with path.open("rb") as file:
        data = tomllib.load(file)
    try:
        start = data["start"]
        if not isinstance(start, date):
            raise PlanFileError(f"{path}: start must be a date like 2025-10-01, not {start!r}")
        amount = Decimal(str(data["amount"]))
        window = int(data["buy_window_days"])
        plan = Plan(
            method=str(data["method"]),
            start=start,
            amount=amount,
            symbols=frozenset(str(symbol) for symbol in data["symbols"]),
            buy_window_days=window,
        )
    except KeyError as missing:
        raise PlanFileError(f"{path}: missing setting {missing}") from None
    except InvalidOperation:
        raise PlanFileError(f'{path}: amount must be a number in quotes, like "100.00"') from None
    if plan.amount <= 0:
        raise PlanFileError(f"{path}: amount must be positive")
    if not 1 <= plan.buy_window_days <= 28:
        raise PlanFileError(f"{path}: buy_window_days must be between 1 and 28")
    if not plan.symbols:
        raise PlanFileError(f"{path}: symbols must name at least one fund")
    return plan
