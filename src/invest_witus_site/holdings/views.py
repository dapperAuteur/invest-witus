"""The owner's accounts, outside the admin: a list, and one account valued at the latest closes.

Both views sit behind `login_required`, which sends a visitor to `LOGIN_URL` (the WitUS sign-in,
chapter 07), and both read only the accounts the signed-in user owns. Someone else's account is a
404, not a 403: the page does not say whether the id exists.
"""

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from invest_witus_site.holdings.models import Account
from invest_witus_site.prices.portfolio import value_snapshot


@login_required
def account_list(request: HttpRequest) -> HttpResponse:
    accounts = Account.objects.filter(owner=request.user)
    return render(request, "holdings/account_list.html", {"accounts": accounts})


@login_required
def account_detail(request: HttpRequest, pk: int) -> HttpResponse:
    account = get_object_or_404(Account, pk=pk, owner=request.user)
    snapshot = account.latest_snapshot()
    valuation = value_snapshot(snapshot, timezone.localdate()) if snapshot is not None else None
    context = {"account": account, "snapshot": snapshot, "valuation": valuation}
    return render(request, "holdings/account_detail.html", context)
