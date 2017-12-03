from flights.models import *
from django.db.models.signals import pre_save, post_save, post_delete
from django.db.models import Sum, Q
import datetime

@receiver(post_save, sender=Aircraft)
@receiver(post_delete, sender=Aircraft)
@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
def amel_updater(sender, **kwargs):
    today = datetime.date.today()
    amel = Total.objects.get(total='AMEL')
    cat_class_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains = 'multi engine land') & Q(aircraft_type__aircraft_category__aircraft_category__icontains = 'airplane')

    total_time = Flight.objects.all().filter(cat_class_query).aggregate(Sum('duration'))
    if total_time.get('duration__sum') is None:
        amel.total_time = 0
    else:
        amel.total_time = round(total_time.get('duration__sum'),1)

    pilot_in_command = Flight.objects.all().filter(cat_class_query).filter(cat_class_query).filter(pilot_in_command=True).aggregate(Sum('duration'))
    if pilot_in_command.get('duration__sum') is None:
        amel.pilot_in_command = 0
    else:
        amel.pilot_in_command = round(pilot_in_command.get('duration__sum'),1)

    second_in_command = Flight.objects.all().filter(cat_class_query).filter(cat_class_query).filter(second_in_command=True).aggregate(Sum('duration'))
    if second_in_command.get('duration__sum') is None:
        amel.second_in_command = 0
    else:
        amel.second_in_command = round(second_in_command.get('duration__sum'),1)

    cross_country = Flight.objects.all().filter(cat_class_query).filter(cross_country=True).aggregate(Sum('duration'))
    if cross_country.get('duration__sum') is None:
        amel.cross_country = 0
    else:
        amel.cross_country = round(cross_country.get('duration__sum'),1)

    instructor = Flight.objects.all().filter(cat_class_query).filter(instructor=True).aggregate(Sum('duration'))
    if instructor.get('duration__sum') is None:
        amel.instructor = 0
    else:
        amel.instructor= round(instructor.get('duration__sum'),1)

    dual = Flight.objects.all().filter(cat_class_query).filter(dual=True).aggregate(Sum('duration'))
    if dual.get('duration__sum') is None:
        amel.dual = 0
    else:
        amel.dual = round(dual.get('duration__sum'),1)

    solo = Flight.objects.all().filter(cat_class_query).filter(solo=True).aggregate(Sum('duration'))
    if solo.get('duration__sum') is None:
        amel.solo = 0
    else:
        amel.solo = round(solo.get('duration__sum'),1)

    instrument = Flight.objects.all().filter(cat_class_query).filter(instrument=True).aggregate(Sum('duration'))
    if instrument.get('duration__sum') is None:
        amel.instrument = 0
    else:
        amel.instrument = round(instrument.get('duration__sum'),1)

    simulated_instrument = Flight.objects.all().filter(cat_class_query).aggregate(Sum('simulated_instrument'))
    if simulated_instrument.get('duration__sum') is None:
        amel.simulated_instrument = 0
    else:
        amel.simulated_instrument = round(simulated_instrument.get('simulated_instrument__sum'),1)

    simulator = Flight.objects.all().filter(cat_class_query).aggregate(Sum('simulator'))
    if simulator.get('duration__sum') is None:
        amel.simulator = 0
    else:
        amel.simulator = round(simulator.get('simulator__sum'),1)

    night = Flight.objects.all().filter(cat_class_query).aggregate(Sum('night'))
    if night.get('duration__sum') is None:
        amel.night = 0
    else:
        amel.night = round(night.get('night__sum'),1)

    landings_day = Flight.objects.all().filter(cat_class_query).aggregate(Sum('landings_day'))
    if landings_day is None:
        amel.landings_day = 0
    else:
        amel.landings_day = landings_day.get('landings_day__sum')

    landings_night = Flight.objects.all().filter(cat_class_query).filter(cat_class_query).aggregate(Sum('landings_night'))
    if landings_night is None:
        amel.landings_night = 0
    else:
        amel.landings_night = landings_night.get('landings_night__sum')

    amel.landings_total = amel.landings_day + amel.landings_night

    try:
        last_flown = Flight.objects.filter(cat_class_query).latest('date')
        amel.last_flown = last_flown.date
    except:
        amel.last_flown = None

    last_30 = today - datetime.timedelta(days=30)
    last_30 = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_30).aggregate(Sum('duration'))
    if last_30.get('duration__sum') is None:
        amel.last_30 = 0
    else:
        amel.last_30 = round(last_30.get('duration__sum'), 1)

    last_60 = today - datetime.timedelta(days=60)
    last_60 = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_60).aggregate(Sum('duration'))
    if last_60.get('duration__sum') is None:
        amel.last_60 = 0
    else:
        amel.last_60 = round(last_60.get('duration__sum'), 1)

    last_90 = today - datetime.timedelta(days=90)
    last_90 = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_90).aggregate(Sum('duration'))
    if last_90.get('duration__sum') is None:
        amel.last_90 = 0
    else:
        amel.last_90 = round(last_90.get('duration__sum'), 1)

    last_180 = today - datetime.timedelta(days=180)
    last_180 = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_180).aggregate(Sum('duration'))
    if last_180.get('duration__sum') is None:
        amel.last_180 = 0
    else:
        amel.last_180 = round(last_180.get('duration__sum'), 1)

    last_yr = today - datetime.timedelta(days=365)
    last_yr = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_yr).aggregate(Sum('duration'))
    if last_yr.get('duration__sum') is None:
        amel.last_yr = 0
    else:
        amel.last_yr = round(last_yr.get('duration__sum'), 1)

    last_2yr = today - datetime.timedelta(days=730)
    last_2yr = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_2yr).aggregate(Sum('duration'))
    if last_2yr.get('duration__sum') is None:
        amel.last_2yr = 0
    else:
        amel.last_2yr = round(last_2yr.get('duration__sum'), 1)

    ydt = datetime.date(today.year, 1, 1)
    ydt = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=ydt).aggregate(Sum('duration'))
    if ydt.get('duration__sum') is None:
        amel.ydt = 0
    else:
        amel.ydt = round(ydt.get('duration__sum'), 1)

    amel.save()

