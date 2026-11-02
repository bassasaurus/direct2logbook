"""Date-sensitive summary fields shared by save signals and daily maintenance."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Max, Q, Sum
from django.utils import timezone

from flights.models import Flight, Imported, Stat, Total


WINDOW_DAYS = {'last_30': 30, 'last_60': 60, 'last_90': 90,
               'last_180': 180, 'last_yr': 365, 'last_2yr': 730}
ROLLING_FIELDS = tuple(WINDOW_DAYS) + ('ytd', 'last_flown')
CATEGORY_FILTERS = {
    'All': Q(),
    'ASEL': Q(aircraft_type__aircraft_category='A', aircraft_type__aircraft_class='SEL'),
    'AMEL': Q(aircraft_type__aircraft_category='A', aircraft_type__aircraft_class='MEL'),
    'ASES': Q(aircraft_type__aircraft_category='A', aircraft_type__aircraft_class='SES'),
    'AMES': Q(aircraft_type__aircraft_category='A', aircraft_type__aircraft_class='MES'),
    'HELO': Q(aircraft_type__aircraft_category='R', aircraft_type__aircraft_class='HELO'),
    'GYRO': Q(aircraft_type__aircraft_category='R', aircraft_type__aircraft_class='GYRO'),
}


def normalize_total_category(label):
    category = label.strip().upper()
    category = 'All' if category == 'ALL' else category
    return category if category in CATEGORY_FILTERS else None


def rolling_values(flights, imported, as_of=None):
    as_of = as_of or timezone.localdate()
    bounds = {field: as_of - timedelta(days=days) for field, days in WINDOW_DAYS.items()}
    bounds['ytd'] = date(as_of.year, 1, 1)
    # CSV-imported flights are normal dated Flight rows. Historical Imported
    # snapshots lack individual dates, so their rolling balances cannot be aged.
    values = flights.aggregate(
        **{field: Sum('duration', filter=Q(date__gte=start, date__lte=as_of))
           for field, start in bounds.items()},
        last_flown=Max('date', filter=Q(date__lte=as_of)),
    )
    historical_last = imported.filter(last_flown__lte=as_of).aggregate(last=Max('last_flown'))['last']
    dates = [value for value in (values['last_flown'], historical_last) if value is not None]
    values['last_flown'] = max(dates) if dates else None
    for field in bounds:
        values[field] = values[field] or Decimal('0.0')
    return values


def assign_rolling_values(summary, flights, imported, as_of=None):
    for field, value in rolling_values(flights, imported, as_of).items():
        setattr(summary, field, value)


def refresh_rolling_stats(as_of=None, user_id=None, dry_run=False):
    as_of = as_of or timezone.localdate()
    stats = Stat.objects.all()
    totals = Total.objects.all()
    if user_id is not None:
        stats = stats.filter(user_id=user_id)
        totals = totals.filter(user_id=user_id)
    counts = {'stats': 0, 'totals': 0, 'skipped_total_ids': []}
    users = stats.order_by().values_list('user_id', flat=True).union(
        totals.order_by().values_list('user_id', flat=True))
    for owner_id in users.iterator():
        # The CSV import also locks its user first. Lock summaries in a stable
        # order, update only these eight fields, and commit each user separately.
        with transaction.atomic():
            if not dry_run and not get_user_model().objects.select_for_update().filter(pk=owner_id).exists():
                continue
            for model, summaries, label in ((Stat, stats, 'stats'), (Total, totals, 'totals')):
                owned = summaries.filter(user_id=owner_id).order_by('pk')
                if not dry_run:
                    owned = owned.select_for_update()
                for summary in owned:
                    if isinstance(summary, Stat):
                        scope = Q(aircraft_type__aircraft_type=summary.aircraft_type)
                    else:
                        category = normalize_total_category(summary.total)
                        if category is None:
                            # Unknown labels have no safe filtering rule. Preserve
                            # their data and report them without blocking other rows.
                            counts['skipped_total_ids'].append(summary.pk)
                            continue
                        scope = CATEGORY_FILTERS[category]
                    values = rolling_values(
                        Flight.objects.filter(user_id=owner_id).filter(scope),
                        Imported.objects.filter(user_id=owner_id).filter(scope), as_of,
                    )
                    if not dry_run:
                        model.objects.filter(pk=summary.pk).update(**values)
                    counts[label] += 1
    return counts
