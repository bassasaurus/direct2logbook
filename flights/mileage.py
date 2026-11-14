"""Great-circle route estimates from the same resolved airports used by maps."""
import math

from flights.map_routes import _coordinates

DISTANCE_UNITS = {'nm': (1, 'NM'), 'mi': (1852 / 1609.344, 'mi'), 'km': (1.852, 'km')}


def format_distance(distance, unit='nm'):
    if distance is None:
        return 'Unavailable'
    factor, label = DISTANCE_UNITS.get(unit, DISTANCE_UNITS['nm'])
    return f'{distance * factor:,.1f} {label}'


def route_distance_nm(flight):
    from flights.airport_resolution import route_segments

    airports = flight.route_data or []
    codes = route_segments(getattr(flight, 'route', '') or '')
    if not codes or len(airports) != len(codes):
        return None
    points = [_coordinates(airport) for airport in airports]
    if any(point is None for point in points):
        return None
    distance = 0.0
    for start, end in zip(points, points[1:]):
        lat1, lon1 = map(math.radians, start)
        lat2, lon2 = map(math.radians, end)
        a = (math.sin((lat2 - lat1) / 2) ** 2
             + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
        distance += 2 * (6371008.8 / 1852) * math.asin(math.sqrt(min(1.0, max(0.0, a))))
    return round(distance, 1)
