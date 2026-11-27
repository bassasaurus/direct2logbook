"""Validate remarks without silently changing a pilot's text."""
from django.core.exceptions import ValidationError


def validate_remarks(value):
    errors = []
    if value and ',' in value:
        errors.append('Remove commas to prevent export corruption.')
    if value and '\t' in value:
        errors.append('Remove tabs to prevent export corruption.')
    if errors:
        raise ValidationError(errors)
