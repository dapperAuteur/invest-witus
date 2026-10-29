"""Chart ranges (2026-10-29, decision 135): the presets 30, 90 and 365 days plus 5 years, 10 years
and All; a From and To pair, checked; long ranges thinned for drawing; the day tables paged.

Rows are written straight into the table: no request leaves the process, and the symbols are
placeholders.
"""

import json
import re
from datetime import date, timedelta
from decimal import Decimal
from html import unescape
from typing import Protocol

import pytest
from django.contrib.auth.models import User
from django.http import QueryDict
from django.test import Client
from django.utils import timezone

from invest_witus_site.holdings.models import Account
from invest_witus_site.prices.charts import MAX_POINTS, SeriesInput, build_plot, thin
from invest_witus_site.prices.history import (
    PRESETS,
    RangeError,
    StoredSpan,
    chosen_range,
)
from invest_witus_site.prices.models import DailyClose
from invest_witus_site.watchlist.models import WatchItem
from invest_witus_site.watchlist.views import ROWS_PER_PAGE

D = Decimal
# FUNDX's stored days, as ages before today: 30 days holds 2, 90 holds 3, 365 holds 4, 5 years
# 6, 10 years 7, All 8.
AGES = (1, 20, 60, 200, 400, 1000, 2000, 4000)
NOW = timezone.now()


def today() -> date:
    return timezone.localdate()


def ago(days: int) -> date:
    return today() - timedelta(days=days)


class Page(Protocol):
    content: bytes
    status_code: int


def text(response: Page) -> str:
    return unescape(response.content.decode())


def table_dates(html: str) -> list[str]:
    """The closes table's row headers (the history page's only `scope="row"` dates)."""
    return re.findall(r'<th scope="row">(\d{4}-\d{2}-\d{2})</th>', html)


def polyline_points(html: str) -> list[str]:
    found = re.search(r'<polyline points="([^"]*)"', html)
    assert found is not None, "no polyline"
    return found.group(1).split()


def chart_data(html: str) -> dict[str, object]:
    found = re.search(r'<script id="chart-data" type="application/json">(.*?)</script>', html)
    assert found is not None
    loaded = json.loads(found.group(1))
    assert isinstance(loaded, dict)
    return loaded  # type: ignore[return-value]


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("owner")


@pytest.fixture
def someone(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("someone")


@pytest.fixture
def account(owner: User) -> Account:
    """FUNDX and OTHER watched. FUNDX has a close at each of `AGES`; OTHER at 1000, 400 and 1."""
    account = Account.objects.create(
        name="Practice", broker="Example Broker", kind="paper", owner=owner
    )
    WatchItem.add_many(account, ["FUNDX", "OTHER"])
    DailyClose.objects.bulk_create(
        [
            DailyClose(
                symbol="FUNDX", date=ago(age), close=D(5000 - age), source="csv", fetched_at=NOW
            )
            for age in AGES
        ]
        + [
            DailyClose(symbol="OTHER", date=ago(age), close=D(close), source="csv", fetched_at=NOW)
            for age, close in ((1000, "20"), (400, "25"), (1, "30"))
        ]
    )
    return account


def history(client: Client, account: Account, query: str = "") -> Page:
    return client.get(f"/accounts/{account.pk}/watch/FUNDX/{query}")


def compare(client: Client, account: Account, query: str) -> Page:
    return client.get(f"/accounts/{account.pk}/compare/{query}")


# --- Presets ------------------------------------------------------------------------------------


def test_the_presets_keep_the_three_defaults_first() -> None:
    assert [preset.key for preset in PRESETS] == ["30", "90", "365", "5y", "10y", "all"]
    assert [preset.label for preset in PRESETS][3:] == ["5 years", "10 years", "All"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("query", "count", "title"),
    [
        ("?days=30", 2, "last 30 days"),
        ("?days=90", 3, "last 90 days"),
        ("", 3, "last 90 days"),
        ("?days=365", 4, "last 365 days"),
        ("?days=5y", 6, "last 5 years"),
        ("?days=10y", 7, "last 10 years"),
        ("?days=all", 8, "all stored days"),
        ("?days=7y", 3, "last 90 days"),
    ],
)
def test_each_preset_sets_the_chart_and_the_table(
    client: Client, owner: User, account: Account, query: str, count: int, title: str
) -> None:
    client.force_login(owner)
    response = history(client, account, query)
    assert response.status_code == 200
    html = text(response)
    assert f'<p class="chart-title" id="chart-heading">FUNDX, {title}</p>' in html
    assert len(polyline_points(html)) == count and len(table_dates(html)) == count
    current = {"last 5 years": "5 years", "last 10 years": "10 years", "all stored days": "All"}
    label = current.get(title, title.removeprefix("last "))
    assert f'<strong aria-current="page">{label}</strong>' in html


@pytest.mark.django_db
def test_compare_offers_the_long_presets_and_opens_on_a_year(
    client: Client, owner: User, account: Account
) -> None:
    client.force_login(owner)
    html = text(compare(client, account, "?symbols=FUNDX,OTHER"))
    assert '<option value="365" selected>365 days</option>' in html
    for key, label in (("5y", "5 years"), ("10y", "10 years"), ("all", "All")):
        assert f'<option value="{key}">{label}</option>' in html
    html = text(compare(client, account, "?symbols=FUNDX,OTHER&days=5y"))
    assert "FUNDX, OTHER: last 5 years</p>" in html and html.count("<polyline ") == 2


# --- A From and To pair -------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_custom_range_sets_the_chart_and_the_table(
    client: Client, owner: User, account: Account
) -> None:
    client.force_login(owner)
    start, end = ago(1100), ago(50)
    html = text(history(client, account, f"?from={start:%Y-%m-%d}&to={end:%Y-%m-%d}"))
    expected = [f"{ago(age):%Y-%m-%d}" for age in (60, 200, 400, 1000)]
    assert table_dates(html) == expected, "newest first, only the days in the pair"
    assert len(polyline_points(html)) == 4
    assert f"FUNDX, {start:%Y-%m-%d} to {end:%Y-%m-%d}</p>" in html
    assert f"every stored day from {start:%Y-%m-%d} to {end:%Y-%m-%d}" in html
    assert f'value="{start:%Y-%m-%d}"' in html and f'value="{end:%Y-%m-%d}"' in html
    # The date inputs are bounded by the stored closes.
    assert f'min="{ago(4000):%Y-%m-%d}" max="{ago(1):%Y-%m-%d}"' in html
    # The compare link keeps the pair.
    assert f"?symbols=FUNDX&from={start:%Y-%m-%d}&to={end:%Y-%m-%d}" in html


