"""The owner's accounts, outside the admin: a list, and one account valued at the latest closes
with its watch list underneath (chapter 09).

Both views sit behind `login_required`, which sends a visitor to `LOGIN_URL` (the WitUS sign-in,
chapter 07), and both read only the accounts the signed-in user owns. Someone else's account is a
404, not a 403: the page does not say whether the id exists.
"""

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from invest_witus_site.holdings.models import Account
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
    context = {
        "account": account,
        "snapshot": snapshot,
        "valuation": valuation,
        "watch": watch_list(account, today),
        "watch_form": watch_form or WatchForm(),
    }
    return render(request, "holdings/account_detail.html", context)
