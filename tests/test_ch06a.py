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
