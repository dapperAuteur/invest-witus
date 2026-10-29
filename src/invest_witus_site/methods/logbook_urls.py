"""The logbook's routes (chapter 12). `invest_witus_site/urls.py` mounts this file under
`accounts/<int:pk>/logbook/`, beside the method page rather than inside it: the logbook is the
account's journal, and it stays when a plan ends."""

from django.urls import path

from invest_witus_site.methods import logbook

urlpatterns = [
    path("", logbook.logbook, name="logbook"),
    path("export.csv", logbook.logbook_csv, name="logbook-csv"),
    path("<int:entry_pk>/edit/", logbook.edit_entry, name="logbook-edit"),
]
