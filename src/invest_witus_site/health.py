"""`GET /healthz/`: is the app up, which version is it, and can it reach its database.

The answer is JSON with three fields and nothing else: no host names, no settings, no error text,
because the page is public. 200 means the database answered; 503 means it did not, which is the
signal a monitor or the owner reads after a deploy.
"""

import logging
import tomllib
from functools import cache

from django.conf import settings
from django.db import DatabaseError, connection
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

log = logging.getLogger(__name__)


@cache
def app_version() -> str:
    """The `version` from `pyproject.toml`, read once. The file ships with the app."""
    with open(settings.BASE_DIR / "pyproject.toml", "rb") as f:
        return str(tomllib.load(f)["project"]["version"])


def database_answers() -> bool:
    """One round trip: the smallest query the database can run."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError as error:
        # The class name says what kind of failure it was; the message could name a host.
        log.error("healthz: database check failed with %s", type(error).__name__)
        return False
    return True


@never_cache
@require_GET
def healthz(request: HttpRequest) -> JsonResponse:
    ok = database_answers()
    body = {"status": "ok" if ok else "degraded", "version": app_version(), "database": ok}
    return JsonResponse(body, status=200 if ok else 503)
