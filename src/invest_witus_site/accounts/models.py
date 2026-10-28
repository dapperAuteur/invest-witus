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
