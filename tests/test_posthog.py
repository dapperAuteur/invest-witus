"""PostHog page views on signed-in pages (2026-11-04, decision 176, backlog 22; witus plan 26).

The switch: on only on Vercel's Production deployment with a public `phc_` key. The pages: only a
signed-in page carries the config and the script; public pages keep no script (decision 151). The
config: the key, `/ingest`, `app: invest` and the page's route with every id and symbol replaced.
The script: PostHog's own loader, the ecosystem's init options, and a `before_send` that lets
only a `$pageview` out. The proxy: `vercel.json` rewrites `/ingest/...` to PostHog, trailing
slash kept. The browser side (one `$pageview`, no title, no ids, no cookie, no other event) was
checked in headless Chromium against posthog-js 1.445.5; these tests pin the markup it relies on.
"""

import importlib
import json
import os
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.test import Client, RequestFactory
from django.urls import URLResolver, get_resolver, resolve
from pytest_django.fixtures import Settings

from invest_witus_site.holdings.models import Account
from invest_witus_site.pages import analytics
from tests.test_ch04 import PUBLIC_PATHS

BASE_DIR = Path(settings.BASE_DIR)
SCRIPT_FILE = BASE_DIR / "src" / "invest_witus_site" / "pages" / "static" / "pages" / "posthog.js"
# Not secrets: made-up values that exist only inside this test run.
TEST_KEY = "test-only-" + "0123456789" * 5
FAKE_PHC = "phc_test_only_not_a_real_key"
SCRIPT_TAG = '<script src="/static/pages/posthog.js" defer></script>'
CONFIG_OPEN = '<script id="posthog-config" type="application/json">'
# The heart of PostHog's HTML snippet (https://posthog.com/docs/libraries/js, read 2026-11-04):
# the stand-in that loads array.js from `<api_host>/static/`, which is why "/ingest" works.
LOADER = 'p.src=s.api_host.replace(".i.posthog.com","-assets.i.posthog.com")+"/static/array.js"'


