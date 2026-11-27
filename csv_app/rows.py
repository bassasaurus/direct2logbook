"""Editable, account-owned CSV rows. Validation never saves flight records."""
import copy
import csv
import io
import re
from django.core.exceptions import ValidationError
from flights.models import Aircraft, TailNumber, Flight
from .validation import HEADERS, OPTIONAL_HEADERS, MAX_ROWS, MAX_BYTES, CSVValidationError, number, parse_csv
from .dates import interpret_dates, AmbiguousDates
from .mapping import converted_value
from .airports import normalize_airport_routes
from .validation import role_hour_errors

PAGE_SIZE = 20
NUMERIC = set(range(4, 18))
COUNTS = {10, 11, 12}
MODEL_FIELDS = {'night': 'night', 'instrument': 'instrument', 'simulated_instrument': 'simulated instrument',
                'landings_day': 'day landing', 'landings_night': 'night landing',
                'launch_method': 'launch method', 'duration': 'duration'}


def serialize(header, values):
    output = io.StringIO()
    csv.writer(output).writerows([header, *values])
    return output.getvalue()


def stage_rows(content):
    records = list(csv.reader(io.StringIO(content), strict=True))
    header = records[0]
    rows = []
    for line, values in enumerate(records[1:], 2):
        if not any(value.strip() for value in values):
            continue
        if len(values) != len(header):
            raise CSVValidationError(f'Row {line}: Expected {len(header)} columns, found {len(values)}.')
        rows.append({'line': line, 'original': values[:], 'values': values[:], 'excluded': False, 'edited_fields': []})
    if not rows or len(rows) > MAX_ROWS:
        raise CSVValidationError(f'Include between 1 and {MAX_ROWS:,} flights.')
    return {'header': header, 'rows': rows}


def included_content(data):
    # Preserve source row numbers, including explicitly excluded rows.
    values = []
    by_line = {row['line']: row for row in data['rows']}
    for line in range(2, max(by_line, default=1) + 1):
        row = by_line.get(line)
        values.append(row['values'] if row and not row['excluded'] else [])
    return serialize(data['header'], values)


