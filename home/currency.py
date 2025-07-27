from flights.models import Flight
from django.db.models import Sum, Q
import datetime
import calendar
from dateutil.relativedelta import relativedelta


asel_query = Q(aircraft_type__aircraft_category='A') & Q(
    aircraft_type__aircraft_class='SEL')
amel_query = Q(aircraft_type__aircraft_category='A') & Q(
    aircraft_type__aircraft_class='MEL')
ases_query = Q(aircraft_type__aircraft_category='A') & Q(
    aircraft_type__aircraft_class='SES')
ames_query = Q(aircraft_type__aircraft_category='A') & Q(
    aircraft_type__aircraft_class='MES')
helo_query = Q(aircraft_type__aircraft_category='R') & Q(
    aircraft_type__aircraft_class='HELO')
gyro_query = Q(aircraft_type__aircraft_category='R') & Q(
    aircraft_type__aircraft_class='GYRO')

today = datetime.date.today()
last_2yr = today - datetime.timedelta(days=730)
last_90 = today - datetime.timedelta(days=90)

type_rating = Q(aircraft_type__requires_type=True) & Q(date__gte=last_2yr)


# type currency
def type_currency(user):

    flights = Flight.objects.filter(user=user).filter(type_rating)

    ac_set = set()

    type_currency_dict = dict()

    for flight in flights:

        ac_set.add(flight.aircraft_type)

    for aircraft in ac_set:

        type_currency_dict[str(aircraft)] = 0, False

        day_landings = Flight.objects.filter(user=user).filter(aircraft_type=aircraft).filter(
            date__lte=today, date__gte=last_90).aggregate(Sum('landings_day'))
        night_landings = Flight.objects.filter(user=user).filter(aircraft_type=aircraft).filter(
            date__lte=today, date__gte=last_90).aggregate(Sum('landings_night'))

        if not day_landings.get('landings_day__sum'):
            day_landings = 0
            day_current = False
        else:
            day_landings = day_landings.get('landings_day__sum')
            if day_landings >= 3:
                day_current = True
            else:
                day_current = False

        if not night_landings.get('landings_night__sum'):
            night_landings = 0
            night_current = False
        else:
            night_landings = night_landings.get('landings_night__sum')
            if night_landings >= 3:
                night_current = True
            else:
                night_current = False

        type_currency_dict[str(
            aircraft)] = day_landings, day_current, night_landings, night_current

    return type_currency_dict


# amel currency
def amel_vfr_day(user):
    today = datetime.date.today()
    last_90 = today - datetime.timedelta(days=90)
    amel_vfr_day = Flight.objects.filter(user=user).filter(amel_query).filter(
        date__lte=today, date__gte=last_90).aggregate(Sum('landings_day'))
    if not amel_vfr_day.get('landings_day__sum'):
        amel_vfr_day = 0
    else:
        amel_vfr_day = amel_vfr_day.get('landings_day__sum')
    if amel_vfr_day < 3:
        current = False
    else:
        current = True
    return amel_vfr_day, current


def amel_vfr_night(user):
    today = datetime.date.today()
    last_90 = today - datetime.timedelta(days=90)
    amel_vfr_night = Flight.objects.filter(user=user).filter(amel_query).filter(
        date__lte=today, date__gte=last_90).aggregate(Sum('landings_night'))
    if not amel_vfr_night.get('landings_night__sum'):
        amel_vfr_night = 0
    else:
        amel_vfr_night = amel_vfr_night.get('landings_night__sum')
    if amel_vfr_night < 3:
        current = False
    else:
        current = True
    return amel_vfr_night, current


# asel currency
def asel_vfr_day(user):
    today = datetime.date.today()
    last_90 = today - datetime.timedelta(days=90)
    asel_vfr_day = Flight.objects.filter(user=user).filter(asel_query).filter(
        date__lte=today, date__gte=last_90).aggregate(Sum('landings_day'))
    if not asel_vfr_day.get('landings_day__sum'):
        asel_vfr_day = 0
    else:
        asel_vfr_day = asel_vfr_day.get('landings_day__sum')
    if asel_vfr_day < 3:
        current = False
    else:
        current = True
    return asel_vfr_day, current


