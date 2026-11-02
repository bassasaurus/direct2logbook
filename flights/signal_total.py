from flights.models import Total, Flight, Imported

from django.db.models.signals import post_save, post_delete
from django.db.models import Q

from django.core.exceptions import ObjectDoesNotExist
from flights.queryset_helpers import avoid_none
from flights.rolling_stats import assign_rolling_values, normalize_total_category
from django.dispatch import receiver


@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
@receiver(post_save, sender=Imported)
@receiver(post_delete, sender=Imported)
def total_all_update(sender, instance, dispatch_uid="total_all_update", **kwargs):

    flight = Flight.objects.filter(user=instance.user)
    imported = Imported.objects.filter(user=instance.user)

    asel_query = Q(aircraft_type__aircraft_category='A') & Q(aircraft_type__aircraft_class='SEL')
    amel_query = Q(aircraft_type__aircraft_category='A') & Q(aircraft_type__aircraft_class='MEL')
    ases_query = Q(aircraft_type__aircraft_category='A') & Q(aircraft_type__aircraft_class='SES')
    ames_query = Q(aircraft_type__aircraft_category='A') & Q(aircraft_type__aircraft_class='MES')
    helo_query = Q(aircraft_type__aircraft_category='R') & Q(aircraft_type__aircraft_class='HELO')
    gyro_query = Q(aircraft_type__aircraft_category='R') & Q(aircraft_type__aircraft_class='GYRO')

    flight_queries = {
                    'All': flight,
                    'ASEL': flight.filter(asel_query),
                    'AMEL': flight.filter(amel_query),
                    'ASES': flight.filter(ases_query),
                    'AMES': flight.filter(ames_query),
                    'HELO': flight.filter(helo_query),
                    'GYRO': flight.filter(gyro_query),
                }

    imported_queries = {
                    'All': imported,
                    'ASEL': imported.filter(asel_query),
                    'AMEL': imported.filter(amel_query),
                    'ASES': imported.filter(ases_query),
                    'AMES': imported.filter(ames_query),
                    'HELO': imported.filter(helo_query),
                    'GYRO': imported.filter(gyro_query),
                }

    if str(instance.aircraft_type.aircraft_category) == "A" and str(instance.aircraft_type.aircraft_class) == 'SEL':
        Total.objects.get_or_create(user=instance.user, total='ASEL',)

    elif str(instance.aircraft_type.aircraft_category) == "A" and str(instance.aircraft_type.aircraft_class) == 'MEL':
        Total.objects.get_or_create(user=instance.user, total='AMEL',)

    elif str(instance.aircraft_type.aircraft_category) == "A" and str(instance.aircraft_type.aircraft_class) == 'SES':
        Total.objects.get_or_create(user=instance.user, total='ASES',)

    elif str(instance.aircraft_type.aircraft_category) == "A" and str(instance.aircraft_type.aircraft_class) == 'MES':
        Total.objects.get_or_create(user=instance.user, total='AMES',)

    elif str(instance.aircraft_type.aircraft_category) == "R" and str(instance.aircraft_type.aircraft_class) == 'HELO':
        Total.objects.get_or_create(user=instance.user, total='HELO',)

    elif str(instance.aircraft_type.aircraft_category) == "R" and str(instance.aircraft_type.aircraft_class) == 'GYRO':
        Total.objects.get_or_create(user=instance.user, total='GYRO',)

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

        object.simulator = avoid_none(flight.filter(simulator=True), 'duration') + avoid_none(imported, 'simulator')

        object.night = avoid_none(flight, 'night') + avoid_none(imported, 'night')

        object.landings_day = avoid_none(flight, 'landings_day') + avoid_none(imported, 'landings_day')

        object.landings_night = avoid_none(flight, 'landings_night') + avoid_none(imported, 'landings_night')

        object.landings_total = object.landings_day + object.landings_night

        assign_rolling_values(object, flight, imported)
        object.save()
