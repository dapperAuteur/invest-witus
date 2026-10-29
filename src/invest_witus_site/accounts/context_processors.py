"""The signed-in person's name, for the header and the home page, without each view passing it,
and whether to offer "Sign out of WitUS everywhere" beside "Sign out"."""

from django.http import HttpRequest

from invest_witus_site.accounts import oidc
from invest_witus_site.accounts.models import WitusIdentity


def identity(request: HttpRequest) -> dict[str, object]:
    user = request.user
    if not user.is_authenticated:
        return {"display_name": "", "sign_out_everywhere": False}
    # The second control shows only while the WitUS client is on. It reads the settings, not the
    # discovery document, so no page waits on the provider; the view goes home after the local
    # sign-out if the provider turns out to have no end-session endpoint.
    everywhere = oidc.config().enabled
    linked = WitusIdentity.objects.filter(user_id=user.pk).only("name", "email").first()
    # The owner signed in at /admin/ with a password has no identity until their first WitUS
    # sign-in; the username is their name until then.
    name = linked.display_name if linked is not None else ""
    return {"display_name": name or user.get_username(), "sign_out_everywhere": everywhere}
