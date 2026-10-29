"""The price chart, labelled; adjusted closes, splits and dividends; comparing symbols; the hover
readout; and Get history for several symbols (2026-10-29, decisions 133 to 139).

Every source is a CSV folder, a `MockTransport` or rows written straight into the table: no
request leaves the process, and the symbols are placeholders.
"""

import json
import re
from datetime import date, timedelta
from decimal import Decimal
from html import unescape
from pathlib import Path

import httpx
import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone
from pytest_django.fixtures import Settings

from invest_witus.prices.csv_file import PricePoint
from invest_witus_site.holdings.models import Account, Holding, Snapshot, SnapshotLine
from invest_witus_site.prices import manual, sources
from invest_witus_site.prices import pull as pull_module
from invest_witus_site.prices.charts import (
    LINE_STYLES,
    MAX_LINES,
    SeriesInput,
    build_plot,
    dividend_text,
    nice_step,
    rebased,
    split_text,
    x_ticks,
    y_scale,
)
from invest_witus_site.prices.models import DailyClose, ManualRun
from invest_witus_site.prices.points import AdjustedPoint, extras
from invest_witus_site.prices.pull import REQUESTS_PER_RUN
from invest_witus_site.prices.sources import CsvPrices, PriceSourceError, TiingoEod, parse_tiingo
from invest_witus_site.watchlist.models import WatchItem
from invest_witus_site.watchlist.views import pick_symbols

D = Decimal
TEST_KEY = "test-only-tiingo-key"
DAY = date(2026, 10, 20)


def adjusted(day: date, close: str, adj: str, split: str = "1", div: str = "0") -> AdjustedPoint:
    return AdjustedPoint(day, D(close), D(adj), D(split), D(div))


# --- Parsing Tiingo's adjusted close, split factor and dividend ----------------------------------


def test_tiingo_days_keep_the_adjusted_close_split_and_dividend_as_decimals() -> None:
    body = (
        '[{"date": "2026-10-20T00:00:00.000Z", "close": 400.12, "adjClose": 99.53, '
        '"splitFactor": 4.0, "divCash": 0.0},'
        ' {"date": "2026-10-21T00:00:00.000Z", "close": 101.5, "adjClose": 101.5, '
        '"splitFactor": 1.0, "divCash": 0.57}]'
    )
    first, second = parse_tiingo("INDEX", body)
    assert isinstance(first, AdjustedPoint) and isinstance(second, AdjustedPoint)
    assert extras(first) == (D("99.53"), D("4.0"), D("0.0"))
    assert extras(second) == (D("101.5"), D("1.0"), D("0.57"))
    assert type(first.adj_close) is Decimal, "never a float"


def test_a_day_without_the_extra_fields_is_a_plain_point() -> None:
    (point,) = parse_tiingo("INDEX", '[{"date": "2026-10-22", "close": 5, "adjClose": null}]')
    assert type(point) is PricePoint and extras(point) == (None, None, None)


@pytest.mark.parametrize(
    ("field", "value", "problem"),
    [
        ("adjClose", '"1"', "adjClose is not a number"),
        ("adjClose", "0", "adjClose must be positive"),
        ("splitFactor", "true", "splitFactor is not a number"),
        ("splitFactor", "-2", "splitFactor must be positive"),
        ("divCash", "-0.5", "divCash must not be negative"),
    ],
)
def test_a_bad_extra_field_is_refused_like_a_bad_close(
    field: str, value: str, problem: str
) -> None:
    with pytest.raises(PriceSourceError, match=problem):
        parse_tiingo("INDEX", f'[{{"date": "2026-10-22", "close": 5, "{field}": {value}}}]')


