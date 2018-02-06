from flights.models import Flight, MapData
from django.db.models.signals import post_save
from django.dispatch import receiver
import re
from itertools import chain

@receiver(post_save, sender=Flight)
def map_error(sender, instance, **kwargs):

    errors = ''
    message = ''

    #search against tuples
    icao = MapData.objects.values_list('icao', flat=True)
    iata = MapData.objects.values_list('iata', flat=True)

    route = re.split('\W+', instance.route )

    for code in route:
        if code not in icao and code not in iata:
            errors = errors + code + ', '
        else:
            pass

    message = errors + " Not in database"

    Flight.objects.filter(pk=instance.pk).update(map_error=message)

@receiver(post_save, sender=Flight)
def duplicate_error(sender, instance, **kwargs):

    errors = ''

    #search against tuple
    iata = MapData.objects.values_list('iata', flat=True)
    iata = list(iata)
    # items_set = set(chain(icao, iata))

    route = re.split('\W+', instance.route )

    for code in route:
        if iata.count(code) > 1:
            errors = errors + code +', '
        else:
            pass

    message = errors + " Duplicate in database"

    Flight.objects.filter(pk=instance.pk).update(duplicate_error=message)
