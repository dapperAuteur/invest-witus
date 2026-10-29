"""Where every URL of the site starts. Each app lists its own paths; this file includes them."""

from django.contrib import admin
from django.urls import include, path

from invest_witus_site import health

urlpatterns = [
    # The owner's back office. Every page under it requires a staff login (chapter 05).
    path("admin/", admin.site.urls),
    # Up, version, database: what a monitor asks after a deploy (chapter 06).
    path("healthz/", health.healthz, name="healthz"),
    # Sign in with WitUS: login, callback and logout (chapter 07).
    path("auth/witus/", include("invest_witus_site.accounts.urls")),
    # The signed-in owner's accounts, valued at the latest stored closes (chapter 08).
    path("accounts/", include("invest_witus_site.holdings.urls")),
    # The watch list's add and remove actions on an account page (chapter 09). The `pk` captured
    # here is passed on to the included views.
    path("accounts/<int:pk>/watch/", include("invest_witus_site.watchlist.urls")),
    # The method an account runs, its journal and the review, in three views (chapter 10).
    path("accounts/<int:pk>/method/", include("invest_witus_site.methods.urls")),
    # The nightly price pull, called by Vercel's cron with the bearer secret (chapter 08).
    path("api/cron/", include("invest_witus_site.prices.urls")),
    path("", include("invest_witus_site.pages.urls")),
]
