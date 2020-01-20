from logbook.celery import app
from flights.queryset_helpers import avoid_none, zero_if_none
from django.core.exceptions import ObjectDoesNotExist
import datetime
from django.core import serializers


@app.task
def stat_update(data):

    from flights.models import Flight, Stat, Imported

    for obj in serializers.deserialize("json", data):
        user = obj.object.user
        aircraft_type = obj.object.aircraft_type

    stat = Stat.objects.get_or_create(user=user, aircraft_type=aircraft_type)
    stat = stat[0]

    flight = Flight.objects.filter(user=user).filter(aircraft_type=aircraft_type)
    imported = Imported.objects.filter(user=user).filter(aircraft_type=aircraft_type)

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
        flight_last_flown = flight.latest('date').date
    except ObjectDoesNotExist:
        flight_last_flown = datetime.date(1900, 1, 1)

    try:
        imported_last_flown = imported.latest('last_flown').last_flown
    except ObjectDoesNotExist:
        imported_last_flown = flight.latest('date').date
    finally:
        imported_last_flown = datetime.date(1900, 1, 1)

    stat.last_flown = max(flight_last_flown, imported_last_flown)

    today = datetime.date.today()

    last_30 = today - datetime.timedelta(days=30)
    last_30 = flight.filter(date__lte=today, date__gte=last_30)
    stat.last_30 = avoid_none(last_30, 'duration') + avoid_none(imported, 'last_30')

    last_60 = today - datetime.timedelta(days=60)
    last_60 = flight.filter(date__lte=today, date__gte=last_60)
    stat.last_60 = avoid_none(last_60, 'duration') + avoid_none(imported, 'last_60')

    last_90 = today - datetime.timedelta(days=90)
    last_90 = flight.filter(date__lte=today, date__gte=last_90)
    stat.last_90 = avoid_none(last_90, 'duration') + avoid_none(imported, 'last_90')

    last_180 = today - datetime.timedelta(days=180)
    last_180 = flight.filter(date__lte=today, date__gte=last_180)
    stat.last_180 = avoid_none(last_180, 'duration') + avoid_none(imported, 'last_180')

    last_yr = today - datetime.timedelta(days=365)
    last_yr = flight.filter(date__lte=today, date__gte=last_yr)
    stat.last_yr = avoid_none(last_yr, 'duration') + avoid_none(imported, 'last_yr')

    last_2yr = today - datetime.timedelta(days=730)
    last_2yr = flight.filter(date__lte=today, date__gte=last_2yr)
    stat.last_2yr = avoid_none(last_2yr, 'duration') + avoid_none(imported, 'last_2yr')

    ytd = datetime.date(today.year, 1, 1)
    ytd = flight.filter(date__lte=today, date__gte=ytd)
    stat.ytd = avoid_none(ytd, 'duration') + avoid_none(imported, 'ytd')

    stat.save()
