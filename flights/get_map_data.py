from flights.models import MapData, Flight
from django.core.cache import cache
import json

def get_map_data(queryset):

    features = []
    line_json = []

    for flight in queryset:

        for map_obj in flight.route_data:

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

    cache.set('airports',feature_collection, 5*60)

    line_json = str(line_json)
    cache.set('routes', line_json, 5*60)
