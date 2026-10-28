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
