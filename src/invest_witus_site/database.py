"""Turn a `DATABASE_URL` into the dictionary Django's `DATABASES` setting wants.

Two shapes are accepted:

- `postgresql://user:password@host:port/name?sslmode=require`, which is what Neon hands out
  (chapter 06). Only the libpq options Neon's strings carry are allowed in the query string.
- `sqlite:///data/private/name.sqlite3` (relative to the repository) or `sqlite:////tmp/name.sqlite3`
  (absolute), for a laptop or a test.

Anything else raises `ValueError` with a message that names the problem, so a typo in a dashboard
fails at startup, where the owner sees it, not at the first request. The `dj-database-url` package
does the same job; forty lines keep the dependency list short and the rules readable.
"""

from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

POSTGRES_SCHEMES = ("postgres", "postgresql")
SQLITE_PREFIX = "sqlite:///"
# libpq connection options a Neon URL may carry. Anything else is refused rather than passed on.
POSTGRES_OPTIONS = ("sslmode", "channel_binding")


def database_from_url(url: str, base_dir: Path) -> dict[str, object]:
    """Django's `DATABASES["default"]` for `url`. `base_dir` anchors a relative SQLite path."""
    parts = urlsplit(url)
    if parts.scheme == "sqlite":
        return sqlite_database(url, base_dir)
    if parts.scheme in POSTGRES_SCHEMES:
        return postgres_database(url)
    raise ValueError(
        f"DATABASE_URL must start with postgresql:// or {SQLITE_PREFIX}, "
        f"not {parts.scheme or url!r}"
    )


def sqlite_database(url: str, base_dir: Path) -> dict[str, object]:
    if not url.startswith(SQLITE_PREFIX):
        raise ValueError(f"a SQLite DATABASE_URL looks like {SQLITE_PREFIX}path/to/file.sqlite3")
    path = url.removeprefix(SQLITE_PREFIX)
    if not path:
        raise ValueError("a SQLite DATABASE_URL needs a file path after sqlite:///")
    name = Path(path) if path.startswith("/") else base_dir / path
    return {"ENGINE": "django.db.backends.sqlite3", "NAME": name}


def postgres_database(url: str) -> dict[str, object]:
    parts = urlsplit(url)
    name = parts.path.removeprefix("/")
    if not parts.hostname or not name:
        raise ValueError(
            "a Postgres DATABASE_URL needs a host and a database name: "
            "postgresql://user:password@host/name"
        )
    options: dict[str, str] = {"sslmode": "require"}  # Neon's Django guide; a URL may override it
    for key, values in parse_qs(parts.query, keep_blank_values=True).items():
        if key not in POSTGRES_OPTIONS:
            raise ValueError(
                f"DATABASE_URL option {key!r} is not one of {', '.join(POSTGRES_OPTIONS)}"
            )
        options[key] = values[-1]
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(name),
        "USER": unquote(parts.username or ""),
        "PASSWORD": unquote(parts.password or ""),
        "HOST": parts.hostname,
        "PORT": str(parts.port) if parts.port else "",
        "OPTIONS": options,
        # Neon's pooled URL goes through PgBouncer in transaction mode, which cannot hold a
        # server-side cursor across statements (Django's docs on transaction pooling).
        "DISABLE_SERVER_SIDE_CURSORS": True,
        # Keep a connection for a minute and check it before reuse: Neon suspends an idle compute
        # after five minutes, and a health check reconnects instead of failing the request.
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
    }
