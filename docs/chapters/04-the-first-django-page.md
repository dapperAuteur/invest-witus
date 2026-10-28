# Chapter 04: The first Django page: the public landing page

**Starts from:** tag `v03`. **Ends at:** tag `v04`.
**Written against:** Python 3.14.10, uv 0.13.6, Django 5.2.18, Markdown 3.11.2, pytest-django 4.14.0,
django-stubs 6.1.2 (October 27, 2026).
**Goal:** `uv run python manage.py runserver` serves the public site: the landing page with its waitlist, the
FAQ, the privacy and terms pages, a contact page, and a header whose "Sign in" link a test protects.
**Time:** 3 to 4 hours. The longest chapter so far, because a website is many small files.

The listings in this chapter are not typed in by hand. `scripts/render_chapter.py` pastes the real files from
tag `v04` into the chapter text, so what you read and what the tests run are the same bytes.

## What you will learn

- **Django's shape:** a *project* (settings and the root URL list) and *apps* (the code for one area of the
  site). If you know Next.js: the project is the app's config, the apps are its route groups.
- **Settings from the environment** with safe defaults, so one file serves your laptop and a server.
- **URLs, views and templates:** a URL pattern names a view function; the view returns a response, usually a
  rendered template. Templates extend a base and include partials, like layouts and components.
- **A model and its migration:** the first database table, the waitlist, and the file Django writes to create
  it.
- **Forms, CSRF and a honeypot:** validation on the server, the token that stops cross-site posts, and a hidden
  field that catches bots.
- **Static files and the test client:** how CSS and images are served, and how a test asks for a page without
  a browser.
- **Accessible names:** why a link's name is its text, and the one link in this app that is never renamed.

## Before the code: what the public site promises

The public site is the part of the app anyone can see, and the invariants from chapter 00 bind it hardest:
information, not advice. No public page recommends a security or shows a price, a chart, a return or a
testimonial, and none reads as "automated trading". The site says what the app is in the one sentence the PRD
fixes: *"Pick a method you learned. Practice it on paper. The app keeps you to its rules and shows you the
lesson behind each one."*

It also has a job the app itself does not have: pointing people who were cheated to the desks that take
reports. The FAQ (`docs/site/faq.md`, already written) opens with "Report a bad actor", and the landing page
and the footer both link to it.

Two rules from the WitUS ecosystem apply to every app, this one included (WitUS, 2026c):

- **The header carries a link whose accessible name is exactly "Sign in"** whenever a visitor is signed out.
  It is never renamed and never replaced by "Apps" or "Account"; a second link is added instead. A test
  tagged `smoke` fails if it changes. The rule exists because witus.online shipped for five months with the
  link renamed, and the ecosystem's owner reported "no login button" twice.
- **The footer is the ecosystem footer:** the same structure in every app, each in its own colors; the Rise
  Wellness callout and its disclaimer word for word; the sibling products from the ecosystem's registry; the
  copyright line verbatim (WitUS, 2026b).

The tests you copy first check all of this. They also check the promise above the way a machine can: no
public page contains a `<table>` element or a signed percentage like `+8.5%`. That is a narrow check on
purpose. It cannot judge wording, but it catches the two shapes a performance claim usually takes, and it lets
the FAQ's "$25,000" (a regulatory threshold, not a price) through.

## Steps

### 04.1 Add Django and the tools

Listing 04-1, Terminal:

```sh
uv add "django>=5.2,<6" "markdown>=3.11"
uv add --dev "pytest-django>=4.14" "django-stubs>=6.1" types-markdown
```

Four new names:

| Package | What it is | Node analogy |
|---|---|---|
| `django` | The web framework: routing, templates, forms, the ORM, the admin | Next.js plus Drizzle plus a form library |
| `markdown` | Python-Markdown, which renders the FAQ and the legal pages from `.md` files | `remark` |
| `pytest-django` | pytest fixtures: a test client and a test database rolled back after each test | `supertest` with a test database |
| `django-stubs`, `types-markdown` | Type information for pyright, which neither package ships itself | `@types/*` |

**Why Django 5.2 and not 6.1.** On the day this was written, 6.1.2 was Django's newest release and 5.2.18 the
newest long-term-support (LTS) release. Both run on Python 3.14; 5.2 added it in 5.2.8 (Django Software
Foundation, n.d.-c). The LTS gets fixes until April 2028, 6.1 until December 2027 (Django Software Foundation,
n.d.-e). A tutorial people follow for a year or two wants the longer runway, so `"django>=5.2,<6"` pins the
series. The `<6` matters: without it, the next `uv lock --upgrade` would be free to pick 6.x.

Then three changes to `pyproject.toml`. The new tables tell uv to install both packages under `src/`, tell
pytest-django where the settings are, and tell pyright about two new folders:

Listing 04-2, Filename: `pyproject.toml`:

```toml
[project]
name = "invest-witus"
version = "0.1.0"
description = "Learn to invest by following one taught method, on paper first."
readme = "README.md"
requires-python = ">=3.14"
dependencies = [
    "django>=5.2,<6",
    "markdown>=3.11",
]

[project.scripts]
invest-witus = "invest_witus.cli:main"

[build-system]
requires = ["uv_build>=0.13.6,<0.14.0"]
build-backend = "uv_build"

[tool.uv.build-backend]
# Two top-level packages in src/: the library from chapters 01 to 03 and the Django project.
module-name = ["invest_witus", "invest_witus_site"]

[dependency-groups]
dev = [
    "django-stubs>=6.1",
    "pyright>=1.1.414",
    "pytest>=9.2.0",
    "pytest-django>=4.14",
    "ruff>=0.17.3",
    "types-markdown>=3.10.2.20261007",
]

[tool.pytest]
testpaths = ["tests"]
DJANGO_SETTINGS_MODULE = "invest_witus_site.settings"
markers = ["smoke: the checks that must pass on every deploy, such as the header Sign in link"]

[tool.ruff]
line-length = 100

[tool.ruff.lint]
# E/F: errors, I: import order, UP: modern Python syntax, B: likely bugs
select = ["E", "F", "I", "UP", "B"]

[tool.pyright]
include = ["src", "tests", "scripts", "manage.py"]
typeCheckingMode = "strict"
```

`module-name` is new. Chapter 00's `uv init --package` made one importable package, `invest_witus`. This
chapter adds a second one beside it, `invest_witus_site`, and uv's build backend installs only the names it is
given (Astral, n.d.-a). Run `uv sync` after the edit so the environment picks up the second package.

The `smoke` marker is declared so pytest does not warn about an unknown mark. `uv run pytest -m smoke` runs
only the tests that carry it.

### 04.2 Copy the checkpoint test

Listing 04-3, Filename: `tests/test_ch04.py`:

