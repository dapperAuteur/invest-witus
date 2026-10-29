"""The watch list's two actions and a symbol's history page. `invest_witus_site/urls.py` mounts
this file under `accounts/<int:pk>/watch/`, and the `pk` captured there reaches every view."""

from django.urls import path

from invest_witus_site.prices import owner_views
from invest_witus_site.watchlist import views

urlpatterns = [
    path("add/", views.add, name="watch-add"),
    path("<int:item_pk>/remove/", views.remove, name="watch-remove"),
    # Fetch history for selected or for all (2026-10-29): before the symbol paths, so
    # "fetch-history/" is never read as a symbol.
    path("fetch-history/", owner_views.fetch_history_many, name="watch-fetch-history-many"),
    # A watched symbol's closes (2026-10-29). After the two fixed paths, so "add/" stays the form's.
    path("<str:symbol>/", views.history, name="watch-history"),
    # Get history (2026-10-29): one request for a watched symbol's closes over a chosen range.
    path("<str:symbol>/fetch-history/", owner_views.fetch_history, name="watch-fetch-history"),
    # Get description (2026-10-30, decision 150): the symbol's name, exchange and description.
    path("<str:symbol>/profile/", owner_views.fetch_profile, name="watch-fetch-profile"),
]
