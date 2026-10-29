"""The method page for one account, in three views, and its two POST actions.

`method_page` renders the same context through one of three templates, A, B or C, named as the
research named them (`docs/research/01-ux-benchmarks-and-three-directions.md`, section 5). The
choice comes from `?view=a|b|c`, is remembered in the session, and defaults to A when the
account runs a method and to C when it does not (PRD 7.2: C to start a method, A as the home).
Every view sits behind `login_required` and the same ownership query as chapter 08's pages, so
another owner's account is a 404; nothing here is public.

Chapter 12 adds the plan's change form (`change_plan`) and the month's review page with its two
actions (`review_month`, `close_month`, `reopen_month`). The method page opens the review of every
month whose window has closed, and view A offers to close the oldest one still open.
"""

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from invest_witus.methods.rulebook import available_methods
from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.engine import MethodReview, build_review, rule_lines
from invest_witus_site.methods.forms import (
    CloseReviewForm,
    JournalEntryForm,
    PlanChangeForm,
    ReopenReviewForm,
    StartMethodForm,
)
from invest_witus_site.methods.models import (
    JournalEntry,
    MethodPlan,
    MonthlyReview,
    ReviewEvent,
)
from invest_witus_site.methods.reviews import (
    ReviewRefused,
    close_review,
    open_due_reviews,
    reopen_review,
)
from invest_witus_site.paper.orders import alpaca_allowed, paper_section

# The three views, by letter, as the research and the PRD name them. The order is the switch's.
VIEWS = {
    "a": ("A: The Plan and the Logbook", "methods/_view_a.html"),
    "b": ("B: Method Console", "methods/_view_b.html"),
    "c": ("C: The Lesson Lab", "methods/_view_c.html"),
}
SESSION_KEY = "method_view"


def chosen_view(request: HttpRequest, has_plan: bool) -> str:
    """`?view=` when it names a view (and remember it); else the session's; else the default."""
    asked = request.GET.get("view", "").lower()
    if asked in VIEWS:
        request.session[SESSION_KEY] = asked
        return asked
    saved = request.session.get(SESSION_KEY)
    if isinstance(saved, str) and saved in VIEWS:
        return saved
    return "a" if has_plan else "c"


def through_date(request: HttpRequest, today: date) -> date:
    """`?through=YYYY-MM-DD` reviews up to that day, as chapter 03's command did; anything else
    is today. The page says which day it was reviewed through."""
    try:
        return date.fromisoformat(request.GET.get("through", ""))
    except ValueError:
        return today


@login_required
def method_page(request: HttpRequest, pk: int) -> HttpResponse:
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    return render_method_page(request, account)


def render_method_page(
    request: HttpRequest,
    account: Account,
    start_form: StartMethodForm | None = None,
    entry_form: JournalEntryForm | None = None,
    force_view: str | None = None,
) -> HttpResponse:
    """One context, three templates. The ownership check is the caller's. The two POST views
    render the page again through this function, with a bound form, when a submission fails."""
    today = timezone.localdate()
    through = through_date(request, today)
    plan = MethodPlan.active_for(account)
    entries = JournalEntry.entries_for(account)
    view = force_view or chosen_view(request, plan is not None)
    # Chapter 12: every month whose window closed by today has a review; the oldest still open
    # is the one view A offers to close. Opened against today, never `?through=`.
    month_reviews = open_due_reviews(plan, today) if plan is not None else []
    still_open = [review for review in month_reviews if not review.closed]
    context = {
        "account": account,
        "plan": plan,
        "review": build_review(plan, entries, through) if plan is not None else None,
        "entries": entries,
        "catalog": [(method, rule_lines(method)) for method in available_methods()],
        "start_form": start_form or StartMethodForm(account),
        "entry_form": entry_form or JournalEntryForm(initial={"date": today}),
        "month_reviews": month_reviews,
        "review_to_close": still_open[0] if still_open else None,
        "open_reviews": len(still_open),
        "view": view,
        "view_label": VIEWS[view][0],
        "view_template": VIEWS[view][1],
        "views": [(key, label) for key, (label, _) in VIEWS.items()],
        "through": through,
        "through_query": f"&through={through.isoformat()}" if through != today else "",
        # Chapter 11: this month's buys and the Confirm button, on an account linked to Alpaca
        # paper only. One request to Alpaca (the clock); `None` everywhere else.
        "paper": (
            paper_section(plan)
            if plan is not None and alpaca_allowed(request.user, account)
            else None
        ),
    }
    return render(request, "methods/method_page.html", context)


@login_required
@require_POST
def start_method(request: HttpRequest, pk: int) -> HttpResponse:
    """Create the plan. A refused form draws view C again with the reasons beside the boxes;
    a started method goes to view A, the everyday home, and the session remembers it."""
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    form = StartMethodForm(account, request.POST)
    if not form.is_valid():
        return render_method_page(request, account, start_form=form, force_view="c")
    plan = form.start()
    messages.success(request, f"Started {plan.method().name} on {account.name}.")
    watched_message(request, form.watched)
    request.session[SESSION_KEY] = "a"
    return redirect("method-page", pk=account.pk)


@login_required
@require_POST
def log_entry(request: HttpRequest, pk: int) -> HttpResponse:
    """Add one journal row to the account and come back to the same view."""
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    form = JournalEntryForm(request.POST, instance=JournalEntry(account=account))
    if not form.is_valid():
        return render_method_page(request, account, entry_form=form)
    entry = form.save()
    messages.success(request, f"Logged: {entry}.")
    return redirect("method-page", pk=account.pk)


