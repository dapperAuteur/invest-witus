"""The add form: one or many symbols in one box, and an optional note for all of them. Since
2026-10-29 also "Fetch their history now" (on in a new form) and its range: when ticked, the
symbols the submission added are fetched in the same request, like Fetch history for selected."""

from django import forms
from django.core.exceptions import ValidationError

from invest_witus_site.prices.manual import DEFAULT_HISTORY_RANGE, HISTORY_RANGES
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
    # An unticked box sends nothing, so a submission without it (an older page, a script) keeps
    # chapter 09's behaviour: prices arrive with the nightly pull or Fetch prices now.
    fetch_history = forms.BooleanField(
        label="Fetch their history now", required=False, initial=True
    )
    history_range = forms.ChoiceField(
        label="History range",
        choices=[(value, label) for value, (label, _) in HISTORY_RANGES.items()],
        initial=DEFAULT_HISTORY_RANGE,
        required=False,
    )

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
