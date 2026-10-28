"""The WSGI entry file at the repository root: what Vercel runs, and what `runserver` loads.

Vercel finds `manage.py`, reads `WSGI_APPLICATION` from the settings and turns it into a file
path beside `manage.py`. The project's own `wsgi.py` lives in `src/invest_witus_site/`, which
Vercel neither looks in nor puts on the import path, so this file is the bridge: it adds `src/`
to the path and hands over the project's application object.
"""

import sys
from pathlib import Path

SRC = str(Path(__file__).resolve().parent / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from invest_witus_site.wsgi import application  # noqa: E402

__all__ = ["application"]
