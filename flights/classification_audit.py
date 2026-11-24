"""Read-only baseline for the 8710 category/class expansion.

Deliberately does not call save hooks or production summary functions: the
comparison must independently count source records, not repeat cached totals.
"""
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal
import hashlib
import json

from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from flights.models import Aircraft, Endorsement, Flight, Imported, Power, Regs, Stat, TailNumber, Total, Weight
from flights.aircraft_classification import CLASSES_BY_CATEGORY, SUMMARY_CLASSIFICATIONS


CLASSES = SUMMARY_CLASSIFICATIONS
VALID_CLASSES = CLASSES_BY_CATEGORY
ROLES = ('pilot_in_command', 'second_in_command', 'cross_country', 'instructor', 'dual', 'solo')
VALUES = ('night', 'instrument', 'simulated_instrument', 'landings_day', 'landings_night')
WINDOWS = {'last_30': 30, 'last_60': 60, 'last_90': 90, 'last_180': 180, 'last_yr': 365, 'last_2yr': 730}
WEIGHTS = ('small', 'large', 'heavy', 'superr')
SOURCE_FIELDS = ('id', 'user_id', 'aircraft_type_id', 'date', 'registration_id', 'route',
                 'duration', 'simulator', 'device_type', 'device_id', 'atd_type',
                 'instrument_credit_eligible', 'hold') + ROLES + VALUES


def numeric(value):
    return Decimal(str(value)) if value is not None else Decimal('0')


def summed(rows, field):
    return sum((numeric(row[field]) for row in rows), Decimal('0'))


def source_totals(sessions, imported, as_of):
    flights = [row for row in sessions if not row['simulator']]
    result = {'total_time': summed(flights, 'duration') + summed(imported, 'total_time')}
    for field in ROLES:
        result[field] = summed([row for row in flights if row[field]], 'duration') + summed(imported, field)
    for field in VALUES:
        result[field] = summed(flights, field) + summed(imported, field)
    result['simulator'] = summed([row for row in sessions if row['simulator']], 'duration') + summed(imported, 'simulator')
    result['landings_total'] = result['landings_day'] + result['landings_night']
    for field, days in WINDOWS.items():
        result[field] = summed([row for row in flights if as_of - timedelta(days=days) <= row['date'] <= as_of], 'duration')
    result['ytd'] = summed([row for row in flights if date(as_of.year, 1, 1) <= row['date'] <= as_of], 'duration')
    dates = [row['date'] for row in flights if row['date'] <= as_of]
    dates += [row['last_flown'] for row in imported if row['last_flown'] and row['last_flown'] <= as_of]
    result['last_flown'] = max(dates, default=None)
    return result


def fingerprint(rows):
    digest = hashlib.sha256()
    for row in rows:
        digest.update(json.dumps(row, cls=DjangoJSONEncoder, sort_keys=True, separators=(',', ':')).encode())
        digest.update(b'\n')
    return digest.hexdigest()


