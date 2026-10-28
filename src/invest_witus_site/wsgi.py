"""WSGI entry point: what a web server calls to hand Django a request."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "invest_witus_site.settings")

application = get_wsgi_application()
