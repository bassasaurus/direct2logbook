"""Evidence-backed source readers. Product names are internal, never UI choices.

Sources and deliberate limitations are documented in RELIABILITY.md. Original
columns stay available for user confirmation; derived columns have plain labels.
"""
import csv
import io
import re
from collections import Counter
from decimal import Decimal, InvalidOperation

from .validation import CSVValidationError, MAX_BYTES, MAX_ROWS
from .approaches import approach_details, format_approaches


def key(value):
    return re.sub(r'[^a-z0-9]', '', value.casefold())


# Match only distinctive native keys; a filename or a lone 'Date' is not a signature.
SIGNATURES = (
    ('logten', {'flightflightdate', 'aircraftaircraftid'}),
    ('logten', {'flightflightdate', 'flightselectedaircraftid', 'flightselectedaircrafttype'}),
    ('safelog', {'date', 'aircrafttype', 'aircraftregistration', 'durationofflight', 'instrumentapproaches'}),
    ('logbook-pro', {'aircraftmakemodel', 'aircraftident', 'routeofflight'}),
    ('logbook-pro', {'date', 'aircrafttype', 'aircraftident', 'route', 'duration'}),
    ('myflightbook', {'date', 'tailnumber', 'totalflighttime'}),
    ('logbook-pro', {'date', 'type', 'ident', 'route', 'duration'}),
    ('logbook-pro', {'date', 'aircrafttype', 'ident', 'route', 'duration'}),
)
ALIASES = {
    'logten': {
        'flightflightdate': 'date', 'aircrafttypetype': 'aircraft',
        'flightselectedaircraftid': 'registration', 'flightselectedaircrafttype': 'aircraft',
        'aircraftaircraftid': 'registration', 'flighttotaltime': 'duration',
        'flightpic': 'pilot in command', 'flightsic': 'second in command',
        'flightcrosscountry': 'cross country', 'flightnight': 'night',
        'flightactualinstrument': 'instrument', 'flightsimulatedinstrument': 'simulated instrument',
        'flightdaylandings': 'day landing', 'flightnightlandings': 'night landing',
        'flightdualreceived': 'dual', 'flightdualgiven': 'instructor', 'flightsolo': 'solo',
        'flightsimulator': 'simulator', 'flightremarks': 'remarks', 'flighttotalapproaches': 'approaches',
        'flightfrom': 'departure', 'flightto': 'destination', 'flightroute': 'route',
    },
    'logbook-pro': {
        'aircraftmakemodel': 'aircraft', 'aircraftident': 'registration', 'ident': 'registration', 'routeofflight': 'route',
        'landingsday': 'day landing', 'landingsnight': 'night landing', 'fltsim': 'simulator',
        'dualreceived': 'dual', 'dualgiven': 'instructor',
        'actualinstrument': 'instrument', 'simulatedinstrument': 'simulated instrument',
        'flightsimulator': 'simulator', 'daylandings': 'day landing', 'nightlandings': 'night landing',
    },
    'myflightbook': {
        'model': 'aircraft', 'totalflighttime': 'duration', 'imc': 'instrument',
        'fsdaylandings': 'day landing', 'fsnightlandings': 'night landing',
        'groundsimulator': 'simulator', 'dualreceived': 'dual',
    },
    'foreflight': {
        'aircraftid': 'registration', 'actualinstrument': 'instrument', 'dualgiven': 'instructor',
        'dualreceived': 'dual', 'simulatedflight': 'simulator', 'pilotcomments': 'remarks',
        'daylandingsfullstop': 'day landing', 'nightlandingsfullstop': 'night landing',
    },
    'safelog': {'durationofflight':'duration', 'instrumentapproaches':'approaches'},
}


