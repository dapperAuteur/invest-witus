# Chapter 06a: Vercel Web Analytics: page views, switched on per environment

**Starts from:** tag `v06`. **Ends at:** tag `v06a`.
**Written against:** Python 3.14.10, uv 0.13.6, Django 5.2.18, and Vercel's Web Analytics documentation as read
on October 28, 2026 (the quickstart last updated June 8, 2026; pricing, August 25, 2026; privacy, June 26, 2026).
Dashboards change; every label below has its source in the references, and when the page and this text
disagree, the page wins.
**Goal:** the public pages count their visitors with Vercel Web Analytics, and only where the owner turned it
on. Two script tags in the base template, rendered when the app runs on Vercel and one variable says so. The
script's path comes from the project, through a variable, with a labeled fallback. The privacy page says what
is collected. Nothing is installed and nothing new runs.
**Time:** 30 to 45 minutes for the code and tests, then 10 minutes in the Vercel dashboard.

This is an addendum to chapter 06, numbered `06a` so that it sorts after the deploy chapter it belongs to and
before chapter 07, which it does not change. The listings are generated from tag `v06a` by
`scripts/render_chapter.py`, as in every chapter from 04 on.

## What you will learn

- **A switch that is on only on a server, and only when the owner says so:** two conditions in one
  setting, and tests for each combination.
- **A context processor:** the one place a value is handed to every template.
- **What a plain-HTML analytics snippet does:** a two-line queue, a deferred script, and why the order
  matters.
- **A value that belongs to the host:** the script's path is the project's, so it is copied, never typed; the
  fallback is labeled as one.
- **Reading a rendered page in a test:** counting tags, checking their order, and flipping a setting at
  request time with pytest-django's `settings` fixture.
- **Saying what a vendor collects, in your own words,** from the vendor's own page, with the date you read it.

## Before the code: what is counted, what it costs, and why this and not PostHog

**What it is.** Vercel Web Analytics counts page views with a script in the page. Each page view is an
event (Vercel, 2026b), recorded with the page, the referrer, the country and the browser among other things
(Vercel, 2026c). For plain HTML sites the quickstart gives two script tags and says there is no package to
install and no route support; this site is server-rendered pages with no router, so the plain-HTML
instructions are the ones to follow (Vercel, 2026a).

**What it costs.** The pricing page, read October 28, 2026: a Hobby team gets 50,000 events a month, shared
across every project in the team, and cannot buy more; past the limit "a three day grace period will start
before Vercel will stop capturing events", and collection resumes after seven days or on an upgrade. The
reporting window on Hobby is one month. A Pro team pays $0.03 per 1,000 events with a twelve-month window
(Vercel, 2026b). A landing page with a waitlist is far inside the free allowance; the numbers are here so that
the owner knows what a traffic spike does.

**What it collects.** The privacy page says the script uses no third-party cookies and tells visitors apart by
a hash made from the incoming request, discarded after 24 hours, and that a page view is not tied to an
individual or an IP address. A data point may hold the timestamp, the URL, the referrer, filtered query
parameters, the country, region and city, the operating system, the browser, the device type and the script
version (Vercel, 2026c). Section 06a.4 writes that into the privacy page.

**Why now, and why not PostHog.** The WitUS ecosystem's analytics standard is PostHog, one shared project with
per-app differentiation, chosen because Sign in with WitUS makes cross-app journeys possible (WitUS, 2026).
That value arrives with sign-in, so PostHog is a later chapter of this tutorial, after chapter 07. The
landing page is live before any of that, and it has one question: does anyone arrive, and from where. Vercel
Web Analytics answers it with no package, no new process and no key, and this chapter does not replace the
standard; it fills the gap until the standard's chapter.

**The rule for the path.** The quickstart's snippet reads `<script defer src="/<unique-path>/script.js">`, and
its note says that enabling Analytics "will add new routes (scoped at `/_vercel/insights/*` and
`/<unique-path>/*`) after your next deployment" (Vercel, 2026a). The unique path is the project's. By the
authoritative-values rule in `CLAUDE.md`, a value owned by Vercel is copied from Vercel, so the path comes in
through a variable. The code needs a value when none is set, and it uses the shared `/_vercel/insights/`
route the quickstart names, with the file name from the snippet. That is a fallback, labeled as one in the
settings, in the template and in `.env.example`; the text never claims it is what your dashboard shows. The
dashboard step says how to tell whether it works.

## Steps

### 06a.1 The tests

Listing 06a-1, Filename: `tests/test_ch06a.py`:

