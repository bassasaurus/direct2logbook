from flights.models import Flight
from accounts.models import User, Profile
from django.db.models import Sum, Q
import datetime
from dateutil.relativedelta import relativedelta

asel_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains = 'single engine land') & Q(aircraft_type__aircraft_category__aircraft_category__icontains = 'airplane')
amel_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains = 'multi engine land') & Q(aircraft_type__aircraft_category__aircraft_category__icontains = 'airplane')
ases_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains = 'single engine sea') & Q(aircraft_type__aircraft_category__aircraft_category__icontains = 'airplane')
ames_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains = 'multi engine sea') & Q(aircraft_type__aircraft_category__aircraft_category__icontains = 'airplane')
helo_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains = 'helicopter') & Q(aircraft_type__aircraft_category__aircraft_category__icontains = 'rotorcraft')
gyro_query = Q(aircraft_type__aircraft_class__aircraft_class__icontains = 'gyroplane') & Q(aircraft_type__aircraft_category__aircraft_category__icontains = 'rotorcraft')

# amel currency
def amel_vfr_day(user):
    user_kwarg = {'user' : user}
    today = datetime.date.today()
    last_90 = today - datetime.timedelta(days=90)
    amel_vfr_day = Flight.objects.filter(user=user).filter(amel_query).filter(date__lte=today,date__gte=last_90).aggregate(Sum('landings_day'))
    if not amel_vfr_day.get('landings_day__sum'):
        amel_vfr_day = 0
    else:
        amel_vfr_day = round(amel_vfr_day.get('landings_day__sum'), 1)
    if amel_vfr_day < 3:
        current = False
    else:
        current = True
    return amel_vfr_day, current

def amel_vfr_night(user):
    user_kwarg = {'user' : user}
    today = datetime.date.today()
    last_90 = today - datetime.timedelta(days=90)
    amel_vfr_night = Flight.objects.filter(user=user).filter(amel_query).filter(date__lte=today,date__gte=last_90).aggregate(Sum('landings_night'))
    if not amel_vfr_night.get('landings_night__sum'):
        amel_vfr_night = 0
    else:
        amel_vfr_night = round(amel_vfr_night.get('landings_night__sum'), 1)
    if amel_vfr_night < 3:
        current = False
    else:
        current = True
    return amel_vfr_night, current

# asel currency
def asel_vfr_day(user):
    user_kwarg = {'user' : user}
    today = datetime.date.today()
    last_90 = today - datetime.timedelta(days=90)
    asel_vfr_day = Flight.objects.filter(user=user).filter(asel_query).filter(date__lte=today,date__gte=last_90).aggregate(Sum('landings_day'))
    if not asel_vfr_day.get('landings_day__sum'):
        asel_vfr_day = 0
    else:
        asel_vfr_day = round(asel_vfr_day.get('landings_day__sum'), 1)
    if asel_vfr_day < 3:
        current = False
    else:
        current = True
    return asel_vfr_day, current

def asel_vfr_night(user):
    user_kwarg = {'user' : user}
    today = datetime.date.today()
    last_90 = today - datetime.timedelta(days=90)
    asel_vfr_night = Flight.objects.filter(user=user).filter(asel_query).filter(date__lte=today,date__gte=last_90).aggregate(Sum('landings_night'))
    if not asel_vfr_night.get('landings_night__sum'):
        asel_vfr_night = 0
    else:
        asel_vfr_night = round(asel_vfr_night.get('landings_night__sum'), 1)
    if asel_vfr_night < 3:
        current = False
    else:
        current = True
    return asel_vfr_night, current

# ases currency
def ases_vfr_day(user):
    user_kwarg = {'user' : user}
    today = datetime.date.today()
    last_90 = today - datetime.timedelta(days=90)
    ases_vfr_day = Flight.objects.filter(user=user).filter(ases_query).filter(date__lte=today,date__gte=last_90).aggregate(Sum('landings_day'))
    if not ases_vfr_day.get('landings_day__sum'):
        ases_vfr_day = 0
    else:
        ases_vfr_day = round(ases_vfr_day.get('landings_day__sum'), 1)
    if ases_vfr_day < 3:
        current = False
    else:
        current = True
    return ases_vfr_day, current

def ases_vfr_night(user):
    user_kwarg = {'user' : user}
    today = datetime.date.today()
    last_90 = today - datetime.timedelta(days=90)
    ases_vfr_night = Flight.objects.filter(user=user).filter(ases_query).filter(date__lte=today,date__gte=last_90).aggregate(Sum('landings_night'))
    if not ases_vfr_night.get('landings_night__sum'):
        ases_vfr_night = 0
    else:
        ases_vfr_night = round(ases_vfr_night.get('landings_night__sum'), 1)
    if ases_vfr_night < 3:
        current = False
    else:
        current = True
    return ases_vfr_night, current

