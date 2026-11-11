"""The stored SEC data, read in the admin. Delete a company's row to make the next refresh read
the ticker maps again; delete the pause to lift it."""

from django.contrib import admin

from invest_witus_site.filings.models import Filing, KeyFact, SecCompany, SecPause


@admin.register(SecCompany)
class SecCompanyAdmin(admin.ModelAdmin[SecCompany]):
    list_display = (
        "symbol",
        "kind",
        "cik",
        "name",
        "filings_fetched_at",
        "facts_fetched_at",
        "problem",
    )
    list_filter = ("kind",)
    search_fields = ("symbol", "name", "cik")


@admin.register(Filing)
class FilingAdmin(admin.ModelAdmin[Filing]):
    list_display = ("symbol", "form", "filing_date", "report_date", "accession", "fetched_at")
    list_filter = ("form",)
    search_fields = ("symbol", "accession")
    date_hierarchy = "filing_date"


@admin.register(KeyFact)
class KeyFactAdmin(admin.ModelAdmin[KeyFact]):
    list_display = (
        "symbol",
        "concept",
        "period_start",
        "period_end",
        "value",
        "unit",
        "form",
        "filed",
    )
    list_filter = ("form", "unit")
    search_fields = ("symbol", "concept")


@admin.register(SecPause)
class SecPauseAdmin(admin.ModelAdmin[SecPause]):
    list_display = ("status", "until", "noted_at")
