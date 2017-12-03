from flights.models import *
from django.db.models.signals import pre_save, post_save, post_delete
from django.db.models import Sum, Q
import datetime

@receiver(post_save, sender=Aircraft)
@receiver(post_delete, sender=Aircraft)
@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
def ames_updater(sender, **kwargs):
    today = datetime.date.today()
    ames = Total.objects.get(total='AMES')
    cat_class_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains = 'multi engine sea') & Q(aircraft_type__aircraft_category__aircraft_category__icontains = 'airplane')

    total_time = Flight.objects.all().filter(cat_class_query).aggregate(Sum('duration'))
    if total_time.get('duration__sum') is None:
        ames.total_time = 0
    else:
        ames.total_time = round(total_time.get('duration__sum'),1)

    pilot_in_command = Flight.objects.all().filter(cat_class_query).filter(cat_class_query).filter(pilot_in_command=True).aggregate(Sum('duration'))
    if pilot_in_command.get('duration__sum') is None:
        ames.pilot_in_command = 0
    else:
        ames.pilot_in_command = round(pilot_in_command.get('duration__sum'),1)

    second_in_command = Flight.objects.all().filter(cat_class_query).filter(cat_class_query).filter(second_in_command=True).aggregate(Sum('duration'))
    if second_in_command.get('duration__sum') is None:
        ames.second_in_command = 0
    else:
        ames.second_in_command = round(second_in_command.get('duration__sum'),1)

    cross_country = Flight.objects.all().filter(cat_class_query).filter(cross_country=True).aggregate(Sum('duration'))
    if cross_country.get('duration__sum') is None:
        ames.cross_country = 0
    else:
        ames.cross_country = round(cross_country.get('duration__sum'),1)

    instructor = Flight.objects.all().filter(cat_class_query).filter(instructor=True).aggregate(Sum('duration'))
    if instructor.get('duration__sum') is None:
        ames.instructor = 0
    else:
        ames.instructor= round(instructor.get('duration__sum'),1)

    dual = Flight.objects.all().filter(cat_class_query).filter(dual=True).aggregate(Sum('duration'))
    if dual.get('duration__sum') is None:
        ames.dual = 0
    else:
        ames.dual = round(dual.get('duration__sum'),1)

    solo = Flight.objects.all().filter(cat_class_query).filter(solo=True).aggregate(Sum('duration'))
    if solo.get('duration__sum') is None:
        ames.solo = 0
    else:
        ames.solo = round(solo.get('duration__sum'),1)

    instrument = Flight.objects.all().filter(cat_class_query).filter(instrument=True).aggregate(Sum('duration'))
    if instrument.get('duration__sum') is None:
        ames.instrument = 0
    else:
        ames.instrument = round(instrument.get('duration__sum'),1)

    simulated_instrument = Flight.objects.all().filter(cat_class_query).aggregate(Sum('simulated_instrument'))
    if simulated_instrument.get('duration__sum') is None:
        ames.simulated_instrument = 0
    else:
        ames.simulated_instrument = round(simulated_instrument.get('simulated_instrument__sum'),1)

    simulator = Flight.objects.all().filter(cat_class_query).aggregate(Sum('simulator'))
    if simulator.get('duration__sum') is None:
        ames.simulator = 0
    else:
        ames.simulator = round(simulator.get('simulator__sum'),1)

    night = Flight.objects.all().filter(cat_class_query).aggregate(Sum('night'))
    if night.get('duration__sum') is None:
        ames.night = 0
    else:
        ames.night = round(night.get('night__sum'),1)

    landings_day = Flight.objects.all().filter(cat_class_query).aggregate(Sum('landings_day'))
    if landings_day.get('landings_day__sum') is None:
        ames.landings_day = 0
    else:
        ames.landings_day = landings_day.get('landings_day__sum')

    landings_night = Flight.objects.all().filter(cat_class_query).filter(cat_class_query).aggregate(Sum('landings_night'))
    if landings_night.get('landings_night__sum') is None:
        ames.landings_night = 0
    else:
        ames.landings_night = landings_night.get('landings_night__sum')

    ames.landings_total = ames.landings_day + ames.landings_night

    try:
        last_flown = Flight.objects.filter(cat_class_query).latest('date')
        ames.last_flown = last_flown.date
    except:
        ames.last_flown = None

    last_30 = today - datetime.timedelta(days=30)
    last_30 = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_30).aggregate(Sum('duration'))
    if last_30.get('duration__sum') is None:
        ames.last_30 = 0
    else:
        ames.last_30 = round(last_30.get('duration__sum'), 1)

    last_60 = today - datetime.timedelta(days=60)
    last_60 = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_60).aggregate(Sum('duration'))
    if last_60.get('duration__sum') is None:
        ames.last_60 = 0
    else:
        ames.last_60 = round(last_60.get('duration__sum'), 1)

    last_90 = today - datetime.timedelta(days=90)
    last_90 = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_90).aggregate(Sum('duration'))
    if last_90.get('duration__sum') is None:
        ames.last_90 = 0
    else:
        ames.last_90 = round(last_90.get('duration__sum'), 1)

    last_180 = today - datetime.timedelta(days=180)
    last_180 = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_180).aggregate(Sum('duration'))
    if last_180.get('duration__sum') is None:
        ames.last_180 = 0
    else:
        ames.last_180 = round(last_180.get('duration__sum'), 1)

    last_yr = today - datetime.timedelta(days=365)
    last_yr = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_yr).aggregate(Sum('duration'))
    if last_yr.get('duration__sum') is None:
        ames.last_yr = 0
    else:
        ames.last_yr = round(last_yr.get('duration__sum'), 1)

    last_2yr = today - datetime.timedelta(days=730)
    last_2yr = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_2yr).aggregate(Sum('duration'))
    if last_2yr.get('duration__sum') is None:
        ames.last_2yr = 0
    else:
        ames.last_2yr = round(last_2yr.get('duration__sum'), 1)

    ydt = datetime.date(today.year, 1, 1)
    ydt = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=ydt).aggregate(Sum('duration'))
    if ydt.get('duration__sum') is None:
        ames.ydt = 0
    else:
        ames.ydt = round(ydt.get('duration__sum'), 1)

    ames.save()