@pytest.mark.django_db
def test_tiingo_fields_reach_the_table(monkeypatch: pytest.MonkeyPatch) -> None:
    def answer(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {"date": "2026-10-20T00:00:00.000Z", "close": 400, "adjClose": 100.25,
                 "splitFactor": 4, "divCash": 0},
            ],
        )  # fmt: skip

    monkeypatch.setattr(sources, "transport", httpx.MockTransport(answer))
    points = TiingoEod(TEST_KEY).closes("INDEX", DAY, DAY)
    DailyClose.upsert("INDEX", points, "tiingo")
    row = DailyClose.objects.get(symbol="INDEX")
    assert (row.close, row.adj_close, row.split_factor, row.div_cash) == (
        D("400"),
        D("100.25"),
        D("4"),
        D("0"),
    )
    assert row.is_split and not row.is_dividend and row.charted == D("100.25")


# --- Storing them -------------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_chart_value_falls_back_to_the_close() -> None:
    DailyClose.upsert("OTHER", [PricePoint(DAY, D("20.5"))], "csv")
    row = DailyClose.objects.get(symbol="OTHER")
    assert row.adj_close is None and row.split_factor is None and row.div_cash is None
    assert row.charted == D("20.5") and not row.is_split and not row.is_dividend


@pytest.mark.django_db
def test_an_adjusted_close_arriving_for_a_stored_day_is_an_update_then_unchanged() -> None:
    DailyClose.upsert("INDEX", [PricePoint(DAY, D("100"))], "tiingo")
    first = DailyClose.upsert("INDEX", [adjusted(DAY, "100", "98.5")], "tiingo")
    assert (first.inserted, first.updated, first.unchanged) == (0, 1, 0)
    again = DailyClose.upsert("INDEX", [adjusted(DAY, "100", "98.5")], "tiingo")
    assert (again.updated, again.unchanged, again.rescaled) == (0, 1, 0)
    assert DailyClose.objects.get(symbol="INDEX").adj_close == D("98.5")


@pytest.mark.django_db
def test_a_new_split_rescales_the_stored_days_the_answer_did_not_cover() -> None:
    """A long history stored with adjusted closes, then a nightly week that includes a 2-for-1
    split: every stored day before the week is halved, as the vendor halves its own history."""
    history = [adjusted(DAY - timedelta(days=age), "200", "200") for age in range(30, 10, -1)]
    DailyClose.upsert("FUNDX", history, "tiingo")
    week_start = DAY - timedelta(days=6)
    week = [
        adjusted(week_start, "200", "100"),  # before the split: halved by the vendor now
        adjusted(week_start + timedelta(days=1), "200", "100"),
        adjusted(week_start + timedelta(days=2), "100", "100", split="2"),
    ]
    # The first day of the week was stored before (as 200), so the answer shows the new footing.
    DailyClose.upsert("FUNDX", [adjusted(week_start, "200", "200")], "tiingo")
    counts = DailyClose.upsert("FUNDX", week, "tiingo")
    assert counts.rescaled == 20 and "rescaled 20" in str(counts)
    old = DailyClose.objects.filter(symbol="FUNDX", date__lt=week_start)
    assert {row.adj_close for row in old} == {D("100")}
    assert {row.close for row in old} == {D("200")}, "the close itself never changes"
    nightly_again = DailyClose.upsert("FUNDX", week, "tiingo")
    assert nightly_again.rescaled == 0 and nightly_again.unchanged == 3


@pytest.mark.django_db
def test_no_rescale_without_a_stored_adjusted_close_to_compare() -> None:
    DailyClose.upsert("FUNDX", [PricePoint(DAY - timedelta(days=10), D("50"))], "tiingo")
    counts = DailyClose.upsert("FUNDX", [adjusted(DAY, "50", "25")], "tiingo")
    assert counts.rescaled == 0
    assert DailyClose.objects.get(symbol="FUNDX", date=DAY - timedelta(days=10)).adj_close is None


# --- The chart's numbers -------------------------------------------------------------------------


def row(day: date, close: str, adj: str | None = None, **extra: str) -> DailyClose:
    return DailyClose(
        symbol="INDEX",
        date=day,
        close=D(close),
        adj_close=None if adj is None else D(adj),
        split_factor=D(extra["split"]) if "split" in extra else None,
        div_cash=D(extra["div"]) if "div" in extra else None,
        source="tiingo",
    )


