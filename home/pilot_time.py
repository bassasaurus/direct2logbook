"""Account-scoped Section III figures shared by web and mobile.

Individual simulator sessions never enter aircraft hours or flight counts.
Imported balances supply only the quantities actually stored in those balances.
"""
from decimal import Decimal
from django.db.models import Count, Q, Sum
from flights.aircraft_classification import SUMMARY_CLASSIFICATIONS, summary_key
from flights.models import Aircraft, Flight, Imported
from .iacra import COLUMNS, device_totals, device_class_totals

CATEGORY_LABELS = {'A': 'Airplanes', 'R': 'Rotorcraft', 'PL': 'Powered Lift', 'GL': 'Gliders', 'LTA': 'Lighter-Than-Air'}
SUMMARY_LABELS = {'GL': 'Glider', 'PL': 'Powered-Lift', 'BALLOON': 'Balloon', 'AIRSHIP': 'Airship',
                  'HELO': 'Helicopter', 'GYRO': 'Gyroplane'}
SHADED = {'GL': (6, 7, 8, 10, 11, 12, 13, 14, 15)}
COUNT_CELLS = (11, 14, 15)
ZERO = Decimal('0.0')
BASIC_IMPORTS = {0: 'total_time', 1: 'dual', 2: 'solo', 3: 'pilot_in_command',
                 4: 'second_in_command', 9: 'instrument', 11: 'landings_night'}


def source_groups(user):
    annotations = dict(total=Sum('duration'), instruction=Sum('duration', filter=Q(dual=True)),
        solo=Sum('duration', filter=Q(solo=True)), pic=Sum('duration', filter=Q(pilot_in_command=True)),
        sic=Sum('duration', filter=Q(second_in_command=True)),
        xc_dual=Sum('duration', filter=Q(cross_country=True, dual=True)),
        xc_solo=Sum('duration', filter=Q(cross_country=True, solo=True)),
        xc_pic=Sum('duration', filter=Q(cross_country=True, pilot_in_command=True)),
        xc_sic=Sum('duration', filter=Q(cross_country=True, second_in_command=True)),
        # Aircraft instrument time includes actual conditions and hood time.
        # Coalesce each sum independently so a blank field cannot erase the other.
        instrument=Sum('instrument', default=ZERO) + Sum('simulated_instrument', default=ZERO),
        night_dual=Sum('night', filter=Q(dual=True)),
        landings=Sum('landings_night'), night_pic=Sum('night', filter=Q(pilot_in_command=True)),
        night_sic=Sum('night', filter=Q(second_in_command=True)),
        night_crew=Sum('night', filter=Q(pilot_in_command=True) | Q(second_in_command=True)),
        landings_pic=Sum('landings_night', filter=Q(pilot_in_command=True)),
        landings_sic=Sum('landings_night', filter=Q(second_in_command=True)),
        flights=Count('pk'), flights_pic=Count('pk', filter=Q(pilot_in_command=True)),
        flights_dual=Count('pk', filter=Q(dual=True)),
        aerotow=Count('pk', filter=Q(launch_method='AEROTOW')),
        ground=Count('pk', filter=Q(launch_method='GROUND')),
        self_launch=Count('pk', filter=Q(launch_method='SELF')))
    fields = ('aircraft_type__aircraft_category', 'aircraft_type__aircraft_class')
    flights = list(Flight.objects.filter(user=user).exclude(simulator=True).order_by().values(*fields).annotate(**{'pt_' + key: value for key, value in annotations.items()}))
    imports = list(Imported.objects.filter(user=user).order_by().values(*fields).annotate(**{
        'pt_' + field: Sum(field) for field in set(BASIC_IMPORTS.values()) | {'night', 'cross_country', 'simulator'}}))
    return tuple([{key.removeprefix('pt_'): value for key, value in row.items()} for row in rows]
                 for rows in (flights, imports))


