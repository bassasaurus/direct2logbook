from django.db.models import Sum, Q
from decimal import *
from .models import Total, Flight, Imported
import datetime

getcontext().prec = 1


def avoid_none(queryset, field):

    field__sum = str(field + '__sum')

    queryset = queryset.aggregate(Sum(field))

    if not queryset.get(field__sum):
        return Decimal(0)
    else:
        return Decimal(queryset.get(field__sum))


def cat_class_sort_total(instance):

    flight = Flight.objects.filter(user=instance.user)
    imported = Imported.objects.filter(user=instance.user)

    asel_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains='single engine land') & Q(
        aircraft_type__aircraft_category__aircraft_category__icontains='airplane')
    amel_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains='multi engine land') & Q(
        aircraft_type__aircraft_category__aircraft_category__icontains='airplane')
    ases_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains='single engine sea') & Q(
        aircraft_type__aircraft_category__aircraft_category__icontains='airplane')
    ases_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains='multi engine sea') & Q(
        aircraft_type__aircraft_category__aircraft_category__icontains='airplane')
    helo_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains='helicopter') & Q(
        aircraft_type__aircraft_category__aircraft_category__icontains='rotorcraft')
    gyro_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains='gyroplane') & Q(
        aircraft_type__aircraft_category__aircraft_category__icontains='rotorcraft')

    if str(instance.aircraft_type.aircraft_category) == "Airplane" and str(instance.aircraft_type.aircraft_class) == 'Single Engine Land':
        object = Total.objects.get_or_create(user=instance.user, total='ASEL',)
        flight = flight.filter(asel_query)
        imported = imported.filter(asel_query)
        object = object[0]

    elif str(instance.aircraft_type.aircraft_category) == "Airplane" and str(instance.aircraft_type.aircraft_class) == 'Multi Engine Land':
        object = Total.objects.get_or_create(user=instance.user, total='AMEL',)
        flight = flight.filter(amel_query)
        imported = imported.filter(amel_query)
        object = object[0]

    elif str(instance.aircraft_type.aircraft_category) == "Airplane" and str(instance.aircraft_type.aircraft_class) == 'Single Engine Sea':
        object = Total.objects.get_or_create(user=instance.user, total='ASES',)
        flight = flight.filter(ases_query)
        imported = imported.filter(ases_query)
        object = object[0]

    elif str(instance.aircraft_type.aircraft_category) == "Airplane" and str(instance.aircraft_type.aircraft_class) == 'Multi Engine Sea':
        object = Total.objects.get_or_create(user=instance.user, total='AMES',)
        flight = flight.filter(ames_query)
        imported = imported.filter(ames_query)
        object = object[0]

    elif str(instance.aircraft_type.aircraft_category) == "Rotorcraft" and str(instance.aircraft_type.aircraft_class) == 'Helicopter':
        object = Total.objects.get_or_create(user=instance.user, total='HELO',)
        flight = flight.filter(helo_query)
        imported = imported.filter(helo_query)
        object = object[0]

    elif str(instance.aircraft_type.aircraft_category) == "Rotorcraft" and str(instance.aircraft_type.aircraft_class) == 'Gyroplane':
        object = Total.objects.get_or_create(user=instance.user, total='GYRO',)
        flight = flight.filter(gyro_query)
        imported = imported.filter(gyro_query)
        object = object[0]

    object.total_time = avoid_none(flight, 'duration') + avoid_none(imported, 'total_time')

    object.pilot_in_command = avoid_none(flight.filter(pilot_in_command=True), 'duration') + avoid_none(imported, 'pilot_in_command')

    object.second_in_command = avoid_none(flight.filter(second_in_command=True), 'duration') + avoid_none(imported, 'second_in_command')

    object.cross_country = avoid_none(flight.filter(cross_country=True), 'duration') + avoid_none(imported, 'cross_country')

    object.instructor = avoid_none(flight.filter(instructor=True), 'duration') + avoid_none(imported, 'instructor')

    object.dual = avoid_none(flight.filter(dual=True), 'duration') + avoid_none(imported, 'dual')

    object.solo = avoid_none(flight.filter(solo=True), 'duration') + avoid_none(imported, 'solo')

    object.instrument = avoid_none(flight, 'instrument') + avoid_none(imported, 'instrument')

    object.simulated_instrument = avoid_none(flight, 'simulated_instrument') + avoid_none(imported, 'simulated_instrument')

    object.simulator = avoid_none(flight.filter(simulator=True), 'duration') +  + avoid_none(imported, 'simulator')

    object.night = avoid_none(flight, 'night') + avoid_none(imported, 'night')

    object.landings_day = avoid_none(flight, 'landings_day') + avoid_none(imported, 'landings_day')

    object.landings_night = avoid_none(flight, 'landings_night') + avoid_none(imported, 'landings_night')

    object.landings_object = object.landings_day + object.landings_night + avoid_none(imported, 'landings_day') + avoid_none(imported, 'landings_night')

    try:
        last_flown = flight.latest('date')
        object.last_flown = last_flown.date
    except:
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
