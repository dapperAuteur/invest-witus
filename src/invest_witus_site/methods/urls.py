"""The method page and its actions. `invest_witus_site/urls.py` mounts this file under
`accounts/<int:pk>/method/`, and the `pk` captured there reaches every view. Chapter 12 adds the
plan's change form and a month's review, with its close and reopen."""

from django.urls import path, re_path

from invest_witus_site.methods import views

# A month in a URL is `YYYY-MM`. A regular expression in the route itself, so anything else is
# not a route at all and answers 404 before a view runs.
MONTH = r"(?P<month>\d{4}-\d{2})"

urlpatterns = [
    path("", views.method_page, name="method-page"),
    path("start/", views.start_method, name="method-start"),
    path("log/", views.log_entry, name="method-log"),
    path("change/", views.change_plan, name="method-change"),
    re_path(rf"^review/{MONTH}/$", views.review_month, name="method-review"),
    re_path(rf"^review/{MONTH}/close/$", views.close_month, name="method-review-close"),
    re_path(rf"^review/{MONTH}/reopen/$", views.reopen_month, name="method-review-reopen"),
]