def asel_vfr_night(user):
    today = datetime.date.today()
    last_90 = today - datetime.timedelta(days=90)
    asel_vfr_night = Flight.objects.filter(user=user).filter(asel_query).filter(
        date__lte=today, date__gte=last_90).aggregate(Sum('landings_night'))
    if not asel_vfr_night.get('landings_night__sum'):
        asel_vfr_night = 0
    else:
        asel_vfr_night = asel_vfr_night.get('landings_night__sum')
    if asel_vfr_night < 3:
        current = False
    else:
        current = True
    return asel_vfr_night, current


# ases currency
def ases_vfr_day(user):
    today = datetime.date.today()
    last_90 = today - datetime.timedelta(days=90)
    ases_vfr_day = Flight.objects.filter(user=user).filter(ases_query).filter(
        date__lte=today, date__gte=last_90).aggregate(Sum('landings_day'))
    if not ases_vfr_day.get('landings_day__sum'):
        ases_vfr_day = 0
    else:
        ases_vfr_day = ases_vfr_day.get('landings_day__sum')
    if ases_vfr_day < 3:
        current = False
    else:
        current = True
    return ases_vfr_day, current


def ases_vfr_night(user):
    today = datetime.date.today()
    last_90 = today - datetime.timedelta(days=90)
    ases_vfr_night = Flight.objects.filter(user=user).filter(ases_query).filter(
        date__lte=today, date__gte=last_90).aggregate(Sum('landings_night'))
    if not ases_vfr_night.get('landings_night__sum'):
        ases_vfr_night = 0
    else:
        ases_vfr_night = ases_vfr_night.get('landings_night__sum')
    if ases_vfr_night < 3:
        current = False
    else:
        current = True
    return ases_vfr_night, current


# ames currency
def ames_vfr_day(user):
    today = datetime.date.today()
    last_90 = today - datetime.timedelta(days=90)
    ames_vfr_day = Flight.objects.filter(user=user).filter(ames_query).filter(
        date__lte=today, date__gte=last_90).aggregate(Sum('landings_day'))
    if not ames_vfr_day.get('landings_day__sum'):
        ames_vfr_day = 0
    else:
        ames_vfr_day = ames_vfr_day.get('landings_day__sum')
    if ames_vfr_day < 3:
        current = False
    else:
        current = True
    return ames_vfr_day, current


def ames_vfr_night(user):
    today = datetime.date.today()
    last_90 = today - datetime.timedelta(days=90)
    ames_vfr_night = Flight.objects.filter(user=user).filter(ames_query).filter(
        date__lte=today, date__gte=last_90).aggregate(Sum('landings_night'))
    if not ames_vfr_night.get('landings_night__sum'):
        ames_vfr_night = 0
    else:
        ames_vfr_night = ames_vfr_night.get('landings_night__sum')
    if ames_vfr_night < 3:
        current = False
    else:
        current = True
    return ames_vfr_night, current


# helo currency
def helo_vfr_day(user):
    today = datetime.date.today()
    last_90 = today - datetime.timedelta(days=90)
    helo_vfr_day = Flight.objects.filter(user=user).filter(helo_query).filter(
        date__lte=today, date__gte=last_90).aggregate(Sum('landings_day'))
    if not helo_vfr_day.get('landings_day__sum'):
        helo_vfr_day = 0
    else:
        helo_vfr_day = helo_vfr_day.get('landings_day__sum')
    if helo_vfr_day < 3:
        current = False
    else:
        current = True
    return helo_vfr_day, current