```python
"""Chapter 04 checkpoint: the public site, its header, footer, legal pages and waitlist."""

import re
from html.parser import HTMLParser

import pytest
from django.conf import settings
from django.test import Client

from invest_witus_site.pages.markdown_pages import render_markdown, trim_url
from invest_witus_site.pages.models import WaitlistEntry

PUBLIC_PATHS = [
    "/",
    "/faq/",
    "/privacy/",
    "/terms/",
    "/contact/",
    "/waitlist/",
    "/waitlist/thanks/",
    "/auth/witus/login/",
]
POSITIONING = (
    "Pick a method you learned. Practice it on paper. "
    "The app keeps you to its rules and shows you the lesson behind each one."
)
SIGN_IN = ("/auth/witus/login/", "Sign in")
MARKETING_RULE = (
    "https://www.ecfr.gov/api/versioner/v1/full/2026-10-23/title-17.xml"
    "?part=275&section=275.206(4)-1"
)


class LinkCollector(HTMLParser):
    """Collects (href, text) for every <a>, naming a link the way a screen reader does: by text."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href") or ""
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join("".join(self._text).split())))
            self._href = None


def links_in(html: str) -> list[tuple[str, str]]:
    collector = LinkCollector()
    collector.feed(html)
    return collector.links


def element(html: str, tag: str) -> str:
    """The first <tag>...</tag> block of the page, as text."""
    match = re.search(rf"<{tag}\b.*?</{tag}>", html, re.DOTALL)
    assert match, f"no <{tag}> on the page"
    return match.group(0)


def get(client: Client, path: str) -> str:
    response = client.get(path)
    assert response.status_code == 200, f"{path} returned {response.status_code}"
    return response.content.decode()


def test_home_shows_the_positioning_line(client: Client) -> None:
    assert POSITIONING in get(client, "/")


def test_home_credits_the_course_and_says_lesson_coming(client: Client) -> None:
    html = get(client, "/")
    assert "freeCodeCamp" in html
    assert "lesson coming" in html
    assert ("/faq/#report-a-bad-actor", "Where to report") in links_in(html)


@pytest.mark.smoke
@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_every_public_page_has_the_sign_in_link(client: Client, path: str) -> None:
    """The header link whose accessible name is exactly "Sign in". Never renamed, never removed."""
    assert SIGN_IN in links_in(element(get(client, path), "header"))


def test_sign_in_is_an_honest_stub_until_chapter_07(client: Client) -> None:
    assert "chapter 07" in get(client, "/auth/witus/login/")


@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_every_public_page_says_not_advice(client: Client, path: str) -> None:
    assert "Not advice" in get(client, path)


@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_no_public_page_shows_a_price_table_or_a_performance_figure(
    client: Client, path: str
) -> None:
    """PRD 7.10, checked narrowly: no <table> at all, and no signed percentage like +8.5% or -12%.

    A dollar amount is not a price: the FAQ's "$25,000" regulatory threshold must pass.
    """
    html = get(client, path)
    assert "<table" not in html.lower()
    assert re.search(r"[+-]\d+(?:\.\d+)?\s?%", html) is None


def test_internal_footer_links_resolve(client: Client) -> None:
    footer_links = links_in(element(get(client, "/"), "footer"))
    internal = {href.split("#")[0] for href, _ in footer_links if href.startswith("/")}
    assert internal, "the footer has no internal links"
    for href in sorted(internal):
        get(client, href)


def test_footer_lists_the_ecosystem_and_keeps_the_disclaimer(client: Client) -> None:
    footer = element(get(client, "/"), "footer")
    assert ("https://learn.witus.online", "Learn.WitUS (opens in new tab)") in links_in(footer)
    assert SIGN_IN in links_in(footer)
    assert "Rise Wellness of Indiana is an independent organization." in footer
    assert "not affiliated with, employed by, or endorsed by Invest.WitUS," in footer
    assert "B4C LLC" in footer


@pytest.mark.parametrize(
    "path, heading",
    [("/privacy/", "Privacy"), ("/terms/", "Terms of use"), ("/faq/", "Invest.WitUS FAQ")],
)
def test_markdown_pages_render_their_headings(client: Client, path: str, heading: str) -> None:
    html = get(client, path)
    assert heading in element(html, "h1")


def test_faq_has_the_report_anchor_and_links_the_marketing_rule(client: Client) -> None:
    html = get(client, "/faq/")
    assert 'id="report-a-bad-actor"' in html
    assert (MARKETING_RULE, MARKETING_RULE) in links_in(html)
    assert ("/faq/#report-a-bad-actor", "Report a bad actor") in links_in(element(html, "footer"))


@pytest.mark.parametrize(
    "text, expected",
    [
        ("https://example.test/a).", "https://example.test/a"),
        ("https://example.test/x(4)-1", "https://example.test/x(4)-1"),
        ("https://example.test/b/.", "https://example.test/b/"),
    ],
)
def test_bare_urls_lose_their_sentence_punctuation(text: str, expected: str) -> None:
    assert trim_url(text) == expected


def test_a_bare_url_in_markdown_becomes_a_link() -> None:
    html = render_markdown("See https://example.test/page?a=1&b=2, then stop.")
    assert ("https://example.test/page?a=1&b=2", "https://example.test/page?a=1&b=2") in links_in(
        html
    )


@pytest.mark.django_db
def test_joining_twice_keeps_one_row_and_shows_the_same_thank_you(client: Client) -> None:
    first = client.post("/waitlist/", {"name": "Ada", "email": "Ada@Example.com "}, follow=True)
    second = client.post("/waitlist/", {"name": "Ada", "email": "ada@example.com"}, follow=True)
    assert first.redirect_chain == [("/waitlist/thanks/", 302)]
    assert first.content == second.content
    assert "You are on the list." in first.content.decode()
    assert WaitlistEntry.objects.count() == 1
    assert WaitlistEntry.objects.get().email == "ada@example.com"


@pytest.mark.django_db
def test_a_bad_email_is_refused_with_a_message(client: Client) -> None:
    response = client.post("/waitlist/", {"name": "Ada", "email": "not-an-email"})
    assert response.status_code == 200
    assert "Enter a valid email address." in response.content.decode()
    assert WaitlistEntry.objects.count() == 0


@pytest.mark.django_db
def test_the_honeypot_keeps_bots_out_quietly(client: Client) -> None:
    data = {"name": "Bot", "email": "bot@example.com", "website": "https://spam.test"}
    response = client.post("/waitlist/", data)
    assert response.status_code == 302 and response["Location"] == "/waitlist/thanks/"
    assert WaitlistEntry.objects.count() == 0


def test_a_post_without_a_csrf_token_is_refused() -> None:
    strict = Client(enforce_csrf_checks=True)
    response = strict.post("/waitlist/", {"name": "Ada", "email": "ada@example.com"})
    assert response.status_code == 403


def test_settings_are_safe_by_default() -> None:
    """Debug off, the database in the folder git ignores, a labeled dev-only key."""
    assert settings.DEBUG is False
    assert settings.DATA_DIR == settings.BASE_DIR / "data" / "private"
    assert settings.SECRET_KEY.startswith("django-insecure-") or len(settings.SECRET_KEY) >= 50
```

Read it before you run it; it is the chapter's contract. Things to notice:

- `LinkCollector` is a small HTML parser from the standard library. It records every link as `(href, text)`,
  because a link's **accessible name**, the thing a screen reader announces, is computed from its content
  (W3C, 2026). The test for "Sign in" asks for that exact pair inside `<header>`; a link whose text is "Sign in
  to WitUS" or "Login" fails it.
- `client` is a pytest-django fixture: Django's test client, which calls your views directly, with no server
  and no network (pytest-dev, n.d.-b; Django Software Foundation, n.d.-k).
- `@pytest.mark.django_db` marks the tests that touch the database. pytest-django creates a throw-away test
  database and rolls back after each test; a test without the mark that touches a model fails on purpose.
- `Client(enforce_csrf_checks=True)` is the test client with CSRF checks turned **on**. They are off by
  default so ordinary tests can post without a token.
- The settings test reads `settings.DATA_DIR`, not the database name: pytest-django points SQLite at memory
  while tests run, so the file name would say nothing.

Run it:

Listing 04-4, Terminal:

```sh
uv run pytest tests/test_ch04.py
```

```text
ImportError: No module named 'invest_witus_site'
```

Red first. pytest-django reads `DJANGO_SETTINGS_MODULE` from `pyproject.toml` (pytest-dev, n.d.-a) and cannot
import it yet. The lines after that one vary; the first is the one that matters.

### 04.3 The project

Django's `django-admin startproject` would create these files beside `manage.py`. Ours live under `src/` with
the rest of the code, so write them by hand. Together they are shorter than this section makes them look.

Listing 04-5, Filename: `manage.py` (repository root):

```python
#!/usr/bin/env python
"""Django's command-line tool: `uv run python manage.py <command>`."""

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "invest_witus_site.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
```

`manage.py` is Django's `npm run`: `uv run python manage.py migrate`, `runserver`, `makemigrations`, `check`.
Its one job is to name the settings module and hand the rest to Django. pytest-django also uses it as a
landmark: a folder with a `manage.py` is a Django project, and it adds that folder to the Python path.

Listing 04-6, Filename: `src/invest_witus_site/__init__.py`:

```python
"""The Django project: settings, the root URL list, and the apps that make the website."""
```

Listing 04-7, Filename: `src/invest_witus_site/settings.py`:

```python
"""Django settings for Invest.WitUS.

Anything that differs between your laptop and a server comes from an environment variable, with a
safe default for the laptop. The names are listed in `.env.example`; values never go in git.
"""

import os
from pathlib import Path

# The repository root. This file is src/invest_witus_site/settings.py, three levels down.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# DEV-ONLY FALLBACK. Django's `check --deploy` warns about the `django-insecure-` prefix, which is
# the point: a server must set DJANGO_SECRET_KEY (chapter 06), and this value must never reach one.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or "django-insecure-dev-only-set-DJANGO_SECRET_KEY"

# Off unless DJANGO_DEBUG=1. Debug pages show settings and source code; never on a server.
DEBUG = os.environ.get("DJANGO_DEBUG") == "1"

# Comma-separated host names. The default answers a laptop and nothing else.
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

# `startproject` lists six contrib apps. We add only what a chapter uses; the admin and
# sessions arrive with chapters 05 and 07.
INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "invest_witus_site.pages",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
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
                "invest_witus_site.pages.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "invest_witus_site.wsgi.application"

# SQLite, in the folder git ignores. Chapter 06 switches to Postgres through DATABASE_URL.
DATA_DIR = BASE_DIR / "data" / "private"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "invest-witus.sqlite3",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

# The FAQ, privacy and terms pages are Markdown files in the repo, so a wording change is a normal
# commit with a diff anyone can read.
SITE_PAGES_DIR = BASE_DIR / "docs" / "site"
```

Settings is a plain module; every uppercase name in it is a setting (Django Software Foundation, n.d.-d). What
differs from the file `startproject` would generate:

- **Nothing secret and nothing machine-specific is written down.** `SECRET_KEY`, `DEBUG` and `ALLOWED_HOSTS`
  come from the environment. The fallback key starts with `django-insecure-` so that `manage.py check --deploy`
  flags it (Django Software Foundation, n.d.-a), and `DEBUG` is off unless you say otherwise. A server that
  forgets a variable gets the safe value, not the convenient one.
- **Two installed apps, not seven.** The generated list has the admin, auth, sessions and more. We add each
  one in the chapter that uses it, so you see what each is for. Chapter 05 adds the admin; chapter 07 adds
  sessions.
- **The database is a SQLite file in `data/private/`,** the folder git already ignores from chapter 03.
  Chapter 06 swaps it for Postgres through `DATABASE_URL` without touching the rest.
