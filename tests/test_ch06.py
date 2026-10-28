"""Chapter 06 checkpoint: settings a server can run, the database from a URL, the health route,
`collectstatic`, a superuser without a keyboard, the root entry file, and the deploy files."""

import importlib
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path
from types import ModuleType
from unittest import mock

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.core.management import CommandError, call_command
from django.core.servers.basehttp import get_internal_wsgi_application
from django.db import OperationalError
from django.db.backends.base.base import BaseDatabaseWrapper
from django.test import Client
from pytest_django.fixtures import Settings

from invest_witus_site.database import database_from_url
from invest_witus_site.health import app_version

BASE_DIR = Path(settings.BASE_DIR)
# The shape Neon's dashboard hands out, with a made-up host and an escaped character in the
# password. Nothing here is a real connection string.
NEON_SHAPED = (
    "postgresql://app_owner:pa%40ss@ep-example-123456-pooler.us-east-2.aws.neon.tech/invest"
    "?sslmode=require&channel_binding=require"
)
# Fifty characters with more than five distinct ones, which is what `check --deploy` wants.
# Not a secret: it exists only inside this test run.
TEST_KEY = "test-only-" + "0123456789" * 5


# --- The database from a URL -----------------------------------------------------------------


def test_a_postgres_url_becomes_django_settings() -> None:
    database = database_from_url(NEON_SHAPED, BASE_DIR)
    assert database["ENGINE"] == "django.db.backends.postgresql"
    assert database["NAME"] == "invest"
    assert database["USER"] == "app_owner"
    assert database["PASSWORD"] == "pa@ss", "percent-escapes in the password are decoded"
    assert database["HOST"] == "ep-example-123456-pooler.us-east-2.aws.neon.tech"
    assert database["PORT"] == "", "no port in the URL means the driver's default"
    assert database["OPTIONS"] == {"sslmode": "require", "channel_binding": "require"}
    assert database["DISABLE_SERVER_SIDE_CURSORS"] is True, "the pooler cannot hold a cursor"
    assert database["CONN_HEALTH_CHECKS"] is True


def test_sslmode_defaults_to_require_and_a_port_is_kept() -> None:
    database = database_from_url("postgres://u:p@db.example.test:5433/name", BASE_DIR)
    assert database["ENGINE"] == "django.db.backends.postgresql"
    assert database["OPTIONS"] == {"sslmode": "require"}
    assert database["PORT"] == "5433"


def test_sqlite_urls_relative_to_the_repo_or_absolute() -> None:
    relative = database_from_url("sqlite:///data/private/x.sqlite3", BASE_DIR)
    assert relative == {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "data" / "private" / "x.sqlite3",
    }
    absolute = database_from_url("sqlite:////tmp/x.sqlite3", BASE_DIR)
    assert absolute["NAME"] == Path("/tmp/x.sqlite3")


@pytest.mark.parametrize(
    "url, problem",
    [
        ("mysql://u:p@h/d", "must start with"),
        ("postgresql://u:p@h/", "database name"),
        ("postgresql:///d", "needs a host"),
        ("sqlite://x.sqlite3", "looks like sqlite:///"),
        ("sqlite:///", "needs a file path"),
        ("postgresql://u:p@h/d?application_name=x", "not one of"),
    ],
)
def test_a_bad_url_is_refused_with_a_reason(url: str, problem: str) -> None:
    with pytest.raises(ValueError, match=problem):
        database_from_url(url, BASE_DIR)


def test_the_laptop_default_is_sqlite_in_the_private_folder() -> None:
    assert settings.DATABASE_URL == "sqlite:///data/private/invest-witus.sqlite3"
    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3"
    assert "direct" not in settings.DATABASES, "the direct alias exists only with Neon's URL"


# --- Settings a server can run ---------------------------------------------------------------


def test_the_production_rules_hold_with_debug_off() -> None:
    """The suite runs with debug off, so these are the values a server gets."""
    assert settings.DEBUG is False
    assert settings.SESSION_COOKIE_SECURE is True
    assert settings.CSRF_COOKIE_SECURE is True
    assert len(settings.SECRET_KEY) >= 50
    assert settings.STATIC_ROOT == BASE_DIR / "staticfiles"
    assert settings.WSGI_APPLICATION == "wsgi.application"
    assert settings.SECURE_PROXY_SSL_HEADER is None, "no proxy on a laptop, so no trusted header"
    assert settings.SECURE_SSL_REDIRECT is False, "Vercel redirects; off everywhere else"


