# Chapter 03: Write the method down, and review yourself against it

**Starts from:** tag `v02`. **Ends at:** tag `v03`.
**Written against:** Python 3.14.10, uv 0.13.6 (October 27, 2026).
**Goal:** `uv run invest-witus review --plan <plan.toml> --journal <journal.csv>` reads what you actually did and
lists every place it broke the method's rules, each with the rule's text and a link to its lesson.
**Time:** 2 hours. This is the chapter the app is for.

## What you will learn

- **TOML** with the standard library's `tomllib`, and **package data** with `importlib.resources`: a data file
  that ships inside your package.
- **`StrEnum`:** a fixed set of string values, like a TypeScript string union with runtime checks.
- **`collections.Counter`,** `frozenset`, and tuples as dictionary keys.
- **A function inside a function** (a closure), the same idea as a JavaScript arrow function that captures
  variables from the function around it.
- **Date arithmetic** without a library: walking month by month across a new year.

## Before the code: method, plan, journal

Three files, three owners. Keeping them apart is the design.

| File | What it holds | Who writes it | Where it lives |
|---|---|---|---|
| The **method** | The rules, in words, each with a link to its lesson | The course | Inside the package: `src/invest_witus/methods/index_dca.toml` |
| Your **plan** | Your numbers for that method: start date, amount, fund, buy window | You, once | `data/private/plan.toml` (git ignores it) |
| Your **journal** | What you actually did, one row per trade | You, after every trade | `data/private/journal.csv` (git ignores it) |

The method file is read by **both** the lesson and the code. When the lesson changes a rule's wording, the app
shows the new wording. A test (below) makes sure the rules in the file and the rules the code checks are the
same set, so neither can drift.

Why bother? The research behind this method (chapter 01) is about what a plan earns **if you follow it**. Most of
what goes wrong is not the arithmetic but the person: skipping a month, buying more after a good month, selling
after a drop. Behavioral-finance researchers have documented biases like these for decades; the course's methods
guide covers them. The monthly review is how the app helps: it doesn't predict anything, it just shows you where
you left your own plan, and sends you back to the lesson.

## Steps

### 03.1 Copy the samples and the checkpoint test

Listing 03-1, Filename: `data/sample/plan.toml`:

```toml
# A sample plan for the index-dca method. Copy it to data/private/plan.toml (git ignores that
# folder) and put in your own numbers.
method = "index-dca"
start = 2025-10-01          # a TOML date: no quotes
amount = "100.00"           # in quotes, so it becomes an exact Decimal, not a float
symbols = ["INDEX"]         # a placeholder; name the fund you chose
buy_window_days = 7         # buy within the first 7 days of each month
```

TOML is the format of `pyproject.toml`. A bare `2025-10-01` is a real date, not a string. The amount is a string
on purpose: TOML would read `100.00` as a float, and chapter 01 showed why money is never a float.

Listing 03-2, Filename: `data/sample/journal.csv`:

```text
date,action,symbol,amount
2025-10-01,buy,INDEX,100.00
2025-11-03,buy,INDEX,100.00
2025-12-01,buy,INDEX,100.00
2026-01-02,buy,INDEX,100.00
2026-02-02,buy,INDEX,100.00
2026-04-01,buy,INDEX,100.00
2026-05-12,buy,INDEX,100.00
2026-06-01,buy,INDEX,100.00
2026-06-19,sell,INDEX,250.00
2026-07-01,buy,INDEX,150.00
2026-08-03,buy,OTHER,100.00
2026-09-01,buy,INDEX,100.00
```

This journal is made up and breaks the plan on purpose. Can you spot the five problems before the code does?

Listing 03-3, Filename: `tests/test_ch03.py`:

