from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from flights.models import Aircraft, Flight, Imported, Regs, TailNumber
from flights.signal_extra import refresh_operating_rule_summaries


class OperatingRuleSummaryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='rules-summary')
        self.aircraft = Aircraft.objects.create(
            user=self.user, aircraft_type='C172', aircraft_category='A', aircraft_class='SEL')
        self.tails = {
            rule: TailNumber.objects.create(user=self.user, aircraft=self.aircraft,
                                           registration=f'N{rule}', **{f'is_{rule}': True})
            for rule in ('91', '121', '135')
        }

    def flight(self, rule, role, duration):
        return Flight.objects.create(user=self.user, aircraft_type=self.aircraft,
                                     registration=self.tails[rule], date=date(2026, 1, 1),
                                     route='IAH-LAX', duration=duration, **{role: True})

    def values(self, rule):
        row = Regs.objects.get(user=self.user, reg_type=rule)
        return row.pilot_in_command, row.second_in_command

    def test_each_rule_combines_only_its_own_flights_and_imported_balances(self):
        for index, rule in enumerate(('91', '121', '135'), start=1):
            self.flight(rule, 'pilot_in_command', Decimal(index))
            self.flight(rule, 'second_in_command', Decimal(index) + Decimal('.5'))
            Imported.objects.create(user=self.user, aircraft_type=self.aircraft,
                                    pilot_in_command=10 * index, second_in_command=20 * index,
                                    **{f'is_{rule}': True})
        for index, rule in enumerate(('91', '121', '135'), start=1):
            self.assertEqual(self.values(rule), (Decimal(11 * index), Decimal(21 * index) + Decimal('.5')))

    def test_part_91_sic_does_not_require_any_pic_flights(self):
        self.flight('91', 'second_in_command', '2.5')
        self.assertEqual(self.values('91'), (0, Decimal('2.5')))

    def test_imported_only_balances_survive_for_all_rules(self):
        for rule in ('91', '121', '135'):
            Imported.objects.create(user=self.user, aircraft_type=self.aircraft,
                                    pilot_in_command='12.3', second_in_command='45.6',
                                    **{f'is_{rule}': True})
            self.assertEqual(self.values(rule), (Decimal('12.3'), Decimal('45.6')))

    def test_part_121_sic_is_persisted_after_update_and_delete(self):
        flight = self.flight('121', 'second_in_command', '2.5')
        self.assertEqual(self.values('121'), (0, Decimal('2.5')))
        flight.duration = Decimal('3.5')
        flight.save()
        self.assertEqual(self.values('121'), (0, Decimal('3.5')))
        flight.delete()
        self.assertEqual(self.values('121'), (0, 0))

    def test_rule_change_moves_hours_between_summaries(self):
        self.flight('135', 'pilot_in_command', '2.5')
        tail = self.tails['135']
        tail.is_135, tail.is_91 = False, True
        tail.save()
        self.assertEqual(self.values('135'), (0, 0))
        self.assertEqual(self.values('91'), (Decimal('2.5'), 0))

    def test_other_users_and_null_hours_do_not_affect_totals(self):
        other = get_user_model().objects.create_user(username='other-rules')
        Regs.objects.create(user=other, reg_type='91', pilot_in_command='99.0')
        self.flight('91', 'pilot_in_command', None)
        Imported.objects.create(user=self.user, aircraft_type=self.aircraft,
                                is_91=True, pilot_in_command=None, second_in_command=None)
        self.assertEqual(self.values('91'), (0, 0))
        self.assertEqual(Regs.objects.get(user=other, reg_type='91').pilot_in_command, Decimal('99'))

    def test_refresh_uses_two_aggregate_queries_and_one_batched_update(self):
        with CaptureQueriesContext(connection) as queries:
            refresh_operating_rule_summaries(self.user.pk)
        selects = [q['sql'] for q in queries if q['sql'].startswith('SELECT')]
        self.assertEqual(sum('SUM(' in sql for sql in selects), 2)
        self.assertFalse(any('"flights_flight"."id"' in sql for sql in selects))
        self.assertEqual(sum(q['sql'].startswith('UPDATE "flights_regs"') for q in queries), 1)

    def test_failed_refresh_rolls_back_created_summary_rows(self):
        Regs.objects.filter(user=self.user).delete()
        from django.db.models.query import QuerySet
        with patch.object(QuerySet, 'bulk_update', side_effect=RuntimeError('write failed')):
            with self.assertRaisesRegex(RuntimeError, 'write failed'):
                refresh_operating_rule_summaries(self.user.pk)
        self.assertFalse(Regs.objects.filter(user=self.user).exists())
