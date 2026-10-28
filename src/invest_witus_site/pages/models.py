"""Database tables for the public pages. This chapter has one: the waitlist."""

from datetime import datetime

from django.db import models


class WaitlistEntry(models.Model):
    """One person who asked to hear when the app opens. One row per email address.

    The `[str, str]` after each field type is for pyright: the type you may assign, and the type
    you read back. django-stubs leaves those two for its mypy plugin to fill in, so with pyright we
    write them ourselves (the way you would write `Field<string, string>` in TypeScript).
    """

    class Status(models.TextChoices):
        """Where a person stands. The public form only ever creates `waiting`; the owner
        approves in the admin (chapter 05). An approved person is told when the app opens."""

        WAITING = "waiting", "Waiting"
        APPROVED = "approved", "Approved"

    name: models.CharField[str, str] = models.CharField(max_length=120)
    email: models.EmailField[str, str] = models.EmailField(max_length=254, unique=True)
    created_at: models.DateTimeField[datetime, datetime] = models.DateTimeField(auto_now_add=True)
    status: models.CharField[str, str] = models.CharField(
        max_length=10, choices=Status.choices, default=Status.WAITING
    )

    class Meta:
        ordering = ["created_at"]
        verbose_name_plural = "waitlist entries"

    def __str__(self) -> str:
        return self.email

    @classmethod
    def join(cls, name: str, email: str) -> tuple[WaitlistEntry, bool]:
        """Add a person once. The same address in any case or spacing keeps the first row.

        Returns the row and whether it was created now, the way `get_or_create` does.
        """
        return cls.objects.get_or_create(
            email=email.strip().lower(), defaults={"name": name.strip()}
        )