```python
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from invest_witus.adherence.journal import Action, Entry, JournalFileError, load_journal
from invest_witus.adherence.plan import Plan, PlanFileError, load_plan
from invest_witus.adherence.review import CHECKED_RULES, months_due, review
from invest_witus.cli import main
from invest_witus.methods.rulebook import LESSON_COMING, UnknownMethodError, load_method

SAMPLES = Path(__file__).parent.parent / "data" / "sample"
D = Decimal

PLAN = Plan(
    method="index-dca",
    start=date(2026, 1, 1),
    amount=D("100.00"),
    symbols=frozenset({"INDEX"}),
    buy_window_days=7,
)


def buy(day: date, amount: str = "100.00", symbol: str = "INDEX") -> Entry:
    return Entry(day=day, action=Action.BUY, symbol=symbol, amount=D(amount))


def rule_ids(entries: list[Entry], through: date) -> list[str]:
    return [f.rule_id for f in review(load_method("index-dca"), PLAN, entries, through)]


def test_the_rules_file_and_the_code_check_the_same_rules() -> None:
    method = load_method("index-dca")
    assert {rule.id for rule in method.rules} == CHECKED_RULES


def test_a_rule_without_a_lesson_says_lesson_coming() -> None:
    assert load_method("index-dca").lesson_for("no-selling") == LESSON_COMING


def test_an_unknown_method_is_an_error() -> None:
    with pytest.raises(UnknownMethodError):
        load_method("get-rich-quick")


def test_the_sample_plan_loads() -> None:
    plan = load_plan(SAMPLES / "plan.toml")
    assert plan.start == date(2025, 10, 1)
    assert plan.amount == D("100.00")
    assert plan.symbols == {"INDEX"}


@pytest.mark.parametrize(
    "toml, problem",
    [
        ('method = "index-dca"\n', "missing setting"),
        (
            'method = "index-dca"\nstart = "2026-01-01"\namount = "100"\n'
            'symbols = ["INDEX"]\nbuy_window_days = 7\n',
            "start must be a date",
        ),
        (
            'method = "index-dca"\nstart = 2026-01-01\namount = "100"\n'
            'symbols = ["INDEX"]\nbuy_window_days = 40\n',
            "between 1 and 28",
        ),
    ],
)
def test_bad_plans_say_what_is_wrong(tmp_path: Path, toml: str, problem: str) -> None:
    path = tmp_path / "plan.toml"
    path.write_text(toml, encoding="utf-8")
    with pytest.raises(PlanFileError, match=problem):
        load_plan(path)


def test_the_journal_reads_actions_and_tidies_symbols(tmp_path: Path) -> None:
    path = tmp_path / "journal.csv"
    path.write_text("date,action,symbol,amount\n2026-01-02,BUY,index,100\n", encoding="utf-8")
    assert load_journal(path) == [buy(date(2026, 1, 2), "100")]


def test_an_unknown_action_names_the_line(tmp_path: Path) -> None:
    path = tmp_path / "journal.csv"
    path.write_text("date,action,symbol,amount\n2026-01-02,hold,INDEX,100\n", encoding="utf-8")
    with pytest.raises(JournalFileError) as info:
        load_journal(path)
    assert info.value.line == 2


def test_the_current_month_is_not_due_until_its_window_closes() -> None:
    assert months_due(PLAN, date(2026, 3, 6)) == [(2026, 1), (2026, 2)]
    assert months_due(PLAN, date(2026, 3, 7)) == [(2026, 1), (2026, 2), (2026, 3)]


def test_months_due_crosses_the_new_year() -> None:
    plan = Plan("index-dca", date(2025, 11, 1), D("100"), frozenset({"INDEX"}), 7)
    assert months_due(plan, date(2026, 1, 31)) == [(2025, 11), (2025, 12), (2026, 1)]


def test_a_plan_followed_exactly_has_no_findings() -> None:
    entries = [buy(date(2026, 1, 2)), buy(date(2026, 2, 2)), buy(date(2026, 3, 2))]
    assert rule_ids(entries, through=date(2026, 3, 31)) == []


@pytest.mark.parametrize(
    "entries, expected",
    [
        ([buy(date(2026, 1, 2))], ["one-buy-each-month"]),  # February is missing
        ([buy(date(2026, 1, 2)), buy(date(2026, 2, 12))], ["buy-in-window"]),
        ([buy(date(2026, 1, 2)), buy(date(2026, 2, 2), "150.00")], ["fixed-amount"]),
        ([buy(date(2026, 1, 2)), buy(date(2026, 2, 2), symbol="OTHER")], ["plan-symbols-only"]),
        (
            [buy(date(2026, 1, 2)), buy(date(2026, 1, 5)), buy(date(2026, 2, 2))],
            ["one-buy-each-month"],
        ),
        (
            [
                buy(date(2026, 1, 2)),
                Entry(date(2026, 1, 20), Action.SELL, "INDEX", D("50")),
                buy(date(2026, 2, 2)),
            ],
            ["no-selling"],
        ),
    ],
)
def test_each_rule_is_flagged(entries: list[Entry], expected: list[str]) -> None:
    assert rule_ids(entries, through=date(2026, 2, 28)) == expected


def test_trades_before_the_plan_started_are_ignored() -> None:
    entries = [Entry(date(2025, 12, 15), Action.SELL, "INDEX", D("50")), buy(date(2026, 1, 2))]
    assert rule_ids(entries, through=date(2026, 1, 31)) == []


def test_review_command_on_the_samples(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(
        [
            "review",
            "--plan",
            str(SAMPLES / "plan.toml"),
            "--journal",
            str(SAMPLES / "journal.csv"),
            "--through",
            "2026-09-30",
        ]
    )
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "5 thing(s) to look at" in out
    assert "No buy in 2026-03." in out
    assert "Lesson: lesson coming" in out


def test_review_command_reports_a_missing_file(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["review", "--plan", "nope.toml", "--journal", "nope.csv"]) == 1
    assert "error:" in capsys.readouterr().err
```

