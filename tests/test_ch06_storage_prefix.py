"""The Neon integration's names may carry the prefix the Vercel connect dialog was given
(production: STORAGE_). Settings accept both; the unprefixed name wins."""

import importlib
import os
import sys
from types import ModuleType

import pytest

SECRET = {"DJANGO_SECRET_KEY": "a-test-key-long-enough-for-the-settings-guard-0123456789"}


def fresh_settings(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> ModuleType:
    for name in list(os.environ):
        if name.startswith(("DJANGO_", "VERCEL", "DATABASE_URL", "STORAGE_DATABASE_URL")):
            monkeypatch.delenv(name)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delitem(sys.modules, "invest_witus_site.settings")
    return importlib.import_module("invest_witus_site.settings")


def test_prefixed_names_alone_give_postgres_and_the_direct_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = fresh_settings(
        monkeypatch,
        SECRET
        | {
            "STORAGE_DATABASE_URL": "postgresql://u:p@pooled.example/db?sslmode=require",
            "STORAGE_DATABASE_URL_UNPOOLED": "postgresql://u:p@direct.example/db?sslmode=require",
        },
    )
    assert server.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"
    assert server.DATABASES["default"]["HOST"] == "pooled.example"
    assert server.DATABASES["direct"]["HOST"] == "direct.example"


def test_the_unprefixed_name_wins_when_both_exist(monkeypatch: pytest.MonkeyPatch) -> None:
    server = fresh_settings(
        monkeypatch,
        SECRET
        | {
            "DATABASE_URL": "postgresql://u:p@plain.example/db",
            "STORAGE_DATABASE_URL": "postgresql://u:p@prefixed.example/db",
        },
    )
    assert server.DATABASES["default"]["HOST"] == "plain.example"


def test_no_database_name_at_all_still_means_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    server = fresh_settings(monkeypatch, SECRET)
    assert server.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3"
    assert "direct" not in server.DATABASES
