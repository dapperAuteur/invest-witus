"""Fixtures every test file shares. pytest loads this file on its own; nothing imports it.

Added in chapter 05, when tests started creating users: Django's default password hasher is slow
on purpose (it is meant to make guessing expensive), which turns every `admin_client` into half a
second of setup. Tests use the fast hasher instead; the real one still guards real logins.
"""

import httpx
import pytest
from pytest_django.fixtures import Settings

from invest_witus_site.outbox import client as outbox_client
from invest_witus_site.reports import inbox


@pytest.fixture(autouse=True)
def fast_password_hashing(settings: Settings) -> None:
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture(autouse=True)
def no_real_inbox(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    """Chapter 13: WitUS Inbox is off in every test, whatever the shell exports, and a request
    that slipped through would fail here instead of leaving the machine. Tests that want Inbox
    on set the three names and their own fake transport (tests/test_ch13.py)."""
    settings.INBOX_INGEST_URL = ""
    settings.INBOX_SOURCE_SLUG = ""
    settings.INBOX_INGEST_SECRET = ""
    monkeypatch.setattr(inbox, "transport", httpx.MockTransport(refuse_real_inbox))


def refuse_real_inbox(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"a test tried to reach {request.url.host}")


@pytest.fixture(autouse=True)
def no_real_outbox(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    """WitUS Outbox is off in every test, kill switch included, whatever the shell exports, and a
    request that slipped through fails here. tests/test_outbox.py turns it on with its own fake."""
    settings.OUTBOX_TRIGGER_ENABLED = ""
    settings.OUTBOX_INGEST_URL = ""
    settings.OUTBOX_SOURCE_SLUG = ""
    settings.OUTBOX_INGEST_SECRET = ""
    monkeypatch.setattr(outbox_client, "transport", httpx.MockTransport(refuse_real_outbox))


def refuse_real_outbox(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"a test tried to reach {request.url.host}")