def helo_vfr_night(user):
    today = datetime.date.today()
    last_90 = today - datetime.timedelta(days=90)
    helo_vfr_night = Flight.objects.filter(user=user).filter(helo_query).filter(
        date__lte=today, date__gte=last_90).aggregate(Sum('landings_night'))
    if not helo_vfr_night.get('landings_night__sum'):
        helo_vfr_night = 0
    else:
        helo_vfr_night = helo_vfr_night.get('landings_night__sum')
    if helo_vfr_night < 3:
        current = False
    else:
        current = True
    return helo_vfr_night, current


# gyro currency
def gyro_vfr_day(user):
    today = datetime.date.today()
    last_90 = today - datetime.timedelta(days=90)
    gyro_vfr_day = Flight.objects.filter(user=user).filter(gyro_query).filter(
        date__lte=today, date__gte=last_90).aggregate(Sum('landings_day'))
    if not gyro_vfr_day.get('landings_day__sum'):
        gyro_vfr_day = 0
    else:
        gyro_vfr_day = gyro_vfr_day.get('landings_day__sum')
    if gyro_vfr_day < 3:
        current = False
    else:
        current = True
    return gyro_vfr_day, current


def gyro_vfr_night(user):
    today = datetime.date.today()
    last_90 = today - datetime.timedelta(days=90)
    gyro_vfr_night = Flight.objects.filter(user=user).filter(gyro_query).filter(
        date__lte=today, date__gte=last_90).aggregate(Sum('landings_night'))
    if not gyro_vfr_night.get('landings_night__sum'):
        gyro_vfr_night = 0
    else:
        gyro_vfr_night = gyro_vfr_night.get('landings_night__sum')
    if gyro_vfr_night < 3:
        current = False
    else:
        current = True
    return gyro_vfr_night, current


def medical_duration(user):  # still need to start calculations from next month after issue
    issue_date = user.profile.medical_issue_date
    current_date = datetime.date.today()

    if user.profile.first_class and not user.profile.over_40:
        one_year = relativedelta(months=+12)
        expiry_date = issue_date + one_year
        expiry_date = expiry_date.replace(
            day=calendar.monthrange(expiry_date.year, expiry_date.month)[1])

    elif user.profile.first_class and user.profile.over_40:
        six_months = relativedelta(months=+6)
        expiry_date = issue_date + six_months
        expiry_date = expiry_date.replace(
            day=calendar.monthrange(expiry_date.year, expiry_date.month)[1])

    elif user.profile.second_class and not user.profile.over_40:
        two_years = relativedelta(months=+24)
        expiry_date = issue_date + two_years
        expiry_date = expiry_date.replace(
            day=calendar.monthrange(expiry_date.year, expiry_date.month)[1])

    elif user.profile.second_class and user.profile.over_40:
        one_year = relativedelta(months=+12)
        expiry_date = issue_date + one_year
        expiry_date = expiry_date.replace(
            day=calendar.monthrange(expiry_date.year, expiry_date.month)[1])

    elif user.profile.third_class and not user.profile.over_40:
        five_years = relativedelta(months=+60)
        expiry_date = issue_date + five_years
        expiry_date = expiry_date.replace(
            day=calendar.monthrange(expiry_date.year, expiry_date.month)[1])

    elif user.profile.third_class and user.profile.over_40:
        three_years = relativedelta(months=+36)
        expiry_date = issue_date + three_years
        expiry_date = expiry_date.replace(
            day=calendar.monthrange(expiry_date.year, expiry_date.month)[1])

    else:
        expiry_date = today - datetime.timedelta(days=1)

# ------------------------------------

    if current_date < expiry_date:
        current = True
    else:
        current = False

    if current_date > expiry_date:
        expired = True
    else:
        expired = False

    if current_date.month == expiry_date.month and current_date.year == expiry_date.year:
        this_month = True
    else:
        this_month = False

    if not expiry_date:
        expiring = True
    else:
        if (expiry_date - current_date) <= datetime.timedelta(days=31):
            expiring = True
        else:
            expiring = False

    return (expiry_date, this_month, expiring, expired, current)
