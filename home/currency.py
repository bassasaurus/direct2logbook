from logbook.date_formats import display_date
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

# Compatibility adapters for callers using the older tuple format.
def type_currency(user):
    from home.passenger_currency import passenger_currency
    snapshot = passenger_currency(user, today=datetime.date.today())
    return {row['label']: (row['day']['count'], row['day']['current'], row['night']['count'], row['night']['current'])
            for row in snapshot['types']}


def _landing_count(user, query, *, night=False):
    from home.passenger_currency import landing_status
    row = landing_status(Flight.objects.filter(user=user).filter(query), night=night, today=datetime.date.today())
    return row['count'], row['current']


def amel_vfr_day(user):
    return _landing_count(user, amel_query)


def amel_vfr_night(user):
    return _landing_count(user, amel_query, night=True)


def asel_vfr_day(user):
    return _landing_count(user, asel_query)


def asel_vfr_night(user):
    return _landing_count(user, asel_query, night=True)


def ases_vfr_day(user):
    return _landing_count(user, ases_query)


def ases_vfr_night(user):
    return _landing_count(user, ases_query, night=True)


def ames_vfr_day(user):
    return _landing_count(user, ames_query)


def ames_vfr_night(user):
    return _landing_count(user, ames_query, night=True)


def helo_vfr_day(user):
    return _landing_count(user, helo_query)


def helo_vfr_night(user):
    return _landing_count(user, helo_query, night=True)


def gyro_vfr_day(user):
    return _landing_count(user, gyro_query)


def gyro_vfr_night(user):
    return _landing_count(user, gyro_query, night=True)


def medical_expiry_date(profile):
    if profile.first_class:
        months = 6 if profile.over_40 else 12
    elif profile.second_class:
        months = 12
    elif profile.third_class:
        months = 24 if profile.over_40 else 60
    else:
        return None

    from home.flight_reviews import calendar_month_due_date
    return calendar_month_due_date(profile.medical_issue_date, months)


def medical_duration(user):
    current_date = datetime.date.today()
    expiry_date = medical_expiry_date(user.profile) or current_date - datetime.timedelta(days=1)

    if current_date <= expiry_date:
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


INSTRUMENT_CATEGORIES = {'A': 'Airplane', 'R': 'Helicopter'}


def default_instrument_category(user):
    from django.utils import timezone
    latest = Flight.objects.filter(user=user, date__lte=timezone.localdate()).select_related('aircraft_type').order_by('-date', '-pk').first()
    if latest:
        aircraft = latest.aircraft_type
        if aircraft.aircraft_category == 'A':
            return 'A'
        if aircraft.aircraft_category == 'R' and aircraft.aircraft_class == 'HELO':
            return 'R'
        return ''
    from profile.models import Reminder
    return Reminder.objects.filter(user=user, kind='ipc').order_by('-ipc_completed_date', '-pk').values_list('ipc_category', flat=True).first() or ''


def instrument_recency_categories(user):
    return [snapshot for category in ('A', 'R', '')
            if (snapshot := instrument_recency(user, category=category))['instrument_applicable']]