Run it and read the `ModuleNotFoundError`. Red first.

### 03.2 The method's rules

Listing 03-4, Filename: `src/invest_witus/methods/index_dca.toml`:

```toml
# Index investing with a fixed monthly contribution, written as rules the app checks.
# The Learn.WitUS lesson and the code read this same file. A rule's `lesson` is the URL of the
# lesson that teaches it; leave it empty until that lesson is published. Never guess a URL.

id = "index-dca"
name = "Index investing with a fixed monthly contribution"
version = 1
summary = "Put the same amount into the same index fund at the start of every month, and don't sell because prices fell."
lesson = ""

[[rules]]
id = "one-buy-each-month"
text = "Buy once in every month of the plan."
lesson = ""

[[rules]]
id = "buy-in-window"
text = "Buy within the plan's buy window at the start of the month, not when the news makes you feel ready."
lesson = ""

[[rules]]
id = "fixed-amount"
text = "Buy the plan's amount every time: no more after a good month, no less after a bad one."
lesson = ""

[[rules]]
id = "plan-symbols-only"
text = "Buy only the fund or funds named in your plan."
lesson = ""

[[rules]]
id = "no-selling"
text = "This method has no sell rule. A sale is a change of plan and needs a written reason."
lesson = ""
```

Every `lesson` is empty. That is deliberate: the Learn.WitUS lessons for this method are not published yet, and a
made-up URL would be worse than none. The app shows "lesson coming" until a real URL goes in.

`[[rules]]` is TOML's array of tables: each `[[rules]]` block adds one item to a `rules` list.

Listing 03-5, Filename: `src/invest_witus/methods/rulebook.py`:

