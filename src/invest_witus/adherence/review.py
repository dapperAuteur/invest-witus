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