def instrument_recency(user, *, ipc=None, category=None):
    """Shared logged instrument checks using the rolling six-calendar-month window."""
    from django.utils import timezone
    from profile.models import Reminder
    from flights.models import Imported
    from home.flight_reviews import calendar_month_due_date
    today = timezone.localdate()
    window_start = (today.replace(day=1) - relativedelta(months=6))
    past = Flight.objects.filter(user=user, date__lte=today)
    if category is None:
        category = ipc.ipc_category if ipc else default_instrument_category(user)
    if category == 'A':
        category_filter = Q(aircraft_type__aircraft_category='A')
    elif category == 'R':
        category_filter = Q(aircraft_type__aircraft_category='R', aircraft_type__aircraft_class='HELO')
    else:
        category_filter = ~Q(aircraft_type__aircraft_category='A') & ~Q(aircraft_type__aircraft_category='R', aircraft_type__aircraft_class='HELO')
    past = past.filter(category_filter)
    flights = past.filter(date__gte=window_start)
    quantity = flights.filter(approach__number__gt=0).aggregate(quantity=Sum('approach__number'))['quantity'] or 0
    approaches = past.filter(approach__number__gt=0).values('date', 'approach__number').order_by('-date', '-pk')
    cumulative = 0
    sixth_date = None
    latest_approach = None
    approach_dates = []
    for row in approaches.iterator():
        if latest_approach is None:
            latest_approach = row['date']
        if row['date'] >= window_start:
            approach_dates.extend([row['date']] * min(row['approach__number'], 6 - len(approach_dates)))
        cumulative += row['approach__number']
        if cumulative >= 6:
            sixth_date = row['date']
            break
    approach_until = calendar_month_due_date(sixth_date or latest_approach, 6)
    last_hold = past.filter(hold=True).order_by('-date', '-pk').values_list('date', flat=True).first()
    hold_date = last_hold if last_hold and last_hold >= window_start else None
    logged_until = min(approach_until, calendar_month_due_date(last_hold, 6)) if sixth_date and last_hold else None
    if ipc is None:
        ipc = Reminder.objects.filter(user=user, kind=Reminder.Kind.IPC, ipc_category=category, ipc_completed_date__lte=today).order_by('-ipc_completed_date', '-pk').first()
    ipc_date = ipc.ipc_completed_date if ipc and ipc.ipc_category == category and ipc.ipc_completed_date <= today else None
    ipc_until = calendar_month_due_date(ipc_date, 6)
    # Undated summary totals cannot establish recency or a known aircraft category.
    instrument_time = past.filter(Q(instrument__gt=0) | Q(simulated_instrument__gt=0)).exists()
    if not category:
        instrument_time = instrument_time or Imported.objects.filter(user=user).filter(
            Q(instrument__gt=0) | Q(simulated_instrument__gt=0)).exists()
    applicable = bool(instrument_time or ipc_date)
    review_until = max(value for value in (ipc_until, logged_until) if value is not None) if ipc_until or logged_until else None
    # Show what will be missing immediately after the current window runs out.
    # Only already-logged experience is projected; future flights are never assumed.
    action_date = review_until + datetime.timedelta(days=1) if review_until and review_until >= today else today
    action_window_start = action_date.replace(day=1) - relativedelta(months=6)
    remaining = past.filter(date__gte=action_window_start, approach__number__gt=0).aggregate(quantity=Sum('approach__number'))['quantity'] or 0
    approaches_needed = max(0, 6 - remaining)
    holding_needed = not last_hold or last_hold < action_window_start
    due = review_until if review_until and review_until >= today else today
    tasks = []
    if approaches_needed:
        tasks.append(f'{approaches_needed} approach' + ('es' if approaches_needed != 1 else ''))
    if holding_needed:
        tasks.append('holding')
    action_text = ('By ' + display_date(due) if action_date > today else 'Check logbook')
    action_text += ': ' + (', '.join(tasks) if tasks else 'review instrument currency')
    ifr_current = bool(category and review_until and review_until >= today)
    category_note = '' if category else 'Verify the aircraft category and IPC record.'
    recency_basis = bool(logged_until and logged_until >= today and (not ipc_until or logged_until >= ipc_until))
    source = 'recency' if ifr_current and recency_basis else 'ipc' if ifr_current else None
    ipc_required_from = (review_until.replace(day=1) + relativedelta(months=7)) if review_until else None
    ipc_required = bool(not ifr_current and ipc_required_from and today >= ipc_required_from)
    recovery_until = ipc_required_from - datetime.timedelta(days=1) if ipc_required_from else None
    if not category:
        status_message = 'Review IFR currency. Category not specified.'
    elif ifr_current:
        status_message = f'Based on logged information:\nRequired by {display_date(review_until)}'
    elif ipc_required:
        status_message = f'IFR currency expired {display_date(review_until)}.\nVerify your records.'
    elif review_until:
        status_message = f'IFR currency expired {display_date(review_until)}. {action_text}.\nVerify your records.'
    else:
        status_message = f'Review IFR currency. {action_text}'
    if category_note:
        status_message += '\n' + category_note
    holding_warning = ('Holding required' if quantity > 0 and not hold_date else None)
    next_requirement = {'due_date': due, 'effective_date': action_date,
                        'approaches_needed': approaches_needed, 'holding_needed': bool(holding_needed),
                        'message': action_text}
    snapshot = {
        'instrument_category': category, 'instrument_category_label': INSTRUMENT_CATEGORIES.get(category, 'Category not specified'),
        'instrument_history': applicable, 'instrument_applicable': applicable,
        'instrument_currency_source': source, 'ipc_required': ipc_required, 'ipc_required_from': ipc_required_from,
        'instrument_recovery_until': recovery_until,
        'ifr_current': ifr_current, 'ifr_current_until': review_until if ifr_current else None,
        'instrument_status_message': status_message, 'instrument_holding_warning': holding_warning,
        'next_instrument_requirement': next_requirement,
        'still_needed': max(0, 6 - quantity), 'appr_quantity': quantity, 'appr_current_date': approach_until,
        'hold_quantity': 1 if hold_date else 0, 'hold_current_date': hold_date,
        'instrument_window_start': window_start,
        'ipc_completed_date': ipc_date, 'ipc_review_due_date': ipc_until,
        'instrument_review_date': review_until,
        'instrument_approach_dates': approach_dates,
    }
    from home.instrument_presentation import instrument_presentation
    snapshot['instrument_display'] = instrument_presentation(snapshot, today=today)
    return snapshot


def instrument_alert_details(instrument, today):
    due = instrument['instrument_review_date']
    days = (due - today).days if due else None
    current = instrument['ifr_current']
    requirement = instrument['next_instrument_requirement']
    tasks_due = bool(requirement['approaches_needed'] or requirement['holding_needed'])
    approaching = current and days is not None and 0 <= days <= 30 and tasks_due
    missing_logged_requirements = instrument['still_needed'] > 0 or not instrument['hold_quantity']
    expired = days is not None and days < 0
    severity = ('danger' if expired else 'warning' if missing_logged_requirements or approaching
                else 'danger' if not current else 'success')
    message = instrument['instrument_status_message']
    if approaching:
        message += '. ' + requirement['message']
    return {'message': message, 'severity': severity, 'due_date': due, 'days_remaining': days,
            'holding_warning': instrument['instrument_holding_warning']}


def instrument_currency_notice(user, instrument):
    """Derived IFR alert, including expired history, without duplicate saved IPC rows."""
    if instrument['ipc_completed_date'] or not instrument['instrument_history']:
        return None
    from django.utils import timezone
    return {'id': 'instrument-currency' + (('-' + instrument['instrument_category']) if instrument['instrument_category'] else ''),
            'kind': 'ipc', 'title': 'IFR — ' + instrument['instrument_category_label'],
            'category': instrument['instrument_category'],
            **instrument_alert_details(instrument, timezone.localdate()),
            'completion_percent': None, 'hours_remaining': None}
