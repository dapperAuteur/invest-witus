"""Alternating row colors on every table (2026-11-03, decision 164; stronger, decision 175).

Every table the app draws is a `.holdings` table with a `<tbody>`, so one rule in `site.css`
stripes them all; the admin's own tables keep Django's stripes. The hover and the ticked-checkbox
row stay visible over the stripe, and text keeps WCAG 2.2's 4.5:1 on every row color (the
fallback rgba values are checked, and a test keeps the color-mix() values equal to them).

Decision 175's minimums (BAM, 2026-11-04: "more contrast between lines on tables"), as WCAG
contrast ratios between two background colors: a striped row against a plain one at least
`STRIPE_MIN`, and the 1px line under every row against each row color it sits on at least
`LINE_MIN`, on the page (`--bg`) and inside a card (`--surface`)."""

import re
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parent.parent / "src" / "invest_witus_site"
CSS = (SITE / "pages" / "static" / "pages" / "site.css").read_text()
TEMPLATES = sorted(
    path for path in SITE.rglob("templates/**/*.html") if "/templates/admin/" not in str(path)
)
ROWS = ["row-alt", "row-hover", "row-selected"]
BASES = ["bg", "surface"]
STRIPE_MIN = 1.2  # decision 164's 5% stripe was 1.08:1 on the page; decision 175's 10% is 1.22:1
LINE_MIN = 1.75  # decision 164's line (--border) was 1.38:1 on the page, 1.22:1 in a card


def hex_color(value: str) -> tuple[float, float, float]:
    value = value.lstrip("#")
    return int(value[0:2], 16) / 255, int(value[2:4], 16) / 255, int(value[4:6], 16) / 255


def token(name: str) -> str:
    match = re.search(rf"--{name}: ([^;]+);", CSS)
    assert match is not None, name
    return match.group(1).strip()


def over(rgba: str, base: tuple[float, float, float]) -> tuple[float, float, float]:
    """An rgba() tint laid over an opaque color."""
    parts = re.findall(r"[\d.]+", rgba)
    red, green, blue, alpha = (float(part) for part in parts)
    tint = (red / 255, green / 255, blue / 255)
    mixed = [alpha * t + (1 - alpha) * b for t, b in zip(tint, base, strict=True)]
    return mixed[0], mixed[1], mixed[2]


def luminance(color: tuple[float, float, float]) -> float:
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    red, green, blue = (channel(c) for c in color)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


@pytest.mark.parametrize("path", TEMPLATES, ids=lambda path: path.name)
def test_every_table_is_a_striped_holdings_table_with_a_body(path: Path) -> None:
    html = path.read_text()
    tables = re.findall(r"<table[^>]*>", html)
    for table in tables:
        assert re.search(r'class="[^"]*\bholdings\b', table), (path, table)
    assert html.count("<tbody") >= len(tables), path


def test_some_templates_have_tables() -> None:
    assert sum("<table" in path.read_text() for path in TEMPLATES) >= 10


def test_one_rule_stripes_every_body_row_and_hover_and_selection_win() -> None:
    stripe = ".holdings tbody tr:nth-child(even) { background: var(--row-alt); }"
    hover = ".holdings tbody tr:hover { background: var(--row-hover); }"
    picked = ".holdings tbody tr:has(input:checked) { background: var(--row-selected);"
    assert stripe in CSS and hover in CSS and picked in CSS
    assert CSS.index(stripe) < CSS.index(hover) < CSS.index(picked), "later rules win the tie"
    assert "box-shadow: inset 4px 0 0 var(--accent);" in CSS, "the selected row's bar"


def test_every_cell_has_the_row_line_under_it() -> None:
    cells = re.search(r"\.holdings th, \.holdings td \{([^}]*)\}", CSS)
    assert cells is not None
    assert "border-bottom: 1px solid var(--row-line);" in cells.group(1)


@pytest.mark.parametrize("name", [*ROWS, "row-line"])
def test_the_color_mix_value_equals_the_rgba_fallback(name: str) -> None:
    """The fallback is what the tests measure, so the mixed value must be the same color."""
    mixed = re.search(rf"--{name}: color-mix\(in srgb, var\(--(\w+)\) (\d+)%, transparent\);", CSS)
    assert mixed is not None, name
    source, percent = mixed.group(1), int(mixed.group(2))
    red, green, blue, alpha = (float(part) for part in re.findall(r"[\d.]+", token(name)))
    expected = tuple(round(c * 255) for c in hex_color(token(source)))
    assert (round(red), round(green), round(blue)) == expected, name
    assert round(alpha * 100) == percent, name


@pytest.mark.parametrize("base", BASES)
def test_a_striped_row_stands_apart_from_a_plain_one(base: str) -> None:
    plain = hex_color(token(base))
    assert contrast(over(token("row-alt"), plain), plain) >= STRIPE_MIN, base


@pytest.mark.parametrize("base", BASES)
@pytest.mark.parametrize("row", [None, *ROWS])
def test_the_line_under_a_row_shows_on_every_row_color(row: str | None, base: str) -> None:
    plain = hex_color(token(base))
    background = plain if row is None else over(token(row), plain)
    line = over(token("row-line"), background)
    assert contrast(line, background) >= LINE_MIN, (row, base)


@pytest.mark.parametrize("base", BASES)
def test_hover_and_selection_stand_out_over_the_stripe(base: str) -> None:
    """Hover is the accent's hue over the stripe's gray and lighter than it; the selected row is
    the lightest of the three and has the accent bar besides."""
    plain = hex_color(token(base))
    stripe, hover, picked = (luminance(over(token(row), plain)) for row in ROWS)
    assert contrast(over(token("row-hover"), plain), over(token("row-alt"), plain)) >= 1.05, base
    assert stripe < hover < picked, base


@pytest.mark.parametrize("base", BASES)
@pytest.mark.parametrize("row", ROWS)
def test_text_keeps_its_contrast_on_every_row_color(row: str, base: str) -> None:
    """A table sits on the page (`--bg`) or inside a card (`--surface`)."""
    plain = hex_color(token(base))
    background = over(token(row), plain)
    for ink in ("text", "muted", "accent"):
        assert contrast(hex_color(token(ink)), background) >= 4.5, (row, base, ink)
    # The tint is visible against the plain rows around it.
    assert contrast(background, plain) >= STRIPE_MIN, (row, base)
