import os
import sys
import django
from django.conf import settings
from collections import OrderedDict

sys.path.append("/Users/blake/django/direct2logbook/")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'logbook.settings')
django.setup()


from django.contrib.auth.models import User
from flights.models import AircraftCategory, Flight, MapData
import re
from django.core.exceptions import ObjectDoesNotExist

user = User.objects.get(pk=1)

flights = Flight.objects.filter(user=user)[:20]


for flight in flights:
    
    coordinates = []
    markers = list(set())
    key = 0
    # print(flight.route, "from DB")
    route = re.split(r'\W+', flight.route)

    # print(route, "after regex", flight.pk)

    us_iata = MapData.objects.filter(country="United States").values_list('iata', flat=True)
    intl_iata =  MapData.objects.exclude(country = "United States").values_list('iata', flat=True)

    for airport in route:
        
        airport = airport.replace(" ", "")

        if airport in us_iata:
            airport = MapData.objects.get(iata=airport, country="United States")
            
        elif airport in intl_iata:
            airport = MapData.objects.get(iata=airport)

        elif airport not in us_iata and airport not in intl_iata:
           airport = MapData.objects.get(icao=airport)

        else:
            pass
        
        coordinates.append({"latitude": airport.latitude, "longitude": airport.longitude})

        marker =  {
            "key": key,
            "icao": airport.icao,
            "iata": airport.iata, 
            "title": airport.name,
            "coordinates": {
                "latitude": airport.latitude,
                "longitude": airport.longitude,
            }
        }

        markers.append(marker)
        key = key + 1

    polyline = {
            "coordinates": coordinates
        }


    print(flight.route, flight.pk)

    flight.app_markers = markers
    flight.app_polylines = polyline
    
    flight.save()