from flights.models import Flight, Aircraft, TailNumber
from django.db.models import Sum
import datetime


def aircraft_total_time(aircraft_type):
    aircraft_total_time = Flight.objects.filter(aircraft_type=aircraft_type).aggregate(Sum('duration'))
    if not aircraft_total_time.get('duration__sum'):
        aircraft_total_time = 0
    else:
        aircraft_total_time = round(aircraft_total_time.get('duration__sum'), 1)
    return aircraft_total_time


def pilot_in_command_total(aircraft_type):
    pilot_in_command = Flight.objects.filter(pilot_in_command=True).filter(aircraft_type=aircraft_type).aggregate(Sum('duration'))
    if not pilot_in_command.get('duration__sum'):
        pilot_in_command = 0
    else:
        pilot_in_command = round(pilot_in_command.get('duration__sum'), 1)
    return pilot_in_command


def second_in_command_total(aircraft_type):
    second_in_command = Flight.objects.filter(second_in_command=True).filter(aircraft_type=aircraft_type).aggregate(Sum('duration'))
    if not second_in_command.get('duration__sum'):
        second_in_command = 0
    else:
        second_in_command = round(second_in_command.get('duration__sum'), 1)
    return second_in_command


def cross_country_total(aircraft_type):
    cross_country = Flight.objects.filter(cross_country=True).filter(aircraft_type=aircraft_type).aggregate(Sum('duration'))
    if not cross_country.get('duration__sum'):
        cross_country = 0
    else:
        cross_country = round(cross_country.get('duration__sum'), 1)
    return cross_country


def instructor_total(aircraft_type):
    instructor = Flight.objects.filter(instructor=True).filter(aircraft_type=aircraft_type).aggregate(Sum('duration'))
    if not instructor.get('duration__sum'):
        instructor = 0
    else:
        instructor = round(instructor.get('duration__sum'), 1)
    return instructor


def dual_total(aircraft_type):
    dual = Flight.objects.filter(dual=True).filter(aircraft_type=aircraft_type).aggregate(Sum('duration'))
    if not dual.get('duration__sum'):
        dual =0
    else:
        dual = round(dual.get('duration__sum'), 1)
    return dual

def solo_total(aircraft_type):
    solo = Flight.objects.filter(solo=True).filter(aircraft_type=aircraft_type).aggregate(Sum('duration'))
    if not solo.get('duration__sum'):
        solo = 0
    else:
        solo = round(solo.get('duration__sum'), 1)
    return solo

def instrument_total(aircraft_type):
    instrument = Flight.objects.filter(aircraft_type=aircraft_type).aggregate(Sum('instrument'))
    if not instrument.get('instrument__sum'):
        instrument = 0
    else:
        instrument = round(instrument.get('instrument__sum'), 1)
    return instrument

def simulated_instrument_total(aircraft_type):
    simulated_instrument = Flight.objects.filter(aircraft_type=aircraft_type).aggregate(Sum('simulated_instrument'))
    if not simulated_instrument.get('simulated_instrument__sum'):
        simulated_instrument = 0
    else:
        simulated_instrument = round(simulated_instrument.get('simulated_instrument__sum'), 1)
    return simulated_instrument

def simulator_total(aircraft_type):
    simulator = Flight.objects.filter(simulator=True).filter(aircraft_type=aircraft_type).aggregate(Sum('duration'))
    if not simulator.get('duration__sum'):
        simulator = 0
    else:
        simulator = round(simulator.get('duration__sum'), 1)
    return simulator

def night_total(aircraft_type):
    night = Flight.objects.filter(aircraft_type=aircraft_type).aggregate(Sum('night'))
    if not night.get('night__sum'):
        night = 0
    else:
        night = round(night.get('night__sum'), 1)
    return night

