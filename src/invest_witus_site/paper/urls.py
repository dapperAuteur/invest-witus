"""The paper account page and its two actions. `invest_witus_site/urls.py` mounts this file under
`accounts/<int:pk>/paper/`, and the `pk` captured there reaches every view."""

from django.urls import path

from invest_witus_site.paper import views

urlpatterns = [
    path("", views.paper_account, name="paper-account"),
    path("confirm/", views.confirm_buys, name="paper-confirm"),
    path("sync/", views.sync_now, name="paper-sync"),
    # Decision 159: choose the account's key slot, check what it reaches, link or unlink.
    path("link/", views.link_alpaca, name="paper-link"),
]
