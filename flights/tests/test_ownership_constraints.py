from datetime import date

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

from flights.models import Aircraft, Flight, Imported, TailNumber
from flights.ownership_integrity import ownership_integrity_issues
from profile.models import Reminder


class MatchingOwnershipTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user, cls.other = get_user_model().objects.bulk_create([
            get_user_model()(username='owner-one'), get_user_model()(username='owner-two')])
        # Pilots may log the same physical aircraft independently.
        cls.aircraft, cls.other_aircraft = Aircraft.objects.bulk_create([
            Aircraft(user=cls.user, aircraft_type='A320'), Aircraft(user=cls.other, aircraft_type='A320')])
        cls.tail, cls.other_tail = TailNumber.objects.bulk_create([
            TailNumber(user=cls.user, aircraft=cls.aircraft, registration='N123A'),
            TailNumber(user=cls.other, aircraft=cls.other_aircraft, registration='N123A')])
        cls.flight = Flight.objects.bulk_create([Flight(user=cls.user, aircraft_type=cls.aircraft,
            registration=cls.tail, date=date(2026, 1, 1), route='KIAH-KLAX', duration=1)])[0]
        cls.imported = Imported.objects.bulk_create([Imported(user=cls.user, aircraft_type=cls.aircraft)])[0]
        cls.reminder = Reminder.objects.bulk_create([Reminder(user=cls.user, kind='time_in_type',
            target_hours=500, aircraft=cls.aircraft)])[0]

    def rejects(self, action):
        with self.assertRaises(IntegrityError), transaction.atomic():
            action()
            connection.check_constraints()  # Composite FKs are deferred to commit.

    def test_cross_owner_inserts_rejected_for_all_owned_relations(self):
        records = [
            TailNumber(user=self.user, aircraft=self.other_aircraft, registration='NNEW'),
            Flight(user=self.user, aircraft_type=self.other_aircraft, registration=self.tail,
                   date=date(2026, 1, 1), route='KIAH-KLAX', duration=1),
            Flight(user=self.user, aircraft_type=self.aircraft, registration=self.other_tail,
                   date=date(2026, 1, 1), route='KIAH-KLAX', duration=1),
            Imported(user=self.user, aircraft_type=self.other_aircraft),
            Reminder(user=self.user, kind='time_in_type', target_hours=500, aircraft=self.other_aircraft),
        ]
        for record in records:
            with self.subTest(model=type(record).__name__):
                self.rejects(lambda: type(record).objects.bulk_create([record]))
        self.assertEqual(ownership_integrity_issues(apps, 'default'), [])

    def test_cross_owner_updates_are_rejected_without_changing_records(self):
        for obj, values in [(self.tail, {'aircraft': self.other_aircraft}),
                            (self.flight, {'aircraft_type': self.other_aircraft}),
                            (self.flight, {'registration': self.other_tail}),
                            (self.flight, {'user': self.other}),
                            (self.imported, {'aircraft_type': self.other_aircraft}),
                            (self.reminder, {'aircraft': self.other_aircraft})]:
            with self.subTest(model=type(obj).__name__, fields=list(values)):
                model = type(obj)
                before = model.objects.filter(pk=obj.pk).values().get()
                self.rejects(lambda: model.objects.filter(pk=obj.pk).update(**values))
                self.assertEqual(model.objects.filter(pk=obj.pk).values().get(), before)

    def test_parent_owner_changes_cannot_invalidate_existing_children(self):
        parent = Aircraft.objects.bulk_create([Aircraft(user=self.user, aircraft_type='C172')])[0]
        tail = TailNumber.objects.bulk_create([TailNumber(user=self.user, aircraft=parent, registration='NTRANS')])[0]
        self.rejects(lambda: Aircraft.objects.filter(pk=parent.pk).update(user=self.other))
        Flight.objects.bulk_create([Flight(user=self.user, aircraft_type=parent, registration=tail,
            date=date(2026, 1, 1), route='KIAH-KLAX', duration=1)])
        self.rejects(lambda: TailNumber.objects.filter(pk=tail.pk).update(user=self.other, aircraft=self.other_aircraft))

    def test_same_aircraft_codes_across_pilots_and_optional_reminder_reference_remain_valid(self):
        Flight.objects.bulk_create([Flight(user=self.other, aircraft_type=self.other_aircraft,
            registration=self.other_tail, date=date(2026, 1, 1), route='KIAH-KLAX', duration=1)])
        Reminder.objects.bulk_create([Reminder(user=self.user, kind='flight_time', target_hours=500)])
        self.assertEqual(Aircraft.objects.filter(aircraft_type='A320').count(), 2)
        self.assertEqual(TailNumber.objects.filter(registration='N123A').count(), 2)
        connection.check_constraints()

    def test_coherent_owner_transfer_can_finish_in_one_transaction(self):
        third = get_user_model().objects.bulk_create([get_user_model()(username='owner-three')])[0]
        with transaction.atomic():
            Aircraft.objects.filter(pk=self.aircraft.pk).update(user=third)
            TailNumber.objects.filter(pk=self.tail.pk).update(user=third)
            Flight.objects.filter(pk=self.flight.pk).update(user=third)
            Imported.objects.filter(pk=self.imported.pk).update(user=third)
            Reminder.objects.filter(pk=self.reminder.pk).update(user=third)
            connection.check_constraints()
        self.assertEqual(ownership_integrity_issues(apps, 'default'), [])

    def test_whole_user_deletion_removes_only_that_pilots_records(self):
        self.user.delete()
        connection.check_constraints()
        self.assertFalse(Flight.objects.filter(pk=self.flight.pk).exists())
        self.assertFalse(Reminder.objects.filter(pk=self.reminder.pk).exists())
        self.assertTrue(Aircraft.objects.filter(pk=self.other_aircraft.pk).exists())
        self.assertTrue(TailNumber.objects.filter(pk=self.other_tail.pk).exists())


class OwnershipMigrationTests(TransactionTestCase):
    def test_cross_owner_legacy_link_aborts_without_reassigning_records(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        before = [('flights', '0069_unique_summary_rows'), ('profile', '0016_cascade_aircraft_reminders')]
        after = [('flights', '0070_matching_ownership')]
        executor.migrate(before)
        old = executor.loader.project_state(before).apps
        user_model = old.get_model('auth', 'User')
        aircraft_model, tail_model = old.get_model('flights', 'Aircraft'), old.get_model('flights', 'TailNumber')
        one = user_model.objects.create(username='legacy-owner-one')
        two = user_model.objects.create(username='legacy-owner-two')
        try:
            aircraft = aircraft_model.objects.create(user_id=two.pk, aircraft_type='A320')
            tail = tail_model.objects.create(user_id=one.pk, aircraft_id=aircraft.pk, registration='N123A')
            snapshot = tail_model.objects.filter(pk=tail.pk).values().get()
            self.assertTrue(ownership_integrity_issues(old, 'default'))
            with self.assertRaisesMessage(RuntimeError, 'ownership mismatch'):
                MigrationExecutor(connection).migrate(after)
            self.assertEqual(tail_model.objects.filter(pk=tail.pk).values().get(), snapshot)
            tail_model.objects.filter(pk=tail.pk).update(user_id=two.pk)  # Only this disposable fixture.
            MigrationExecutor(connection).migrate(after)
        finally:
            user_model.objects.filter(pk__in=[one.pk, two.pk]).delete()
            MigrationExecutor(connection).migrate(latest)