@receiver(post_save, sender=Aircraft)
@receiver(post_delete, sender=Aircraft)
@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
def asel_updater(sender, **kwargs):
    today = datetime.date.today()
    ases = Total.objects.get(total='ASES')
    cat_class_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains = 'single engine sea') & Q(aircraft_type__aircraft_category__aircraft_category__icontains = 'airplane')

    total_time = Flight.objects.all().filter(cat_class_query).aggregate(Sum('duration'))
    if total_time.get('duration__sum') is None:
        ases.total_time = 0
    else:
        ases.total_time = round(total_time.get('duration__sum'),1)

    pilot_in_command = Flight.objects.all().filter(cat_class_query).filter(cat_class_query).filter(pilot_in_command=True).aggregate(Sum('duration'))
    if pilot_in_command.get('duration__sum') is None:
        ases.pilot_in_command = 0
    else:
        ases.pilot_in_command = round(pilot_in_command.get('duration__sum'),1)

    second_in_command = Flight.objects.all().filter(cat_class_query).filter(cat_class_query).filter(second_in_command=True).aggregate(Sum('duration'))
    if second_in_command.get('duration__sum') is None:
        ases.second_in_command = 0
    else:
        ases.second_in_command = round(second_in_command.get('duration__sum'),1)

    cross_country = Flight.objects.all().filter(cat_class_query).filter(cross_country=True).aggregate(Sum('duration'))
    if cross_country.get('duration__sum') is None:
        ases.cross_country = 0
    else:
        ases.cross_country = round(cross_country.get('duration__sum'),1)

    instructor = Flight.objects.all().filter(cat_class_query).filter(instructor=True).aggregate(Sum('duration'))
    if instructor.get('duration__sum') is None:
        ases.instructor = 0
    else:
        ases.instructor= round(instructor.get('duration__sum'),1)

    dual = Flight.objects.all().filter(cat_class_query).filter(dual=True).aggregate(Sum('duration'))
    if dual.get('duration__sum') is None:
        ases.dual = 0
    else:
        ases.dual = round(dual.get('duration__sum'),1)

    solo = Flight.objects.all().filter(cat_class_query).filter(solo=True).aggregate(Sum('duration'))
    if solo.get('duration__sum') is None:
        ases.solo = 0
    else:
        ases.solo = round(solo.get('duration__sum'),1)

    instrument = Flight.objects.all().filter(cat_class_query).filter(instrument=True).aggregate(Sum('duration'))
    if instrument.get('duration__sum') is None:
        ases.instrument = 0
    else:
        ases.instrument = round(instrument.get('duration__sum'),1)

    simulated_instrument = Flight.objects.all().filter(cat_class_query).aggregate(Sum('simulated_instrument'))
    if simulated_instrument.get('duration__sum') is None:
        ases.simulated_instrument = 0
    else:
        ases.simulated_instrument = round(simulated_instrument.get('simulated_instrument__sum'),1)

    simulator = Flight.objects.all().filter(cat_class_query).aggregate(Sum('simulator'))
    if simulator.get('duration__sum') is None:
        ases.simulator = 0
    else:
        ases.simulator = round(simulator.get('simulator__sum'),1)

    night = Flight.objects.all().filter(cat_class_query).aggregate(Sum('night'))
    if night.get('duration__sum') is None:
        ases.night = 0
    else:
        ases.night = round(night.get('night__sum'),1)

    landings_day = Flight.objects.all().filter(cat_class_query).aggregate(Sum('landings_day'))
    if landings_day.get('landings_day__sum') is None:
        ases.landings_day = 0
    else:
        ases.landings_day = landings_day.get('landings_day__sum')

    landings_night = Flight.objects.all().filter(cat_class_query).filter(cat_class_query).aggregate(Sum('landings_night'))
    if landings_night.get('landings_night__sum') is None:
        ases.landings_night = 0
    else:
        ases.landings_night = landings_night.get('landings_night__sum')

    ases.landings_total = ases.landings_day + ases.landings_night

    try:
        last_flown = Flight.objects.filter(cat_class_query).latest('date')
        ases.last_flown = last_flown.date
    except:
        ases.last_flown = None

    last_30 = today - datetime.timedelta(days=30)
    last_30 = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_30).aggregate(Sum('duration'))
    if last_30.get('duration__sum') is None:
        ases.last_30 = 0
    else:
        ases.last_30 = round(last_30.get('duration__sum'), 1)

    last_60 = today - datetime.timedelta(days=60)
    last_60 = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_60).aggregate(Sum('duration'))
    if last_60.get('duration__sum') is None:
        ases.last_60 = 0
    else:
        ases.last_60 = round(last_60.get('duration__sum'), 1)

    last_90 = today - datetime.timedelta(days=90)
    last_90 = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_90).aggregate(Sum('duration'))
    if last_90.get('duration__sum') is None:
        ases.last_90 = 0
    else:
        ases.last_90 = round(last_90.get('duration__sum'), 1)

    last_180 = today - datetime.timedelta(days=180)
    last_180 = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_180).aggregate(Sum('duration'))
    if last_180.get('duration__sum') is None:
        ases.last_180 = 0
    else:
        ases.last_180 = round(last_180.get('duration__sum'), 1)

    last_yr = today - datetime.timedelta(days=365)
    last_yr = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_yr).aggregate(Sum('duration'))
    if last_yr.get('duration__sum') is None:
        ases.last_yr = 0
    else:
        ases.last_yr = round(last_yr.get('duration__sum'), 1)

    last_2yr = today - datetime.timedelta(days=730)
    last_2yr = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_2yr).aggregate(Sum('duration'))
    if last_2yr.get('duration__sum') is None:
        ases.last_2yr = 0
    else:
        ases.last_2yr = round(last_2yr.get('duration__sum'), 1)

    ydt = datetime.date(today.year, 1, 1)
    ydt = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=ydt).aggregate(Sum('duration'))
    if ydt.get('duration__sum') is None:
        ases.ydt = 0
    else:
        ases.ydt = round(ydt.get('duration__sum'), 1)

    ases.save()
