"""The watch list's two actions and a symbol's history page. `invest_witus_site/urls.py` mounts
this file under `accounts/<int:pk>/watch/`, and the `pk` captured there reaches every view."""

from django.urls import path

from invest_witus_site.watchlist import views

urlpatterns = [
    path("add/", views.add, name="watch-add"),
    path("<int:item_pk>/remove/", views.remove, name="watch-remove"),
    # A watched symbol's closes (2026-10-29). After the two fixed paths, so "add/" stays the form's.
    path("<str:symbol>/", views.history, name="watch-history"),
]
