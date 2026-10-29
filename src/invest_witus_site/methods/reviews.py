"""The monthly review: opened when a month's buy window closes, closed by the owner with a short
written review, and reopened only with a reason.

A `MonthlyReview` row is made for every month of the plan whose window has closed, the first time
a page that shows the plan is drawn after that day; its `opened_on` is the day the window closed,
not the day the row was written, so the record says when the review became due whatever day the
owner first looked. Closing asks three questions (what I did, what the rules said, what I'll do
next month) and is refused while the month has a missed buy with no skip to explain it: the PRD's
"a review cannot be closed with an unexplained skip". Every close and every reopen is a
`ReviewEvent`, so the history of a month survives a reopen and a second close.
"""

from datetime import date

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.db import transaction
from django.utils import timezone

from invest_witus.adherence.review import months_due
from invest_witus_site.methods.engine import MethodReview, month_label, span_through
from invest_witus_site.methods.models import (
    MethodPlan,
    MonthlyReview,
    ReviewEvent,
    version_spans,
)


class ReviewRefused(Exception):
    """The review cannot be closed or reopened; the message says why, in a sentence."""


def open_due_reviews(plan: MethodPlan, today: date) -> list[MonthlyReview]:
    """Make the review row for every month of the plan whose window has closed by `today`, one per
    version and month, and return them all, oldest first. Safe to call on every page view: the
    rows that exist are left alone, and `ignore_conflicts` lets two requests race harmlessly."""
    spans = version_spans(plan.versions())
    versions = [span.plan for span in spans]
    existing = set(MonthlyReview.objects.filter(plan__in=versions).values_list("plan_id", "month"))
    missing: list[MonthlyReview] = []
    for span in spans:
        for year, month in months_due(span.plan.to_plan(), span_through(span, today)):
            label = month_label(year, month)
            if (span.plan.pk, label) not in existing:
                window_closed = date(year, month, span.plan.buy_window_days)
                missing.append(MonthlyReview(plan=span.plan, month=label, opened_on=window_closed))
    if missing:
        MonthlyReview.objects.bulk_create(missing, ignore_conflicts=True)
    return list(
        MonthlyReview.objects.filter(plan__in=versions).select_related("plan").order_by("month")
    )


def close_refusal(review: MonthlyReview, context: MethodReview) -> str:
    """The reason the month cannot be closed, or "". Only a missed buy with no skip blocks it:
    any other finding (a late buy, a wrong amount) is what the written review is for."""
    if review.closed:
        return f"{review.month} is already closed."
    row = context.month(review.month)
    if row is not None and row.status == "missed":
        return (
            f"{review.month} has no buy and no skip with a reason. Log a skip that says why "
            "the month had no buy, then close it."
        )
    return ""


def written(review: MonthlyReview) -> str:
    """The three answers as one text, the way the audit trail keeps them."""
    return (
        f"What I did: {review.did}\n"
        f"What the rules said: {review.rules_said}\n"
        f"What I'll do next month: {review.next_month}"
    )


def close_review(
    review: MonthlyReview,
    context: MethodReview,
    *,
    did: str,
    rules_said: str,
    next_month: str,
    by: AbstractBaseUser | AnonymousUser,
) -> None:
    refusal = close_refusal(review, context)
    if refusal:
        raise ReviewRefused(refusal)
    with transaction.atomic():
        review.did, review.rules_said, review.next_month = did, rules_said, next_month
        review.closed_at = timezone.now()
        review.save()
        ReviewEvent.objects.create(
            review=review, action=ReviewEvent.CLOSED, text=written(review), by=user_or_none(by)
        )


def reopen_review(
    review: MonthlyReview, *, reason: str, by: AbstractBaseUser | AnonymousUser
) -> None:
    """Open a closed month again so its entries can change. The written review stays on the row
    and in the closed event; the reopen event keeps the reason."""
    if not review.closed:
        raise ReviewRefused(f"{review.month} is open already.")
    with transaction.atomic():
        review.closed_at = None
        review.save(update_fields=["closed_at"])
        ReviewEvent.objects.create(
            review=review, action=ReviewEvent.REOPENED, text=reason, by=user_or_none(by)
        )


def user_or_none(user: AbstractBaseUser | AnonymousUser) -> AbstractBaseUser | None:
    return user if isinstance(user, AbstractBaseUser) else None
