"""Whether a plan has history yet, and so whether it may be edited in place or deleted
(2026-11-02, decisions 157 and 158).

Chapter 12 made a plan's numbers history: a change is a new version, so every month keeps the
numbers that judged it. That is right once something has happened under the numbers. Before
anything has, there is nothing to keep, and a version would only record a typo. This module
draws the line, in one place, for the edit page, the delete page and the links to them.

A plan **has history** when any of these is true, counted over every version from the first:

- a paper order of the plan bought shares (any `filled_qty`, a part fill included);
- the journal holds an entry dated on or after the plan's first day that is not the entry of one
  of the plan's own orders still open at Alpaca (that entry is booked at the order's notional and
  disappears when the order is cancelled unfilled, as the nightly sync would remove it);
- one of the plan's monthly reviews was written, closed or reopened.

A plan with history can be neither edited in place nor deleted: change it with a new version, or
end it, and its months stay. A plan with none can be deleted, with its empty reviews and its
unfilled order rows, after its open orders are cancelled at Alpaca. It can be edited in place
when, in addition, it is version 1 (a changed plan already keeps a version history) and no month's
buy window has closed under it (no review exists, so no month is judged by these numbers yet).

Journal entries belong to the account, not to a plan (chapter 10), so deleting a plan deletes no
entry; the rule above keeps a plan whose entries it judges from disappearing from under them.
"""

from dataclasses import dataclass, field

from django.db import transaction

from invest_witus_site.methods.models import JournalEntry, MethodPlan, MonthlyReview, ReviewEvent
from invest_witus_site.paper.models import PaperOrder


def plural(count: int, word: str, many: str = "") -> str:
    return f"{count} {word if count == 1 else (many or word + 's')}"


@dataclass(frozen=True, slots=True)
class PlanState:
    """One active plan, sorted into what counts as history and what would go with it."""

    plan: MethodPlan
    versions: list[MethodPlan]
    filled: list[PaperOrder] = field(default_factory=list[PaperOrder])
    open_orders: list[PaperOrder] = field(default_factory=list[PaperOrder])
    unfilled_orders: list[PaperOrder] = field(default_factory=list[PaperOrder])
    entries: list[JournalEntry] = field(default_factory=list[JournalEntry])
    kept_reviews: list[MonthlyReview] = field(default_factory=list[MonthlyReview])
    empty_reviews: list[MonthlyReview] = field(default_factory=list[MonthlyReview])

    @property
    def history(self) -> list[str]:
        """Why the plan has history, one sentence each; empty when it has none."""
        reasons: list[str] = []
        if self.filled:
            symbols = ", ".join(sorted({order.symbol for order in self.filled}))
            reasons.append(
                f"{plural(len(self.filled), 'paper order')} bought shares ({symbols}). "
                "Those trades are real history on the paper account."
            )
        if self.entries:
            first = self.entries[0].date
            reasons.append(
                f"The journal has {plural(len(self.entries), 'entry', 'entries')} this plan "
                f"judges, from {first:%Y-%m-%d}."
            )
        if self.kept_reviews:
            months = ", ".join(review.month for review in self.kept_reviews)
            reasons.append(f"The review of {months} was written, closed or reopened, and is kept.")
        return reasons

    @property
    def can_delete(self) -> bool:
        return not self.history

    @property
    def edit_blockers(self) -> list[str]:
        """Why the numbers cannot be edited in place; empty when they can."""
        reasons = list(self.history)
        if self.plan.previous is not None:
            reasons.append(
                f"This plan was already changed (it is version {self.plan.version}), so its "
                "numbers are kept as versions."
            )
        if self.empty_reviews and not self.kept_reviews:
            months = ", ".join(review.month for review in self.empty_reviews)
            reasons.append(
                f"The buy window of {months} closed under these numbers, so that month is "
                "judged by them."
            )
        return reasons

    @property
    def can_edit(self) -> bool:
        return not self.edit_blockers


def plan_state(plan: MethodPlan) -> PlanState:
    """Sort the plan's orders, entries and reviews. A handful of queries, run on the method page,
    the change page, and the edit and delete pages."""
    versions = plan.versions()
    orders = list(PaperOrder.objects.filter(plan__in=versions).order_by("month", "symbol", "pk"))
    filled = [order for order in orders if order.filled_qty > 0]
    open_orders = [order for order in orders if not order.final and order.filled_qty == 0]
    unfilled = [order for order in orders if order.final and order.filled_qty == 0]
    open_entry_ids = {order.journal_entry_id for order in open_orders if order.journal_entry_id}
    entries = [
        entry
        for entry in JournalEntry.objects.filter(
            account=plan.account, date__gte=versions[0].started_on
        )
        if entry.pk not in open_entry_ids
    ]
    reviews = list(MonthlyReview.objects.filter(plan__in=versions).order_by("month", "pk"))
    with_events = set(
        ReviewEvent.objects.filter(review__in=reviews).values_list("review_id", flat=True)
    )
    kept = [review for review in reviews if is_kept(review, with_events)]
    empty = [review for review in reviews if not is_kept(review, with_events)]
    return PlanState(
        plan=plan,
        versions=versions,
        filled=filled,
        open_orders=open_orders,
        unfilled_orders=unfilled,
        entries=entries,
        kept_reviews=kept,
        empty_reviews=empty,
    )


def is_kept(review: MonthlyReview, with_events: set[int]) -> bool:
    """A review someone wrote in, closed or reopened is history; one the app opened when the
    window closed, and nobody touched, is not."""
    written = any(text.strip() for text in (review.did, review.rules_said, review.next_month))
    return review.closed or written or review.pk in with_events


class PlanHasHistory(Exception):
    """The plan cannot be deleted; the message lists why."""


def delete_plan(plan: MethodPlan) -> PlanState:
    """Delete the plan, every version of it, its empty reviews and its unfilled order rows, in one
    transaction, after checking again that it has no history and no order still open. The caller
    cancels open orders first (`paper.orders.withdraw_orders`). Returns what was deleted."""
    with transaction.atomic():
        state = plan_state(plan)
        if state.history:
            raise PlanHasHistory(" ".join(state.history))
        if state.open_orders:
            raise PlanHasHistory(
                f"{plural(len(state.open_orders), 'order')} at Alpaca still open; cancel first."
            )
        for review in state.empty_reviews:
            review.delete()
        for order in state.unfilled_orders:
            order.delete()
        # Newest first: `previous` protects each version from being deleted under its successor.
        for version in reversed(state.versions):
            version.delete()
    return state