def fresh_settings(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> ModuleType:
    """Import `invest_witus_site.settings` again, in this process, with exactly the variables in
    `env` and none of the usual ones, the way a server would see it. Django's own settings object
    is left alone, so the rest of the suite is unaffected; monkeypatch undoes everything after."""
    for name in list(os.environ):
        if name.startswith(("DJANGO_", "VERCEL", "DATABASE_URL", "STORAGE_DATABASE_URL")):
            monkeypatch.delenv(name)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delitem(sys.modules, "invest_witus_site.settings")
    return importlib.import_module("invest_witus_site.settings")


def test_settings_refuse_to_start_without_a_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ImproperlyConfigured, match="DJANGO_SECRET_KEY is not set") as refused:
        fresh_settings(monkeypatch, {})
    assert "get_random_secret_key" in str(refused.value), "the message says how to make one"


def test_debug_is_refused_on_vercel(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ImproperlyConfigured, match="DJANGO_DEBUG=1 on Vercel"):
        fresh_settings(monkeypatch, {"DJANGO_DEBUG": "1", "VERCEL": "1"})


def test_a_laptop_with_debug_on_gets_the_labeled_key(monkeypatch: pytest.MonkeyPatch) -> None:
    laptop = fresh_settings(monkeypatch, {"DJANGO_DEBUG": "1"})
    assert laptop.SECRET_KEY.startswith("django-insecure-")
    assert laptop.SESSION_COOKIE_SECURE is False and laptop.CSRF_COOKIE_SECURE is False
    assert laptop.ALLOWED_HOSTS == ["localhost", "127.0.0.1"]


def production_env(tmp_path: Path) -> dict[str, str]:
    return {
        "VERCEL": "1",
        "VERCEL_URL": "invest-witus-abc123-example.vercel.app",
        "VERCEL_PROJECT_PRODUCTION_URL": "invest.witus.online",
        "DJANGO_SECRET_KEY": TEST_KEY,
        "DJANGO_ALLOWED_HOSTS": "invest.witus.online",
        "DJANGO_CSRF_TRUSTED_ORIGINS": "https://invest.witus.online",
        "DATABASE_URL": f"sqlite:///{tmp_path / 'app.sqlite3'}",
    }


