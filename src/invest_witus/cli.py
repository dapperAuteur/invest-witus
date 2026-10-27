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