def validate_rows(user, data, order='auto'):
    errors, typed, valid = {}, [], []
    header = data['header']
    if len(included_content(data).encode('utf-8')) > MAX_BYTES:
        included = next((row for row in data['rows'] if not row['excluded']), None)
        return {included['line']: {'flight': f'The corrected CSV must be no larger than {MAX_BYTES // (1024 * 1024)} MB.'}} if included else {}
    for row in data['rows']:
        if row['excluded']:
            continue
        fields = errors.setdefault(row['line'], {})
        source_issue = data.get('source_errors', {}).get(str(row['line']))
        if source_issue:
            if isinstance(source_issue, dict):
                try:
                    fixed = source_issue.get('kind') == 'device_duration' and number(row['values'][4]) > 0 and number(row['values'][17]) > 0
                except CSVValidationError:
                    fixed = False
                if not fixed:
                    fields['flight'] = source_issue['message']
            else:
                fields['flight'] = source_issue
        values = row['values'][:]
        for index, name in enumerate(header):
            try:
                values[index] = converted_value(name, values[index], row['line'])
                if index in NUMERIC:
                    number(values[index], integer=index in COUNTS)
            except CSVValidationError as exc:
                fields[name] = re.sub(r'^Row \d+: ', '', str(exc))
        try:
            simulator = number(values[17]) > 0
        except CSVValidationError:
            simulator = False
        for index, label, limit in [(1, 'aircraft', 10), (2, 'registration', 10), (3, 'route', 50), (18, 'remarks', 500)]:
            if not values[index].strip() and (index == 1 or index in (2, 3) and not simulator):
                fields[label] = 'Required.'
            elif len(values[index].strip()) > limit:
                fields[label] = f'Use at most {limit} characters.'
        if not values[4].strip():
            fields['duration'] = 'Duration is required.'
        if not any(header[index] in fields for index in (4, 5, 6, 7, 14, 15, 16, 17)):
            fields.update(role_hour_errors(values, number(values[4]), strict=data.get('role_times', False)))
        single = serialize(header, [values])
        try:
            try:
                interpreted, _ = interpret_dates(single, order if order in ('mdy', 'dmy') else 'auto')
            except AmbiguousDates:
                interpreted, _ = interpret_dates(single, 'mdy')  # Only provisional; the Dates step still requires a choice.
        except CSVValidationError as exc:
            fields['date'] = re.sub(r'^Row \d+: ', '', str(exc))
            continue
        try:
            parsed, _ = parse_csv(interpreted)
        except CSVValidationError as exc:
            message = re.sub(r'^Row \d+: ', '', str(exc))
            if not fields:
                prefix = message.split(':',1)[0].lower()
                missing_device = {'Select device type.':'device type', 'Device ID required.':'device id',
                                  'Select BATD or AATD.':'atd type'}
                fields[prefix if prefix in header else missing_device.get(message,'flight')] = (
                    message.split(':',1)[1].strip() if prefix in header else message)
            continue
        if not fields:
            typed.append(parsed[0])
            valid.append((row, list(csv.reader(io.StringIO(interpreted)))[1]))
    # Check all routes with the existing batched airport resolver.
    if valid:
        records = [[] for _ in range(max(row['line'] for row, _ in valid) - 1)]
        for row, values in valid:
            records[row['line'] - 2] = values
        route_errors = {}
        normalize_airport_routes(serialize(header, records), typed, errors=route_errors)
        for line, message in route_errors.items():
            errors.setdefault(line, {})['route'] = message
        aircraft = {a.aircraft_type.casefold(): a for a in Aircraft.objects.filter(user=user)}
        tails = {t.registration.casefold(): t for t in TailNumber.objects.filter(user=user)}
        for (row, _), values in zip(valid, typed):
            a = aircraft.get(values['aircraft'].casefold())
            t = tails.get(values['registration'].casefold())
            # Missing/conflicting account records belong in the Records step.
            if not a or values['registration'] and (not t or t.aircraft_id != a.pk):
                continue
            fields = errors.setdefault(row['line'], {})
            flight_values = {key: value for key, value in values.items() if key not in ('aircraft', 'registration', 'approaches', 'approach_details')}
            flight = Flight(user=user, aircraft_type=a, registration=t, **flight_values)
            from .flight_rules import flight_errors
            for field, message in flight_errors(values, a, t).items():
                fields[MODEL_FIELDS.get(field, field.replace('_', ' '))] = message
            try:
                flight.full_clean(exclude=['user', 'aircraft_type', 'registration', 'route_data', 'app_markers', 'app_polylines'],
                                  validate_unique=False, validate_constraints=False)
            except ValidationError as exc:
                for field, messages in exc.message_dict.items():
                    fields[MODEL_FIELDS.get(field, field.replace('_', ' '))] = '; '.join(messages)
            if values.get('device_type') or values.get('device_id') or values.get('instrument_credit_eligible'):
                from flights.simulator_validation import validate_simulator_entry
                for field, message in validate_simulator_entry(values, aircraft_category=a.aircraft_category).items():
                    fields[MODEL_FIELDS.get(field, field.replace('_', ' '))] = message
    errors = {line: fields for line, fields in errors.items() if fields}
    # File-wide mixed numeric dates must also be corrected; do not silently guess.
    if not errors and typed:
        try:
            interpret_dates(included_content(data), order if order in ('mdy', 'dmy') else 'auto')
        except AmbiguousDates:
            pass
        except CSVValidationError as exc:
            match = re.match(r'Row (\d+): (.*)', str(exc))
            if match:
                errors.setdefault(int(match[1]), {})['date'] = match[2]
            else:
                raise
    return errors


def normalize_values(data):
    data = copy.deepcopy(data)
    for row in data['rows']:
        if not row['excluded']:
            row['values'] = [converted_value(name, value, row['line']) for name, value in zip(data['header'], row['values'])]
    return data


def validate_import_requirements(batch, user):
    """Check required/model values without rerunning airport matching or saving."""
    parsed, _ = parse_csv(batch.content)
    aircraft = {item.aircraft_type.casefold(): item for item in Aircraft.objects.filter(user=user)}
    tails = {item.registration.casefold(): item for item in TailNumber.objects.filter(user=user)}
    raw_rows = [(line, row) for line, row in enumerate(csv.reader(io.StringIO(batch.content)), 1)
                if line > 1 and any(value.strip() for value in row)]
    for (line, raw), values in zip(raw_rows, parsed):
        role_errors = role_hour_errors(raw, values['duration'], strict=batch.source_metadata.get('role_times', False))
        if role_errors:
            raise CSVValidationError(f'Row {line}: {"; ".join(role_errors.values())} Correct or exclude this row before importing.')
        attrs = {name: value for name, value in values.items() if name not in ('aircraft', 'registration', 'approaches', 'approach_details')}
        flight = Flight(user=user, aircraft_type=aircraft.get(values['aircraft'].casefold()),
                        registration=tails.get(values['registration'].casefold()), **attrs)
        from .flight_rules import flight_errors
        required_errors = flight_errors(values, aircraft.get(values['aircraft'].casefold()), tails.get(values['registration'].casefold()))
        if required_errors:
            raise CSVValidationError(f'Row {line}: {"; ".join(required_errors.values())} Correct or exclude this row before importing.')
        # Account references are resolved by Records; their snapshot is checked separately.
        try:
            flight.full_clean(exclude=['user', 'aircraft_type', 'registration', 'route_data', 'app_markers', 'app_polylines'],
                              validate_unique=False, validate_constraints=False)
        except ValidationError as exc:
            raise CSVValidationError(f'Row {line}: {"; ".join(exc.messages)} Correct or exclude this row before importing.') from exc
