from flights.models import MapData, Flight
from django.core.cache import cache
import json

def get_map_data(queryset, user):

    features = []
    line_json = []

    for flight in queryset:

        for map_obj in flight.route_data:

            if not map_obj:
                pass

            else:
                feature = {"type":"Feature","properties":{"icao": "","iata": "", "name": "", "city": "", "state": "", "country": "", "elevation": ""},"geometry":{"type":"Point","coordinates":['','']}}

                feature["properties"]["icao"] = map_obj.icao
                feature["properties"]["iata"] = map_obj.iata
                feature["properties"]["name"] = map_obj.name
                feature["properties"]["city"] = map_obj.city
                feature["properties"]["state"] = map_obj.state
                feature["properties"]["country"] = map_obj.country
                feature["properties"]["elevation"] = map_obj.elevation
                feature["geometry"]["coordinates"] = [map_obj.longitude, map_obj.latitude]

                features.append(feature)

                line_json.append([map_obj.latitude, map_obj.longitude]) #assemble polyline

    feature_collection = {"type":"FeatureCollection","features": features }

    user_cache = 'airports_{}'.format(user.id)
    cache.set(user_cache, feature_collection, 1*60)

    line_json = str(line_json)
    user_cache = 'routes_{}'.format(user.id)
    cache.set(user_cache, line_json, 1*60)

    return feature_collection, line_json