def read_delimited(content):
    if not isinstance(content, str) or len(content.encode('utf-8')) > MAX_BYTES:
        raise CSVValidationError(f'Use a CSV or TSV no larger than {MAX_BYTES // (1024 * 1024)} MB.')
    if '\x00' in content:
        raise CSVValidationError('The file contains invalid null characters.')
    content = content.lstrip('\ufeff')
    # Compare parsed headers, never punctuation in data/remarks. Sectioned files
    # have a flight header below their preamble and aircraft metadata.
    candidates = []
    for delimiter in (',', '\t', ';'):
        try:
            reader = csv.reader(io.StringIO(content), delimiter=delimiter, strict=True)
            sample = []
            for _, record in zip(range(40), reader):
                if any(value.strip() for value in record):
                    sample.append(record)
            native_headers = [row for row in sample if
                {'date', 'aircraftid'} <= {key(value) for value in row}]
            header = native_headers[-1] if native_headers else sample[0] if sample else []
            score = len(header)
            candidates.append((score, delimiter))
        except csv.Error:
            continue
    if not candidates:
        raise CSVValidationError('The file has invalid quoting or an oversized field.')
    # A tied multi-column parse needs a deliberate correction, not a guessed delimiter.
    best = max(score for score, _ in candidates)
    winners = [delimiter for score, delimiter in candidates if score == best]
    if best > 1 and len(winners) != 1:
        raise CSVValidationError('The column separator is unclear. Save as UTF-8 comma-separated CSV or tab-separated TSV.')
    delimiter = winners[0] if best > 1 else ','
    try:
        return list(csv.reader(io.StringIO(content), delimiter=delimiter, strict=True)), delimiter
    except csv.Error as exc:
        raise CSVValidationError('The file has invalid quoting or an oversized field.') from exc


def source_kind(headers):
    names = {key(name) for name in headers}
    return next((name for name, signature in SIGNATURES if signature <= names), '')


def trim_padding(row):
    row = row[:]
    while row and not row[-1].strip():
        row.pop()
    return row


def foreflight_tables(records):
    section = None
    aircraft_header = flight_header = None
    aircraft = {}
    ambiguous = set()
    flights = []
    for line, raw in enumerate(records, 1):
        row = trim_padding(raw)
        if not row:
            continue
        first = row[0].strip().casefold()
        if first == 'aircraft table':
            section = 'aircraft'
            continue
        if first.startswith('flights table'):
            section = 'flights'
            continue
        names = [key(cell) for cell in row]
        if section == 'aircraft':
            if 'aircraftid' in names and ('typecode' in names or 'model' in names):
                aircraft_header = names
                continue
            if not aircraft_header or first in ('text', 'date'):
                continue
            if len(row) > len(aircraft_header):
                raise CSVValidationError(f'Row {line}: Aircraft table columns do not match the header.')
            item = dict(zip(aircraft_header, row))
            registration = item.get('aircraftid', '').strip().casefold()
            if registration in aircraft and aircraft[registration] != item:
                ambiguous.add(registration)
            aircraft[registration] = item
        elif section == 'flights':
            if 'date' in names and 'aircraftid' in names:
                flight_header = row
                continue
            if not flight_header or first in ('date', 'text'):
                continue
            if len(raw) > len(flight_header) and any(value.strip() for value in raw[len(flight_header):]):
                raise CSVValidationError(f'Row {line}: Flight table columns do not match the header.')
            # Spreadsheet saves often pad aircraft/flight sections to a shared width.
            values = raw[:len(flight_header)] + [''] * max(0, len(flight_header) - len(raw))
            flights.append((line, values))
    if not flight_header or not flights:
        raise CSVValidationError('The file has no readable flight table.')
    output = [[] for _ in range(max(line for line, _ in flights) - 1)]
    for line, values in flights:
        output[line - 2] = values
    return flight_header, output, aircraft, ambiguous


def full_route(origin, intermediate, destination):
    split = lambda value: [part for part in re.split(r'[\s-]+', value.strip().upper()) if part]
    route, start, end = split(intermediate), split(origin), split(destination)
    if not route:
        # Equal endpoints still describe a local flight (AXH-AXH), not one stop.
        return '-'.join(start + end)
    if start and route[:len(start)] != start:
        route = start + route
    if end and route[-len(end):] != end:
        route += end
    return '-'.join(route)


def is_positive(value):
    try:
        return Decimal(value.strip() or '0') > 0
    except InvalidOperation:
        return ':' in value and any(character in '123456789' for character in value)