- **`SITE_PAGES_DIR`** is our own setting. Django does not mind extra names; `settings.SITE_PAGES_DIR` works
  like a built-in one.

Listing 04-8, Filename: `.env.example`:

```sh
# Copy to .env (git ignores it) and run with: uv run --env-file .env python manage.py runserver
# Names only; values never go in git. Every setting has a safe default in settings.py.

# "1" shows Django's debug pages and serves static files from runserver. Never "1" on a server.
DJANGO_DEBUG=1

# Leave empty on your laptop (a labeled dev-only key is used). A server sets a real one.
DJANGO_SECRET_KEY=

# Comma-separated host names the site answers to. Default: localhost,127.0.0.1
DJANGO_ALLOWED_HOSTS=
```

Copy it to `.env` (git ignores `.env`; chapter 00's `.gitignore` already has the rule) and run commands with
`uv run --env-file .env ...`; uv loads the file into the environment for that one command (Astral, n.d.-b).
Nothing in the app reads `.env` itself, which is the point: on a server there is no file, only variables.

Listing 04-9, Filename: `src/invest_witus_site/urls.py`:

```python
"""Where every URL of the site starts. Each app lists its own paths; this file includes them."""

from django.urls import include, path

urlpatterns = [
    path("", include("invest_witus_site.pages.urls")),
]
```

The root URL list. `include` hands every path to the app's own list, so an app carries its own routes (Django
Software Foundation, n.d.-l).

Listing 04-10, Filename: `src/invest_witus_site/wsgi.py`:

```python
"""WSGI entry point: what a web server calls to hand Django a request."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "invest_witus_site.settings")

application = get_wsgi_application()
```

Listing 04-11, Filename: `src/invest_witus_site/asgi.py`:

```python
"""ASGI entry point: the async twin of wsgi.py, for servers that speak ASGI."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "invest_witus_site.settings")

application = get_asgi_application()
```

Two entry points for two server protocols. `runserver` needs neither; chapter 06's host wants `wsgi.py`.

### 04.4 The app and its one table

An app is a Python package with a known layout: `models.py`, `views.py`, `urls.py`, `templates/`, `static/`,
`migrations/`. This chapter's app is `pages`: the public pages.

Listing 04-12, Filename: `src/invest_witus_site/pages/__init__.py`:

```python
"""The public pages: landing, waitlist, FAQ, privacy, terms, contact, and the sign-in stub."""
```

Listing 04-13, Filename: `src/invest_witus_site/pages/apps.py`:

```python
from django.apps import AppConfig


class PagesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "invest_witus_site.pages"
```

Listing 04-14, Filename: `src/invest_witus_site/pages/models.py`:

```python
"""Database tables for the public pages. This chapter has one: the waitlist."""

from datetime import datetime

from django.db import models


class WaitlistEntry(models.Model):
    """One person who asked to hear when the app opens. One row per email address.

    The `[str, str]` after each field type is for pyright: the type you may assign, and the type
    you read back. django-stubs leaves those two for its mypy plugin to fill in, so with pyright we
    write them ourselves (the way you would write `Field<string, string>` in TypeScript).
    """

    name: models.CharField[str, str] = models.CharField(max_length=120)
    email: models.EmailField[str, str] = models.EmailField(max_length=254, unique=True)
    created_at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name_plural = "waitlist entries"

    def __str__(self) -> str:
        return self.email

    @classmethod
    def join(cls, name: str, email: str) -> tuple[WaitlistEntry, bool]:
        """Add a person once. The same address in any case or spacing keeps the first row.

        Returns the row and whether it was created now, the way `get_or_create` does.
        """
        return cls.objects.get_or_create(
            email=email.strip().lower(), defaults={"name": name.strip()}
        )
```

A model is a class whose attributes are columns; Django makes the table and gives you `WaitlistEntry.objects`
to query it (Django Software Foundation, n.d.-i). Four things in this one:

- `unique=True` on `email` makes the database refuse a second row with the same address. `join` lowercases
  and trims the address first, so `Ada@Example.com ` and `ada@example.com` are one row; a test checks that.
- `get_or_create` finds the row or inserts it, and says which. The view does not care which: the thank-you
  page is the same either way, so the form never reveals who is already on the list.
- The `[str, str]` annotations are for pyright. django-stubs describes a field as a generic with two type
  parameters, the type you assign and the type you read back, and leaves its mypy plugin to fill them in.
  pyright has no plugin, so we write them, the way you would write `Field<string, string>` (typeddjango,
  n.d.). `created_at` reads back as a `datetime`.
- `tuple[WaitlistEntry, bool]` names the class inside its own body. Python 3.14 evaluates annotations lazily,
  so the forward reference needs no quotes; older code wrote `"WaitlistEntry"`.

Make the migrations package and let Django write the first migration:

Listing 04-15, Terminal:

```sh
mkdir -p src/invest_witus_site/pages/migrations
touch src/invest_witus_site/pages/migrations/__init__.py
uv run python manage.py makemigrations pages
uv run ruff format src/invest_witus_site/pages/migrations
```

```text
Migrations for 'pages':
  src/invest_witus_site/pages/migrations/0001_initial.py
    + Create model WaitlistEntry
```

Listing 04-16, Filename: `src/invest_witus_site/pages/migrations/0001_initial.py`:

```python
# Generated by Django 5.2.18 on 2026-10-28 03:52

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="WaitlistEntry",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=120)),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name_plural": "waitlist entries",
                "ordering": ["created_at"],
            },
        ),
    ]
```

A migration is the difference between the models and the database, written as Python so it can be reviewed
and run on any machine (Django Software Foundation, n.d.-h). Django wrote it; `ruff format` only changed
quotes and line breaks to match the project. Commit migrations, and never edit one that has run somewhere.
Your timestamp in the first line will differ; keep yours.

### 04.5 The form

Listing 04-17, Filename: `src/invest_witus_site/pages/forms.py`:

```python
"""The waitlist form: name and email, nothing more."""

from django import forms


class WaitlistForm(forms.Form):
    name = forms.CharField(label="Name", max_length=120)
    email = forms.EmailField(label="Email", max_length=254)
    # A honeypot. People never see this field (the stylesheet hides it and it is skipped by
    # keyboard); bots fill in every field they find. A filled value means "not a person".
    website = forms.CharField(
        required=False,
        label="Leave this field empty",
        widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}),
    )

    def is_bot(self) -> bool:
        return bool(self.cleaned_data.get("website"))
```

A Django form declares fields and validates a POST body against them (Django Software Foundation, n.d.-m):
`EmailField` rejects `not-an-email` with the message the test looks for, and `max_length` matches the model.
The `website` field is the honeypot. The stylesheet moves it off screen and `tabindex="-1"` keeps the keyboard
away from it, so a person never fills it in and a form-filling bot usually does. The view treats a filled
honeypot as "say thank you, store nothing".

### 04.6 Pages from Markdown

The FAQ, privacy and terms pages are Markdown files in `docs/site/`. A wording change is a commit with a
readable diff, and the same file reads well on GitHub.

Listing 04-18, Filename: `src/invest_witus_site/pages/markdown_pages.py`:

