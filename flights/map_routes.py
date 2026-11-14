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
    from flights.mileage import route_distance_nm

    routes, features, seen = {}, [], set()
    total_nm, counted, unavailable = 0.0, 0, 0
    distances = {}
    for flight in flights:
        distance = route_distance_nm(flight)
        distances[str(flight.pk)] = distance
        if distance is None:
            unavailable += 1
        else:
            total_nm += distance
            counted += 1
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
    return {'routes': routes, 'airports': {'type': 'FeatureCollection', 'features': features},
            'mileage': {'total_nm': round(total_nm, 1) if counted or not unavailable else None,
                        'unavailable': unavailable, 'distances': distances}}