# ames currency
def ames_vfr_day(user):
    user_kwarg = {'user' : user}
    today = datetime.date.today()
    last_90 = today - datetime.timedelta(days=90)
    ames_vfr_day = Flight.objects.filter(user=user).filter(ames_query).filter(date__lte=today,date__gte=last_90).aggregate(Sum('landings_day'))
    if not ames_vfr_day.get('landings_day__sum'):
        ames_vfr_day = 0
    else:
        ames_vfr_day = round(ames_vfr_day.get('landings_day__sum'), 1)
    if ames_vfr_day < 3:
        current = False
    else:
        current = True
    return ames_vfr_day, current

def ames_vfr_night(user):
    user_kwarg = {'user' : user}
    today = datetime.date.today()
    last_90 = today - datetime.timedelta(days=90)
    ames_vfr_night = Flight.objects.filter(user=user).filter(ames_query).filter(date__lte=today,date__gte=last_90).aggregate(Sum('landings_night'))
    if not ames_vfr_night.get('landings_night__sum'):
        ames_vfr_night = 0
    else:
        ames_vfr_night = round(ames_vfr_night.get('landings_night__sum'), 1)
    if ames_vfr_night < 3:
        current = False
    else:
        current = True
    return ames_vfr_night, current

# helo currency
def helo_vfr_day(user):
    user_kwarg = {'user' : user}
    today = datetime.date.today()
    last_90 = today - datetime.timedelta(days=90)
    helo_vfr_day = Flight.objects.filter(user=user).filter(helo_query).filter(date__lte=today,date__gte=last_90).aggregate(Sum('landings_day'))
    if not helo_vfr_day.get('landings_day__sum'):
        helo_vfr_day = 0
    else:
        helo_vfr_day = round(helo_vfr_day.get('landings_day__sum'), 1)
    if helo_vfr_day < 3:
        current = False
    else:
        current = True
    return helo_vfr_day, current

def helo_vfr_night(user):
    user_kwarg = {'user' : user}
    today = datetime.date.today()
    last_90 = today - datetime.timedelta(days=90)
    helo_vfr_night = Flight.objects.filter(user=user).filter(helo_query).filter(date__lte=today,date__gte=last_90).aggregate(Sum('landings_night'))
    if not helo_vfr_night.get('landings_night__sum'):
        helo_vfr_night = 0
    else:
        helo_vfr_night = round(helo_vfr_night.get('landings_night__sum'), 1)
    if helo_vfr_night < 3:
        current = False
    else:
        current = True
    return helo_vfr_night, current

# gyro currency
def gyro_vfr_day(user):
    user_kwarg = {'user' : user}
    today = datetime.date.today()
    last_90 = today - datetime.timedelta(days=90)
    gyro_vfr_day = Flight.objects.filter(user=user).filter(gyro_query).filter(date__lte=today,date__gte=last_90).aggregate(Sum('landings_day'))
    if not gyro_vfr_day.get('landings_day__sum'):
        gyro_vfr_day = 0
    else:
        gyro_vfr_day = round(gyro_vfr_day.get('landings_day__sum'), 1)
    if gyro_vfr_day < 3:
        current = False
    else:
        current = True
    return gyro_vfr_day, current

def gyro_vfr_night(user):
    user_kwarg = {'user' : user}
    today = datetime.date.today()
    last_90 = today - datetime.timedelta(days=90)
    gyro_vfr_night = Flight.objects.filter(user=user).filter(gyro_query).filter(date__lte=today,date__gte=last_90).aggregate(Sum('landings_night'))
    if not gyro_vfr_night.get('landings_night__sum'):
        gyro_vfr_night = 0
    else:
        gyro_vfr_night = round(gyro_vfr_night.get('landings_night__sum'), 1)
    if gyro_vfr_night < 3:
        current = False
    else:
        current = True
    return gyro_vfr_night, current

def medical_duration(user): #still need to start calculations from next month after issue
    issue_date = user.profile.medical_issue_date
    current_month = datetime.date.today()

    if user.profile.first_class and not user.profile.over_40:
        one_year = relativedelta(months=+12)
        expiry_date = issue_date + one_year

    elif user.profile.first_class and user.profile.over_40:
        six_months = relativedelta(months=+6)
        expiry_date = issue_date + six_months

    elif user.profile.second_class and not user.profile.over_40:
        two_years = relativedelta(months=+24)
        expiry_date = issue_date + two_years

    elif user.profile.second_class and user.profile.over_40:
        one_year = relativedelta(months=+12)
        expiry_date = issue_date + one_year

    elif user.profile.third_class and not user.profile.over_40:
        five_years = relativedelta(months=+60)
        expiry_date = issue_date + five_years

    elif user.profile.third_class and user.profile.over_40:
        three_years = relativedelta(months=+36)
        expiry_date = issue_date + three_years

    else:
        expiry_date = None

    if current_month == expiry_date:
        this_month = True
    else:
        this_month = False

    return(expiry_date, this_month)