```python
"""Load a method's rules from the TOML file that ships inside the package."""

import tomllib
from dataclasses import dataclass
from importlib.resources import files

LESSON_COMING = "lesson coming"


class UnknownMethodError(LookupError):
    """No rules file ships for this method id."""


@dataclass(frozen=True, slots=True)
class Rule:
    id: str
    text: str
    lesson: str


@dataclass(frozen=True, slots=True)
class Method:
    id: str
    name: str
    version: int
    summary: str
    lesson: str
    rules: tuple[Rule, ...]

    def rule(self, rule_id: str) -> Rule:
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        raise KeyError(f"method {self.id!r} has no rule {rule_id!r}")

    def lesson_for(self, rule_id: str) -> str:
        """The rule's lesson, else the method's lesson, else 'lesson coming'."""
        return self.rule(rule_id).lesson or self.lesson or LESSON_COMING


def load_method(method_id: str) -> Method:
    """Read `<method_id with underscores>.toml` from the methods package."""
    resource = files("invest_witus.methods") / f"{method_id.replace('-', '_')}.toml"
    if not resource.is_file():
        raise UnknownMethodError(f"unknown method {method_id!r}")
    data = tomllib.loads(resource.read_text(encoding="utf-8"))
    return Method(
        id=str(data["id"]),
        name=str(data["name"]),
        version=int(data["version"]),
        summary=str(data["summary"]),
        lesson=str(data.get("lesson", "")),
        rules=tuple(
            Rule(id=str(r["id"]), text=str(r["text"]), lesson=str(r.get("lesson", "")))
            for r in data["rules"]
        ),
    )
```

Notes:

- `files("invest_witus.methods") / "index_dca.toml"` finds the file **inside the installed package**, wherever
  that is. Never build that path from `__file__` or the current directory: on a server the working directory is
  not your repo. uv's build backend includes the `.toml` file in the package automatically.
- `tuple[Rule, ...]` means "a tuple of any length, all `Rule`s". A tuple, not a list, because the dataclass is
  frozen and a list inside it could still be changed.
- `self.rule(rule_id).lesson or self.lesson or LESSON_COMING`: `or` returns the first value that isn't empty,
  like `??` in TypeScript, except that `or` also skips empty strings and zeros.
- `LookupError` is the parent of `KeyError` and `IndexError`; an unknown method is a failed lookup.

### 03.3 Your plan

Listing 03-6, Filename: `src/invest_witus/adherence/__init__.py`:

```python
"""Adherence: comparing what you did with the method you chose."""
```

Listing 03-7, Filename: `src/invest_witus/adherence/plan.py`:

```python
"""Your plan: the personal numbers you chose for a method."""

import tomllib
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Plan:
    method: str
    start: date
    amount: Decimal
    symbols: frozenset[str]
    buy_window_days: int


class PlanFileError(ValueError):
    """A plan file with a missing or wrong setting."""


def load_plan(path: Path) -> Plan:
    with path.open("rb") as file:
        data = tomllib.load(file)
    try:
        start = data["start"]
        if not isinstance(start, date):
            raise PlanFileError(f"{path}: start must be a date like 2025-10-01, not {start!r}")
        amount = Decimal(str(data["amount"]))
        window = int(data["buy_window_days"])
        plan = Plan(
            method=str(data["method"]),
            start=start,
            amount=amount,
            symbols=frozenset(str(symbol) for symbol in data["symbols"]),
            buy_window_days=window,
        )
    except KeyError as missing:
        raise PlanFileError(f"{path}: missing setting {missing}") from None
    except InvalidOperation:
        raise PlanFileError(f'{path}: amount must be a number in quotes, like "100.00"') from None
    if plan.amount <= 0:
        raise PlanFileError(f"{path}: amount must be positive")
    if not 1 <= plan.buy_window_days <= 28:
        raise PlanFileError(f"{path}: buy_window_days must be between 1 and 28")
    if not plan.symbols:
        raise PlanFileError(f"{path}: symbols must name at least one fund")
    return plan
```

- `tomllib` reads TOML; it cannot write it. It wants the file opened in binary mode, `"rb"`.
- `isinstance(start, date)` is a runtime type check. TOML could have handed back a string if someone quoted the
  date, and type hints don't check anything at runtime.
