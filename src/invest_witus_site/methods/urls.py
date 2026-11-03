"""The method page and its actions. `invest_witus_site/urls.py` mounts this file under
`accounts/<int:pk>/method/`, and the `pk` captured there reaches every view. Chapter 12 adds the
plan's change form and a month's review, with its close and reopen. 2026-11-02 adds the saved
default view and the edit and delete pages of a plan with no history (decisions 155 to 158)."""

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
    # 2026-11-02: the saved default view, and a plan with no history edited or deleted.
    path("default-view/", views.set_default_view, name="method-default-view"),
    path("edit/", views.edit_plan, name="method-edit"),
    path("delete/", views.delete_plan, name="method-delete"),
    re_path(rf"^review/{MONTH}/$", views.review_month, name="method-review"),
    re_path(rf"^review/{MONTH}/close/$", views.close_month, name="method-review-close"),
    re_path(rf"^review/{MONTH}/reopen/$", views.reopen_month, name="method-review-reopen"),
]
