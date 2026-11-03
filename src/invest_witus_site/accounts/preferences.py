"""`/settings/`: the signed-in person's own settings (2026-11-03, decision 163).

One page, linked from the header, for options that belong to the person rather than to an account
or a plan. It holds one setting now, the default view of the method pages (decision 155's
`ViewPreference`, also set by "Make <view> my default view" under the A/B/C switch), and is built
so the next per-person option is one more field on `SettingsForm` and one more line in `save`.
Site-wide options stay in the owner's admin; nothing here is shown to anyone but the person.
"""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from invest_witus_site.methods.models import VIEW_CHOICES, ViewPreference
from invest_witus_site.methods.views import SESSION_KEY

# The choice that removes a saved default, so chapter 10's defaults apply again.
NO_DEFAULT = "none"


class SettingsForm(forms.Form):
    default_view = forms.ChoiceField(
        label="Default view on method pages",
        choices=[
            (NO_DEFAULT, "No default: A while a method runs, C while none"),
            *VIEW_CHOICES,
        ],
        widget=forms.RadioSelect,
        help_text=(
            "The view a method page opens on when you have not picked one since you signed in. "
            "Picking a view with the A, B and C links still holds for the rest of the sign-in."
        ),
    )

    def save(self, request: HttpRequest) -> str:
        """Write each setting for the person and return the sentence the page confirms with."""
        view: str = self.cleaned_data["default_view"]
        if view == NO_DEFAULT:
            ViewPreference.objects.filter(user=request.user).delete()
            request.session.pop(SESSION_KEY, None)
            return "Saved. Method pages open on A while a method runs and on C while none does."
        ViewPreference.save_for(request.user, view)
        # The same as "Make <view> my default": the choice holds for this sign-in too.
        request.session[SESSION_KEY] = view
        return f"Saved. Method pages open on {dict(VIEW_CHOICES)[view]}."


@login_required
def settings_page(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = SettingsForm(request.POST)
        if form.is_valid():
            messages.success(request, form.save(request))
            return redirect("settings")
    else:
        saved = ViewPreference.for_user(request.user)
        form = SettingsForm(initial={"default_view": saved or NO_DEFAULT})
    return render(request, "accounts/settings.html", {"form": form})
