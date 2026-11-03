"""Alternating row colors on every table (2026-11-03, decision 164).

Every table the app draws is a `.holdings` table with a `<tbody>`, so one rule in `site.css`
stripes them all; the admin's own tables keep Django's stripes. The hover and the ticked-checkbox
row stay visible over the stripe, and text keeps WCAG 2.2's 4.5:1 on every row color (the
fallback rgba values are checked, which the color-mix() values equal on this theme)."""

import re
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parent.parent / "src" / "invest_witus_site"
CSS = (SITE / "pages" / "static" / "pages" / "site.css").read_text()
TEMPLATES = sorted(
    path for path in SITE.rglob("templates/**/*.html") if "/templates/admin/" not in str(path)
)


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
    assert "color-mix(in srgb, var(--text) 5%, transparent)" in CSS


@pytest.mark.parametrize("base", ["bg", "surface"])
@pytest.mark.parametrize("row", ["row-alt", "row-hover", "row-selected"])
def test_text_keeps_its_contrast_on_every_row_color(row: str, base: str) -> None:
    """A table sits on the page (`--bg`) or inside a card (`--surface`)."""
    plain = hex_color(token(base))
    background = over(token(row), plain)
    for ink in ("text", "muted", "accent"):
        assert contrast(hex_color(token(ink)), background) >= 4.5, (row, base, ink)
    # The tint is visible against the plain rows around it.
    assert contrast(background, plain) > 1.05, (row, base)
