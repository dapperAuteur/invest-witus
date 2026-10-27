import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from invest_witus.cli import main
from invest_witus.prices.csv_file import (
    PriceFileError,
    PricePoint,
    first_trading_day_of_each_month,
    load_prices,
)

SAMPLE = Path(__file__).parent.parent / "data" / "sample" / "illustrative-daily-prices.csv"


def write_csv(folder: Path, text: str) -> Path:
    path = folder / "prices.csv"
    path.write_text(text, encoding="utf-8")
    return path


def test_the_sample_file_loads_in_date_order() -> None:
    points = load_prices(SAMPLE)
    assert points[0] == PricePoint(day=date(2024, 10, 1), close=Decimal("100.00"))
    assert points[-1].day == date(2026, 9, 30)
    assert [p.day for p in points] == sorted(p.day for p in points)


def test_rows_out_of_order_come_back_sorted(tmp_path: Path) -> None:
    path = write_csv(tmp_path, "date,close\n2026-01-06,11\n2026-01-05,10\n")
    assert [p.close for p in load_prices(path)] == [Decimal("10"), Decimal("11")]


@pytest.mark.parametrize(
    "text, line, problem",
    [
        ("day,price\n2026-01-05,10\n", 1, "missing column(s): date, close"),
        ("date,close\n2026-01-05,10\n01/06/2026,11\n", 3, "not a YYYY-MM-DD date"),
        ("date,close\n2026-01-05,ten\n", 2, "not a number"),
        ("date,close\n2026-01-05,-3\n", 2, "price must be positive"),
        ("date,close\n2026-01-05,10\n2026-01-05,11\n", 3, "appears twice"),
        ("date,close\n", 1, "no prices"),
    ],
)
def test_bad_files_name_the_line_and_the_problem(
    tmp_path: Path, text: str, line: int, problem: str
) -> None:
    path = write_csv(tmp_path, text)
    with pytest.raises(PriceFileError, match=re.escape(problem)) as info:
        load_prices(path)
    assert info.value.line == line


def test_first_trading_day_skips_the_weekend() -> None:
    points = [
        PricePoint(date(2026, 1, 30), Decimal("10")),
        PricePoint(date(2026, 2, 2), Decimal("11")),  # February 1, 2026 is a Sunday
        PricePoint(date(2026, 2, 3), Decimal("12")),
        PricePoint(date(2026, 3, 2), Decimal("13")),
    ]
    firsts = first_trading_day_of_each_month(points)
    assert [p.day for p in firsts] == [date(2026, 1, 30), date(2026, 2, 2), date(2026, 3, 2)]


def test_the_sample_file_has_one_buy_day_per_month() -> None:
    assert len(first_trading_day_of_each_month(load_prices(SAMPLE))) == 24


def test_plan_command_prints_the_summary(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["plan", "--prices", str(SAMPLE), "--amount", "100"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Purchases:     24" in out
    assert "Invested:      2400.00" in out


def test_plan_command_reports_a_bad_file_on_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_csv(tmp_path, "date,close\n2026-01-05,ten\n")
    assert main(["plan", "--prices", str(path), "--amount", "100"]) == 1
    assert "line 2: not a number" in capsys.readouterr().err


def test_plan_command_rejects_a_negative_amount(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["plan", "--prices", str(SAMPLE), "--amount", "-5"])
    assert "amount must be positive" in capsys.readouterr().err