def test_rebasing_is_exact_decimal_arithmetic() -> None:
    assert rebased(D("550"), D("500")) == D("110")
    assert rebased(D("19"), D("20")) == D("95")
    assert rebased(D("0.1") + D("0.2"), D("0.3")) == D("100"), "no float drift"


def test_a_compare_plot_starts_every_line_at_100_and_reports_the_change() -> None:
    fund = [row(DAY, "500", "500"), row(DAY + timedelta(days=1), "550", "550")]
    stock = [row(DAY, "20", "20"), row(DAY + timedelta(days=1), "19", "19")]
    plot = build_plot([SeriesInput("FUNDX", fund), SeriesInput("OTHER", stock)], "t", True)
    assert plot is not None
    fundx, other = plot.lines
    assert [day.index for day in fundx.days] == [D("100"), D("110")]
    assert [day.index for day in other.days] == [D("100"), D("95")]
    assert (fundx.change_pct, other.change_pct) == (D("10"), D("-5"))
    assert plot.low == D("95") and plot.high == D("110")
    hover = plot.hover()
    assert hover["rebased"] is True and hover["dates"] == ["2026-10-20", "2026-10-21"]
    series = hover["series"]
    assert isinstance(series, list)
    assert series[1]["index"] == ["100.00", "95.00"] and series[1]["close"] == ["$20.00", "$19.00"]
    assert series[0]["change"] == [None, "+$50.00"] and series[0]["changePct"] == [None, "+10.00%"]


def test_a_line_uses_the_adjusted_close_only_when_every_day_has_one() -> None:
    whole = [row(DAY, "400", "100"), row(DAY + timedelta(days=1), "101", "101", split="4")]
    plot = build_plot([SeriesInput("INDEX", whole)], "t", False)
    assert plot is not None and plot.lines[0].basis == "adjusted close"
    assert plot.y_title == "Adjusted close, US dollars"
    assert [day.value for day in plot.lines[0].days] == [D("100"), D("101")], "no fake crash"
    partial = [row(DAY, "400"), row(DAY + timedelta(days=1), "101", "101")]
    fallback = build_plot([SeriesInput("INDEX", partial)], "t", False)
    assert fallback is not None and fallback.lines[0].basis == "close"
    assert fallback.lines[0].missing_adjusted == 1 and fallback.y_title == "Close, US dollars"


def test_the_first_days_change_uses_the_stored_day_before_the_range() -> None:
    before = row(DAY - timedelta(days=3), "98", "98")
    plot = build_plot([SeriesInput("INDEX", [row(DAY, "100", "100")], before)], "t", False)
    assert plot is not None
    (day,) = plot.lines[0].days
    assert day.change == D("2") and day.change_pct is not None
    assert f"{day.change_pct:.4f}" == "2.0408"


def test_split_and_dividend_markers_and_their_words() -> None:
    days = [
        row(DAY, "400", "100", split="1", div="0"),
        row(DAY + timedelta(days=1), "100", "100", split="4", div="0"),
        row(DAY + timedelta(days=2), "100", "100", split="1", div="0.57"),
    ]
    plot = build_plot([SeriesInput("INDEX", days)], "t", False)
    assert plot is not None
    assert [(m.kind, m.text, m.letter) for m in plot.markers] == [
        ("split", "Split 4-for-1", "S"),
        ("dividend", "Dividend $0.57", "D"),
    ]
    assert [kind for kind, _, _ in plot.marker_kinds] == ["split", "dividend"]
    events = plot.hover()["series"]
    assert isinstance(events, list) and events[0]["events"] == [
        None,
        "Split 4-for-1",
        "Dividend $0.57",
    ]
    assert split_text(D("0.1")) == "Reverse split 1-for-10"
    assert dividend_text(D("0.5734")) == "Dividend $0.5734"


