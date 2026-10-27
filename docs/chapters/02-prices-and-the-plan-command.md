# Chapter 02: Read a price history and give the app its first command

**Starts from:** tag `v01`. **Ends at:** tag `v02`.
**Written against:** Python 3.14.10, uv 0.13.6 (October 27, 2026).
**Goal:** `uv run invest-witus plan --prices <file> --amount 100` replays a fixed monthly contribution over a file
of daily prices and prints every purchase and the result.
**Time:** 90 minutes.

## What you will learn

- **Files:** `pathlib.Path` (Node's `path` and `fs` in one object) and `with` blocks, which close the file for you
  the way `try/finally` would.
- **CSV:** `csv.DictReader` turns each row into a dictionary keyed by the header.
- **Your own exception class,** and `raise ... from None` to replace a low-level error with a clear one.
- **`sorted`, `set`, `itertools.groupby` and `next`:** grouping a sorted list without a loop counter.
- **A command-line interface with `argparse`,** subcommands, and `match`, Python's `switch`.
- **Two pytest fixtures:** `tmp_path` (a fresh temporary folder per test) and `capsys` (captures what you print).

## Before the code: what a price file is

The plan needs one price per month: the price on the day you buy. Price files usually come one row per trading
day, so the app reads the whole file and keeps the **first trading day of each month**. That is the day the plan
buys. Markets are closed on weekends and holidays, so the first trading day is not always the 1st.

The file in this chapter is **made up**: a slow rise, a wave and one sharp drop, written out for 24 months under
the placeholder symbol `INDEX`. It is not any real fund's history. Chapter 08 connects real prices from a data
source whose terms allow it; until then, made-up data keeps the lesson about code and keeps real numbers out of a
public repository.

## Steps

### 02.1 Copy the sample data and the checkpoint test

Take the sample file and its README from the reference (Browse link at the end of the chapter) into
`data/sample/`. Then add the test. It fails until the chapter is done.

Listing 02-1, Filename: `data/sample/README.md`:

```markdown
# Sample data

**`illustrative-daily-prices.csv` is made up.** It is a formula (a slow rise, a wave and one sharp drop) written
out as one closing price per weekday from October 1, 2024 to September 30, 2026, under the placeholder symbol
`INDEX`. It is not the price history of any real fund. Holidays are not removed. Use it to learn the code; use
real data only from a source whose terms you have read.

Your own files (real prices, statements, journals) go in `data/private/`, which git ignores.
```

Listing 02-2, Filename: `tests/test_ch02.py`:

```python
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
```

New in this test file:

- `tmp_path: Path` is a **fixture**. pytest sees the parameter name and passes in a new empty folder for each
  test. You never create or delete it yourself.
- `capsys` captures `print` output. `capsys.readouterr().out` is what went to the screen, `.err` what went to
  standard error.
- `pytest.raises(..., match=...)` checks the error message with a regular expression; `re.escape` stops the
  parentheses in "column(s)" from being read as regex syntax.
- `with pytest.raises(...) as info:` keeps the exception so the test can check `info.value.line`.

Run `uv run pytest tests/test_ch02.py` and read the `ModuleNotFoundError`. Red first.

### 02.2 The prices package

Listing 02-3, Filename: `src/invest_witus/prices/__init__.py`:

```python
"""Price history: where prices come from and how the app reads them."""
```

### 02.3 Read and check the file

Listing 02-4, Filename: `src/invest_witus/prices/csv_file.py`:

```python
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
```

Reading it as a TypeScript developer:

| Python | TypeScript or Node |
|---|---|
| `class PriceFileError(ValueError):` | `class PriceFileError extends RangeError` |
| `super().__init__(message)` | `super(message)` |
| `with path.open(...) as file:` | `const file = await open(path)` plus a `finally { file.close() }` you can't forget |
| `except ValueError:` | `catch (e) { if (!(e instanceof RangeError)) throw e; ... }` |
| `raise X from None` | throw a new error and drop the original from the stack trace |
| `set[date]` | `Set<Date>`, except Python's `date` compares by value, so two equal dates are one entry |
| `sorted(points, key=lambda point: point.day)` | `[...points].sort((a, b) => a.day - b.day)` |
| `f"{raw_day!r}"` | the value as code would show it, with quotes: `'01/06/2026'` |

**Why the line numbers.** When a file you downloaded has one bad row out of 500, "invalid date" is useless and
"line 214: not a YYYY-MM-DD date: '01/06/2026'" fixes it in a minute. `reader.line_num` is the line the reader
just read, counting the header as line 1.

**How `first_trading_day_of_each_month` works.** `groupby` walks a list and starts a new group every time the key
changes. The key here is `(year, month)`, so each group is one month's prices. Because the list is sorted, the
first item of each group is that month's first trading day, and `next(month_points)` takes it. `groupby` only
groups items that sit next to each other, which is why the docstring says the input must be sorted.

### 02.4 The command

Listing 02-5, Filename: `src/invest_witus/cli.py`:

```python
"""The `invest-witus` command."""

import argparse
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

from invest_witus.methods.index_dca import plan_purchases, summarize
from invest_witus.prices.csv_file import (
    PriceFileError,
    first_trading_day_of_each_month,
    load_prices,
)


def money_argument(text: str) -> Decimal:
    """argparse type: a positive amount of money such as 100 or 250.50."""
    try:
        amount = Decimal(text)
    except InvalidOperation:
        raise argparse.ArgumentTypeError(f"not an amount: {text!r}") from None
    if amount <= 0:
        raise argparse.ArgumentTypeError(f"amount must be positive, got {text}")
    return amount


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="invest-witus", description="Learn to invest by following one method at a time."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    plan = commands.add_parser(
        "plan", help="Replay a fixed monthly contribution over a price history."
    )
    plan.add_argument("--prices", type=Path, required=True, help="CSV file with date,close")
    plan.add_argument("--amount", type=money_argument, required=True, help="amount per month")
    return parser


def run_plan(prices_path: Path, amount: Decimal) -> int:
    try:
        points = load_prices(prices_path)
    except (OSError, PriceFileError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    buy_days = first_trading_day_of_each_month(points)
    purchases = plan_purchases(amount, [(p.day, p.close) for p in buy_days])
    summary = summarize(purchases, latest_price=points[-1].close)

    print(f"{'Day':<12}{'Price':>10}{'Amount':>10}{'Shares':>14}")
    for p in purchases:
        print(f"{p.day.isoformat():<12}{p.price:>10.2f}{p.amount:>10.2f}{p.shares:>14}")
    print()
    print(f"Purchases:     {summary.purchases}")
    print(f"Invested:      {summary.invested:.2f}")
    print(f"Shares:        {summary.shares}")
    print(f"Average cost:  {summary.average_cost}")
    print(f"Value on {points[-1].day.isoformat()}: {summary.value}")
    print(f"Gain or loss:  {summary.gain}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    match args.command:
        case "plan":
            return run_plan(args.prices, args.amount)
        case _:
            return 2
```

Notes:

- `argparse` builds the `--help` text, checks the arguments and exits with an error message on bad input. A
  function passed as `type=` converts one argument; raising `ArgumentTypeError` turns into a clean error.
- `main(argv: list[str] | None = None)` lets the tests pass arguments directly. When you run the command, `argv`
  is `None` and argparse reads the real command line.
- `match args.command:` with `case "plan":` is a `switch`. `case _:` is `default`.
- The function returns an **exit code**: 0 for success, anything else for an error. Shells, CI and cron all read
  it.
- `f"{p.price:>10.2f}"` means right-aligned, 10 wide, 2 decimal places. The same mini-language as Python's
  `format()`.

### 02.5 Point the command at `cli.main`

Replace the generated `main` with a docstring, and change the script entry in `pyproject.toml`.

Listing 02-6, Filename: `src/invest_witus/__init__.py`:

```python
"""Invest.WitUS: learn to invest by following one taught method, on paper first."""
```

Listing 02-7, Filename: `pyproject.toml` (one changed line):

```toml
[project.scripts]
invest-witus = "invest_witus.cli:main"
```

The next `uv run` rebuilds your package because the entry point changed; you will see `Uninstalled 1 package`
and `Installed 1 package` once.

### 02.6 Run it

Listing 02-8, Terminal:

```sh
uv run invest-witus plan --prices data/sample/illustrative-daily-prices.csv --amount 100
```

```text
Day              Price    Amount        Shares
2024-10-01      100.00    100.00      1.000000
2024-11-01      108.26    100.00      0.923702
2024-12-02      109.80    100.00      0.910746
...
2026-08-03      122.64    100.00      0.815394
2026-09-01      117.24    100.00      0.852951

Purchases:     24
Invested:      2400.00
Shares:        22.486373
Average cost:  106.73
Value on 2026-09-30: 2475.75
Gain or loss:  75.75
```

December 2, 2024 and August 3, 2026: the 1st fell on a weekend, so the plan bought on the next trading day. Run
the command with a file that doesn't exist and with `--amount -5` and read both errors.

## Checkpoint

- `uv run pytest` prints `27 passed`.
- `uv run ruff check .`, `uv run ruff format --check .` and `uv run pyright` pass.
- `uv run invest-witus --help` lists the `plan` command.
- Commit and push: `git add -A && git commit -m "Chapter 02: prices from a CSV and the plan command"`.

## Exercises

1. Add a `--day` option that buys on the first trading day **on or after** a chosen day of the month (for
   example the 15th, the day after a paycheck). Write the test first.
2. Make a small CSV by hand with a holiday missing in the middle of a week and check the plan still buys once a
   month.
3. Change `load_prices` so a blank line at the end of the file is skipped instead of reported. Is that a good
   idea? Write down why or why not.

## If you get stuck

- Browse: https://github.com/dapperAuteur/invest-witus/tree/v02
- Diff for this chapter: https://github.com/dapperAuteur/invest-witus/compare/v01...v02
- Zip: https://github.com/dapperAuteur/invest-witus/archive/v02.zip
- Take the reference's files: `git fetch reference --tags && git checkout v02 -- src tests data pyproject.toml`
  (set up the `reference` remote as in chapter 01), then `uv sync`.
- `invest-witus: command not found` or the old "Hello" message: `pyproject.toml` still points at
  `invest_witus:main`.
- `KeyError: 'date'`: your CSV header isn't exactly `date,close`. The missing-column check should catch this; if
  it doesn't, look at how `reader.fieldnames` is read.

## What we learned

- `Path`, `with` and `csv.DictReader` read a file safely.
- A custom exception with a line number turns a bad file into a one-minute fix.
- `groupby` on a sorted list plus `next` picks the first item of each group.
- argparse gives a command `--help`, validation and exit codes.
- The `tmp_path` and `capsys` fixtures test file reading and printed output without touching your real files.

## Next

Chapter 03 starts from tag `v02`. It writes the method down as rules the app can check, reads a journal of what
you actually did, and adds `invest-witus review`: the monthly review that tells you where you broke your own
plan, with a link to the lesson for each rule.