def foreflight_approaches(cells):
    """Convert #;type;runway;airport;comments;circle, retaining source details.

    Unsupported/ambiguous types remain editable errors in the Rows step. Never
    infer a minima line from generic RNAV or select one side of ILS OR LOC.
    """
    details, notes, invalid = [], [], []
    aliases = {'RNAVGPS': 'RNAV', 'ASRSRA': 'ASR'}
    for name, value in cells:
        if not value.strip():
            continue
        parts = [part.strip() for part in value.split(';')]
        try:
            if len(parts) < 2 or len(parts) > 6 or not re.fullmatch(r'\d+', parts[0]):
                raise CSVValidationError('Invalid structured approach.')
            kind = aliases.get(key(parts[1]).upper(), parts[1])
            if not kind:
                raise CSVValidationError('Missing approach type.')
            details.extend(approach_details(f'{kind}: {parts[0]}'))
        except CSVValidationError:
            invalid.append(f'{name}: {value}')
        # Runway, airport, comments and circling have no separate model fields.
        # Keep malformed source values too, so correcting a type loses no data.
        notes.append(f'{name}: {value}')
    if invalid:
        return '', '; '.join(filter(None, [format_approaches(details), 'Review ' + ' | '.join(invalid)])), notes
    combined = approach_details(format_approaches(details)) if details else []
    return str(sum(item['number'] for item in combined)), format_approaches(combined), notes


