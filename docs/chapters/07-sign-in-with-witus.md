# Chapter 07: Sign in with WitUS

**Starts from:** tag `v06a`. **Ends at:** tag `v07`.
**Written against:** Python 3.14.10, uv 0.13.6, Django 5.2.18, httpx 0.28.1, PyJWT 2.15.1 with cryptography 50.0.2,
and the ecosystem identity provider's discovery document and key set as read on October 28, 2026. The provider
is a running service; when it and this text disagree, read its discovery document again.
**Goal:** "Sign in" in the header sends the browser to the WitUS identity provider and brings it back signed in.
The app does OpenID Connect with no auth framework: three HTTP calls with httpx, one signature check with PyJWT,
and every check the standard asks for written where you can read it. People are keyed by the WitUS user id,
never by email. The client is off until the owner sets a secret, so the site keeps deploying as before.
**Time:** 3 to 4 hours for the code and tests. The provider side is the owner's and takes 20 minutes.

The listings in this chapter are not typed in by hand. `scripts/render_chapter.py` pastes the real files from
tag `v07` into the chapter text, so what you read and what the tests run are the same bytes.

## What you will learn

- **The authorization code flow, step by step:** a redirect out with a state, a nonce and a PKCE challenge; a
  callback with a code; a server-to-server exchange of the code for tokens; an id token verified; a session.
- **Reading a provider's discovery document** and its key set, and what to do when the document is not where
  the standard says.
- **Verifying a JWT the way the standard asks:** signature, algorithm, issuer, audience, expiry, nonce, and
  why the algorithm is pinned to the one the provider uses.
- **PKCE with S256,** in eight lines, and the worked example from the RFC as a test.
- **Django sessions and `login()` / `logout()`:** what is in the session cookie (an id) and what is not.
- **A one-to-one profile keyed by an external id,** instead of a custom user model, and a linking rule written
  down before it runs.
- **A fake provider in a test,** with a real Ed25519 key, through httpx's `MockTransport`.
- **A POST-only view** and a form where a link would have been wrong.

## Before the code: what the provider says about itself, and what the client must check

**The flow.** The visitor clicks "Sign in". The app sends the browser to the provider's authorize endpoint
with a random `state`, a random `nonce` and a hash of a random `code_verifier`, and keeps all three in the
session. The provider signs the person in (a magic link, on WitUS) and sends the browser back to this app's
callback with a `code` and the `state`. The app checks the `state`, then, server to server, trades the `code`
plus the `code_verifier` for tokens. The id token is a signed JWT that names the person; the app verifies it,
finds or makes the Django user, and calls `login()`. Six steps, and each one has a test.

**What discovery said.** An OpenID provider publishes a JSON document about itself. Discovery 1.0 puts it at
the issuer plus `/.well-known/openid-configuration` and says the document's `issuer` must be identical to the
URL it was fetched under (OpenID Foundation, 2023). On October 28, 2026, that path on
`https://accounts.witus.online` answered 404 with the witus.online not-found page; the document lives at
`/api/idp/.well-known/openid-configuration`, because the provider is better-auth's OIDC plugin mounted at
`/api/idp` (WitUS, 2026d). The document itself says:

| Field | Value read October 28, 2026 |
|---|---|
| `issuer` | `https://accounts.witus.online` |
| `authorization_endpoint`, `token_endpoint`, `userinfo_endpoint` | `https://accounts.witus.online/api/idp/oauth2/` + `authorize`, `token`, `userinfo` |
| `jwks_uri` | `https://accounts.witus.online/api/idp/jwks` |
| `end_session_endpoint` | `https://accounts.witus.online/api/idp/oauth2/endsession` (present) |
| `id_token_signing_alg_values_supported` | `RS256`, `EdDSA` |
| `token_endpoint_auth_methods_supported` | `client_secret_basic`, `client_secret_post`, `none` |
| `code_challenge_methods_supported` | `S256` |
| `scopes_supported` | `openid`, `profile`, `email`, `offline_access` |
| `claims_supported` | includes `sub`, `email`, `email_verified`, `name` |

(WitUS, 2026a). The key set at `jwks_uri` holds one key: `kty` `OKP`, `crv` `Ed25519`, `alg` `EdDSA`, with a
`kid` (WitUS, 2026b). That is the whole story of the algorithm: the document lists RS256 because the standard
requires the list to include it, but there is no RSA key, so a client that defaults to RS256 fails at the
callback. The ecosystem's NextAuth apps hit exactly that and now pin EdDSA (WitUS, 2026c). This client accepts
EdDSA and refuses everything else, including `none`, which is not a signature.

The client reads the document at the standard's path first and at the provider's path second, and refuses a
document whose `issuer` is not the one configured. The default issuer in the settings is the host read that
day, labeled as such; the authoritative-values rule in `CLAUDE.md` is why the chapter copies these values from
the document instead of typing paths into the code.

**What the client must check.** Core 1.0, section 3.1.3.7: the issuer "MUST exactly match the value of the
`iss` (issuer) Claim"; the token "MUST be rejected if the ID Token does not list the Client as a valid
audience"; "The current time MUST be before the time represented by the `exp` Claim"; and "If a nonce value was
sent in the Authentication Request, a nonce Claim MUST be present" and match (Sakimura et al., 2023). The
nonce is a "String value used to associate a Client session with an ID Token, and to mitigate replay attacks"
(section 3.1.2.1). PKCE, RFC 7636, is for the code: the provider stores a hash of a secret the app made, and the
app sends the secret itself with the code, so an attacker who intercepts the code "cannot exchange it for
tokens, because they lack the code_verifier" (Sakimura et al., 2015). The S256 transform is
`BASE64URL-ENCODE(SHA256(ASCII(code_verifier)))`, and the RFC's appendix gives a worked example that the tests
use. This provider requires PKCE for every client (WitUS, 2026d), which is a good default to meet anyway.

**`sub`, never email.** Core 1.0, section 5.7: "the only guaranteed unique identifier for a given End-User is
the combination of the `iss` Claim and the `sub` Claim", and claims such as email "MUST NOT be used as unique
identifiers for the End-User" (Sakimura et al., 2023). Chapter 05 left `Account.witus_user_id` empty for
exactly this (decisions log, row 43); this chapter fills it. The one place email is read is the first sign-in,
to link the owner's existing superuser, and only when the provider says the address is verified.

**Why no framework, and why PyJWT.** The PRD and research 04 proposed Authlib's Django client. Its
`parse_id_token` takes the allowed algorithms from the discovery document's
`id_token_signing_alg_values_supported` (Authlib contributors, n.d.-a), which here lists RS256 too, so pinning
EdDSA would mean subclassing a client you did not write; its Django client page answered 404 on the day this
was written. More to the point, the flow is six steps and a learner should read all six. PyJWT does the one
part that should not be hand-written, the signature: it lists EdDSA with Ed25519 (PyJWT contributors, n.d.-b),
wants the `[crypto]` extra for it (PyJWT contributors, n.d.-c), and `jwt.decode` takes `algorithms`,
`audience`, `issuer`, `leeway` and `options={"require": [...]}` in one call, with a named exception for each
failure (PyJWT contributors, n.d.-a). Its API reference warns: "Do not compute the algorithms parameter based
on the alg from the token itself." The list is a constant in the code. Decisions log, row 62.

**Off until the owner says so.** The client is on exactly when `WITUS_OIDC_CLIENT_SECRET` is set. A copy of
the app with no secret serves the public site with chapter 04's stub page behind "Sign in", which is what your
copy does: the provider accepts first-party ecosystem apps only, registered in the witus repo, and a redirect
URI is matched exactly (WitUS, 2026c). Your checkpoint is the fake provider in the tests; exercise 2 opens the
client to a provider of your own.

## Steps

### 07.1 The tests

Listing 07-1, Filename: `tests/test_ch07.py`:

