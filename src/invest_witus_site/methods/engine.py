"""What the method page shows, built once: the plan, its rules with their lessons, the review's
findings, every month of the plan with its status, and the next action.

Chapter 03's `review` is called here exactly as the command line called it, on the values the
two converters in `models.py` produce. Everything else in this module is arrangement: the same
findings grouped by rule for a table, by month for another, and the one sentence that says what
to do next. The three views (A, B and C) render this one `MethodReview`; none of them queries
anything the others do not get.

Chapter 12 adds three things, all arrangement, none a new rule:

- **Versions.** A plan that changed is several rows; each judges only its own months (its span),
  so `review` runs once per version with that version's numbers and the results are joined.
- **Explained misses.** Chapter 03's "No buy in 2026-03" is still a finding of the rule "buy once
  in every month". When the journal has a skip for that month, the skip's reason is attached to
  the finding, the month reads "skipped" instead of "missed", and the rule's status reads
  "explained" when every finding it has is. The rule and `CHECKED_RULES` are unchanged.
- **The count of months followed:** the months due that were done with no finding.
"""

from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal

from invest_witus.adherence.journal import Action, Entry
from invest_witus.adherence.plan import Plan
from invest_witus.adherence.review import Finding, months_due, review
from invest_witus.methods.rulebook import LESSON_COMING, Method
from invest_witus_site.methods.models import SKIP, JournalEntry, MethodPlan, Span, version_spans

ZERO = Decimal("0")
# The one rule a skip can explain: a month with no buy. The id is the TOML file's.
ONE_BUY = "one-buy-each-month"


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
    """One finding with the rule it broke and the month it concerns. `explanation` is the reason
    of the skip that explains it, or "" when nothing does."""

    day: date
    month: str
    rule: RuleLine
    message: str
    explanation: str = ""

    @property
    def explained(self) -> bool:
        return bool(self.explanation)


@dataclass(frozen=True, slots=True)
class RuleCheck:
    """One rule's result through the review date: pass with no findings, fail with the list."""

    rule: RuleLine
    findings: list[FindingLine]

    @property
    def status(self) -> str:
        """pass with no findings; explained when every finding has a skip's reason; else fail."""
        if not self.findings:
            return "pass"
        return "explained" if all(f.explained for f in self.findings) else "fail"

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
        explained = sum(1 for finding in self.findings if finding.explained)
        note = f" ({explained} explained)" if explained else ""
        return f"{count} finding{'' if count == 1 else 's'}: {self.months}{note}"


@dataclass(frozen=True, slots=True)
class MonthRow:
    """One month of the plan: the window, what was bought, and whether the month is done,
    missed, skipped (no buy, and a skip with its reason), or still open on the review date.
    `version` is the plan version that judged it."""

    label: str
    window_closes: date
    status: str
    buys: int
    amount: Decimal
    shares: Decimal | None
    rule_ids: list[str]
    version: int = 1
    skip_reason: str = ""


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
    spans: list[Span] = field(default_factory=list[Span])

    @property
    def on_plan(self) -> bool:
        return not self.findings

    @property
    def unexplained(self) -> list[FindingLine]:
        return [finding for finding in self.findings if not finding.explained]

    @property
    def explained_count(self) -> int:
        return len(self.findings) - len(self.unexplained)

    @property
    def months_followed(self) -> int:
        """Months due that were done as the rules said: a buy, and no finding in the month."""
        return sum(1 for row in self.months if row.status == "done" and not row.rule_ids)

    def month(self, label: str) -> MonthRow | None:
        return next((row for row in self.months if row.label == label), None)

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
    plan: Plan,
    entries: list[JournalEntry],
    findings: list[FindingLine],
    through: date,
    version: int = 1,
) -> list[MonthRow]:
    """Every month from the plan's start through `through`: the months whose window has closed
    (chapter 03's `months_due`) and, if the review date falls inside a window that is still open,
    that month too, marked open. The rows are the journal's own, not chapter 03's values, because
    the shares column exists only here; the shares total is `None` when any buy in the month
    left shares blank, so a partial total is never printed as a whole. A month with no buy and a
    skip in the journal reads "skipped", with the skip's reason."""
    due = months_due(plan, through)
    months = list(due)
    if through >= plan.start:
        current = (through.year, through.month)
        if current not in months and current >= (plan.start.year, plan.start.month):
            months.append(current)
    buys = [e for e in entries if e.action == Action.BUY.value and plan.start <= e.date <= through]
    skips = [e for e in entries if e.kind == SKIP and plan.start <= e.date <= through]
    rows: list[MonthRow] = []
    for year, month in months:
        label = month_label(year, month)
        in_month = [b for b in buys if (b.date.year, b.date.month) == (year, month)]
        skipped = [s for s in skips if (s.date.year, s.date.month) == (year, month)]
        if in_month:
            status = "done"
        elif skipped:
            status = "skipped"
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
                amount=sum((b.money for b in in_month), ZERO),
                shares=shares,
                rule_ids=sorted({f.rule.id for f in findings if f.month == label}),
                version=version,
                skip_reason=skipped[0].reason if skipped and not in_month else "",
            )
        )
    return rows


