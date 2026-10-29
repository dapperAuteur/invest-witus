"""The owner's accounts, outside the admin: a list, and one account valued at the latest closes
with its watch list underneath (chapter 09) and a line naming the method it runs (chapter 10).

Both views sit behind `login_required`, which sends a visitor to `LOGIN_URL` (the WitUS sign-in,
chapter 07), and both read only the accounts the signed-in user owns. Someone else's account is a
404, not a 403: the page does not say whether the id exists.
"""

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from invest_witus_site.holdings.models import Account
from invest_witus_site.methods.models import MethodPlan
from invest_witus_site.methods.momentum import badges_for
from invest_witus_site.prices.manual import HISTORY_RANGES
from invest_witus_site.prices.portfolio import value_snapshot, watch_list
from invest_witus_site.watchlist.forms import WatchForm


@login_required
def account_list(request: HttpRequest) -> HttpResponse:
    accounts = Account.objects.filter(owner=request.user)
    return render(request, "holdings/account_list.html", {"accounts": accounts})


@login_required
def account_detail(request: HttpRequest, pk: int) -> HttpResponse:
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    return account_page(request, account)


def account_page(
    request: HttpRequest, account: Account, watch_form: WatchForm | None = None
) -> HttpResponse:
    """The account page: the latest statement valued, then the watch list with its add form.
    The ownership check is the caller's. Chapter 09's add view renders the page again through
    this function, with the bound form, when nothing in a submission could be added."""
    today = timezone.localdate()
    snapshot = account.latest_snapshot()
    valuation = value_snapshot(snapshot, today) if snapshot is not None else None
    plan = MethodPlan.active_for(account)
    watch = watch_list(account, today)
    context = {
        "account": account,
        "snapshot": snapshot,
        "valuation": valuation,
        "watch": watch,
        "watch_form": watch_form or WatchForm(),
        # Chapter 10: the method this account runs, or None; the method page holds the rest.
        "method_plan": plan,
        # Chapter 14: each watched symbol's 12-1 badge, on an account running 12-1 momentum only.
        "momentum_badges": (
            badges_for([row.item.symbol for row in watch.rows], today)
            if plan is not None and plan.is_momentum
            else None
        ),
        # The Get history form's choices beside each watched symbol (2026-10-29).
        "history_ranges": [(value, label) for value, (label, _) in HISTORY_RANGES.items()],
    }
    return render(request, "holdings/account_detail.html", context)