@pytest.mark.django_db
def test_compare_rebases_on_the_first_day_of_the_chosen_range(
    client: Client, owner: User, account: Account
) -> None:
    client.force_login(owner)
    start, end = ago(450), ago(1)
    html = text(
        compare(client, account, f"?symbols=FUNDX,OTHER&from={start:%Y-%m-%d}&to={end:%Y-%m-%d}")
    )
    data = chart_data(html)
    first = f"{ago(400):%Y-%m-%d}"
    assert data["dates"][0] == first  # type: ignore[index]
    for series in data["series"]:  # type: ignore[attr-defined]
        assert series["index"][0] == "100.00", series["symbol"]
    # OTHER: 25 on the range's first day, 30 at the end, so +20%; its 1000-day close is outside.
    assert '<td class="num">+20.00%</td>' in html
    assert f"<td>{first}</td>" in html


@pytest.mark.parametrize(
    ("start", "end", "words"),
    [
        ("2020-05-01", "", "Pick both a From date and a To date"),
        ("", "2020-05-01", "Pick both a From date and a To date"),
        ("2020-13-01", "2021-01-01", "From is not a date in the form YYYY-MM-DD"),
        ("2020-01-01", "tomorrow", "To is not a date in the form YYYY-MM-DD"),
        ("2021-01-01", "2020-01-01", "From (2021-01-01) must be before To (2020-01-01)."),
        ("2020-01-01", "2020-01-01", "must be before To"),
        ("2009-12-31", "2020-01-01", "Pick dates within the stored closes, 2010-01-04 to"),
        ("2015-01-01", "2026-01-01", "Pick dates within the stored closes"),
    ],
)
def test_a_bad_pair_is_refused_with_its_reason(start: str, end: str, words: str) -> None:
    span = StoredSpan(date(2010, 1, 4), date(2025, 12, 31))
    with pytest.raises(RangeError, match=re.escape(words)):
        chosen_range(QueryDict(f"from={start}&to={end}"), date(2026, 1, 2), span)


def test_a_pair_with_nothing_stored_is_refused() -> None:
    with pytest.raises(RangeError, match="No closes are stored yet"):
        chosen_range(
            QueryDict("from=2020-01-01&to=2020-02-01"), date(2026, 1, 2), StoredSpan(None, None)
        )


@pytest.mark.django_db
def test_an_invalid_range_is_a_400_with_the_reason_and_the_default_range(
    client: Client, owner: User, account: Account
) -> None:
    client.force_login(owner)
    response = history(client, account, f"?from={ago(10):%Y-%m-%d}&to={ago(20):%Y-%m-%d}")
    assert response.status_code == 400
    html = text(response)
    assert '<p class="message error" id="range-error" role="alert">From (' in html
    assert "must be before To" in html and "Showing the last 90 days instead." in html
    assert 'aria-describedby="range-error"' in html
    assert len(table_dates(html)) == 3, "the default range under the error"
    response = compare(
        client, account, f"?symbols=FUNDX&from={ago(9000):%Y-%m-%d}&to={ago(5):%Y-%m-%d}"
    )
    assert response.status_code == 400
    assert "Pick dates within the stored closes" in text(response)
    assert "Showing the last 365 days instead." in text(response)


# --- Thinning and pages -------------------------------------------------------------------------


