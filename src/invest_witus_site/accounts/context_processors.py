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