- `frozenset` is a set that can't change, so it can live in a frozen dataclass.
- `1 <= plan.buy_window_days <= 28` is a chained comparison. 28 keeps the window inside every month, February
  included.

### 03.4 Your journal

Listing 03-8, Filename: `src/invest_witus/adherence/journal.py`:

```python
"""Your journal: what you actually bought and sold, one row per trade."""

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path

REQUIRED_COLUMNS = ("date", "action", "symbol", "amount")


class Action(StrEnum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True, slots=True)
class Entry:
    day: date
    action: Action
    symbol: str
    amount: Decimal


class JournalFileError(ValueError):
    def __init__(self, path: Path, line: int, problem: str) -> None:
        super().__init__(f"{path}, line {line}: {problem}")
        self.line = line


def load_journal(path: Path) -> list[Entry]:
    entries: list[Entry] = []
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        missing = [name for name in REQUIRED_COLUMNS if name not in (reader.fieldnames or [])]
        if missing:
            raise JournalFileError(path, 1, f"missing column(s): {', '.join(missing)}")
        for row in reader:
            line = reader.line_num
            try:
                day = date.fromisoformat(row["date"])
                action = Action(row["action"].strip().lower())
                amount = Decimal(row["amount"])
            except ValueError as error:
                raise JournalFileError(path, line, str(error)) from None
            except InvalidOperation:
                raise JournalFileError(path, line, f"not an amount: {row['amount']!r}") from None
            symbol = row["symbol"].strip().upper()
            if not symbol:
                raise JournalFileError(path, line, "symbol is empty")
            if amount <= 0:
                raise JournalFileError(path, line, "amount must be positive")
            entries.append(Entry(day=day, action=action, symbol=symbol, amount=amount))
    return sorted(entries, key=lambda entry: entry.day)
```

- `Action(row["action"].strip().lower())` turns `"BUY "` into `Action.BUY`, and anything that isn't a known
  action into a `ValueError` the loader reports with its line number.
- A `StrEnum` member **is** a string: `Action.BUY == "buy"` is `True`, and it prints as `buy`.
- Compare enum members with `is`: there is exactly one `Action.BUY` object.

### 03.5 The review

Listing 03-9, Filename: `src/invest_witus/adherence/review.py`:

```python
"""The monthly review: every place the journal breaks the method's rules."""

from collections import Counter
from dataclasses import dataclass
from datetime import date

from invest_witus.adherence.journal import Action, Entry
from invest_witus.adherence.plan import Plan
from invest_witus.methods.rulebook import Method

# The rule ids this module checks. A test keeps this set and the method's TOML file in step.
CHECKED_RULES = frozenset(
    {"one-buy-each-month", "buy-in-window", "fixed-amount", "plan-symbols-only", "no-selling"}
)


@dataclass(frozen=True, slots=True)
class Finding:
    day: date
    rule_id: str
    message: str
    lesson: str


def months_due(plan: Plan, through: date) -> list[tuple[int, int]]:
    """Every (year, month) from the plan's start whose buy window has closed by `through`."""
    months: list[tuple[int, int]] = []
    year, month = plan.start.year, plan.start.month
    while date(year, month, plan.buy_window_days) <= through:
        months.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def review(method: Method, plan: Plan, journal: list[Entry], through: date) -> list[Finding]:
    findings: list[Finding] = []

    def flag(day: date, rule_id: str, message: str) -> None:
        findings.append(Finding(day, rule_id, message, method.lesson_for(rule_id)))

    entries = [e for e in journal if plan.start <= e.day <= through]
    buys = [e for e in entries if e.action is Action.BUY]

    for entry in entries:
        if entry.action is Action.SELL:
            flag(entry.day, "no-selling", f"Sold {entry.amount:.2f} of {entry.symbol}.")
    for buy in buys:
        if buy.symbol not in plan.symbols:
            flag(buy.day, "plan-symbols-only", f"Bought {buy.symbol}, which is not in the plan.")
        if buy.amount != plan.amount:
            message = f"Bought {buy.amount:.2f}; the plan says {plan.amount:.2f}."
            flag(buy.day, "fixed-amount", message)
        if buy.day.day > plan.buy_window_days:
            flag(
                buy.day,
                "buy-in-window",
                f"Bought on day {buy.day.day}; the window is days 1 to {plan.buy_window_days}.",
            )

    buys_per_month = Counter((b.day.year, b.day.month) for b in buys)
    for year, month in months_due(plan, through):
        count = buys_per_month[(year, month)]
        if count != 1:
            what = "No buy" if count == 0 else f"{count} buys"
            flag(date(year, month, 1), "one-buy-each-month", f"{what} in {year}-{month:02d}.")

    return sorted(findings, key=lambda f: (f.day, f.rule_id))
```

