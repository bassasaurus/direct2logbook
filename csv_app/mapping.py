"""Conservative, provider-neutral column matching before date interpretation."""
import csv
import io
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from datetime import datetime

from .validation import ALIASES, HEADERS, OPTIONAL_HEADERS, MAX_BYTES, MAX_ROWS, CSVValidationError

MAPPING_FIELDS = HEADERS + OPTIONAL_HEADERS + ['departure', 'destination', 'block out', 'block in']
REQUIRED_FIELDS = ('date', 'aircraft', 'duration')
BASIC_FIELDS = ('date', 'aircraft', 'registration', 'duration', 'route', 'departure', 'destination')
LABELS = {'date': 'Date', 'aircraft': 'Aircraft Type', 'registration': 'Tailnumber',
          'duration': 'Duration', 'instrument': 'Actual Instrument', 'departure': 'Departure Airport',
          'destination': 'Destination Airport', 'pilot in command': 'PIC', 'second in command': 'SIC',
          'instructor': 'CFI', 'atd type': 'ATD Type', 'device id': 'Device ID'}
SELECTION_FIELDS = {'pilot in command', 'second in command', 'cross country', 'instructor',
                    'dual', 'solo', 'simulator', 'instrument credit eligible'}
HOUR_FIELDS = {'duration', 'night', 'instrument', 'simulated instrument'} | (SELECTION_FIELDS - {'instrument credit eligible'})


def key(value):
    return re.sub(r'[^a-z0-9]', '', value.lower())


MATCHES = {key(name): name for name in MAPPING_FIELDS}
MATCHES.update({key(alias): name for alias, name in ALIASES.items()})
MATCHES.update({key(alias): name for name, aliases in {
    'date': ['Flight Date', 'Date of Flight', 'Log Date'],
    'aircraft': ['Aircraft Model', 'AircraftType', 'AC Type'],
    'registration': ['Tail Number', 'Tail No', 'Aircraft Registration', 'Aircraft ID', 'Registration Number'],
    'duration': ['Total Time', 'Flight Time', 'Total Duration', 'Block Time', 'Duration of Flight'],
    'departure': ['From', 'Origin', 'Departure Airport', 'Airport From', 'Departure ICAO', 'Departure IATA',
                  'Departure FAA', 'Dep ICAO', 'Dep IATA', 'Dep FAA'],
    'destination': ['To', 'Destination Airport', 'Arrival Airport', 'Airport To', 'Arrival',
                    'Destination ICAO', 'Destination IATA', 'Destination FAA', 'Arrival ICAO',
                    'Arrival IATA', 'Arrival FAA', 'Arr ICAO', 'Arr IATA', 'Arr FAA'],
    'block out': ['Out', 'Block Out Time', 'Gate Out', 'Out Time', 'Flight Out'],
    'block in': ['In', 'Block In Time', 'Gate In', 'In Time', 'Flight In'],
    'day landing': ['Day Landings', 'Day Landing Count'],
    'night landing': ['Night Landings', 'Night Landing Count'],
    'simulated instrument': ['Hood', 'Simulated Instrument Time'],
    'remarks': ['Comments', 'Notes'],
    'holding': ['Hold', 'Holds', 'Holding Performed', 'flight_holds'],
    'approach types': ['Approach Type', 'Approach Details', 'Instrument Approach Types'],
    'approaches': ['Instrument Approaches'],
    'dual': ['Dual Received'], 'instructor': ['Dual Given', 'Flight Instructor'],
    'instrument': ['Actual Instrument'],
    'device type': ['Training Device Type', 'Simulator Type'], 'device id': ['Training Device ID'],
    'simulator': ['Simulator / FTD'],
    'night full stop': ['Full Stop', 'Night Full Stop Confirmed'],
}.items() for alias in aliases})


