from django.db.models import Sum, Q
from decimal import *
from .models import Total, Flight
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
        object = object[0]

    elif str(instance.aircraft_type.aircraft_category) == "Airplane" and str(instance.aircraft_type.aircraft_class) == 'Multi Engine Land':
        object = Total.objects.get_or_create(user=instance.user, total='AMEL',)
        flight = flight.filter(amel_query)
        object = object[0]

    elif str(instance.aircraft_type.aircraft_category) == "Airplane" and str(instance.aircraft_type.aircraft_class) == 'Single Engine Sea':
        object = Total.objects.get_or_create(user=instance.user, total='ASES',)
        flight = flight.filter(ases_query)

        object = object[0]

    elif str(instance.aircraft_type.aircraft_category) == "Airplane" and str(instance.aircraft_type.aircraft_class) == 'Multi Engine Sea':
        object = Total.objects.get_or_create(user=instance.user, total='AMES',)
        flight = flight.filter(ames_query)

        object = object[0]

    elif str(instance.aircraft_type.aircraft_category) == "Rotorcraft" and str(instance.aircraft_type.aircraft_class) == 'Helicopter':
        object = Total.objects.get_or_create(user=instance.user, total='HELO',)
        flight = flight.filter(helo_query)

        object = object[0]

    elif str(instance.aircraft_type.aircraft_category) == "Rotorcraft" and str(instance.aircraft_type.aircraft_class) == 'Gyroplane':
        object = Total.objects.get_or_create(user=instance.user, total='GYRO',)
        flight = flight.filter(gyro_query)

        object = object[0]

    object.total_time = avoid_none(flight, 'duration')

    object.pilot_in_command = avoid_none(
        flight.filter(pilot_in_command=True), 'duration')

    object.second_in_command = avoid_none(
        flight.filter(second_in_command=True), 'duration')

    object.cross_country = avoid_none(
        flight.filter(cross_country=True), 'duration')

    object.instructor = avoid_none(flight.filter(instructor=True), 'duration')

    object.dual = avoid_none(flight.filter(dual=True), 'duration')

    object.solo = avoid_none(flight.filter(solo=True), 'duration')

    object.instrument = avoid_none(flight, 'instrument')

    object.simulated_instrument = avoid_none(flight, 'simulated_instrument')

    object.simulator = avoid_none(flight.filter(simulator=True), 'duration')

    object.night = avoid_none(flight, 'night')

    object.landings_day = avoid_none(flight, 'landings_day')

    object.landings_night = avoid_none(flight, 'landings_night')

    object.landings_object = object.landings_day + object.landings_night

    try:
        last_flown = flight_queryset.latest('date')
        object.last_flown = last_flown.date
    except:
        object.last_flown = None

    today = datetime.date.today()

    last_30 = today - datetime.timedelta(days=30)
    last_30 = flight.filter(date__lte=today, date__gte=last_30)
    object.last_30 = avoid_none(last_30, 'duration')

    last_60 = today - datetime.timedelta(days=60)
    last_60 = flight.filter(date__lte=today, date__gte=last_60)
    object.last_60 = avoid_none(last_60, 'duration')

    last_90 = today - datetime.timedelta(days=90)
    last_90 = flight.filter(date__lte=today, date__gte=last_90)
    object.last_90 = avoid_none(last_90, 'duration')

    last_180 = today - datetime.timedelta(days=180)
    last_180 = flight.filter(date__lte=today, date__gte=last_180)
    object.last_180 = avoid_none(last_180, 'duration')

    last_yr = today - datetime.timedelta(days=365)
    last_yr = flight.filter(date__lte=today, date__gte=last_yr)
    object.last_yr = avoid_none(last_yr, 'duration')

    last_2yr = today - datetime.timedelta(days=730)
    last_2yr = flight.filter(date__lte=today, date__gte=last_2yr)
    object.last_2yr = avoid_none(last_2yr, 'duration')

    ytd = datetime.date(today.year, 1, 1)
    ytd = flight.filter(date__lte=today, date__gte=ytd)
    object.ytd = avoid_none(ytd, 'duration')

    object.save()