```python
"""Chapter 07 checkpoint: Sign in with WitUS against a fake provider that signs with a real
Ed25519 key, the checks a callback makes, who gets linked to whom, and the header's two states."""

import importlib
import json
import os
import re
import sys
import time
from collections.abc import Callable, Iterator
from html.parser import HTMLParser
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.test import Client
from jwt.algorithms import OKPAlgorithm
from pytest_django.fixtures import Settings

from invest_witus_site.accounts import oidc
from invest_witus_site.accounts.models import WitusIdentity
from invest_witus_site.accounts.views import SESSION_KEY
from invest_witus_site.holdings.models import Account

BASE_DIR = Path(settings.BASE_DIR)
# Not a secret: it exists only inside this test run (the same string chapter 06 uses).
TEST_KEY = "test-only-" + "0123456789" * 5
ISSUER = "https://idp.test"
CLIENT_ID = "witus-invest"
CLIENT_SECRET = "test-only-client-secret"
LOGIN, CALLBACK, LOGOUT = "/auth/witus/login/", "/auth/witus/callback/", "/auth/witus/logout/"
# The person the fake provider vouches for. The app lower-cases the email and keys on `sub`.
PERSON: dict[str, Any] = {
    "sub": "usr_0123456789abcdefghij",
    "email": "Learner@Example.com",
    "email_verified": True,
    "name": "Ada Learner",
}
OMIT = object()  # an override that removes a claim from the id token


# --- A provider small enough to read --------------------------------------------------------


class FakeIdp:
    """The ecosystem's identity provider, as far as this app can see it: a discovery document,
    a JWKS with one Ed25519 key, a token endpoint that checks the client and the PKCE verifier,
    and userinfo. `handle` is an httpx transport handler; `authorize` plays the browser's part."""

    def __init__(self, end_session: bool = True) -> None:
        self.private_key = Ed25519PrivateKey.generate()
        self.kid = "test-key-1"
        self.alg = "EdDSA"
        self.end_session = end_session
        self.discovery_at_root = False  # like the live host: the document is under /api/idp
        self.document_overrides: dict[str, Any] = {}
        self.token_overrides: dict[str, Any] = {}
        self.userinfo_overrides: dict[str, Any] = {}
        self.codes: dict[str, dict[str, str]] = {}
        self.paths: list[str] = []  # every path the app requested, in order

    @property
    def base(self) -> str:
        return f"{ISSUER}/api/idp"

    def document(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "issuer": ISSUER,
            "authorization_endpoint": f"{self.base}/oauth2/authorize",
            "token_endpoint": f"{self.base}/oauth2/token",
            "userinfo_endpoint": f"{self.base}/oauth2/userinfo",
            "jwks_uri": f"{self.base}/jwks",
            "id_token_signing_alg_values_supported": ["RS256", "EdDSA"],
            "code_challenge_methods_supported": ["S256"],
        }
        if self.end_session:
            document["end_session_endpoint"] = f"{self.base}/oauth2/endsession"
        return document | self.document_overrides

    def jwks(self) -> dict[str, Any]:
        public = OKPAlgorithm.to_jwk(self.private_key.public_key(), as_dict=True)
        return {"keys": [public | {"kid": "test-key-1", "alg": "EdDSA"}]}

    def authorize(self, location: str) -> str:
        """The browser's trip to the provider: read the authorize URL the app sent it to, keep what
        the provider would keep, and come back to the callback with a code and the state."""
        url = urlsplit(location)
        assert f"{url.scheme}://{url.netloc}{url.path}" == f"{self.base}/oauth2/authorize"
        query = {key: values[0] for key, values in parse_qs(url.query).items()}
        assert query["response_type"] == "code" and query["client_id"] == CLIENT_ID
        assert query["code_challenge_method"] == "S256"
        code = f"code-{len(self.codes) + 1}"
        self.codes[code] = {
            "challenge": query["code_challenge"],
            "nonce": query["nonce"],
            "redirect_uri": query["redirect_uri"],
        }
        return f"{CALLBACK}?code={code}&state={query['state']}"

    def id_token(self, nonce: str) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "iss": ISSUER,
            "aud": CLIENT_ID,
            "iat": now,
            "exp": now + 3600,
            "nonce": nonce,
            **PERSON,
            **self.token_overrides,
        }
        claims = {key: value for key, value in claims.items() if value is not OMIT}
        if self.alg == "EdDSA":
            return jwt.encode(
                claims, self.private_key, algorithm="EdDSA", headers={"kid": self.kid}
            )
        # A token with another `alg` and no real signature: the client must refuse it on the
        # header alone, before it looks for a key.
        header = {"alg": self.alg, "typ": "JWT", "kid": self.kid}
        signature = b"" if self.alg == "none" else b"not-a-signature"
        parts = (json.dumps(header).encode(), json.dumps(claims).encode(), signature)
        return ".".join(oidc.b64url(part) for part in parts)

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.paths.append(path)
        if path == "/.well-known/openid-configuration":
            if not self.discovery_at_root:
                return httpx.Response(404, text="not here")
            return httpx.Response(200, json=self.document())
        if path == "/api/idp/.well-known/openid-configuration":
            return httpx.Response(200, json=self.document())
        if path == "/api/idp/jwks":
            return httpx.Response(200, json=self.jwks())
        if path == "/api/idp/oauth2/token":
            return self.token(request)
        if path == "/api/idp/oauth2/userinfo":
            if request.headers.get("Authorization", "").removeprefix("Bearer ") not in self.codes:
                return httpx.Response(401, json={"error": "invalid_token"})
            return httpx.Response(200, json=PERSON | self.userinfo_overrides)
        return httpx.Response(404, text="no such route")

    def token(self, request: httpx.Request) -> httpx.Response:
        form = {key: values[0] for key, values in parse_qs(request.content.decode()).items()}
        if request.method != "POST" or form.get("grant_type") != "authorization_code":
            return httpx.Response(400, json={"error": "unsupported_grant_type"})
        if form.get("client_id") != CLIENT_ID or form.get("client_secret") != CLIENT_SECRET:
            return httpx.Response(401, json={"error": "invalid_client"})
        issued = self.codes.get(form.get("code", ""))
        if issued is None or form.get("redirect_uri") != issued["redirect_uri"]:
            return httpx.Response(400, json={"error": "invalid_grant"})
        if oidc.code_challenge(form.get("code_verifier", "")) != issued["challenge"]:
            return httpx.Response(400, json={"error": "invalid_grant", "pkce": "verifier"})
        body = {
            "access_token": form["code"],  # so userinfo can tell the sign-in it belongs to
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "openid email profile",
            "id_token": self.id_token(issued["nonce"]),
        }
        return httpx.Response(200, json=body)


@pytest.fixture
def idp(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> Iterator[FakeIdp]:
    """The client switched on and pointed at the fake provider, with empty caches."""
    provider = FakeIdp()
    monkeypatch.setattr(oidc, "transport", httpx.MockTransport(provider.handle))
    settings.WITUS_OIDC_ISSUER = ISSUER
    settings.WITUS_OIDC_CLIENT_ID = CLIENT_ID
    settings.WITUS_OIDC_CLIENT_SECRET = CLIENT_SECRET
    oidc.clear_caches()
    yield provider
    oidc.clear_caches()


def sign_in(client: Client, provider: FakeIdp) -> Any:
    """The whole trip: out to the provider, back to the callback. Returns the callback response."""
    out = client.get(LOGIN)
    assert out.status_code == 302, out.status_code
    return client.get(provider.authorize(out["Location"]))


class ControlCollector(HTMLParser):
    """(kind, href or action, accessible name) for every link and submit button in a page."""

    def __init__(self) -> None:
        super().__init__()
        self.controls: list[tuple[str, str, str]] = []
        self._open: tuple[str, str] | None = None
        self._text: list[str] = []
        self._action = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "form":
            self._action = a.get("action") or ""
        if tag == "a":
            self._open, self._text = ("link", a.get("href") or ""), []
        if tag == "button" and (a.get("type") or "submit") == "submit":
            self._open, self._text = ("button", self._action), []

    def handle_data(self, data: str) -> None:
        if self._open is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("a", "button") and self._open is not None:
            kind, target = self._open
            self.controls.append((kind, target, " ".join("".join(self._text).split())))
            self._open = None


def element(html: str, tag: str) -> str:
    """The first <tag>...</tag> block of the page, as text (chapter 04's helper)."""
    match = re.search(rf"<{tag}\b.*?</{tag}>", html, re.DOTALL)
    assert match, f"no <{tag}> on the page"
    return match.group(0)


def controls_in(html: str, tag: str) -> list[tuple[str, str, str]]:
    collector = ControlCollector()
    collector.feed(element(html, tag))
    return collector.controls


SIGN_IN = ("link", LOGIN, "Sign in")
SIGN_OUT = ("button", LOGOUT, "Sign out")


def fresh_settings(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> ModuleType:
    """Chapter 06's helper, with the WitUS names added to the ones it clears."""
    for name in list(os.environ):
        if name.startswith(("DJANGO_", "VERCEL", "DATABASE_URL", "WITUS_")):
            monkeypatch.delenv(name)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delitem(sys.modules, "invest_witus_site.settings")
    return importlib.import_module("invest_witus_site.settings")


# --- The settings and the switch ------------------------------------------------------------


def test_the_client_is_off_without_a_secret_and_the_defaults_are_the_ecosystems(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = fresh_settings(monkeypatch, {"DJANGO_SECRET_KEY": TEST_KEY})
    assert server.WITUS_OIDC_CLIENT_SECRET == ""
    assert server.WITUS_OIDC_ISSUER == "https://accounts.witus.online"
    assert server.WITUS_OIDC_CLIENT_ID == "witus-invest"
    assert server.WITUS_OIDC_SCOPES == "openid email profile"
    assert server.LOGIN_URL == "sign-in"
    assert "invest_witus_site.accounts" in server.INSTALLED_APPS


def test_the_four_names_are_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "DJANGO_SECRET_KEY": TEST_KEY,
        "WITUS_OIDC_ISSUER": "https://idp.example/",
        "WITUS_OIDC_CLIENT_ID": "witus-example",
        "WITUS_OIDC_CLIENT_SECRET": "s",
        "WITUS_OIDC_SCOPES": "openid email",
    }
    server = fresh_settings(monkeypatch, env)
    assert server.WITUS_OIDC_ISSUER == "https://idp.example", "the trailing slash is dropped"
    assert server.WITUS_OIDC_CLIENT_ID == "witus-example"
    assert server.WITUS_OIDC_CLIENT_SECRET == "s"
    assert server.WITUS_OIDC_SCOPES == "openid email"


@pytest.mark.parametrize(
    "name, value",
    [("WITUS_OIDC_ISSUER", "http://idp.example"), ("WITUS_OIDC_SCOPES", "email profile")],
)
def test_a_plain_http_issuer_or_scopes_without_openid_are_refused(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    with pytest.raises(ImproperlyConfigured, match=name):
        fresh_settings(monkeypatch, {"DJANGO_SECRET_KEY": TEST_KEY, name: value})


def test_with_the_client_off_the_sign_in_route_is_the_stub_and_the_smoke_test_holds(
    client: Client,
) -> None:
    assert oidc.config().enabled is False, "this suite runs with no secret set"
    html = client.get(LOGIN).content.decode()
    assert "chapter 07" in html and "not switched on" in html
    assert client.get(CALLBACK + "?code=x&state=y").status_code == 200, "the stub, not an error"
    for path in ["/", "/faq/", LOGIN]:
        assert SIGN_IN in controls_in(client.get(path).content.decode(), "header")


# --- Out to the provider --------------------------------------------------------------------


@pytest.mark.django_db
def test_login_redirects_to_the_provider_with_pkce_state_and_nonce(
    client: Client, idp: FakeIdp
) -> None:
    response = client.get(LOGIN)
    assert response.status_code == 302
    url = urlsplit(response["Location"])
    assert f"{url.scheme}://{url.netloc}{url.path}" == f"{idp.base}/oauth2/authorize"
    query = {key: values[0] for key, values in parse_qs(url.query).items()}
    flight = client.session[SESSION_KEY]
    assert query["response_type"] == "code"
    assert query["client_id"] == CLIENT_ID
    assert query["redirect_uri"] == f"http://testserver{CALLBACK}" == flight["redirect_uri"]
    assert query["scope"] == "openid email profile"
    assert query["state"] == flight["state"] and len(flight["state"]) >= 32
    assert query["nonce"] == flight["nonce"] and len(flight["nonce"]) >= 32
    assert query["code_challenge_method"] == "S256"
    assert query["code_challenge"] == oidc.code_challenge(flight["verifier"])
    assert 43 <= len(flight["verifier"]) <= 128, "RFC 7636's length rule"
    assert "code_verifier" not in url.query and flight["verifier"] not in url.query


@pytest.mark.django_db
def test_discovery_falls_back_to_the_api_idp_path_and_is_cached(
    client: Client, idp: FakeIdp
) -> None:
    client.get(LOGIN)
    client.get(LOGIN)
    assert idp.paths == [
        "/.well-known/openid-configuration",
        "/api/idp/.well-known/openid-configuration",
    ], "the spec's path first, then better-auth's, and only once for two sign-ins"
    oidc.clear_caches()
    idp.discovery_at_root = True
    client.get(LOGIN)
    assert idp.paths[2:] == ["/.well-known/openid-configuration"]


@pytest.mark.django_db
def test_a_discovery_document_with_another_issuer_is_refused(client: Client, idp: FakeIdp) -> None:
    idp.document_overrides = {"issuer": "https://someone-else.test"}
    response = client.get(LOGIN)
    assert response.status_code == 503
    assert "did not complete" in response.content.decode()


@pytest.mark.django_db
def test_a_signed_in_visitor_is_sent_home_from_login(client: Client, idp: FakeIdp) -> None:
    sign_in(client, idp)
    response = client.get(LOGIN)
    assert response.status_code == 302 and response["Location"] == "/"


# --- Back from the provider: the refusals ---------------------------------------------------


@pytest.mark.django_db
def test_callback_rejects_a_bad_state_and_a_missing_session(client: Client, idp: FakeIdp) -> None:
    assert client.get(CALLBACK + "?code=x&state=never-issued").status_code == 400
    out = client.get(LOGIN)
    callback = idp.authorize(out["Location"])
    wrong = client.get(callback.replace("state=", "state=x"))
    assert wrong.status_code == 400 and "<code>state</code>" in wrong.content.decode()
    assert "/oauth2/token" not in "".join(idp.paths), "no code was exchanged"
    assert SESSION_KEY not in client.session, "the attempt was consumed"
    assert client.get("/").wsgi_request.user.is_anonymous


@pytest.mark.django_db
def test_callback_relays_the_providers_error(client: Client, idp: FakeIdp) -> None:
    out = client.get(LOGIN)
    state = client.session[SESSION_KEY]["state"]
    response = client.get(f"{CALLBACK}?error=access_denied&state={state}")
    assert response.status_code == 400 and "access_denied" in response.content.decode()
    assert out.status_code == 302 and "/oauth2/token" not in "".join(idp.paths)


@pytest.mark.django_db
def test_callback_cannot_be_replayed(client: Client, idp: FakeIdp) -> None:
    out = client.get(LOGIN)
    callback = idp.authorize(out["Location"])
    assert client.get(callback).status_code == 302
    assert client.get(callback).status_code == 400
    assert idp.paths.count("/api/idp/oauth2/token") == 1


@pytest.mark.parametrize(
    "change, reason",
    [
        ({"aud": "witus-someone-else"}, "a wrong aud"),
        ({"iss": "https://someone-else.test"}, "a wrong iss"),
        ({"exp": int(time.time()) - 3600}, "an expired token"),
        ({"nonce": "not-the-one-this-browser-sent"}, "a nonce mismatch"),
        ({"nonce": OMIT}, "a missing nonce"),
        ({"sub": OMIT}, "a missing sub"),
    ],
)
@pytest.mark.django_db
def test_callback_rejects_a_bad_id_token(
    client: Client, idp: FakeIdp, change: dict[str, Any], reason: str
) -> None:
    idp.token_overrides = change
    response = sign_in(client, idp)
    assert response.status_code == 400, reason
    assert "<code>refused</code>" in response.content.decode()
    assert WitusIdentity.objects.count() == 0 and User.objects.count() == 0
    assert client.get("/").wsgi_request.user.is_anonymous


@pytest.mark.parametrize("alg", ["RS256", "none"])
@pytest.mark.django_db
def test_callback_rejects_a_token_that_is_not_eddsa(client: Client, idp: FakeIdp, alg: str) -> None:
    idp.alg = alg
    assert sign_in(client, idp).status_code == 400
    assert "/api/idp/jwks" not in idp.paths, "refused on the header, before any key was fetched"
    assert User.objects.count() == 0


@pytest.mark.django_db
def test_an_unknown_kid_costs_one_jwks_fetch_and_fails(client: Client, idp: FakeIdp) -> None:
    client.get(LOGIN)  # warms the discovery cache; the JWKS is fetched only when a token arrives
    idp.kid = "retired-key"
    assert sign_in(client, idp).status_code == 400
    assert idp.paths.count("/api/idp/jwks") == 1


@pytest.mark.django_db
def test_a_userinfo_sub_that_differs_is_refused(client: Client, idp: FakeIdp) -> None:
    idp.token_overrides = {"email": OMIT, "name": OMIT}
    idp.userinfo_overrides = {"sub": "usr_someone_else"}
    assert sign_in(client, idp).status_code == 400
    assert "/api/idp/oauth2/userinfo" in idp.paths and User.objects.count() == 0


# --- Back from the provider: the welcome ----------------------------------------------------


@pytest.mark.django_db
def test_a_good_callback_creates_the_identity_and_signs_the_person_in(
    client: Client, idp: FakeIdp
) -> None:
    response = sign_in(client, idp)
    assert response.status_code == 302 and response["Location"] == "/"
    identity = WitusIdentity.objects.get()
    assert identity.sub == PERSON["sub"]
    assert identity.email == "learner@example.com" and identity.name == "Ada Learner"
    assert identity.last_login_at is not None
    user = identity.user
    assert user.username == f"witus-{PERSON['sub']}" and user.email == "learner@example.com"
    assert not user.is_staff and not user.is_superuser and not user.has_usable_password()
    assert SESSION_KEY not in client.session, "the attempt was consumed"
    home = client.get("/")
    assert home.wsgi_request.user == user
    html = home.content.decode()
    assert "Signed in as Ada Learner." in html
    assert "Open the admin" not in html, "the admin link is for staff only"
    assert SIGN_OUT in controls_in(html, "header") and SIGN_IN not in controls_in(html, "header")
    assert "Ada Learner" in element(html, "header"), "the name sits in the header"


@pytest.mark.django_db
def test_a_second_sign_in_matches_by_sub_and_never_by_email(client: Client, idp: FakeIdp) -> None:
    sign_in(client, idp)
    first = WitusIdentity.objects.get()
    client.post(LOGOUT)
    idp.token_overrides = {"email": "New.Address@Example.com", "name": "Ada L."}
    assert sign_in(client, idp).status_code == 302
    identity = WitusIdentity.objects.get()
    assert identity.pk == first.pk and identity.user == first.user
    assert identity.email == "new.address@example.com" and identity.name == "Ada L."
    assert identity.last_login_at > first.last_login_at
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_the_id_token_without_an_email_is_completed_from_userinfo(
    client: Client, idp: FakeIdp
) -> None:
    idp.token_overrides = {"email": OMIT, "name": OMIT}
    assert sign_in(client, idp).status_code == 302
    assert "/api/idp/oauth2/userinfo" in idp.paths
    identity = WitusIdentity.objects.get()
    assert identity.email == "learner@example.com" and identity.name == "Ada Learner"


@pytest.mark.django_db
def test_the_owners_superuser_links_by_verified_email(client: Client, idp: FakeIdp) -> None:
    owner = User.objects.create_superuser("owner", "LEARNER@example.com", "a-password-for-tests")
    account = Account.objects.create(
        owner=owner, name="Brokerage", broker="Example", kind=Account.Kind.BROKERAGE
    )
    assert account.witus_user_id is None
    assert sign_in(client, idp).status_code == 302
    identity = WitusIdentity.objects.get()
    assert identity.user == owner, "matched by the verified email, once"
    assert User.objects.count() == 1, "no second user was made"
    account.refresh_from_db()
    assert account.witus_user_id == PERSON["sub"], "the owner's accounts now name the person"
    html = client.get("/").content.decode()
    assert "Signed in as Ada Learner." in html and 'href="/admin/">Open the admin</a>' in html
    assert SIGN_OUT in controls_in(html, "header")


@pytest.mark.django_db
def test_an_unverified_email_never_links_an_existing_user(client: Client, idp: FakeIdp) -> None:
    owner = User.objects.create_superuser("owner", "learner@example.com", "a-password-for-tests")
    idp.token_overrides = {"email_verified": False}
    assert sign_in(client, idp).status_code == 302
    identity = WitusIdentity.objects.get()
    assert identity.user != owner and not identity.user.is_staff
    assert User.objects.count() == 2
    assert not WitusIdentity.objects.filter(user=owner).exists()


@pytest.mark.django_db
def test_the_owner_signed_in_at_the_admin_sees_sign_out_and_the_admin_link(
    admin_client: Client,
) -> None:
    """A password login at /admin/ is still a login: the header reads "Sign out" for it too, and
    with no WitUS identity yet the name shown is the username."""
    html = admin_client.get("/").content.decode()
    assert SIGN_OUT in controls_in(html, "header")
    assert "Signed in as admin." in html and "Open the admin" in html


# --- Out of the app -------------------------------------------------------------------------


@pytest.mark.django_db
def test_logout_clears_the_session_and_sends_the_browser_to_the_provider(
    client: Client, idp: FakeIdp
) -> None:
    sign_in(client, idp)
    response = client.post(LOGOUT)
    assert response.status_code == 302
    url = urlsplit(response["Location"])
    assert f"{url.scheme}://{url.netloc}{url.path}" == f"{idp.base}/oauth2/endsession"
    query = {key: values[0] for key, values in parse_qs(url.query).items()}
    assert query == {"client_id": CLIENT_ID, "post_logout_redirect_uri": "http://testserver/"}
    assert client.get("/").wsgi_request.user.is_anonymous
    assert SIGN_IN in controls_in(client.get("/").content.decode(), "header")


@pytest.mark.django_db
def test_logout_goes_home_when_the_provider_has_no_end_session_endpoint(
    client: Client, idp: FakeIdp
) -> None:
    idp.end_session = False
    sign_in(client, idp)
    response = client.post(LOGOUT)
    assert response.status_code == 302 and response["Location"] == "/"
    assert client.get("/").wsgi_request.user.is_anonymous


@pytest.mark.django_db
def test_logout_is_a_post_and_goes_home_with_the_client_off(
    client: Client, admin_client: Client
) -> None:
    assert client.get(LOGOUT).status_code == 405
    response = admin_client.post(LOGOUT)
    assert response.status_code == 302 and response["Location"] == "/"
    assert admin_client.get("/").wsgi_request.user.is_anonymous


# --- The pieces on their own ----------------------------------------------------------------


def test_code_challenge_is_s256_of_the_verifier() -> None:
    """RFC 7636 appendix B's worked example."""
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    assert oidc.code_challenge(verifier) == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


def test_claims_take_the_email_lower_cased_and_the_name_trimmed() -> None:
    never: Callable[[], dict[str, Any]] = lambda: pytest.fail("userinfo was not needed")  # noqa: E731
    claims = oidc.claims_for({"sub": "s", "email": " A@B.test ", "name": " Ada "}, never)
    assert claims == oidc.Claims(sub="s", email="a@b.test", email_verified=False, name="Ada")
    with pytest.raises(oidc.OidcError, match="no email"):
        oidc.claims_for({"sub": "s"}, lambda: {"sub": "s"})


def test_env_example_names_the_four_variables() -> None:
    text = (BASE_DIR / ".env.example").read_text(encoding="utf-8")
    for name in ("WITUS_OIDC_ISSUER", "WITUS_OIDC_CLIENT_ID", "WITUS_OIDC_CLIENT_SECRET"):
        assert f"\n{name}=\n" in text
    assert "\nWITUS_OIDC_SCOPES=\n" in text
    assert "https://accounts.witus.online" in text and "witus-invest" in text
```

