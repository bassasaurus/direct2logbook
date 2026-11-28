"""Logged simulator hours by training program; no course credit inferred."""
from decimal import Decimal
from django.db.models import Sum
from django.utils import timezone
from flights.models import Flight


def training_program_totals(user):
    rows = {key: {'program': key, 'label': label, 'total': Decimal('0.0'),
                  'ffs': Decimal('0.0'), 'ftd': Decimal('0.0'), 'atd': Decimal('0.0'), 'unclassified': Decimal('0.0')}
            for key, label in [('141', 'Part 141'), ('142', 'Part 142'), ('', 'Not specified')]}
    groups = Flight.objects.filter(user=user, simulator=True, date__lte=timezone.localdate()).order_by().values(
        'training_program', 'device_type').annotate(hours=Sum('duration'))
    for group in groups:
        row = rows[group['training_program']]
        hours = group['hours'] or Decimal('0.0')
        row['total'] += hours
        row[group['device_type'].lower() if group['device_type'] in ('FFS', 'FTD', 'ATD') else 'unclassified'] += hours
    return list(rows.values())
