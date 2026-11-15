from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

from flights.models import Aircraft, Endorsement, Flight, Power, Regs, Stat, TailNumber, Total, Weight
from flights.record_integrity import summary_integrity_issues

SUMMARY_KEYS = ((Stat, 'aircraft_type', 'A320'), (Total, 'total', 'All'),
                (Power, 'role', 'PIC'), (Regs, 'reg_type', '121'),
                (Endorsement, 'endorsement', 'Complex'), (Weight, 'weight', 'Heavy'))


class SummaryConstraintTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.other = get_user_model().objects.bulk_create([
            get_user_model()(username='summary-owner'), get_user_model()(username='summary-other')])

    def test_duplicate_keys_rejected_on_insert_and_update_without_changing_balances(self):
        for model, field, key in SUMMARY_KEYS:
            with self.subTest(model=model.__name__):
                first = model.objects.create(user=self.owner, **{field: key})
                before = model.objects.filter(pk=first.pk).values().get()
                with self.assertRaises(IntegrityError), transaction.atomic():
                    model.objects.bulk_create([model(user=self.owner, **{field: key})])
                second = model.objects.create(user=self.owner, **{field: 'Other'})
                with self.assertRaises(IntegrityError), transaction.atomic():
                    model.objects.filter(pk=second.pk).update(**{field: key})
                self.assertEqual(model.objects.filter(pk=first.pk).values().get(), before)
                model.objects.create(user=self.other, **{field: key})
                self.assertEqual(model.objects.filter(**{field: key}).count(), 2)
                found, created = model.objects.get_or_create(user=self.owner, **{field: key})
                self.assertFalse(created)
                self.assertEqual(found.pk, first.pk)
        self.assertEqual(summary_integrity_issues(apps, 'default'), [])

    def test_repeated_flight_writes_keep_one_summary_per_key_and_correct_totals(self):
        user = get_user_model().objects.create_user(username='summary-signals')
        aircraft = Aircraft.objects.create(user=user, aircraft_type='C172', aircraft_category='A',
            aircraft_class='SEL', piston=True, small=True, simple=True)
        tail = TailNumber.objects.create(user=user, aircraft=aircraft, registration='N123A', is_91=True)
        first = Flight.objects.create(user=user, aircraft_type=aircraft, registration=tail,
            route='KIAH-KLAX', date=date(2026, 1, 1), duration=Decimal('1.5'), pilot_in_command=True)
        first.duration = Decimal('2.5')
        first.save()
        second = Flight.objects.create(user=user, aircraft_type=aircraft, registration=tail,
            route='KIAH-KLAX', date=date(2026, 1, 2), duration=Decimal('1.0'), pilot_in_command=True)
        self.assertEqual(Total.objects.get(user=user, total='All').total_time, Decimal('3.5'))
        self.assertEqual(Stat.objects.get(user=user, aircraft_type='C172').total_time, Decimal('3.5'))
        first.delete()
        self.assertEqual(Total.objects.get(user=user, total='All').total_time, second.duration)
        self.assertEqual(Stat.objects.get(user=user, aircraft_type='C172').total_time, second.duration)
        self.assertEqual(summary_integrity_issues(apps, 'default'), [])


class SummaryConcurrencyTests(TransactionTestCase):
    def test_concurrent_get_or_create_returns_the_same_summary(self):
        user = get_user_model().objects.bulk_create([get_user_model()(username='summary-race')])[0]
        barrier = Barrier(2)

        def create():
            try:
                barrier.wait(timeout=10)
                row, created = Stat.objects.get_or_create(user_id=user.pk, aircraft_type='C172')
                return row.pk, created
            finally:
                connections['default'].close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: create(), range(2)))
        self.assertEqual(len({pk for pk, _ in results}), 1)
        self.assertEqual(sum(created for _, created in results), 1)
        self.assertEqual(Stat.objects.filter(user=user, aircraft_type='C172').count(), 1)


class SummaryMigrationTests(TransactionTestCase):
    def test_dirty_summary_data_aborts_migration_without_merging_balances(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        before = [('flights', '0068_core_record_constraints')]
        after = [('flights', '0069_unique_summary_rows')]
        executor.migrate(before)
        old = executor.loader.project_state(before).apps
        user_model = old.get_model('auth', 'User')
        stat_model = old.get_model('flights', 'Stat')
        user = user_model.objects.create(username='summary-migration')
        try:
            first = stat_model.objects.create(user_id=user.pk, aircraft_type='A320', total_time=10)
            second = stat_model.objects.create(user_id=user.pk, aircraft_type='A320', total_time=20)
            snapshot = list(stat_model.objects.filter(user_id=user.pk).order_by('pk').values_list('pk', 'total_time'))
            self.assertTrue(summary_integrity_issues(old, 'default'))
            with self.assertRaisesMessage(RuntimeError, 'duplicate summary group'):
                MigrationExecutor(connection).migrate(after)
            self.assertEqual(list(stat_model.objects.filter(user_id=user.pk).order_by('pk').values_list('pk', 'total_time')), snapshot)
            stat_model.objects.filter(pk=second.pk).delete()  # Correct only this disposable fixture.
            MigrationExecutor(connection).migrate(after)
            self.assertEqual(stat_model.objects.get(pk=first.pk).total_time, Decimal('10.0'))
        finally:
            user_model.objects.filter(pk=user.pk).delete()
            MigrationExecutor(connection).migrate(latest)