```python
"""Chapter 06a checkpoint: Vercel Web Analytics, rendered only where it is switched on, with a
script path that belongs to the project, and a privacy page that says so."""

import importlib
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import Client
from pytest_django.fixtures import Settings

BASE_DIR = Path(settings.BASE_DIR)
# Not a secret: it exists only inside this test run (the same string chapter 06 uses).
TEST_KEY = "test-only-" + "0123456789" * 5
# The first tag's one line, byte for byte from Vercel's quickstart for plain HTML sites (read
# October 28, 2026). It queues calls until the deferred script loads.
SHIM = "window.va = window.va || function () { (window.vaq = window.vaq || []).push(arguments); };"
# The fallback the settings use with no path set: the shared route the quickstart names.
FALLBACK_PATH = "/_vercel/insights/script.js"
# The shape the dashboard's snippet shows once Analytics is enabled, with a made-up unique path.
PROJECT_PATH = "/abc123def456/script.js"
# Three pages that extend the base template: the landing page, a Markdown page, a form page.
PUBLIC_PATHS = ["/", "/privacy/", "/waitlist/"]


def fresh_settings(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> ModuleType:
    """Chapter 06's helper, copied so this file stands alone: import the settings module again
    with exactly the variables in `env` and none of the usual ones, the way a server sees it."""
    for name in list(os.environ):
        if name.startswith(("DJANGO_", "VERCEL", "DATABASE_URL")):
            monkeypatch.delenv(name)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delitem(sys.modules, "invest_witus_site.settings")
    return importlib.import_module("invest_witus_site.settings")


def production_env(tmp_path: Path) -> dict[str, str]:
    """A production-shaped environment with the analytics flag unset, as chapter 06 left it."""
    return {
        "VERCEL": "1",
        "VERCEL_URL": "invest-witus-abc123-example.vercel.app",
        "DJANGO_SECRET_KEY": TEST_KEY,
        "DJANGO_ALLOWED_HOSTS": "invest.witus.online",
        "DATABASE_URL": f"sqlite:///{tmp_path / 'app.sqlite3'}",
    }


# --- The switch -----------------------------------------------------------------------------


def test_analytics_is_off_on_a_laptop_and_in_this_suite() -> None:
    assert settings.VERCEL_ANALYTICS_ENABLED is False
    assert settings.VERCEL_ANALYTICS_SCRIPT_PATH == FALLBACK_PATH


def test_debug_on_never_turns_it_on(monkeypatch: pytest.MonkeyPatch) -> None:
    laptop = fresh_settings(monkeypatch, {"DJANGO_DEBUG": "1", "VERCEL_ANALYTICS": "1"})
    assert laptop.DEBUG is True
    assert laptop.VERCEL_ANALYTICS_ENABLED is False, "runserver with the flag set stays silent"


def test_the_flag_alone_is_not_enough_off_vercel(monkeypatch: pytest.MonkeyPatch) -> None:
    server = fresh_settings(monkeypatch, {"DJANGO_SECRET_KEY": TEST_KEY, "VERCEL_ANALYTICS": "1"})
    assert server.DEBUG is False and server.ON_VERCEL is False
    assert server.VERCEL_ANALYTICS_ENABLED is False


def test_vercel_without_the_flag_keeps_it_off(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = fresh_settings(monkeypatch, production_env(tmp_path))
    assert server.ON_VERCEL is True
    assert server.VERCEL_ANALYTICS_ENABLED is False, "a preview with the flag unset stays silent"


def test_vercel_with_the_flag_turns_it_on_with_the_fallback_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = fresh_settings(monkeypatch, production_env(tmp_path) | {"VERCEL_ANALYTICS": "1"})
    assert server.VERCEL_ANALYTICS_ENABLED is True
    assert server.VERCEL_ANALYTICS_SCRIPT_PATH == FALLBACK_PATH


def test_the_script_path_honors_the_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = production_env(tmp_path) | {
        "VERCEL_ANALYTICS": "1",
        "VERCEL_ANALYTICS_SCRIPT_PATH": PROJECT_PATH,
    }
    server = fresh_settings(monkeypatch, env)
    assert server.VERCEL_ANALYTICS_SCRIPT_PATH == PROJECT_PATH


def test_a_script_path_that_is_not_a_path_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = production_env(tmp_path) | {"VERCEL_ANALYTICS_SCRIPT_PATH": "https://x.test/script.js"}
    with pytest.raises(ImproperlyConfigured, match="VERCEL_ANALYTICS_SCRIPT_PATH"):
        fresh_settings(monkeypatch, env)


# --- The tags -------------------------------------------------------------------------------


@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_no_tags_render_while_analytics_is_off(client: Client, path: str) -> None:
    html = client.get(path).content.decode()
    assert "<script" not in html, "the public pages carry no script at all until it is on"
    assert "window.va" not in html and "script.js" not in html


@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_the_two_tags_render_when_analytics_is_on(
    client: Client, settings: Settings, path: str
) -> None:
    settings.VERCEL_ANALYTICS_ENABLED = True
    settings.VERCEL_ANALYTICS_SCRIPT_PATH = PROJECT_PATH
    html = client.get(path).content.decode()
    assert html.count("<script") == 2
    shim = html.index(SHIM)
    script = html.index(f'<script defer src="{PROJECT_PATH}"></script>')
    assert shim < script < html.index("</body>"), "the shim first, then the script, inside body"
    assert FALLBACK_PATH not in html, "the project's path, not the fallback"


def test_the_switch_alone_renders_the_fallback_path(client: Client, settings: Settings) -> None:
    settings.VERCEL_ANALYTICS_ENABLED = True
    html = client.get("/").content.decode()
    assert f'<script defer src="{FALLBACK_PATH}"></script>' in html


# --- The privacy page and the env example ---------------------------------------------------


def test_the_privacy_page_names_the_analytics(client: Client) -> None:
    html = client.get("/privacy/").content.decode()
    assert "Vercel Web Analytics" in html
    assert "October 28, 2026" in html, "the dated line, and the last-updated line moved with it"
    assert "no third-party cookies" in html


def test_env_example_names_both_variables_and_labels_the_fallback() -> None:
    text = (BASE_DIR / ".env.example").read_text(encoding="utf-8")
    assert "\nVERCEL_ANALYTICS=\n" in text
    assert "\nVERCEL_ANALYTICS_SCRIPT_PATH=\n" in text
    assert "FALLBACK" in text and FALLBACK_PATH in text
```

