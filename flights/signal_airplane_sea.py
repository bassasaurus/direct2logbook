from flights.models import *
from django.db.models.signals import pre_save, post_save, post_delete
from django.db.models import Sum, Q
import datetime

@receiver(post_save, sender=Aircraft)
@receiver(post_delete, sender=Aircraft)
@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
def ames_update(sender, **kwargs):
    today = datetime.date.today()
    ames = Total.objects.get(total='AMES')
    cat_class_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains = 'multi engine sea') & Q(aircraft_type__aircraft_category__aircraft_category__icontains = 'airplane')

    total_time = Flight.objects.all().filter(cat_class_query).aggregate(Sum('duration'))
    if total_time.get('duration__sum') is None:
        ames.total_time = 0
    else:
        ames.total_time = total_time.get('duration__sum')

    pilot_in_command = Flight.objects.all().filter(cat_class_query, pilot_in_command=True).aggregate(Sum('duration'))
    if pilot_in_command.get('duration__sum') is None:
        ames.pilot_in_command = 0
    else:
        ames.pilot_in_command = pilot_in_command.get('duration__sum')

    second_in_command = Flight.objects.all().filter(cat_class_query, second_in_command=True).aggregate(Sum('duration'))
    if second_in_command.get('duration__sum') is None:
        ames.second_in_command = 0
    else:
        ames.second_in_command = second_in_command.get('duration__sum')

    cross_country = Flight.objects.all().filter(cat_class_query, cross_country=True).aggregate(Sum('duration'))
    if cross_country.get('duration__sum') is None:
        ames.cross_country = 0
    else:
        ames.cross_country = cross_country.get('duration__sum')

    instructor = Flight.objects.all().filter(cat_class_query, instructor=True).aggregate(Sum('duration'))
    if instructor.get('duration__sum') is None:
        ames.instructor = 0
    else:
        ames.instructor= instructor.get('duration__sum')

    dual = Flight.objects.all().filter(cat_class_query, dual=True).aggregate(Sum('duration'))
    if dual.get('duration__sum') is None:
        ames.dual = 0
    else:
        ames.dual = dual.get('duration__sum')

    solo = Flight.objects.all().filter(cat_class_query, solo=True).aggregate(Sum('duration'))
    if solo.get('duration__sum') is None:
        ames.solo = 0
    else:
        ames.solo = solo.get('duration__sum')

    instrument = Flight.objects.all().filter(cat_class_query, instrument__gt=0).aggregate(Sum('instrument'))
    if instrument.get('duration__sum') is None:
        ames.instrument = 0
    else:
        ames.instrument = instrument.get('duration__sum')

    simulated_instrument = Flight.objects.all().filter(cat_class_query, simulated_instrument__gt=0).aggregate(Sum('simulated_instrument'))
    if simulated_instrument.get('simulated_instrument') is None:
        ames.simulated_instrument = 0
    else:
        ames.simulated_instrument = simulated_instrument.get('simulated_instrument__sum')

    simulator = Flight.objects.all().filter(cat_class_query).aggregate(Sum('simulator'))
    if simulator.get('duration__sum') is None:
        ames.simulator = 0
    else:
        ames.simulator = simulator.get('duration__sum')

    night = Flight.objects.all().filter(cat_class_query, night__gt=0).aggregate(Sum('night'))
    if night.get('night__sum') is None:
        ames.night = 0
    else:
        ames.night = night.get('night__sum')

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
        ames.last_30 = last_30.get('duration__sum')

    last_60 = today - datetime.timedelta(days=60)
    last_60 = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_60).aggregate(Sum('duration'))
    if last_60.get('duration__sum') is None:
        ames.last_60 = 0
    else:
        ames.last_60 = last_60.get('duration__sum')

    last_90 = today - datetime.timedelta(days=90)
    last_90 = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_90).aggregate(Sum('duration'))
    if last_90.get('duration__sum') is None:
        ames.last_90 = 0
    else:
        ames.last_90 = last_90.get('duration__sum')

    last_180 = today - datetime.timedelta(days=180)
    last_180 = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_180).aggregate(Sum('duration'))
    if last_180.get('duration__sum') is None:
        ames.last_180 = 0
    else:
        ames.last_180 = last_180.get('duration__sum')

    last_yr = today - datetime.timedelta(days=365)
    last_yr = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_yr).aggregate(Sum('duration'))
    if last_yr.get('duration__sum') is None:
        ames.last_yr = 0
    else:
        ames.last_yr = last_yr.get('duration__sum')

    last_2yr = today - datetime.timedelta(days=730)
    last_2yr = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_2yr).aggregate(Sum('duration'))
    if last_2yr.get('duration__sum') is None:
        ames.last_2yr = 0
    else:
        ames.last_2yr = last_2yr.get('duration__sum')

    ytd = datetime.date(today.year, 1, 1)
    ytd = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=ytd).aggregate(Sum('duration'))
    if ytd.get('duration__sum') is None:
        ames.ytd = 0
    else:
        ames.ytd = ytd.get('duration__sum')

    ames.save()