Things to notice:

- **`FakeIdp` is a provider small enough to read.** It makes a real Ed25519 key, publishes it as a JWK with a
  `kid`, serves the discovery document under `/api/idp/` and a 404 at the standard's path (like the live host),
  checks the client id and secret and the PKCE verifier at its token endpoint, signs a real id token with the
  nonce it was sent, and answers userinfo. `handle` is an `httpx.MockTransport` handler: a function from a
  request to a response (Encode, n.d.). `authorize` plays the browser's part of the trip.
- **The overrides are the test cases.** `token_overrides` changes one claim (`aud`, `iss`, `exp`, `nonce`) or
  removes one (`OMIT`); `alg` makes a token that is not EdDSA; `kid` names a key the JWKS does not have;
  `end_session` and `discovery_at_root` change the document. Each refusal is one line of setup and one assert.
- **`sign_in` is the whole trip in three lines,** and every test of the callback goes through it, so the
  tests cannot pass by calling the callback with a shape the login never produces.
- **`ControlCollector` names buttons the way `LinkCollector` named links in chapter 04:** by their text. "Sign
  out" is a button in a form, so a link collector would miss it.
- **`fresh_settings`** is chapter 06's helper with `WITUS_` added to the names it clears.
- **The `settings` fixture** (pytest-django, n.d.) switches the client on for one test; the views read the
  settings when a request arrives, which is why that works.
