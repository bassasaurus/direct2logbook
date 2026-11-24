"""Reconcile every stored summary number against independently summed source rows."""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from flights.models import Aircraft, Endorsement, Flight, Imported, Power, Regs, Stat, TailNumber, Total, Weight


ZERO = Decimal('0')
ROLE_FIELDS = ('pilot_in_command', 'second_in_command', 'cross_country', 'instructor', 'dual', 'solo', 'simulator')
VALUE_FIELDS = ('night', 'instrument', 'simulated_instrument', 'landings_day', 'landings_night')
CLASSES = {'ASEL': ('A', 'SEL'), 'AMEL': ('A', 'MEL'), 'ASES': ('A', 'SES'),
           'AMES': ('A', 'MES'), 'HELO': ('R', 'HELO'), 'GYRO': ('R', 'GYRO')}
WEIGHTS = {'Super': 'superr', 'Heavy': 'heavy', 'Large': 'large', 'Medium': 'medium', 'Small': 'small', 'LSA': 'light_sport'}
ENDORSEMENTS = {'Simple': 'simple', 'Complex': 'compleks', 'High Performance': 'high_performance',
                'Tailwheel': 'tailwheel', 'Type Rating': 'requires_type'}


def number(value):
    return ZERO if value is None else Decimal(str(value))


def summed(rows, field):
    return sum((number(getattr(row, field)) for row in rows), ZERO)


