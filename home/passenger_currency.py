"""Logged landing recency shared by web and mobile; aircraft sessions only."""
from datetime import timedelta

from django.db.models import Q, Sum
from django.utils import timezone

from flights.aircraft_classification import SUMMARY_CLASSIFICATIONS
from flights.models import Flight
from home.pilot_time import SUMMARY_LABELS


def landing_status(rows, *, night=False, today=None):
    today = today or timezone.localdate()
    recorded = rows.exclude(simulator=True).filter(date__lte=today)
    rows = recorded.filter(date__gte=today - timedelta(days=90))
    if night:
        rows = rows.filter(night_landings_full_stop=True)
        totals = rows.aggregate(night=Sum('landings_night'))
        count = totals['night'] or 0
        date_rows = recorded.filter(night_landings_full_stop=True, landings_night__gt=0)
    else:
        totals = rows.aggregate(day=Sum('landings_day'), night=Sum('landings_night'))
        count = (totals['day'] or 0) + (totals['night'] or 0)
        date_rows = recorded.filter(Q(landings_day__gt=0) | Q(landings_night__gt=0))
    dates = []
    for row in date_rows.order_by('-date', '-pk').values('date', 'landings_day', 'landings_night').iterator():
        quantity = (row['landings_night'] or 0) + (0 if night else row['landings_day'] or 0)
        dates.extend([row['date']] * min(quantity, 3 - len(dates)))
        if len(dates) == 3:
            break
    return {'count': count, 'required': 3, 'current': count >= 3,
            'last_dates': dates, 'still_needed': max(0, 3 - count),
            'valid_through': min(dates) + timedelta(days=90) if len(dates) == 3 else None}


def passenger_currency(user, *, today=None):
    today = today or timezone.localdate()
    flights = Flight.objects.filter(user=user, date__lte=today).exclude(simulator=True)
    recorded = set(flights.order_by().values_list('aircraft_type__aircraft_category', 'aircraft_type__aircraft_class').distinct())
    categories = []
    for code, (category, klass) in SUMMARY_CLASSIFICATIONS.items():
        if (category, klass) in recorded:
            rows = flights.filter(aircraft_type__aircraft_category=category, aircraft_type__aircraft_class=klass)
            categories.append({'label': code, 'display_label': SUMMARY_LABELS.get(code, code),
                               'day': landing_status(rows, today=today),
                               'night': landing_status(rows, night=True, today=today)})
    types = []
    aircraft = flights.filter(aircraft_type__requires_type=True,
        date__gte=today - timedelta(days=730)).order_by().values_list('aircraft_type_id', 'aircraft_type__aircraft_type').distinct()
    for pk, name in sorted(aircraft, key=lambda pair: pair[1]):
        rows = flights.filter(aircraft_type_id=pk)
        types.append({'label': name, 'display_label': name,
                      'day': landing_status(rows, today=today),
                      'night': landing_status(rows, night=True, today=today)})
    return {'categories': categories, 'types': types}
