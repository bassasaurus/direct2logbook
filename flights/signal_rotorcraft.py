from flights.models import *
from django.db.models.signals import pre_save, post_save, post_delete
from django.db.models import Sum, Q
import datetime


@receiver(post_save, sender=Aircraft)
@receiver(post_delete, sender=Aircraft)
@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
def helo_update(sender, instance, **kwargs):
    today = datetime.date.today()

    user = instance.user

    helo = Total.objects.get(total='HELO')
    cat_class_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains='helicopter') & Q(
        aircraft_type__aircraft_category__aircraft_category__icontains='rotorcraft')

    total_time = Flight.objects.filter(user=user).filter(
        cat_class_query).aggregate(Sum('duration'))
    if total_time.get('duration__sum') is None:
        helo.total_time = 0
    else:
        helo.total_time = total_time.get('duration__sum')

    pilot_in_command = Flight.objects.filter(user=user).filter(
        cat_class_query, pilot_in_command=True).aggregate(Sum('duration'))
    if pilot_in_command.get('duration__sum') is None:
        helo.pilot_in_command = 0
    else:
        helo.pilot_in_command = pilot_in_command.get('duration__sum')

    second_in_command = Flight.objects.filter(user=user).filter(
        cat_class_query, second_in_command=True).aggregate(Sum('duration'))
    if second_in_command.get('duration__sum') is None:
        helo.second_in_command = 0
    else:
        helo.second_in_command = second_in_command.get('duration__sum')

    cross_country = Flight.objects.filter(user=user).filter(
        cat_class_query, cross_country=True).aggregate(Sum('duration'))
    if cross_country.get('duration__sum') is None:
        helo.cross_country = 0
    else:
        helo.cross_country = cross_country.get('duration__sum')

    instructor = Flight.objects.filter(user=user).filter(
        cat_class_query, instructor=True).aggregate(Sum('duration'))
    if instructor.get('duration__sum') is None:
        helo.instructor = 0
    else:
        helo.instructor = instructor.get('duration__sum')

    dual = Flight.objects.filter(user=user).filter(
        cat_class_query, dual=True).aggregate(Sum('duration'))
    if dual.get('duration__sum') is None:
        helo.dual = 0
    else:
        helo.dual = dual.get('duration__sum')

    solo = Flight.objects.filter(user=user).filter(
        cat_class_query, solo=True).aggregate(Sum('duration'))
    if solo.get('duration__sum') is None:
        helo.solo = 0
    else:
        helo.solo = solo.get('duration__sum')

    instrument = Flight.objects.filter(user=user).filter(
        cat_class_query, instrument__gt=0).aggregate(Sum('instrument'))
    if instrument.get('instrument__sum') is None:
        helo.instrument = 0
    else:
        helo.instrument = instrument.get('instrument__sum')

    simulated_instrument = Flight.objects.filter(user=user).filter(
        cat_class_query, simulated_instrument__gt=0).aggregate(Sum('simulated_instrument'))
    if simulated_instrument.get('simulated_instrument__sum') is None:
        helo.simulated_instrument = 0
    else:
        helo.simulated_instrument = simulated_instrument.get(
            'simulated_instrument__sum')

    simulator = Flight.objects.filter(user=user).filter(
        cat_class_query, simulator=True).aggregate(Sum('duration'))
    if not simulator.get('duration__sum'):
        helo.simulator = 0
    else:
        helo.simulator = simulator.get('duration__sum')

    night = Flight.objects.filter(user=user).filter(
        cat_class_query, night__gt=0).aggregate(Sum('night'))
    if night.get('night__sum') is None:
        helo.night = 0
    else:
        helo.night = night.get('night__sum')

    landings_day = Flight.objects.filter(user=user).filter(
        cat_class_query).aggregate(Sum('landings_day'))
    if not landings_day.get('landings_day__sum'):
        helo.landings_day = 0
    else:
        helo.landings_day = landings_day.get('landings_day__sum')

    landings_night = Flight.objects.filter(user=user).filter(
        cat_class_query).filter(cat_class_query).aggregate(Sum('landings_night'))
    if not landings_night.get('landings_night__sum'):
        helo.landings_night = 0
    else:
        helo.landings_night = landings_night.get('landings_night__sum')

    helo.landings_total = helo.landings_day + helo.landings_night

    try:
        last_flown = Flight.objects.filter(
            user=user).filter(cat_class_query).latest('date')
        helo.last_flown = last_flown.date
    except:
        helo.last_flown = None

    last_30 = today - datetime.timedelta(days=30)
    last_30 = Flight.objects.filter(user=user).filter(cat_class_query).filter(
        date__lte=today, date__gte=last_30).aggregate(Sum('duration'))
    if last_30.get('duration__sum') is None:
        helo.last_30 = 0
    else:
        helo.last_30 = last_30.get('duration__sum')

    last_60 = today - datetime.timedelta(days=60)
    last_60 = Flight.objects.filter(user=user).filter(cat_class_query).filter(
        date__lte=today, date__gte=last_60).aggregate(Sum('duration'))
    if last_60.get('duration__sum') is None:
        helo.last_60 = 0
    else:
        helo.last_60 = last_60.get('duration__sum')

    last_90 = today - datetime.timedelta(days=90)
    last_90 = Flight.objects.filter(user=user).filter(cat_class_query).filter(
        date__lte=today, date__gte=last_90).aggregate(Sum('duration'))
    if last_90.get('duration__sum') is None:
        helo.last_90 = 0
    else:
        helo.last_90 = last_90.get('duration__sum')

    last_180 = today - datetime.timedelta(days=180)
    last_180 = Flight.objects.filter(user=user).filter(cat_class_query).filter(
        date__lte=today, date__gte=last_180).aggregate(Sum('duration'))
    if last_180.get('duration__sum') is None:
        helo.last_180 = 0
    else:
        helo.last_180 = last_180.get('duration__sum')

    last_yr = today - datetime.timedelta(days=365)
    last_yr = Flight.objects.filter(user=user).filter(cat_class_query).filter(
        date__lte=today, date__gte=last_yr).aggregate(Sum('duration'))
    if last_yr.get('duration__sum') is None:
        helo.last_yr = 0
    else:
        helo.last_yr = last_yr.get('duration__sum')

    last_2yr = today - datetime.timedelta(days=730)
    last_2yr = Flight.objects.filter(user=user).filter(cat_class_query).filter(
        date__lte=today, date__gte=last_2yr).aggregate(Sum('duration'))
    if last_2yr.get('duration__sum') is None:
        helo.last_2yr = 0
    else:
        helo.last_2yr = last_2yr.get('duration__sum')

    ytd = datetime.date(today.year, 1, 1)
    ytd = Flight.objects.filter(user=user).filter(cat_class_query).filter(
        date__lte=today, date__gte=ytd).aggregate(Sum('duration'))
    if ytd.get('duration__sum') is None:
        helo.ytd = 0
    else:
        helo.ytd = ytd.get('duration__sum')

    helo.save()


