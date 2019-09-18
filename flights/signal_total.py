from flights.models import *
from accounts.models import Profile
from django.db.models.signals import pre_save, post_save, post_delete
from django.db.models import Sum, Q
import datetime
from math import floor
from django.core.exceptions import ObjectDoesNotExist
from flights.queryset_helpers import *

@receiver(pre_save, sender=Profile)
def create_total_instances(sender, instance, **kwargs):
    user = instance.user

    total = Total.objects.get_or_create(user = user, total = 'All',)
    amel = Total.objects.get_or_create(user = user, total = 'AMEL',)
    asel = Total.objects.get_or_create(user = user, total = 'ASEL',)
    ames = Total.objects.get_or_create(user = user, total = 'AMES',)
    ases = Total.objects.get_or_create(user = user, total = 'ASES',)
    helo = Total.objects.get_or_create(user = user, total = 'HELO',)
    gyro = Total.objects.get_or_create(user = user, total = 'GYRO',)

@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
def total_update(sender, instance, **kwargs):

    user = instance.user
    flight_queryset = Flight.objects.filter(user=user)

    try:
        total = Total.objects.filter(user=user).get(total='All')
        amel = Total.objects.filter(user=user).get(total='AMEL')
        asel = Total.objects.filter(user=user).get(total='ASEL')
        ames = Total.objects.filter(user=user).get(total='AMES')
        ases = Total.objects.filter(user=user).get(total='ASES')
        helo = Total.objects.filter(user=user).get(total='HELO')
        gyro = Total.objects.filter(user=user).get(total='GYRO')

        total.total_time = amel.total_time + asel.total_time + ames.total_time + ases.total_time + helo.total_time + gyro.total_time

        total.pilot_in_command = amel.pilot_in_command + asel.pilot_in_command + ames.pilot_in_command + ases.pilot_in_command + helo.pilot_in_command + gyro.pilot_in_command

        total.second_in_command = amel.second_in_command + asel.second_in_command + ames.second_in_command + ases.second_in_command + helo.second_in_command + gyro.second_in_command

        total.cross_country = amel.cross_country + asel.cross_country + ames.cross_country + ases.cross_country + helo.cross_country + gyro.cross_country

        total.instructor = amel.instructor + asel.instructor + ames.instructor + ases.instructor + helo.instructor + gyro.instructor

        total.dual = amel.dual + asel.dual + ames.dual + ases.dual + helo.dual + gyro.dual

        total.solo = amel.solo + asel.solo + ames.solo + ases.solo + helo.solo + gyro.solo

        total.instrument = amel.instrument + asel.instrument + ames.instrument + ases.instrument + helo.instrument + gyro.instrument

        total.simulated_instrument = amel.simulated_instrument + asel.simulated_instrument + ames.simulated_instrument + ases.simulated_instrument + helo.simulated_instrument + gyro.simulated_instrument

        total.simulator = amel.simulator + asel.simulator + ames.simulator + ases.simulator + helo.simulator + gyro.simulator

        total.night = amel.night + asel.night + ames.night + ases.night + helo.night + gyro.night

        total.landings_day = amel.landings_day + asel.landings_day + ames.landings_day + ases.landings_day + helo.landings_day + gyro.landings_day

        total.landings_night = amel.landings_night + asel.landings_night + ames.landings_night + ases.landings_night + helo.landings_night + gyro.landings_night

        total.landings_total = total.landings_day + total.landings_night

        try:
            last_flown = flight_queryset.latest('date')
            total.last_flown = last_flown.date
        except:
            total.last_flown = None

        today = datetime.date.today()

        last_30 = today - datetime.timedelta(days=30)
        last_30 = flight_queryset.filter(date__lte=today,date__gte=last_30).aggregate(Sum('duration'))
        last_30 = avoid_none_duration(last_30)

        last_60 = today - datetime.timedelta(days=60)
        last_60 = flight_queryset.filter(date__lte=today,date__gte=last_60).aggregate(Sum('duration'))
        last_60 = avoid_none_duration(last_60)

        last_90 = today - datetime.timedelta(days=90)
        last_90 = flight_queryset.filter(date__lte=today,date__gte=last_90).aggregate(Sum('duration'))
        last_90 = avoid_none_duration(last_90)

        last_180 = today - datetime.timedelta(days=180)
        last_180 = flight_queryset.filter(date__lte=today,date__gte=last_180).aggregate(Sum('duration'))
        last_180 = avoid_none_duration(last_180)

        last_yr = today - datetime.timedelta(days=365)
        last_yr = flight_queryset.filter(date__lte=today,date__gte=last_yr).aggregate(Sum('duration'))
        last_yr = avoid_none_duration(last_yr)

        last_2yr = today - datetime.timedelta(days=730)
        last_2yr = flight_queryset.filter(date__lte=today,date__gte=last_2yr).aggregate(Sum('duration'))
        last_2yr = avoid_none_duration(last_2yr)

        ytd = datetime.date(today.year, 1, 1)
        ytd = flight_queryset.filter(date__lte=today,date__gte=ytd).aggregate(Sum('duration'))
        ytd = avoid_none_duration(ytd)

        total.save()

    except ObjectDoesNotExist:
        pass
