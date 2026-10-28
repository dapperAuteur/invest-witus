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
