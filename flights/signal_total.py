from flights.queryset_helpers import is_user_deletion
from flights.models import Total, Flight, Imported

from django.db.models.signals import post_save, post_delete
from flights.aircraft_classification import summary_key

from django.core.exceptions import ObjectDoesNotExist
from flights.queryset_helpers import avoid_none
from flights.rolling_stats import assign_rolling_values, normalize_total_category, CATEGORY_FILTERS
from django.dispatch import receiver


@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
@receiver(post_save, sender=Imported)
@receiver(post_delete, sender=Imported)
def total_all_update(sender, instance, dispatch_uid="total_all_update", **kwargs):
    if is_user_deletion(kwargs.get('origin')):
        return

    all_sessions = Flight.objects.filter(user=instance.user)
    flight = all_sessions.exclude(simulator=True)
    imported = Imported.objects.filter(user=instance.user)

    flight_queries = {key: flight.filter(scope) for key, scope in CATEGORY_FILTERS.items()}
    imported_queries = {key: imported.filter(scope) for key, scope in CATEGORY_FILTERS.items()}
    key = summary_key(instance.aircraft_type.aircraft_category, instance.aircraft_type.aircraft_class)
    if key:
        Total.objects.get_or_create(user=instance.user, total=key)

    total = Total.objects.filter(user=instance.user)

    for object in total:
        key = normalize_total_category(object.total)
        if key is None:
            continue  # Preserve unsupported legacy rows for operator review.
        flight = flight_queries[key]
        imported = imported_queries[key]

        object.total_time = avoid_none(flight, 'duration') + avoid_none(imported, 'total_time')

        object.pilot_in_command = avoid_none(flight.filter(pilot_in_command=True), 'duration') + avoid_none(imported, 'pilot_in_command')

        object.second_in_command = avoid_none(flight.filter(second_in_command=True), 'duration') + avoid_none(imported, 'second_in_command')

        object.cross_country = avoid_none(flight.filter(cross_country=True), 'duration') + avoid_none(imported, 'cross_country')

        object.instructor = avoid_none(flight.filter(instructor=True), 'duration') + avoid_none(imported, 'instructor')

        object.dual = avoid_none(flight.filter(dual=True), 'duration') + avoid_none(imported, 'dual')

        object.solo = avoid_none(flight.filter(solo=True), 'duration') + avoid_none(imported, 'solo')

        object.instrument = avoid_none(flight, 'instrument') + avoid_none(imported, 'instrument')

        object.simulated_instrument = avoid_none(flight, 'simulated_instrument') + avoid_none(imported, 'simulated_instrument')

        object.simulator = avoid_none(all_sessions.filter(simulator=True).filter(
            CATEGORY_FILTERS[key]), 'duration') + avoid_none(imported, 'simulator')

        object.night = avoid_none(flight, 'night') + avoid_none(imported, 'night')

        object.landings_day = avoid_none(flight, 'landings_day') + avoid_none(imported, 'landings_day')

        object.landings_night = avoid_none(flight, 'landings_night') + avoid_none(imported, 'landings_night')

        object.landings_total = object.landings_day + object.landings_night

        assign_rolling_values(object, flight, imported)
        object.save()
