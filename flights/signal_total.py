from django.db.models import Q
import datetime
from django.core.exceptions import ObjectDoesNotExist
from flights.queryset_helpers import avoid_none
from logbook.celery import app
import json
from django.core import serializers


@app.task
def total_all_update(data):

    from flights.models import Total, Flight, Imported

    for obj in serializers.deserialize("json", data):
        user = obj.object.user
        pk = obj.object.pk
        aircaft_type = obj.object.aircraft_type

    flight = Flight.objects.filter(user=user)

    try:
        instance = Flight.objects.get(pk=pk)

    except ObjectDoesNotExist:
        instance = Flight.objects.get(user=user, aircraft_type=aircraft_type).latest('date')

    imported = Imported.objects.filter(user=user)

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
        key = str(object.total)
        flight = flight_queries[key]
        imported = imported_queries[key]

        object.total_time = avoid_none(flight, 'duration') + avoid_none(imported, 'total_time')
        print(object.total_time)

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

        try:
            last_flown = flight.latest('date')
            object.last_flown = last_flown.date

        except ObjectDoesNotExist:
            object.last_flown = None

        today = datetime.date.today()

        last_30 = today - datetime.timedelta(days=30)
        last_30 = flight.filter(date__lte=today, date__gte=last_30)
        object.last_30 = avoid_none(last_30, 'duration') + avoid_none(imported, 'last_30')

        last_60 = today - datetime.timedelta(days=60)
        last_60 = flight.filter(date__lte=today, date__gte=last_60)
        object.last_60 = avoid_none(last_60, 'duration') + avoid_none(imported, 'last_60')

        last_90 = today - datetime.timedelta(days=90)
        last_90 = flight.filter(date__lte=today, date__gte=last_90)
        object.last_90 = avoid_none(last_90, 'duration') + avoid_none(imported, 'last_90')

        last_180 = today - datetime.timedelta(days=180)
        last_180 = flight.filter(date__lte=today, date__gte=last_180)
        object.last_180 = avoid_none(last_180, 'duration') + avoid_none(imported, 'last_180')

        last_yr = today - datetime.timedelta(days=365)
        last_yr = flight.filter(date__lte=today, date__gte=last_yr)
        object.last_yr = avoid_none(last_yr, 'duration') + avoid_none(imported, 'last_yr')

        last_2yr = today - datetime.timedelta(days=730)
        last_2yr = flight.filter(date__lte=today, date__gte=last_2yr)
        object.last_2yr = avoid_none(last_2yr, 'duration') + avoid_none(imported, 'last_2yr')

        ytd = datetime.date(today.year, 1, 1)
        ytd = flight.filter(date__lte=today, date__gte=ytd)
        object.ytd = avoid_none(ytd, 'duration') + avoid_none(imported, 'ytd')

        object.save()
