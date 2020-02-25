from flights.models import Flight, MapData
from django.db.models.signals import post_save
from django.dispatch import receiver
import re


@receiver(post_save, sender=Flight)
def map_error(sender, instance, dispatch_uid='map_error', **kwargs):

    user = instance.user

    errors = ''
    message = ''

    # search against tuples
    icao = MapData.objects.values_list('icao', flat=True)
    iata = MapData.objects.values_list('iata', flat=True)

    route = re.split('\W+', instance.route)

    for code in route:
        if code not in icao and code not in iata:
            errors = errors + code + ', '
            message = errors + " Not in database"
        else:
            message = ''

    Flight.objects.filter(user=user).filter(pk=instance.pk).update(map_error=message)


@receiver(post_save, sender=Flight)
def duplicate_error(sender, instance, dispatch_uid='duplicate_error', **kwargs):

    user = instance.user

    errors = ''

    # search against tuple
    iata = MapData.objects.values_list('iata', flat=True)
    iata = list(iata)

    route = re.split('\W+', instance.route)

    for code in route:
        if iata.count(code) > 1:
            # print(code, iata.count(code))
            errors = errors + code + ', '
            message = errors + " Duplicate in database"
        else:
            message = ''

    Flight.objects.filter(user=user).filter(pk=instance.pk).update(duplicate_error=message)


@receiver(post_save, sender=Flight)
def flight_misc_error(sender, instance, dispatch_uid='flight_misc_error', **kwargs):

    user = instance.user

    if not instance.aircraft_type:
        aircraft_type_error = "Please select an aircraft type"
        Flight.objects.filter(user=user).filter(pk=instance.pk).update(aircraft_type_error=aircraft_type_error)
    else:
        Flight.objects.filter(user=user).filter(pk=instance.pk).update(aircraft_type_error='')

    if not instance.registration:
        registration_error = "Please select a tailnumber"
        Flight.objects.filter(user=user).filter(pk=instance.pk).update(registration_error=registration_error)
    else:
        Flight.objects.filter(user=user).filter(pk=instance.pk).update(registration_error='')

    data = (instance.pilot_in_command, instance.second_in_command, instance.dual, instance.instructor, instance.solo)
    if not any(data):
        crew_error = "Please select a crew position"
        Flight.objects.filter(user=user).filter(pk=instance.pk).update(crew_error=crew_error)
    else:
        Flight.objects.filter(user=user).filter(pk=instance.pk).update(crew_error='')