- **The RFC's worked example** is a test of eight lines of code. When a test can be a published vector, it
  should be.

Add the two packages first (07.2), then run it:

Listing 07-2, Terminal:

```sh
uv run pytest tests/test_ch07.py
```

```text
tests/test_ch07.py:28: in <module>
    from invest_witus_site.accounts import oidc
E   ModuleNotFoundError: No module named 'invest_witus_site.accounts'
=========================== short test summary info ============================
ERROR tests/test_ch07.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.55s
```

Red first, at import: the app the tests describe does not exist.

### 07.2 Two packages and four names

Listing 07-3, Terminal:

```sh
uv add httpx "pyjwt[crypto]"
```

`httpx` makes the HTTP calls. `pyjwt[crypto]` is PyJWT with the `cryptography` library, which EdDSA needs; the
installation page recommends writing the extra this way so that a separate `cryptography` line is not "later
mistaken for an unused requirement and removed" (PyJWT contributors, n.d.-c). No test library is added: the
fake provider is plain httpx.

Listing 07-4, Filename: `pyproject.toml`:

```toml
[project]
name = "invest-witus"
version = "0.1.0"
description = "Learn to invest by following one taught method, on paper first."
readme = "README.md"
requires-python = ">=3.14"
dependencies = [
    "django>=5.2,<6",
    "django-stubs-ext>=6.1",
    "httpx>=0.28.1",
    "markdown>=3.11",
    "psycopg[binary]>=3.2",
    "pyjwt[crypto]>=2.15.1",
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
# tests/settings.py: the real settings plus a test-only secret key (chapter 06).
DJANGO_SETTINGS_MODULE = "tests.settings"
markers = ["smoke: the checks that must pass on every deploy, such as the header Sign in link"]

[tool.ruff]
line-length = 100

[tool.ruff.lint]
# E/F: errors, I: import order, UP: modern Python syntax, B: likely bugs
select = ["E", "F", "I", "UP", "B"]

[tool.pyright]
include = ["src", "tests", "scripts", "manage.py", "wsgi.py"]
typeCheckingMode = "strict"
```

The settings gain the four names at the end, the app in `INSTALLED_APPS`, one context processor, and
`LOGIN_URL`. Everything else is chapter 06's.

Listing 07-5, Filename: `src/invest_witus_site/settings.py`:

```python
"""Django settings for Invest.WitUS.

Anything that differs between your laptop and a server comes from an environment variable, with a
safe default for the laptop. The names are listed in `.env.example`; values never go in git.
Chapter 06 added the server's side: the database from `DATABASE_URL`, a secret key the server
must set, the HTTPS cookie and proxy settings, the folder `collectstatic` fills, and logging a
server can show. Chapter 07 added the four names of Sign in with WitUS, at the end.
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
```

- **`WITUS_OIDC_CLIENT_SECRET` is the switch.** Empty means off. There is no second flag to forget.
- **`WITUS_OIDC_ISSUER`** defaults to the host read on October 28, 2026, with the trailing slash dropped, and
  must be `https://`. The client compares it with the discovery document's own `issuer`, so a wrong value fails
  at the first sign-in with a message, not with a token from the wrong place.
- **`WITUS_OIDC_CLIENT_ID`** defaults to `witus-invest`, the registry's `witus-<slug>` form. **`WITUS_OIDC_SCOPES`**
  must include `openid`, or there is no id token to verify.
- **`LOGIN_URL = "sign-in"`.** The setting "accepts view function names and named URL patterns" (Django Software
  Foundation, n.d.-a), so when a later chapter puts a page behind `login_required`, the visitor lands on the
  WitUS sign-in, not on `/accounts/login/`.

### 07.3 The accounts app: who signed in

Listing 07-6, Filename: `src/invest_witus_site/accounts/apps.py`:

```python
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "invest_witus_site.accounts"
    verbose_name = "Sign in with WitUS"
```

Listing 07-7, Filename: `src/invest_witus_site/accounts/models.py`:

```python
"""Who signed in with WitUS: one row per WitUS user, keyed by the provider's `sub` and tied to
one Django user.

Chapter 05 decided against a custom user model (decisions log, row 43), so the WitUS id lives in
this one-to-one table beside `auth.User`, and `Account.witus_user_id` is filled from it so the
owner's accounts name the person who signs in. The email is kept for contact; it is never what a
person is matched by after their first sign-in.
"""

from datetime import datetime

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from invest_witus_site.accounts.oidc import Claims
from invest_witus_site.holdings.models import Account


class WitusIdentity(models.Model):
    user: models.OneToOneField[User, User] = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="witus_identity"
    )
    sub: models.CharField[str, str] = models.CharField(
        max_length=64, unique=True, help_text="The WitUS user id (the `sub` claim). Never an email."
    )
    email: models.EmailField[str, str] = models.EmailField(max_length=254, blank=True)
    name: models.CharField[str, str] = models.CharField(max_length=150, blank=True)
    last_login_at: models.DateTimeField[datetime, datetime] = models.DateTimeField()
    created_at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "WitUS identity"
        verbose_name_plural = "WitUS identities"

    def __str__(self) -> str:
        return self.display_name or self.sub

    @property
    def display_name(self) -> str:
        return self.name or self.email

    @classmethod
    def sign_in(cls, claims: Claims) -> WitusIdentity:
        """Find the person by `sub`; or link them to a user the owner made (by verified email);
        or make a new ordinary user. Then record the visit and stamp their accounts."""
        identity = cls.objects.filter(sub=claims.sub).select_related("user").first()
        if identity is None:
            user = cls.existing_user(claims) or cls.new_user(claims)
            identity = cls(user=user, sub=claims.sub)
        identity.email = claims.email
        identity.name = claims.name
        identity.last_login_at = timezone.now()
        identity.save()
        Account.objects.filter(owner=identity.user).exclude(witus_user_id=claims.sub).update(
            witus_user_id=claims.sub
        )
        return identity

    @staticmethod
    def existing_user(claims: Claims) -> User | None:
        """The owner's superuser (chapter 05) links on its first sign-in by email, and only when
        the provider says the address is verified. Any user without a WitUS identity qualifies:
        the only way such a user exists is that the owner made it, with `createsuperuser` or in
        the admin. Exactly one match, or none."""
        if not claims.email_verified:
            return None
        matches = list(
            User.objects.filter(email__iexact=claims.email, witus_identity__isnull=True)[:2]
        )
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def new_user(claims: Claims) -> User:
        """An ordinary user: not staff, no password (`create_user` with none sets an unusable
        one), a username built from the `sub` so that it is unique and never an email."""
        return User.objects.create_user(username=f"witus-{claims.sub}"[:150], email=claims.email)
```

- **One table, one-to-one with `auth.User`.** `sub` is unique and is the key; `email` and `name` are a copy of
  what the provider said last time, for display and contact; `last_login_at` is written on every sign-in.
  Chapter 05 chose not to swap the user model after a production database existed (row 43), and this is the
  profile it promised instead.
- **`sign_in` is the linking rule, in order.** By `sub` first. Then, only when the provider says the email is
  verified, the one existing user without an identity whose email matches: that is how the owner's superuser
  from chapter 05 links on its first sign-in, and the only way an identity-less user exists is that the owner
  made it, with `createsuperuser` or in the admin. Otherwise a new ordinary user: not staff, no password
  (`create_user` with none sets an unusable one), a username built from the `sub` so it is unique and never an
  email. After the first sign-in, email is not consulted again; a changed address updates the row and matches
  nothing.
- **`Account.witus_user_id` is set on every sign-in,** for every account the user owns. The owner's accounts
  from chapter 05 carry the WitUS id after the first sign-in without anyone typing it.

Make the migration and read it:

Listing 07-8, Terminal:

```sh
uv run --env-file .env python manage.py makemigrations accounts
uv run ruff format src/invest_witus_site/accounts/migrations/
```

Listing 07-9, Filename: `src/invest_witus_site/accounts/migrations/0001_initial.py`:

```python
# Generated by Django 5.2.18 on 2026-10-28 21:10

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WitusIdentity",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "sub",
                    models.CharField(
                        help_text="The WitUS user id (the `sub` claim). Never an email.",
                        max_length=64,
                        unique=True,
                    ),
                ),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("name", models.CharField(blank=True, max_length=150)),
                ("last_login_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="witus_identity",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "WitUS identity",
                "verbose_name_plural": "WitUS identities",
            },
        ),
    ]
```

Listing 07-10, Filename: `src/invest_witus_site/accounts/admin.py`:

```python
"""WitUS identities in the admin: who has signed in, with which WitUS id, and when. Rows come
only from sign-ins. The owner may re-point one at another user (a stray row made before the
superuser's email matched, say) but never edits the `sub`."""

from django.contrib import admin
from django.http import HttpRequest

from invest_witus_site.accounts.models import WitusIdentity


@admin.register(WitusIdentity)
class WitusIdentityAdmin(admin.ModelAdmin[WitusIdentity]):
    list_display = ("sub", "user", "email", "name", "last_login_at")
    search_fields = ("sub", "email", "name", "user__username")
    readonly_fields = ("sub", "email", "name", "last_login_at", "created_at")
    raw_id_fields = ("user",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False
```

Rows are made by sign-ins, so the admin cannot add one. It can change `user`: if the owner's first sign-in made
a stray `witus-<sub>` user because the emails did not match, the owner points the identity at the superuser here
and deletes the stray.

### 07.4 The client

Listing 07-11, Filename: `src/invest_witus_site/accounts/oidc.py`:

```python
"""The OpenID Connect client behind Sign in with WitUS, written out rather than installed.

Three HTTP calls with httpx (the discovery document, the token exchange, userinfo), one signature
check with PyJWT, and the small pieces around them: PKCE, `state` and `nonce`, a cached discovery
document and a cache of signing keys by `kid`. The views in `views.py` call these functions in
order; the tests in `tests/test_ch07.py` run them against a fake provider through `transport`.

The provider, as read on October 28, 2026: better-auth's OIDC provider on the ecosystem's accounts
host. Its JWKS holds one Ed25519 key, so id tokens carry `alg: EdDSA`. Its discovery document also
lists RS256, but no RSA key exists, so this client accepts EdDSA and nothing else.
"""

import base64
import hashlib
import logging
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast
from urllib.parse import urlencode

import httpx
import jwt
from django.conf import settings

log = logging.getLogger(__name__)

# Where the provider's discovery document may be, tried in order. The first is the path OpenID
# Connect Discovery defines under the issuer. The second is where better-auth serves it when the
# provider is mounted at `/api/idp`, as it is on accounts.witus.online, where the first path
# answered 404 on October 28, 2026. Whichever answers, its `issuer` must equal ours.
DISCOVERY_PATHS = (
    "/.well-known/openid-configuration",
    "/api/idp/.well-known/openid-configuration",
)
# The only id-token signature this client accepts. RS256 is in the provider's discovery document
# but no RSA key exists, and `none` is not a signature.
ALLOWED_ALGORITHMS = ("EdDSA",)
DISCOVERY_TTL_SECONDS = 60 * 60
CLOCK_LEEWAY_SECONDS = 60
TIMEOUT_SECONDS = 10.0

# The seam the tests use: an `httpx.MockTransport` that plays the provider. None means the network.
transport: httpx.BaseTransport | None = None


class OidcError(Exception):
    """Anything that stops a sign-in. The message is for the log; the visitor sees a plain page."""


@dataclass(frozen=True, slots=True)
class Config:
    """The four settings, read when a request arrives rather than at import, so a test can change
    them and so the client is on exactly when the secret is set."""

    issuer: str
    client_id: str
    client_secret: str
    scopes: str

    @property
    def enabled(self) -> bool:
        return bool(self.client_secret)


def config() -> Config:
    return Config(
        issuer=settings.WITUS_OIDC_ISSUER,
        client_id=settings.WITUS_OIDC_CLIENT_ID,
        client_secret=settings.WITUS_OIDC_CLIENT_SECRET,
        scopes=settings.WITUS_OIDC_SCOPES,
    )


@dataclass(frozen=True, slots=True)
class Provider:
    """What discovery said: the endpoints this client uses, and the issuer tokens must name."""

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    jwks_uri: str
    end_session_endpoint: str | None

    @classmethod
    def from_document(cls, document: dict[str, Any], expected_issuer: str) -> Provider:
        issuer = document.get("issuer")
        if issuer != expected_issuer:
            raise OidcError(f"discovery issuer {issuer!r} is not {expected_issuer!r}")
        end_session = document.get("end_session_endpoint")
        try:
            return cls(
                issuer=expected_issuer,
                authorization_endpoint=str(document["authorization_endpoint"]),
                token_endpoint=str(document["token_endpoint"]),
                userinfo_endpoint=str(document["userinfo_endpoint"]),
                jwks_uri=str(document["jwks_uri"]),
                end_session_endpoint=str(end_session) if end_session else None,
            )
        except KeyError as missing:
            raise OidcError(f"discovery document has no {missing}") from missing


@dataclass(frozen=True, slots=True)
class Flight:
    """One sign-in in progress: what the session keeps between the redirect out and the callback.
    `state` ties the callback to this browser, `nonce` ties the id token to it, `verifier` proves
    to the provider that the process exchanging the code is the one that started the sign-in."""

    state: str
    nonce: str
    verifier: str
    redirect_uri: str


def flight_from_session(stored: object) -> Flight | None:
    """The sign-in the session remembers, or None when there is none or it is not the shape
    `begin` stored. Session data is ours, but it is still data: read it, do not unpack it."""
    if not isinstance(stored, dict):
        return None
    data = cast(dict[str, object], stored)
    fields = [data.get(name) for name in ("state", "nonce", "verifier", "redirect_uri")]
    strings = [field for field in fields if isinstance(field, str) and field]
    if len(strings) != len(fields):
        return None
    return Flight(*strings)


@dataclass(frozen=True, slots=True)
class Claims:
    """The person, as the provider vouches for them. `sub` is the identifier; the email is for
    contact and, once, for linking the owner's existing user (`models.py`)."""

    sub: str
    email: str
    email_verified: bool
    name: str


def http() -> httpx.Client:
    return httpx.Client(
        transport=transport, timeout=TIMEOUT_SECONDS, headers={"Accept": "application/json"}
    )


def json_body(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError as error:
        raise OidcError(f"{response.url} did not answer JSON") from error
    if not isinstance(body, dict):
        raise OidcError(f"{response.url} did not answer a JSON object")
    return cast(dict[str, Any], body)


# --- Discovery and keys, cached in the process ----------------------------------------------

_provider: tuple[float, Provider] | None = None
_keys: dict[str, jwt.PyJWK] = {}


def clear_caches() -> None:
    global _provider
    _provider = None
    _keys.clear()


def provider(cfg: Config) -> Provider:
    """The discovery document, fetched at most once an hour per process."""
    global _provider
    now = time.monotonic()
    if (
        _provider is not None
        and _provider[1].issuer == cfg.issuer
        and now - _provider[0] < DISCOVERY_TTL_SECONDS
    ):
        return _provider[1]
    found = fetch_provider(cfg)
    _provider = (now, found)
    return found


def fetch_provider(cfg: Config) -> Provider:
    with http() as client:
        for path in DISCOVERY_PATHS:
            try:
                response = client.get(cfg.issuer + path)
            except httpx.HTTPError as error:
                raise OidcError(f"discovery failed: {type(error).__name__}") from error
            if response.status_code == 200:
                return Provider.from_document(json_body(response), cfg.issuer)
    raise OidcError(f"no discovery document under {cfg.issuer}")


def signing_key(prov: Provider, kid: str) -> jwt.PyJWK:
    """The provider's public key named `kid`, from the cache or from a fresh JWKS. One refetch per
    call: a token that names an unknown key costs one request, then fails."""
    if kid not in _keys:
        _keys.clear()
        _keys.update(fetch_keys(prov))
    try:
        return _keys[kid]
    except KeyError:
        raise OidcError(f"no signing key {kid!r} in the provider's JWKS") from None


def fetch_keys(prov: Provider) -> dict[str, jwt.PyJWK]:
    """Every key in the JWKS that signs with an allowed algorithm, by `kid`. Others are skipped."""
    with http() as client:
        try:
            response = client.get(prov.jwks_uri)
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise OidcError(f"JWKS fetch failed: {type(error).__name__}") from error
    keys: dict[str, jwt.PyJWK] = {}
    for entry in json_body(response).get("keys", []):
        try:
            key = jwt.PyJWK(entry)
        except jwt.PyJWTError as error:
            log.warning("JWKS: skipped a key: %s", type(error).__name__)
            continue
        if key.algorithm_name in ALLOWED_ALGORITHMS and key.key_id:
            keys[key.key_id] = key
    return keys


# --- The flow -------------------------------------------------------------------------------


def b64url(data: bytes) -> str:
    """Base64url without padding, the encoding JOSE and PKCE use."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def code_challenge(verifier: str) -> str:
    """RFC 7636, S256: BASE64URL(SHA256(ASCII(code_verifier)))."""
    return b64url(hashlib.sha256(verifier.encode("ascii")).digest())


def begin(cfg: Config, prov: Provider, redirect_uri: str) -> tuple[str, Flight]:
    """The authorize URL to send the browser to, and what to remember until it comes back."""
    flight = Flight(
        state=secrets.token_urlsafe(32),
        nonce=secrets.token_urlsafe(32),
        # 64 unreserved characters, inside RFC 7636's 43 to 128.
        verifier=secrets.token_urlsafe(48),
        redirect_uri=redirect_uri,
    )
    query = urlencode(
        {
            "response_type": "code",
            "client_id": cfg.client_id,
            "redirect_uri": redirect_uri,
            "scope": cfg.scopes,
            "state": flight.state,
            "nonce": flight.nonce,
            "code_challenge": code_challenge(flight.verifier),
            "code_challenge_method": "S256",
        }
    )
    return f"{prov.authorization_endpoint}?{query}", flight


def exchange_code(cfg: Config, prov: Provider, code: str, flight: Flight) -> dict[str, Any]:
    """The code for the tokens. The client secret travels in the form body (`client_secret_post`,
    one of the two methods discovery lists and the one the ecosystem's reference client uses).
    The verifier is what the provider hashes and compares with the challenge it stored."""
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": flight.redirect_uri,
        "client_id": cfg.client_id,
        "client_secret": cfg.client_secret,
        "code_verifier": flight.verifier,
    }
    with http() as client:
        try:
            response = client.post(prov.token_endpoint, data=form)
        except httpx.HTTPError as error:
            raise OidcError(f"token request failed: {type(error).__name__}") from error
    if response.status_code != 200:
        # The body names the error (`invalid_grant`, `invalid_client`); no secret is in it.
        raise OidcError(f"token endpoint answered {response.status_code}: {response.text[:200]}")
    tokens = json_body(response)
    if "id_token" not in tokens or "access_token" not in tokens:
        raise OidcError("token response has no id_token or no access_token")
    return tokens


def verify_id_token(cfg: Config, prov: Provider, token: str, nonce: str) -> dict[str, Any]:
    """The checks OpenID Connect Core 3.1.3.7 asks of a client: the signature with the provider's
    key for the token's `kid`, `alg` EdDSA and nothing else, `iss`, `aud` equal to our client id,
    `exp` (with a minute of leeway for clocks), and the `nonce` this sign-in sent."""
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as error:
        raise OidcError(f"id token is not a JWT: {type(error).__name__}") from error
    algorithm = header.get("alg")
    if algorithm not in ALLOWED_ALGORITHMS:
        raise OidcError(f"id token alg {algorithm!r} is not one of {ALLOWED_ALGORITHMS}")
    kid = header.get("kid")
    if not isinstance(kid, str) or not kid:
        raise OidcError("id token names no signing key (kid)")
    key = signing_key(prov, kid)
    try:
        claims = jwt.decode(
            token,
            key=key,
            algorithms=list(ALLOWED_ALGORITHMS),
            audience=cfg.client_id,
            issuer=prov.issuer,
            leeway=CLOCK_LEEWAY_SECONDS,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except jwt.PyJWTError as error:
        raise OidcError(f"id token rejected: {type(error).__name__}") from error
    if claims.get("nonce") != nonce:
        raise OidcError("id token nonce does not match this sign-in")
    return claims


def userinfo(prov: Provider, access_token: str) -> dict[str, Any]:
    with http() as client:
        try:
            response = client.get(
                prov.userinfo_endpoint, headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise OidcError(f"userinfo failed: {type(error).__name__}") from error
    return json_body(response)


def claims_for(id_claims: dict[str, Any], fetch_userinfo: Callable[[], dict[str, Any]]) -> Claims:
    """The person from the id token; userinfo only when the token carries no email. A userinfo
    answer whose `sub` differs from the token's is refused (Core 5.3.2)."""
    sub = id_claims.get("sub")
    if not isinstance(sub, str) or not sub:
        raise OidcError("id token has no sub")
    source = id_claims
    if "email" not in id_claims:
        source = fetch_userinfo()
        if source.get("sub") != sub:
            raise OidcError("userinfo sub does not match the id token")
    email = source.get("email")
    if not isinstance(email, str) or not email.strip():
        raise OidcError("the provider gave no email address")
    name = source.get("name")
    return Claims(
        sub=sub,
        email=email.strip().lower(),
        email_verified=source.get("email_verified") is True,
        name=name.strip() if isinstance(name, str) else "",
    )


def end_session_url(cfg: Config, prov: Provider, post_logout_redirect_uri: str) -> str | None:
    """Where to send the browser after the local sign-out so the provider ends its session too
    (RP-Initiated Logout). `client_id` is required when `post_logout_redirect_uri` is sent without
    an `id_token_hint`, and the URI must be one registered for this client, exactly."""
    if prov.end_session_endpoint is None:
        return None
    query = urlencode(
        {"client_id": cfg.client_id, "post_logout_redirect_uri": post_logout_redirect_uri}
    )
    return f"{prov.end_session_endpoint}?{query}"
```