class SummarySourceTotalsTests(TestCase):
    today = date(2026, 11, 19)

    def setUp(self):
        clock = patch('flights.rolling_stats.timezone.localdate', return_value=self.today)
        clock.start()
        self.addCleanup(clock.stop)
        self.user = get_user_model().objects.create_user(username='source-totals')
        self.other = get_user_model().objects.create_user(username='unrelated-totals')
        for index, (category, klass) in enumerate(CLASSES.values()):
            aircraft = Aircraft.objects.create(
                user=self.user, aircraft_type=f'T{index}', aircraft_category=category, aircraft_class=klass,
                turbine=index % 2 == 0, piston=index % 2 == 1,
                **{field: index == offset for offset, field in enumerate(WEIGHTS.values())},
                **{field: index % 2 == offset % 2 for offset, field in enumerate(ENDORSEMENTS.values())})
            rule = ('91', '121', '135')[index % 3]
            tail = TailNumber.objects.create(user=self.user, aircraft=aircraft, registration=f'N{index+100}', **{f'is_{rule}': True})
            Imported.objects.create(user=self.user, aircraft_type=aircraft, **{f'is_{rule}': True},
                                    total_time='10.1', pilot_in_command='5.1', second_in_command='3.2',
                                    cross_country='4.3', instructor='1.1', dual='1.2', solo='0.3', simulator='0.4',
                                    night='2.1', instrument='1.3', simulated_instrument='0.2',
                                    landings_day=7, landings_night=3, last_flown=date(2020, 1, 1))
            # Boundary days, expired history, and a future record exercise date scopes.
            for offset, age in enumerate((0, 30, 31, 60, 61, 90, 91, 180, 181, 365, 366, 730, 731, -1)):
                Flight.objects.create(
                    user=self.user, aircraft_type=aircraft, registration=tail,
                    date=self.today - timedelta(days=age), duration='0.3', route='IAH-LAX',
                    pilot_in_command=offset % 2 == 0, second_in_command=offset % 2 == 1,
                    cross_country=offset % 3 == 0, instructor=offset % 4 == 0,
                    dual=offset % 4 == 1, solo=offset % 4 == 2, simulator=offset % 4 == 3,
                    night='0.1' if offset % 2 else None, instrument='0.2',
                    simulated_instrument='0.1', landings_day=1, landings_night=offset % 2)
        # Foreign-owner data must never leak into any of these summaries.
        aircraft = Aircraft.objects.create(user=self.other, aircraft_type='T0', aircraft_category='A', aircraft_class='SEL')
        Imported.objects.create(user=self.other, aircraft_type=aircraft, total_time='999', is_91=True, pilot_in_command='999')

    def sources(self):
        return (list(Flight.objects.filter(user=self.user).select_related('aircraft_type', 'registration')),
                list(Imported.objects.filter(user=self.user).select_related('aircraft_type')))

    def assert_lifetime_and_recency(self, summary, flights, imported):
        sessions = flights
        flights = [row for row in sessions if not row.simulator]
        expected = {'total_time': summed(flights, 'duration') + summed(imported, 'total_time')}
        for field in ROLE_FIELDS:
            expected[field] = summed([row for row in (sessions if field == 'simulator' else flights) if getattr(row, field)], 'duration') + summed(imported, field)
        for field in VALUE_FIELDS:
            expected[field] = summed(flights, field) + summed(imported, field)
        if isinstance(summary, Total):
            expected['landings_total'] = expected['landings_day'] + expected['landings_night']
        for field, days in (('last_30', 30), ('last_60', 60), ('last_90', 90), ('last_180', 180), ('last_yr', 365), ('last_2yr', 730)):
            expected[field] = summed([row for row in flights if self.today - timedelta(days=days) <= row.date <= self.today], 'duration')
        expected['ytd'] = summed([row for row in flights if date(self.today.year, 1, 1) <= row.date <= self.today], 'duration')
        dates = [row.date for row in flights if row.date <= self.today]
        dates += [row.last_flown for row in imported if row.last_flown and row.last_flown <= self.today]
        expected['last_flown'] = max(dates, default=None)
        for field, value in expected.items():
            with self.subTest(table=type(summary).__name__, row=str(summary), field=field):
                self.assertEqual(getattr(summary, field), value)

    def assert_all_summaries(self):
        flights, imported = self.sources()
        totals = {row.total: row for row in Total.objects.filter(user=self.user)}
        self.assertEqual(set(totals), {'All', *CLASSES})
        for category, summary in totals.items():
            matches = lambda row: category == 'All' or (row.aircraft_type.aircraft_category, row.aircraft_type.aircraft_class) == CLASSES[category]
            self.assert_lifetime_and_recency(summary, list(filter(matches, flights)), list(filter(matches, imported)))
        stats = list(Stat.objects.filter(user=self.user))
        self.assertEqual(len(stats), 6)
        for summary in stats:
            self.assert_lifetime_and_recency(summary,
                [row for row in flights if row.aircraft_type.aircraft_type == summary.aircraft_type],
                [row for row in imported if row.aircraft_type.aircraft_type == summary.aircraft_type])
        flights = [row for row in flights if not row.simulator]
        for summary in Regs.objects.filter(user=self.user):
            for role in ('pilot_in_command', 'second_in_command'):
                expected = summed([row for row in flights if getattr(row.registration, f'is_{summary.reg_type}') and getattr(row, role)], 'duration')
                expected += summed([row for row in imported if getattr(row, f'is_{summary.reg_type}')], role)
                with self.subTest(table='Regs', rule=summary.reg_type, field=role):
                    self.assertEqual(getattr(summary, role), expected)
        for model, mapping, label in ((Weight, WEIGHTS, 'weight'), (Endorsement, ENDORSEMENTS, 'endorsement')):
            summaries = list(model.objects.filter(user=self.user))
            self.assertEqual({getattr(row, label) for row in summaries}, set(mapping))
            for summary in summaries:
                field = mapping[getattr(summary, label)]
                expected = summed([row for row in flights if getattr(row.aircraft_type, field)], 'duration')
                expected += summed([row for row in imported if getattr(row.aircraft_type, field)], 'total_time')
                with self.subTest(table=model.__name__, field=field):
                    self.assertEqual(summary.total, expected)
        for summary in Power.objects.filter(user=self.user):
            roles = ('pilot_in_command', 'second_in_command') if summary.role == 'Total' else (('pilot_in_command',) if summary.role == 'PIC' else ('second_in_command',))
            for engine in ('turbine', 'piston'):
                expected = sum((summed([row for row in flights if getattr(row.aircraft_type, engine) and getattr(row, role)], 'duration') +
                                summed([row for row in imported if getattr(row.aircraft_type, engine)], role) for role in roles), ZERO)
                with self.subTest(table='Power', role=summary.role, engine=engine):
                    self.assertEqual(getattr(summary, engine), expected)

    def test_all_summary_numbers_match_database_sources(self):
        self.assert_all_summaries()

    def test_summaries_remain_correct_after_source_edits_and_deletions(self):
        flight = Flight.objects.filter(user=self.user).first()
        flight.duration = Decimal('1.7')
        flight.night = Decimal('0.4')
        flight.landings_day = 4
        flight.save()
        Flight.objects.filter(user=self.user).last().delete()
        imported = Imported.objects.filter(user=self.user).first()
        imported.pilot_in_command = Decimal('7.3')
        imported.landings_night = 5
        imported.save()
        self.assert_all_summaries()

    def test_removing_all_source_records_clears_numeric_summaries(self):
        Flight.objects.filter(user=self.user).delete()
        Imported.objects.filter(user=self.user).delete()
        self.assertFalse(Stat.objects.filter(user=self.user).exists())
        self.assertFalse(Weight.objects.filter(user=self.user).exists())
        self.assertFalse(Endorsement.objects.filter(user=self.user).exists())
        for row in Total.objects.filter(user=self.user):
            self.assert_lifetime_and_recency(row, [], [])
        for row in Regs.objects.filter(user=self.user):
            self.assertEqual((row.pilot_in_command, row.second_in_command), (0, 0))
        for row in Power.objects.filter(user=self.user):
            with self.subTest(role=row.role):
                self.assertEqual((row.turbine, row.piston), (0, 0))

    def test_simulator_migration_rebuilds_every_summary_without_changing_sources(self):
        from importlib import import_module
        from types import SimpleNamespace
        from django.apps import apps
        from django.db import connection
        migration = import_module('flights.migrations.0074_separate_simulator_summaries')
        schema = SimpleNamespace(connection=connection)
        models = (Total, Stat, Regs, Power, Weight, Endorsement)
        before_sources = {model.__name__: list(model.objects.order_by('pk').values())
                          for model in (Flight, Imported)}
        foreign = {model.__name__: list(model.objects.filter(user=self.other).order_by('pk').values())
                   for model in models}
        # Recreate the old inclusion of simulator duration, then upgrade it.
        migration.restore(apps, schema)
        migration.rebuild(apps, schema)
        self.assert_all_summaries()
        once = {model.__name__: list(model.objects.order_by('pk').values()) for model in models}
        migration.rebuild(apps, schema)
        self.assertEqual(once, {model.__name__: list(model.objects.order_by('pk').values()) for model in models})
        for model in (Flight, Imported):
            self.assertEqual(before_sources[model.__name__], list(model.objects.order_by('pk').values()))
        for model in models:
            self.assertEqual(foreign[model.__name__], list(model.objects.filter(user=self.other).order_by('pk').values()))