```python
"""Render the site's Markdown pages (`docs/site/*.md`) to HTML."""

import re
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

import markdown
from markdown.extensions import Extension
from markdown.inlinepatterns import InlineProcessor

# The pages the site serves and the file behind each. A fixed table, not a URL parameter, so a
# request can never name a file outside this folder.
PAGES = {"faq": "faq.md", "privacy": "privacy.md", "terms": "terms.md"}

# A URL written bare in the text. Not preceded by a quote, `=` or `>`, so a URL that is already
# inside an HTML tag is left alone.
BARE_URL = r"(?<![\w\"'=>])https?://[^\s<>\"']+"
TRAILING_PUNCTUATION = ".,;:!?"


@dataclass(frozen=True, slots=True)
class Page:
    title: str
    html: str


def trim_url(url: str) -> str:
    """Drop the sentence punctuation a bare URL picks up, but keep balanced parentheses.

    `https://example.test/a).` becomes `https://example.test/a`;
    `https://example.test/x(4)-1` stays as it is.
    """
    while True:
        before = url
        url = url.rstrip(TRAILING_PUNCTUATION)
        if url.endswith(")") and url.count("(") < url.count(")"):
            url = url[:-1]
        if url == before:
            return url


class BareUrlProcessor(InlineProcessor):
    """Turn a bare `https://...` in the text into a link whose text is the URL."""

    def handleMatch(  # noqa: N802 (Python-Markdown's name)
        self, m: re.Match[str], data: str
    ) -> tuple[ElementTree.Element, int, int]:
        url = trim_url(m.group(0))
        link = ElementTree.Element("a")
        link.set("href", url)
        link.text = url
        return link, m.start(0), m.start(0) + len(url)


class BareUrlExtension(Extension):
    def extendMarkdown(self, md: markdown.Markdown) -> None:  # noqa: N802
        # Priority 115: after Markdown's own `[text](url)` and `<url>` patterns (160 and 120),
        # before emphasis (60), so an underscore inside a URL is never read as italics.
        md.inlinePatterns.register(BareUrlProcessor(BARE_URL, md), "bare_url", 115)


def render_markdown(text: str) -> str:
    # `toc` gives every heading an id made from its text ("Report a bad actor" becomes
    # `report-a-bad-actor`), which is what the landing page and the footer link to.
    converter = markdown.Markdown(extensions=["toc", BareUrlExtension()])
    return converter.convert(text)


def load_page(pages_dir: Path, slug: str) -> Page:
    """Read one of the pages in PAGES and render it. The title is the file's first `# ` heading."""
    text = (pages_dir / PAGES[slug]).read_text(encoding="utf-8")
    title = next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), slug)
    return Page(title=title, html=render_markdown(text))
```

Two things Python-Markdown does not do on its own:

- **Heading ids.** The `toc` extension gives each heading an `id` made from its text (Python-Markdown,
  n.d.-b), so `## Report a bad actor` becomes `<h2 id="report-a-bad-actor">` and the landing page can link
  straight to it.
- **Bare URLs.** Markdown links only `<https://...>` in angle brackets or `[text](url)`. The FAQ writes its
  sources as plain URLs, so `BareUrlProcessor` is a small inline extension (Python-Markdown, n.d.-a): a regular
  expression finds `https://...`, `trim_url` drops the sentence punctuation that follows a URL, and the
  processor returns an `<a>` element plus the span of text it replaces. The balanced-parentheses rule exists
  for one real link, the SEC marketing rule at `.../section=275.206(4)-1`, whose `(4)` is part of the address.
  A test checks that exact link renders.

`PAGES` is a fixed table from slug to file name. The URL never names a file, so a request cannot reach
outside `docs/site/`.

Now write the two pages the FAQ does not cover. The PRD lists what they must say (education only, not advice;
not a broker or an adviser; paper by default; what is stored, where, and who sees it; keys server-side;
vendors named; no market data shown to others; how to delete your data; contact; a lawyer reviews both before
other users are admitted). Copy ours or write your own to that list; the tests look only for the headings.

Listing 04-19, Filename: `docs/site/privacy.md`:

```markdown
# Privacy

Last updated: October 27, 2026. Plain language on purpose. A securities lawyer reviews this page and the Terms before anyone other than the operator is admitted to the app; until then it describes what the app does today and what it is built to do.

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

Vendors the app uses or is built to use, each named so you can read its own terms: Alpaca (paper trading and, if you choose it, live trading), Tiingo (end-of-day prices), Neon (the database), Vercel (hosting), Mailgun (email), and WitUS Inbox (where the waitlist and in-app reports are mirrored for the operator). Each vendor sees only what it needs: Alpaca sees the orders you place through it, Tiingo sees the symbols whose prices are asked for, Mailgun sees the address an email goes to.

## Market data

No market data, prices or performance figures are shown on any public page, and no one's data is shown to anyone else. Prices inside the app are for the signed-in owner of the account they value.

## Cookies

The public pages set one cookie, for the form protection Django uses (CSRF). Signing in, when it arrives, adds a session cookie. There are no advertising or analytics cookies.

## Deleting your data

Email the Contact address in the footer from the address you signed up with. A waitlist entry is deleted on request; an account, when accounts exist, is deleted with everything attached to it. Plans and the journal export to CSV first if you ask.

## Children

The app is for adults. It is not directed at anyone under 13 and does not knowingly collect their data (see COPPA in the FAQ).

## Changes

Edits to this page are commits in the repository, with dates. The "last updated" line above moves when the text does.

## Contact

Use the Contact link in the footer of every page.
```

Listing 04-20, Filename: `docs/site/terms.md`:

```markdown
# Terms of use

Last updated: October 27, 2026. Plain language on purpose. A securities lawyer reviews these terms and the Privacy page before anyone other than the operator is admitted to the app.

## Education only, not advice

Invest.WitUS is a learning tool built alongside the Learn.WitUS and ElementaryMBA courses. It shows you the rules of a method you chose and whether what you did follows them. It does not tell you what to buy or sell, when, or how much, and it does not look at your income, goals or taxes. Nothing on this site or in the app is investment, legal or tax advice. Not advice, in every sense of the word.

## Not a broker, not an adviser

The operator is not registered with the SEC, FINRA, the Indiana Securities Division or any other body as a broker-dealer or an investment adviser, and the app is not one. It never holds money or securities. A brokerage does; the app only reads from it or passes your own orders to it. The FAQ names the bodies that would govern a professional tool and how to reach them.

## Paper by default

Every account starts as a paper (simulated) account. Paper results are practice at following rules, not a forecast; the broker that runs the simulation says it leaves out dividends, slippage and fees. A live account is connected only by you, later, with separate keys, behind an explicit checklist.

## Who may use the app

Today, the operator. Other learners are admitted from the waitlist, for education and alongside the course, only after the legal review above. The app is for adults. Any use must follow the terms of the broker and data vendors behind it, which are contracts you accept with them.

## Your responsibility

You decide what to do with your money. If you connect a live account, the orders are yours. Trust the broker's statement over any number in the app, and tell us when a number looks wrong.

## Your data

What we store, where, who sees it, and how to delete it are in the Privacy page. Broker keys stay on the server. No market data, prices or performance figures are shown on public pages or to any other user.

## No warranty

The app is provided as is, for learning, at no charge. It may be wrong, late or unavailable, and it may change or shut down. If it shuts down, your brokerage account stays at the broker and your plans and journal export to CSV.

## Changes

Edits to these terms are commits in the repository, with dates. The "last updated" line above moves when the text does.

## Contact

Use the Contact link in the footer of every page. To report a company or a person who took your money, use the government desks listed under "Report a bad actor" in the FAQ, not us.
```

### 04.7 Views and URLs

Listing 04-21, Filename: `src/invest_witus_site/pages/views.py`:

```python
"""The public pages. A view takes a request and returns a response; the templates do the HTML."""

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.safestring import mark_safe

from invest_witus_site.pages.forms import WaitlistForm
from invest_witus_site.pages.markdown_pages import load_page
from invest_witus_site.pages.models import WaitlistEntry

# The positioning line, word for word from the PRD (section 7.10).
POSITIONING = (
    "Pick a method you learned. Practice it on paper. "
    "The app keeps you to its rules and shows you the lesson behind each one."
)


def home(request: HttpRequest) -> HttpResponse:
    return render(request, "pages/home.html", {"positioning": POSITIONING, "form": WaitlistForm()})


def waitlist(request: HttpRequest) -> HttpResponse:
    """GET shows the form; POST adds the person once and redirects to the thank-you page.

    Redirecting after a POST (Post/Redirect/Get) means a browser refresh repeats a harmless GET,
    not the form submission. The thank-you is the same whether the address was new or already on
    the list, so the page never reveals who signed up.
    """
    if request.method != "POST":
        return render(request, "pages/waitlist.html", {"form": WaitlistForm()})
    form = WaitlistForm(request.POST)
    if not form.is_valid():
        return render(request, "pages/waitlist.html", {"form": form})
    if not form.is_bot():
        WaitlistEntry.join(name=form.cleaned_data["name"], email=form.cleaned_data["email"])
    # TODO(chapter 13): mirror the signup to WitUS Inbox as a `waitlist-signup` (doc 02, section 6).
    return redirect("waitlist-thanks")


def waitlist_thanks(request: HttpRequest) -> HttpResponse:
    return render(request, "pages/waitlist_thanks.html")


def markdown_page(request: HttpRequest, slug: str) -> HttpResponse:
    page = load_page(settings.SITE_PAGES_DIR, slug)
    # Django escapes everything a template prints. This HTML came from our own Markdown file, so
    # it is marked safe here, on purpose, in one place.
    return render(request, "pages/markdown_page.html", {"page": page, "body": mark_safe(page.html)})


def contact(request: HttpRequest) -> HttpResponse:
    return render(request, "pages/contact.html")


def sign_in_stub(request: HttpRequest) -> HttpResponse:
    """Sign in with WitUS arrives in chapter 07. Until then the link leads somewhere honest."""
    return render(request, "pages/sign_in_stub.html")
```

A view is a function from `HttpRequest` to `HttpResponse`. `render` loads a template, fills it from the
dictionary you pass (the *context*) and wraps the result in a response. Notes:

- `waitlist` is the one view that handles two methods. After a valid POST it **redirects** instead of
  rendering: if it rendered, a browser refresh would post the form again. With the redirect, a refresh
  repeats a harmless GET of the thank-you page. The test checks the redirect chain.
- `mark_safe` is the only place HTML skips escaping. Django escapes every value a template prints, which is
  what makes templates safe with user input; the Markdown HTML is ours, from a file in the repo, so this one
  value is marked safe where it is made.
- `sign_in_stub` exists so the header's "Sign in" link goes somewhere true. A 404 would pass no test and
  would mislead a visitor. Chapter 07 replaces it.
- The `TODO(chapter 13)` is the whole Inbox mirror for now. The ecosystem contract (doc 02) says store first,
  mirror later, never block the person; the storing is done.

Listing 04-22, Filename: `src/invest_witus_site/pages/urls.py`:

```python
"""The app's URLs. `name` lets templates write `{% url 'faq' %}` instead of a hard-coded path."""

from django.urls import path

from invest_witus_site.pages import views

urlpatterns = [
    path("", views.home, name="home"),
    path("waitlist/", views.waitlist, name="waitlist"),
    path("waitlist/thanks/", views.waitlist_thanks, name="waitlist-thanks"),
    path("faq/", views.markdown_page, {"slug": "faq"}, name="faq"),
    path("privacy/", views.markdown_page, {"slug": "privacy"}, name="privacy"),
    path("terms/", views.markdown_page, {"slug": "terms"}, name="terms"),
    path("contact/", views.contact, name="contact"),
    # The sign-in route the ecosystem registry points at (products.ts: signInHref). A stub now.
    path("auth/witus/login/", views.sign_in_stub, name="sign-in"),
]
```

Every path has a `name`, so templates write `{% url 'faq' %}` and a path can change in one place. The three
Markdown pages share one view and pass the slug as a keyword argument. The sign-in path is the one the
ecosystem registry already lists for this app (`signInHref` in `products.ts`); the app matches the registry,
not the other way round.

### 04.8 Templates: base, header, footer

Django's template language is HTML with `{{ variables }}`, `{% tags %}` and inheritance: a child template names
its parent with `{% extends %}` and fills the parent's `{% block %}`s (Django Software Foundation, n.d.-j).
With `APP_DIRS` on, Django looks in each app's `templates/` folder, so the files go under
`pages/templates/pages/`; the repeated `pages/` keeps names unique across apps.

Listing 04-23, Filename: `src/invest_witus_site/pages/templates/pages/base.html`:

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
</body>
</html>
```

`{% load static %}` enables the `{% static %}` tag, which turns `brand/witus/favicon.svg` into its URL. The skip
link and `<main id="main" tabindex="-1">` are the smallest keyboard-accessibility shape: press Tab once at the
top of any page, press Enter, and focus lands on the content.

Listing 04-24, Filename: `src/invest_witus_site/pages/templates/pages/_header.html`:

```html
{% load static %}
{# Logo: gemini/witus/public/brand/04-orbit-type/logomark.svg, drawn for dark backgrounds, copied into static/brand/witus/. #}
<header class="site-header">
  <div class="container header-row">
    <a class="brand" href="{% url 'home' %}">
      <img src="{% static 'brand/witus/logomark.svg' %}" alt="" width="32" height="32">
      Invest.WitUS
    </a>
    <nav aria-label="Primary">
      <a href="{% url 'faq' %}">FAQ</a>
      <a href="{% url 'home' %}#waitlist">Waitlist</a>
      {# While a visitor is signed out, this link's accessible name is exactly "Sign in" on every page. #}
      {# Never rename it (shared UI rule, 2026-10-16): the smoke test in tests/test_ch04.py fails if it changes. #}
      <a class="button" href="{% url 'sign-in' %}">Sign in</a>
    </nav>
  </div>
</header>
```

The logo's `alt` is empty on purpose: the link's name is the text beside it, "Invest.WitUS", and a screen
reader would otherwise announce an image name and then the text. The sign-in link is the one the tests guard.
`{# ... #}` is a template comment; it never reaches the browser.

The footer needs two things every page shares: the ecosystem products and the year. Rather than passing them
from every view, a **context processor** adds them to every template's context:

Listing 04-25, Filename: `src/invest_witus_site/pages/ecosystem.py`:

```python
"""The WitUS ecosystem's product list, for the footer.

Copied as data from `gemini/witus/lib/products.ts`, the canonical registry, on 2026-10-27: every
product whose `surfaces` includes "public-directory", except this app. Nothing here is invented;
when the registry changes, this list changes with it (the authoritative-values rule).
"""

from dataclasses import dataclass
from typing import Literal

Status = Literal["live", "beta", "coming-soon", "infrastructure"]


@dataclass(frozen=True, slots=True)
class Product:
    name: str
    href: str
    status: Status


SIBLINGS: tuple[Product, ...] = (
    Product("WitUS", "https://witus.online", "infrastructure"),
    Product("WitUS Inbox", "https://inbox.witus.online", "infrastructure"),
    Product("WitUS Outbox", "https://outbox.witus.online", "infrastructure"),
    Product("CentenarianOS", "https://centenarianos.com", "live"),
    Product("Work.WitUS", "https://work.witus.online", "live"),
    Product("Tour Manager OS", "https://tour.witus.online", "beta"),
    Product("Wanderlust", "https://wanderlust.witus.online", "beta"),
    Product("Fly.WitUS", "https://fly.witus.online", "beta"),
    Product("FlashLearnAI", "https://flashlearnai.witus.online", "beta"),
    Product("Learn.WitUS", "https://learn.witus.online", "live"),
    Product("AwesomeWebStore", "https://awesomewebstore.com", "live"),
    Product("Triage.Agent.WitUS", "https://triage.agent.witus.online", "beta"),
    Product("Stream.WitUS", "https://stream.witus.online", "beta"),
    Product("Centenarian Coach", "https://centenarian.coach.multiagent.witus.online", "beta"),
    Product("Shop.WitUS", "https://shop.witus.online", "infrastructure"),
    Product("Stay.WitUS", "https://stay.witus.online", "beta"),
    Product("RealEstate.WitUS", "https://realestate.witus.online", "coming-soon"),
    Product("Create.WitUS", "https://create.witus.online", "coming-soon"),
    Product("VO GOAT", "https://vogoat.witus.online", "coming-soon"),
    Product("RideWitUS", "https://ride.witus.online", "beta"),
    Product(
        "Wanderlearn Field Reporter",
        "https://wanderlearn.field.reporter.witus.online",
        "infrastructure",
    ),
)


def products() -> list[Product]:
    """The products people use, in registry order (witus.online's footer splits them this way)."""
    return [p for p in SIBLINGS if p.status != "infrastructure"]


def infrastructure() -> list[Product]:
    """The shared services behind the products."""
    return [p for p in SIBLINGS if p.status == "infrastructure"]
```

Listing 04-26, Filename: `src/invest_witus_site/pages/context_processors.py`:

```python
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
```

The products are copied, as data, from the ecosystem's registry file; the footer recipe accepts that cost so
each app stays its own repository. Products marked "coming soon" are shown without a link, the way
witus.online's own footer shows them, because a link to a site that does not exist yet is a broken promise.
`settings.py` already names the processor in `TEMPLATES`.

Listing 04-27, Filename: `src/invest_witus_site/pages/templates/pages/_footer.html`:

```html
{% load static %}
{# The ecosystem footer, after gemini/witus/public/brand/footer-recipe.md: the same structure as every #}
{# WitUS app in this app's own palette. The Rise Wellness callout and its disclaimer are verbatim (only #}
{# the app name changed) and so is the copyright line. The dashes in them are written as HTML entities #}
{# so the source file stays dash-free; the page shows them. #}
<footer class="site-footer">
  <div class="container">
    <div class="footer-brand">
      {# Logo: gemini/witus/public/brand/04-orbit-type/wordmark.svg, copied into static/brand/witus/. #}
      <img src="{% static 'brand/witus/wordmark.svg' %}" alt="WitUS" width="110" height="28">
      <p class="footer-name">Invest.WitUS</p>
      <p class="muted">Pick a taught investing method and stay with it, on paper first.</p>
      <p class="notice">Not advice. Invest.WitUS is a learning tool: it recommends nothing, holds no money, and shows no market data on public pages.</p>
    </div>

    <section aria-labelledby="rise-wellness-heading" class="rise">
      <header class="rise-header">
        <p class="eyebrow">Mental health support</p>
        <h2 id="rise-wellness-heading">Rise Wellness of Indiana</h2>
        <p class="muted small">Independent mental health provider &middot; Not affiliated with Invest.WitUS</p>
      </header>
      <p>Rise Wellness of Indiana provides compassionate, personalized, holistic mental health care: evidence-based medicine, trauma-informed care, and a whole-person approach to help you heal, grow, and thrive in mind, body, and spirit.</p>
      <div class="rise-grid">
        <div>
          <p class="eyebrow muted">Services</p>
          <ul class="plain small">
            <li>ADHD testing &amp; management (in-person and from home)</li>
            <li>Anxiety &amp; depression</li>
            <li>Maternal mental health</li>
            <li>Medication management</li>
            <li>GeneSight&reg; genetic testing</li>
            <li>Behavioral therapy &amp; coaching</li>
            <li>Routine lab testing</li>
          </ul>
        </div>
        <div>
          <p class="eyebrow muted">Visit or call</p>
          <address class="small">320 North Meridian Street<br>Indianapolis, IN 46204<br>Mon&ndash;Sat by appointment &middot; Sun closed</address>
          <p class="small rise-links">
            <a href="tel:+13179650299">317-965-0299</a>
            <span aria-hidden="true">&middot;</span>
            <a href="https://risewellnessofindiana.com" target="_blank" rel="noopener noreferrer">risewellnessofindiana.com<span class="sr-only"> (opens in new tab)</span></a>
            <span aria-hidden="true">&middot;</span>
            <a href="https://www.centenarianos.com/safety#rise-wellness" target="_blank" rel="noopener noreferrer">Full safety page<span class="sr-only"> on centenarianos.com (opens in new tab)</span></a>
          </p>
        </div>
      </div>
      <blockquote class="rise-quote small">
        &ldquo;At Rise Wellness, we believe everyone has the capacity to rise above challenges and live a fulfilling, healthy life. Our care is guided by the belief that healing is personal, holistic, and rooted in compassion.&rdquo;
        <span class="attribution muted">Rise Wellness of Indiana</span>
      </blockquote>
      {# The non-negotiable disclaimer. Only the app name token changed; never paraphrase, trim or reorder it. #}
      <p class="disclaimer muted">Rise Wellness of Indiana is an independent organization. They are not affiliated with, employed by, or endorsed by Invest.WitUS, CentenarianOS, B4C LLC, AwesomeWebStore.com, or Anthony McDonald. We are grateful for their collaboration on mental health safety resources for our community.</p>
    </section>

    <div class="footer-grid">
      <div>
        <p class="footer-heading">Ecosystem</p>
        <ul class="plain">
          {% for product in ecosystem_products %}
            <li>
              {% if product.status == "coming-soon" %}
                <span class="muted">{{ product.name }} (coming soon)</span>
              {% else %}
                <a href="{{ product.href }}" target="_blank" rel="noopener noreferrer">{{ product.name }}<span class="sr-only"> (opens in new tab)</span></a>
              {% endif %}
            </li>
          {% endfor %}
        </ul>
        <p class="footer-heading">Infrastructure</p>
        <ul class="plain">
          {% for product in infrastructure_products %}
            <li><a href="{{ product.href }}" target="_blank" rel="noopener noreferrer">{{ product.name }}<span class="sr-only"> (opens in new tab)</span></a></li>
          {% endfor %}
        </ul>
      </div>
      <div>
        <p class="footer-heading">Invest.WitUS</p>
        <ul class="plain">
          <li><a href="{% url 'home' %}#roadmap">Roadmap</a></li>
          <li><a href="{% url 'faq' %}">FAQ</a></li>
          <li><a href="{% url 'sign-in' %}">Sign in</a></li>
        </ul>
      </div>
      <div>
        <p class="footer-heading">Partners &amp; Legal</p>
        <ul class="plain">
          <li>
            <a href="https://www.centenarianos.com/safety#rise-wellness" target="_blank" rel="noopener noreferrer">Rise Wellness<span class="sr-only"> (mental-health partner, opens in new tab)</span></a>
            <p class="muted small">Mental-health partner</p>
          </li>
          <li><a href="{% url 'terms' %}">Terms</a></li>
          <li><a href="{% url 'privacy' %}">Privacy</a></li>
          <li><a href="{% url 'faq' %}#report-a-bad-actor">Report a bad actor</a></li>
          <li><a href="{% url 'contact' %}">Contact</a></li>
        </ul>
      </div>
    </div>

    <div class="copyright muted small">
      <p>&copy; {{ year }} B4C LLC &mdash; A <a href="https://awesomewebstore.com" target="_blank" rel="noopener noreferrer">AwesomeWebStore.com<span class="sr-only"> (opens in new tab)</span></a> brand</p>
    </div>
  </div>
</footer>
```

This is the ecosystem footer from the brand package's recipe (WitUS, 2026b): an optional logo and one-line
summary, the Rise Wellness callout, three columns, the copyright line. Two pieces are copied word for word and
stay that way: the callout, whose disclaimer was cleared with the partner (only the app name token changed),
and the copyright line. Their dashes are written as `&mdash;` and `&ndash;` so the source stays free of dash
characters, which this project's writing rule bans, while the page shows the recipe's exact text. The "Not
advice" line at the top of the footer is what puts those words on every page, which the PRD requires and a
test checks.

`<span class="sr-only">` holds text only screen readers get: "(opens in new tab)" after each external link,
because `target="_blank"` is otherwise a surprise.

### 04.9 The pages

Listing 04-28, Filename: `src/invest_witus_site/pages/templates/pages/home.html`:

```html
{% extends "pages/base.html" %}
{% block title %}Invest.WitUS: pick a taught investing method and stay with it{% endblock %}
{% block content %}
<section class="container hero" aria-labelledby="hero-heading">
  <p class="eyebrow">A learning tool, not advice</p>
  <h1 id="hero-heading">{{ positioning }}</h1>
  <p class="lead">Invest.WitUS is a Python app for people learning to invest with the Learn.WitUS and ElementaryMBA courses. You choose a method a course teaches, run it on a paper (simulated) account first, and the app checks what you did against that method's rules. Every rule links to the lesson that teaches it.</p>
  <p class="actions"><a class="button" href="#waitlist">Join the waitlist</a> <a href="{% url 'faq' %}">Read the FAQ</a></p>
</section>

<section class="container" aria-labelledby="how-heading">
  <h2 id="how-heading">How it works</h2>
  <ol class="steps">
    <li><strong>Pick a method you learned.</strong> The first is index investing with a fixed monthly contribution; 12-1 momentum comes next.</li>
    <li><strong>Practice it on paper.</strong> Paper by default. No money moves unless you connect a live account yourself, later, behind a checklist.</li>
    <li><strong>Review yourself against the rules.</strong> A monthly review shows where you left your plan and sends you back to the lesson. It predicts nothing.</li>
  </ol>
</section>

<section class="container" aria-labelledby="courses-heading">
  <h2 id="courses-heading">The courses</h2>
  <p>The app is built alongside two courses. Neither lesson page is published yet, so there is no link to follow; this text changes when there is.</p>
  <ul>
    <li>The investing methods course, in ElementaryMBA with a preview in Learn.WitUS: <span class="muted">lesson coming</span></li>
    <li>The Python tutorial that builds this app chapter by chapter, in Learn.WitUS: <span class="muted">lesson coming</span></li>
  </ul>
</section>

<section class="container" aria-labelledby="report-heading">
  <div class="callout">
    <h2 id="report-heading">Report a bad actor</h2>
    <p>If someone took your money, pressured you, or will not give it back, report it now. Reporting is free and you do not need a lawyer. This app takes no complaints about other companies; the government desks that do are listed in the FAQ.</p>
    <p><a class="button" href="{% url 'faq' %}#report-a-bad-actor">Where to report</a></p>
  </div>
</section>

<section class="container" id="waitlist" aria-labelledby="waitlist-heading">
  <h2 id="waitlist-heading">Waitlist</h2>
  <p>Leave your name and email and you will hear when the app opens.</p>
  {% include "pages/_waitlist_form.html" %}
</section>

<section class="container" id="roadmap" aria-labelledby="roadmap-heading">
  <h2 id="roadmap-heading">Roadmap</h2>
  <ol>
    <li><strong>Now:</strong> the operator's own accounts. Methods and their rules, a monthly review, holdings entered by hand from statements, a journal, paper trading.</li>
    <li><strong>Next:</strong> other learners, education only, admitted from the waitlist with the course, after a securities lawyer has reviewed the terms and the privacy page.</li>
  </ol>
  <p class="muted">The tutorial's chapter list lives with the code. Each chapter becomes a Learn.WitUS lesson.</p>
</section>

<section class="container" aria-labelledby="credit-heading">
  <h2 id="credit-heading">Credit</h2>
  <p>The project began from freeCodeCamp's course "Python Algorithmic Trading with SnapTrade, Massive, Alpaca" (Carnes, 2026), which builds a momentum app in Django and invites learners to extend it. Invest.WitUS keeps the idea, a rules-based method run on a paper account, and builds its own stack and code.</p>
  <p class="small muted">Carnes, B. (2026, September 29). <cite>Python algorithmic trading with SnapTrade, Massive, Alpaca</cite> [Video course announcement]. freeCodeCamp. <a href="https://www.freecodecamp.org/news/python-algorithmic-trading-with-snaptrade-massive-alpaca/">https://www.freecodecamp.org/news/python-algorithmic-trading-with-snaptrade-massive-alpaca/</a></p>
</section>
{% endblock %}
```

The landing page, section by section: the positioning line as the `<h1>`; what the app is; how it works; the
two courses, each marked "lesson coming" because no lesson URL exists yet (the authoritative-values rule:
never invent one); the "Report a bad actor" callout; the waitlist; a two-line roadmap, which is where the
footer's Roadmap link points; and the freeCodeCamp credit with its reference. There is no price, chart,
return or promise on it, and the test will tell you if one creeps in.

Listing 04-29, Filename: `src/invest_witus_site/pages/templates/pages/_waitlist_form.html`:

```html
<form method="post" action="{% url 'waitlist' %}" class="waitlist-form" novalidate>
  {% csrf_token %}
  <div class="field">
    <label for="{{ form.name.id_for_label }}">Name</label>
    {{ form.name }}
    {{ form.name.errors }}
  </div>
  <div class="field">
    <label for="{{ form.email.id_for_label }}">Email</label>
    {{ form.email }}
    {{ form.email.errors }}
  </div>
  {# The honeypot. Hidden from people by the stylesheet and from assistive tech by aria-hidden. #}
  <div class="honeypot" aria-hidden="true">
    <label for="{{ form.website.id_for_label }}">Leave this field empty</label>
    {{ form.website }}
  </div>
  <p class="small">Invest.WitUS is a learning tool, not advice, and not open to other users yet. Access later is for education, alongside the course.</p>
  <button type="submit">Join the waitlist</button>
</form>
```

`{% csrf_token %}` renders a hidden input holding a token tied to a cookie; `CsrfViewMiddleware` rejects any
POST without a matching pair (Django Software Foundation, n.d.-g). That is what the 403 test checks. Each field
is rendered with its own `<label for=...>`. Django adds `aria-invalid` and `aria-describedby` to a field with
errors on its own (Django Software Foundation, n.d.-b), so the error list is announced with the field.
`novalidate` turns off the browser's built-in checks, so the server's messages are the ones people see, which
is also what the tests see.

Listing 04-30, Filename: `src/invest_witus_site/pages/templates/pages/waitlist.html`:

```html
{% extends "pages/base.html" %}
{% block title %}Waitlist: Invest.WitUS{% endblock %}
{% block content %}
<section class="container narrow">
  <h1>Join the waitlist</h1>
  <p>Leave your name and email and you will hear when the app opens.</p>
  {% include "pages/_waitlist_form.html" %}
</section>
{% endblock %}
```

Listing 04-31, Filename: `src/invest_witus_site/pages/templates/pages/waitlist_thanks.html`:

```html
{% extends "pages/base.html" %}
{% block title %}Thank you: Invest.WitUS{% endblock %}
{% block content %}
<section class="container narrow">
  <h1>Thank you</h1>
  <p>You are on the list. You will hear from us when the app opens to learners, and not before.</p>
  <p>Until then, the <a href="{% url 'faq' %}">FAQ</a> explains what the app is and is not.</p>
</section>
{% endblock %}
```

Listing 04-32, Filename: `src/invest_witus_site/pages/templates/pages/markdown_page.html`:

```html
{% extends "pages/base.html" %}
{% block title %}{{ page.title }}: Invest.WitUS{% endblock %}
{% block content %}
<article class="container prose">
  {{ body }}
</article>
{% endblock %}
```

Listing 04-33, Filename: `src/invest_witus_site/pages/templates/pages/contact.html`:

```html
{% extends "pages/base.html" %}
{% block title %}Contact: Invest.WitUS{% endblock %}
{% block content %}
<section class="container narrow">
  <h1>Contact</h1>
  {# The address is the ecosystem's contact from the shared footer recipe, not a guess. #}
  <p>Email the operator at <a href="mailto:bam@awews.com">bam@awews.com</a>. That is the one route in this phase: to ask a question, to report a wrong number, to leave the waitlist, or to have your data deleted. Write from the address you signed up with.</p>
  <p>An in-app form for bugs, feature requests and questions arrives in chapter 13 of the tutorial.</p>
  <p>To report a company or a person who took your money, do not write to us; use the government desks listed under <a href="{% url 'faq' %}#report-a-bad-actor">Report a bad actor</a> in the FAQ.</p>
</section>
{% endblock %}
```

The contact address is the ecosystem's, from the footer recipe, not a guess; in this phase email is the only
route, and chapter 13 adds the in-app form.

Listing 04-34, Filename: `src/invest_witus_site/pages/templates/pages/sign_in_stub.html`:

```html
{% extends "pages/base.html" %}
{% block title %}Sign in: Invest.WitUS{% endblock %}
{% block content %}
<section class="container narrow">
  <h1>Sign in</h1>
  <p>Sign in with WitUS arrives in chapter 07 of the tutorial. Until then there is nothing to sign in to: the app's only user is its operator, and every public page works without an account.</p>
  <p><a href="{% url 'home' %}">Back to the home page</a></p>
</section>
{% endblock %}
```

### 04.10 Static files: the logo and the stylesheet

Static files live in each app's `static/` folder and `runserver` serves them at `STATIC_URL` while `DEBUG` is
on (Django Software Foundation, n.d.-f). A server needs `collectstatic` and a file server; that is chapter 06.

Copy the WitUS logo files. The ecosystem keeps one brand package and each app copies the variant it uses
(WitUS, 2026a). This app uses the default, `04-orbit-type`, which is drawn for dark backgrounds, so the site is
dark. The six files (`favicon.svg`, `favicon-16.png`, `favicon-32.png`, `favicon-180.png`, `logomark.svg`,
`wordmark.svg`) go into `src/invest_witus_site/pages/static/brand/witus/`. Take them from the reference
repository's tree at `v04` (Browse link below) or from the raw URLs the brand package's README lists.

Listing 04-35, Filename: `src/invest_witus_site/pages/static/pages/site.css`:

```css
/* Invest.WitUS: one hand-written stylesheet, no build step.
   Dark surface because the WitUS logo (static/brand/witus/, from gemini/witus/public/brand/04-orbit-type/)
   is drawn for dark backgrounds. Accent: sky, this app's color in the ecosystem registry. */