def fresh_settings(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> ModuleType:
    """Import the settings module again with exactly the variables in `env`, the way a server
    sees it (chapter 06a's helper, plus the PostHog names)."""
    for name in list(os.environ):
        if name.startswith(
            ("DJANGO_", "VERCEL", "DATABASE_URL", "POSTHOG_", "NEXT_PUBLIC_POSTHOG")
        ):
            monkeypatch.delenv(name)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delitem(sys.modules, "invest_witus_site.settings", raising=False)
    return importlib.import_module("invest_witus_site.settings")


def production_env(tmp_path: Path, vercel_env: str = "production") -> dict[str, str]:
    return {
        "VERCEL": "1",
        "VERCEL_ENV": vercel_env,
        "VERCEL_URL": "invest-witus-abc123-example.vercel.app",
        "DJANGO_SECRET_KEY": TEST_KEY,
        "DJANGO_ALLOWED_HOSTS": "invest.witus.online",
        "DATABASE_URL": f"sqlite:///{tmp_path / 'app.sqlite3'}",
    }


@pytest.fixture
def owner(django_user_model: type[User]) -> User:
    return django_user_model.objects.create_user("owner", "owner@example.com", "pw")


@pytest.fixture
def account(owner: User) -> Account:
    return Account.objects.create(
        name="Roth of Anthony", broker="Example", kind="paper", owner=owner
    )


@pytest.fixture
def posthog_on(settings: Settings) -> Settings:
    settings.POSTHOG_ENABLED = True
    settings.POSTHOG_KEY = FAKE_PHC
    return settings


def config_of(html: str) -> dict[str, str]:
    start = html.index(CONFIG_OPEN) + len(CONFIG_OPEN)
    return json.loads(html[start : html.index("</script>", start)])


# --- The switch -----------------------------------------------------------------------------


def test_off_in_this_suite_with_the_documented_defaults() -> None:
    assert settings.POSTHOG_ENABLED is False
    assert settings.POSTHOG_HOST == "https://us.i.posthog.com"
    assert settings.POSTHOG_API_HOST == "/ingest"
    assert settings.POSTHOG_UI_HOST == "https://us.posthog.com"
    assert settings.POSTHOG_APP == "invest", "the slug of this app's Sign in with WitUS client"


def test_a_key_on_a_laptop_stays_off(monkeypatch: pytest.MonkeyPatch) -> None:
    laptop = fresh_settings(monkeypatch, {"DJANGO_DEBUG": "1", "POSTHOG_KEY": FAKE_PHC})
    assert laptop.POSTHOG_ENABLED is False


def test_a_key_on_a_server_off_vercel_stays_off(monkeypatch: pytest.MonkeyPatch) -> None:
    server = fresh_settings(monkeypatch, {"DJANGO_SECRET_KEY": TEST_KEY, "POSTHOG_KEY": FAKE_PHC})
    assert server.POSTHOG_ENABLED is False


def test_a_preview_with_a_key_stays_off(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env = production_env(tmp_path, "preview") | {"POSTHOG_KEY": FAKE_PHC}
    assert fresh_settings(monkeypatch, env).POSTHOG_ENABLED is False


def test_production_without_a_key_stays_off(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert fresh_settings(monkeypatch, production_env(tmp_path)).POSTHOG_ENABLED is False


@pytest.mark.parametrize("name", ["POSTHOG_KEY", "NEXT_PUBLIC_POSTHOG_KEY"])
def test_production_with_a_key_under_either_name_turns_it_on(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str
) -> None:
    server = fresh_settings(monkeypatch, production_env(tmp_path) | {name: FAKE_PHC + "\n"})
    assert server.POSTHOG_ENABLED is True
    assert server.POSTHOG_KEY == FAKE_PHC, "a trailing newline from a pipe is dropped"


def test_a_key_that_is_not_a_public_project_key_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = production_env(tmp_path) | {"POSTHOG_KEY": "phx_personal_api_key_never_in_a_page"}
    with pytest.raises(ImproperlyConfigured, match="phc_") as raised:
        fresh_settings(monkeypatch, env)
    assert "phx_personal" not in str(raised.value), "the message never prints the value"


def test_a_host_other_than_the_proxys_upstream_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = production_env(tmp_path) | {"POSTHOG_HOST": "https://eu.example.test"}
    with pytest.raises(ImproperlyConfigured, match="POSTHOG_HOST"):
        fresh_settings(monkeypatch, env)
    same = production_env(tmp_path) | {"POSTHOG_HOST": "https://us.i.posthog.com/"}
    assert fresh_settings(monkeypatch, same).POSTHOG_HOST == "https://us.i.posthog.com"


# --- The pages ------------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_public_pages_carry_nothing_even_when_it_is_on(
    client: Client, posthog_on: Settings, path: str
) -> None:
    html = client.get(path).content.decode()
    assert "posthog-config" not in html and "posthog.js" not in html
    assert "<script" not in html, "decision 151: a public page carries no script"


@pytest.mark.django_db
def test_signed_in_pages_carry_nothing_while_it_is_off(
    client: Client, owner: User, account: Account
) -> None:
    client.force_login(owner)
    for path in ["/accounts/", f"/accounts/{account.pk}/", "/settings/"]:
        html = client.get(path).content.decode()
        assert "posthog-config" not in html and "posthog.js" not in html, path


@pytest.mark.django_db
def test_a_signed_in_page_carries_the_config_and_the_script_when_on(
    client: Client, owner: User, account: Account, posthog_on: Settings
) -> None:
    client.force_login(owner)
    html = client.get(f"/accounts/{account.pk}/?view=B").content.decode()
    assert html.count(SCRIPT_TAG) == 1 and html.count(CONFIG_OPEN) == 1
    assert html.index(CONFIG_OPEN) < html.index(SCRIPT_TAG) < html.index("</body>")
    config = config_of(html)
    assert config == {
        "key": FAKE_PHC,
        "api_host": "/ingest",
        "ui_host": "https://us.posthog.com",
        "app": "invest",
        "path": "/accounts/:id/",
    }
    text = json.dumps(config)
    assert str(account.pk) not in config["path"] and "Roth" not in text and "owner" not in text


@pytest.mark.django_db
def test_signed_in_but_on_the_report_form_too(
    client: Client, owner: User, posthog_on: Settings
) -> None:
    client.force_login(owner)
    assert config_of(client.get("/report/").content.decode())["path"] == "/report/"


# --- The path -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/accounts/", "/accounts/"),
        ("/accounts/12/", "/accounts/:id/"),
        ("/accounts/12/watch/SPY/", "/accounts/:id/watch/:symbol/"),
        ("/accounts/12/watch/BRK.B/profile/", "/accounts/:id/watch/:symbol/profile/"),
        ("/accounts/12/watch/7/remove/", "/accounts/:id/watch/:item_id/remove/"),
        ("/accounts/12/method/review/2026-10/", "/accounts/:id/method/review/:month/"),
        ("/accounts/12/method/review/2026-10/close/", "/accounts/:id/method/review/:month/close/"),
        ("/accounts/12/logbook/34/edit/", "/accounts/:id/logbook/:entry_id/edit/"),
        ("/accounts/12/paper/link/", "/accounts/:id/paper/link/"),
        ("/compare/", "/compare/"),
        ("/settings/", "/settings/"),
        ("/", "/"),
    ],
)
def test_the_path_is_the_route_with_every_part_named(path: str, expected: str) -> None:
    request = RequestFactory().get(path + "?accounts=12&symbol=SPY#x")
    request.resolver_match = resolve(path)
    assert analytics.page_path(request) == expected