Read it top to bottom; the functions sit in the order the flow calls them.

- **`transport`** is the seam. The views never pass it; `http()` reads it. In production it is `None` and
  httpx talks to the network; in the tests it is a `MockTransport` and nothing leaves the process.
- **`config()` reads the settings on every call,** so a test can switch the client on and the pytest-django
  fixture can switch it off again. `enabled` is derived from the secret, not stored twice.
- **`Provider.from_document`** refuses a document with another `issuer` and a document missing an endpoint,
  with a message that names the field. `end_session_endpoint` is optional in the standard, so it is optional
  here, and the logout view behaves either way.
- **`provider()` and `fetch_provider()`:** the document is fetched once an hour per process. The two paths are
  tried in order, and the first 200 wins. A Vercel function is short-lived, so the hour is a ceiling, not a
  promise.
- **`signing_key()` and `fetch_keys()`:** keys are cached by `kid`. A token that names a key not in the cache
  causes one fetch of the key set; if the key is still missing, the token is refused. Only keys whose algorithm
  is allowed are kept, so an RSA key the provider might add one day is skipped with a log line.
- **`begin()`** makes three random strings and the authorize URL. `secrets.token_urlsafe(48)` gives 64
  characters from the unreserved set, inside RFC 7636's 43 to 128. The verifier never leaves the server; its
  hash does.
- **`flight_from_session()`** reads the session back as data: four strings, or nothing. Session data is the
  app's own, and it is still read, not unpacked.
- **`exchange_code()`** posts the form. The secret goes in the body (`client_secret_post`): the ecosystem's
  reference client does the same against this provider (WitUS, 2026f), the provider's token endpoint reads
  `client_secret` from the body and falls back to HTTP Basic (WitUS, 2026d), and discovery lists both. A non-200
  answer is an error with the status and the first 200 characters of the body, which names the OAuth error and
  never the secret.
- **`verify_id_token()`** is the section-3.1.3.7 list. The header is read unverified first, for two fields: the
  `alg`, which must be in `ALLOWED_ALGORITHMS` before anything else happens, and the `kid`, which picks the
  key. Then one `jwt.decode` call checks the signature, the algorithm again, `iss`, `aud`, `exp` with a minute
  of leeway and the presence of the required claims, each with its own exception class (PyJWT contributors,
  n.d.-a), and the function turns any of them into an `OidcError` that carries the class name. The `nonce` is
  the last check and the only one PyJWT does not know about.
- **`claims_for()`** takes the person from the id token. This provider puts `email`, `email_verified` and
  `name` in the token when the `email` and `profile` scopes were asked for (WitUS, 2026d), so userinfo is a
  fallback: called only when the token has no email, and its `sub` must match the token's, as Core 5.3.2 asks.
  The email is lower-cased for matching; the name is trimmed.
- **`end_session_url()`** builds the RP-initiated logout URL: `client_id` "is most commonly needed when
  `post_logout_redirect_uri` is used without `id_token_hint`", and the URI must be one registered with the
  provider, matched exactly (OpenID Foundation, 2022). The registry registers each app's root for this (WitUS,
  2026c), which is why the view sends the home page's absolute URL and nothing cleverer.

### 07.5 The three views and their routes

Listing 07-12, Filename: `src/invest_witus_site/accounts/views.py`:

```python
"""The three views of Sign in with WitUS: out to the provider, back from it, and out of the app.

Each one reads the client's configuration when the request arrives. With no client secret the
feature is off: the sign-in route shows chapter 04's stub page, and nothing else here runs.
"""

import logging
from dataclasses import asdict

from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from invest_witus_site.accounts import oidc
from invest_witus_site.accounts.models import WitusIdentity
from invest_witus_site.pages.views import sign_in_stub

log = logging.getLogger(__name__)

# The session key that holds the sign-in in progress (an `oidc.Flight` as a dict).
SESSION_KEY = "witus_oidc"
# The one backend this app has; `login()` wants it named when the user did not come from
# `authenticate()`, and this user came from the provider.
BACKEND = "django.contrib.auth.backends.ModelBackend"


def failed(request: HttpRequest, reason: str, status: int = 400) -> HttpResponse:
    """The page for a sign-in that did not finish. The reason is one word; the log has the rest."""
    return render(request, "accounts/sign_in_failed.html", {"reason": reason}, status=status)


def login(request: HttpRequest) -> HttpResponse:
    """Remember a state, a nonce and a code verifier, then send the browser to the provider."""
    cfg = oidc.config()
    if not cfg.enabled:
        return sign_in_stub(request)
    if request.user.is_authenticated:
        return redirect("home")
    try:
        prov = oidc.provider(cfg)
    except oidc.OidcError as error:
        log.error("sign in with WitUS: provider unavailable: %s", error)
        return failed(request, "provider", status=503)
    # The exact URI registered for this client at the provider: this host, this path.
    url, flight = oidc.begin(cfg, prov, request.build_absolute_uri(reverse("witus-callback")))
    request.session[SESSION_KEY] = asdict(flight)
    return redirect(url)


def callback(request: HttpRequest) -> HttpResponse:
    """Check the state, trade the code for tokens, verify the id token, find or create the person,
    and sign them in. Every refusal is a 400 with one word; the detail goes to the log."""
    cfg = oidc.config()
    if not cfg.enabled:
        return sign_in_stub(request)
    # Popped, not read: a callback is good for one attempt, so a replayed URL fails on state.
    flight = oidc.flight_from_session(request.session.pop(SESSION_KEY, None))
    state = request.GET.get("state", "")
    if flight is None or not state or state != flight.state:
        return failed(request, "state")
    if error := request.GET.get("error"):
        log.warning("sign in with WitUS: the provider answered %s", error)
        return failed(request, error)
    code = request.GET.get("code", "")
    if not code:
        return failed(request, "code")
    try:
        prov = oidc.provider(cfg)
        tokens = oidc.exchange_code(cfg, prov, code, flight)
        id_claims = oidc.verify_id_token(cfg, prov, str(tokens["id_token"]), flight.nonce)
        claims = oidc.claims_for(
            id_claims, lambda: oidc.userinfo(prov, str(tokens["access_token"]))
        )
    except oidc.OidcError as error:
        log.warning("sign in with WitUS refused: %s", error)
        return failed(request, "refused")
    identity = WitusIdentity.sign_in(claims)
    auth_login(request, identity.user, backend=BACKEND)
    return redirect("home")


@require_POST
def logout(request: HttpRequest) -> HttpResponse:
    """End the Django session, then let the provider end its own and send the browser home."""
    cfg = oidc.config()
    auth_logout(request)
    if not cfg.enabled:
        return redirect("home")
    try:
        prov = oidc.provider(cfg)
    except oidc.OidcError as error:
        log.error("sign out of WitUS: provider unavailable: %s", error)
        return redirect("home")
    url = oidc.end_session_url(cfg, prov, request.build_absolute_uri(reverse("home")))
    return redirect(url or reverse("home"))
```

- **`login`** renders the stub when the client is off, sends a signed-in visitor home, and otherwise stores the
  flight in the session and redirects. The session is database-backed by default
  (`django.contrib.sessions.backends.db`); the browser gets a cookie with "a session ID, not the data itself"
  (Django Software Foundation, n.d.-b), so the verifier is never in the browser. `redirect_uri` is built from
  the request, which on Vercel is the production origin behind chapter 06's proxy header: exactly the URI the
  registry holds.
- **`callback`** pops the flight. Popped, not read: the callback is good for one attempt, and a replayed URL
  fails on `state` before the app talks to the provider. Then the provider's own `error` parameter, then the
  code, then the four calls from 07.4 inside one `try`. Every `OidcError` becomes a 400 whose page shows one word
  (`state`, `code`, `refused`, or the provider's error code) and whose log line has the rest.
- **`auth_login(request, user, backend=...)`.** `login()` "saves the user's ID in the session" and needs to know
  which backend to record; it takes the `backend` argument, or `user.backend` as set by `authenticate()`, or
  the only backend configured (Django Software Foundation, n.d.-a). This user did not come through
  `authenticate()`, so the backend is named. `login()` also cycles the session key against session fixation
  (Django Software Foundation, n.d.-b).
- **`logout` is POST only.** `auth_logout()` flushes the session: "the session data for the current request is
  completely cleaned out" (Django Software Foundation, n.d.-a). Django 5.0 removed GET from its own
  `LogoutView` (Django Software Foundation, n.d.-d); a link can be followed by a prefetch or a cross-site image
  tag, and a sign-out should happen when the person asked. After the local sign-out, the browser goes to the
  provider's end-session endpoint so the WitUS session ends too, and comes back to the home page.
- **Why the callback's cookie survives the trip.** The session cookie's `SameSite` is `Lax` by default, which
  allows the cookie "when following a regular link from an external website" and blocks it on cross-site POSTs
  (Django Software Foundation, n.d.-c). The provider sends the browser back with a GET, so the session, and
  the flight in it, are there. It is also why the sign-out form posts from this site and not from anywhere
  else.

Listing 07-13, Filename: `src/invest_witus_site/accounts/urls.py`:

```python
"""Sign in with WitUS: three routes under /auth/witus/. The ecosystem's client registry names the
callback path exactly (`/auth/witus/callback/`), and its product list names the login route; the
URL names are what the templates use."""

from django.urls import path

from invest_witus_site.accounts import views

urlpatterns = [
    path("login/", views.login, name="sign-in"),
    path("callback/", views.callback, name="witus-callback"),
    path("logout/", views.logout, name="sign-out"),
]
```

Listing 07-14, Filename: `src/invest_witus_site/urls.py`:

```python
"""Where every URL of the site starts. Each app lists its own paths; this file includes them."""

from django.contrib import admin
from django.urls import include, path

from invest_witus_site import health

urlpatterns = [
    # The owner's back office. Every page under it requires a staff login (chapter 05).
    path("admin/", admin.site.urls),
    # Up, version, database: what a monitor asks after a deploy (chapter 06).
    path("healthz/", health.healthz, name="healthz"),
    # Sign in with WitUS: login, callback and logout (chapter 07).
    path("auth/witus/", include("invest_witus_site.accounts.urls")),
    path("", include("invest_witus_site.pages.urls")),
]
```

The stub route leaves `pages/urls.py`; its name, `sign-in`, is unchanged, so every `{% url 'sign-in' %}` in
the templates and the ecosystem registry's link to `/auth/witus/login/` still point at the same place.

Listing 07-15, Filename: `src/invest_witus_site/pages/urls.py`:

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
    # The sign-in route (`/auth/witus/login/`, name "sign-in") lives in the accounts app since
    # chapter 07; `sign_in_stub` below is what it renders while the client is off.
]
```

The stub page's text changes, and still names chapter 07, because tag `v04`'s test looks for those words and
tags are immutable:

Listing 07-16, Filename: `src/invest_witus_site/pages/templates/pages/sign_in_stub.html`:

```html
{% extends "pages/base.html" %}
{% block title %}Sign in: Invest.WitUS{% endblock %}
{% block content %}
<section class="container narrow">
  <h1>Sign in</h1>
  <p>Sign in with WitUS (chapter 07 of the tutorial) is not switched on in this copy of the app: it has no client secret for the WitUS identity provider, so there is nothing to sign in to. Every public page works without an account.</p>
  <p><a href="{% url 'home' %}">Back to the home page</a></p>