def next_action(
    plan: Plan,
    entries: list[Entry],
    today: date,
    skipped: frozenset[tuple[int, int]] = frozenset(),
) -> NextAction:
    """The next buy. Before the start: the start month's window. In a month with no buy yet and
    the window open: that window, due now. Otherwise, the month after: this month's buy is done,
    or its window has closed (the review says "No buy" for it; the next action is still the
    next window, because the method has no catching up). Chapter 12: a month in `skipped` (a
    skip with its reason in the journal) counts as decided, like a month with a buy."""
    bought = {(e.day.year, e.day.month) for e in entries if e.action is Action.BUY} | skipped
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


def explain(findings: list[FindingLine], months: list[MonthRow]) -> list[FindingLine]:
    """Attach a skip's reason to the "No buy" finding of a month the journal says was skipped.
    Only that rule, and only a month with no buy: a skip does not excuse two buys."""
    skipped = {row.label: row.skip_reason for row in months if row.status == "skipped"}
    return [
        replace(finding, explanation=skipped[finding.month])
        if finding.rule.id == ONE_BUY and finding.month in skipped
        else finding
        for finding in findings
    ]


def span_through(span: Span, through: date) -> date:
    return through if span.last is None else min(through, span.last)


def version_on(spans: list[Span], day: date) -> MethodPlan:
    begun = [span.plan for span in spans if span.first <= day]
    return begun[-1] if begun else spans[0].plan


def build_review(plan: MethodPlan, entries: list[JournalEntry], through: date) -> MethodReview:
    """The whole context for the method page, from the row, the rows and the date. `plan` is the
    newest version; each version in its history is reviewed over its own span, with its own
    numbers, and the findings and months are joined in order."""
    method = plan.method()
    spans = version_spans(plan.versions() if plan.pk is not None else [plan])
    if not spans:
        spans = [Span(plan, plan.started_on, plan.ended_on)]
    trades = [entry.to_entry() for entry in entries if entry.is_trade]
    rules = rule_lines(method)
    by_id = {rule.id: rule for rule in rules}
    findings: list[FindingLine] = []
    months: list[MonthRow] = []
    for span in spans:
        upto = span_through(span, through)
        version = span.plan.to_plan()
        found = finding_lines(review(span.plan.method(), version, trades, upto), by_id)
        findings += found
        months += month_rows(version, entries, found, upto, span.plan.version)
    findings = explain(findings, months)
    skipped = frozenset(
        (e.date.year, e.date.month) for e in entries if e.kind == SKIP and e.date >= spans[0].first
    )
    now = version_on(spans, through)
    action = next_action(now.to_plan(), trades, through, skipped)
    if now is not plan and action.opens >= plan.started_on:
        action = next_action(plan.to_plan(), trades, through, skipped)
    return MethodReview(
        plan=plan,
        method=method,
        rules=rules,
        through=through,
        entries=entries,
        findings=findings,
        checks=rule_checks(rules, findings),
        months=months,
        next_action=action,
        spans=spans,
    )
