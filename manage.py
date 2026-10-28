#!/usr/bin/env python
"""Django's command-line tool: `uv run --env-file .env python manage.py <command>`."""

import os
import sys
from pathlib import Path

# The Django project lives under src/. `uv sync` installs it into the virtual environment, but a
# server that installs only the dependencies (Vercel's build does) must still find it, so src/
# goes onto the import path here, before Django imports the settings.
SRC = str(Path(__file__).resolve().parent / "src")


def main() -> None:
    if SRC not in sys.path:
        sys.path.insert(0, SRC)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "invest_witus_site.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
