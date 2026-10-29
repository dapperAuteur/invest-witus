"""The owner's own pages. `invest_witus_site/urls.py` mounts this file at `accounts/`."""

from django.urls import path

from invest_witus_site.holdings import views

urlpatterns = [
    path("", views.account_list, name="account-list"),
    path("<int:pk>/", views.account_detail, name="account-detail"),
]
