"""Resolve route occurrences by airport country, never by the visitor's location."""
import re

from django.db.models import Q

from flights.models import MapData

ROUTABLE_CODE_KINDS = ('icao', 'iata', 'faa', 'legacy')


FACILITY_LABELS = {
    'large_airport': 'Large airport',
    'medium_airport': 'Medium airport',
    'small_airport': 'Small airport',
    'heliport': 'Heliport',
    'seaplane_base': 'Seaplane base',
    'balloonport': 'Balloonport',
    'closed': 'Closed facility',
}


def airport_choice_label(airport):
    """Describe a candidate consistently without treating legacy codes as IATA."""
    location = ', '.join(dict.fromkeys(value.strip() for value in
        (airport.city, airport.state, airport.country) if value.strip()))
    identifiers = []
    if airport.icao:
        identifiers.append('ICAO ' + airport.icao)
    aliases = list(airport.codes.all())
    for kind, title in (('iata', 'IATA'), ('faa', 'FAA')):
        codes = sorted({alias.code for alias in aliases if alias.kind == kind})
        if codes:
            identifiers.append(title + ' ' + ', '.join(codes))
    if airport.iata and not any(alias.code == airport.iata and alias.kind in ('iata', 'faa') for alias in aliases):
        identifiers.append('Code ' + airport.iata)
    facility = FACILITY_LABELS.get(airport.airport_type, 'Unclassified facility')
    return ' — '.join(value for value in (airport.name, location, facility, ' | '.join(identifiers)) if value)


def route_segments(route):
    return [code for code in re.split(r'[^A-Za-z0-9]+', route.upper()) if code]


def matching_airports(codes):
    return list(MapData.objects.filter(Q(icao__in=codes) | Q(iata__in=codes) | Q(codes__code__in=codes, codes__kind__in=ROUTABLE_CODE_KINDS))
                .distinct().prefetch_related('codes').order_by('name', 'pk'))


def is_us(airport):
    return airport.country.strip().casefold() == 'united states'


def distinct_airports(airports):
    groups = {}
    for airport in airports:
        icao = airport.icao.strip().upper()
        key = ('icao', icao) if icao else ('location', airport.name.strip().casefold(),
                                          airport.latitude, airport.longitude)
        current = groups.get(key)
        # A US row representing the same airport preserves its known US status.
        if current is None or (is_us(airport) and not is_us(current)):
            groups[key] = airport
    return sorted(groups.values(), key=lambda airport: (airport.name.casefold(), airport.pk))


def airport_matches_code(airport, code):
    aliases = [alias for alias in airport.codes.all() if alias.kind in ROUTABLE_CODE_KINDS]
    if len(code) == 4 and code.isalpha():
        return airport.icao.strip().upper() == code or any(alias.code == code and alias.kind == 'icao' for alias in aliases)
    return code in (airport.iata.strip().upper(), airport.icao.strip().upper()) or any(alias.code == code for alias in aliases)


def resolve_route(route, choices=None, airports=None):
    segments = route_segments(route)
    airports = matching_airports(set(segments)) if airports is None else list(airports)
    saved = choices.get('airports', {}) if isinstance(choices, dict) and choices.get('route') == route else {}
    if not isinstance(saved, dict):
        saved = {}
    result = []
    for position, code in enumerate(segments):
        matches = [airport for airport in airports if airport_matches_code(airport, code)]
        candidates = distinct_airports(matches)
        domestic = [airport for airport in candidates if is_us(airport)] if len(code) == 3 else []
        if domestic:
            candidates = domestic
        automatic = len(candidates) == 1
        selected = next((airport for airport in candidates if airport.pk == saved.get(str(position))), None)
        airport = candidates[0] if automatic else selected
        result.append(dict(position=position, code=code, airport=airport, candidates=candidates,
                           confirmed=selected is not None and not automatic,
                           requires_choice=bool(candidates) and not automatic,
                           needs_confirmation=bool(candidates) and airport is None,
                           unknown=not candidates))
    return result


def flight_resolution(flight):
    choices = getattr(flight, 'route_airport_choices', {})
    key = (flight.route, repr(choices))
    if getattr(flight, '_airport_resolution_key', None) != key:
        flight._airport_resolution = resolve_route(flight.route, choices)
        flight._airport_resolution_key = key
    return flight._airport_resolution


def warning_values(resolution):
    missing = list(dict.fromkeys(item['code'] for item in resolution if item['unknown']))
    pending = list(dict.fromkeys(item['code'] for item in resolution if item['needs_confirmation']))
    return {
        'map_error': 'Unknown airport codes: ' + ', '.join(missing) if missing else '',
        'duplicate_error': 'Confirm airport locations: ' + ', '.join(pending) if pending else '',
    }


def map_values(resolution):
    # Do not draw an invented route between airports either side of an unresolved leg.
    airports = [item['airport'] for item in resolution] if all(item['airport'] for item in resolution) else []
    coordinates, markers = [], []
    for index, airport in enumerate(airports):
        point = {'latitude': airport.latitude, 'longitude': airport.longitude}
        coordinates.append(point)
        markers.append({'key': index, 'icao': airport.icao, 'iata': airport.iata,
                        'title': airport.name, 'coordinates': point})
    return {'route_data': airports, 'app_markers': markers, 'app_polylines': {'coordinates': coordinates}}
