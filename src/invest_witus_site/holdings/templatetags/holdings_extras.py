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