@dataclass
class SourceTable:
    headers: list
    records: list
    source_key: str = ''
    delimiter: str = ','
    derived: dict = field(default_factory=dict)
    notices: list = field(default_factory=list)
    source_errors: dict = field(default_factory=dict)

    @property
    def dependencies(self):
        lookup = {}
        for index, name in enumerate(self.headers):
            lookup.setdefault(key(name), []).append(index)
        definitions = {
            'completeroute': ('flightfrom', 'flightroute', 'flightto') if self.source_key == 'logten' else ('from', 'route', 'to'),
            'entryduration': ('totaltime', 'totalflighttime', 'flighttotaltime', 'duration', 'durationofflight', 'flightsimulator', 'groundsimulator', 'simulator', 'simulatorftd', 'fltsim', 'simulatedflight'),
            'devicetime': ('totaltime', 'totalflighttime', 'flighttotaltime', 'duration', 'durationofflight', 'flightsimulator', 'groundsimulator', 'simulator', 'simulatorftd', 'fltsim', 'simulatedflight', 'flighttype'),
            'matchedaircrafttype': ('aircraftid', 'tailnumber'),
            'flightregistration': ('tailnumber', 'groundsimulator') if self.source_key == 'myflightbook' else ('aircraftid',), 'trainingdevicetype': ('aircraftid',),
            'trainingdeviceid': ('aircraftid',), 'atdlevel': ('aircraftid',),
            'nightfullstopconfirmed': ('nightlandingsfullstop','fsnightlandings'),
        }
        approach_names = tuple(name for name in lookup if re.fullmatch(r'approach[1-9]\d*', name))
        definitions.update({'structuredapproachcount': approach_names,
                            'structuredapproachtypes': approach_names,
                            'commentsandapproachdetails': ('pilotcomments',) + approach_names})
        return {str(index): [dependency for name in definitions.get(key(self.headers[index]), ())
                            for dependency in lookup.get(name, []) if len(lookup.get(name, [])) == 1]
                for index in self.derived}

    def consumed_columns(self, used):
        used = {str(index) for index in used}
        for index in list(used):
            used.update(str(dependency) for dependency in self.dependencies.get(index, []))
        return used

    @property
    def role_times(self):
        if self.source_key:
            return True
        # Preserve the old canonical template's numeric 0/1 checkbox contract.
        # Other mapped exports use numeric role hours; literal Yes/True values
        # still become full-duration selections in normalize_mapping.
        names = [key(name) for name in self.headers]
        current = [key(name) for name in HEADERS]
        legacy = [key(name) for name in HEADERS[:10] + HEADERS[11:]]
        return names[:len(current)] != current and names[:len(legacy)] != legacy

    @property
    def needs_time_units(self):
        suggestions = self.suggestions()
        fields = HOUR_FIELDS if self.source_key else {'duration', 'night', 'instrument', 'simulated instrument'}
        for name in fields:
            index = suggestions.get(name)
            if index is None:
                continue
            for row in self.records:
                if not any(value.strip() for value in row):
                    continue
                value = row[index].strip()
                if re.fullmatch(r'-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?', value) and Decimal(value) > 0:
                    if self.source_key or '.' not in value:
                        return True
        return False

    @property
    def row_count(self):
        return sum(any(value.strip() for value in row) for row in self.records)

    def samples(self, index):
        values = []
        for row in self.records:
            if any(value.strip() for value in row) and row[index].strip() and row[index].strip() not in values:
                values.append(row[index].strip())
            if len(values) == 3:
                break
        return [value[:80] for value in values]

    @property
    def column_formats(self):
        formats = {}
        for index in range(len(self.headers)):
            values = [row[index].strip() for row in self.records if any(row)]
            formats[str(index)] = {
                'hhmm': any(re.fullmatch(r'\d{1,3}:[0-5]\d', value) for value in values),
                'numeric': any(re.fullmatch(r'-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?', value) and Decimal(value) > 0 for value in values),
                'fractional': any(re.fullmatch(r'\d+\.\d+', value) and Decimal(value) > 0 for value in values),
                'over30': any(re.fullmatch(r'\d+(?:\.\d+)?', value) and Decimal(value) > 30 for value in values),
                'samples': self.samples(index),
                'whole': any(re.fullmatch(r'\d+', value) and Decimal(value) > 0 for value in values),
            }
        return formats

    def candidates(self):
        from .adapters import ALIASES as SOURCE_ALIASES
        candidates = {}
        aliases = SOURCE_ALIASES.get(self.source_key, {})
        for index, header in enumerate(self.headers):
            target = aliases.get(key(header), MATCHES.get(key(header)))
            if self.source_key and key(header) == 'ifr':
                target = None  # Flight rules are not actual instrument conditions.

            if key(header) in ('departure', 'arrival'):
                samples = self.samples(index)
                if not samples or not all(re.fullmatch(r'[A-Za-z0-9]{2,5}', value) and re.search(r'[A-Za-z]', value) for value in samples):
                    continue  # These headings may refer to times rather than airports.
            if target:
                candidates.setdefault(target, []).append(index)
        return candidates

    def suggestions(self):
        candidates = self.candidates()
        suggestions = {target: indexes[0] for target, indexes in candidates.items() if len(indexes) == 1}
        for target in ('departure', 'destination'):
            indexes = candidates.get(target, [])
            for kind in ('icao', 'iata', 'faa'):
                explicit = [index for index in indexes if kind in key(self.headers[index]) and self.samples(index)]
                if len(explicit) == 1:
                    suggestions[target] = explicit[0]
                    break
                if explicit:
                    break
        for index, target in self.derived.items():
            suggestions[target] = index
        if 'route' in suggestions:
            suggestions.pop('departure', None)
            suggestions.pop('destination', None)
        return suggestions