@receiver(post_save, sender=Aircraft)
@receiver(post_delete, sender=Aircraft)
@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
def asel_updater(sender, instance, **kwargs):
    today = datetime.date.today()

    user = instance.user

    gyro = Total.objects.get(total='GYRO')
    cat_class_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains='gyroplane') & Q(
        aircraft_type__aircraft_category__aircraft_category__icontains='rotorcraft')

    total_time = Flight.objects.filter(user=user).filter(
        cat_class_query).aggregate(Sum('duration'))
    if total_time.get('duration__sum') is None:
        gyro.total_time = 0
    else:
        gyro.total_time = total_time.get('duration__sum')

    pilot_in_command = Flight.objects.filter(user=user).filter(cat_class_query).filter(
        cat_class_query).filter(pilot_in_command=True).aggregate(Sum('duration'))
    if pilot_in_command.get('duration__sum') is None:
        gyro.pilot_in_command = 0
    else:
        gyro.pilot_in_command = pilot_in_command.get('duration__sum')

    second_in_command = Flight.objects.filter(user=user).filter(cat_class_query).filter(
        cat_class_query).filter(second_in_command=True).aggregate(Sum('duration'))
    if second_in_command.get('duration__sum') is None:
        gyro.second_in_command = 0
    else:
        gyro.second_in_command = second_in_command.get('duration__sum')

    cross_country = Flight.objects.filter(user=user).filter(
        cat_class_query).filter(cross_country=True).aggregate(Sum('duration'))
    if cross_country.get('duration__sum') is None:
        gyro.cross_country = 0
    else:
        gyro.cross_country = cross_country.get('duration__sum')

    instructor = Flight.objects.filter(user=user).filter(
        cat_class_query).filter(instructor=True).aggregate(Sum('duration'))
    if instructor.get('duration__sum') is None:
        gyro.instructor = 0
    else:
        gyro.instructor = instructor.get('duration__sum')

    dual = Flight.objects.filter(user=user).filter(
        cat_class_query).filter(dual=True).aggregate(Sum('duration'))
    if dual.get('duration__sum') is None:
        gyro.dual = 0
    else:
        gyro.dual = dual.get('duration__sum')

    solo = Flight.objects.filter(user=user).filter(
        cat_class_query).filter(solo=True).aggregate(Sum('duration'))
    if solo.get('duration__sum') is None:
        gyro.solo = 0
    else:
        gyro.solo = solo.get('duration__sum')

    instrument = Flight.objects.filter(user=user).filter(
        cat_class_query).filter(instrument=True).aggregate(Sum('duration'))
    if instrument.get('duration__sum') is None:
        gyro.instrument = 0
    else:
        gyro.instrument = instrument.get('duration__sum')

    simulated_instrument = Flight.objects.filter(user=user).filter(
        cat_class_query).aggregate(Sum('simulated_instrument'))
    if simulated_instrument.get('duration__sum') is None:
        gyro.simulated_instrument = 0
    else:
        gyro.simulated_instrument = simulated_instrument.get(
            'simulated_instrument__sum')

    simulator = Flight.objects.filter(user=user).filter(
        cat_class_query, simulator=True).aggregate(Sum('duration'))
    if simulator.get('duration__sum') is None:
        gyro.simulator = 0
    else:
        gyro.simulator = simulator.get('duration__sum')

    night = Flight.objects.filter(user=user).filter(
        cat_class_query).aggregate(Sum('night'))
    if night.get('duration__sum') is None:
        gyro.night = 0
    else:
        gyro.night = night.get('night__sum')

    landings_day = Flight.objects.filter(user=user).filter(
        cat_class_query).aggregate(Sum('landings_day'))
    if not landings_day.get('landings_day__sum'):
        gyro.landings_day = 0
    else:
        gyro.landings_day = landings_day.get('landings_day__sum')

    landings_night = Flight.objects.filter(user=user).filter(
        cat_class_query).filter(cat_class_query).aggregate(Sum('landings_night'))
    if not landings_night.get('landings_night__sum'):
        gyro.landings_night = 0
    else:
        gyro.landings_night = landings_night.get('landings_night__sum')

    gyro.landings_total = gyro.landings_day + gyro.landings_night

    try:
        last_flown = Flight.objects.filter(cat_class_query).latest('date')
        gyro.last_flown = last_flown.date
    except:
        gyro.last_flown = None

    last_30 = today - datetime.timedelta(days=30)
    last_30 = Flight.objects.filter(cat_class_query).filter(
        date__lte=today, date__gte=last_30).aggregate(Sum('duration'))
    if last_30.get('duration__sum') is None:
        gyro.last_30 = 0
    else:
        gyro.last_30 = last_30.get('duration__sum')

    last_60 = today - datetime.timedelta(days=60)
    last_60 = Flight.objects.filter(cat_class_query).filter(
        date__lte=today, date__gte=last_60).aggregate(Sum('duration'))
    if last_60.get('duration__sum') is None:
        gyro.last_60 = 0
    else:
        gyro.last_60 = last_60.get('duration__sum')

    last_90 = today - datetime.timedelta(days=90)
    last_90 = Flight.objects.filter(cat_class_query).filter(
        date__lte=today, date__gte=last_90).aggregate(Sum('duration'))
    if last_90.get('duration__sum') is None:
        gyro.last_90 = 0
    else:
        gyro.last_90 = last_90.get('duration__sum')

    last_180 = today - datetime.timedelta(days=180)
    last_180 = Flight.objects.filter(cat_class_query).filter(
        date__lte=today, date__gte=last_180).aggregate(Sum('duration'))
    if last_180.get('duration__sum') is None:
        gyro.last_180 = 0
    else:
        gyro.last_180 = last_180.get('duration__sum')

    last_yr = today - datetime.timedelta(days=365)
    last_yr = Flight.objects.filter(cat_class_query).filter(
        date__lte=today, date__gte=last_yr).aggregate(Sum('duration'))
    if last_yr.get('duration__sum') is None:
        gyro.last_yr = 0
    else:
        gyro.last_yr = last_yr.get('duration__sum')

    last_2yr = today - datetime.timedelta(days=730)
    last_2yr = Flight.objects.filter(cat_class_query).filter(
        date__lte=today, date__gte=last_2yr).aggregate(Sum('duration'))
    if last_2yr.get('duration__sum') is None:
        gyro.last_2yr = 0
    else:
        gyro.last_2yr = last_2yr.get('duration__sum')

    ytd = datetime.date(today.year, 1, 1)
    ytd = Flight.objects.filter(cat_class_query).filter(
        date__lte=today, date__gte=ytd).aggregate(Sum('duration'))
    if ytd.get('duration__sum') is None:
        gyro.ytd = 0
    else:
        gyro.ytd = ytd.get('duration__sum')

    gyro.save()