def watched_message(request: HttpRequest, added: list[str]) -> None:
    """Chapter 14: say which candidates a momentum plan put on the watch list, and why."""
    if added:
        messages.info(
            request,
            "Added to the watch list, so the nightly pull stores their closes: "
            f"{', '.join(added)}. A candidate needs about 13 months of closes to be ranked; "
            "the nightly pull fetches two years, and Get history fetches them now.",
        )


# --- Chapter 12: change or end the plan -----------------------------------------------------------


@login_required
def change_plan(request: HttpRequest, pk: int) -> HttpResponse:
    """GET draws the form with the plan's numbers; POST writes a new version or ends the plan."""
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    plan = MethodPlan.active_for(account)
    if plan is None:
        messages.info(request, "No method runs on this account, so there is no plan to change.")
        return redirect("method-page", pk=account.pk)
    today = timezone.localdate()
    form = PlanChangeForm(plan, today, request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        written = form.apply()
        watched_message(request, form.watched)
        if written.active:
            messages.success(
                request,
                f"Version {written.version} of the plan starts on {written.started_on:%Y-%m-%d}. "
                f"Version {plan.version} keeps its months, judged by its own numbers.",
            )
        else:
            messages.success(
                request,
                f"Ended {plan.method().name} on {account.name}. Its months and reviews stay; "
                "start a new method when you are ready.",
            )
            # With no plan, the method page is the Lesson Lab, where a new one starts.
            request.session[SESSION_KEY] = "c"
        return redirect("method-page", pk=account.pk)
    context = {"account": account, "plan": plan, "form": form, "versions": plan.versions()}
    return render(request, "methods/plan_change.html", context)


# --- Chapter 12: the month's review ---------------------------------------------------------------


def review_or_404(account: Account, month: str) -> MonthlyReview:
    """The account's review for the month: the newest plan's, if two plans share the month. The
    running plan's due reviews are opened first, so a link to a month works before the method
    page has been drawn that day."""
    plan = MethodPlan.active_for(account)
    if plan is not None:
        open_due_reviews(plan, timezone.localdate())
    review = (
        MonthlyReview.objects.filter(plan__account=account, month=month)
        .select_related("plan")
        .order_by("-plan__pk")
        .first()
    )
    if review is None:
        raise Http404("No review for that month.")
    return review


def month_context(review: MonthlyReview) -> MethodReview:
    """The plan's whole review through today, from the newest version of the review's plan."""
    plan = review.plan.latest_version()
    entries = JournalEntry.entries_for(plan.account)
    return build_review(plan, entries, timezone.localdate())


def rules_said_draft(context: MethodReview, month: str) -> str:
    """The second answer's starting text: the month's findings, or the sentence that none."""
    found = [f for f in context.findings if f.month == month]
    if not found:
        return "Every rule passed this month."
    lines: list[str] = []
    for finding in found:
        line = finding.message
        if finding.explained:
            line += f" (skipped: {finding.explanation})"
        lines.append(line)
    return " ".join(lines)


def render_review_page(
    request: HttpRequest,
    account: Account,
    review: MonthlyReview,
    close_form: CloseReviewForm | None = None,
    reopen_form: ReopenReviewForm | None = None,
) -> HttpResponse:
    context = month_context(review)
    row = context.month(review.month)
    entries = [entry for entry in context.entries if f"{entry.date:%Y-%m}" == review.month]
    page = {
        "account": account,
        "review": review,
        "version": review.plan,
        "row": row,
        "findings": [f for f in context.findings if f.month == review.month],
        "entries": entries,
        "events": list(ReviewEvent.objects.filter(review=review).select_related("by")),
        "close_form": close_form
        or CloseReviewForm(initial={"rules_said": rules_said_draft(context, review.month)}),
        "reopen_form": reopen_form or ReopenReviewForm(),
    }
    return render(request, "methods/review_month.html", page)


@login_required
def review_month(request: HttpRequest, pk: int, month: str) -> HttpResponse:
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    return render_review_page(request, account, review_or_404(account, month))


@login_required
@require_POST
def close_month(request: HttpRequest, pk: int, month: str) -> HttpResponse:
    """Close the month with the three answers. Refused, with the page drawn again, when a field
    is empty or the month has a missed buy that no skip explains."""
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    review = review_or_404(account, month)
    if review.closed:
        messages.error(request, f"{review.month} is already closed.")
        return redirect("method-review", pk=account.pk, month=review.month)
    form = CloseReviewForm(request.POST)
    if not form.is_valid():
        return render_review_page(request, account, review, close_form=form)
    try:
        close_review(review, month_context(review), by=request.user, **form.cleaned_data)
    except ReviewRefused as refused:
        form.add_error(None, str(refused))
        return render_review_page(request, account, review, close_form=form)
    messages.success(request, f"Closed {review.month}. Its entries are read-only now.")
    return redirect("method-page", pk=account.pk)


@login_required
@require_POST
def reopen_month(request: HttpRequest, pk: int, month: str) -> HttpResponse:
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    review = review_or_404(account, month)
    form = ReopenReviewForm(request.POST)
    if not form.is_valid():
        return render_review_page(request, account, review, reopen_form=form)
    try:
        reopen_review(review, reason=form.cleaned_data["reason"], by=request.user)
    except ReviewRefused as refused:
        messages.error(request, str(refused))
    else:
        messages.success(request, f"Reopened {review.month}. Its entries can change again.")
    return redirect("method-review", pk=account.pk, month=review.month)
