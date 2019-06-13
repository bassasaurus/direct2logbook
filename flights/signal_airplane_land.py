from flights.models import *
from django.db.models.signals import pre_save, post_save, post_delete
from django.db.models import Sum, Q
import datetime

@receiver(post_save, sender=Aircraft)
@receiver(post_delete, sender=Aircraft)
@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
def amel_update(sender, instance, **kwargs):
    today = datetime.date.today()

    user = instance.user

    amel = Total.objects.filter(user=user).get(total='AMEL')
    flight = Flight()
    cat_class_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains = 'multi engine land') & Q(aircraft_type__aircraft_category__aircraft_category__icontains = 'airplane')

    total_time = Flight.objects.filter(user=user).filter(cat_class_query).aggregate(Sum('duration'))
    if not total_time.get('duration__sum'):
      amel.total_time = 0
    else:
      amel.total_time = total_time.get('duration__sum')

    pilot_in_command = Flight.objects.filter(user=user).filter(cat_class_query, pilot_in_command=True).aggregate(Sum('duration'))
    if not pilot_in_command.get('duration__sum'):
      amel.pilot_in_command = 0
    else:
      amel.pilot_in_command = pilot_in_command.get('duration__sum')

    second_in_command = Flight.objects.filter(user=user).filter(cat_class_query, second_in_command=True).aggregate(Sum('duration'))
    if not second_in_command.get('duration__sum'):
      amel.second_in_command = 0
    else:
      amel.second_in_command = second_in_command.get('duration__sum')

    cross_country = Flight.objects.filter(user=user).filter(cat_class_query, cross_country=True).aggregate(Sum('duration'))
    if not cross_country.get('duration__sum'):
      amel.cross_country = 0
    else:
      amel.cross_country = cross_country.get('duration__sum')

    instructor = Flight.objects.filter(user=user).filter(cat_class_query, instructor=True).aggregate(Sum('duration'))
    if not instructor.get('duration__sum'):
      amel.instructor = 0
    else:
      amel.instructor= instructor.get('duration__sum')

    dual = Flight.objects.filter(user=user).filter(cat_class_query, dual=True).aggregate(Sum('duration'))
    if not dual.get('duration__sum'):
      amel.dual = 0
    else:
      amel.dual = dual.get('duration__sum')

    solo = Flight.objects.filter(user=user).filter(cat_class_query, solo=True).aggregate(Sum('duration'))
    if not solo.get('duration__sum'):
      amel.solo = 0
    else:
      amel.solo = solo.get('duration__sum')

    #field_aggregate
    instrument = Flight.objects.filter(user=user).filter(cat_class_query, instrument__gt=0).aggregate(Sum('instrument'))
    if not instrument.get('instrument__sum'):
      amel.instrument = 0
    else:
      amel.instrument = instrument.get('instrument__sum')

    simulated_instrument = Flight.objects.filter(user=user).filter(cat_class_query, simulated_instrument__gt=0).aggregate(Sum('simulated_instrument'))
    if not simulated_instrument.get('simulated_instrument__sum'):
      amel.simulated_instrument = 0
    else:
      amel.simulated_instrument = simulated_instrument.get('simulated_instrument__sum')

    simulator = Flight.objects.filter(user=user).filter(cat_class_query, simulator=True).aggregate(Sum('duration'))
    if not simulator.get('duration__sum'):
      amel.simulator = 0
    else:
      amel.simulator = simulator.get('duration__sum')

    night = Flight.objects.filter(user=user).filter(cat_class_query, night__gte=0).aggregate(Sum('night'))
    if not night.get('night__sum'):
      amel.night = 0
    else:
      amel.night = night.get('night__sum')

    landings_day = Flight.objects.filter(user=user).filter(cat_class_query).aggregate(Sum('landings_day'))
    if not landings_day:
      amel.landings_day = 0
    else:
      amel.landings_day = landings_day.get('landings_day__sum')

    landings_night = Flight.objects.filter(user=user).filter(cat_class_query).aggregate(Sum('landings_night'))
    if not landings_night:
      amel.landings_night = 0
    else:
      amel.landings_night = landings_night.get('landings_night__sum')

    if amel.landings_day and amel.landings_night is None:
        amel.landings_total = 0
    else:
        amel.landings_total = amel.landings_day + amel.landings_night

    try:
      last_flown = Flight.objects.filter(user=user).filter(cat_class_query).latest('date')
      amel.last_flown = last_flown.date
    except:
      amel.last_flown = None

    last_30 = today - datetime.timedelta(days=30)
    last_30 = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_30).aggregate(Sum('duration'))
    if not last_30.get('duration__sum'):
      amel.last_30 = 0
    else:
      amel.last_30 = last_30.get('duration__sum')

    last_60 = today - datetime.timedelta(days=60)
    last_60 = Flight.objects.filter(user=user).filter(cat_class_query).filter(date__lte=today,date__gte=last_60).aggregate(Sum('duration'))
    if not last_60.get('duration__sum'):
      amel.last_60 = 0
    else:
      amel.last_60 = last_60.get('duration__sum')

    last_90 = today - datetime.timedelta(days=90)
    last_90 = Flight.objects.filter(user=user).filter(cat_class_query).filter(date__lte=today,date__gte=last_90).aggregate(Sum('duration'))
    if not last_90.get('duration__sum'):
      amel.last_90 = 0
    else:
      amel.last_90 = last_90.get('duration__sum')

    last_180 = today - datetime.timedelta(days=180)
    last_180 = Flight.objects.filter(user=user).filter(cat_class_query).filter(date__lte=today,date__gte=last_180).aggregate(Sum('duration'))
    if not last_180.get('duration__sum'):
      amel.last_180 = 0
    else:
      amel.last_180 = last_180.get('duration__sum')

    last_yr = today - datetime.timedelta(days=365)
    last_yr = Flight.objects.filter(user=user).filter(cat_class_query).filter(date__lte=today,date__gte=last_yr).aggregate(Sum('duration'))
    if not last_yr.get('duration__sum'):
      amel.last_yr = 0
    else:
      amel.last_yr = last_yr.get('duration__sum')

    last_2yr = today - datetime.timedelta(days=730)
    last_2yr = Flight.objects.filter(user=user).filter(cat_class_query).filter(date__lte=today,date__gte=last_2yr).aggregate(Sum('duration'))
    if not last_2yr.get('duration__sum'):
      amel.last_2yr = 0
    else:
      amel.last_2yr = last_2yr.get('duration__sum')

    jan_1 = datetime.date(today.year, 1, 1)
    ytd = Flight.objects.filter(user=user).filter(cat_class_query).filter(date__lte=today,date__gte=jan_1).aggregate(Sum('duration'))
    if not ytd.get('duration__sum'):
        amel.ytd = 0
    else:
        amel.ytd = ytd.get('duration__sum')

    amel.save()

