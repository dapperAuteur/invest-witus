"""Money and share amounts as exact decimals, never floats."""

from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
# This app records shares to six decimal places. Brokers set their own limits for fractional shares.
SHARE_STEP = Decimal("0.000001")


def to_money(value: Decimal) -> Decimal:
    """Round to whole cents, halves away from zero (the rounding most people expect)."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def to_shares(value: Decimal) -> Decimal:
    """Round down to the share step, so a purchase never records more shares than it paid for."""
    return value.quantize(SHARE_STEP, rounding=ROUND_DOWN)
