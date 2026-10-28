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
