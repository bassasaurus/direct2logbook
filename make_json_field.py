import os
import sys
import django
from django.conf import settings

sys.path.append("/Users/blake/django/direct2logbook/")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'logbook.settings')
django.setup()

import json
from django.contrib.auth.models import User
from flights.models import AircraftCategory, Flight, MapData

from django.core.exceptions import ObjectDoesNotExist

user = User.objects.get(pk=1)

flights = Flight.objects.filter(user=user)[:1]


for flight in flights:
    
    line_data_set = []
    features = []


    route = flight.route.split('-')

    for airport in route:
        # print('ii')
        try:
            if len(airport) == 3:
                airport = MapData.objects.get(iata=airport, country="United States")
            elif len(airport) == 4:
                airport = MapData.objects.get(icao=airport)
        except ObjectDoesNotExist:
            print(airport + ' error')
             
        line_data_set.append([airport.latitude, airport.longitude])

        feature = {"type": "Feature", 
            "properties": {
                "icao": airport.icao,
                "iata":airport.iata,
                "name": airport.name,
                "city": airport.city,
                "state": airport.state,
                "country": airport.country,
                "elevation": airport.elevation,
                },
            "geometry":{
                "type": "Point",
            "coordinates": [
                airport.latitude,
                airport.longitude,
            ]
            }
        }
    
        features.append(feature)

    feature_collection = {"type": "FeatureCollection", "features": features}
    # collection = str({"type": "FeatureCollection", "features": airport_data_set}).replace("'", '"')

    flight.app_airport_detail = feature_collection
    flight.app_route_detail = line_data_set

    flight.save()