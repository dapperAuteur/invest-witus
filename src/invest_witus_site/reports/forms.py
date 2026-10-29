"""The report form: a kind, a message, the page, an email when signed out, and the honeypot."""

from typing import Any

from django import forms

from invest_witus_site.reports.models import MESSAGE_LIMIT, PAGE_LIMIT, Report


class ReportForm(forms.Form):
    kind = forms.ChoiceField(
        label="What is this about?", choices=Report.Kind.choices, widget=forms.RadioSelect
    )
    message = forms.CharField(
        label="Your message",
        max_length=MESSAGE_LIMIT,
        widget=forms.Textarea(attrs={"rows": 6}),
        help_text="What happened, or what you want to know. Leave out passwords and keys.",
    )
    page = forms.CharField(
        label="What page were you on? (optional)",
        max_length=PAGE_LIMIT,
        required=False,
        help_text="Filled in from the page you came from. Change or clear it.",
    )
    email = forms.EmailField(
        label="Your email",
        max_length=254,
        required=False,
        help_text="So the answer can reach you. Used for this report only.",
    )
    # The honeypot, as on the waitlist form (chapter 04): people never see it, bots fill it in.
    website = forms.CharField(
        required=False,
        label="Leave this field empty",
        widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}),
    )

    def __init__(self, *args: Any, signed_in: bool = False, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.signed_in = signed_in
        if signed_in:
            # Signed in, the WitUS identity says who wrote it; there is no email to type.
            del self.fields["email"]
        else:
            self.fields["email"].required = True

    def clean_message(self) -> str:
        message = str(self.cleaned_data["message"]).strip()
        if not message:
            raise forms.ValidationError("Write a sentence or two.")
        return message

    def clean_page(self) -> str:
        return page_path(str(self.cleaned_data.get("page") or ""))

    def is_bot(self) -> bool:
        return bool(self.cleaned_data.get("website"))


def page_path(text: str) -> str:
    """A path on this site, without its query string, or empty. Anything else (a full URL to
    another site, a sentence) is kept as typed, trimmed, because the person may mean it."""
    value = text.strip()[:PAGE_LIMIT]
    if value.startswith("/") and not value.startswith("//"):
        return value.split("?", 1)[0].split("#", 1)[0]
    return value