:root {
  --bg: #020617;
  --surface: #0f172a;
  --border: #1e293b;
  --text: #f1f5f9;
  --muted: #94a3b8;
  --accent: #38bdf8;
  --accent-ink: #082f49;
  --danger: #fda4af;
  --max: 64rem;
  --gutter: 1rem;
}

* { box-sizing: border-box; }

html { color-scheme: dark; }

body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 16px/1.6 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}

a { color: var(--accent); }
a:hover { text-decoration-thickness: 2px; }

a:focus-visible, button:focus-visible, input:focus-visible, [tabindex="-1"]:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-radius: 2px;
}

h1, h2, h3 { line-height: 1.2; }
h1 { font-size: clamp(1.6rem, 4vw, 2.4rem); }
h2 { font-size: 1.35rem; margin-top: 2.5rem; }
h3 { font-size: 1.1rem; }

.container { max-width: var(--max); margin: 0 auto; padding: 0 var(--gutter); }
.narrow { max-width: 42rem; }
.muted { color: var(--muted); }
.small { font-size: 0.875rem; }
.eyebrow { font-size: 0.75rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent); font-weight: 600; }
.lead { font-size: 1.125rem; }
.plain { list-style: none; margin: 0; padding: 0; }
.plain li { margin: 0.25rem 0; }

