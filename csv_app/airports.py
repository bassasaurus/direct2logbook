"""Validate CSV route airports and prefer ICAO, then IATA, then FAA codes."""
import csv
import io

from flights.airport_resolution import matching_airports, resolve_route, route_segments
from .validation import CSVValidationError


def preferred_codes(airport):
    aliases = list(airport.codes.all())
    codes = [airport.icao.strip().upper()] if airport.icao.strip() else []
    for kind in ('iata', 'faa'):
        values = sorted({alias.code for alias in aliases if alias.kind == kind})
        if kind == 'iata' and airport.iata and not any(alias.code == airport.iata and alias.kind in ('faa', 'legacy') for alias in aliases):
            values = sorted(set(values) | {airport.iata})
        if kind == 'iata' and airport.iata in values:
            values.remove(airport.iata)
            values.insert(0, airport.iata)
        codes.extend(values)
    # Older airport rows used this field for IATA/FAA/legacy identifiers alike.
    if airport.iata.strip():
        codes.append(airport.iata.strip().upper())
    return list(dict.fromkeys(codes))


def same_airport(first, second):
    if first.icao and second.icao:
        return first.icao.strip().upper() == second.icao.strip().upper()
    return first.pk == second.pk or (first.name.casefold(), first.latitude, first.longitude) == (
        second.name.casefold(), second.latitude, second.longitude)


def normalize_airport_routes(content, rows, errors=None):
    actual = [row for row in rows if not row['simulator']]
    airports = matching_airports({code for row in actual for code in route_segments(row['route'])}) if actual else []
    resolutions = {}
    selected = {}
    # Resolve each distinct route once; preserve every occurrence/leg in the CSV.
    for row in actual:
        route = row['route']
        if route not in resolutions:
            resolutions[route] = resolve_route(route, airports=airports)
            for item in resolutions[route]:
                if item['airport']:
                    selected[item['airport'].pk] = item['airport']
    candidate_codes = {code for airport in selected.values() for code in preferred_codes(airport)}
    canonical_airports = matching_airports(candidate_codes) if candidate_codes else []
    preferred = {}
    for airport in selected.values():
        for code in preferred_codes(airport):
            match = resolve_route(code, airports=canonical_airports)
            if len(match) == 1 and match[0]['airport'] and same_airport(airport, match[0]['airport']):
                preferred[airport.pk] = code
                break
    records = list(csv.reader(io.StringIO(content)))
    typed = iter(rows)
    for line, record in enumerate(records[1:], start=2):
        if not any(value.strip() for value in record):
            continue
        row = next(typed)
        if row['simulator']:
            continue
        resolution = resolutions[row['route']]
        unknown = list(dict.fromkeys(item['code'] for item in resolution if item['unknown']))
        ambiguous = list(dict.fromkeys(item['code'] for item in resolution if item['needs_confirmation']))
        message = None
        if not resolution:
            message = 'Enter a route with ICAO, IATA or FAA airport codes.'
        elif unknown:
            message = f"Airport not found: {', '.join(unknown)}. Check the ICAO, IATA or FAA code."
        elif ambiguous:
            message = f"Multiple airports match {', '.join(ambiguous)}. Use a unique ICAO, IATA or FAA code."
        if message:
            if errors is None:
                raise CSVValidationError(f'Row {line}: {message}')
            errors[line] = message
            continue
        record[3] = '-'.join(preferred.get(item['airport'].pk, item['code']) for item in resolution)
    output = io.StringIO()
    csv.writer(output).writerows(records)
    return output.getvalue()