def adapt_source(headers, records, kind, aircraft=None, ambiguous=()):
    """Append derived columns, retaining every source value for review."""
    headers = headers[:]
    counts = Counter(key(name) for name in headers)
    indexes = {key(name): index for index, name in enumerate(headers) if counts[key(name)] == 1}
    aliases = ALIASES.get(kind, {})
    derived = {}
    issues = {}
    notices = []
    if kind:
        notices.append('Flight columns recognized. Check the suggested matches and any unused columns.')
    def index_for(target):
        # Explicit native semantics win over superficially similar names, e.g. IFR vs actual IMC.
        explicit = [i for name, i in indexes.items() if aliases.get(name) == target]
        return explicit[0] if len(explicit) == 1 else None
    if kind == 'logten':
        origin, destination, route = (indexes.get(name) for name in ('flightfrom', 'flightto', 'flightroute'))
    elif kind in ('foreflight', 'myflightbook', 'safelog'):
        origin, destination, route = (indexes.get(name) for name in ('from', 'to', 'route'))
    else:
        origin = destination = route = None
    route_key = 'flightroute' if kind == 'logten' else 'route'
    combine = origin is not None and destination is not None and counts[route_key] <= 1
    if combine:
        derived['Complete Route'] = 'route'
    if kind == 'foreflight':
        derived.update({'Matched Aircraft Type': 'aircraft', 'Flight Registration': 'registration',
                        'Training Device Type': 'device type', 'Training Device ID': 'device id', 'ATD Level': 'atd type'})
        notices.append('Aircraft information was matched by registration. Missing or conflicting types need your review.')
    approach_columns = [(name, index) for name, index in indexes.items()
                        if kind == 'foreflight' and re.fullmatch(r'approach[1-9]\d*', name)]
    if kind == 'foreflight' and any(re.fullmatch(r'approach[1-9]\d*', name) and count > 1
                                   for name, count in counts.items()):
        raise CSVValidationError('Approach column names must be unique. Rename duplicate Approach columns before uploading.')
    if approach_columns:
        derived.update({'Structured Approach Count': 'approaches', 'Structured Approach Types': 'approach types',
                        'Comments and Approach Details': 'remarks'})
        notices.append('Approach counts and supported types are combined. Runway, airport, comments and circling details are retained in Remarks. Ambiguous types need correction.')
    full_stop_index = indexes.get('nightlandingsfullstop') if kind == 'foreflight' else indexes.get('fsnightlandings') if kind == 'myflightbook' else None
    if full_stop_index is not None:
        derived['Night Full Stop Confirmed'] = 'night full stop'
    if kind == 'myflightbook':
        if 'tailnumber' in indexes and 'groundsimulator' in indexes:
            derived['Flight Registration'] = 'registration'
            notices.append('SIM identifies a training device, not an aircraft tailnumber. Complete its device details before importing.')
        if 'landings' in indexes and any(name in indexes for name in ('fsdaylandings', 'fsnightlandings')):
            notices.append('Full-stop day/night landing counts are matched. Total Landings includes other landings; review any differences before importing.')
    duration = next((indexes[name] for name in ('totaltime', 'totalflighttime', 'flighttotaltime', 'duration', 'durationofflight') if name in indexes), None)
    simulator = index_for('simulator')
    if simulator is None and kind == 'logbook-pro':
        simulator = indexes.get('simulator')
    if simulator is None and kind == 'safelog':
        simulator = indexes.get('simulatorftd')
    duplicate_duration = any(counts[name] > 1 for name in ('totaltime', 'totalflighttime', 'flighttotaltime', 'duration', 'durationofflight'))
    if kind and not duplicate_duration and (duration is not None or simulator is not None):
        derived['Entry Duration'] = 'duration'
        derived['Device Time'] = 'simulator'
    if kind == 'logbook-pro':
        notices.append('Each included row creates one entry. Grouped daily routes stay together; leg counts do not split hours into separate flights.')
    new_names = list(derived)
    for line, row in enumerate(records, 2):
        if not any(cell.strip() for cell in row):
            continue
        get = lambda index: row[index] if index is not None else ''
        extra = {}
        if full_stop_index is not None:
            extra['Night Full Stop Confirmed'] = 'Yes' if is_positive(get(full_stop_index)) else 'No'
        if combine:
            extra['Complete Route'] = full_route(get(origin), get(route), get(destination))
        is_device = False
        if kind == 'foreflight':
            if approach_columns:
                total, types, notes = foreflight_approaches([(headers[index], get(index)) for _, index in approach_columns])
                extra.update({'Structured Approach Count': total, 'Structured Approach Types': types,
                              'Comments and Approach Details': ' | '.join(filter(None, [get(indexes.get('pilotcomments')), *notes]))})
            registration = get(indexes.get('aircraftid')).strip()
            item = (aircraft or {}).get(registration.casefold(), {}) if registration.casefold() not in ambiguous else {}
            equipment = item.get('equipmenttype', 'aircraft').strip().upper()
            is_device = equipment in ('FFS', 'FTD', 'BATD', 'AATD')
            extra.update({'Matched Aircraft Type': item.get('typecode') or item.get('model', ''),
                'Flight Registration': '' if is_device else registration,
                'Training Device Type': 'ATD' if equipment in ('BATD', 'AATD') else equipment if is_device else '',
                'Training Device ID': registration if is_device else '',
                'ATD Level': equipment if equipment in ('BATD', 'AATD') else ''})
            if equipment not in ('AIRCRAFT', '', 'FFS', 'FTD', 'BATD', 'AATD'):
                issues[str(line)] = 'Unrecognized equipment type. Exclude this row or correct the source file.'
        if kind == 'myflightbook' and 'Flight Registration' in derived:
            registration = get(indexes['tailnumber']).strip()
            extra['Flight Registration'] = '' if registration.casefold() == 'sim' and is_positive(get(simulator)) else registration
        if kind == 'logten' and 'flighttype' in indexes:
            entry_type = get(indexes['flighttype']).strip()
            if entry_type not in ('', '0', '3'):
                issues[str(line)] = 'This entry is not a flight or training session. Exclude it before importing.'
            is_device = entry_type == '3'
        if 'Entry Duration' in derived:
            total, sim = get(duration), get(simulator)
            extra['Entry Duration'] = sim if not is_positive(total) and is_positive(sim) else total
            extra['Device Time'] = sim if is_positive(sim) else total if is_device else sim
        if is_device and not is_positive(extra.get('Entry Duration', '')):
            issues[str(line)] = {'kind': 'device_duration', 'message': 'Enter Duration and Sim hours for this training session.'}
        row.extend(extra.get(name, '') for name in new_names)
    headers.extend(new_names)
    return headers, records, {len(headers) - len(new_names) + i: target for i, target in enumerate(derived.values())}, notices, issues
