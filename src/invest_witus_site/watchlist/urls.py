"""The watch list's two actions. `invest_witus_site/urls.py` mounts this file under
`accounts/<int:pk>/watch/`, and the `pk` captured there reaches both views."""

from django.urls import path

from invest_witus_site.watchlist import views

urlpatterns = [
    path("add/", views.add, name="watch-add"),
    path("<int:item_pk>/remove/", views.remove, name="watch-remove"),
]
