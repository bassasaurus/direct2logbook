"""Resolve numeric date order once per CSV, before a batch can be submitted."""
import csv
import io
import re
from datetime import date

from logbook.date_formats import display_date, parse_date
from .validation import CSVValidationError

DATE_ORDER_CHOICES = (('mdy', 'Month/Day/Year (MM/DD/YYYY)'),
                      ('dmy', 'Day/Month/Year (DD/MM/YYYY)'))
DATE_ORDER_LABELS = dict(DATE_ORDER_CHOICES)
NUMERIC_DATE = re.compile(r'^(\d{1,2})([/\-])(\d{1,2})\2(\d{4})$')


class AmbiguousDates(CSVValidationError):
    def __init__(self, examples):
        super().__init__('Choose the date format used in this file.')
        self.examples = examples


def interpret_dates(content, order='auto'):
    if order not in ('auto', 'mdy', 'dmy'):
        raise CSVValidationError('Choose a valid date format.')
    try:
        records = list(csv.reader(io.StringIO(content), strict=True))
    except csv.Error as exc:
        raise CSVValidationError('The CSV has invalid quoting.') from exc
    possible = {'mdy', 'dmy'}
    parsed = []
    examples = []
    has_numeric = False
    for line, record in enumerate(records[1:], start=2):
        if not any(value.strip() for value in record):
            continue
        value = record[0].strip()
        match = NUMERIC_DATE.fullmatch(value)
        if match:
            has_numeric = True
            first, second, year = int(match[1]), int(match[3]), int(match[4])
            options = {}
            for key, month, day in [('mdy', first, second), ('dmy', second, first)]:
                try:
                    options[key] = date(year, month, day)
                except ValueError:
                    pass
            if not options:
                raise CSVValidationError(f'Row {line}: Enter a valid date.')
            possible &= options.keys()
            if not possible:
                raise CSVValidationError(f'Row {line}: Numeric dates mix Month/Day/Year and Day/Month/Year. Use one date order throughout the file.')
            if order != 'auto' and order not in options:
                raise CSVValidationError(f'Row {line}: Date does not match {DATE_ORDER_LABELS[order]}.')
            if len(options) == 2 and options['mdy'] != options['dmy'] and len(examples) < 3:
                examples.append({'original': value, 'mdy': display_date(options['mdy']), 'dmy': display_date(options['dmy'])})
        else:
            try:
                resolved = parse_date(value)
            except ValueError as exc:
                raise CSVValidationError(f'Row {line}: Enter a valid date, such as Nov 30, 2026 or 2026-11-30.') from exc
            options = {'mdy': resolved, 'dmy': resolved}
        parsed.append((record, options))
    if order == 'auto' and len(possible) == 2 and examples:
        raise AmbiguousDates(examples)
    resolved_order = order if order != 'auto' else next(iter(possible)) if len(possible) == 1 else 'unambiguous'
    for record, options in parsed:
        record[0] = (options[resolved_order] if resolved_order in options else next(iter(options.values()))).isoformat()
    output = io.StringIO()
    csv.writer(output).writerows(records)
    return output.getvalue(), resolved_order if has_numeric else 'unambiguous'
