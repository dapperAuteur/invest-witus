"""A company's recent filings and key numbers from SEC EDGAR, kept in the app's own tables so a
page never asks the SEC (chapter 16, decisions 177 to 184).

`SecCompany` is what EDGAR says a symbol is (a company with a CIK, a fund, or not listed), checked
against the ticker maps at most once a day. `Filing` holds the last eight 10-K, 10-Q and 8-K
filings, `KeyFact` the figures of the Key numbers table's concepts, both replaced whole on each
refresh. `SecPause` is the one row that says the SEC refused us (403 or 429) and until when the
app leaves it alone, shared by every Vercel function through the database.
"""

import datetime
from decimal import Decimal
from typing import Any

from django.db import models

CIK_LENGTH = 10
FORM_MAX = 20
CONCEPT_MAX = 120
# The three kinds, as the strings the column holds (compared as strings, like `Account.kind`).
COMPANY = "company"
FUND = "fund"
NOT_LISTED = "not listed"


class SecCompany(models.Model):
    """One row per symbol: the CIK the ticker map gave it, what kind of filer it is, and when
    the filings and the figures were last stored."""

    class Kind(models.TextChoices):
        COMPANY = COMPANY, "Company"
        FUND = FUND, "Fund"
        NOT_LISTED = NOT_LISTED, "Not listed with the SEC"

    symbol: models.CharField[str, str] = models.CharField(max_length=20, unique=True)
    cik: models.CharField[str, str] = models.CharField(
        max_length=CIK_LENGTH, blank=True, help_text="Ten digits with leading zeros."
    )
    name: models.CharField[str, str] = models.CharField(max_length=200, blank=True)
    kind: models.CharField[str, str] = models.CharField(
        max_length=20, choices=Kind.choices, default=Kind.NOT_LISTED
    )
    checked_at: models.DateTimeField[datetime.datetime, datetime.datetime] = models.DateTimeField(
        help_text="When the ticker maps were last read for this symbol."
    )
    filings_fetched_at: models.DateTimeField[datetime.datetime | None, datetime.datetime | None] = (
        models.DateTimeField(null=True, blank=True)
    )
    facts_fetched_at: models.DateTimeField[datetime.datetime | None, datetime.datetime | None] = (
        models.DateTimeField(null=True, blank=True)
    )
    problem: models.CharField[str, str] = models.CharField(
        max_length=300, blank=True, help_text="Why the last refresh failed; empty after a good one."
    )
    problem_at: models.DateTimeField[datetime.datetime | None, datetime.datetime | None] = (
        models.DateTimeField(null=True, blank=True)
    )

    class Meta:
        ordering = ["symbol"]
        verbose_name = "SEC company"
        verbose_name_plural = "SEC companies"

    def __str__(self) -> str:
        return f"{self.symbol} ({self.Kind(self.kind).label})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.symbol = self.symbol.strip().upper()
        super().save(*args, **kwargs)


class Filing(models.Model):
    """One of a company's recent 10-K, 10-Q or 8-K filings, with its document's address on
    sec.gov. The page links there; it never copies the document."""

    symbol: models.CharField[str, str] = models.CharField(max_length=20)
    cik: models.CharField[str, str] = models.CharField(max_length=CIK_LENGTH)
    form: models.CharField[str, str] = models.CharField(max_length=FORM_MAX)
    filing_date: models.DateField[datetime.date, datetime.date] = models.DateField()
    report_date: models.DateField[datetime.date | None, datetime.date | None] = models.DateField(
        null=True, blank=True, help_text="The period the filing reports on, when it names one."
    )
    accession: models.CharField[str, str] = models.CharField(max_length=25)
    primary_document: models.CharField[str, str] = models.CharField(max_length=200)
    document_url: models.URLField[str, str] = models.URLField(max_length=400)
    description: models.CharField[str, str] = models.CharField(max_length=200, blank=True)
    fetched_at: models.DateTimeField[datetime.datetime, datetime.datetime] = models.DateTimeField()

    class Meta:
        ordering = ["symbol", "-filing_date", "-accession"]
        constraints = [
            models.UniqueConstraint(fields=["symbol", "accession"], name="filing_once_per_symbol")
        ]

    def __str__(self) -> str:
        return f"{self.symbol} {self.form} {self.filing_date:%Y-%m-%d}"


class KeyFact(models.Model):
    """One reported figure of a Key numbers concept. `period_start` is empty for a value on one
    day (a balance sheet line)."""

    symbol: models.CharField[str, str] = models.CharField(max_length=20)
    concept: models.CharField[str, str] = models.CharField(max_length=CONCEPT_MAX)
    unit: models.CharField[str, str] = models.CharField(max_length=20)
    period_start: models.DateField[datetime.date | None, datetime.date | None] = models.DateField(
        null=True, blank=True
    )
    period_end: models.DateField[datetime.date, datetime.date] = models.DateField()
    # Companies report whole dollars and shares; four places leave room for the few that do not.
    value: models.DecimalField[Decimal, Decimal] = models.DecimalField(
        max_digits=28, decimal_places=4
    )
    form: models.CharField[str, str] = models.CharField(max_length=FORM_MAX)
    filed: models.DateField[datetime.date, datetime.date] = models.DateField()
    accession: models.CharField[str, str] = models.CharField(max_length=25)
    fiscal_year: models.IntegerField[int | None, int | None] = models.IntegerField(
        null=True, blank=True
    )
    fiscal_period: models.CharField[str, str] = models.CharField(max_length=4, blank=True)
    fetched_at: models.DateTimeField[datetime.datetime, datetime.datetime] = models.DateTimeField()

    class Meta:
        ordering = ["symbol", "concept", "period_end"]
        indexes = [models.Index(fields=["symbol", "concept"], name="keyfact_symbol_concept")]

    def __str__(self) -> str:
        return f"{self.symbol} {self.concept} {self.period_end:%Y-%m-%d}: {self.value}"


class SecPause(models.Model):
    """The SEC's last refusal (403 or 429) and the time before which no request is sent. One
    row, id 1."""

    until: models.DateTimeField[datetime.datetime, datetime.datetime] = models.DateTimeField()
    status: models.IntegerField[int, int] = models.IntegerField()
    noted_at: models.DateTimeField[datetime.datetime, datetime.datetime] = models.DateTimeField()

    class Meta:
        verbose_name = "SEC pause"
        verbose_name_plural = "SEC pause"

    def __str__(self) -> str:
        return f"SEC answered {self.status}; paused until {self.until:%Y-%m-%d %H:%M}"
