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
