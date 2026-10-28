"""What an account holds on one statement, and what changed between two statements.

Pure functions over plain values: no database here. The Django models (chapter 05) turn their
rows into `Position`s and hand them to `compare`, so the arithmetic can be tested without a
database and reused by a CSV import later.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from invest_witus.money import to_money, to_shares

ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class Position:
    """One line of a statement: how much of one symbol, and what it cost in total.

    `cost_basis` is None when the statement did not print one. That is different from zero:
    zero means "cost nothing", None means "the statement did not say".
    """

    symbol: str
    shares: Decimal
    cost_basis: Decimal | None = None


@dataclass(frozen=True, slots=True)
class Change:
    """One symbol, before and after. A symbol missing from a statement counts as not held:
    zero shares and zero cost."""

    symbol: str
    shares_before: Decimal
    shares_after: Decimal
    cost_before: Decimal | None
    cost_after: Decimal | None

    @property
    def shares_change(self) -> Decimal:
        return to_shares(self.shares_after - self.shares_before)

    @property
    def cost_change(self) -> Decimal | None:
        """None when either statement left the cost basis out: no number beats a wrong one."""
        if self.cost_before is None or self.cost_after is None:
            return None
        return to_money(self.cost_after - self.cost_before)

    @property
    def changed(self) -> bool:
        return self.shares_change != ZERO or self.cost_change not in (ZERO, None)


def _by_symbol(positions: Iterable[Position]) -> dict[str, Position]:
    table: dict[str, Position] = {}
    for position in positions:
        if position.symbol in table:
            raise ValueError(f"{position.symbol} appears twice on one statement")
        table[position.symbol] = position
    return table


def compare(before: Iterable[Position], after: Iterable[Position]) -> list[Change]:
    """Every symbol on either statement, in symbol order, with its shares and cost on each side.

    Shares are rounded down to the share step and money to the cent (chapter 01), so two
    statements typed with different precision still compare like for like.
    """
    earlier = _by_symbol(before)
    later = _by_symbol(after)
    changes: list[Change] = []
    for symbol in sorted(earlier.keys() | later.keys()):
        old = earlier.get(symbol)
        new = later.get(symbol)
        changes.append(
            Change(
                symbol=symbol,
                shares_before=to_shares(old.shares if old else ZERO),
                shares_after=to_shares(new.shares if new else ZERO),
                cost_before=_cost(old),
                cost_after=_cost(new),
            )
        )
    return changes


def _cost(position: Position | None) -> Decimal | None:
    if position is None:
        return to_money(ZERO)
    if position.cost_basis is None:
        return None
    return to_money(position.cost_basis)
