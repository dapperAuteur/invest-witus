"""The price chart, labelled; adjusted closes, splits and dividends; comparing symbols; the hover
readout; and Get history for several symbols (2026-10-29, decisions 119 to 125).

Every source is a CSV folder, a `MockTransport` or rows written straight into the table: no
request leaves the process, and the symbols are placeholders.
"""

from datetime import date, timedelta
from decimal import Decimal

import httpx
import pytest

from invest_witus.prices.csv_file import PricePoint
from invest_witus_site.prices import sources
from invest_witus_site.prices.models import DailyClose
from invest_witus_site.prices.points import AdjustedPoint, extras
from invest_witus_site.prices.sources import PriceSourceError, TiingoEod, parse_tiingo

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
