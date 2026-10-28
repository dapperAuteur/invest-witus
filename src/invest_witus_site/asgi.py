"""ASGI entry point: the async twin of wsgi.py, for servers that speak ASGI."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "invest_witus_site.settings")

application = get_asgi_application()
