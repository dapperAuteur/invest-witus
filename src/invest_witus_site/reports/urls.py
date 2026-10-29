"""The report form and its thank-you page. `invest_witus_site/urls.py` mounts this at `report/`."""

from django.urls import path

from invest_witus_site.reports import views

urlpatterns = [
    path("", views.report, name="report"),
    path("thanks/", views.thanks, name="report-thanks"),
]
