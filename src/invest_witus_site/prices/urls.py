"""The cron route. `invest_witus_site/urls.py` mounts this file at `api/cron/`."""

from django.urls import path

from invest_witus_site.prices import views

urlpatterns = [
    path("pull-prices/", views.pull_prices_cron, name="cron-pull-prices"),
]