def pilot_time_report(user):
    flights, imports = source_groups(user)
    present = set(Aircraft.objects.filter(user=user).values_list('aircraft_category', 'aircraft_class'))
    present.update((row['aircraft_type__aircraft_category'], row['aircraft_type__aircraft_class']) for row in flights + imports)
    categories = {category for category, _ in present}
    category_values = {code: [ZERO] * len(COLUMNS) for code in categories if code in CATEGORY_LABELS}
    class_values = {key: [ZERO] * len(COLUMNS) for key, pair in SUMMARY_CLASSIFICATIONS.items() if pair in present}
    counts = {code: dict(flights=0, pic=0, dual=0, aerotow=0, ground=0, self_launch=0)
              for code in ('GL', 'LTA') if code in categories}
    metrics = ('total', 'instruction', 'solo', 'pic', 'sic', 'xc_dual', 'xc_solo', 'xc_pic', 'xc_sic',
               'instrument', 'night_dual', 'landings', 'night_pic', 'night_sic', 'landings_pic', 'landings_sic')
    for row in flights + imports:
        code, klass = row['aircraft_type__aircraft_category'], row['aircraft_type__aircraft_class']
        if code not in category_values:
            continue
        key = summary_key(code, klass)
        targets = [category_values[code]] + ([class_values[key]] if key in class_values else [])
        is_flight = 'flights' in row
        for target in targets:
            for i in range(len(COLUMNS)):
                field = metrics[i] if is_flight else BASIC_IMPORTS.get(i)
                if field and target[i] is not None:
                    target[i] += row[field] or ZERO
            if not is_flight:
                # Aggregate imports lack joint role/XC/night figures. Do not invent them.
                unknown = (() if not row['cross_country'] else (5, 6, 7, 8))
                unknown += (() if not row['night'] else (10, 12, 13))
                unknown += (() if not row['landings_night'] else (14, 15))
                for i in unknown:
                    target[i] = None
        if is_flight and code in counts:
            for name, source in (('flights', 'flights'), ('pic', 'flights_pic'), ('dual', 'flights_dual'),
                                 ('aerotow', 'aerotow'), ('ground', 'ground'), ('self_launch', 'self_launch')):
                counts[code][name] += row[source]

    def cells(values, shaded=()):
        return [dict(label=label, value=values[i], shaded=i in shaded, count=i in COUNT_CELLS)
                for i, label in enumerate(COLUMNS)]

    rows = [dict(code=code, label=CATEGORY_LABELS[code], cells=cells(category_values[code], SHADED.get(code, ())))
            for code in CATEGORY_LABELS if code in category_values]
    devices = device_totals(user)
    for kind in ('FFS', 'FTD', 'ATD'):
        if kind in devices:
            shaded = (2, 3, 4, 5, 6, 7, 8) + (() if kind == 'FFS' else (11, 12, 13, 14, 15))
            rows.append(dict(code=kind, label=kind, cells=cells(devices[kind], shaded)))
    classes = [dict(code=key, label=SUMMARY_LABELS.get(key, key), category=pair[0],
                    total=class_values[key][0], pic=class_values[key][3], sic=class_values[key][4], instruction=class_values[key][1])
               for key, pair in SUMMARY_CLASSIFICATIONS.items() if key in class_values]
    launches = [dict(code=code, label=CATEGORY_LABELS[code], **values) for code, values in counts.items()]
    return dict(rows=rows, classes=classes, launches=launches,
                devices=[row for row in device_class_totals(user) if row['type'] in devices],
                night_crew={code: sum((row['night_crew'] or ZERO for row in flights if row['aircraft_type__aircraft_category'] == code), ZERO) for code in ('A', 'R')},
                note='Flight and launch counts use individual aircraft flight records only. Imported hour balances do not add counts. A dash means the recorded information cannot supply that value. Unclassified simulator sessions remain in Simulator totals.')


def report_context(report):
    """Keep the dashboard's established currency/template names available."""
    context = {'iacra_rows': report['rows'], 'iacra_classes': report['classes'],
               'iacra_launches': report['launches'], 'iacra_device_classes': report['devices'],
               'iacra_note': report['note']}
    suffixes = ('total', 'dual', 'solo', 'pic', 'sic', 'xc_dual', 'xc_solo', 'xc_pic', 'xc_sic',
                'ifr', 'night_dual', 'ldg_night', 'night_pic', 'night_sic', 'night_ldg_pic', 'night_ldg_sic')
    for code, prefix in (('A', 'airplane'), ('R', 'rotorcraft')):
        row = next((row for row in report['rows'] if row['code'] == code), None)
        values = [cell['value'] for cell in row['cells']] if row else [ZERO] * len(COLUMNS)
        context.update({prefix + '_' + suffix: value for suffix, value in zip(suffixes, values)})
        # This context figure is not an FAA cell: keep its no-double-counting semantics.
        context[prefix + '_night_pic_sic'] = report['night_crew'][code]
    # The web IACRA tab mirrors the complete FAA form. Compact summaries and
    # the mobile report still omit categories/classes absent from the account.
    from copy import deepcopy
    from .iacra import iacra_tables
    by_code = {row['code']: row for row in report['rows']}
    form_rows = []
    for code, skeleton in zip(('A', 'R', 'PL', 'GL', 'LTA', 'FFS', 'FTD', 'ATD'), iacra_tables({})['iacra_rows']):
        if code in by_code:
            form_rows.append(deepcopy(by_code[code]))
        else:
            skeleton['code'] = code
            for cell in skeleton['cells']:
                cell['value'] = None if cell['shaded'] else 0 if cell['count'] else ZERO
            form_rows.append(skeleton)
    context['iacra_rows'] = form_rows
    classes = {row['code']: row for row in report['classes']}
    context['iacra_airplane_classes'] = [dict(label=label,
        **{field: classes.get(code, {}).get(field, ZERO) for field in ('pic', 'sic', 'instruction')})
        for code, label in (('ASEL', 'SEL'), ('AMEL', 'MEL'), ('ASES', 'SES'), ('AMES', 'MES'))]
    for code in ('HELO', 'GYRO', 'BALLOON', 'AIRSHIP'):
        context['iacra_' + code.lower() + '_total'] = classes.get(code, {}).get('total', ZERO)
    counts = {row['code']: row for row in report['launches']}
    context['iacra_launches'] = [counts.get(code, dict(code=code, label=CATEGORY_LABELS[code],
        flights=0, pic=0, dual=0, aerotow=0, ground=0, self_launch=0)) for code in ('GL', 'LTA')]
    devices = {row['type']: row for row in report['devices']}
    context['iacra_device_classes'] = [devices.get(kind, dict(type=kind, se=ZERO, me=ZERO, helicopter=ZERO))
                                       for kind in ('FFS', 'FTD', 'ATD')]
    return context