.sr-only {
  position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
  overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;
}

.skip-link { position: absolute; left: -999px; top: 0.5rem; background: var(--accent); color: var(--accent-ink); padding: 0.5rem 1rem; z-index: 10; }
.skip-link:focus { left: 0.5rem; }

/* Header */
.site-header { border-bottom: 1px solid var(--border); background: var(--surface); }
.header-row { display: flex; align-items: center; justify-content: space-between; gap: 1rem; min-height: 3.5rem; flex-wrap: wrap; }
.brand { display: inline-flex; align-items: center; gap: 0.5rem; color: var(--text); font-weight: 800; text-decoration: none; }
.brand img { display: block; }
.site-header nav { display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }
.site-header nav a { min-height: 2.75rem; display: inline-flex; align-items: center; }

.button {
  display: inline-flex; align-items: center; min-height: 2.75rem; padding: 0 1rem;
  background: var(--accent); color: var(--accent-ink); font-weight: 700; text-decoration: none; border-radius: 0.375rem;
}
.button:hover { background: #7dd3fc; }

main { padding: 1rem 0 3rem; }
.hero { padding-top: 2rem; }
.actions { display: flex; gap: 1rem; align-items: center; flex-wrap: wrap; }
.steps li { margin-bottom: 0.75rem; }

.callout { border: 1px solid var(--accent); background: rgba(56, 189, 248, 0.08); border-radius: 0.5rem; padding: 1rem 1.25rem; }
.callout h2 { margin-top: 0; }

/* Forms */
.waitlist-form { max-width: 28rem; }
.field { margin-bottom: 1rem; }
.field label { display: block; font-weight: 600; margin-bottom: 0.25rem; }
.field input { width: 100%; min-height: 2.75rem; padding: 0.5rem 0.75rem; background: var(--surface); color: var(--text); border: 1px solid var(--border); border-radius: 0.375rem; font: inherit; }
.errorlist { list-style: none; padding: 0; margin: 0.25rem 0 0; color: var(--danger); font-size: 0.875rem; }
button[type="submit"] { min-height: 2.75rem; padding: 0 1.25rem; background: var(--accent); color: var(--accent-ink); font: inherit; font-weight: 700; border: 0; border-radius: 0.375rem; cursor: pointer; }
.honeypot { position: absolute; left: -10000px; top: auto; width: 1px; height: 1px; overflow: hidden; }

/* Markdown pages */
.prose { max-width: 48rem; }
.prose blockquote { margin: 1.5rem 0; padding: 1rem 1.25rem; border-left: 4px solid var(--accent); background: rgba(56, 189, 248, 0.08); border-radius: 0 0.5rem 0.5rem 0; }
.prose a { overflow-wrap: anywhere; }

/* Footer */
.site-footer { border-top: 1px solid var(--border); margin-top: 3rem; padding: 2.5rem 0; background: var(--surface); font-size: 0.9375rem; }
.footer-brand { text-align: center; margin-bottom: 2rem; }
.footer-brand img { display: inline-block; }
.footer-name { font-weight: 800; margin: 0.5rem 0 0; }
.footer-brand p { margin: 0.25rem 0; }
.notice { max-width: 40rem; margin: 0.75rem auto 0; }
.footer-heading { font-weight: 600; margin: 0 0 0.5rem; }
.footer-grid { display: grid; grid-template-columns: 1fr; gap: 2rem; }
@media (min-width: 40rem) { .footer-grid { grid-template-columns: repeat(3, 1fr); } }
.footer-grid a, .rise-links a { display: inline-flex; align-items: center; min-height: 1.75rem; }
.footer-grid .footer-heading + ul + .footer-heading { margin-top: 1.25rem; }
.copyright { margin-top: 2rem; padding-top: 1.5rem; border-top: 1px solid var(--border); text-align: center; }

.rise { border: 1px solid rgba(56, 189, 248, 0.3); background: rgba(56, 189, 248, 0.06); border-radius: 0.5rem; padding: 1.25rem; margin-bottom: 2rem; }
.rise h2 { font-size: 1rem; margin: 0.25rem 0 0; }
.rise-header p { margin: 0; }
.rise-grid { display: grid; grid-template-columns: 1fr; gap: 1rem; margin-top: 1rem; }
@media (min-width: 40rem) { .rise-grid { grid-template-columns: 1fr 1fr; } }
.rise address { font-style: normal; }
.rise-links { display: flex; flex-wrap: wrap; gap: 0.5rem 0.75rem; align-items: center; }
.rise-quote { margin: 1rem 0 0; padding-left: 0.75rem; border-left: 2px solid var(--accent); font-style: italic; }
.rise-quote .attribution { display: block; font-style: normal; margin-top: 0.25rem; }
.disclaimer { font-size: 0.75rem; margin: 1rem 0 0; }
```

One hand-written stylesheet. The ecosystem's TypeScript apps use Tailwind; this repository has no Node
toolchain, and a Python tutorial should not grow one for a landing page, so plain CSS with a few custom
properties does the job. The parts that matter for accessibility: a visible focus outline on every control,
link and button targets at least 2.75rem tall, muted text that still reads against the dark surface, and
`.sr-only` and `.honeypot`, which hide things the right way for the right audience.

### 04.11 Run it

Listing 04-36, Terminal:

```sh
cp .env.example .env
uv run python manage.py migrate
uv run --env-file .env python manage.py runserver
```

```text
Operations to perform:
  Apply all migrations: pages
Running migrations:
  Applying pages.0001_initial... OK
...
Starting development server at http://127.0.0.1:8000/
```

Open http://127.0.0.1:8000/. Press Tab through the header; its last stop is "Sign in". Join the waitlist
twice with the same address in different capitals; the thank-you page is the same both times. Read `/faq/`,
`/privacy/` and `/terms/`; press "Where to report" and watch the page jump to the heading. `/nope/` is a 404.

`migrate` created `data/private/invest-witus.sqlite3`. `git status` must list neither it nor `.env`.

### 04.12 Green

Listing 04-37, Terminal:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

```text
90 passed in 0.77s
All checks passed!
57 files already formatted
0 errors, 0 warnings, 0 informations
```

Forty-two new tests and the forty-eight from before. `uv run pytest -m smoke` runs the eight sign-in checks
alone; chapter 06 runs that set against every deployment.

## Checkpoint

- `uv run pytest` prints `90 passed`; ruff and pyright pass.
- `uv run --env-file .env python manage.py runserver` serves `/`, `/faq/`, `/privacy/`, `/terms/`, `/contact/`
  and `/auth/witus/login/`, each with the header and the footer.
- Joining the waitlist twice keeps one row:
  `uv run python manage.py shell -c "from invest_witus_site.pages.models import WaitlistEntry; print(WaitlistEntry.objects.count())"`.
- `git status` shows neither `.env` nor anything under `data/private/`.
- Commit and push: `git add -A && git commit -m "Chapter 04: the public landing page"`.

## Exercises

1. The FAQ's headings have ids now. Python-Markdown's `toc` extension also builds a table of contents
   (`converter.toc`, after `convert`). Render it at the top of `/faq/` as an "On this page" list. Keep every
   chapter 04 test green.
2. Move the roadmap off the landing page: write `docs/site/roadmap.md`, add it to `PAGES` and to `urls.py` at
   `/roadmap/`, and point the footer's Roadmap link at it. Which test tells you the footer still works?
3. A person who types their email with a trailing period (`ada@example.com.`) is told "Enter a valid email
   address." Decide whether the form should fix it for them or tell them, write the test for your answer, then
   make it pass.

## If you get stuck

- Browse: https://github.com/dapperAuteur/invest-witus/tree/v04
- Diff for this chapter: https://github.com/dapperAuteur/invest-witus/compare/v03...v04
- Zip: https://github.com/dapperAuteur/invest-witus/archive/v04.zip
- Take the reference's files:
  `git fetch reference --tags && git checkout v04 -- src tests docs/site manage.py pyproject.toml .env.example scripts`,
  then `uv sync`.
- `ImportError: No module named 'invest_witus_site'` after the files exist: `module-name` in `pyproject.toml`
  does not list it, or you did not run `uv sync` after adding it.
- `TemplateDoesNotExist: pages/home.html`: the app is missing from `INSTALLED_APPS`, or the file is at
  `templates/home.html` instead of `templates/pages/home.html`.
- `DisallowedHost`: the host you opened is not in `DJANGO_ALLOWED_HOSTS` (the default covers `localhost` and
  `127.0.0.1`).
- `CSRF verification failed`: the form is missing `{% csrf_token %}`.
- The page is unstyled and the logo is missing under `runserver`: `DJANGO_DEBUG` is not `1`. With debug off,
  Django does not serve static files; chapter 06 handles that for a server.
- `no such table: pages_waitlistentry`: run `uv run python manage.py migrate`.
- pyright says a field's type is "partially unknown": the `[str, str]` annotation is missing on that field.

## What we learned

- A Django project is settings plus a root URL list; an app is a package with models, views, URLs, templates
  and static files.
- Settings read the environment and default to the safe value, never the convenient one.
- A URL pattern names a view; a view returns a response; templates extend a base and include partials; a
  context processor adds the same values to every page.
- A model is a table; a migration is the reviewed, versioned change that creates it.
- Forms validate on the server; CSRF tokens stop cross-site posts; a redirect after POST stops double
  submits; a honeypot catches bots.
- A link's accessible name is its text. One link in this app is named "Sign in", and a test keeps it so.
- Public pages are information, not advice, and a narrow test keeps tables and percentages off them.

## Next

Chapter 05 starts from tag `v04` and adds the data behind the app: accounts, securities and holdings entered
from statements, with the Django admin as the first back office, where the waitlist becomes a list you can
read.

## References

Astral. (n.d.-a). *Build backend*. uv documentation. https://docs.astral.sh/uv/concepts/build-backend/
(retrieved October 27, 2026)

Astral. (n.d.-b). *Command-line reference*. uv documentation. https://docs.astral.sh/uv/reference/cli/
(retrieved October 27, 2026)

Django Software Foundation. (n.d.-a). *Deployment checklist*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/ (retrieved October 27, 2026)

Django Software Foundation. (n.d.-b). *Django 5.0 release notes*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/releases/5.0/ (retrieved October 27, 2026)

Django Software Foundation. (n.d.-c). *Django 5.2 release notes*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/releases/5.2/ (retrieved October 27, 2026)

Django Software Foundation. (n.d.-d). *Django settings*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/settings/ (retrieved October 27, 2026)

Django Software Foundation. (n.d.-e). *Download Django* [Supported versions]. https://www.djangoproject.com/download/
(retrieved October 27, 2026)

Django Software Foundation. (n.d.-f). *How to manage static files (e.g. images, JavaScript, CSS)*. Django 5.2
documentation. https://docs.djangoproject.com/en/5.2/howto/static-files/ (retrieved October 27, 2026)

Django Software Foundation. (n.d.-g). *How to use Django's CSRF protection*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/howto/csrf/ (retrieved October 27, 2026)

Django Software Foundation. (n.d.-h). *Migrations*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/migrations/ (retrieved October 27, 2026)

Django Software Foundation. (n.d.-i). *Models*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/db/models/ (retrieved October 27, 2026)

Django Software Foundation. (n.d.-j). *Templates*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/templates/ (retrieved October 27, 2026)

Django Software Foundation. (n.d.-k). *Testing tools*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/testing/tools/ (retrieved October 27, 2026)

Django Software Foundation. (n.d.-l). *URL dispatcher*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/http/urls/ (retrieved October 27, 2026)

Django Software Foundation. (n.d.-m). *Working with forms*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/forms/ (retrieved October 27, 2026)

pytest-dev. (n.d.-a). *Configuring Django settings*. pytest-django documentation.
https://pytest-django.readthedocs.io/en/latest/configuring_django.html (retrieved October 27, 2026)

pytest-dev. (n.d.-b). *Django helpers*. pytest-django documentation.
https://pytest-django.readthedocs.io/en/latest/helpers.html (retrieved October 27, 2026)

Python-Markdown. (n.d.-a). *Extensions API*. https://python-markdown.github.io/extensions/api/ (retrieved
October 27, 2026)

Python-Markdown. (n.d.-b). *Table of Contents extension*. https://python-markdown.github.io/extensions/toc/
(retrieved October 27, 2026)

typeddjango. (n.d.). *django-stubs* [README]. GitHub. https://github.com/typeddjango/django-stubs (retrieved
October 27, 2026)

W3C. (2026, October 21). *Accessible name and description computation 1.2* [W3C Working Draft].
https://www.w3.org/TR/accname-1.2/ (retrieved October 27, 2026)

WitUS. (2026a). *WitUS ecosystem brand package* [README]. Internal document, `gemini/witus/public/brand/README.md`
(read October 27, 2026)

WitUS. (2026b). *Ecosystem footer recipe*. Internal document, `gemini/witus/public/brand/footer-recipe.md` (read
October 27, 2026)

WitUS. (2026c). *Shared UI, UX and DX standard*. Internal document, `gemini/witus/docs/shared-ui-ux-dx.md` (read
October 27, 2026)