Things to notice:

- **`fresh_settings` and `production_env`** are chapter 06's helpers, copied in so the file stands alone like
  every other checkpoint file. The first imports the settings module again with exactly the variables a test
  names; the second is a production-shaped environment with the analytics flag unset.
- **Seven tests for one switch.** A laptop, a laptop with debug on and the flag set, a server off Vercel with
  the flag set, Vercel without the flag, Vercel with the flag, the path override, and a path that is not a
  path. Each is a row in the table you would otherwise keep in your head.
- **The `settings` fixture** from pytest-django lets a test set a Django setting for its own duration and
  "automatically revert any changes made to the settings" afterwards (pytest-django, n.d.). The two rendering
  tests use it to flip the switch at request time without a server, which is also why the switch is read by a
  context processor on every request rather than once at import.
- **`html.count("<script") == 2`** says the public pages carry exactly the two tags when it is on, and the
  matching test with the switch off says they carry none at all. **`html.index`** three times gives the
  order: the queue first, then the deferred script, both before `</body>`.
- **`SHIM`** is the first tag's one line, byte for byte from the quickstart. If Vercel changes it, this
  constant and the template change together.

Run it:

Listing 06a-2, Terminal:

```sh
uv run pytest tests/test_ch06a.py
```

```text
E       AttributeError: 'Settings' object has no attribute 'VERCEL_ANALYTICS_ENABLED'
...
13 failed, 3 passed in 0.62s
```

Red first: the setting does not exist, so every test that reads it fails with an `AttributeError`, and the pages
that should carry two tags fail on the count. The three that pass say the pages carry no script, which was true
before this chapter as well.

### 06a.2 The switch, in the settings

The new block is at the end of the file; everything above it is chapter 06's.

Listing 06a-3, Filename: `src/invest_witus_site/settings.py`:

