"""Where every URL of the site starts. Each app lists its own paths; this file includes them."""

from django.urls import include, path

urlpatterns = [
    path("", include("invest_witus_site.pages.urls")),
]
