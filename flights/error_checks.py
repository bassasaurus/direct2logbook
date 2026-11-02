"""Shared persisted-error presentation and airport-code checks."""
from decimal import Decimal

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
    from flights.airport_resolution import route_segments
    return list(dict.fromkeys(route_segments(route)))


def route_warning_values(route, airport_rows=None, choices=None):
    from flights.airport_resolution import resolve_route, warning_values
    return warning_values(resolve_route(route, choices, airport_rows))
