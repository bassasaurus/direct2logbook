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
@receiver(post_save, sender=Imported)
@receiver(post_delete, sender=Flight)
@receiver(post_delete, sender=Imported)
def total_update(sender, instance, **kwargs):

    cat_class_sort_total(instance)

    flight = Flight.objects.filter(user=instance.user)
    imported = Imported.objects.filter(user=instance.user)

    total = Total.objects.get_or_create(user=instance.user, total='All')
    total = total[0]

    total.total_time = avoid_none(flight, 'duration') + avoid_none(imported, 'total_time')

    total.pilot_in_command = avoid_none(flight.filter(pilot_in_command=True), 'duration') + avoid_none(imported, 'pilot_in_command')

    total.second_in_command = avoid_none(flight.filter(second_in_command=True), 'duration') + avoid_none(imported, 'second_in_command')

    total.cross_country = avoid_none(flight.filter(cross_country=True), 'duration') + avoid_none(imported, 'cross_country')

    total.instructor = avoid_none(flight.filter(instructor=True), 'duration') + avoid_none(imported, 'instructor')

    total.dual =avoid_none(flight.filter(dual=True), 'duration') + avoid_none(imported, 'dual')

    total.solo = avoid_none(flight.filter(solo=True), 'duration') + avoid_none(imported, 'solo')

    total.instrument = avoid_none(flight, 'instrument') + avoid_none(imported, 'instrument')

    total.simulated_instrument = avoid_none(flight, 'simulated_instrument') + avoid_none(imported, 'simulated_instrument')

    total.simulator = avoid_none(flight.filter(simulator=True), 'duration') + avoid_none(imported, 'simulator')

    total.night = avoid_none(flight, 'night') + avoid_none(imported, 'night')

    total.landings_day = avoid_none(flight, 'landings_day') + avoid_none(imported, 'landings_day')

    total.landings_night = avoid_none(flight, 'landings_night') + avoid_none(imported, 'landings_night')

    total.landings_total = total.landings_day + total.landings_night + avoid_none(imported, 'landings_night') + avoid_none(imported, 'landings_day')

    try:
        last_flown = flight.latest('date')
        total.last_flown = last_flown.date
    except:
        total.last_flown = None

    today = datetime.date.today()

    last_30 = today - datetime.timedelta(days=30)
    last_30 = flight.filter(date__lte=today,date__gte=last_30)
    total.last_30 = avoid_none(last_30, 'duration') + avoid_none(imported, 'last_30')

    last_60 = today - datetime.timedelta(days=60)
    last_60 = flight.filter(date__lte=today,date__gte=last_60)
    total.last_60 = avoid_none(last_60, 'duration') + avoid_none(imported, 'last_60')

    last_90 = today - datetime.timedelta(days=90)
    last_90 = flight.filter(date__lte=today,date__gte=last_90)
    total.last_90 = avoid_none(last_90, 'duration') + avoid_none(imported, 'last_90')

    last_180 = today - datetime.timedelta(days=180)
    last_180 = flight.filter(date__lte=today,date__gte=last_180)
    total.last_180 = avoid_none(last_180, 'duration') + avoid_none(imported, 'last_180')

    last_yr = today - datetime.timedelta(days=365)
    last_yr = flight.filter(date__lte=today,date__gte=last_yr)
    total.last_yr = avoid_none(last_yr, 'duration') + avoid_none(imported, 'last_yr')

    last_2yr = today - datetime.timedelta(days=730)
    last_2yr = flight.filter(date__lte=today,date__gte=last_2yr)
    total.last_2yr = avoid_none(last_2yr, 'duration') + avoid_none(imported, 'last_2yr')

    ytd = datetime.date(today.year, 1, 1)
    ytd = flight.filter(date__lte=today,date__gte=ytd)
    total.ytd = avoid_none(ytd, 'duration') + avoid_none(imported, 'ytd')

    total.save()
