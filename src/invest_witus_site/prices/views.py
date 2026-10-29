"""`GET /api/cron/pull-prices/`: the nightly pull, called by Vercel's cron, since chapter 11 the
paper order check after it, and since chapter 13 the retry of what WitUS Inbox has not taken.

Vercel sends the project's `CRON_SECRET` as `Authorization: Bearer <value>` with every cron
request (its docs, read October 28, 2026). The route compares that header with the setting in
constant time and answers 403 to anything else. With no secret configured it answers 503 and runs
nothing: a deploy that forgot the variable fails closed instead of pulling for anyone who asks.
"""

import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from invest_witus_site.paper.alpaca import AlpacaError, keys_configured, paper_client
from invest_witus_site.paper.orders import sync_orders
from invest_witus_site.prices.pull import DAYS_BACK, pull, symbol_universe
from invest_witus_site.prices.sources import source_from_settings
from invest_witus_site.reports.delivery import send_unsent
from invest_witus_site.reports.inbox import configured as inbox_configured

log = logging.getLogger(__name__)


def bearer_matches(header: str, secret: str) -> bool:
    """`compare_digest` takes the same time whether the first or the last byte differs."""
    return secrets.compare_digest(header.encode("utf-8"), f"Bearer {secret}".encode())


@never_cache
@require_GET
def pull_prices_cron(request: HttpRequest) -> JsonResponse:
    secret = settings.CRON_SECRET
    if not secret:
        log.error("cron: CRON_SECRET is not set; the pull did not run")
        return JsonResponse({"error": "CRON_SECRET is not set"}, status=503)
    if not bearer_matches(request.headers.get("Authorization", ""), secret):
        return JsonResponse({"error": "forbidden"}, status=403)
    today = timezone.localdate()
    result = pull(
        source_from_settings(), symbol_universe(), today - timedelta(days=DAYS_BACK), today
    )
    body = result.as_dict()
    # Chapter 11: then the paper orders, once the owner's Alpaca paper keys are set. Without them
    # the body is chapter 08's, unchanged. A failure is reported in the body; the prices stand.
    if keys_configured():
        try:
            body["orders"] = sync_orders(paper_client()).as_dict()
        except AlpacaError as error:
            body["orders"] = {"error": error.message}
    # Chapter 13: then every report and waitlist copy WitUS Inbox has not taken yet, once Inbox is
    # configured. Without it the body is unchanged, as with the Alpaca step above.
    if inbox_configured():
        body["inbox"] = send_unsent().as_dict()
    # Which schedule fired, when more than one cron shares a path; empty for a call by hand.
    body["schedule"] = request.headers.get("x-vercel-cron-schedule", "")
    log.info("cron: pull-prices %s", body)
    return JsonResponse(body)
