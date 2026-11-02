"""Shared persisted-error presentation and airport-code checks."""
from collections import Counter
from decimal import Decimal
import re

from django.db.models import Q


ERROR_FIELDS = ('map_error', 'duplicate_error', 'aircraft_type_error',
                'registration_error', 'crew_error')


def flight_error_filter():
    errors = Q(duration__isnull=True) | Q(duration__lt=Decimal('0.1'))
    for field in ERROR_FIELDS:
        errors |= Q(**{field + '__gt': ''})
    return errors


def flight_error_messages(flight):
    errors = [getattr(flight, field) for field in ERROR_FIELDS if getattr(flight, field)]
    if flight.duration is None or flight.duration < Decimal('0.1'):
        errors.append('Please check the duration of this flight.')
    return errors


def route_codes(route):
    return list(dict.fromkeys(code for code in re.split(r'\W+', route) if code))


def route_warning_values(route, airport_rows=None):
    from flights.models import MapData
    codes = route_codes(route)
    if airport_rows is None:
        airport_rows = MapData.objects.filter(Q(icao__in=codes) | Q(iata__in=codes)).values_list('icao', 'iata')
    known = set()
    iata_counts = Counter()
    for icao, iata in airport_rows:
        known.update((icao, iata))
        if iata:
            iata_counts[iata] += 1
    missing = [code for code in codes if code not in known]
    ambiguous = [code for code in codes if iata_counts[code] > 1]
    return {
        'map_error': 'Unknown airport codes: ' + ', '.join(missing) if missing else '',
        'duplicate_error': 'Ambiguous airport codes: ' + ', '.join(ambiguous) if ambiguous else '',
    }