```python
"""Django settings for Invest.WitUS.

Anything that differs between your laptop and a server comes from an environment variable, with a
safe default for the laptop. The names are listed in `.env.example`; values never go in git.
Chapter 06 added the server's side: the database from `DATABASE_URL`, a secret key the server
must set, the HTTPS cookie and proxy settings, the folder `collectstatic` fills, and logging a
server can show.
"""

import contextlib
import os
from pathlib import Path

import django_stubs_ext
from django.core.exceptions import ImproperlyConfigured

from invest_witus_site.database import database_from_url

# django-stubs describes Django's classes as generics (`ModelAdmin[WaitlistEntry]`) so pyright can
# check them, but Django itself does not accept `[...]` on those classes at runtime. This one call
# teaches them to, so the admin code can be written the way the type checker reads it.
django_stubs_ext.monkeypatch()

# The repository root. This file is src/invest_witus_site/settings.py, three levels down.
BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env_list(name: str) -> list[str]:
    """A comma-separated variable as a list, blanks dropped: "a, b," becomes ["a", "b"]."""
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


# Off unless DJANGO_DEBUG=1. Debug pages show settings and source code; never on a server.
DEBUG = os.environ.get("DJANGO_DEBUG") == "1"

# Vercel sets VERCEL=1 on its build machine and inside the function (its system environment
# variables). It is read for one question only: does a proxy that ends HTTPS sit in front?
ON_VERCEL = os.environ.get("VERCEL") == "1"
if DEBUG and ON_VERCEL:
    raise ImproperlyConfigured(
        "DJANGO_DEBUG=1 on Vercel: debug pages would show settings and code to anyone. Unset it."
    )


def secret_key(debug: bool) -> str:
    """DJANGO_SECRET_KEY, which a server must set. With debug off and no key, Django refuses to
    start here, with a message that says what to do, rather than sign sessions with a key anyone
    can read in git."""
    key = os.environ.get("DJANGO_SECRET_KEY", "")
    if key:
        return key
    if not debug:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY is not set and DJANGO_DEBUG is not 1. A server needs a secret key. "
            "Make one with: uv run python -c "
            '"from django.core.management.utils import get_random_secret_key as k; print(k())"'
        )
    # DEV-ONLY FALLBACK, reachable only with DJANGO_DEBUG=1 on a laptop. `check --deploy` warns
    # about the `django-insecure-` prefix, which is the point.
    return "django-insecure-dev-only-set-DJANGO_SECRET_KEY"


SECRET_KEY = secret_key(DEBUG)

# Host names the site answers to. The default answers a laptop and nothing else; production sets
# DJANGO_ALLOWED_HOSTS=invest.witus.online. The host names Vercel gives a deployment (its
# *.vercel.app URLs, and the production domain once one is added) come from Vercel's own
# variables, so a preview deployment answers without anyone listing its URL by hand.
VERCEL_HOSTS = [
    host
    for name in ("VERCEL_URL", "VERCEL_BRANCH_URL", "VERCEL_PROJECT_PRODUCTION_URL")
    if (host := os.environ.get(name))
]
# (dict.fromkeys keeps the order and drops a name listed twice.)
ALLOWED_HOSTS = list(
    dict.fromkeys((env_list("DJANGO_ALLOWED_HOSTS") or ["localhost", "127.0.0.1"]) + VERCEL_HOSTS)
)

# Origins (scheme and host) a form may be posted from. Django compares a POST's Origin header with
# the request's own origin; listing the site's HTTPS origin keeps that check passing even if the
# proxy header below were ever missing. Production sets https://invest.witus.online.
CSRF_TRUSTED_ORIGINS = list(
    dict.fromkeys(
        env_list("DJANGO_CSRF_TRUSTED_ORIGINS") + [f"https://{host}" for host in VERCEL_HOSTS]
    )
)

# Chapter 04 installed only staticfiles and the pages app. The admin (chapter 05) needs the four
# contrib apps it is built on: auth (users and permissions), contenttypes (the table of tables that
# permissions point at), sessions (how a login is remembered) and messages (the "2 entries approved"
# notes after an action). They arrive together because the admin does not start without them.
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "invest_witus_site.pages",
    "invest_witus_site.holdings",
]

# Order matters: a middleware sees the request top to bottom and the response bottom to top.
# Sessions must load before authentication can read the session, and messages after that.
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "invest_witus_site.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Templates live in each app's templates/ folder; nothing outside an app.
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "invest_witus_site.pages.context_processors.site",
            ],
        },
    },
]

# The WSGI application `runserver` loads. It names the bridge file at the repository root, not
# `invest_witus_site.wsgi`, because Vercel turns this value into a file path beside `manage.py`,
# and the bridge is what puts `src/` on the import path there (chapter 06).
WSGI_APPLICATION = "wsgi.application"

# The database. With no DATABASE_URL: SQLite in the folder git ignores, as in chapter 04. On
# Vercel the Neon integration sets DATABASE_URL (the pooled connection, for the app) and
# DATABASE_URL_UNPOOLED (the direct one, for migrations). `database_from_url` reads either shape.
DATA_DIR = BASE_DIR / "data" / "private"
DATABASE_URL = os.environ.get("DATABASE_URL") or "sqlite:///data/private/invest-witus.sqlite3"
if not os.environ.get("DATABASE_URL"):
    # A server's filesystem may be read-only; then /healthz/ reports the database as missing.
    with contextlib.suppress(OSError):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASES = {"default": database_from_url(DATABASE_URL, BASE_DIR)}
if unpooled := os.environ.get("DATABASE_URL_UNPOOLED"):
    # Neon: schema changes take the direct connection, not the pooler. The owner runs
    # `manage.py migrate --database direct` and `createsuperuser --database direct` against it.
    DATABASES["direct"] = database_from_url(unpooled, BASE_DIR)

# The only password in this app is the owner's admin login (chapter 05). Sign in with WitUS
# (chapter 07) adds no passwords. `createsuperuser` refuses a password these validators reject.
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
# Where `collectstatic` copies every app's static files into one folder (gitignored). Vercel sees
# STATIC_ROOT, runs collectstatic itself during the build, and serves that folder from its CDN at
# STATIC_URL; the function never serves a static file.
STATIC_ROOT = BASE_DIR / "staticfiles"

# HTTPS. Vercel ends TLS at its CDN and calls the function over plain HTTP with the header
# X-Forwarded-Proto: https. Django is told to trust that header only on Vercel, where the proxy
# sets it on every request (Django's warning: never where a client could send it to Django
# directly). Vercel also answers every plain-HTTP request with a 308 to HTTPS before Django sees
# it, and sends Strict-Transport-Security on custom domains, so the redirect below is a second
# line and the HSTS check (security.W004) is silenced on purpose.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if ON_VERCEL else None
SECURE_SSL_REDIRECT = ON_VERCEL
SILENCED_SYSTEM_CHECKS = ["security.W004"]
# Cookies marked Secure travel only over HTTPS. On whenever debug is off, so a server never sends
# the admin's session over plain HTTP. It is also why `runserver` with debug off cannot sign you
# in at http://127.0.0.1:8000/admin/: the browser keeps a Secure cookie off a plain connection.
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# Django's default logging prints to the console only while debug is on, so a server would show
# nothing. This sends warnings and errors (a 500's traceback, a refused host) to stderr, which
# Vercel collects as the function's logs. Nothing here logs a request body or a setting.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"stderr": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["stderr"], "level": "WARNING"},
}

# The FAQ, privacy and terms pages are Markdown files in the repo, so a wording change is a normal
# commit with a diff anyone can read.
SITE_PAGES_DIR = BASE_DIR / "docs" / "site"

# Vercel Web Analytics (chapter 06a): two script tags in the base template, rendered only when
# both hold: the app runs on Vercel, and the owner set VERCEL_ANALYTICS=1 on that environment. So
# production and preview can differ, and `runserver` never emits the tags (debug on Vercel is
# refused above, so a debug server never does either). The script's path belongs to the project:
# once Analytics is enabled, the project's Analytics page shows it, and that value goes in
# VERCEL_ANALYTICS_SCRIPT_PATH. FALLBACK, not a value read from any dashboard: the shared
# `/_vercel/insights/` route the quickstart names, with the file name from its snippet.
VERCEL_ANALYTICS_ENABLED = ON_VERCEL and os.environ.get("VERCEL_ANALYTICS") == "1"
VERCEL_ANALYTICS_SCRIPT_PATH = (
    os.environ.get("VERCEL_ANALYTICS_SCRIPT_PATH") or "/_vercel/insights/script.js"
)
if not VERCEL_ANALYTICS_SCRIPT_PATH.startswith("/"):
    raise ImproperlyConfigured(
        "VERCEL_ANALYTICS_SCRIPT_PATH must be a path on this site, starting with /, such as "
        "/<unique-path>/script.js from the Analytics page of the Vercel project."
    )
```

