"""Values every template gets without each view passing them."""

from datetime import UTC, datetime

from django.conf import settings
from django.http import HttpRequest
from django.urls import reverse

from invest_witus_site.pages import ecosystem
from invest_witus_site.reports.forms import ReportForm


def site(request: HttpRequest) -> dict[str, object]:
    return {
        "ecosystem_products": ecosystem.products(),
        "infrastructure_products": ecosystem.infrastructure(),
        "year": datetime.now(UTC).year,
        # Vercel Web Analytics (chapter 06a): the base template renders its two script tags only
        # when the first is True, and names the script by the second.
        "vercel_analytics_enabled": settings.VERCEL_ANALYTICS_ENABLED,
        "vercel_analytics_script_path": settings.VERCEL_ANALYTICS_SCRIPT_PATH,
    }


def help_bubble(request: HttpRequest) -> dict[str, object]:
    """The floating Help bubble (2026-10-30, decision 151), on every page but the report form
    itself. Signed out it is a plain link to `/report/`, so a public page still carries no
    script. Signed in, the base template also renders the report form in a `<dialog>` that
    `pages/help.js` opens; the form's ids start `help_` so they never clash with the page's."""
    on = request.path != reverse("report")
    form = None
    if on and request.user.is_authenticated:
        form = ReportForm(initial={"page": request.path}, signed_in=True, auto_id="help_%s")
    return {"help_bubble_on": on, "help_form": form}