@pytest.mark.parametrize(
    ("raw", "step"), [("0.7", "1"), ("1.3", "2"), ("2.2", "2.5"), ("3", "5"), ("37", "50")]
)
def test_nice_steps(raw: str, step: str) -> None:
    assert nice_step(D(raw)) == D(step)


def test_the_y_axis_brackets_the_values_with_round_numbers() -> None:
    assert y_scale(D("1180"), D("1234.5")) == (D("1180"), D("1240"), D("20"))
    bottom, top, _ = y_scale(D("5"), D("5"))
    assert bottom < D("5") < top, "a flat line gets room"


def test_the_x_axis_picks_mondays_months_or_years() -> None:
    month = x_ticks(date(2026, 9, 29), date(2026, 10, 28))
    assert [tick.label for tick in month] == ["Oct 5", "Oct 12", "Oct 19", "Oct 26"]
    year = x_ticks(date(2025, 10, 29), date(2026, 10, 28))
    assert [tick.label for tick in year] == ["Nov 2025", "Jan 2026", "Mar", "May", "Jul", "Sep"]
    assert any(tick.minor for tick in year), "every other label hides on a phone"
    decades = x_ticks(date(1999, 3, 10), date(2026, 10, 28))
    assert [tick.label for tick in decades] == ["2000", "2005", "2010", "2015", "2020", "2025"]
    assert decades[-1].edge == "end"


