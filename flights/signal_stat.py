from flights.models import Flight, Aircraft, Stat, Imported
from django.db.models.signals import pre_delete, post_delete
from django.db.models import Sum
from django.dispatch import receiver
from django.core.exceptions import ObjectDoesNotExist
from flights.queryset_helpers import avoid_none


@receiver(post_delete, sender=Flight)
def no_flight_stat_delete(sender, instance, dispatch_uid="no_flight_stat_delete", **kwargs):

    user = instance.user
    aircraft_type = instance.aircraft_type

    aircraft_total_time = Flight.objects.filter(aircraft_type=aircraft_type).aggregate(Sum('duration'))

    try:
        if not aircraft_total_time.get('duration__sum'):
            kwargs = {'aircraft_type': instance.aircraft_type}
            stat = Stat.objects.filter(user=user).get(**kwargs)
            stat.delete()
    except ObjectDoesNotExist:
        pass


@receiver(pre_delete, sender=Aircraft)
def no_aircraft_stat_delete(sender, instance, dispatch_uid="no_aircraft_stat_delete", **kwargs):

    user = instance.user
    try:
        kwargs = {'aircraft_type': instance.aircraft_type}
        stat = Stat.objects.filter(user=user).get(**kwargs)
        stat.delete()

    except ObjectDoesNotExist:
        pass


@receiver(post_delete, sender=Imported)
def imported_deleted(sender, instance, dispatch_uid="imported_deleted", **kwargs):

    try:
        stat = Stat.objects.filter(user=instance.user).get(aircraft_type=instance.aircraft_type)
        flight = Flight.objects.filter(user=instance.user).filter(aircraft_type=instance.aircraft_type)
        if avoid_none(flight, 'duration') == 0:
            stat.delete()
    except ObjectDoesNotExist:
        pass
