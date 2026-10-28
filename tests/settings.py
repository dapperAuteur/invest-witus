"""The settings the tests run with: the real ones, plus a secret key.

`settings.py` refuses to start without `DJANGO_SECRET_KEY` when debug is off (chapter 06), and
the tests run with debug off on purpose, so that the production rules (Secure cookies and the
rest) are what they exercise. pytest-django imports the settings before any conftest or fixture
runs, so the key is set here, in the settings module itself. It is not a secret: nothing signed
with it leaves the test run.
"""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-" + "0123456789" * 5)

from invest_witus_site.settings import *  # noqa: E402, F403
