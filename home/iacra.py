"""Presentation mapping for Section III of FAA Form 8710-1 (03/26).

Use existing dashboard figures without inventing aircraft categories or device
qualifications. Night landing counts also represent takeoffs by user convention.
"""
COLUMNS = (
    'Total', 'Instruction Received', 'Solo', 'PIC', 'SIC',
    'Cross Country Instruction Received', 'Cross Country Solo',
    'Cross Country PIC', 'Cross Country SIC', 'Instrument',
    'Night Instruction Received', 'Night Take-Off/Landing',
    'Night PIC', 'Night SIC', 'Night Take-Off/Landing PIC', 'Night Take-Off/Landing SIC',
)


def iacra_tables(context):
    def category(label, prefix, total_prefix):
        keys = (
            total_prefix + '_total', total_prefix + '_dual', total_prefix + '_solo',
            total_prefix + '_pic', total_prefix + '_sic', prefix + '_xc_dual',
            prefix + '_xc_solo', prefix + '_xc_pic', prefix + '_xc_sic',
            total_prefix + '_ifr', prefix + '_night_dual', total_prefix + '_ldg_night',
            prefix + '_night_pic', prefix + '_night_sic', prefix + '_night_ldg_pic', prefix + '_night_ldg_sic',
        )
        return row(label, [context.get(key) if key else None for key in keys])

    def row(label, values=None, shaded=()):
        return {'label': label, 'cells': [
            {'value': value, 'label': column, 'shaded': index in shaded, 'count': index in (11, 14, 15)}
            for index, (column, value) in enumerate(zip(COLUMNS, values or [None] * len(COLUMNS)))
        ]}

    # Zero-based metric positions; these cells are shaded on the FAA form.
    device_shading = (2, 3, 4, 5, 6, 7, 8)
    rows = [
        category('Airplanes', 'airplane', 'airplane'),
        category('Rotorcraft', 'rotorcraft', 'rotor'),
        row('Powered Lift'),
        row('Gliders', shaded=(6, 7, 8, 10, 11, 12, 13, 14, 15)),
        row('Lighter-Than-Air'),
        row('FFS', context.get('iacra_devices', {}).get('FFS'), shaded=device_shading),
        row('FTD', context.get('iacra_devices', {}).get('FTD'), shaded=device_shading + (11, 12, 13, 14, 15)),
        row('ATD', context.get('iacra_devices', {}).get('ATD'), shaded=device_shading + (11, 12, 13, 14, 15)),
    ]
    return {
        'iacra_rows': rows,
        'iacra_device_classes': context.get('iacra_device_classes', []),
        'iacra_airplane_classes': [
            {'label': label, 'pic': context.get(prefix + '_pic'),
             'sic': context.get(prefix + '_sic'), 'instruction': context.get(prefix + '_dual')}
            for label, prefix in [('SEL', 'asel'), ('MEL', 'amel'), ('SES', 'ases'), ('MES', 'ames')]
        ],
    }


def device_totals(user):
    from django.db.models import Sum, Q
    from flights.models import Flight
    rows = Flight.objects.filter(user=user, simulator=True).values('device_type').annotate(
        total=Sum('duration'), instruction=Sum('duration', filter=Q(dual=True)),
        instrument=Sum('simulated_instrument'),
        night_instruction=Sum('night', filter=Q(dual=True)), landings=Sum('landings_night'),
        night_pic=Sum('night', filter=Q(pilot_in_command=True)),
        night_sic=Sum('night', filter=Q(second_in_command=True)),
        landings_pic=Sum('landings_night', filter=Q(pilot_in_command=True)),
        landings_sic=Sum('landings_night', filter=Q(second_in_command=True)))
    result = {}
    for item in rows:
        if item['device_type'] not in ('FFS', 'FTD', 'ATD'):
            continue  # Preserve legacy sessions without guessing their qualification.
        values = [None] * len(COLUMNS)
        for index, key in ((0, 'total'), (1, 'instruction'), (9, 'instrument'), (10, 'night_instruction'), (11, 'landings'), (12, 'night_pic'), (13, 'night_sic'), (14, 'landings_pic'), (15, 'landings_sic')):
            values[index] = item[key] or 0
        result[item['device_type']] = values
    return result


def device_class_totals(user):
    from django.db.models import Sum
    from flights.models import Flight
    groups = Flight.objects.filter(user=user, simulator=True, device_type__in=('FFS', 'FTD', 'ATD')).values(
        'device_type', 'aircraft_type__aircraft_category', 'aircraft_type__aircraft_class').annotate(total=Sum('duration'))
    totals = {kind: {'type': kind, 'se': None, 'me': None, 'helicopter': None} for kind in ('FFS', 'FTD', 'ATD')}
    for group in groups:
        category, aircraft_class = group['aircraft_type__aircraft_category'], group['aircraft_type__aircraft_class']
        key = ('se' if category == 'A' and aircraft_class in ('SEL', 'SES') else
               'me' if category == 'A' and aircraft_class in ('MEL', 'MES') else
               'helicopter' if category == 'R' and aircraft_class == 'HELO' else None)
        if key:
            row = totals[group['device_type']]
            row[key] = (row[key] or 0) + (group['total'] or 0)
    return list(totals.values())
