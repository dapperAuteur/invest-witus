"""Django settings for Invest.WitUS.

Anything that differs between your laptop and a server comes from an environment variable, with a
safe default for the laptop. The names are listed in `.env.example`; values never go in git.
Chapter 06 added the server's side: the database from `DATABASE_URL`, a secret key the server
must set, the HTTPS cookie and proxy settings, the folder `collectstatic` fills, and logging a
server can show. Chapter 07 added the four names of Sign in with WitUS; chapter 08 the price
source and the cron secret, at the end. Chapters 09 and 10 add one app each and no names.
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
    "invest_witus_site.accounts",
    "invest_witus_site.prices",
    # The watch list (chapter 09): symbols the owner follows, kept per account, pulled nightly.
    "invest_witus_site.watchlist",
    # The method engine (chapter 10): the plan an account runs, its journal, the review, the views.
    "invest_witus_site.methods",
    # Alpaca paper trading (chapter 11): the paper client, the orders, the confirm step, the sync.
    "invest_witus_site.paper",
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
                "invest_witus_site.accounts.context_processors.identity",
                # The header's "Paper account" link for the owner of a linked account.
                "invest_witus_site.paper.context_processors.paper_link",
                # The header's "Logbook" link for an owner with a plan or an entry (decision 115).
                "invest_witus_site.methods.context_processors.logbook_link",
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
# Vercel's connect dialog can put a prefix on every name the integration writes; the production
# project was connected with the prefix STORAGE (read from its variable list, 2026-10-28), so the
# prefixed names are accepted as well. An unprefixed name wins when both exist.
def first_env(*names: str) -> str | None:
    """The first of `names` that is set and not empty, or None."""
    for name in names:
        if value := os.environ.get(name):
            return value
    return None


DATA_DIR = BASE_DIR / "data" / "private"
POOLED_URL = first_env("DATABASE_URL", "STORAGE_DATABASE_URL")
DATABASE_URL = POOLED_URL or "sqlite:///data/private/invest-witus.sqlite3"
if not POOLED_URL:
    # A server's filesystem may be read-only; then /healthz/ reports the database as missing.
    with contextlib.suppress(OSError):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASES = {"default": database_from_url(DATABASE_URL, BASE_DIR)}
if unpooled := first_env("DATABASE_URL_UNPOOLED", "STORAGE_DATABASE_URL_UNPOOLED"):
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

# Sign in with WitUS (chapter 07): OpenID Connect against the ecosystem's identity provider. The
# client is ON only when the secret is set; without it the sign-in route shows chapter 04's stub
# page and the site deploys as before. The issuer is what the provider asserts in its discovery
# document; the default is the ecosystem's accounts host as read on October 28, 2026, copied from
# that document, and the client refuses a document whose issuer differs. The client id follows the
# registry's `witus-<slug>` form. The secret is minted in the witus repo (task 07) and never
# written anywhere but the two Vercel projects' Environment Variables pages.
WITUS_OIDC_ISSUER = (os.environ.get("WITUS_OIDC_ISSUER") or "https://accounts.witus.online").rstrip(
    "/"
)
WITUS_OIDC_CLIENT_ID = os.environ.get("WITUS_OIDC_CLIENT_ID") or "witus-invest"
WITUS_OIDC_CLIENT_SECRET = os.environ.get("WITUS_OIDC_CLIENT_SECRET", "")
WITUS_OIDC_SCOPES = os.environ.get("WITUS_OIDC_SCOPES") or "openid email profile"
if not WITUS_OIDC_ISSUER.startswith("https://"):
    raise ImproperlyConfigured(
        "WITUS_OIDC_ISSUER must be the provider's https:// issuer, as its discovery document "
        "states it, such as https://accounts.witus.online"
    )
if "openid" not in WITUS_OIDC_SCOPES.split():
    raise ImproperlyConfigured(
        "WITUS_OIDC_SCOPES must include openid, such as: openid email profile"
    )

# Where `login_required` sends a visitor who is not signed in: the WitUS sign-in route, by name.
LOGIN_URL = "sign-in"

# Prices (chapter 08). The nightly pull writes one close per symbol per day into the app's own
# table. With TIINGO_API_KEY set, the closes come from Tiingo's end-of-day endpoint with the
# owner's own key; the free plan's license is "Internal Use Only" (its pricing page, read October
# 28, 2026), and the values are shown to the signed-in owner and to no one else. Without a key the
# pull reads `<SYMBOL>.csv` files from PRICES_CSV_DIR, chapter 02's format, which is what a laptop
# and a learner's copy use.
TIINGO_API_KEY = os.environ.get("TIINGO_API_KEY", "")
PRICES_CSV_DIR = Path(os.environ.get("PRICES_CSV_DIR") or DATA_DIR / "prices")
# What Vercel sends as `Authorization: Bearer <value>` when it calls the cron route (its docs,
# read October 28, 2026; at least 16 random characters). Empty means the route answers 503 and
# runs nothing: a deploy that forgot the variable fails closed.
CRON_SECRET = os.environ.get("CRON_SECRET", "")

# Alpaca paper trading (chapter 11). The owner's paper keys, from the paper dashboard's API Keys
# module; empty means every Alpaca feature says "not set" and nothing is called. The client's host
# is fixed in `paper/alpaca.py` to paper-api.alpaca.markets, never read from here. Live trading is
# not built: it needs the checklist in a later chapter and separate keys under other names.
ALPACA_PAPER_KEY_ID = os.environ.get("ALPACA_PAPER_KEY_ID", "")
ALPACA_PAPER_SECRET_KEY = os.environ.get("ALPACA_PAPER_SECRET_KEY", "")
# Alpaca's own tools read the host from APCA_API_BASE_URL (its paper trading page, read October
# 29, 2026). This app does not, but a value pointing anywhere except the paper host means someone
# expects live trading here, so the settings refuse to start rather than run beside that belief.
_alpaca_base_url = os.environ.get("APCA_API_BASE_URL", "")
if _alpaca_base_url and _alpaca_base_url.rstrip("/") != "https://paper-api.alpaca.markets":
    raise ImproperlyConfigured(
        "APCA_API_BASE_URL points somewhere other than https://paper-api.alpaca.markets. "
        "This app trades on paper only; unset it or set it to the paper host."
    )
