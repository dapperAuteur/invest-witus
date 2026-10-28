"""Template filters for the holdings pages. `{% load holdings_extras %}` makes them available."""

from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def signed(value: Decimal | None) -> str:
    """A change with its sign: `+1.500000`, `-500.00`, or plain `0.00`. None: the statement
    did not show the number, so there is nothing to compare."""
    if value is None:
        return "not shown"
    if value == 0:
        return str(value)
    return f"{value:+}"


@register.filter
def plain_number(value: Decimal | None) -> str:
    """A Decimal without the column's trailing zeros, with at least two places: `2.500000`
    becomes `2.50`, `101.230000` becomes `101.23`, `12.3456` stays, `1` becomes `1.00`."""
    if value is None:
        return ""
    text = f"{value:f}"
    whole, point, fraction = text.partition(".")
    fraction = fraction.rstrip("0") if point else ""
    return f"{whole}.{fraction.ljust(2, '0')}"
