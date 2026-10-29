"""The owner's own pages. `invest_witus_site/urls.py` mounts this file at `accounts/`."""

from django.urls import path

from invest_witus_site.holdings import views
from invest_witus_site.prices import owner_views
from invest_witus_site.watchlist import views as watch_views

urlpatterns = [
    path("", views.account_list, name="account-list"),
    path("<int:pk>/", views.account_detail, name="account-detail"),
    # Fetch prices now (2026-10-29): the nightly pull for the owner's symbols, from either page.
    path("fetch-prices/", owner_views.fetch_now, name="fetch-prices"),
    path("<int:pk>/fetch-prices/", owner_views.fetch_now_for_account, name="account-fetch-prices"),
    # Compare (2026-10-29): up to six of the account's symbols on one chart, rebased to 100.
    path("<int:pk>/compare/", watch_views.compare, name="compare"),
]