def read_source(content, user=None):
    from .adapters import read_delimited, source_kind, foreflight_tables, adapt_source
    parsed, delimiter = read_delimited(content)
    if not parsed or not parsed[0]:
        raise CSVValidationError('The CSV is empty or has no header.')
    sectioned = any(row and row[0].strip().casefold() in ('aircraft table', 'flights table') for row in parsed[:40])
    aircraft, ambiguous = {}, set()
    if sectioned:
        headers, records, aircraft, ambiguous = foreflight_tables(parsed)
        kind = 'foreflight'
    else:
        headers, records = parsed[0], parsed[1:]
        kind = source_kind(headers)
    if len(headers) > (500 if kind else 100):
        raise CSVValidationError('Use a file with at most 500 recognized columns or 100 generic columns.')
    count = 0
    for line, row in enumerate(records, 2):
        if any(value.strip() for value in row):
            if len(row) != len(headers):
                raise CSVValidationError(f'Row {line}: Expected {len(headers)} columns, found {len(row)}.')
            count += 1
            if count > MAX_ROWS:
                raise CSVValidationError(f'Import at most {MAX_ROWS:,} flights at a time.')
    if not count:
        raise CSVValidationError('The CSV contains no flights.')
    headers, records, derived, notices, issues = adapt_source(headers, records, kind, aircraft, ambiguous)
    table = SourceTable(headers, records, kind, delimiter, derived, notices, issues)
    if kind == 'myflightbook':
        model_indexes = [i for i, name in enumerate(headers) if key(name) == 'model']
        model_index = model_indexes[0] if len(model_indexes) == 1 else None
        tail_indexes = [i for i, name in enumerate(headers) if key(name) == 'tailnumber']
        tail_index = tail_indexes[0] if len(tail_indexes) == 1 else None
        if tail_index is not None and not table.candidates().get('aircraft'):
            owned = {}
            if user is not None:
                from flights.models import TailNumber
                owned = {tail.registration.casefold(): tail.aircraft.aircraft_type
                         for tail in TailNumber.objects.filter(user=user).select_related('aircraft')}
            table.derived[len(headers)] = 'aircraft'
            table.headers.append('Matched Aircraft Type')
            for row in table.records:
                if any(row):
                    row.append(owned.get(row[tail_index].strip().casefold(), ''))
            table.notices.append('Missing aircraft types are looked up from tailnumbers in your account. Unmatched types need your review.')
    return table


