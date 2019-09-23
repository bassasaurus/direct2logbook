from flights.models import *
from accounts.models import Profile
from django.db.models.signals import pre_save, post_save, post_delete
from django.db.models import Sum, Q
import datetime
from math import floor
from django.core.exceptions import ObjectDoesNotExist
from flights.queryset_helpers import *
from django.dispatch import receiver


@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
def total_update(sender, instance, **kwargs):

    cat_class_sort_total(instance)

    flight = Flight.objects.filter(user=instance.user)

    total = Total.objects.get_or_create(user=instance.user, total='All')
    total = total[0]

    total.total_time = avoid_none(flight, 'duration')

    total.pilot_in_command = avoid_none(flight.filter(pilot_in_command=True), 'duration')

    total.second_in_command = avoid_none(flight.filter(second_in_command=True), 'duration')

    total.cross_country = avoid_none(flight.filter(cross_country=True), 'duration')

    total.instructor = avoid_none(flight.filter(instructor=True), 'duration')

    total.dual =avoid_none(flight.filter(dual=True), 'duration')

    total.solo = avoid_none(flight.filter(solo=True), 'duration')

    total.instrument = avoid_none(flight, 'instrument')

    total.simulated_instrument = avoid_none(flight, 'simulated_instrument')

    total.simulator = avoid_none(flight.filter(simulator=True), 'duration')

    total.night = avoid_none(flight, 'night')

    total.landings_day = avoid_none(flight, 'landings_day')

    total.landings_night = avoid_none(flight, 'landings_night')

    total.landings_total = total.landings_day + total.landings_night

    try:
        last_flown = flight_queryset.latest('date')
        total.last_flown = last_flown.date
    except:
        total.last_flown = None

    today = datetime.date.today()

    last_30 = today - datetime.timedelta(days=30)
    last_30 = flight.filter(date__lte=today,date__gte=last_30)
    total.last_30 = avoid_none(last_30, 'duration')

    last_60 = today - datetime.timedelta(days=60)
    last_60 = flight.filter(date__lte=today,date__gte=last_60)
    total.last_60 = avoid_none(last_60, 'duration')

    last_90 = today - datetime.timedelta(days=90)
    last_90 = flight.filter(date__lte=today,date__gte=last_90)
    total.last_90 = avoid_none(last_90, 'duration')

    last_180 = today - datetime.timedelta(days=180)
    last_180 = flight.filter(date__lte=today,date__gte=last_180)
    total.last_180 = avoid_none(last_180, 'duration')

    last_yr = today - datetime.timedelta(days=365)
    last_yr = flight.filter(date__lte=today,date__gte=last_yr)
    total.last_yr = avoid_none(last_yr, 'duration')

    last_2yr = today - datetime.timedelta(days=730)
    last_2yr = flight.filter(date__lte=today,date__gte=last_2yr)
    total.last_2yr = avoid_none(last_2yr, 'duration')

    ytd = datetime.date(today.year, 1, 1)
    ytd = flight.filter(date__lte=today,date__gte=ytd)
    total.ytd = avoid_none(ytd, 'duration')

    total.save()
