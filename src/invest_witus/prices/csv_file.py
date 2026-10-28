"""Read a daily price history from a CSV file with the columns `date,close`."""

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from itertools import groupby
from pathlib import Path

REQUIRED_COLUMNS = ("date", "close")


@dataclass(frozen=True, slots=True)
class PricePoint:
    day: date
    close: Decimal


class PriceFileError(ValueError):
    """A price file that can't be read, with the line number of the problem."""

    def __init__(self, path: Path, line: int, problem: str) -> None:
        super().__init__(f"{path}, line {line}: {problem}")
        self.path = path
        self.line = line


def load_prices(path: Path) -> list[PricePoint]:
    """Read every row, check it, and return the prices sorted by day."""
    points: list[PricePoint] = []
    seen: set[date] = set()
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        missing = [name for name in REQUIRED_COLUMNS if name not in (reader.fieldnames or [])]
        if missing:
            raise PriceFileError(path, 1, f"missing column(s): {', '.join(missing)}")
        for row in reader:
            line = reader.line_num
            raw_day, raw_close = row["date"], row["close"]
            try:
                day = date.fromisoformat(raw_day)
            except ValueError:
                raise PriceFileError(path, line, f"not a YYYY-MM-DD date: {raw_day!r}") from None
            try:
                close = Decimal(raw_close)
            except InvalidOperation:
                raise PriceFileError(path, line, f"not a number: {raw_close!r}") from None
            if close <= 0:
                raise PriceFileError(path, line, f"price must be positive, got {close}")
            if day in seen:
                raise PriceFileError(path, line, f"{day} appears twice")
            seen.add(day)
            points.append(PricePoint(day=day, close=close))
    if not points:
        raise PriceFileError(path, 1, "no prices in the file")
    return sorted(points, key=lambda point: point.day)


def first_trading_day_of_each_month(points: list[PricePoint]) -> list[PricePoint]:
    """Keep the earliest price in each calendar month. Expects `points` sorted by day."""
    by_month = groupby(points, key=lambda point: (point.day.year, point.day.month))
    return [next(month_points) for _, month_points in by_month]
