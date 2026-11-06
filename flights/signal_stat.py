from flights.models import Flight, Aircraft, Stat, Imported
from django.db.models.signals import pre_save, pre_delete, post_save, post_delete
from django.dispatch import receiver
from flights.queryset_helpers import avoid_none, zero_if_none
from flights.rolling_stats import assign_rolling_values


@receiver(pre_delete, sender=Aircraft)
def remove_aircraft_summary(sender, instance, **kwargs):
    Stat.objects.filter(user_id=instance.user_id, aircraft_type=instance.aircraft_type).delete()


@receiver(post_save, sender=Imported)
@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Imported)
@receiver(post_delete, sender=Flight)
def stat_update(sender, instance, dispatch_uid="stat_update", **kwargs):

    flight = Flight.objects.filter(user=instance.user).filter(aircraft_type=instance.aircraft_type)
    imported = Imported.objects.filter(user=instance.user).filter(aircraft_type=instance.aircraft_type)
    # Recalculate only after deletion, while preserving historical summaries if
    # dated flights disappear but Imported balances still exist.
    if not flight.exists() and not imported.exists():
        Stat.objects.filter(user=instance.user, aircraft_type=str(instance.aircraft_type)).delete()
        return
    stat, _ = Stat.objects.get_or_create(user=instance.user, aircraft_type=str(instance.aircraft_type))

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


@receiver(pre_save, sender=Flight)
@receiver(pre_save, sender=Imported)
def remember_summary_aircraft(sender, instance, **kwargs):
    instance._previous_summary_aircraft_id = None
    if instance.pk:
        instance._previous_summary_aircraft_id = sender.objects.filter(
            pk=instance.pk, user_id=instance.user_id).values_list('aircraft_type_id', flat=True).first()


@receiver(post_save, sender=Flight)
@receiver(post_save, sender=Imported)
def refresh_previous_aircraft_summary(sender, instance, **kwargs):
    from types import SimpleNamespace
    previous_id = getattr(instance, '_previous_summary_aircraft_id', None)
    if previous_id and previous_id != instance.aircraft_type_id:
        previous = Aircraft.objects.filter(pk=previous_id, user_id=instance.user_id).first()
        if previous:
            stat_update(sender, SimpleNamespace(user=instance.user, aircraft_type=previous))
