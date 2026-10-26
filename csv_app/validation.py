import csv
import io
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .formatters import format_route

MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 1000
HEADERS = ['date', 'aircraft', 'registration', 'route', 'duration',
           'pilot in command', 'second in command', 'cross country', 'night',
           'instrument', 'approaches', 'day landing', 'night landing',
           'simulated instrument', 'instructor', 'dual', 'solo', 'simulator', 'remarks']
ALIASES = {'type': 'aircraft', 'aircraft type': 'aircraft', 'reg': 'registration',
           'pic': 'pilot in command', 'sic': 'second in command', 'xc': 'cross country',
           'x country': 'cross country', 'ifr': 'instrument', 'appr': 'approaches',
           'approach': 'approaches', 'day ldg': 'day landing', 'night ldg': 'night landing',
           'sim inst': 'simulated instrument', 'cfi': 'instructor', 'sim': 'simulator'}


class CSVValidationError(ValueError):
    pass


def number(value, integer=False):
    try:
        value = Decimal(value.strip() or '0')
    except InvalidOperation:
        raise CSVValidationError('Numbers must contain a valid numeric value.')
    if not value.is_finite() or value < 0:
        raise CSVValidationError('Numbers must be finite and nonnegative.')
    if integer:
        if value != value.to_integral_value() or value > 2147483647:
            raise CSVValidationError('Counts must be nonnegative whole numbers within the supported range.')
        return int(value)
    if value > Decimal('99.9'):
        raise CSVValidationError('Per-flight hours must not exceed 99.9.')
    return value.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)


def parse_csv(content):
    if not isinstance(content, str) or len(content.encode('utf-8')) > MAX_BYTES:
        raise CSVValidationError('The CSV must be no larger than 2 MB.')
    if '\x00' in content:
        raise CSVValidationError('The CSV contains invalid null characters.')
    try:
        reader = csv.reader(io.StringIO(content.lstrip('\ufeff')), strict=True)
        header = next(reader, None)
        if not header:
            raise CSVValidationError('The CSV is empty or has no header.')
        normalized = []
        for cell in header:
            name = re.sub(r'[_-]+', ' ', cell.strip().lower())
            name = ' '.join(name.split())
            normalized.append(ALIASES.get(name, name))
        legacy = normalized == HEADERS[:10] + HEADERS[11:]
        if normalized != HEADERS and not legacy:
            raise CSVValidationError('Headers must match the displayed 19-column format (or the older 18-column download).')
        rows, preview = [], []
        for line, raw in enumerate(reader, start=2):
            if not any(cell.strip() for cell in raw):
                continue
            try:
                if len(raw) != len(header):
                    raise CSVValidationError(f'Expected {len(header)} columns, found {len(raw)}.')
                if len(rows) >= MAX_ROWS:
                    raise CSVValidationError('Import at most 1,000 flights at a time.')
                raw = [cell.strip() for cell in raw]
                if legacy:
                    raw.insert(10, '0')
                date = None
                for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%m-%d-%Y'):
                    try:
                        date = datetime.strptime(raw[0], fmt).date()
                        break
                    except ValueError:
                        pass
                if date is None:
                    raise CSVValidationError('Use YYYY-MM-DD, MM/DD/YYYY, or MM-DD-YYYY for dates.')
                for index, label, limit in [(1, 'Aircraft type', 4), (2, 'Registration', 10), (3, 'Route', 50)]:
                    if not raw[index] or len(raw[index]) > limit:
                        raise CSVValidationError(f'{label} is required and must be at most {limit} characters.')
                if len(raw[18]) > 500:
                    raise CSVValidationError('Remarks must be at most 500 characters.')
                values = {
                    'date': date, 'aircraft': raw[1], 'registration': raw[2],
                    'route': format_route(raw[3]), 'duration': number(raw[4]),
                    'night': float(number(raw[8])), 'instrument': float(number(raw[9])),
                    'approaches': number(raw[10], integer=True),
                    'landings_day': number(raw[11], integer=True),
                    'landings_night': number(raw[12], integer=True),
                    'simulated_instrument': float(number(raw[13])), 'remarks': raw[18],
                }
                for index, field in [(5, 'pilot_in_command'), (6, 'second_in_command'),
                                     (7, 'cross_country'), (14, 'instructor'),
                                     (15, 'dual'), (16, 'solo'), (17, 'simulator')]:
                    values[field] = number(raw[index]) > 0
                rows.append(values)
                raw[3] = values['route']
                preview.append(raw)
            except CSVValidationError as exc:
                raise CSVValidationError(f'Row {line}: {exc}') from exc
        if not rows:
            raise CSVValidationError('The CSV contains no flights.')
        return rows, preview
    except csv.Error as exc:
        raise CSVValidationError('The CSV has invalid quoting or an oversized field.') from exc