Three lines of code and one refusal:

- **`VERCEL_ANALYTICS_ENABLED`** is true only when `ON_VERCEL` (chapter 06's reading of Vercel's own
  `VERCEL=1`) and `VERCEL_ANALYTICS=1` both hold. The second is a variable the owner sets per environment, so
  Production can count while Preview stays silent. `runserver` on a laptop has neither, so it never emits the
  tags; and debug on Vercel is refused higher in the file, so a debug server never does either.
- **`VERCEL_ANALYTICS_SCRIPT_PATH`** is the variable's value, or the fallback. The comment says what the
  fallback is and is not.
- **The refusal.** A value that does not start with `/` is not a path on this site; the settings refuse to
  start and the message says what to set, in the chapter 06 style: a typo in a dashboard fails when the
  function starts, where the log shows it.

### 06a.3 The context processor and the template

Listing 06a-4, Filename: `src/invest_witus_site/pages/context_processors.py`:

```python
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
```

A context processor is a callable that takes "a request object as their argument and return[s] a dictionary
of items to be merged into the context", listed under `context_processors` in `TEMPLATES` (Django Software
Foundation, n.d.). Chapter 04 wrote this one for the footer's product list and the year; two keys join them.
Reading `settings` inside the function, on every request, is what lets a test flip the switch after the
module has loaded.

Listing 06a-5, Filename: `src/invest_witus_site/pages/templates/pages/base.html`:

```html
{% load static %}<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Invest.WitUS{% endblock %}</title>
  <meta name="description" content="Pick a taught investing method and stay with it, on paper first. A learning tool, not advice.">
  {# Favicons: gemini/witus/public/brand/04-orbit-type/, copied into static/brand/witus/. #}
  <link rel="icon" href="{% static 'brand/witus/favicon.svg' %}" type="image/svg+xml">
  <link rel="icon" href="{% static 'brand/witus/favicon-32.png' %}" sizes="32x32" type="image/png">
  <link rel="icon" href="{% static 'brand/witus/favicon-16.png' %}" sizes="16x16" type="image/png">
  <link rel="apple-touch-icon" href="{% static 'brand/witus/favicon-180.png' %}">
  <link rel="stylesheet" href="{% static 'pages/site.css' %}">
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
  {% include "pages/_header.html" %}
  <main id="main" tabindex="-1">
    {% block content %}{% endblock %}
  </main>
  {% include "pages/_footer.html" %}
  {% if vercel_analytics_enabled %}
  {# Vercel Web Analytics (chapter 06a): the snippet from Vercel's quickstart for plain HTML sites, read #}
  {# October 28, 2026. The first tag queues calls until the deferred script loads. The path is the setting #}
  {# VERCEL_ANALYTICS_SCRIPT_PATH; with it unset, the FALLBACK is the shared /_vercel/insights/ route the #}
  {# quickstart names, not a value read from the dashboard. Rendered only with VERCEL=1 and VERCEL_ANALYTICS=1. #}
  <script>
    window.va = window.va || function () { (window.vaq = window.vaq || []).push(arguments); };
  </script>
  <script defer src="{{ vercel_analytics_script_path }}"></script>
  {% endif %}
</body>
</html>
```

What the tags do, and where they sit:

- **The first tag** defines `window.va` as a function that pushes its arguments onto `window.vaq`, a queue,
  unless a `va` already exists. Nothing on this site calls it; the snippet defines it so that a call made
  before the script arrives (a custom event, on the plans that have them) is queued rather than lost. That
  is why it comes first.
- **The second tag** loads the script with `defer`: the browser fetches it while parsing goes on and runs it
  "after the document has been parsed, but before firing `DOMContentLoaded`" (MDN contributors, 2026). The
  page's own content never waits for it.
- **At the end of `<body>`,** after the footer, inside `{% if vercel_analytics_enabled %}`. With the switch
  off, the page has no `<script>` at all, which the tests check.
- **`{{ vercel_analytics_script_path }}`** is escaped by Django's template engine like any other variable, so
  the value can only ever land inside the quotes of `src`.
- **The comment** repeats, next to the tags, what the fallback is. Someone reading the page source in six
  months should not have to open the settings to learn that.