def classification_baseline(database='default', user_id=None, as_of=None):
    """Return a JSON-serializable-in-Django report; perform SELECTs only.

    The command supplies a consistent PostgreSQL read-only transaction. No
    source rows are exported: fingerprints cover the listed fields, with IDs,
    classifications, flags and summary figures included for review.
    """
    as_of = as_of or timezone.localdate()
    sources, snapshots = {}, {}
    for model in (Aircraft, TailNumber, Flight, Imported, Total, Stat, Power, Regs, Weight, Endorsement):
        rows = model.objects.using(database).order_by('pk')
        if user_id is not None:
            rows = rows.filter(user_id=user_id)
        fields = SOURCE_FIELDS if model is Flight else tuple(field.attname for field in model._meta.concrete_fields)
        values = list(rows.values(*fields))
        sources[model.__name__] = values
        snapshots[model.__name__] = {'count': len(values), 'sha256': fingerprint(values), 'fields': fields}

    aircraft = {row['id']: row for row in sources['Aircraft']}
    # Resolve foreign-owner links too, without including them in this owner's
    # baseline. This permits an audit to report rather than crash on bad links.
    referenced = {row['aircraft_type_id'] for name in ('Flight', 'Imported') for row in sources[name]}
    missing = referenced - aircraft.keys()
    if missing:
        aircraft.update({row['id']: row for row in Aircraft.objects.using(database).filter(pk__in=missing).values()})
    issues = []
    by_aircraft, by_owner = defaultdict(lambda: defaultdict(list)), defaultdict(lambda: defaultdict(list))
    for name in ('Flight', 'Imported'):
        for row in sources[name]:
            by_aircraft[row['aircraft_type_id']][name].append(row)
            by_owner[row['user_id']][name].append(row)
            linked = aircraft.get(row['aircraft_type_id'])
            if not linked or linked['user_id'] != row['user_id']:
                issues.append({'kind': 'ownership', 'model': name, 'id': row['id'], 'user_id': row['user_id'],
                               'aircraft_id': row['aircraft_type_id']})
    tails = Counter(row['aircraft_id'] for row in sources['TailNumber'])
    aircraft_reports = []
    for row in sources['Aircraft']:
        category, klass = row['aircraft_category'], row['aircraft_class']
        findings = []
        if not category:
            findings.append('category_not_recorded')
        elif category not in VALID_CLASSES:
            findings.append('category_not_currently_supported')
        if not klass and VALID_CLASSES.get(category):
            findings.append('class_not_recorded')
        elif not klass and not category:
            findings.append('class_not_recorded')
        elif category in VALID_CLASSES and klass not in VALID_CLASSES[category]:
            if klass:
                findings.append('category_class_mismatch')
        engines = [name for name in ('piston', 'turbine', 'electric') if row[name]]
        weights = [name for name in WEIGHTS if row[name]]
        from flights.aircraft_characteristics import engine_required
        if engine_required(category, klass) and len(engines) != 1:
            findings.append('engine_not_recorded' if not engines else 'multiple_engines_selected')
        if len(weights) != 1:
            findings.append('weight_not_recorded' if not weights else 'multiple_weights_selected')
        flights, imported = by_aircraft[row['id']]['Flight'], by_aircraft[row['id']]['Imported']
        aircraft_reports.append({'id': row['id'], 'user_id': row['user_id'], 'aircraft_type': row['aircraft_type'],
            'category': category, 'class': klass, 'engines': engines, 'weights': weights, 'findings': findings,
            'counts': {'flights': sum(not item['simulator'] for item in flights),
                       'simulator_sessions': sum(bool(item['simulator']) for item in flights),
                       'imported_balances': len(imported), 'tailnumbers': tails[row['id']]},
            'source_totals': source_totals(flights, imported, as_of)})

    for name in ('Total', 'Stat'):
        for row in sources[name]:
            by_owner[row['user_id']][name].append(row)

    owner_reports = []
    for owner_id, owned in sorted(by_owner.items()):
        flights, imported = owned['Flight'], owned['Imported']

        def pair(item):
            linked = aircraft[item['aircraft_type_id']]
            return linked['aircraft_category'], linked['aircraft_class']

        observed_pairs = sorted({pair(item) for item in flights + imported})
        groups = []
        for category, klass in observed_pairs:
            groups.append({'category': category, 'class': klass, 'source_totals': source_totals(
                [item for item in flights if pair(item) == (category, klass)],
                [item for item in imported if pair(item) == (category, klass)], as_of)})

        for name, label in (('Total', 'total'), ('Stat', 'aircraft_type')):
            summaries = defaultdict(list)
            for row in owned[name]:
                key = row[label]
                if name == 'Total':
                    key = key.strip().upper()
                    key = 'All' if key == 'ALL' else key
                summaries[key].append(row)
            if name == 'Total':
                expected_keys = {'All'} if flights or imported else set()
                expected_keys.update(key for key, value in CLASSES.items() if value in observed_pairs)
            else:
                expected_keys = {aircraft[item['aircraft_type_id']]['aircraft_type'] for item in flights + imported}
            for key in sorted(expected_keys - summaries.keys()):
                issues.append({'kind': 'missing_summary', 'model': name, 'user_id': owner_id, 'group': key})
            for key, rows in summaries.items():
                if len(rows) > 1:
                    issues.append({'kind': 'duplicate_summary', 'model': name, 'user_id': owner_id,
                                   'group': key, 'ids': [row['id'] for row in rows]})
                if name == 'Total' and key != 'All' and key not in CLASSES:
                    issues.append({'kind': 'unsupported_summary', 'model': name, 'user_id': owner_id,
                                   'group': key, 'ids': [row['id'] for row in rows]})
                    continue

                def matches(item):
                    return ((key == 'All' or pair(item) == CLASSES[key]) if name == 'Total'
                            else aircraft[item['aircraft_type_id']]['aircraft_type'] == key)

                expected = source_totals(list(filter(matches, flights)), list(filter(matches, imported)), as_of)
                for row in rows:
                    for field, value in expected.items():
                        if field not in row:
                            continue  # Stat has no landings_total column.
                        actual = row[field] if field == 'last_flown' else numeric(row[field])
                        if actual != value:
                            issues.append({'kind': 'summary_mismatch', 'model': name, 'id': row['id'],
                                'user_id': owner_id, 'group': key, 'field': field,
                                'scope': 'rolling' if field in (*WINDOWS, 'ytd', 'last_flown') else 'lifetime',
                                'stored': row[field], 'expected': value})
        owner_reports.append({'user_id': owner_id, 'source_totals': source_totals(flights, imported, as_of),
                              'classification_groups': groups})
    return {'report_version': 1, 'created_at': timezone.now(), 'as_of': as_of,
        'database_alias': database, 'user_id': user_id, 'records_changed': False,
        'comparison_policy': {'null_numeric_equals_zero': True, 'imported_balances_in_rolling_windows': False,
                              'simulator_time_in_flight_totals': False, 'cutoff_inclusive': True},
        'snapshots': snapshots, 'aircraft': aircraft_reports, 'users': owner_reports,
        'stored_summaries': {name: sources[name] for name in ('Total', 'Stat', 'Power', 'Regs', 'Weight', 'Endorsement')},
        'issues': issues,
        'finding_counts': dict(Counter(finding for row in aircraft_reports for finding in row['findings'])),
        'issue_counts': dict(Counter(issue['kind'] for issue in issues)),
        'coverage': {'reconciled': ['Total', 'Stat'], 'snapshot_only': ['Power', 'Regs', 'Weight', 'Endorsement'],
                     'flight_fingerprint': 'Listed fields only; excludes remarks, map caches and error messages.'}}
