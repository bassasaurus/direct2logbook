from flights.models import Flight, Aircraft, Stat, Imported
from django.db.models.signals import pre_delete, post_save, post_delete
from django.db.models import Sum
from django.dispatch import receiver
from django.core.exceptions import ObjectDoesNotExist
from flights.queryset_helpers import avoid_none, zero_if_none
from flights.rolling_stats import assign_rolling_values


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


@receiver(post_save, sender=Imported)
@receiver(post_save, sender=Flight)
@receiver(pre_delete, sender=Imported)
@receiver(pre_delete, sender=Flight)
def stat_update(sender, instance, dispatch_uid="stat_update", **kwargs):

    stat = Stat.objects.get_or_create(user=instance.user, aircraft_type=str(instance.aircraft_type))
    stat = stat[0]

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

    assign_rolling_values(stat, flight, imported)
    stat.save()