### 06a.4 The names, and the privacy page

Listing 06a-6, Filename: `.env.example`:

```sh
# Copy to .env (git ignores it) and run with: uv run --env-file .env python manage.py runserver
# Names only; values never go in git. On Vercel the same names are set in the project's
# Environment Variables page (chapter 06); the laptop and the server share one settings file.

# "1" shows Django's debug pages and serves static files from runserver. Never "1" on a server:
# settings.py refuses to start on Vercel with it set.
DJANGO_DEBUG=1

# Required whenever DJANGO_DEBUG is not 1, which is every server. Make one with:
#   uv run python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
# Leave empty on your laptop: with DJANGO_DEBUG=1 a labeled dev-only key is used instead.
DJANGO_SECRET_KEY=

# Comma-separated host names the site answers to. Default: localhost,127.0.0.1
# Production: invest.witus.online (Vercel's own *.vercel.app host names are added on their own).
DJANGO_ALLOWED_HOSTS=

# Comma-separated origins, scheme and host, that may post the site's forms.
# Production: https://invest.witus.online
DJANGO_CSRF_TRUSTED_ORIGINS=

# The database. Empty: SQLite at data/private/invest-witus.sqlite3. On Vercel the Neon integration
# sets both names: DATABASE_URL is the pooled connection the app uses, DATABASE_URL_UNPOOLED the
# direct one that migrations use (`manage.py migrate --database direct`).
# Shape: postgresql://user:password@host/name?sslmode=require
DATABASE_URL=
DATABASE_URL_UNPOOLED=

# The owner's one-time, non-interactive superuser on a new database (chapter 06). These three are
# set in the shell for that one command, never written to a file:
#   DJANGO_SUPERUSER_USERNAME  DJANGO_SUPERUSER_EMAIL  DJANGO_SUPERUSER_PASSWORD
#   ... vercel env run -e production -- uv run python manage.py createsuperuser --noinput --database direct

# Vercel Web Analytics (chapter 06a). Both are set on Vercel, per environment, never on a laptop: the
# two script tags render only with VERCEL=1 (Vercel's own variable) and VERCEL_ANALYTICS=1, so
# Production can be on while Preview stays off. VERCEL_ANALYTICS_SCRIPT_PATH is the script path the
# project's Analytics page shows once Analytics is enabled (the quickstart writes it as
# /<unique-path>/script.js): copy it from there. Left empty, the FALLBACK /_vercel/insights/script.js
# is used, the shared route the quickstart names, not a value read from your dashboard. If the
# dashboard shows no page views after a deploy, set the path to what the page shows.
VERCEL_ANALYTICS=
VERCEL_ANALYTICS_SCRIPT_PATH=
```

Both names are listed with empty values, like the rest of the file: a laptop leaves them empty, and the
server's values are typed into Vercel's dashboard, never into a file.

Listing 06a-7, Filename: `docs/site/privacy.md`:

```markdown
# Privacy

Last updated: October 28, 2026. Plain language on purpose. A securities lawyer reviews this page and the Terms before anyone other than the operator is admitted to the app; until then it describes what the app does today and what it is built to do.

Not advice. Invest.WitUS is a learning tool. It is not a broker, not an investment adviser, and it never recommends a security.

## Who runs the app

One operator in Indiana, who builds the WitUS family of learning tools. No employees, no contractors, no one else with access to the data.

## What we store, and why

Today the app holds two kinds of data:

- **The waitlist.** Your name and email address, and the time you joined. We keep it to tell you when the app opens to learners. Nothing else is collected with it.
- **The operator's own records.** Plans, holdings entered by hand from statements, a trading journal, and paper (simulated) trades, all belonging to the operator.

When the app opens to other learners, education only and alongside the course, it will store for each person: the WitUS user id and email address from Sign in with WitUS; the plans they write; the holdings they enter; their journal; and their paper trades. Nothing is collected that the app does not use.

## Where it lives

The hosted app keeps its database at Neon, a Postgres hosting service, and runs on Vercel. A copy of the app you run yourself from the tutorial keeps a SQLite file on your own machine, in a folder git ignores.

## Who can see it

The operator only. Your holdings, plans and journal are never shown to another user, never sold, and never shared with a vendor beyond what that vendor needs to do its job (below).

## Broker keys

Paper trading keys are the default. Any broker key you give the app stays on the server, is never sent to a browser, and is never written to a log. A live-trading key is separate, optional, and only accepted behind an explicit checklist.

## Vendors

Vendors the app uses or is built to use, each named so you can read its own terms: Alpaca (paper trading and, if you choose it, live trading), Tiingo (end-of-day prices), Neon (the database), Vercel (hosting and page-view analytics), Mailgun (email), and WitUS Inbox (where the waitlist and in-app reports are mirrored for the operator). Each vendor sees only what it needs: Alpaca sees the orders you place through it, Tiingo sees the symbols whose prices are asked for, Mailgun sees the address an email goes to.

## Market data

No market data, prices or performance figures are shown on any public page, and no one's data is shown to anyone else. Prices inside the app are for the signed-in owner of the account they value.

## Cookies

The public pages set one cookie, for the form protection Django uses (CSRF). Signing in, when it arrives, adds a session cookie. There are no advertising or analytics cookies.

## Analytics

Added October 28, 2026: the hosted site uses Vercel Web Analytics, which counts page views. Vercel's privacy page (read October 28, 2026) says the script sets no third-party cookies, tells visitors apart by a hash made from the request that is discarded after 24 hours, and ties no page view to an individual or an IP address. Each page view records the page, the referrer, the country, region and city, the browser, the operating system, and the device type. A copy you run on your own machine from the tutorial sends nothing.

## Deleting your data

Email the Contact address in the footer from the address you signed up with. A waitlist entry is deleted on request; an account, when accounts exist, is deleted with everything attached to it. Plans and the journal export to CSV first if you ask.

## Children

The app is for adults. It is not directed at anyone under 13 and does not knowingly collect their data (see COPPA in the FAQ).

## Changes

Edits to this page are commits in the repository, with dates. The "last updated" line above moves when the text does.

## Contact

Use the Contact link in the footer of every page.
```

