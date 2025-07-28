from django.core.cache import cache
from flights.models import MapData


def get_map_data(queryset, user):

    features = []
    line_json = []

    seen_map_objs = set()

    for flight in queryset:
        for airport in flight.route_data:
            line_json.append([airport.latitude, airport.longitude])

    for flight in queryset:
        for map_obj in flight.route_data:
            if map_obj not in seen_map_objs:
                seen_map_objs.add(map_obj)

    for map_obj in seen_map_objs:
        if not map_obj:
            pass
        else:
            feature = {"type": "Feature", "properties": {"icao": "", "iata": "", "name": "", "city": "",
                                                         "state": "", "country": "", "elevation": ""}, "geometry": {"type": "Point", "coordinates": ['', '']}}

            feature["properties"]["icao"] = map_obj.icao
            feature["properties"]["iata"] = map_obj.iata
            feature["properties"]["name"] = map_obj.name
            feature["properties"]["city"] = map_obj.city
            feature["properties"]["state"] = map_obj.state
            feature["properties"]["country"] = map_obj.country
            feature["properties"]["elevation"] = map_obj.elevation
            feature["geometry"]["coordinates"] = [
                map_obj.longitude, map_obj.latitude]

            features.append(feature)

    feature_collection = {"type": "FeatureCollection", "features": features}

    user_map_cache = 'airports_{}'.format(user.id)
    cache.set(user_map_cache, feature_collection, 1 * 60)

    line_json = str(line_json)
    user_map_cache = 'routes_{}'.format(user.id)
    cache.set(user_map_cache, line_json, 1 * 60)
    return feature_collection, line_json
