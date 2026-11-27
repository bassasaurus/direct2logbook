"""Preserve supported approach types and counts without inventing a type."""
import re
from collections import OrderedDict
from .validation import CSVValidationError, number
from flights.approach_choices import ALL_APPROACH_CHOICES


def type_key(value):
    return re.sub(r'[^A-Z0-9]', '', value.upper())


TYPES = {'UNSPECIFIED': '', 'UNKNOWN': ''}
for code, label in ALL_APPROACH_CHOICES:
    if code:
        TYPES.setdefault(type_key(code), code)
        TYPES.setdefault(type_key(label), code)


def approach_details(text, count=None):
    text = text.strip()
    if not text:
        return [{'approach_type':'', 'number':count}] if count else []
    parts = [part.strip() for part in re.split(r'[;,\n]+', text) if part.strip()]
    totals = OrderedDict()
    for part in parts:
        match = re.fullmatch(r'(.+?)\s*(?::|[x×-])\s*(\d+)', part, re.IGNORECASE)
        leading = re.fullmatch(r'(\d+)\s*[x×]?\s+(.+)', part, re.IGNORECASE)
        if match:
            kind, amount = match[1], number(match[2], integer=True)
        elif leading:
            kind, amount = leading[2], number(leading[1], integer=True)
        else:
            kind, amount = part, count if len(parts) == 1 and count else 1
        code = TYPES.get(type_key(kind))
        if code is None:
            raise CSVValidationError('Approach types: Choose a supported type, such as ILS, LPV or VOR.')
        if amount <= 0:
            raise CSVValidationError('Approach types: Counts must be greater than zero.')
        totals[code] = totals.get(code, 0) + amount
    total = number(str(sum(totals.values())), integer=True)
    if count is not None and total != count:
        raise CSVValidationError('Approach types: Counts must match Approaches.')
    return [{'approach_type':code, 'number':amount} for code, amount in totals.items()]


def format_approaches(details):
    return '; '.join(f'{item["approach_type"] or "Unspecified"}: {item["number"]}' for item in details)
