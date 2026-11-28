"""Review matches on date, aircraft, tailnumber, directional route and duration.

Different durations or reversed routes represent distinct entries. Even exact
matches need an explicit decision: instructors may repeat the same local flight.
Decisions never edit existing flights.
"""
import csv
import hashlib
import io
import json
from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum
from flights.models import Flight
from flights.airport_resolution import matching_airports, resolve_route, route_segments
from .validation import parse_csv, CSVValidationError

PAGE_SIZE = 10


class OverlapReviewRequired(CSVValidationError):
    pass


def possible_overlaps(batch, user):
    typed, _ = parse_csv(batch.content)
    lines = [line for line, row in enumerate(list(csv.reader(io.StringIO(batch.content)))[1:], 2) if any(cell.strip() for cell in row)]
    candidates = list(Flight.objects.filter(user=user, date__in={row['date'] for row in typed},
        duration__in={row['duration'] for row in typed}).select_related('aircraft_type', 'registration')
        .annotate(approach_count=Sum('approach__number')).prefetch_related('approach_set','holding_set').order_by('pk'))
    if not candidates:
        return []
    all_routes = {row['route'] for row in typed} | {flight.route for flight in candidates}
    codes = {code for route in all_routes for code in route_segments(route)}
    airports = matching_airports(codes) if codes else []
    routes = {}
    for route in all_routes:
        resolved = resolve_route(route, airports=airports)
        routes[route] = tuple(('airport', item['airport'].pk) if item['airport'] and not item['needs_confirmation']
                             else ('code', item['code'].upper()) for item in resolved)
    def signature(row):
        sim = bool(row['simulator'])
        device = (row.get('device_type') or '', (row.get('device_id') or '').strip().casefold(), row.get('atd_type') or '') if sim else ()
        return (row['date'], row['aircraft'].strip().casefold(), row['registration'].strip().casefold(),
                routes.get(row['route'], ()), row['duration'], sim, device)
    def detail(row):
        roles = [(name, label) for name, label in [('pilot_in_command','PIC'),('second_in_command','SIC'),
            ('solo','Solo'),('dual','Dual'),('instructor','CFI'),('cross_country','XC')] if row.get(name)]
        from .approaches import format_approaches
        return dict(row, roles=', '.join(label for name, label in roles) or '—',
                    approach_summary=format_approaches(row.get('approach_details', [])))
    grouped = defaultdict(list)
    for flight in candidates:
        row = {'pk': flight.pk, 'date': flight.date, 'aircraft': flight.aircraft_type.aircraft_type,
            'registration': flight.registration.registration if flight.registration else '',
            'route': flight.route or '', 'duration': flight.duration, 'simulator': bool(flight.simulator),
            'device_type': flight.device_type or '', 'device_id': flight.device_id or '', 'atd_type': flight.atd_type or '',
            'night': flight.night or Decimal('0'), 'instrument': flight.instrument or Decimal('0'),
            'simulated_instrument': flight.simulated_instrument or Decimal('0'),
            'landings_day': flight.landings_day or 0, 'landings_night': flight.landings_night or 0,
            'approaches': flight.approach_count or 0, 'remarks': flight.remarks or '',
            'hold': flight.hold or any(item.hold for item in flight.holding_set.all()),
            'approach_details': [{'approach_type':a.approach_type,'number':a.number} for a in flight.approach_set.all() if a.number]}
        row.update({name: getattr(flight, name) for name in ('pilot_in_command','second_in_command','solo','dual','instructor','cross_country')})
        row['night_landings_full_stop'] = flight.night_landings_full_stop
        grouped[signature(row)].append(row)
    results = []
    for line, row in zip(lines, typed):
        matches = grouped.get(signature(row), [])
        if not matches:
            continue
        encoded = json.dumps({'incoming': row, 'matches': matches}, sort_keys=True, default=str).encode()
        token = hashlib.sha256(encoded).hexdigest()
        decision = batch.overlap_review.get(str(line), {})
        results.append({'line': line, 'token': token, 'incoming': detail(row),
            'matches': [detail(match) for match in matches],
            'approved': decision.get('action') == 'include' and decision.get('token') == token})
    return results


def unresolved_overlaps(batch, user):
    return [issue for issue in possible_overlaps(batch, user) if not issue['approved']]


def validate_overlap_review(batch, user):
    if unresolved_overlaps(batch, user):
        raise OverlapReviewRequired('Review possible duplicate entries before importing. If matches changed, review them again.')
