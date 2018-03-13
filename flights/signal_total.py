from flights.models import *
from django.db.models.signals import pre_save, post_save, post_delete
from django.db.models import Sum, Q
import datetime

@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
def total_update(sender, **kwargs):
    today = datetime.date.today()
    total = Total.objects.get(total='All')

    total_time = Flight.objects.all().aggregate(Sum('duration'))
    if not total_time.get('duration__sum'):
        total.total_time = 0
    else:
        total.total_time = round(total_time.get('duration__sum'),1)

    pilot_in_command = Flight.objects.all().filter(pilot_in_command=True).aggregate(Sum('duration'))
    if not pilot_in_command.get('duration__sum'):
        total.pilot_in_command = 0
    else:
        total.pilot_in_command = round(pilot_in_command.get('duration__sum'),1)

    second_in_command = Flight.objects.all().filter(second_in_command=True).aggregate(Sum('duration'))
    if not second_in_command.get('duration__sum'):
        total.second_in_command = 0
    else:
        total.second_in_command = round(second_in_command.get('duration__sum'),1)

    cross_country = Flight.objects.all().filter(cross_country=True).aggregate(Sum('duration'))
    if not cross_country.get('duration__sum'):
        total.cross_country = 0
    else:
        total.cross_country = round(cross_country.get('duration__sum'),1)

    instructor = Flight.objects.all().filter(instructor=True).aggregate(Sum('duration'))
    if not instructor.get('duration__sum'):
        total.instructor = 0
    else:
        total.instructor= round(instructor.get('duration__sum'),1)

    dual = Flight.objects.all().filter(dual=True).aggregate(Sum('duration'))
    if not dual.get('duration__sum'):
        total.dual = 0
    else:
        total.dual = round(dual.get('duration__sum'),1)

    solo = Flight.objects.all().filter(solo=True).aggregate(Sum('duration'))
    if not solo.get('duration__sum'):
        total.solo = 0
    else:
        total.solo = round(solo.get('duration__sum'),1)

    instrument = Flight.objects.all().aggregate(Sum('instrument'))
    if not instrument.get('instrument__sum'):
        total.instrument = 0
    else:
        total.instrument = round(instrument.get('instrument__sum'),1)

    simulated_instrument = Flight.objects.all().aggregate(Sum('simulated_instrument'))
    if not simulated_instrument.get('simulated_instrument__sum'):
        total.simulated_instrument = 0
    else:
        total.simulated_instrument = round(simulated_instrument.get('simulated_instrument__sum'),1)

    simulator = Flight.objects.all().aggregate(Sum('simulator'))
    if not simulator.get('simulator__sum'):
        total.simulator = 0
    else:
        total.simulator = round(simulator.get('simulator__sum'),1)

    night = Flight.objects.all().aggregate(Sum('night'))
    if not night.get('night__sum'):
        total.night = 0
    else:
        total.night = round(night.get('night__sum'),1)

    landings_day = Flight.objects.all().aggregate(Sum('landings_day'))
    if not landings_day.get('landings_day__sum'):
        total.landings_day = 0
    else:
        total.landings_day = landings_day.get('landings_day__sum')

    landings_night = Flight.objects.all().aggregate(Sum('landings_night'))
    if not landings_night.get('landings_night__sum'):
        total.landings_night = 0
    else:
        total.landings_night = landings_night.get('landings_night__sum')

    total.landings_total = total.landings_day + total.landings_night

    try:
        last_flown = Flight.objects.filter().latest('date')
        total.last_flown = last_flown.date
    except:
        total.last_flown = None

    last_30 = today - datetime.timedelta(days=30)
    last_30 = Flight.objects.filter(date__lte=today,date__gte=last_30).aggregate(Sum('duration'))
    if not last_30.get('duration__sum'):
        total.last_30 = 0
    else:
        total.last_30 = round(last_30.get('duration__sum'), 1)

    last_60 = today - datetime.timedelta(days=60)
    last_60 = Flight.objects.filter(date__lte=today,date__gte=last_60).aggregate(Sum('duration'))
    if not last_60.get('duration__sum'):
        total.last_60 = 0
    else:
        total.last_60 = round(last_60.get('duration__sum'), 1)

    last_90 = today - datetime.timedelta(days=90)
    last_90 = Flight.objects.filter(date__lte=today,date__gte=last_90).aggregate(Sum('duration'))
    if not last_90.get('duration__sum'):
        total.last_90 = 0
    else:
        total.last_90 = round(last_90.get('duration__sum'), 1)

    last_180 = today - datetime.timedelta(days=180)
    last_180 = Flight.objects.filter(date__lte=today,date__gte=last_180).aggregate(Sum('duration'))
    if not last_180.get('duration__sum'):
        total.last_180 = 0
    else:
        total.last_180 = round(last_180.get('duration__sum'), 1)

    last_yr = today - datetime.timedelta(days=365)
    last_yr = Flight.objects.filter(date__lte=today,date__gte=last_yr).aggregate(Sum('duration'))
    if not last_yr.get('duration__sum'):
        total.last_yr = 0
    else:
        total.last_yr = round(last_yr.get('duration__sum'), 1)

    last_2yr = today - datetime.timedelta(days=730)
    last_2yr = Flight.objects.filter(date__lte=today,date__gte=last_2yr).aggregate(Sum('duration'))
    if not last_2yr.get('duration__sum'):
        total.last_2yr = 0
    else:
        total.last_2yr = round(last_2yr.get('duration__sum'), 1)

    ydt = datetime.date(today.year, 1, 1)
    ydt = Flight.objects.filter(date__lte=today,date__gte=ydt).aggregate(Sum('duration'))
    if not ydt.get('duration__sum'):
        total.ytd = 0
    else:
        total.ytd = round(ydt.get('duration__sum'), 1)

    total.save()
