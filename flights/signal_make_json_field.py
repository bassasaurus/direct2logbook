from django import dispatch
from flights.models import Flight, MapData
from django.db.models.signals import post_save
from django.dispatch import receiver
import re

@receiver(post_save, sender=Flight)
def make_json_feild(sender, instance, dispatch_uid="app_data_update", **kwargs):

    post_save.disconnect(make_json_feild, sender=sender)

    coordinates = []
    markers = list(set())
    key = 0
    
    route = re.split(r'\W+', instance.route)
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


    # print(instance.route, instance.pk)

    instance.app_markers = markers
    instance.app_polylines = polyline
    
    instance.save()

    post_save.connect(make_json_feild, sender=sender)