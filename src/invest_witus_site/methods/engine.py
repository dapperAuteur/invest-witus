"""What the method page shows, built once: the plan, its rules with their lessons, the review's
findings, every month of the plan with its status, and the next action.

Chapter 03's `review` is called here exactly as the command line called it, on the values the
two converters in `models.py` produce. Everything else in this module is arrangement: the same
findings grouped by rule for a table, by month for another, and the one sentence that says what
to do next. The three views (A, B and C) render this one `MethodReview`; none of them queries
anything the others do not get.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from invest_witus.adherence.journal import Action, Entry
from invest_witus.adherence.plan import Plan
from invest_witus.adherence.review import Finding, months_due, review
from invest_witus.methods.rulebook import LESSON_COMING, Method
from invest_witus_site.methods.models import JournalEntry, MethodPlan

ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class RuleLine:
    """One rule as a page prints it: its id, its text, and the lesson's URL or `None`, which the
    template renders as the words "lesson coming". The URL is the TOML file's, through
    `Method.lesson_for`; nothing here invents one."""

    id: str
    text: str
    lesson_url: str | None


@dataclass(frozen=True, slots=True)
class FindingLine:
    """One finding with the rule it broke and the month it concerns."""

    day: date
    month: str
    rule: RuleLine
    message: str


@dataclass(frozen=True, slots=True)
class RuleCheck:
    """One rule's result through the review date: pass with no findings, fail with the list."""

    rule: RuleLine
    findings: list[FindingLine]

    @property
    def status(self) -> str:
        return "fail" if self.findings else "pass"

    @property
    def months(self) -> str:
        """The months the findings fall in, each once, in order."""
        return ", ".join(sorted({finding.month for finding in self.findings}))

    @property
    def evidence(self) -> str:
        """The fact that decided it, in words: how many findings, and in which months."""
        if not self.findings:
            return "no findings"
        count = len(self.findings)
        return f"{count} finding{'' if count == 1 else 's'}: {self.months}"


@dataclass(frozen=True, slots=True)
class MonthRow:
    """One month of the plan: the window, what was bought, and whether the month is done,
    missed, or still open on the review date."""

    label: str
    window_closes: date
    status: str
    buys: int
    amount: Decimal
    shares: Decimal | None
    rule_ids: list[str]


@dataclass(frozen=True, slots=True)
class NextAction:
    """The one thing the method asks for next: a buy in a window, and whether that window is
    open now ("due"), or ahead ("upcoming") because this month's buy is done or missed."""

    label: str
    opens: date
    closes: date
    amount: Decimal
    symbols: list[str]
    status: str


@dataclass(frozen=True, slots=True)
class MethodReview:
    """Everything the three views render, from one plan and one journal."""

    plan: MethodPlan
    method: Method
    rules: list[RuleLine]
    through: date
    entries: list[JournalEntry]
    findings: list[FindingLine]
    checks: list[RuleCheck]
    months: list[MonthRow]
    next_action: NextAction

    @property
    def on_plan(self) -> bool:
        return not self.findings

    @property
    def months_done(self) -> int:
        return sum(1 for row in self.months if row.status == "done")

    @property
    def months_due(self) -> int:
        return sum(1 for row in self.months if row.status != "open")


def month_label(year: int, month: int) -> str:
    return f"{year}-{month:02d}"


def rule_lines(method: Method) -> list[RuleLine]:
    """Each rule with its lesson resolved: the rule's own, else the method's, else nothing."""
    lines: list[RuleLine] = []
    for rule in method.rules:
        lesson = method.lesson_for(rule.id)
        lines.append(RuleLine(rule.id, rule.text, None if lesson == LESSON_COMING else lesson))
    return lines


def finding_lines(findings: list[Finding], rules: dict[str, RuleLine]) -> list[FindingLine]:
    return [
        FindingLine(f.day, month_label(f.day.year, f.day.month), rules[f.rule_id], f.message)
        for f in findings
    ]


def rule_checks(rules: list[RuleLine], findings: list[FindingLine]) -> list[RuleCheck]:
    return [RuleCheck(rule, [f for f in findings if f.rule.id == rule.id]) for rule in rules]


def next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def month_rows(
    plan: Plan, entries: list[JournalEntry], findings: list[FindingLine], through: date
) -> list[MonthRow]:
    """Every month from the plan's start through `through`: the months whose window has closed
    (chapter 03's `months_due`) and, if the review date falls inside a window that is still open,
    that month too, marked open. The rows are the journal's own, not chapter 03's values, because
    the shares column exists only here; the shares total is `None` when any buy in the month
    left shares blank, so a partial total is never printed as a whole."""
    due = months_due(plan, through)
    months = list(due)
    if through >= plan.start:
        current = (through.year, through.month)
        if current not in months and current >= (plan.start.year, plan.start.month):
            months.append(current)
    buys = [e for e in entries if e.action == Action.BUY.value and plan.start <= e.date <= through]
    rows: list[MonthRow] = []
    for year, month in months:
        label = month_label(year, month)
        in_month = [b for b in buys if (b.date.year, b.date.month) == (year, month)]
        if in_month:
            status = "done"
        elif (year, month) in due:
            status = "missed"
        else:
            status = "open"
        shares: Decimal | None = None
        if in_month and all(b.shares is not None for b in in_month):
            shares = sum((b.shares for b in in_month if b.shares is not None), ZERO)
        rows.append(
            MonthRow(
                label=label,
                window_closes=date(year, month, plan.buy_window_days),
                status=status,
                buys=len(in_month),
                amount=sum((b.amount for b in in_month), ZERO),
                shares=shares,
                rule_ids=sorted({f.rule.id for f in findings if f.month == label}),
            )
        )
    return rows


def next_action(plan: Plan, entries: list[Entry], today: date) -> NextAction:
    """The next buy. Before the start: the start month's window. In a month with no buy yet and
    the window open: that window, due now. Otherwise, the month after: this month's buy is done,
    or its window has closed (the review says "No buy" for it; the next action is still the
    next window, because the method has no catching up)."""
    bought = {(e.day.year, e.day.month) for e in entries if e.action is Action.BUY}
    if today < plan.start:
        year, month, status = plan.start.year, plan.start.month, "upcoming"
    elif (today.year, today.month) in bought or today.day > plan.buy_window_days:
        (year, month), status = next_month(today.year, today.month), "upcoming"
    else:
        year, month, status = today.year, today.month, "due"
    return NextAction(
        label=month_label(year, month),
        opens=date(year, month, 1),
        closes=date(year, month, plan.buy_window_days),
        amount=plan.amount,
        symbols=sorted(plan.symbols),
        status=status,
    )


def build_review(plan: MethodPlan, entries: list[JournalEntry], through: date) -> MethodReview:
    """The whole context for the method page, from the row, the rows and the date."""
    method = plan.method()
    chapter_plan = plan.to_plan()
    chapter_entries = [entry.to_entry() for entry in entries]
    rules = rule_lines(method)
    by_id = {rule.id: rule for rule in rules}
    findings = finding_lines(review(method, chapter_plan, chapter_entries, through), by_id)
    months = month_rows(chapter_plan, entries, findings, through)
    return MethodReview(
        plan=plan,
        method=method,
        rules=rules,
        through=through,
        entries=entries,
        findings=findings,
        checks=rule_checks(rules, findings),
        months=months,
        next_action=next_action(chapter_plan, chapter_entries, through),
    )