def converted_value(field, value, line):
    if field == 'remarks':
        return value
    value = value.strip()
    if field == 'date' and re.fullmatch(r'\d{4}/\d{1,2}/\d{1,2}', value):
        try:
            return datetime.strptime(value, '%Y/%m/%d').date().isoformat()
        except ValueError:
            return value

    if field in SELECTION_FIELDS and value.lower() in ('true', 'false', 'yes', 'no'):
        return '1' if value.lower() in ('true', 'yes') else '0'
    if field in HOUR_FIELDS and ':' in value:
        match = re.fullmatch(r'(\d{1,3}):([0-5]\d)', value)
        if not match:
            raise CSVValidationError(f'Row {line}: Use decimal hours or HH:MM for {LABELS.get(field, field)}.')
        return str(Decimal(match[1]) + Decimal(match[2]) / 60)
    return value


def editable_value(field, value, line):
    try:
        return converted_value(field, value, line)
    except CSVValidationError:
        return value.strip()


def normalize_mapping(table, mapping, time_units='hours', allow_short_years=False, allow_overnight=False):
    if time_units not in ('hours', 'minutes'):
        raise CSVValidationError('Choose decimal hours or minutes for numeric times.')
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(HEADERS + OPTIONAL_HEADERS)
    for line, record in enumerate(table.records, start=2):
        if not any(value.strip() for value in record):
            writer.writerow([])
            continue
        values = {name: editable_value(name, str(item['value']) if 'value' in item else record[item['column']], line)
                  for name, item in mapping.items() if 'calculated' not in item}
        if allow_short_years and 'date' in values:
            match = re.fullmatch(r'(\d{1,2})([/\-])(\d{1,2})\2(\d{2})', values['date'])
            if match:
                year = datetime.strptime(match[4], '%y').year
                values['date'] = f'{match[1]}{match[2]}{match[3]}{match[2]}{year}'
        if time_units == 'minutes':
            for name in (HOUR_FIELDS if table.role_times else {'duration', 'night', 'instrument', 'simulated instrument'}):
                item = mapping.get(name)
                original = (str(item['value']) if 'value' in item else record[item['column']]).strip() if item and 'calculated' not in item else ''
                if original and ':' not in original and original.lower() not in ('true', 'false', 'yes', 'no'):
                    try:
                        values[name] = str(Decimal(original) / 60)
                    except InvalidOperation:
                        pass  # Retain invalid input for row corrections.
        if mapping.get('duration', {}).get('calculated') == 'block_times':
            from .block_times import elapsed_hours
            try:
                values['duration'] = str(elapsed_hours(values.get('block out', ''), values.get('block in', ''), allow_overnight))
            except CSVValidationError as exc:
                values['duration'] = str(exc)  # Rows can correct Duration or exclude the entry.
        if not values.get('route') and (values.get('departure') or values.get('destination')):
            values['route'] = f"{values['departure']}-{values['destination']}"
        for name in ('pilot in command','second in command','cross country','instructor','dual','solo'):
            item = mapping.get(name, {})
            original = str(item.get('value', record[item['column']] if 'column' in item else '')).strip().lower()
            if original in ('true','yes') or (not table.role_times and original in ('1','1.0')):
                values[name] = values.get('duration', '')
        writer.writerow([values.get(name, '') for name in HEADERS + OPTIONAL_HEADERS])
    return output.getvalue()


def source_record_choices(table, mapping=None):
    """Keep aircraft/registration choices from the file after canonical mapping."""
    mapping = mapping or {}
    candidates = table.candidates()
    aircraft, pairs = {}, {}
    def values_for(name, record):
        selected = mapping.get(name, {})
        value = str(selected['value']) if 'value' in selected else record[selected['column']] if 'column' in selected else ''
        if value.strip():
            return [value.strip()]
        return list(dict.fromkeys(record[index].strip() for index in candidates.get(name, [])
                                 if index not in table.derived and record[index].strip()))
    for record in table.records:
        if not any(record):
            continue
        types = values_for('aircraft', record)
        registrations = values_for('registration', record)
        for designator in types:
            key = designator.casefold()
            aircraft.setdefault(key, designator)
            pair = pairs.setdefault(key, {})
            for registration in registrations:
                pair.setdefault(registration.casefold(), registration)
    return {'aircraft': list(aircraft.values()), 'tailnumbers': {key: list(values.values()) for key, values in pairs.items()}}
