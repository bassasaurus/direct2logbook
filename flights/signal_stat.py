from flights.models import *
from flights import querys
from django.db.models.signals import pre_save, pre_delete, post_save, post_delete
from django.db.models import Sum, Q
from django.dispatch import receiver
import datetime
from django.core.exceptions import ObjectDoesNotExist

@receiver(post_delete, sender=Flight)
def no_flight_stat_delete(sender, instance, **kwargs):

    user = instance.user
    aircraft_type = instance.aircraft_type

    aircraft_total_time = Flight.objects.filter(aircraft_type=aircraft_type).aggregate(Sum('duration'))

    if not aircraft_total_time.get('duration__sum'):
        kwargs = {'aircraft_type': instance.aircraft_type}
        stat = Stat.objects.filter(user=user).get(**kwargs)
        stat.delete()
    else:
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

@receiver(post_save, sender=Flight)
@receiver(pre_delete, sender=Flight)
def stat_update(sender, instance, **kwargs):

    user = instance.user

    try:
        stat = Stat.objects.get_or_create(user=user, aircraft_type = instance.aircraft_type)

        aircraft_type = instance.aircraft_type

        Stat.objects.filter(user=user).filter(aircraft_type = aircraft_type).update(
            aircraft_type = str(aircraft_type),
            total_time = querys.aircraft_total_time(aircraft_type),
            pilot_in_command = querys.pilot_in_command_total(aircraft_type),
            second_in_command = querys.second_in_command_total(aircraft_type),
            cross_country = querys.cross_country_total(aircraft_type),
            instructor = querys.instructor_total(aircraft_type),
            dual = querys.dual_total(aircraft_type),
            solo = querys.solo_total(aircraft_type),
            instrument = querys.instrument_total(aircraft_type),
            simulated_instrument = querys.simulated_instrument_total(aircraft_type),
            simulator = querys.simulator_total(aircraft_type),
            night = querys.night_total(aircraft_type),
            landings_day = querys.landings_day_total(aircraft_type),
            landings_night = querys.landings_night_total(aircraft_type),
            last_flown = querys.last_flown(aircraft_type),
            last_30 = querys.last_30(aircraft_type),
            last_60 = querys.last_60(aircraft_type),
            last_90 = querys.last_90(aircraft_type),
            last_180 = querys.last_yr(aircraft_type),
            last_yr = querys.last_yr(aircraft_type),
            last_2yr = querys.last_2yr(aircraft_type),
            ytd = querys.ytd(aircraft_type),
            )
    except ObjectDoesNotExist:
        pass
