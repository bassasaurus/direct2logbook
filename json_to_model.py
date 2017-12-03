import os.path
import django

os.environ["DJANGO_SETTINGS_MODULE"] = "logbook.settings"
django.setup()

from flights.models import MapData, Flight
import re
from django.db.models import Q
from django.core.cache import cache
import json

object_list = Flight.objects.all()

# object_list = Flight.objects.filter().order_by('-date')[:4]

def json_to_model(object_list):

    line_json = []

    for obj in object_list: #<flight queryset>
        route_data = []
        route = re.split('\W+', obj.route) #separate individual codes
        # print('input', route)

        for code in route: #XXXX, XXXX, XXXX

            if code == '':
                pass
            else:
                iata_kwargs = {'iata' : code}
                icao_kwargs = {'icao' : code}
                map_object = (MapData.objects.filter(**iata_kwargs) | MapData.objects.filter(**icao_kwargs)).first()

            route_data.append(map_object)

        # geojson = str(geojson).strip("[]").strip("'")
        obj.route_data = route_data
        obj.save()
        print(obj.pk, " saved")

json_to_model(object_list)
