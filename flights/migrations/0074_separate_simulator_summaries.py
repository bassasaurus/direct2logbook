"""Rebuild affected cached summaries; never rewrite source flight/import records."""
from datetime import date, timedelta
from decimal import Decimal

from django.db import migrations
from django.db.models import Max, Q, Sum
from django.utils import timezone


CATEGORIES = {
    'ASEL': ('A', 'SEL'), 'AMEL': ('A', 'MEL'), 'ASES': ('A', 'SES'),
    'AMES': ('A', 'MES'), 'HELO': ('R', 'HELO'), 'GYRO': ('R', 'GYRO'),
}
ROLES = ('pilot_in_command', 'second_in_command', 'cross_country', 'instructor', 'dual', 'solo')
VALUES = ('night', 'instrument', 'simulated_instrument', 'landings_day', 'landings_night')
WINDOWS = {'last_30': 30, 'last_60': 60, 'last_90': 90, 'last_180': 180, 'last_yr': 365, 'last_2yr': 730}
WEIGHTS = {'Super': 'superr', 'Heavy': 'heavy', 'Large': 'large', 'Medium': 'medium', 'Small': 'small', 'LSA': 'light_sport'}
ENDORSEMENTS = {'Simple': 'simple', 'Complex': 'compleks', 'High Performance': 'high_performance', 'Tailwheel': 'tailwheel', 'Type Rating': 'requires_type'}


def rebuild(apps, schema_editor, separate=True):
    using = schema_editor.connection.alias
    Flight = apps.get_model('flights', 'Flight')
    Imported = apps.get_model('flights', 'Imported')
    today = timezone.localdate()

    def summed(rows, name):
        return rows.aggregate(value=Sum(name))['value'] or Decimal('0')

    for owner in Flight.objects.using(using).filter(simulator=True).order_by().values_list('user_id', flat=True).distinct():
        sessions = Flight.objects.using(using).filter(user_id=owner)
        flying = sessions.exclude(simulator=True) if separate else sessions
        balances = Imported.objects.using(using).filter(user_id=owner)
        # Stat stores a type name rather than an FK. Rebuild its keys from sources
        # so a previously renamed aircraft cannot lose its per-type summary.
        Stat = apps.get_model('flights', 'Stat')
        types = set(sessions.values_list('aircraft_type__aircraft_type', flat=True))
        types.update(balances.values_list('aircraft_type__aircraft_type', flat=True))
        Stat.objects.using(using).filter(user_id=owner).exclude(aircraft_type__in=types).delete()
        for aircraft_type in sorted(types):
            Stat.objects.using(using).get_or_create(user_id=owner, aircraft_type=aircraft_type)
        for name in ('Total', 'Stat'):
            Model = apps.get_model('flights', name)
            for row in Model.objects.using(using).filter(user_id=owner):
                scope = Q(aircraft_type__aircraft_type=row.aircraft_type) if name == 'Stat' else Q()
                if name == 'Total':
                    key = row.total.strip().upper()
                    if key != 'ALL':
                        if key not in CATEGORIES:
                            continue
                        category, aircraft_class = CATEGORIES[key]
                        scope = Q(aircraft_type__aircraft_category=category, aircraft_type__aircraft_class=aircraft_class)
                flights, imported = flying.filter(scope), balances.filter(scope)
                values = {'total_time': summed(flights, 'duration') + summed(imported, 'total_time')}
                values.update({role: summed(flights.filter(**{role: True}), 'duration') + summed(imported, role) for role in ROLES})
                values.update({field: summed(flights, field) + summed(imported, field) for field in VALUES})
                values['simulator'] = summed(sessions.filter(scope, simulator=True), 'duration') + summed(imported, 'simulator')
                # Keep existing historical snapshot balances intact.
                if name == 'Total':
                    values['landings_total'] = values['landings_day'] + values['landings_night']
                for field, days in WINDOWS.items():
                    values[field] = summed(flights.filter(date__range=(today - timedelta(days=days), today)), 'duration')
                values['ytd'] = summed(flights.filter(date__range=(date(today.year, 1, 1), today)), 'duration')
                last_dates = [flights.filter(date__lte=today).aggregate(last=Max('date'))['last'],
                              imported.filter(last_flown__lte=today).aggregate(last=Max('last_flown'))['last']]
                values['last_flown'] = max((item for item in last_dates if item), default=None)
                Model.objects.using(using).filter(pk=row.pk).update(**values)
        for name, labels, field in (('Weight', WEIGHTS, 'weight'), ('Endorsement', ENDORSEMENTS, 'endorsement')):
            Model = apps.get_model('flights', name)
            for row in Model.objects.using(using).filter(user_id=owner):
                flag = labels.get(getattr(row, field))
                if flag:
                    scope = {f'aircraft_type__{flag}': True}
                    Model.objects.using(using).filter(pk=row.pk).update(total=summed(flying.filter(**scope), 'duration') + summed(balances.filter(**scope), 'total_time'))
        Regs = apps.get_model('flights', 'Regs')
        for row in Regs.objects.using(using).filter(user_id=owner):
            scope = {f'registration__is_{row.reg_type}': True}
            values = {role: summed(flying.filter(**scope, **{role: True}), 'duration') + summed(balances.filter(**{f'is_{row.reg_type}': True}), role) for role in ROLES[:2]}
            Regs.objects.using(using).filter(pk=row.pk).update(**values)
        Power = apps.get_model('flights', 'Power')
        for row in Power.objects.using(using).filter(user_id=owner):
            roles = ROLES[:2] if row.role == 'Total' else (('pilot_in_command',) if row.role == 'PIC' else ('second_in_command',))
            values = {engine: sum((summed(flying.filter(**{f'aircraft_type__{engine}': True, role: True}), 'duration') + summed(balances.filter(**{f'aircraft_type__{engine}': True}), role) for role in roles), Decimal('0')) for engine in ('turbine', 'piston')}
            Power.objects.using(using).filter(pk=row.pk).update(**values)


def restore(apps, schema_editor):
    rebuild(apps, schema_editor, separate=False)


class Migration(migrations.Migration):
    dependencies = [('flights', '0073_simulator_devices')]
    operations = [migrations.RunPython(rebuild, restore)]