def contrast(color: str, background: str = "#020617") -> float:
    def luminance(hex_color: str) -> float:
        channels = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    light, dark = sorted((luminance(color), luminance(background)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def test_six_line_styles_differ_by_color_and_dash_and_pass_3_to_1() -> None:
    assert MAX_LINES == 6
    assert len({color for color, _, _ in LINE_STYLES}) == 6
    assert len({dash for _, dash, _ in LINE_STYLES}) == 6, "not color alone"
    assert all(contrast(color) >= 3 for color, _, _ in LINE_STYLES)


def test_pick_symbols_keeps_the_order_and_the_limit() -> None:
    allowed = ["A", "B", "C", "D", "E", "F", "G", "INDEX"]
    picked = pick_symbols(["a,b", "C", "x", "b", "D,E,F,G"], allowed)
    assert picked.symbols == ["A", "B", "C", "D", "E", "F"]
    assert picked.not_allowed == ["X"] and picked.over_limit == ["G"]


# --- The pages -----------------------------------------------------------------------------------


def today() -> date:
    return timezone.localdate()


@pytest.fixture(autouse=True)
def no_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pull_module, "PAUSE_SECONDS", 0.0)


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("owner", email="owner@example.com")


@pytest.fixture
def someone(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("someone")


@pytest.fixture
def account(owner: User) -> Account:
    """INDEX held (and cash), FUNDX and OTHER watched, with closes the last five days; FUNDX
    with a 4-for-1 split two days ago and a dividend yesterday."""
    account = Account.objects.create(
        name="Practice", broker="Example Broker", kind="paper", owner=owner
    )
    snapshot = Snapshot.objects.create(account=account, as_of=date(2026, 10, 1), source="test")
    for symbol, shares in (("INDEX", "2.5"), ("CASH", "500")):
        SnapshotLine.objects.create(snapshot=snapshot, symbol=symbol, shares=D(shares))
    Holding.objects.filter(account=account, symbol="CASH").update(kind=Holding.Kind.CASH)
    WatchItem.add_many(account, ["FUNDX", "OTHER"])
    for symbol, base in (("INDEX", 100), ("FUNDX", 500), ("OTHER", 20)):
        points: list[PricePoint] = []
        for age in range(5, 0, -1):
            day = today() - timedelta(days=age)
            close = D(base + 5 - age)
            split = "4" if symbol == "FUNDX" and age == 2 else "1"
            div = "0.57" if symbol == "FUNDX" and age == 1 else "0"
            points.append(AdjustedPoint(day, close, close, D(split), D(div)))
        DailyClose.upsert(symbol, points, "tiingo")
    return account


def text(response: object) -> str:
    content = getattr(response, "content")  # noqa: B009
    assert isinstance(content, bytes)
    return unescape(content.decode())


def compare_url(account: Account, query: str = "") -> str:
    return f"/accounts/{account.pk}/compare/{query}"


def chart_data(html: str) -> dict[str, object]:
    found = re.search(r'<script id="chart-data" type="application/json">(.*?)</script>', html)
    assert found is not None
    loaded = json.loads(found.group(1))
    assert isinstance(loaded, dict)
    return loaded  # type: ignore[return-value]


@pytest.mark.django_db
def test_the_history_chart_has_a_title_axes_key_source_and_caption(
    client: Client, owner: User, account: Account
) -> None:
    client.force_login(owner)
    html = text(client.get(f"/accounts/{account.pk}/watch/FUNDX/?days=30"))
    assert '<p class="chart-title" id="chart-heading">FUNDX, last 30 days</p>' in html
    assert "Daily closes from Tiingo, as of" in html
    assert '<p class="axis-title axis-y">Adjusted close, US dollars</p>' in html
    assert '<p class="axis-title axis-x">Date</p>' in html
    assert re.search(
        r'<div class="chart-y" aria-hidden="true">\s*<span style="top: [\d.]+%">\$', html
    )
    assert '<ul class="legend" aria-label="Key">' in html
    assert 'FUNDX <span class="muted">(adjusted close, solid line)</span>' in html
    assert "Split</li>" in html and "Dividend (ex-date)</li>" in html
    assert "<caption>Splits and dividends from" in html
    assert "<td>Split 4-for-1</td>" in html and "<td>Dividend $0.57</td>" in html
    assert '<caption id="closes-caption">FUNDX, every stored day in the last 30 days' in html
    for header in ("Date", "Close", "Adjusted close", "Change", "Change %", "Split or dividend"):
        assert f">{header}</th>" in html
    assert '<title id="chart-title">' in html and '<desc id="chart-desc">' in html
    assert 'aria-live="polite"' in html
    assert f"/accounts/{account.pk}/compare/?symbols=FUNDX&days=30" in html


@pytest.mark.django_db
def test_the_hover_data_holds_the_formatted_values(
    client: Client, owner: User, account: Account
) -> None:
    client.force_login(owner)
    data = chart_data(text(client.get(f"/accounts/{account.pk}/watch/FUNDX/?days=30")))
    assert data["rebased"] is False and len(data["dates"]) == 5  # type: ignore[arg-type]
    (series,) = data["series"]  # type: ignore[misc]
    assert series["close"][-1] == "$504.00" and series["adj"][-1] == "$504.00"
    assert series["change"][-1] == "+$1.00" and series["changePct"][-1] == "+0.20%"
    assert series["events"][-1] == "Dividend $0.57"


@pytest.mark.django_db
def test_the_compare_page_rebases_and_tabulates_the_owners_symbols(
    client: Client, owner: User, account: Account
) -> None:
    client.force_login(owner)
    html = text(client.get(compare_url(account, "?symbols=FUNDX,INDEX,OTHER&days=30")))
    assert '<p class="chart-title" id="chart-heading">FUNDX, INDEX, OTHER: last 30 days</p>' in html
    assert "so a $500 fund and a $20 stock compare fairly" in html
    assert "rebased so its first day in the range is 100" in html
    assert html.count("<polyline ") == 3
    assert "Value, with each line's first day in the range at 100" in html
    assert '<td class="num">$500.00</td>' in html and '<td class="num">$504.00</td>' in html
    assert '<td class="num">+0.80%</td>' in html, "FUNDX 500 to 504"
    assert '<td class="num">+20.00%</td>' in html, "OTHER 20 to 24"
    assert "Every day's values" in html and '<td class="num">120.00</td>' in html
    # The checkboxes offer the watch list and the holdings, not cash.
    for symbol in ("FUNDX", "INDEX", "OTHER"):
        assert f'value="{symbol}" checked' in html
    assert 'value="CASH"' not in html
    assert '<script src="/static/prices/chart.js" defer></script>' in html


@pytest.mark.django_db
def test_compare_refuses_symbols_outside_the_account_and_over_six(
    client: Client, owner: User, account: Account
) -> None:
    client.force_login(owner)
    html = text(client.get(compare_url(account, "?symbols=FUNDX,NOPE,CASH")))
    assert "left out: NOPE, CASH." in html and html.count("<polyline ") == 1
    WatchItem.add_many(account, ["S1", "S2", "S3", "S4", "S5"])
    many = "FUNDX,INDEX,OTHER,S1,S2,S3,S4,S5"
    html = text(client.get(compare_url(account, f"?symbols={many}")))
    assert "Up to 6 symbols at once; left out: S4, S5." in html
    assert "No closes stored in the last 365 days for S1, S2, S3." in html
    assert html.count("<polyline ") == 3


@pytest.mark.django_db
def test_the_compare_page_is_the_owners_only(
    client: Client, owner: User, someone: User, account: Account
) -> None:
    signed_out = client.get(compare_url(account))
    assert signed_out.status_code == 302 and "/auth/witus/login/" in signed_out["Location"]
    client.force_login(someone)
    assert client.get(compare_url(account, "?symbols=FUNDX")).status_code == 404
    client.force_login(owner)
    assert client.get(compare_url(account)).status_code == 200
    assert client.post(compare_url(account)).status_code == 405


@pytest.mark.django_db
def test_the_hover_script_is_served_on_chart_pages_only(
    client: Client, owner: User, account: Account
) -> None:
    client.force_login(owner)
    tag = '<script src="/static/prices/chart.js" defer></script>'
    assert tag in text(client.get(f"/accounts/{account.pk}/watch/FUNDX/"))
    assert tag in text(client.get(compare_url(account, "?symbols=FUNDX")))
    assert tag not in text(client.get(compare_url(account))), "no symbols, no chart, no script"
    for path in (f"/accounts/{account.pk}/", "/accounts/", f"/accounts/{account.pk}/logbook/"):
        assert "chart.js" not in text(client.get(path))
    script = (
        Path(__file__).parents[1] / "src/invest_witus_site/prices/static/prices/chart.js"
    ).read_text()
    assert '"ArrowLeft"' in script and '"ArrowRight"' in script and "tabIndex = 0" in script
    assert "innerHTML" not in script, "the readout is written as text"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path", ["/", "/faq/", "/privacy/", "/terms/", "/contact/", "/waitlist/", "/auth/witus/login/"]
)
def test_public_pages_stay_script_free_and_chart_free(
    client: Client, account: Account, path: str
) -> None:
    html = client.get(path).content.decode()
    assert "<script" not in html and "chart-data" not in html and "/compare/" not in html
    assert "$504.00" not in html


@pytest.mark.django_db
def test_the_watch_list_links_compare_and_offers_bulk_history(
    client: Client, owner: User, account: Account
) -> None:
    client.force_login(owner)
    html = text(client.get(f"/accounts/{account.pk}/"))
    assert f'href="/accounts/{account.pk}/compare/?symbols=FUNDX,OTHER"' in html
    assert 'name="symbols" value="FUNDX" form="bulk-history"' in html
    assert 'name="which" value="selected">Fetch history for selected</button>' in html
    assert 'name="which" value="all">Fetch history for all</button>' in html


# --- Fetch history for selected and for all -------------------------------------------------------


@pytest.fixture
def csv_folder(tmp_path: Path, settings: Settings) -> Path:
    for symbol, close in (("FUNDX", "12.34"), ("OTHER", "20.50"), ("INDEX", "101.25")):
        day = today() - timedelta(days=400)
        (tmp_path / f"{symbol}.csv").write_text(f"date,close\n{day.isoformat()},{close}\n")
    settings.TIINGO_API_KEY = ""
    settings.PRICES_CSV_DIR = tmp_path
    return tmp_path


def many_url(account: Account) -> str:
    return f"/accounts/{account.pk}/watch/fetch-history/"


@pytest.mark.django_db
def test_fetch_history_for_selected_asks_only_the_ticked_symbols(
    client: Client, owner: User, account: Account, csv_folder: Path
) -> None:
    client.force_login(owner)
    response = client.post(
        many_url(account), {"which": "selected", "symbols": ["OTHER", "INDEX"], "range": "5y"}
    )
    assert response.status_code == 302 and response["Location"] == f"/accounts/{account.pk}/"
    html = text(client.get(response["Location"]))
    stored = f"{today() - timedelta(days=400):%Y-%m-%d}"
    assert f"OTHER, 5 years: 1 day added, 0 updated; earliest close stored {stored}." in html
    assert "Not on this watch list, so left out: INDEX." in html, "held, not watched"
    assert "FUNDX, 5 years" not in html
    assert list(ManualRun.objects.values_list("key", flat=True)) == ["OTHER"]


@pytest.mark.django_db
def test_fetch_history_for_all_asks_every_watched_symbol_and_skips_guarded_ones(
    client: Client, owner: User, account: Account, csv_folder: Path
) -> None:
    manual.claim(ManualRun.Kind.HISTORY, "OTHER")
    client.force_login(owner)
    html = text(client.post(many_url(account), {"which": "all", "range": "all"}, follow=True))
    assert "FUNDX, all available: 1 day added" in html
    assert "Skipped, fetched less than 10 minutes ago" in html and "OTHER (at " in html
    assert "OTHER, all available" not in html


@pytest.mark.django_db
def test_fetch_history_for_selected_needs_a_tick_and_a_range(
    client: Client, owner: User, account: Account, csv_folder: Path
) -> None:
    client.force_login(owner)
    html = text(client.post(many_url(account), {"which": "selected", "range": "1y"}, follow=True))
    assert "Tick or type at least one symbol on this list, or press Fetch history for all." in html
    html = text(client.post(many_url(account), {"which": "all", "range": "3y"}, follow=True))
    assert "Pick a range:" in html and not ManualRun.objects.exists()


def test_fetch_history_many_stops_at_the_budget_and_names_the_rest(
    csv_folder: Path, db: None
) -> None:
    symbols = [f"S{number:02d}" for number in range(REQUESTS_PER_RUN + 2)]
    result = manual.fetch_history_many(CsvPrices(csv_folder), symbols, DAY, today())
    assert result.requests == 50 and result.stopped == "budget"
    assert result.not_reached == ["S50", "S51"] and len(result.failed) == 50
    _, _, infos = manual.many_messages(result, "1 year")
    assert infos[-1] == (
        "Stopped by the 50-request limit for one run. The rest: press again in 60 minutes: "
        "S50, S51."
    )


def test_fetch_history_many_stops_at_the_time_limit(csv_folder: Path, db: None) -> None:
    ticks = iter([0.0, 0.0, 300.0])
    result = manual.fetch_history_many(
        CsvPrices(csv_folder), ["FUNDX", "OTHER", "INDEX"], DAY, today(), clock=lambda: next(ticks)
    )
    assert (result.requests, result.not_reached, result.stopped) == (
        1,
        ["OTHER", "INDEX"],
        "time limit",
    )
    assert "press again in 1 minute: OTHER, INDEX." in manual.many_messages(result, "x")[2][-1]


def test_a_429_stops_fetch_history_many(monkeypatch: pytest.MonkeyPatch, db: None) -> None:
    monkeypatch.setattr(
        sources, "transport", httpx.MockTransport(lambda request: httpx.Response(429))
    )
    result = manual.fetch_history_many(TiingoEod(TEST_KEY), ["FUNDX", "OTHER"], DAY, today())
    assert result.stopped == "rate limit" and result.not_reached == ["OTHER"]
    assert list(result.failed) == ["FUNDX"]


@pytest.mark.django_db
def test_fetch_history_many_is_the_owners_and_post_only(
    client: Client, owner: User, someone: User, account: Account, csv_folder: Path
) -> None:
    client.force_login(someone)
    assert client.post(many_url(account), {"which": "all", "range": "1y"}).status_code == 404
    client.force_login(owner)
    assert client.get(many_url(account)).status_code == 405
    strict = Client(enforce_csrf_checks=True)
    strict.force_login(owner)
    assert strict.post(many_url(account), {"which": "all", "range": "1y"}).status_code == 403
    assert not ManualRun.objects.exists()


# --- The statements comparison's split note -------------------------------------------------------


def statements_path(account: Account) -> str:
    return f"/admin/holdings/account/{account.pk}/statements/"


@pytest.mark.django_db
def test_a_split_between_two_statements_is_noted_under_the_symbol(
    admin_client: Client, owner: User
) -> None:
    account = Account.objects.create(name="Splits", broker="Example", kind="paper", owner=owner)
    for as_of, shares in ((date(2026, 6, 30), "10"), (date(2026, 9, 30), "41")):
        snapshot = Snapshot.objects.create(account=account, as_of=as_of, source="test")
        SnapshotLine.objects.create(snapshot=snapshot, symbol="FUNDX", shares=D(shares))
        SnapshotLine.objects.create(snapshot=snapshot, symbol="INDEX", shares=D("3"))
    DailyClose.upsert("FUNDX", [adjusted(date(2026, 7, 15), "100", "100", split="4")], "tiingo")
    DailyClose.upsert("FUNDX", [adjusted(date(2026, 6, 30), "400", "100", split="1")], "tiingo")
    html = text(admin_client.get(statements_path(account)))
    assert (
        "FUNDX: A 4-for-1 split on 2026-07-15 explains a share change of this size: 10 shares "
        "before it are 40 after it. The statement shows 41; the other 1 came from buying, "
        "selling or reinvesting."
    ) in html
    assert "INDEX: A" not in html
    assert html.count('class="split-note"') == 1
    assert SnapshotLine.objects.filter(symbol="FUNDX", shares=D("10")).exists(), "unchanged"


@pytest.mark.django_db
def test_a_split_on_the_earlier_statement_date_is_already_in_it(
    admin_client: Client, owner: User
) -> None:
    account = Account.objects.create(name="Splits", broker="Example", kind="paper", owner=owner)
    for as_of, shares in ((date(2026, 6, 30), "40"), (date(2026, 9, 30), "40")):
        snapshot = Snapshot.objects.create(account=account, as_of=as_of, source="test")
        SnapshotLine.objects.create(snapshot=snapshot, symbol="FUNDX", shares=D(shares))
    DailyClose.upsert("FUNDX", [adjusted(date(2026, 6, 30), "100", "100", split="4")], "tiingo")
    assert 'class="split-note"' not in text(admin_client.get(statements_path(account)))


@pytest.mark.django_db
def test_a_split_that_explains_the_whole_change_says_so(admin_client: Client, owner: User) -> None:
    account = Account.objects.create(name="Splits", broker="Example", kind="paper", owner=owner)
    for as_of, shares in ((date(2026, 6, 30), "30"), (date(2026, 9, 30), "3")):
        snapshot = Snapshot.objects.create(account=account, as_of=as_of, source="test")
        SnapshotLine.objects.create(snapshot=snapshot, symbol="OTHER", shares=D(shares))
    DailyClose.upsert("OTHER", [adjusted(date(2026, 8, 3), "50", "50", split="0.1")], "tiingo")
    html = text(admin_client.get(statements_path(account)))
    assert "A 1-for-10 reverse split on 2026-08-03" in html and "That is the whole change." in html
