"""The waitlist form: name and email, nothing more."""

from django import forms


class WaitlistForm(forms.Form):
    name = forms.CharField(label="Name", max_length=120)
    email = forms.EmailField(label="Email", max_length=254)
    # A honeypot. People never see this field (the stylesheet hides it and it is skipped by
    # keyboard); bots fill in every field they find. A filled value means "not a person".
    website = forms.CharField(
        required=False,
        label="Leave this field empty",
        widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}),
    )

    def is_bot(self) -> bool:
        return bool(self.cleaned_data.get("website"))
