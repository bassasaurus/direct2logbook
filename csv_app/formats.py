"""Source adapters translate CSV files into the existing validated import format.

Only verified formats belong in this registry. Recognition uses headings, never
the filename; unknown sources must not be guessed into an import.
"""
import csv
import io
import re
from dataclasses import dataclass

from .validation import ALIASES, HEADERS, OPTIONAL_HEADERS, MAX_BYTES, MAX_ROWS, CSVValidationError
from .mapping import editable_value, read_source


def heading(value):
    name = ' '.join(re.sub(r'[_-]+', ' ', value.strip().lower()).split())
    return ALIASES.get(name, name)


class ColumnsNeedMapping(CSVValidationError):
    pass


@dataclass(frozen=True)
class Direct2LogbookFormat:
    key: str = 'direct2logbook-v1'
    label: str = 'Direct2Logbook CSV'

    def matches(self, headings):
        required = set(HEADERS) - {'approaches'}
        return (len(headings) == len(set(headings)) and required <= set(headings)
                and set(headings) <= set(HEADERS + OPTIONAL_HEADERS))

    def normalize(self, headings, records):
        # Old exports omitted approaches. Other missing base columns remain errors.
        optional = [name for name in OPTIONAL_HEADERS if name in headings]
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(HEADERS + optional)
        count = 0
        for line, record in enumerate(records, start=2):
            if not any(cell.strip() for cell in record):
                writer.writerow([])  # Preserve source row numbering in validation.
                continue
            if len(record) != len(headings):
                raise CSVValidationError(f'Row {line}: Expected {len(headings)} columns, found {len(record)}.')
            count += 1
            if count > MAX_ROWS:
                raise CSVValidationError(f'Import at most {MAX_ROWS:,} flights at a time.')
            values = dict(zip(headings, record))
            writer.writerow([editable_value(name, values.get(name, '0' if name == 'approaches' else ''), line)
                             for name in HEADERS + optional])
        return output.getvalue()


FORMATS = (Direct2LogbookFormat(),)


def prepare_csv(content):
    if not isinstance(content, str) or len(content.encode('utf-8')) > MAX_BYTES:
        raise CSVValidationError(f'The CSV must be no larger than {MAX_BYTES // (1024 * 1024)} MB.')
    if '\x00' in content:
        raise CSVValidationError('The CSV contains invalid null characters.')
    table = read_source(content)
    headings = [heading(value) for value in table.headers]
    source = next((item for item in FORMATS if item.matches(headings)), None) if not table.source_key else None
    if source is None:
        raise ColumnsNeedMapping('Match the columns in this file before continuing.')
    return source, source.normalize(headings, table.records)