def test_a_page_no_route_matched_sends_none_of_its_path() -> None:
    request = RequestFactory().get("/accounts/12/nothing-here/SPY/")
    assert request.resolver_match is None
    assert analytics.page_path(request) == analytics.NOT_FOUND == "/:not-found/"


@pytest.mark.parametrize(
    ("route", "expected"),
    [
        ("accounts/<int:pk>/watch/<str:symbol>/", "/accounts/:id/watch/:symbol/"),
        ("things/<slug>/", "/things/:slug/"),
        (r"x/^(?P<month>\d{4}-(\d{2}))/$", "/x/:month/"),
        (r"x/(\d+)/[a-z]/", "/x/:part/[a-z]/"),
        (r"files/report\.csv", "/files/report.csv"),
    ],
)
def test_route_template(route: str, expected: str) -> None:
    assert analytics.route_template(route) == expected


def every_route(resolver: URLResolver, prefix: str = "") -> list[str]:
    routes: list[str] = []
    for item in resolver.url_patterns:
        if isinstance(item, URLResolver):
            routes += every_route(item, prefix + str(item.pattern))
        else:
            routes.append(prefix + str(item.pattern))
    return routes


def test_no_route_in_the_project_leaves_a_captured_part_in_the_path() -> None:
    routes = [r for r in every_route(get_resolver()) if not r.startswith("admin/")]
    assert len(routes) > 30
    for route in routes:
        template = analytics.route_template(route)
        assert not re.search(r"[<>()\\^$?]", template), (route, template)
        assert not re.search(r"\d", template), (route, template)


# --- The script -----------------------------------------------------------------------------


def test_the_script_is_posthogs_loader_with_the_ecosystems_options() -> None:
    script = SCRIPT_FILE.read_text(encoding="utf-8")
    assert LOADER in script and script.count("!function(t,e)") == 1
    for option in [
        "autocapture: false",
        "capture_pageview: false",
        "capture_pageleave: false",
        "disable_session_recording: true",
        'persistence: "memory"',
        'person_profiles: "never"',
        "advanced_disable_flags: true",
        "rageclick: false",
        "capture_dead_clicks: false",
        "capture_heatmaps: false",
        "capture_exceptions: false",
        "capture_performance: false",
        "disable_surveys: true",
        "disable_external_dependency_loading: true",
        "before_send: beforeSend",
        "ph.register({ app: config.app })",
        'ph.capture("$pageview", { $current_url: page, $pathname: config.path })',
    ]:
        assert option in script, option
    assert "identify(" not in script, "anonymous only: no cross-app identity (plan 26)"
    assert "eu.i.posthog.com" not in script


def test_before_send_lets_only_a_pageview_out_and_drops_the_title() -> None:
    script = SCRIPT_FILE.read_text(encoding="utf-8")
    assert 'event.event !== "$pageview"' in script and "return null;" in script
    assert 'name === "title" || name === "$title"' in script
    assert "referrerOrigin(value)" in script, "a referrer is cut to its origin"


# --- The proxy ------------------------------------------------------------------------------


def test_vercel_rewrites_ingest_to_posthog_keeping_the_trailing_slash() -> None:
    config = json.loads((BASE_DIR / "vercel.json").read_text(encoding="utf-8"))
    assert config["rewrites"] == [
        {
            "source": "/ingest/static/:path(.*)",
            "destination": "https://us-assets.i.posthog.com/static/:path",
        },
        {"source": "/ingest/:path(.*)", "destination": "https://us.i.posthog.com/:path"},
    ], "assets first, then the catch-all, as in witus.online's next.config.ts"
    # `/ingest/:path*` compiles (Vercel's routing-utils, path-to-regexp) to a pattern that does not
    # match a path ending in "/", so PostHog's /e/ and /flags/ would fall through to Django.
    assert all(":path*" not in rule["source"] for rule in config["rewrites"])
    upstream = config["rewrites"][1]["destination"].removesuffix("/:path")
    assert upstream == settings.POSTHOG_PROXY_UPSTREAM == settings.POSTHOG_HOST


# --- The docs -------------------------------------------------------------------------------


def test_env_example_names_both_variables() -> None:
    text = (BASE_DIR / ".env.example").read_text(encoding="utf-8")
    assert "\nPOSTHOG_KEY=\n" in text and "\nPOSTHOG_HOST=\n" in text


@pytest.mark.django_db
def test_the_privacy_page_names_posthog(client: Client) -> None:
    html = client.get("/privacy/").content.decode()
    assert "PostHog" in html and "November 4, 2026" in html
    assert "signed-in" in html
