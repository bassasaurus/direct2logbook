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

flights = Flight.objects.filter(user=user)


for flight in flights:
    
    line_data_set = []
    markers = []


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
             
        marker =  {
                "icao": airport.icao,
                "iata":airport.iata, 
                "title": airport.name,
            
            "coordinates": {
                "latitude": airport.latitude,
                "longitude": airport.longitude,
            }
        }

        line_data_set.append([airport.latitude, airport.longitude])
    
        markers.append(marker)

    flight.app_markers = markers
    flight.app_lines = line_data_set
    
    print(flight.route)
    flight.save()