@receiver(post_save, sender=Aircraft)
@receiver(post_delete, sender=Aircraft)
@receiver(post_save, sender=Flight)
@receiver(post_delete, sender=Flight)
def asel_update(sender, **kwargs):
    today = datetime.date.today()
    ases = Total.objects.get(total='ASES')
    cat_class_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains = 'single engine sea') & Q(aircraft_type__aircraft_category__aircraft_category__icontains = 'airplane')

    total_time = Flight.objects.all().filter(cat_class_query).aggregate(Sum('duration'))
    if total_time.get('duration__sum') is None:
        ases.total_time = 0
    else:
        ases.total_time = total_time.get('duration__sum')

    pilot_in_command = Flight.objects.all().filter(cat_class_query, pilot_in_command=True).aggregate(Sum('duration'))
    if pilot_in_command.get('duration__sum') is None:
        ases.pilot_in_command = 0
    else:
        ases.pilot_in_command = pilot_in_command.get('duration__sum')

    second_in_command = Flight.objects.all().filter(cat_class_query).filter(cat_class_query, second_in_command=True).aggregate(Sum('duration'))
    if second_in_command.get('duration__sum') is None:
        ases.second_in_command = 0
    else:
        ases.second_in_command = second_in_command.get('duration__sum')

    cross_country = Flight.objects.all().filter(cat_class_query, cross_country=True).aggregate(Sum('duration'))
    if cross_country.get('duration__sum') is None:
        ases.cross_country = 0
    else:
        ases.cross_country = cross_country.get('duration__sum')

    instructor = Flight.objects.all().filter(cat_class_query, instructor=True).aggregate(Sum('duration'))
    if instructor.get('duration__sum') is None:
        ases.instructor = 0
    else:
        ases.instructor= instructor.get('duration__sum')

    dual = Flight.objects.all().filter(cat_class_query, dual=True).aggregate(Sum('duration'))
    if dual.get('duration__sum') is None:
        ases.dual = 0
    else:
        ases.dual = dual.get('duration__sum')

    solo = Flight.objects.all().filter(cat_class_query, solo=True).aggregate(Sum('duration'))
    if solo.get('duration__sum') is None:
        ases.solo = 0
    else:
        ases.solo = solo.get('duration__sum')

    instrument = Flight.objects.all().filter(cat_class_query, instrument__gt=0).aggregate(Sum('instrument'))
    if instrument.get('instrument__sum') is None:
        ases.instrument = 0
    else:
        ases.instrument = instrument.get('instrument__sum')

    simulated_instrument = Flight.objects.all().filter(cat_class_query, simulated_instrument__gt=0).aggregate(Sum('simulated_instrument'))
    if simulated_instrument.get('simulated_instrument__sum') is None:
        ases.simulated_instrument = 0
    else:
        ases.simulated_instrument = simulated_instrument.get('simulated_instrument__sum')

    simulator = Flight.objects.all().filter(cat_class_query).aggregate(Sum('duration'))
    if simulator.get('duration__sum') is None:
        ases.simulator = 0
    else:
        ases.simulator = simulator.get('duration__sum')

    night = Flight.objects.all().filter(cat_class_query, night__gt=0).aggregate(Sum('night'))
    if night.get('night__sum') is None:
        ases.night = 0
    else:
        ases.night = night.get('night__sum')

    landings_day = Flight.objects.all().filter(cat_class_query).aggregate(Sum('landings_day'))
    if landings_day.get('landings_day__sum') is None:
        ases.landings_day = 0
    else:
        ases.landings_day = landings_day.get('landings_day__sum')

    landings_night = Flight.objects.all().filter(cat_class_query).aggregate(Sum('landings_night'))
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
        ases.last_30 = last_30.get('duration__sum')

    last_60 = today - datetime.timedelta(days=60)
    last_60 = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_60).aggregate(Sum('duration'))
    if last_60.get('duration__sum') is None:
        ases.last_60 = 0
    else:
        ases.last_60 = last_60.get('duration__sum')

    last_90 = today - datetime.timedelta(days=90)
    last_90 = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_90).aggregate(Sum('duration'))
    if last_90.get('duration__sum') is None:
        ases.last_90 = 0
    else:
        ases.last_90 = last_90.get('duration__sum')

    last_180 = today - datetime.timedelta(days=180)
    last_180 = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_180).aggregate(Sum('duration'))
    if last_180.get('duration__sum') is None:
        ases.last_180 = 0
    else:
        ases.last_180 = last_180.get('duration__sum')

    last_yr = today - datetime.timedelta(days=365)
    last_yr = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_yr).aggregate(Sum('duration'))
    if last_yr.get('duration__sum') is None:
        ases.last_yr = 0
    else:
        ases.last_yr = last_yr.get('duration__sum')

    last_2yr = today - datetime.timedelta(days=730)
    last_2yr = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=last_2yr).aggregate(Sum('duration'))
    if last_2yr.get('duration__sum') is None:
        ases.last_2yr = 0
    else:
        ases.last_2yr = last_2yr.get('duration__sum')

    ytd = datetime.date(today.year, 1, 1)
    ytd = Flight.objects.filter(cat_class_query).filter(date__lte=today,date__gte=ytd).aggregate(Sum('duration'))
    if ytd.get('duration__sum') is None:
        ases.ytd = 0
    else:
        ases.ytd = ytd.get('duration__sum')

    ases.save()