</section>
{% endblock %}
```

Listing 07-17, Filename: `src/invest_witus_site/accounts/templates/accounts/sign_in_failed.html`:

```html
{% extends "pages/base.html" %}
{% block title %}Sign in did not complete: Invest.WitUS{% endblock %}
{% block content %}
<section class="container narrow">
  <h1>Sign in did not complete</h1>
  <p>The sign-in with WitUS stopped before it finished (<code>{{ reason }}</code>). Nothing was changed. The owner's log has the detail.</p>
  <p class="actions"><a class="button" href="{% url 'sign-in' %}">Try again</a> <a href="{% url 'home' %}">Back to the home page</a></p>
</section>
{% endblock %}
```

### 07.6 The header's two states

Listing 07-18, Filename: `src/invest_witus_site/accounts/templates/accounts/_sign_out_form.html`:

```html
{# The "Sign out" control, shown in the header and the footer while someone is signed in. A POST, #}
{# not a link: Django's own LogoutView dropped GET in 5.0, because a link can be followed by a #}
{# prefetch or a cross-site image tag, and a sign-out should happen only when the person asked. #}
{# The accessible name is exactly "Sign out"; never rename it (PRD 7.9). #}
<form method="post" action="{% url 'sign-out' %}" class="sign-out">
  {% csrf_token %}
  <button type="submit">Sign out</button>
</form>
```

Listing 07-19, Filename: `src/invest_witus_site/pages/templates/pages/_header.html`:

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
      {% if user.is_authenticated %}
        {# Signed in (chapter 07): the person's name, then the "Sign out" control, a form. #}
        <span class="who muted">{{ display_name }}</span>
        {% include "accounts/_sign_out_form.html" %}
      {% else %}
        {# While a visitor is signed out, this link's accessible name is exactly "Sign in" on every page. #}
        {# Never rename it (shared UI rule, 2026-10-16): the smoke test in tests/test_ch04.py fails if it changes. #}
        <a class="button" href="{% url 'sign-in' %}">Sign in</a>
      {% endif %}
    </nav>
  </div>
</header>
```

Signed out, the header is chapter 04's, byte for byte in the part that matters: the link whose accessible name
is "Sign in", which the smoke test protects and which the PRD says is never renamed. Signed in, the same spot
holds the person's name and the "Sign out" button. The footer's "Sign in" item gets the same `{% if %}`, with
the same include in the other branch.

Listing 07-20, Filename: `src/invest_witus_site/accounts/context_processors.py`:

```python
"""The signed-in person's name, for the header and the home page, without each view passing it."""

from django.http import HttpRequest

from invest_witus_site.accounts.models import WitusIdentity


def identity(request: HttpRequest) -> dict[str, object]:
    user = request.user
    if not user.is_authenticated:
        return {"display_name": ""}
    linked = WitusIdentity.objects.filter(user_id=user.pk).only("name", "email").first()
    # The owner signed in at /admin/ with a password has no identity until their first WitUS
    # sign-in; the username is their name until then.
    name = linked.display_name if linked is not None else ""
    return {"display_name": name or user.get_username()}
```

One query per request for a signed-in visitor, none for anyone else. The owner signed in at `/admin/` with a
password has no identity until their first WitUS sign-in, so the username stands in, and the header reads
"Sign out" for them as well: a login is a login.

Listing 07-21, Filename: `src/invest_witus_site/pages/templates/pages/home.html`:

```html
{% extends "pages/base.html" %}
{% block title %}Invest.WitUS: pick a taught investing method and stay with it{% endblock %}
{% block content %}
{% if user.is_authenticated %}
<section class="container" aria-label="Your session">
  {# Chapter 07: one line for the signed-in person; the admin link only for staff. #}
  <p class="signed-in muted">Signed in as {{ display_name }}.{% if user.is_staff %} <a href="{% url 'admin:index' %}">Open the admin</a>.{% endif %}</p>
</section>
{% endif %}
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

One line at the top of the home page for a signed-in person, with the admin link only for staff. Five short
rules in `site.css` let the form sit in the header's row and the footer's list like the links around them
(`.site-header nav form`, `.site-header .who`, `.site-footer form`, the footer's button, `.signed-in`).

### 07.7 Green, and a look at the real provider

Listing 07-22, Terminal:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

```text
190 passed in 4.52s
All checks passed!
95 files already formatted
0 errors, 0 warnings, 0 informations
```

Thirty-four new tests. The four names go in `.env.example`, with the switch first:

Listing 07-23, Filename: `.env.example`:

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

# Sign in with WitUS (chapter 07): OpenID Connect against the ecosystem's identity provider. The
# client is OFF until WITUS_OIDC_CLIENT_SECRET is set; until then the sign-in route shows the stub
# page from chapter 04 and the site deploys as before. The owner mints the secret in the witus repo
# (`node scripts/gen-oidc-client.mjs invest`), which prints one value for the provider
# (WITUS_OIDC_SECRET__INVEST, on witus-online) and the same value for this app. Mark it Secret on
# Vercel. A learner's copy of the app is not registered with the provider and leaves it empty.
WITUS_OIDC_CLIENT_SECRET=
# The issuer the provider asserts in its discovery document. Default: https://accounts.witus.online,
# the ecosystem's accounts host as read on October 28, 2026. The discovery document is read from
# under it, and its own `issuer` field must match.
WITUS_OIDC_ISSUER=
# This app's client id at the provider. Default: witus-invest (the registry's `witus-<slug>`).
WITUS_OIDC_CLIENT_ID=
# The scopes asked for. Default: openid email profile. `openid` is required.
WITUS_OIDC_SCOPES=
```

Now see the first step against the real provider, without a server and without a secret of your own: any
non-empty value switches the client on, discovery is fetched from accounts.witus.online, and the redirect is
built. The provider is not contacted with anything but two GETs for public documents.

Listing 07-24, Terminal:

```sh
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:////tmp/invest-witus-07.sqlite3 \
uv run python manage.py migrate -v 0
DJANGO_DEBUG=1 DJANGO_ALLOWED_HOSTS=testserver DATABASE_URL=sqlite:////tmp/invest-witus-07.sqlite3 \
WITUS_OIDC_CLIENT_SECRET=not-the-real-secret-just-for-this-check \
uv run python manage.py shell -c "from django.test import Client; r = Client().get('/auth/witus/login/'); print(r.status_code); print(r['Location'])"
```

```text
302
https://accounts.witus.online/api/idp/oauth2/authorize?response_type=code&client_id=witus-invest&redirect_uri=http%3A%2F%2Ftestserver%2Fauth%2Fwitus%2Fcallback%2F&scope=openid+email+profile&state=ZNhXesuS0TiluB-7aeGM6aLlVF11tLmTxUWW9HF83VM&nonce=gyMfbPluzSuwMPNYo__aUypOFfAyYxzMOnDQahR2ExY&code_challenge=eSrVMyFlPYiapJ8Go4rRrrGVVWYtZaK9n4ttmEeLd5I&code_challenge_method=S256
```

(The shell's line about imported objects is trimmed; your `state`, `nonce` and `code_challenge` are different
random strings.) The discovery document was read from the second path, its issuer matched, and the authorize
endpoint came from it. Follow that URL in a browser and the provider answers 400 "Invalid redirect URI", since
`http://testserver/...` is registered nowhere: the provider doing its job. Drop `WITUS_OIDC_CLIENT_SECRET` from
the command and the status is 200 with the stub page. Delete the temporary database afterwards.

### 07.8 What the owner does outside the editor

The reference app's registration is the owner's, in the witus repo, where the provider's client registry lives
(WitUS, 2026c); task 07 in the owner's queue has the dashboard steps. A learner's copy cannot do this: the
provider accepts first-party ecosystem apps only, and each one's redirect URI is matched exactly. What the
steps are, so the chapter is complete:

1. **The registry entry.** `lib/identity/clients.ts` holds slug `invest`, origin
   `https://invest.witus.online` and `callbackPath` `/auth/witus/callback/`; the registry registers the root
   `https://invest.witus.online/` as the post-logout URI by default. The client id is `witus-invest`.
2. **Mint the secret.** `node scripts/gen-oidc-client.mjs invest` refuses a slug that is not registered, makes
   a 32-byte secret, and prints two blocks: one for the provider's own Vercel project
   (`WITUS_OIDC_SECRET__INVEST`) and one, marked as belonging to the app's project and not the provider's, with
   `WITUS_OIDC_CLIENT_ID` and `WITUS_OIDC_CLIENT_SECRET` (WitUS, 2026e). It stores nothing; the secret is shown
   once and goes in a password manager. The provider ignores the `invest` client until its variable exists and
   the provider's function has restarted with it. This step was done on October 28, 2026.
3. **Set the secret on this app's Vercel project:** `WITUS_OIDC_CLIENT_SECRET`, marked sensitive, Production
   and Preview. The other three names keep their defaults. A preview deployment can show the header but not
   finish a sign-in, because its host is not the registered origin.
4. **Migrate and redeploy.** `vercel env run -e production -- uv run python manage.py migrate --database direct`
   adds the identity table (chapter 06's recipe); then Redeploy, so the function starts with the secret.
5. **Sign in once and check:** `/auth/witus/login/` answers 302 to `accounts.witus.online/api/idp/oauth2/authorize`;
   the callback lands on the home page with "Signed in as" and a header that reads "Sign out"; the admin's
   WitUS identities list has one row, attached to the superuser if the emails matched and the provider marked
   the email verified, or to a new `witus-<sub>` user otherwise (the admin re-points it); each of the owner's
   accounts shows the WitUS user id; "Sign out" passes through the provider's end-session endpoint and returns
   to the home page.

## Checkpoint

- `uv run pytest` prints `190 passed`; ruff and pyright pass.
- With `.env` as before (no secret), `/auth/witus/login/` is the stub page and every public page has the "Sign
  in" link.
- Listing 07-24 prints a 302 to the provider's authorize endpoint with `code_challenge_method=S256`.
- `test_code_challenge_is_s256_of_the_verifier` passes against the RFC's own numbers.
- On the reference app, after 07.8: a sign-in lands with "Signed in as", and "Sign out" returns to the home
  page signed out.
- Commit and push: `git add -A && git commit -m "Chapter 07: Sign in with WitUS"`.

## Exercises

1. The callback refuses a token whose `exp` is an hour old. Write the test for a token whose `iat` is an hour in
   the future, decide what the client should do about it (PyJWT has a `verify_iat` option and `leeway` applies
   to it), and change `verify_id_token` or leave it, with a sentence in your notes saying why.
2. Make the allowed algorithm a setting, `WITUS_OIDC_ID_TOKEN_ALG`, defaulting to `EdDSA`, so your copy can talk
   to a provider of your own that signs RS256. Keep `none` refused whatever the setting says, and keep the test
   that proves it. Then register your copy with that provider and sign in from your laptop.
3. The sign-out form appears twice on every signed-in page. Write the test that counts the forms and asserts
   both post to `/auth/witus/logout/`, then decide whether the footer's copy earns its place.

## If you get stuck

- Browse: https://github.com/dapperAuteur/invest-witus/tree/v07
- Diff for this chapter: https://github.com/dapperAuteur/invest-witus/compare/v06a...v07
- Zip: https://github.com/dapperAuteur/invest-witus/archive/v07.zip
- Take the reference's files. Chapter 07 changed `pyproject.toml` and `uv.lock` (httpx, PyJWT), `.env.example`,
  `src/invest_witus_site/settings.py`, `src/invest_witus_site/urls.py`, `src/invest_witus_site/pages/urls.py`,
  `src/invest_witus_site/pages/views.py`, the templates `pages/_header.html`, `pages/_footer.html`,
  `pages/home.html` and `pages/sign_in_stub.html`, `pages/static/pages/site.css` and `docs/site/privacy.md`,
  and added `src/invest_witus_site/accounts/` (the whole app) and `tests/test_ch07.py`. Nothing moved:
  `git fetch reference --tags && git checkout v07 -- src tests .env.example pyproject.toml uv.lock docs/site/privacy.md`,
  then `uv sync`.
- `ModuleNotFoundError: No module named 'httpx'` or `'jwt'`: 07.2's `uv add` did not run, or the test is being
  run with another Python; use `uv run pytest`.
- `No module named 'invest_witus_site.accounts'` after 07.3: the app folder is missing its `__init__.py`, or sits
  outside `src/invest_witus_site/`.
- `ImproperlyConfigured: WITUS_OIDC_ISSUER must be the provider's https:// issuer`: the variable holds a path or
  a plain-http URL; it wants the origin the discovery document names.
- `test_discovery_falls_back_to_the_api_idp_path_and_is_cached` fails on the second path: `DISCOVERY_PATHS`
  is in the wrong order, or `fetch_provider` stops at the first non-200 instead of trying the next path.
- `test_callback_rejects_a_token_that_is_not_eddsa` fails with the JWKS fetched: the `alg` check sits after
  `signing_key()`; it must come first, on the unverified header.
- `test_a_good_callback_creates_the_identity_and_signs_the_person_in` fails on `has_usable_password`:
  `new_user` passed a password; `create_user(username=..., email=...)` with no password is the point.
- `test_the_owners_superuser_links_by_verified_email` makes two users: `existing_user` filters on
  `witus_identity__isnull=True` and `email__iexact`; check the related name on the `OneToOneField`.
- `test_logout_is_a_post_and_goes_home_with_the_client_off` gets 302 for the GET: `@require_POST` is missing
  from `logout`.
- `ValueError: ... backend` from `auth_login`: the `backend=` argument is missing; this user did not come
  through `authenticate()`.
- On the reference app, the provider's page says "Invalid redirect URI": the host is not the registered
  origin, or the registry's `callbackPath` differs from `/auth/witus/callback/`.
- The callback page says `refused` and the log says `token endpoint answered 401`: the two secrets differ, or
  the provider has not restarted since its variable was set.
- The callback page says `state`: the session cookie did not survive the trip. Over plain HTTP with debug off,
  chapter 06's Secure cookie is never sent; use `--env-file .env` on a laptop. On Vercel, a callback opened in
  another browser or after the session expired fails the same way, on purpose.

## What we learned

- The authorization code flow is six steps, and each is a function a test can call: out with `state`, `nonce`
  and a challenge; back with a code; the exchange with the verifier; the id token's checks; the person; the
  session.
- A provider's discovery document is read, not assumed, and its `issuer` is checked against the configured one;
  when the document is not at the standard's path, the code says where it looked and why.
- The algorithm a client accepts is a constant, never the token's own header; `kid` picks the key, the key set
  is cached and refetched once; `iss`, `aud`, `exp` and `nonce` each have a test that fails them.
- PKCE is a hash on the way out and the secret on the way back, and the RFC's worked example is a test.
- The session holds the sign-in in progress on the server; the browser holds an id; `Lax` is why the callback
  still sees it and why the sign-out is a POST.
- People are keyed by `sub`. Email links an existing user once, only when verified, and the rule is written
  before it runs.
- The client is on exactly when its secret is set, so a copy of the app without one is the chapter 06 site with
  a stub, and the owner's registration is a dashboard task with its checks written down.

## Next

Chapter 08 adds prices: end-of-day closes in the app's own table, one daily cron route guarded by `CRON_SECRET`,
idempotent and recording its last run, and the owner's holdings valued with the price date shown. Nothing from
this chapter changes for it; the signed-in owner is who those values are for.

## References

Authlib contributors. (n.d.-a). *sync_openid.py* [Source code, `main` branch]. GitHub.
https://raw.githubusercontent.com/authlib/authlib/main/authlib/integrations/base_client/sync_openid.py
(retrieved October 28, 2026)

Authlib contributors. (n.d.-b). *JSON Web Signature (JWS)*. Authlib documentation.
https://docs.authlib.org/en/latest/jose/jws.html (retrieved October 28, 2026)

better-auth. (n.d.). *JWT*. better-auth documentation. https://www.better-auth.com/docs/plugins/jwt (retrieved
October 28, 2026)

Django Software Foundation. (n.d.-a). *Using the Django authentication system*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/auth/default/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-b). *How to use sessions*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/topics/http/sessions/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-c). *Settings*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/ref/settings/ (retrieved October 28, 2026)

Django Software Foundation. (n.d.-d). *Django 5.0 release notes*. Django 5.2 documentation.
https://docs.djangoproject.com/en/5.2/releases/5.0/ (retrieved October 28, 2026)

Encode. (n.d.). *Transports*. HTTPX documentation. https://www.python-httpx.org/advanced/transports/ (retrieved
October 28, 2026)

Liusvaara, I. (2017). *CFRG elliptic curve Diffie-Hellman (ECDH) and signatures in JSON Object Signing and
Encryption (JOSE)* (RFC 8037). RFC Editor. https://www.rfc-editor.org/rfc/rfc8037 (retrieved October 28, 2026)

OpenID Foundation. (2022). *OpenID Connect RP-Initiated Logout 1.0*.
https://openid.net/specs/openid-connect-rpinitiated-1_0.html (retrieved October 28, 2026)

OpenID Foundation. (2023). *OpenID Connect Discovery 1.0 incorporating errata set 2*.
https://openid.net/specs/openid-connect-discovery-1_0.html (retrieved October 28, 2026)

PyJWT contributors. (n.d.-a). *API reference*. PyJWT documentation.
https://pyjwt.readthedocs.io/en/stable/api.html (retrieved October 28, 2026)

PyJWT contributors. (n.d.-b). *Digital signature algorithms*. PyJWT documentation.
https://pyjwt.readthedocs.io/en/stable/algorithms.html (retrieved October 28, 2026)

PyJWT contributors. (n.d.-c). *Installation*. PyJWT documentation.
https://pyjwt.readthedocs.io/en/stable/installation.html (retrieved October 28, 2026)

pytest-django. (n.d.). *Django helpers*. pytest-django documentation.
https://pytest-django.readthedocs.io/en/latest/helpers.html (retrieved October 28, 2026)

Sakimura, N., Bradley, J., & Agarwal, N. (2015). *Proof Key for Code Exchange by OAuth public clients* (RFC
7636). RFC Editor. https://www.rfc-editor.org/rfc/rfc7636 (retrieved October 28, 2026)

Sakimura, N., Bradley, J., Jones, M., de Medeiros, B., & Mortimore, C. (2023). *OpenID Connect Core 1.0
incorporating errata set 2*. OpenID Foundation. https://openid.net/specs/openid-connect-core-1_0.html
(retrieved October 28, 2026)

WitUS. (2026a). *OpenID provider configuration* [Discovery document].
https://accounts.witus.online/api/idp/.well-known/openid-configuration (read October 28, 2026)

WitUS. (2026b). *JSON Web Key Set*. https://accounts.witus.online/api/idp/jwks (read October 28, 2026)

WitUS. (2026c). *WitUS Accounts: first-party OAuth/OIDC client registry* [Source code].
`gemini/witus/lib/identity/clients.ts` and `lib/identity/id-token-alg.ts` (read October 28, 2026)

WitUS. (2026d). *WitUS Accounts: the ecosystem identity provider* [Source code]. `gemini/witus/lib/identity/auth.ts`,
`lib/identity/env.ts` and `node_modules/better-auth/dist/plugins/oidc-provider/index.mjs` (better-auth 1.6;
read October 28, 2026)

WitUS. (2026e). *gen-oidc-client.mjs* [Source code]. `gemini/witus/scripts/gen-oidc-client.mjs` (read October
28, 2026)

WitUS. (2026f). *Ecosystem SSO helpers and the authorize and callback routes* [Source code].
`claude/lang-chain/wanderlearn-field-reporter/src/lib/witus-sso.ts`, `src/lib/witus-sso-config.ts`,
`src/app/api/auth/witus/authorize/route.ts` and `callback/route.ts` (read October 28, 2026)