The new section is the privacy page's summary of 06a's "What it collects", dated twice: once for the change,
once for the day the vendor's page was read. The "Last updated" line at the top moved with it, as the page's
own last section promises, and Vercel's entry in the vendors list now says what it does. The wording stays
inside what Vercel's page says: "no third-party cookies" rather than "no cookies", because that is the claim
the page makes.

### 06a.5 Green on the laptop

Listing 06a-8, Terminal:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

```text
156 passed in 3.49s
All checks passed!
80 files already formatted
0 errors, 0 warnings, 0 informations
```

Sixteen new tests. Then see the tags without a server. `VERCEL=1` turns on chapter 06's SSL redirect, so a
plain `curl` to `runserver` would get a 301; the test client can ask over HTTPS instead, from `manage.py
shell`, with the switch on:

Listing 06a-9, Terminal:

```sh
VERCEL=1 VERCEL_ANALYTICS=1 DJANGO_SECRET_KEY=not-a-secret-just-for-this-check \
DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:////tmp/invest-witus-06a.sqlite3 \
uv run python manage.py shell -c "from django.test import Client; r = Client().get('/', secure=True); print(r.status_code); print(r.content.decode()[-230:])"
```

```text
200
</div>
</footer>

  <script>
    window.va = window.va || function () { (window.vaq = window.vaq || []).push(arguments); };
  </script>
  <script defer src="/_vercel/insights/script.js"></script>

</body>
</html>
```

(The shell prints a line about objects imported, and the template's comments leave a few blank lines; both
are trimmed here.) Drop `VERCEL_ANALYTICS=1` from the same command and the tail is `</footer>`, `</body>`,
`</html>` with no script between them. Delete the temporary database afterwards. The path printed is the
fallback, because no `VERCEL_ANALYTICS_SCRIPT_PATH` was set; the dashboard decides the real one.

### 06a.6 The dashboard

Labels are from Vercel's quickstart as read on October 28, 2026 (Vercel, 2026a). Your project is your own;
the reference repository's is the owner's.

1. **Enable Web Analytics.** On the Vercel dashboard, open **Analytics** in the sidebar and select the
   project, then click the **Enable** button in the header. The quickstart's note: "Enabling Web Analytics
   will add new routes (scoped at `/_vercel/insights/*` and `/<unique-path>/*`) after your next deployment."
2. **Look for the path.** The quickstart writes the script's path as `/<unique-path>/script.js` and does not
   say where the dashboard shows the project's own value, so look on the project's Analytics page after
   enabling, and in the quickstart's HTML instructions opened from your project. If you find a path, it is
   the value of `VERCEL_ANALYTICS_SCRIPT_PATH` in the next step. If you find none, leave that variable unset;
   the fallback applies, and step 5 tells you whether it works.
3. **Set the variables.** The project → **Settings** → **Environment Variables**: `VERCEL_ANALYTICS` with the
   value `1` for **Production** (add **Preview** only if preview page views should count; they draw on the
   same allowance), and `VERCEL_ANALYTICS_SCRIPT_PATH` with the path from step 2, if there was one.
   Neither is a secret.
4. **Redeploy** the latest production deployment (**Deployments** → the menu on the deployment →
   **Redeploy**): the function reads its variables when it starts, and the routes from step 1 arrive with
   the next deployment.
5. **Verify in the browser.** Open the production URL with the developer tools' **Network** tab open. The
   quickstart: "you should be able to see a Fetch/XHR request in your browser's Network tab from
   `/<unique-path>/view` when you visit any page." View the page source as well: the two tags sit before
   `</body>`. If the request for `script.js` is a 404, the path is wrong; take the one the dashboard shows
   and repeat steps 3 and 4.
6. **View the data.** The dashboard → the project → **Analytics** in the sidebar. "After a few days of
   visitors, you'll be able to start exploring your data" (Vercel, 2026a).

## Checkpoint

- `uv run pytest` prints `156 passed`; ruff and pyright pass.
- `uv run --env-file .env python manage.py runserver` serves the public pages with no `<script>` in them.
- Listing 06a-9 prints the two tags; without `VERCEL_ANALYTICS=1` it prints none.
- `/privacy/` carries the Analytics section with both dates.
- On Vercel, after 06a.6: a request to `/…/view` in the Network tab, and no 404 for `script.js`.
- Commit and push: `git add -A && git commit -m "Chapter 06a: Vercel Web Analytics"`.

