"""The owner's "Draft a post" and "Send again", in the admin. Superuser only.

**Draft a post** is the admin's add form for `SocialDraft`: pick the occasion, write the text,
tick the platforms, Save. The draft is saved, one row per platform is made, and each is sent to
WitUS Outbox as a draft at once; the message says what Outbox answered. A saved draft is
read-only here: edit, schedule, approve or reject it in Outbox, which is where it is posted from.
**Send again to WitUS Outbox** sends the selected drafts' rows that Outbox has not taken, the
manual fallback for the nightly retry; a row already in Outbox is left alone.
"""

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.models import User
from django.db.models import QuerySet
from django.http import HttpRequest

from invest_witus_site.outbox.client import DEFAULT_PLATFORMS
from invest_witus_site.outbox.delivery import DeliveryRun, send_draft
from invest_witus_site.outbox.models import PLATFORM_CHOICES, SENT, SocialDraft, SocialPost

if TYPE_CHECKING:
    # The stubs' own names for what these two methods return; they exist only in django-stubs.
    from django.contrib.admin.options import _FieldGroups  # pyright: ignore[reportPrivateUsage]
    from django.utils.datastructures import _ListOrTuple  # pyright: ignore[reportPrivateUsage]

POST_FIELDS = (
    "platform",
    "outbox_status",
    "outbox_record_status",
    "outbox_id",
    "attempts",
    "last_tried_at",
    "last_error",
)


class SocialDraftForm(forms.ModelForm[SocialDraft]):
    platforms = forms.MultipleChoiceField(
        choices=PLATFORM_CHOICES,
        initial=list(DEFAULT_PLATFORMS),
        widget=forms.CheckboxSelectMultiple,
        help_text="One draft per platform arrives in Outbox.",
    )

    class Meta:
        model = SocialDraft
        fields = ("occasion", "text")
        widgets = {"text": forms.Textarea(attrs={"rows": 4, "maxlength": 280})}


class SocialPostInline(admin.TabularInline[SocialPost, SocialDraft]):
    model = SocialPost
    fields = POST_FIELDS
    readonly_fields = POST_FIELDS
    extra = 0
    can_delete = False

    def has_add_permission(self, request: HttpRequest, obj: SocialDraft | None = None) -> bool:
        return False


def is_owner(request: HttpRequest) -> bool:
    return getattr(request.user, "is_superuser", False) is True


def report(model_admin: admin.ModelAdmin[Any], request: HttpRequest, run: DeliveryRun) -> None:
    if run.checked == 0:
        model_admin.message_user(request, "Outbox: nothing to send.", messages.INFO)
        return
    summary = f"Outbox: {run.sent} of {run.checked} sent."
    level = messages.WARNING if run.errors else messages.SUCCESS
    model_admin.message_user(request, summary, level)
    for error in run.errors:
        model_admin.message_user(request, error, messages.WARNING)


@admin.register(SocialDraft)
class SocialDraftAdmin(admin.ModelAdmin[SocialDraft]):
    form = SocialDraftForm
    list_display = ("__str__", "occasion", "in_outbox", "created_at")
    list_filter = ("occasion",)
    inlines = (SocialPostInline,)
    actions = ("send_selected_again",)

    # Superuser only, whatever a staff account's permissions say: the guide's owner-only gate.
    def has_module_permission(self, request: HttpRequest) -> bool:
        return is_owner(request)

    def has_view_permission(self, request: HttpRequest, obj: SocialDraft | None = None) -> bool:
        return is_owner(request)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return is_owner(request)

    def has_change_permission(self, request: HttpRequest, obj: SocialDraft | None = None) -> bool:
        return is_owner(request)

    def has_delete_permission(self, request: HttpRequest, obj: SocialDraft | None = None) -> bool:
        return is_owner(request)

    def get_fields(self, request: HttpRequest, obj: SocialDraft | None = None) -> _FieldGroups:
        if obj is None:
            return ("occasion", "text", "platforms")
        return ("occasion", "text", "created_by", "created_at")

    def get_readonly_fields(
        self, request: HttpRequest, obj: SocialDraft | None = None
    ) -> _ListOrTuple[str]:
        if obj is None:
            return ()
        return ("occasion", "text", "created_by", "created_at")

    @admin.display(description="In Outbox")
    def in_outbox(self, obj: SocialDraft) -> str:
        posts = list(SocialPost.objects.filter(draft=obj))
        taken = sum(1 for post in posts if post.outbox_status == SENT)
        return f"{taken} of {len(posts)}"

    def save_model(
        self,
        request: HttpRequest,
        obj: SocialDraft,
        form: forms.ModelForm[SocialDraft],
        change: bool,
    ) -> None:
        if change:
            return
        obj.created_by = request.user if isinstance(request.user, User) else None
        super().save_model(request, obj, form, change)
        platforms: Iterable[str] = form.cleaned_data["platforms"]
        for platform in platforms:
            SocialPost.objects.create(draft=obj, platform=platform)
        report(self, request, send_draft(obj))

    @admin.action(description="Send again to WitUS Outbox")
    def send_selected_again(self, request: HttpRequest, queryset: QuerySet[SocialDraft]) -> None:
        total = DeliveryRun()
        for draft in queryset:
            run = send_draft(draft)
            total.checked += run.checked
            total.sent += run.sent
            total.errors.extend(run.errors)
        report(self, request, total)