How it works:

1. Keep only trades from the plan's start through the review day.
2. Every sale breaks `no-selling`. Every buy is checked for symbol, amount and day of the month.
3. `Counter` counts buys per `(year, month)`. A `Counter` returns 0 for a key it has never seen, so a skipped month
   needs no special case.
4. `months_due` lists the months whose buy window has **closed**. Reviewing on March 6 with a 7-day window, March
   isn't due yet, so it can't be "missed". The test `test_the_current_month_is_not_due_until_its_window_closes`
   pins that edge down.
5. `flag` is a function defined inside `review`. It can read `method` and append to `findings` because it closes
   over them.

### 03.6 The `review` command

Listing 03-10, Filename: `src/invest_witus/cli.py`:

```python
"""The `invest-witus` command."""

import argparse
import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from invest_witus.adherence.journal import load_journal
from invest_witus.adherence.plan import load_plan
from invest_witus.adherence.review import review
from invest_witus.methods.index_dca import plan_purchases, summarize
from invest_witus.methods.rulebook import UnknownMethodError, load_method
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

    check = commands.add_parser("review", help="Check your journal against your plan's method.")
    check.add_argument("--plan", type=Path, required=True, help="your plan, a TOML file")
    check.add_argument("--journal", type=Path, required=True, help="your trades, a CSV file")
    check.add_argument(
        "--through",
        type=date.fromisoformat,
        default=None,
        help="review up to this day, YYYY-MM-DD (default: today)",
    )
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


def run_review(plan_path: Path, journal_path: Path, through: date) -> int:
    try:
        plan = load_plan(plan_path)
        method = load_method(plan.method)
        journal = load_journal(journal_path)
    except (OSError, ValueError, UnknownMethodError) as error:
        # ValueError covers PlanFileError, JournalFileError and TOML syntax errors.
        print(f"error: {error}", file=sys.stderr)
        return 1

    findings = review(method, plan, journal, through)
    print(f"{method.name} (version {method.version})")
    symbols = ", ".join(sorted(plan.symbols))
    print(f"Plan: {plan.amount:.2f} a month into {symbols}, from {plan.start}")
    print(f"Reviewed through {through}.")
    print()
    if not findings:
        print("You followed every rule. Nothing to look at this month.")
        return 0
    print(f"{len(findings)} thing(s) to look at:")
    for finding in findings:
        rule = method.rule(finding.rule_id)
        print()
        print(f"  {finding.day}  {finding.message}")
        print(f"    Rule: {rule.text}")
        print(f"    Lesson: {finding.lesson}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    match args.command:
        case "plan":
            return run_plan(args.prices, args.amount)
        case "review":
            return run_review(args.plan, args.journal, args.through or date.today())
        case _:
            return 2
```

- `type=date.fromisoformat` uses a standard-library function as the argument parser; a bad date becomes a clean
  argparse error.
- `args.through or date.today()`: the default is decided when the command runs, not when the parser is built.
- `except (OSError, ValueError, UnknownMethodError)` catches a missing file, a bad plan or journal (both errors
  are `ValueError`s), and a TOML syntax error (`tomllib.TOMLDecodeError` is a `ValueError` too).

