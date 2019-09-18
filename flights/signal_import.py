from flights.models import Total, Imported
from django.db.models.signals import pre_save, post_save, post_delete
from django.db.models import Sum, Q
import datetime
from flights.queryset_helpers import *
from django.dispatch import receiver

@receiver(post_save, sender=Imported)
@receiver(post_delete, sender=Imported)
def update_total(sender, instance, **kwargs):

    user = instance.user
    total = Total.objects.filter(user=user).get(total='All')
    amel = Total.objects.filter(user=user).get(total='AMEL')
    asel = Total.objects.filter(user=user).get(total='ASEL')
    ames = Total.objects.filter(user=user).get(total='AMES')
    ases = Total.objects.filter(user=user).get(total='ASES')
    helo = Total.objects.filter(user=user).get(total='HELO')
    gyro = Total.objects.filter(user=user).get(total='GYRO')

    asel_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains = 'single engine land') & Q(aircraft_type__aircraft_category__aircraft_category__icontains = 'airplane')
    amel_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains = 'multi engine land') & Q(aircraft_type__aircraft_category__aircraft_category__icontains = 'airplane')
    ases_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains = 'single engine sea') & Q(aircraft_type__aircraft_category__aircraft_category__icontains = 'airplane')
    ases_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains = 'multi engine sea') & Q(aircraft_type__aircraft_category__aircraft_category__icontains = 'airplane')
    helo_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains = 'helicopter') & Q(aircraft_type__aircraft_category__aircraft_category__icontains = 'rotorcraft')
    gyro_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains = 'gyroplane') & Q(aircraft_type__aircraft_category__aircraft_category__icontains = 'rotorcraft')

    imported = Imported.objects.filter(user=user)

    total.total_time = total.total_time + avoid_none_duration(imported.aggregate(Sum('total_time')))
    print(total.total_time)
    total.pilot_in_command = total.pilot_in_command
    total.second_in_command = total.second_in_command
    total.cross_country = total.cross_country
    total.instructor = total.instructor
    total.dual = total.dual
    total.solo = total.solo
    total.instrument = total.instrument
    total.simulated_instrument = total.simulated_instrument
    total.simulator = total.simulator
    total.night = total.night
    total.landings_day = total.landings_day
    total.landings_night = total.landings_night
    total.landings_total = total.landings_total
    #
    # try:
    #     last_flown = flight_queryset.latest('date')
    #     total.last_flown = last_flown.date
    # except:
    #     total.last_flown = None
    #
    # today = datetime.date.today()
    #
    # last_30 = today - datetime.timedelta(days=30)
    # last_30 = flight_queryset.filter(date__lte=today,date__gte=last_30).aggregate(Sum('duration'))
    # last_30 = avoid_none_duration(last_30)
    #
    # last_60 = today - datetime.timedelta(days=60)
    # last_60 = flight_queryset.filter(date__lte=today,date__gte=last_60).aggregate(Sum('duration'))
    # last_60 = avoid_none_duration(last_60)
    #
    # last_90 = today - datetime.timedelta(days=90)
    # last_90 = flight_queryset.filter(date__lte=today,date__gte=last_90).aggregate(Sum('duration'))
    # last_90 = avoid_none_duration(last_90)
    #
    # last_180 = today - datetime.timedelta(days=180)
    # last_180 = flight_queryset.filter(date__lte=today,date__gte=last_180).aggregate(Sum('duration'))
    # last_180 = avoid_none_duration(last_180)
    #
    # last_yr = today - datetime.timedelta(days=365)
    # last_yr = flight_queryset.filter(date__lte=today,date__gte=last_yr).aggregate(Sum('duration'))
    # last_yr = avoid_none_duration(last_yr)
    #
    # last_2yr = today - datetime.timedelta(days=730)
    # last_2yr = flight_queryset.filter(date__lte=today,date__gte=last_2yr).aggregate(Sum('duration'))
    # last_2yr = avoid_none_duration(last_2yr)
    #
    # ytd = datetime.date(today.year, 1, 1)
    # ytd = flight_queryset.filter(date__lte=today,date__gte=ytd).aggregate(Sum('duration'))
    # ytd = avoid_none_duration(ytd)
    #
    #
    #

    return None