def test_vercel_tells_the_settings_about_its_proxy_and_host_names(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = fresh_settings(monkeypatch, production_env(tmp_path))
    assert server.DEBUG is False
    assert server.SECRET_KEY == TEST_KEY
    assert server.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")
    assert server.SECURE_SSL_REDIRECT is True
    assert server.SESSION_COOKIE_SECURE is True and server.CSRF_COOKIE_SECURE is True
    assert server.ALLOWED_HOSTS == [
        "invest.witus.online",
        "invest-witus-abc123-example.vercel.app",
    ], "the domain, listed by hand and again by Vercel, appears once"
    assert server.CSRF_TRUSTED_ORIGINS == [
        "https://invest.witus.online",
        "https://invest-witus-abc123-example.vercel.app",
    ]
    assert server.DATABASES["default"]["NAME"] == tmp_path / "app.sqlite3"
    assert "direct" not in server.DATABASES, "only DATABASE_URL was set"


def test_the_direct_alias_appears_with_neons_unpooled_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = production_env(tmp_path) | {"DATABASE_URL_UNPOOLED": f"sqlite:///{tmp_path / 'd.db'}"}
    server = fresh_settings(monkeypatch, env)
    assert server.DATABASES["direct"]["NAME"] == tmp_path / "d.db"
    assert server.DATABASES["default"]["NAME"] == tmp_path / "app.sqlite3"


def manage(env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    """`manage.py <args>` in a fresh process that sees only the variables given, so a test can
    stand in for a server whose environment is exactly known."""
    keep = {name: os.environ[name] for name in ("PATH", "HOME") if name in os.environ}
    return subprocess.run(
        [sys.executable, "manage.py", *args],
        cwd=BASE_DIR,
        env={**keep, **env},
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_deploy_checklist_passes_in_a_production_environment(tmp_path: Path) -> None:
    """Django's own `check --deploy`, run the way Vercel would run it: a separate process whose
    whole environment is the production one."""
    result = manage(production_env(tmp_path), "check", "--deploy")
    assert result.returncode == 0, result.stderr
    assert "System check identified no issues" in result.stdout + result.stderr


# --- The root entry file, with and without the project installed -----------------------------


def test_the_root_entry_file_hands_over_the_project_application() -> None:
    import wsgi
    from invest_witus_site.wsgi import application

    assert wsgi.application is application
    assert get_internal_wsgi_application() is application, "runserver loads the same object"


def test_manage_and_the_entry_file_work_without_the_project_installed(tmp_path: Path) -> None:
    """Vercel installs the dependencies, never this project. This takes src/ off the import
    path, the way Vercel's function sees the world, then runs manage.py and loads wsgi.py."""
    script = (
        "import runpy, sys\n"
        "sys.path[:] = [p for p in sys.path if not p.rstrip('/').endswith('/src')]\n"
        "sys.argv = ['manage.py', 'check']\n"
        "runpy.run_path('manage.py', run_name='__main__')\n"
        "application = runpy.run_path('wsgi.py')['application']\n"
        "print('application:', type(application).__name__)\n"
    )
    keep = {name: os.environ[name] for name in ("PATH", "HOME") if name in os.environ}
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BASE_DIR,
        env={**keep, **production_env(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "application: WSGIHandler" in result.stdout


# --- /healthz/ -------------------------------------------------------------------------------


@pytest.mark.django_db
def test_healthz_reports_the_version_and_a_live_database(client: Client) -> None:
    response = client.get("/healthz/")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"
    assert "no-store" in response["Cache-Control"]
    with open(BASE_DIR / "pyproject.toml", "rb") as f:
        version = tomllib.load(f)["project"]["version"]
    assert json.loads(response.content) == {"status": "ok", "version": version, "database": True}
    assert app_version() == version


@pytest.mark.django_db
def test_healthz_is_503_when_the_database_does_not_answer(client: Client) -> None:
    broken = mock.patch.object(
        BaseDatabaseWrapper, "cursor", side_effect=OperationalError("host unreachable")
    )
    with broken:
        response = client.get("/healthz/")
    assert response.status_code == 503
    body = json.loads(response.content)
    assert body == {"status": "degraded", "version": app_version(), "database": False}
    assert "unreachable" not in response.content.decode(), "no error text leaves the server"


def test_healthz_answers_get_only(client: Client) -> None:
    assert client.post("/healthz/").status_code == 405


# --- collectstatic and the superuser --------------------------------------------------------


def test_collectstatic_gathers_every_apps_files(tmp_path: Path, settings: Settings) -> None:
    settings.STATIC_ROOT = tmp_path / "static"
    call_command("collectstatic", interactive=False, verbosity=0)
    assert (tmp_path / "static" / "pages" / "site.css").is_file()
    assert (tmp_path / "static" / "brand" / "witus" / "logomark.svg").is_file()
    assert (tmp_path / "static" / "admin" / "css" / "base.css").is_file(), "the admin's too"


@pytest.mark.django_db
def test_a_superuser_can_be_made_without_a_keyboard(
    monkeypatch: pytest.MonkeyPatch, django_user_model: type[User]
) -> None:
    monkeypatch.setenv("DJANGO_SUPERUSER_USERNAME", "owner")
    monkeypatch.setenv("DJANGO_SUPERUSER_EMAIL", "owner@example.com")
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "correct-horse-battery-staple")
    call_command("createsuperuser", interactive=False, verbosity=0)
    owner = django_user_model.objects.get(username="owner")
    assert owner.is_superuser and owner.is_staff
    assert owner.email == "owner@example.com"
    assert owner.check_password("correct-horse-battery-staple")
    with pytest.raises(CommandError, match="already taken"):
        call_command("createsuperuser", interactive=False, verbosity=0)


# --- The deploy files ------------------------------------------------------------------------


def test_vercel_json_names_the_entry_file_and_builds_only_what_the_ecosystem_builds() -> None:
    config = json.loads((BASE_DIR / "vercel.json").read_text(encoding="utf-8"))
    assert "wsgi.py" in config["functions"]
    assert "tests/**" in config["functions"]["wsgi.py"]["excludeFiles"]
    assert "docs/site" not in config["functions"]["wsgi.py"]["excludeFiles"], "the FAQ ships"
    ignore = config["ignoreCommand"]
    assert '"$VERCEL_ENV" = "production"' in ignore and "bundle/*" in ignore


def test_the_neon_cleanup_workflow_is_in_place() -> None:
    workflow = (BASE_DIR / ".github" / "workflows" / "neon-preview-cleanup.yml").read_text()
    assert "neon-preview-cleanup" in workflow
    assert "vars.NEON_PROJECT_ID" in workflow and "secrets.NEON_API_KEY" in workflow


def test_the_runtime_is_pinned_to_a_version_vercel_offers() -> None:
    assert (BASE_DIR / ".python-version").read_text().strip() == "3.14"
    with open(BASE_DIR / "pyproject.toml", "rb") as f:
        assert tomllib.load(f)["project"]["requires-python"] == ">=3.14"
