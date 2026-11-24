"""Standard Part 61 instrument-airplane device credit under 61.65(h)-(j).

This is a logged-data estimate, not a determination of certificate eligibility.
Part 141/142 course-specific allowances are deliberately not inferred.
"""
from decimal import Decimal
from django.utils import timezone
from flights.models import Flight

LIMITS = {'FFS': Decimal('20.0'), 'FTD': Decimal('20.0'),
          'BATD': Decimal('10.0'), 'AATD': Decimal('20.0')}
ZERO = Decimal('0.0')


def instrument_airplane_device_credit(user):
    logged = dict.fromkeys(LIMITS, ZERO)
    eligible = dict.fromkeys(LIMITS, ZERO)
    unclassified = ZERO
    sessions = Flight.objects.filter(user=user, simulator=True, date__lte=timezone.localdate(),
        aircraft_type__aircraft_category='A').values('device_type', 'atd_type', 'device_id',
            'instrument_credit_eligible', 'dual', 'duration', 'simulated_instrument')
    for item in sessions:
        hours = min(max(item['simulated_instrument'] or ZERO, ZERO), max(item['duration'] or ZERO, ZERO))
        kind = item['atd_type'] if item['device_type'] == 'ATD' else item['device_type']
        if kind not in LIMITS:
            unclassified += hours
            continue
        logged[kind] += hours
        if item['instrument_credit_eligible'] and item['dual'] and item['device_id'].strip():
            eligible[kind] += hours
    within_caps = {kind: min(eligible[kind], limit) for kind, limit in LIMITS.items()}
    credit = min(Decimal('20.0'), sum(within_caps.values(), ZERO))
    return {
        'title': 'Instrument–Airplane Device Credit',
        'basis': 'Standard Part 61 — 14 CFR 61.65(h)–(j)',
        'rows': [{'type': kind, 'logged': logged[kind], 'eligible': eligible[kind],
                  'limit': limit, 'within_type_limit': within_caps[kind]} for kind, limit in LIMITS.items()],
        'device_credit': credit, 'combined_limit': Decimal('20.0'),
        'unclassified_instrument': unclassified,
        'note': 'Based on logged instrument time marked as approved training with an authorized instructor. Verify device approval and training records. Part 141/142 course-specific credit is not evaluated.',
    }
