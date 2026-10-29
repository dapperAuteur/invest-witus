"""The method page and its two actions. `invest_witus_site/urls.py` mounts this file under
`accounts/<int:pk>/method/`, and the `pk` captured there reaches all three views."""

from django.urls import path

from invest_witus_site.methods import views

urlpatterns = [
    path("", views.method_page, name="method-page"),
    path("start/", views.start_method, name="method-start"),
    path("log/", views.log_entry, name="method-log"),
]
