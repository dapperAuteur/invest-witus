"""Version 2 of the index rules: one buy of each fund a month, and the month's total (decision 173).

Chapter 03's `review` (version 1) expects one buy of the plan's whole amount each month. Since
decision 161 the amount is the month's total, split across the plan's funds, so a plan with three
funds made three buys of a third each and version 1 flagged all three, every month. Version 2 keeps
version 1's rule ids and judges what the split asks for:

- `one-buy-each-month`: a month due with no buy at all is "No buy in 2026-03." as before (a skip
  with its reason explains it); a month with buys names each fund of the plan that got none ("No
  buy of BETA in 2026-03.", with the reason when the caller knows it, such as Alpaca's answer) and
  each fund bought more than once.
- `fixed-amount`: in a month where every fund of the plan was bought, the buys of the plan's funds
  add up to the plan's amount within `tolerance(plan)`: one cent for each fund after the first,
  the most that rounding each equal part to the cent can move the total. A full Alpaca fill books
  exactly its part, so a month placed by Confirm adds up to the cent. A month with a fund missing
  is not judged on its total: the missing fund is the finding, and the total is short because of it.
  A part fill (or a refused or unfilled order made up by hand) is a finding with the reason in it.
- `buy-in-window`, `plan-symbols-only`, `no-selling`: as in version 1.

A plan with one fund is judged by version 1's checks unchanged: one buy of each fund is one buy a
month, and the month's total is that buy, so the two versions give the same findings, word for word.
"""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from invest_witus.adherence import review as version_1
from invest_witus.adherence.journal import Action, Entry
from invest_witus.adherence.plan import Plan
from invest_witus.adherence.review import Finding, months_due
from invest_witus.methods.rulebook import Method
from invest_witus.money import CENT

# The rule ids this module checks: version 1's ids. A test keeps this set and `index_dca.v2.toml`
# in step.
CHECKED_RULES = frozenset(
    {"one-buy-each-month", "buy-in-window", "fixed-amount", "plan-symbols-only", "no-selling"}
)
# The rule a skip explains: a month with no buy, or one fund's missing buy when the skip names it.
MISSED_MONTH = "one-buy-each-month"

type Month = tuple[int, int]
# Why a fund's buy of a month is missing or short, in words, by (month, symbol): from the caller
# (the web app reads its paper orders), never guessed here.
type Reasons = Mapping[tuple[Month, str], str]


@dataclass(frozen=True, slots=True)
class SymbolFinding(Finding):
    """A finding about one fund's buy in one month, so a skip naming that fund can explain it."""

    symbol: str = ""


def tolerance(plan: Plan) -> Decimal:
    """How far the month's total may be from the plan's amount: one cent for each fund after the
    first. $100.00 over three funds is 33.34, 33.33 and 33.33; rounding every part up instead
    gives 100.02, and down 99.99. With one fund the total must be exact, as in version 1."""
    return CENT * (len(plan.symbols) - 1)


def month_text(month: Month) -> str:
    return f"{month[0]}-{month[1]:02d}"


def review(
    method: Method,
    plan: Plan,
    journal: list[Entry],
    through: date,
    reasons: Reasons | None = None,
) -> list[Finding]:
    """Every finding from the plan's start through `through`. `reasons` holds why a fund's buy of
    a month is missing or short, when the caller knows (the paper orders); it only adds words."""
    if len(plan.symbols) == 1:
        return version_1.review(method, plan, journal, through)
    known = reasons or {}
    findings: list[Finding] = []

    def flag(day: date, rule_id: str, message: str, symbol: str = "") -> None:
        lesson = method.lesson_for(rule_id)
        findings.append(SymbolFinding(day, rule_id, message, lesson, symbol))

    entries = [e for e in journal if plan.start <= e.day <= through]
    buys = [e for e in entries if e.action is Action.BUY]
    for entry in entries:
        if entry.action is Action.SELL:
            flag(entry.day, "no-selling", f"Sold {entry.amount:.2f} of {entry.symbol}.")
    for buy in buys:
        if buy.symbol not in plan.symbols:
            flag(buy.day, "plan-symbols-only", f"Bought {buy.symbol}, which is not in the plan.")
        if buy.day.day > plan.buy_window_days:
            flag(
                buy.day,
                "buy-in-window",
                f"Bought {buy.symbol} on day {buy.day.day}; the window is days 1 to "
                f"{plan.buy_window_days}.",
            )

    def because(month: Month, symbols: list[str]) -> str:
        """The known reasons for the month's funds, as sentences after the finding's own."""
        said = [f"{s}: {known[(month, s)]}" for s in symbols if known.get((month, s))]
        return "".join(f" {line}" for line in said)

    funds = sorted(plan.symbols)
    for month in months_due(plan, through):
        first = date(month[0], month[1], 1)
        in_month = [b for b in buys if (b.day.year, b.day.month) == month]
        if not in_month:
            flag(first, MISSED_MONTH, f"No buy in {month_text(month)}.{because(month, funds)}")
            continue
        count = Counter(b.symbol for b in in_month if b.symbol in plan.symbols)
        for symbol in funds:
            if count[symbol] == 0:
                reason = known.get((month, symbol), "")
                message = f"No buy of {symbol} in {month_text(month)}."
                flag(first, MISSED_MONTH, f"{message} {reason}" if reason else message, symbol)
            elif count[symbol] > 1:
                # No symbol: a skip explains a missing buy, never a second one.
                twice = f"{count[symbol]} buys of {symbol} in {month_text(month)}."
                flag(first, MISSED_MONTH, twice)

    in_plan = [b for b in buys if b.symbol in plan.symbols]
    for month in sorted({(b.day.year, b.day.month) for b in in_plan}):
        bought = [b for b in in_plan if (b.day.year, b.day.month) == month]
        if frozenset(b.symbol for b in bought) != plan.symbols:
            continue  # a fund is missing: `one-buy-each-month` says so once the window closes
        total = sum((b.amount for b in bought), start=Decimal(0))
        gap = total - plan.amount
        if abs(gap) > tolerance(plan):
            side = "short" if gap < 0 else "over"
            flag(
                max(b.day for b in bought),
                "fixed-amount",
                f"The buys of {month_text(month)} add up to {total:.2f}; the plan says "
                f"{plan.amount:.2f} in all ({side} by {abs(gap):.2f}).{because(month, funds)}",
            )

    return sorted(findings, key=lambda f: (f.day, f.rule_id, f.message))
