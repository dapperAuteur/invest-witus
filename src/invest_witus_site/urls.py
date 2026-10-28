"""Where every URL of the site starts. Each app lists its own paths; this file includes them."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # The owner's back office. Every page under it requires a staff login (chapter 05).
    path("admin/", admin.site.urls),
    path("", include("invest_witus_site.pages.urls")),
]