def test_thin_keeps_a_short_range_whole_and_a_long_one_near_the_limit() -> None:
    days = [date(2000, 1, 1) + timedelta(days=n) for n in range(2500)]
    assert thin(days[:MAX_POINTS], set(), MAX_POINTS) == days[:MAX_POINTS]
    kept = {days[777], days[778]}
    drawn = thin(days, kept, MAX_POINTS)
    assert MAX_POINTS <= len(drawn) <= MAX_POINTS + 2
    assert drawn[0] == days[0] and drawn[-1] == days[-1] and kept <= set(drawn)
    assert drawn == sorted(set(drawn))


def test_a_thinned_plot_draws_fewer_points_but_keeps_every_day_and_event() -> None:
    rows = [
        DailyClose(
            symbol="FUNDX",
            date=date(2000, 1, 1) + timedelta(days=n),
            close=D(100 + n),
            adj_close=D(100 + n),
            split_factor=D("2") if n == 1234 else D(1),
            div_cash=D(0),
            source="tiingo",
        )
        for n in range(3000)
    ]
    plot = build_plot([SeriesInput("FUNDX", rows)], "FUNDX", rebase=False)
    assert plot is not None and plot.thinned
    assert plot.total_days == 3000 and len(plot.lines[0].days) == 3000
    assert len(plot.dates) == MAX_POINTS == plot.count
    assert len(plot.lines[0].points.split()) == MAX_POINTS
    assert date(2000, 1, 1) + timedelta(days=1234) in plot.dates, "the split day is drawn"
    assert len(plot.hover()["dates"]) == MAX_POINTS  # type: ignore[arg-type]
    assert len(plot.daily_rows()) == 3000
    small = build_plot([SeriesInput("FUNDX", rows[:200])], "FUNDX", rebase=False)
    assert small is not None and not small.thinned and len(small.dates) == 200


@pytest.fixture
def long_history(account: Account) -> int:
    """1,500 daily closes for FUNDX ending yesterday, rising, on top of the fixture's eight."""
    DailyClose.objects.filter(symbol="FUNDX").delete()
    DailyClose.objects.bulk_create(
        [
            DailyClose(
                symbol="FUNDX", date=ago(1500 - n), close=D(100 + n), source="csv", fetched_at=NOW
            )
            for n in range(1500)
        ]
    )
    return 1500


@pytest.mark.django_db
def test_a_long_range_is_thinned_on_the_page_and_the_table_paged(
    client: Client, owner: User, account: Account, long_history: int
) -> None:
    client.force_login(owner)
    html = text(history(client, account, "?days=all"))
    assert len(polyline_points(html)) == MAX_POINTS
    assert f'data-points="{MAX_POINTS}"' in html
    assert f"This range has {long_history} stored days." in html
    assert f"it draws {MAX_POINTS} of them" in html and "the table below lists every day" in html
    dates = table_dates(html)
    assert len(dates) == ROWS_PER_PAGE and dates[0] == f"{ago(1):%Y-%m-%d}"
    assert f"Rows 1 to 100 of {long_history}, page 1 of 15." in html
    assert '<a href="?days=all&page=2#closes" rel="next">Older</a>' in html
    page = text(history(client, account, "?days=all&page=15"))
    assert table_dates(page)[-1] == f"{ago(1500):%Y-%m-%d}"
    assert "Rows 1401 to 1500 of 1500, page 15 of 15." in page and 'rel="prev"' in page
    assert "Rows 1401 to 1500" in text(history(client, account, "?days=all&page=99"))
    # Ninety days fits on one page: no pager, no thinning note.
    short = text(history(client, account, "?days=90"))
    assert "page 1 of" not in short and "This range has" not in short


@pytest.mark.django_db
def test_the_compare_days_table_is_paged_and_keeps_symbols_and_range(
    client: Client, owner: User, account: Account, long_history: int
) -> None:
    client.force_login(owner)
    html = text(compare(client, account, "?symbols=FUNDX,OTHER&days=all"))
    assert html.count("<polyline ") == 2 and "This range has 1500 stored days." in html
    assert '<details class="daily" id="daily">' in html
    assert "?symbols=FUNDX,OTHER&days=all&page=2#daily" in html
    page = text(compare(client, account, "?symbols=FUNDX,OTHER&days=all&page=2"))
    assert '<details class="daily" id="daily" open>' in page
    assert "Rows 101 to 200 of 1500, page 2 of 15." in page


# --- Ownership ----------------------------------------------------------------------------------


@pytest.mark.django_db
def test_another_owner_gets_a_404_whatever_the_range(
    client: Client, someone: User, account: Account
) -> None:
    client.force_login(someone)
    for query in ("?days=all", f"?from={ago(400):%Y-%m-%d}&to={ago(1):%Y-%m-%d}", "?page=2"):
        assert history(client, account, query).status_code == 404
        assert compare(client, account, f"?symbols=FUNDX&{query[1:]}").status_code == 404


@pytest.mark.django_db
def test_signed_out_is_sent_to_sign_in(client: Client, account: Account) -> None:
    response = history(client, account, "?days=10y")
    assert response.status_code == 302
