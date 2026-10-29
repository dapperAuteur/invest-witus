"""The add form: one or many symbols in one box, and an optional note for all of them."""

from django import forms
from django.core.exceptions import ValidationError

from invest_witus_site.watchlist.models import ParsedSymbols, parse_symbols


class WatchForm(forms.Form):
    symbols = forms.CharField(
        label="Symbols",
        max_length=400,
        widget=forms.TextInput(
            attrs={"autocomplete": "off", "autocapitalize": "characters", "spellcheck": "false"}
        ),
    )
    note = forms.CharField(label="Note", required=False, max_length=200)

    def clean_symbols(self) -> ParsedSymbols:
        """The box as a parsed list. It is a form error only when nothing in it can be added;
        a refused token beside a valid one is reported after the valid one is added."""
        parsed = parse_symbols(self.cleaned_data["symbols"])
        if parsed.symbols:
            return parsed
        if parsed.refused:
            reasons = "; ".join(f"{token} ({reason})" for token, reason in parsed.refused)
            raise ValidationError(f"No symbol to add: {reasons}.")
        raise ValidationError("Enter at least one symbol.")
