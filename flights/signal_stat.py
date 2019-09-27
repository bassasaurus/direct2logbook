from flights.models import *
from flights import querys
from django.db.models.signals import pre_save, pre_delete, post_save, post_delete
from django.db.models import Sum, Q
from django.dispatch import receiver
import datetime
from django.core.exceptions import ObjectDoesNotExist
from flights.queryset_helpers import *

@receiver(post_delete, sender=Flight)
def no_flight_stat_delete(sender, instance, **kwargs):

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
def no_aircraft_stat_delete(sender, instance, **kwargs):

    user = instance.user
    try:
        kwargs = {'aircraft_type': instance.aircraft_type}
        stat = Stat.objects.filter(user=user).get(**kwargs)
        stat.delete()

    except ObjectDoesNotExist:
        pass

@receiver(post_delete, sender=Imported)
def imported_deleted(sender, instance, **kwargs):
    user = instance.user
    try:
        stat = Stat.objects.filter(user=instance.user).get(aircraft_type=instance.aircraft_type)
        flight = Flight.objects.filter(user=instance.user).filter(aircraft_type=instance.aircraft_type)
        if avoid_none(flight, 'duration') == 0:
            stat.delete()
    except ObjectDoesNotExist:
        pass

@receiver(post_save, sender=Imported)
@receiver(post_save, sender=Flight)
@receiver(pre_delete, sender=Imported)
@receiver(pre_delete, sender=Flight)
def stat_update(sender, instance, **kwargs):

    stat = Stat.objects.get_or_create(user=instance.user, aircraft_type=str(instance.aircraft_type))
    stat=stat[0]

    flight = Flight.objects.filter(user=instance.user).filter(aircraft_type=instance.aircraft_type)
    imported = Imported.objects.filter(user=instance.user).filter(aircraft_type=instance.aircraft_type)

    stat.total_time = avoid_none(flight, 'duration') + avoid_none(imported, 'total_time')

    stat.pilot_in_command = avoid_none(flight.filter(pilot_in_command=True), 'duration') + avoid_none(imported, 'pilot_in_command')

    stat.second_in_command = avoid_none(flight.filter(second_in_command=True), 'duration') + avoid_none(imported, 'second_in_command')

    stat.cross_country = avoid_none(flight.filter(cross_country=True), 'duration') + avoid_none(imported, 'cross_country')

    stat.instructor = avoid_none(flight.filter(instructor=True), 'duration') + avoid_none(imported, 'instructor')

    stat.dual = avoid_none(flight.filter(dual=True), 'duration') + avoid_none(imported, 'dual')

    stat.solo = avoid_none(flight.filter(solo=True), 'duration') + avoid_none(imported, 'solo')

    stat.instrument = avoid_none(flight, 'instrument') + avoid_none(imported, 'instrument')

    stat.simulated_instrument = avoid_none(flight, 'simulated_instrument') + avoid_none(imported, 'simulated_instrument')

    stat.simulator = avoid_none(flight.filter(simulator=True), 'duration') + avoid_none(imported, 'simulator')

    stat.night = avoid_none(flight, 'night') + avoid_none(imported, 'night')

    stat.landings_day = avoid_none(flight, 'landings_day') + avoid_none(imported, 'landings_day')

    stat.landings_night = avoid_none(flight, 'landings_night') + avoid_none(imported, 'landings_night')

    stat.landings_stat = zero_if_none(stat.landings_day) + zero_if_none(stat.landings_night) + avoid_none(imported, 'landings_day') + avoid_none(imported, 'landings_night')

    try:
        last_flown = flight.latest('date').date
        stat.last_flown = last_flown
    except ObjectDoesNotExist:
        pass
    try:
        stat.last_flown = imported.latest('last_flown').last_flown
    except ObjectDoesNotExist:
        stat.last_flown = None

    today = datetime.date.today()

    last_30 = today - datetime.timedelta(days=30)
    last_30 = flight.filter(date__lte=today,date__gte=last_30)
    stat.last_30 = avoid_none(last_30, 'duration') + avoid_none(imported, 'last_30')

    last_60 = today - datetime.timedelta(days=60)
    last_60 = flight.filter(date__lte=today,date__gte=last_60)
    stat.last_60 = avoid_none(last_60, 'duration') + avoid_none(imported, 'last_60')

    last_90 = today - datetime.timedelta(days=90)
    last_90 = flight.filter(date__lte=today,date__gte=last_90)
    stat.last_90 = avoid_none(last_90, 'duration') + avoid_none(imported, 'last_90')

    last_180 = today - datetime.timedelta(days=180)
    last_180 = flight.filter(date__lte=today,date__gte=last_180)
    stat.last_180 = avoid_none(last_180, 'duration') + avoid_none(imported, 'last_180')

    last_yr = today - datetime.timedelta(days=365)
    last_yr = flight.filter(date__lte=today,date__gte=last_yr)
    stat.last_yr = avoid_none(last_yr, 'duration') + avoid_none(imported, 'last_yr')

    last_2yr = today - datetime.timedelta(days=730)
    last_2yr = flight.filter(date__lte=today,date__gte=last_2yr)
    stat.last_2yr = avoid_none(last_2yr, 'duration') + avoid_none(imported, 'last_2yr')

    ytd = datetime.date(today.year, 1, 1)
    ytd = flight.filter(date__lte=today,date__gte=ytd)
    stat.ytd = avoid_none(ytd, 'duration') + avoid_none(imported, 'ytd')

    stat.save()
