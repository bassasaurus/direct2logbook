import math


def _coordinates(airport):
    try:
        point = [float(airport.latitude), float(airport.longitude)]
    except (AttributeError, TypeError, ValueError):
        return None
    if (all(math.isfinite(value) for value in point)
            and -90 <= point[0] <= 90 and -180 <= point[1] <= 180):
        return point
    return None


def flight_map_data(flights):
    """Render owner-scoped, per-flight routes without shared per-user caches."""
    routes, features, seen = {}, [], set()
    for flight in flights:
        points = []
        for airport in flight.route_data or []:
            point = _coordinates(airport)
            if point is None:
                continue
            if not points or points[-1] != point:
                points.append(point)
            key = (getattr(airport, 'pk', None), tuple(point))
            if key not in seen:
                seen.add(key)
                features.append({
                    'type': 'Feature',
                    'properties': {field: getattr(airport, field, '') for field in
                                   ('icao', 'iata', 'name', 'city', 'state', 'country', 'elevation')},
                    'geometry': {'type': 'Point', 'coordinates': [point[1], point[0]]},
                })
        routes[str(flight.pk)] = points
    return {'routes': routes, 'airports': {'type': 'FeatureCollection', 'features': features}}
