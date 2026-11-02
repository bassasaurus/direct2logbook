from itertools import islice

from django.core.management.base import BaseCommand
from django.db.models import Q

from flights.error_checks import route_codes, route_warning_values
from flights.models import Flight, MapData
from flights.airport_resolution import resolve_route, map_values


class Command(BaseCommand):
    help = 'Recheck existing route warnings without saving flights or changing their totals.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--user-id', type=int)
        parser.add_argument('--refresh-maps', action='store_true', help='Also rebuild maps using the confirmed airport-country rule.')

    def handle(self, *args, **options):
        flights = Flight.objects.order_by('pk').only('pk', 'route', 'map_error', 'duplicate_error', 'route_airport_choices')
        if options['user_id'] is not None:
            flights = flights.filter(user_id=options['user_id'])
        iterator = flights.iterator(chunk_size=200)
        checked = changed = 0
        while batch := list(islice(iterator, 200)):
            codes = {code for flight in batch for code in route_codes(flight.route)}
            rows = list(MapData.objects.filter(Q(icao__in=codes) | Q(iata__in=codes)))
            updates = []
            for flight in batch:
                checked += 1
                values = route_warning_values(flight.route, rows, flight.route_airport_choices)
                if options['refresh_maps']:
                    values.update(map_values(resolve_route(flight.route, flight.route_airport_choices, rows)))
                if options['refresh_maps'] or any(getattr(flight, field) != value for field, value in values.items()):
                    for field, value in values.items():
                        setattr(flight, field, value)
                    updates.append((flight, values))
            if options['dry_run']:
                changed += len(updates)
            else:
                for flight, values in updates:
                    # A concurrent route edit must keep its own fresh warnings.
                    changed += Flight.objects.filter(pk=flight.pk, route=flight.route,
                        route_airport_choices=flight.route_airport_choices).update(**values)
        verb = 'Would update' if options['dry_run'] else 'Updated'
        self.stdout.write(f'Checked {checked} flight(s). {verb} route warnings for {changed} flight(s). Route text, flight hours and totals unchanged.')
