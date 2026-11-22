from django import forms
from .date_formats import display_date


class NamedDateInput(forms.DateInput):
    """Text date entry with an unambiguous, non-zero-padded display."""
    def format_value(self, value):
        if value is None or value == '':
            return ''
        # Preserve submitted text: legacy medical dates use day/month order.
        if isinstance(value, str):
            return value
        try:
            return display_date(value)
        except (ValueError, TypeError):
            return value