@receiver(post_save, sender=Aircraft)
@receiver(post_delete, sender=Aircraft)
@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
def asel_update(sender, instance, **kwargs):
    today = datetime.date.today()

    user = instance.user
    #start here .filter(user=user)
    asel = Total.objects.filter(user=user).get(total='ASEL')
    cat_class_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains = 'single engine land') & Q(aircraft_type__aircraft_category__aircraft_category__icontains = 'airplane')

    total_time = Flight.objects.filter(user=user).filter(cat_class_query).aggregate(Sum('duration'))
    if not total_time.get('duration__sum'):
        asel.total_time = 0
    else:
        asel.total_time = total_time.get('duration__sum')

    pilot_in_command = Flight.objects.filter(user=user).filter(cat_class_query, pilot_in_command=True).aggregate(Sum('duration'))
    if not pilot_in_command.get('duration__sum'):
        asel.pilot_in_command = 0
    else:
        asel.pilot_in_command = pilot_in_command.get('duration__sum')

    second_in_command = Flight.objects.filter(user=user).filter(cat_class_query, second_in_command=True).aggregate(Sum('duration'))
    if not second_in_command.get('duration__sum'):
        asel.second_in_command = 0
    else:
        asel.second_in_command = second_in_command.get('duration__sum')

    cross_country = Flight.objects.filter(user=user).filter(cat_class_query, cross_country=True).aggregate(Sum('duration'))
    if not cross_country.get('duration__sum'):
        asel.cross_country = 0
    else:
        asel.cross_country = cross_country.get('duration__sum')

    instructor = Flight.objects.filter(user=user).filter(cat_class_query, instructor=True).aggregate(Sum('duration'))
    if not instructor.get('duration__sum'):
        asel.instructor = 0
    else:
        asel.instructor= instructor.get('duration__sum')

    dual = Flight.objects.filter(user=user).filter(cat_class_query, dual=True).aggregate(Sum('duration'))
    if not dual.get('duration__sum'):
        asel.dual = 0
    else:
        asel.dual = dual.get('duration__sum')

    solo = Flight.objects.filter(user=user).filter(user=user).filter(cat_class_query, solo=True).aggregate(Sum('duration'))
    if not solo.get('duration__sum'):
        asel.solo = 0
    else:
        asel.solo = solo.get('duration__sum')

    instrument = Flight.objects.filter(user=user).filter(cat_class_query, instrument__gt=0).aggregate(Sum('instrument'))
    if not instrument.get('instrument__sum'):
        asel.instrument = 0
    else:
        asel.instrument = instrument.get('instrument__sum')

    simulated_instrument = Flight.objects.all().filter(cat_class_query, simulated_instrument__gt=0).aggregate(Sum('simulated_instrument'))
    if not simulated_instrument.get('simulated_instrument__sum'):
        asel.simulated_instrument = 0
    else:
        asel.simulated_instrument = simulated_instrument.get('simulated_instrument__sum')

    simulator = Flight.objects.filter(user=user).filter(cat_class_query, simulator=True).aggregate(Sum('duration'))
    if not simulator.get('duration__sum'):
        asel.simulator = 0
    else:
        asel.simulator = simulator.get('duration__sum')

    night = Flight.objects.all().filter(cat_class_query, night__gt=0).aggregate(Sum('night'))
    if not night.get('night__sum'):
        asel.night = 0
    else:
        asel.night = night.get('night__sum')

    landings_day = Flight.objects.filter(user=user).filter(cat_class_query).aggregate(Sum('landings_day'))
    if not landings_day:
        asel.landings_day = 0
    else:
        asel.landings_day = landings_day.get('landings_day__sum')

    landings_night = Flight.objects.filter(user=user).filter(cat_class_query).filter(cat_class_query).aggregate(Sum('landings_night'))
    if not landings_night:
        asel.landings_night = 0
    else:
        asel.landings_night = landings_night.get('landings_night__sum')

    if asel.landings_day and asel.landings_night is None:
        asel.landings_total = 0
    else:
        asel.landings_total = asel.landings_day + asel.landings_night

    try:
        last_flown = Flight.objects.filter(user=user).filter(cat_class_query).latest('date')
        asel.last_flown = last_flown.date
    except:
        asel.last_flown = None

    last_30 = today - datetime.timedelta(days=30)
    last_30 = Flight.objects.filter(user=user).filter(cat_class_query).filter(date__lte=today,date__gte=last_30).aggregate(Sum('duration'))
    if not last_30.get('duration__sum'):
        asel.last_30 = 0
    else:
        asel.last_30 = last_30.get('duration__sum')

    last_60 = today - datetime.timedelta(days=60)
    last_60 = Flight.objects.filter(user=user).filter(cat_class_query).filter(date__lte=today,date__gte=last_60).aggregate(Sum('duration'))
    if not last_60.get('duration__sum'):
        asel.last_60 = 0
    else:
        asel.last_60 = last_60.get('duration__sum')

    last_90 = today - datetime.timedelta(days=90)
    last_90 = Flight.objects.filter(user=user).filter(cat_class_query).filter(date__lte=today,date__gte=last_90).aggregate(Sum('duration'))
    if not last_90.get('duration__sum'):
        asel.last_90 = 0
    else:
        asel.last_90 = last_90.get('duration__sum')

    last_180 = today - datetime.timedelta(days=180)
    last_180 = Flight.objects.filter(user=user).filter(cat_class_query).filter(date__lte=today,date__gte=last_180).aggregate(Sum('duration'))
    if not last_180.get('duration__sum'):
        asel.last_180 = 0
    else:
        asel.last_180 = last_180.get('duration__sum')

    last_yr = today - datetime.timedelta(days=365)
    last_yr = Flight.objects.filter(user=user).filter(cat_class_query).filter(date__lte=today,date__gte=last_yr).aggregate(Sum('duration'))
    if not last_yr.get('duration__sum'):
        asel.last_yr = 0
    else:
        asel.last_yr = last_yr.get('duration__sum')

    last_2yr = today - datetime.timedelta(days=730)
    last_2yr = Flight.objects.filter(user=user).filter(cat_class_query).filter(date__lte=today,date__gte=last_2yr).aggregate(Sum('duration'))
    if not last_2yr.get('duration__sum'):
        asel.last_2yr = 0
    else:
        asel.last_2yr = last_2yr.get('duration__sum')

    ydt = datetime.date(today.year, 1, 1)
    ydt = Flight.objects.filter(user=user).filter(cat_class_query).filter(date__lte=today,date__gte=ydt).aggregate(Sum('duration'))
    if not ydt.get('duration__sum'):
        asel.ydt = 0
    else:
        asel.ydt = ydt.get('duration__sum')

    asel.save()
