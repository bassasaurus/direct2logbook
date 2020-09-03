import re
from flights.models import MapData, Flight
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=Flight)
def save_route_data(sender, instance, dispatch_uid='save_route_data', **kwargs):

    user = instance.user

    route_data = []
    route = re.split('\W+', instance.route)  # separate individual codes

    icao = MapData.objects.values_list('icao', flat=True)
    iata = MapData.objects.values_list('iata', flat=True)

    for code in route:  # XXXX, XXXX, XXXX
        code = code.upper()
        if code not in icao and code not in iata:
            pass
        else:
            # print("code to match ", code)
            iata_kwargs = {'iata': code}
            icao_kwargs = {'icao': code}
            map_object = (MapData.objects.filter(**iata_kwargs) | MapData.objects.filter(**icao_kwargs)).first()
            route_data.append(map_object)

    # print(route_data, " compiled")

    # gets object through a queryset to avoid infinite loop casued by save() method
    Flight.objects.filter(user=user).filter(pk=instance.pk).update(route_data=route_data)

    return route_data

    # print(instance.pk, " updated")
