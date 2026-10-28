"""Values every template gets without each view passing them."""

from datetime import UTC, datetime

from django.http import HttpRequest

from invest_witus_site.pages import ecosystem


def site(request: HttpRequest) -> dict[str, object]:
    return {
        "ecosystem_products": ecosystem.products(),
        "infrastructure_products": ecosystem.infrastructure(),
        "year": datetime.now(UTC).year,
    }