## Exercises

1. The admin's pages do not extend `base.html`, so the owner's back office is never counted. Write a test
   that proves it: sign in with `admin_client`, set the switch on, and assert that `/admin/` carries no
   `window.va`.
2. The settings refuse a path that does not start with `/`. Decide whether a path that does not end in
   `script.js` should be refused too, and write the test for the decision either way.
3. The pricing page lists custom events for Pro and Enterprise only. Read the custom-events page the quickstart
   links to and write,
   in one paragraph in your own notes, which single event this site would send if it could, and why the
   waitlist's thank-you page is a better signal than a button click.

## If you get stuck

- Browse: https://github.com/dapperAuteur/invest-witus/tree/v06a
- Diff for this chapter: https://github.com/dapperAuteur/invest-witus/compare/v06...v06a
- Zip: https://github.com/dapperAuteur/invest-witus/archive/v06a.zip
- Take the reference's files. Chapter 06a changed `src/invest_witus_site/settings.py`,
  `src/invest_witus_site/pages/context_processors.py`, `src/invest_witus_site/pages/templates/pages/base.html`,
  `.env.example` and `docs/site/privacy.md`, and added `tests/test_ch06a.py`. Nothing moved:
  `git fetch reference --tags && git checkout v06a -- src/invest_witus_site/settings.py src/invest_witus_site/pages/context_processors.py src/invest_witus_site/pages/templates/pages/base.html .env.example docs/site/privacy.md tests/test_ch06a.py`.
- `AttributeError: 'Settings' object has no attribute 'VERCEL_ANALYTICS_ENABLED'`: the block from 06a.2 is
  missing, or sits above `ON_VERCEL` in the file and raised a `NameError` that the test run shows earlier.
- `test_the_two_tags_render_when_analytics_is_on` fails on the count: the tags are outside the
  `{% if %}`, or the context processor does not pass `vercel_analytics_enabled` (check the key's spelling in
  both files).
- `test_no_tags_render_while_analytics_is_off` fails: a `<script>` from somewhere else on the page; this
  site has none, so look for a pasted snippet in another template.
- `ImproperlyConfigured: VERCEL_ANALYTICS_SCRIPT_PATH must be a path` on Vercel: the variable holds a full
  URL or a value with quotes around it; it wants a path such as `/<unique-path>/script.js`.
- On Vercel the tags are missing from the page source: `VERCEL_ANALYTICS` is not `1` on that environment, or
  the deployment was built before the variable existed; redeploy. If system environment variables are off
  (chapter 06, 06.8 step 5), `VERCEL=1` never arrives and the switch stays off.
- The script request is a 404 and the Network tab shows no `/…/view`: the fallback path is not what your
  project serves; find the path on the Analytics page and set the variable.

## What we learned

- A switch with two conditions, one from the host and one from the owner, covers laptop, preview and
  production with no code change between them, and seven short tests cover the table.
- A context processor hands a value to every template; reading settings inside it keeps the value live for
  tests.
- The plain-HTML snippet is a queue and a deferred script; the queue comes first, the script never blocks the
  page, and with the switch off the page has no script at all.
- A value the host owns comes in through a variable; a fallback may exist, labeled as a fallback, with a
  behavior check (the `view` request) rather than a guess deciding whether it is right.
- A privacy page repeats the vendor's claims and no more, with the date they were read.
- The ecosystem's PostHog standard is not replaced; it waits for sign-in, when it has something to join.

## Next

Chapter 07 replaces the stub at `/auth/witus/login/` with Sign in with WitUS: OIDC against the ecosystem's
identity provider, EdDSA id tokens, a callback that matches a user by the WitUS user id and never by email, and
a sign-out. Nothing in this chapter changes for it.

## References

Django Software Foundation. (n.d.). *The Django template language: For Python programmers*. Django 5.2
documentation. https://docs.djangoproject.com/en/5.2/ref/templates/api/ (retrieved October 28, 2026)

MDN contributors. (2026, May 9). *<script>: The script element*. MDN Web Docs.
https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/script (retrieved October 28, 2026)

pytest-django. (n.d.). *Django helpers*. pytest-django documentation.
https://pytest-django.readthedocs.io/en/latest/helpers.html (retrieved October 28, 2026)

Vercel. (2026a, June 8). *Getting started with Vercel Web Analytics*. Vercel documentation.
https://vercel.com/docs/analytics/quickstart (retrieved October 28, 2026)

Vercel. (2026b, August 25). *Pricing for Web Analytics*. Vercel documentation.
https://vercel.com/docs/analytics/limits-and-pricing (retrieved October 28, 2026)

Vercel. (2026c, June 26). *Privacy and compliance*. Vercel documentation.
https://vercel.com/docs/analytics/privacy-policy (retrieved October 28, 2026)

WitUS. (2026). *PostHog across the ecosystem: One shared project, per-app differentiation* [Internal plan 26,
decisions locked July 28, 2026]. `gemini/witus/plans/26-posthog-ecosystem-rollout.md` (read October 28, 2026)
