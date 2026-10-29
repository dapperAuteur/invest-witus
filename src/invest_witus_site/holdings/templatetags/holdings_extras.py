"""Template filters for the holdings pages. `{% load holdings_extras %}` makes them available."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django import template

register = template.Library()

CENT = Decimal("0.01")
# Shares are stored to six places (chapter 05's share step), so a count shows at most six.
SHARE_STEP = Decimal("0.000001")


def as_decimal(value: Decimal | int | str) -> Decimal | None:
    """A Decimal as it is; an int or a numeric string through `Decimal(str(...))`, never through
    a float. Anything else is None, so a filter shows the empty text instead of an error page."""
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


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


@register.filter
def money(value: Decimal | int | str | None) -> str:
    """US dollars to the cent, halves rounded up and away from zero, with thousands commas:
    `1234.5` is `$1,234.50`, `-1234.565` is `-$1,234.57`, `0.004` is `$0.00`. None is empty,
    as `plain_number` leaves it, so a template's own "not set" text stays in charge."""
    if value is None:
        return ""
    number = as_decimal(value)
    if number is None:
        return ""
    cents = number.quantize(CENT, rounding=ROUND_HALF_UP)
    # A value that rounds to zero is $0.00, never -$0.00.
    sign = "-" if cents < 0 else ""
    return f"{sign}${abs(cents):,.2f}"


@register.filter
def quantity(value: Decimal | int | str | None) -> str:
    """A share count with thousands commas and up to six places, trailing zeros dropped:
    `1234.500000` is `1,234.5`, `0.123456` stays, `10.000000` is `10`. None is empty."""
    if value is None:
        return ""
    number = as_decimal(value)
    if number is None:
        return ""
    shares = number.quantize(SHARE_STEP, rounding=ROUND_HALF_UP)
    sign = "-" if shares < 0 else ""
    text = f"{abs(shares):,f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return f"{sign}{text}"