### 03.7 Run your first review

Listing 03-11, Terminal:

```sh
uv run invest-witus review --plan data/sample/plan.toml --journal data/sample/journal.csv --through 2026-09-30
```

```text
Index investing with a fixed monthly contribution (version 1)
Plan: 100.00 a month into INDEX, from 2025-10-01
Reviewed through 2026-09-30.

5 thing(s) to look at:

  2026-03-01  No buy in 2026-03.
    Rule: Buy once in every month of the plan.
    Lesson: lesson coming

  2026-05-12  Bought on day 12; the window is days 1 to 7.
    Rule: Buy within the plan's buy window at the start of the month, not when the news makes you feel ready.
    Lesson: lesson coming

  2026-06-19  Sold 250.00 of INDEX.
    Rule: This method has no sell rule. A sale is a change of plan and needs a written reason.
    Lesson: lesson coming

  2026-07-01  Bought 150.00; the plan says 100.00.
    Rule: Buy the plan's amount every time: no more after a good month, no less after a bad one.
    Lesson: lesson coming

  2026-08-03  Bought OTHER, which is not in the plan.
    Rule: Buy only the fund or funds named in your plan.
    Lesson: lesson coming
```

### 03.8 Make it yours

Copy the sample plan to `data/private/plan.toml`, put in your own numbers, and start a `data/private/journal.csv`
with the same header. `git status` should not list either file: check that before your next commit. From now
on, the monthly review is a habit, not a feature:

```sh
uv run invest-witus review --plan data/private/plan.toml --journal data/private/journal.csv
```

If you are using a paper-trading account, log the paper trades. The point of the first months is to learn the
habit with no money at risk.

## Checkpoint

- `uv run pytest` prints `48 passed`.
- ruff and pyright pass.
- The review of the samples lists exactly five things.
- `git status` does not show anything under `data/private/`.
- Commit and push: `git add -A && git commit -m "Chapter 03: rules, plan, journal and review"`.

## Exercises

1. Add a `--json` flag to `review` that prints the findings as JSON (`json.dumps` with a list of dicts). This is
   the shape a web page will want in a later chapter.
2. The method says "a sale needs a written reason." Add an optional `note` column to the journal, and let a sale
   with a note print as "Sold, with a reason" instead of a finding. Should it still count as a finding? Write down
   your answer and then the test.
3. `load_journal` and `load_prices` repeat the missing-column check. Pull it into one helper in a new module and
   use it from both. Run the whole suite after.

## If you get stuck

- Browse: https://github.com/dapperAuteur/invest-witus/tree/v03
- Diff for this chapter: https://github.com/dapperAuteur/invest-witus/compare/v02...v03
- Zip: https://github.com/dapperAuteur/invest-witus/archive/v03.zip
- Take the reference's files: `git fetch reference --tags && git checkout v03 -- src tests data`.
- `UnknownMethodError: unknown method 'index-dca'`: the TOML file is missing, misnamed (it must be
  `index_dca.toml`, with an underscore) or outside `src/invest_witus/methods/`.
- `TOMLDecodeError`: usually a missing quote or a date written with slashes.
- A month you did buy shows as "No buy": check the journal's date column is `YYYY-MM-DD` and the action is `buy`.

## What we learned

- A method is data (rules in TOML, read by the lesson and the code); a plan is your numbers; a journal is what you
  did. Keep them apart.
- `importlib.resources` reads files shipped inside the package.
- `StrEnum`, `Counter` and `frozenset` make the checks short and exact.
- A month is only "missed" once its buy window has closed.
- The review doesn't predict anything. It shows where you left your plan, and points to the lesson.

## Next

Chapter 04 starts from tag `v03` and adds Django: the first web page is the app's public landing page, with a
waitlist, the WitUS footer, and privacy and terms pages. The code from chapters 01 to 03 stays exactly where it is
and becomes what the web pages call.