def landings_day_total(aircraft_type):
    landings_day = Flight.objects.filter(aircraft_type=aircraft_type).aggregate(Sum('landings_day'))
    if not landings_day.get('landings_day__sum'):
        landings_day = 0
    else:
        landings_day = landings_day.get('landings_day__sum')
    return landings_day

def landings_night_total(aircraft_type):
    landings_night = Flight.objects.filter(aircraft_type=aircraft_type).aggregate(Sum('landings_night'))
    if not landings_night.get('landings_night__sum'):
        landings_night = 0
    else:
        landings_night = landings_night.get('landings_night__sum')
    return landings_night

def last_flown(aircraft_type):
    try:
        last_flown = Flight.objects.filter(aircraft_type=aircraft_type).latest('date')
        last_flown = last_flown.date
        return last_flown
    except:
        pass

def last_30(aircraft_type):
    today = datetime.date.today()
    last_30 = datetime.timedelta(days=30)
    last_30 = today - last_30
    last_30 = Flight.objects.filter(aircraft_type=aircraft_type).filter(date__lte=today,date__gte=last_30).aggregate(Sum('duration'))
    if not last_30.get('duration__sum'):
        last_30 = 0
    else:
        last_30 = round(last_30.get('duration__sum'), 1)
    return last_30


def last_60(aircraft_type):
    today = datetime.date.today()
    last_60 = datetime.timedelta(days=60)
    last_60 = today - last_60
    last_60 = Flight.objects.filter(aircraft_type=aircraft_type).filter(date__lte=today,date__gte=last_60).aggregate(Sum('duration'))
    if not last_60.get('duration__sum'):
        last_60 = 0
    else:
        last_60 = round(last_60.get('duration__sum'), 1)
    return last_60


def last_90(aircraft_type):
    today = datetime.date.today()
    last_90 = datetime.timedelta(days=90)
    last_90 = today - last_90
    last_90 = Flight.objects.filter(aircraft_type=aircraft_type).filter(date__lte=today,date__gte=last_90).aggregate(Sum('duration'))
    if not last_90.get('duration__sum'):
        last_90 = 0
    else:
        last_90 = round(last_90.get('duration__sum'), 1)
    return last_90


def last_180(aircraft_type):
    today = datetime.date.today()
    last_180 = datetime.timedelta(days=180)
    last_180 = today - last_180
    last_180 = Flight.objects.filter(aircraft_type=aircraft_type).filter(date__lte=today,date__gte=last_180).aggregate(Sum('duration'))
    if not last_180.get('duration__sum'):
        last_180 = 0
    else:
        last_180 = round(last_180.get('duration__sum'), 1)
    return last_180

def last_yr(aircraft_type):
    today = datetime.date.today()
    last_yr = datetime.timedelta(days=365)
    last_yr = today - last_yr
    last_yr = Flight.objects.filter(aircraft_type=aircraft_type).filter(date__lte=today,date__gte=last_yr).aggregate(Sum('duration'))
    if not last_yr.get('duration__sum'):
        last_yr = 0
    else:
        last_yr = round(last_yr.get('duration__sum'), 1)
    return last_yr

def last_2yr(aircraft_type):
    today = datetime.date.today()
    last_2yr = datetime.timedelta(days=730)
    last_2yr = today - last_2yr
    last_2yr = Flight.objects.filter(aircraft_type=aircraft_type).filter(date__lte=today, date__gte=last_2yr).aggregate(Sum('duration'))
    if not last_2yr.get('duration__sum'):
        last_2yr = 0
    else:
        last_2yr = round(last_2yr.get('duration__sum'), 1)
    return last_2yr

def ytd(aircraft_type):
    today = datetime.date.today()
    ytd = datetime.date(today.year, 1, 1)
    ytd = Flight.objects.filter(aircraft_type=aircraft_type).filter(date__lte=today,date__gte=ytd).aggregate(Sum('duration'))
    if not ytd.get('duration__sum'):
        ytd = 0
    else:
        ytd = round(ytd.get('duration__sum'), 1)
    return ytd
