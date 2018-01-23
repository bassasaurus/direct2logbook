from flights.models import *
from flights import querys
from django.db.models.signals import pre_save, pre_delete, post_save, post_delete
from django.db.models import Sum, Q
import datetime

@receiver(pre_delete, sender=Aircraft)
def stat_delete(sender, instance, **kwargs):
    kwargs = {'aircraft_type': instance.aircraft_type}
    stat = Stat.objects.get(**kwargs)
    stat.delete()

@receiver(pre_save, sender=Aircraft)
def stat_pre_save(sender, instance, **kwargs):
    Stat.objects.get_or_create(aircraft_type = instance.aircraft_type)

@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
def stat_update(sender, instance, **kwargs):

    if not instance.aircraft_type or instance.registration: #prevents empty aircraft_type from breaking query
        pass

        aircraft_type = instance.aircraft_type
        stat_queryset = Stat.objects.all()

    elif stat_queryset.filter(aircraft_type=aircraft_type).exists():
        stat = Stat.objects.get(aircraft_type=aircraft_type)
        stat.total_time = querys.aircraft_total_time(aircraft_type)
        stat.pilot_in_command = querys.pilot_in_command_total(aircraft_type)
        stat.second_in_command = querys.second_in_command_total(aircraft_type)
        stat.cross_country = querys.cross_country_total(aircraft_type)
        stat.instructor = querys.instructor_total(aircraft_type)
        stat.dual = querys.dual_total(aircraft_type)
        stat.solo = querys.solo_total(aircraft_type)
        stat.instrument = querys.instrument_total(aircraft_type)
        stat.simulated_instrument = querys.simulated_instrument_total(aircraft_type)
        stat.simulator = querys.simulator_total(aircraft_type)
        stat.night = querys.night_total(aircraft_type)
        stat.landings_day = querys.landings_day_total(aircraft_type)
        stat.landings_night = querys.landings_night_total(aircraft_type)

        stat.last_flown = querys.last_flown(aircraft_type)
        stat.last_30 = querys.last_30(aircraft_type)
        stat.last_60 = querys.last_60(aircraft_type)
        stat.last_90 = querys.last_90(aircraft_type)
        stat.last_180 = querys.last_180(aircraft_type)
        stat.last_yr = querys.last_yr(aircraft_type)
        stat.last_2yr = querys.last_2yr(aircraft_type)
        stat.ytd = querys.ytd(aircraft_type)
        stat.save()
    # creates new instance if needed
    else:
        stat = Stat(
            aircraft_type = aircraft_type,
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
        stat.save()
