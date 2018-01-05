import re
from flights.models import MapData
from django.db.models.signals import post_save

@receiver(post_save, sender=Flight)
def save_route_data((sender, instance, **kwargs):):

    route_data = []
    route = re.split('\W+', instance.route) #separate individual code

    print(route)

    for code in route: #XXXX, XXXX, XXXX
        print(code)
        if code == '':
            pass
        else:
            iata_kwargs = {'iata' : code}
            icao_kwargs = {'icao' : code}
            map_object = (MapData.objects.filter(**iata_kwargs) | MapData.objects.filter(**icao_kwargs)).first()

        route_data.append(map_object)

    instance.route_data = route_data
    instance.save()
    print(instance.pk, " saved")
