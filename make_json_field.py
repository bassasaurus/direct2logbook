import os
import sys
import django
from django.conf import settings

sys.path.append("/Users/blake/django/direct2logbook/")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'logbook.settings')
django.setup()


from django.contrib.auth.models import User
from flights.models import Flight, MapData

from django.core.exceptions import ObjectDoesNotExist

user = User.objects.get(pk=1)

flights = Flight.objects.filter(user=user)[:1]


for flight in flights:
    
    route = flight.route.split('-')
    features = ''

    for airport in route:
        # print('ii')
        try:
            if len(airport) == 3:
                airport = MapData.objects.get(iata=airport, country="United States")
            elif len(airport) == 4:
                airport = MapData.objects.get(icao=airport)
        except ObjectDoesNotExist:
            print(airport + ' error')
             
    
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
    
        features = features + str(feature) + ','

    print(features)