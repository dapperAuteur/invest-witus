"""The monthly review for 12-1 momentum: every place the journal breaks that method's rules.

Chapter 03's `review` checks index investing and stays as it was. This is the second rule set, in
the same shape: a set of the rule ids it checks (a test keeps it equal to the TOML file's), and a
function from the method, the plan, the journal and the review date to a sorted list of
`Finding`s. The one thing it needs that chapter 03 did not is the ranking of each month, which
the caller computes from prices with `invest_witus.methods.momentum_12_1.rank` and passes in.

A month whose ranking is missing, or ranks nothing (no candidate has both closes stored), is not
judged by rank: the checks that need a rank are skipped for it, and the page says why. The app
never flags a buy because the app lacks the prices.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from invest_witus.adherence.journal import Action, Entry
from invest_witus.adherence.plan import Plan
from invest_witus.adherence.review import Finding, months_due
from invest_witus.methods.momentum_12_1 import Month, Ranking, month_text
from invest_witus.methods.rulebook import Method
from invest_witus.money import CENT, to_money

# The rule ids this module checks. A test keeps this set and the method's TOML file in step.
CHECKED_RULES = frozenset(
    {
        "candidates-only",
        "rank-by-12-1",
        "hold-top-n",
        "equal-weight",
        "sell-what-leaves",
        "rebalance-each-month",
        "trade-only-at-review",
    }
)
# The rule a skip with its reason can explain: a month with no trade (chapter 12's idea).
MISSED_MONTH = "rebalance-each-month"

# `flag` inside `review`: a day, a rule id and a message.
type FlagFunction = Callable[[date, str, str], None]


def equal_part(amount: Decimal, count: int) -> Decimal:
    """The amount over `count` symbols, unrounded: 100.00 over 3 is 33.333... A buy within a cent
    of it follows the rule, so 33.34 and 33.33 both do."""
    return amount / count


def equal_parts(amount: Decimal, symbols: list[str]) -> list[tuple[str, Decimal]]:
    """The amount in equal parts to the cent, one per symbol in rank order; the cents that do not
    divide go one each to the first symbols, so the parts add up exactly: 100.00 over three is
    33.34, 33.33 and 33.33 (chapter 11's split, which the paper orders use)."""
    if not symbols:
        return []
    cents = int(to_money(amount) / CENT)
    each, left_over = divmod(cents, len(symbols))
    return [(s, (each + (1 if i < left_over else 0)) * CENT) for i, s in enumerate(symbols)]


def ordinal(number: int) -> str:
    endings = {1: "st", 2: "nd", 3: "rd"}
    suffix = "th" if 10 <= number % 100 <= 20 else endings.get(number % 10, "th")
    return f"{number}{suffix}"


@dataclass(frozen=True, slots=True)
class Holdings:
    """What the journal says was held at the start of a month: every symbol whose latest trade
    before the month was a buy. A sale ends a holding, because the method sells it whole."""

    symbols: frozenset[str]

    @classmethod
    def before(cls, journal: list[Entry], month: Month, since: date) -> Holdings:
        first = date(month[0], month[1], 1)
        last_action: dict[str, Action] = {}
        for entry in sorted(journal, key=lambda e: e.day):
            if since <= entry.day < first:
                last_action[entry.symbol] = entry.action
        return cls(frozenset(s for s, action in last_action.items() if action is Action.BUY))


def review(
    method: Method,
    plan: Plan,
    top_n: int,
    journal: list[Entry],
    through: date,
    rankings: Mapping[Month, Ranking],
    held_since: date | None = None,
) -> list[Finding]:
    """Every finding from the plan's start through `through`. `rankings` holds the ranking of each
    month by its rebalance month; `held_since` is where holdings start counting (the first
    version's start, so a holding bought under version 1 is still held under version 2)."""
    findings: list[Finding] = []

    def flag(day: date, rule_id: str, message: str) -> None:
        findings.append(Finding(day, rule_id, message, method.lesson_for(rule_id)))

    entries = [e for e in journal if plan.start <= e.day <= through]
    for entry in entries:
        if entry.day.day > plan.buy_window_days:
            what = "Bought" if entry.action is Action.BUY else "Sold"
            flag(
                entry.day,
                "trade-only-at-review",
                f"{what} {entry.symbol} on day {entry.day.day}; the window is days 1 to "
                f"{plan.buy_window_days}.",
            )
        if entry.action is Action.BUY and entry.symbol not in plan.symbols:
            flag(entry.day, "candidates-only", f"Bought {entry.symbol}, which is not a candidate.")

    for month in months_due(plan, through):
        first = date(month[0], month[1], 1)
        in_month = [e for e in entries if (e.day.year, e.day.month) == month]
        if not in_month:
            flag(first, MISSED_MONTH, f"No rebalance in {month_text(month)}.")
            continue
        ranking = rankings.get(month)
        buys = [e for e in in_month if e.action is Action.BUY]
        divisor = top_n
        if ranking is not None and ranking.ranked:
            check_ranks(flag, plan, ranking, buys, month, top_n)
            divisor = len(ranking.top)
            held = Holdings.before(journal, month, held_since or plan.start).symbols
            check_sells(flag, ranking, in_month, held, month, top_n)
        part = equal_part(plan.amount, divisor)
        for buy in buys:
            if buy.symbol in plan.symbols and abs(buy.amount - part) >= CENT:
                flag(
                    buy.day,
                    "equal-weight",
                    f"Bought {buy.amount:.2f} of {buy.symbol}; an equal part of "
                    f"{plan.amount:.2f} over {divisor} is {to_money(part):.2f}.",
                )

    return sorted(findings, key=lambda f: (f.day, f.rule_id, f.message))


def check_ranks(
    flag: FlagFunction,
    plan: Plan,
    ranking: Ranking,
    buys: list[Entry],
    month: Month,
    top_n: int,
) -> None:
    """A buy of a candidate the window could not score, a buy ranked below the top N, and, in a
    month that had a buy, a top-N candidate that got none."""
    label = month_text(month)
    for buy in buys:
        if buy.symbol not in plan.symbols:
            continue
        if ranking.is_unranked(buy.symbol):
            flag(buy.day, "rank-by-12-1", f"Bought {buy.symbol}, which was not ranked in {label}.")
            continue
        place = ranking.place_of(buy.symbol)
        if place is not None and not place.top:
            flag(
                buy.day,
                "hold-top-n",
                f"Bought {buy.symbol}, ranked {ordinal(place.rank)} in {label}; the plan holds "
                f"the top {top_n}.",
            )
    if not buys:
        return
    bought = {buy.symbol for buy in buys}
    first = date(month[0], month[1], 1)
    for symbol in ranking.top:
        if symbol not in bought:
            place = ranking.place_of(symbol)
            rank = ordinal(place.rank) if place is not None else "top"
            flag(first, "hold-top-n", f"No buy of {symbol} in {label}; it ranked {rank}.")


def check_sells(
    flag: FlagFunction,
    ranking: Ranking,
    in_month: list[Entry],
    held: frozenset[str],
    month: Month,
    top_n: int,
) -> None:
    """A holding that left the top N and was not sold this month, and a sale of a top-N symbol."""
    label = month_text(month)
    sold = {e.symbol for e in in_month if e.action is Action.SELL}
    top = set(ranking.top)
    first = date(month[0], month[1], 1)
    for symbol in sorted(held - top - sold):
        place = ranking.place_of(symbol)
        where = f"ranked {ordinal(place.rank)}" if place is not None else "not ranked"
        flag(
            first,
            "sell-what-leaves",
            f"Held {symbol} into {label}, {where}, outside the top {top_n}, and did not sell it.",
        )
    for entry in in_month:
        if entry.action is Action.SELL and entry.symbol in top:
            flag(
                entry.day,
                "sell-what-leaves",
                f"Sold {entry.symbol}, still in the top {top_n} in {label}.",
            )
