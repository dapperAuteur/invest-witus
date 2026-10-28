"""Values every template gets without each view passing them."""

from datetime import UTC, datetime

from django.conf import settings
from django.http import HttpRequest

from invest_witus_site.pages import ecosystem


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