@receiver(post_save, sender=Aircraft)
@receiver(post_delete, sender=Aircraft)
@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
def asel_updater(sender, **kwargs):
    today = datetime.date.today()
    asel = Total.objects.get(total='ASEL')
    cat_class_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains = 'single engine land') & Q(aircraft_type__aircraft_category__aircraft_category__icontains = 'airplane')

    total_time = Flight.objects.all().filter(cat_class_query).aggregate(Sum('duration'))
    if total_time.get('duration__sum') is None:
        asel.total_time = 0
    else:
        asel.total_time = round(total_time.get('duration__sum'),1)

    pilot_in_command = Flight.objects.all().filter(cat_class_query).filter(cat_class_query).filter(pilot_in_command=True).aggregate(Sum('duration'))
    if pilot_in_command.get('duration__sum') is None:
        asel.pilot_in_command = 0
    else:
        asel.pilot_in_command = round(pilot_in_command.get('duration__sum'),1)

    second_in_command = Flight.objects.all().filter(cat_class_query).filter(cat_class_query).filter(second_in_command=True).aggregate(Sum('duration'))
    if second_in_command.get('duration__sum') is None:
        asel.second_in_command = 0
    else:
        asel.second_in_command = round(second_in_command.get('duration__sum'),1)

    cross_country = Flight.objects.all().filter(cat_class_query).filter(cross_country=True).aggregate(Sum('duration'))
    if cross_country.get('duration__sum') is None:
        asel.cross_country = 0
    else:
        asel.cross_country = round(cross_country.get('duration__sum'),1)

    instructor = Flight.objects.all().filter(cat_class_query).filter(instructor=True).aggregate(Sum('duration'))
    if instructor.get('duration__sum') is None:
        asel.instructor = 0
    else:
        asel.instructor= round(instructor.get('duration__sum'),1)

    dual = Flight.objects.all().filter(cat_class_query).filter(dual=True).aggregate(Sum('duration'))
    if dual.get('duration__sum') is None:
        asel.dual = 0
    else:
        asel.dual = round(dual.get('duration__sum'),1)

    solo = Flight.objects.all().filter(cat_class_query).filter(solo=True).aggregate(Sum('duration'))
    if solo.get('duration__sum') is None:
        asel.solo = 0
    else:
        asel.solo = round(solo.get('duration__sum'),1)

    instrument = Flight.objects.all().filter(cat_class_query).filter(instrument=True).aggregate(Sum('duration'))
    if instrument.get('duration__sum') is None:
        asel.instrument = 0
    else:
        asel.instrument = round(instrument.get('duration__sum'),1)

    simulated_instrument = Flight.objects.all().filter(cat_class_query).aggregate(Sum('simulated_instrument'))
    if simulated_instrument.get('duration__sum') is None:
        asel.simulated_instrument = 0
    else:
        asel.simulated_instrument = round(simulated_instrument.get('simulated_instrument__sum'),1)

    simulator = Flight.objects.all().filter(cat_class_query).aggregate(Sum('simulator'))
    if simulator.get('duration__sum') is None:
        asel.simulator = 0
    else:
        asel.simulator = round(simulator.get('simulator__sum'),1)

    night = Flight.objects.all().filter(cat_class_query).aggregate(Sum('night'))
    if night.get('duration__sum') is None:
        asel.night = 0
    else:
        asel.night = round(night.get('night__sum'),1)

    landings_day = Flight.objects.all().filter(cat_class_query).aggregate(Sum('landings_day'))
    if landings_day is None:
        asel.landings_day = 0
    else:
        asel.landings_day = landings_day.get('landings_day__sum')

    landings_night = Flight.objects.all().filter(cat_class_query).filter(cat_class_query).aggregate(Sum('landings_night'))
    if landings_night is None:
        asel.landings_night = 0
    else:
        asel.landings_night = landings_night.get('landings_night__sum')

    asel.landings_total = asel.landings_day + asel.landings_night

    try:
        last_flown = Flight.objects.filter(cat_class_query).latest('date')
        asel.last_flown = last_flown.date
    except:
        asel.last_flown = None

    last_30 = today - datetime.timedelta(days=30)
    last_30 = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_30).aggregate(Sum('duration'))
    if last_30.get('duration__sum') is None:
        asel.last_30 = 0
    else:
        asel.last_30 = round(last_30.get('duration__sum'), 1)

    last_60 = today - datetime.timedelta(days=60)
    last_60 = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_60).aggregate(Sum('duration'))
    if last_60.get('duration__sum') is None:
        asel.last_60 = 0
    else:
        asel.last_60 = round(last_60.get('duration__sum'), 1)

    last_90 = today - datetime.timedelta(days=90)
    last_90 = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_90).aggregate(Sum('duration'))
    if last_90.get('duration__sum') is None:
        asel.last_90 = 0
    else:
        asel.last_90 = round(last_90.get('duration__sum'), 1)

    last_180 = today - datetime.timedelta(days=180)
    last_180 = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_180).aggregate(Sum('duration'))
    if last_180.get('duration__sum') is None:
        asel.last_180 = 0
    else:
        asel.last_180 = round(last_180.get('duration__sum'), 1)

    last_yr = today - datetime.timedelta(days=365)
    last_yr = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_yr).aggregate(Sum('duration'))
    if last_yr.get('duration__sum') is None:
        asel.last_yr = 0
    else:
        asel.last_yr = round(last_yr.get('duration__sum'), 1)

    last_2yr = today - datetime.timedelta(days=730)
    last_2yr = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_2yr).aggregate(Sum('duration'))
    if last_2yr.get('duration__sum') is None:
        asel.last_2yr = 0
    else:
        asel.last_2yr = round(last_2yr.get('duration__sum'), 1)

    ydt = datetime.date(today.year, 1, 1)
    ydt = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=ydt).aggregate(Sum('duration'))
    if ydt.get('duration__sum') is None:
        asel.ydt = 0
    else:
        asel.ydt = round(ydt.get('duration__sum'), 1)

    asel.save()
