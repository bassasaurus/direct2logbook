from datetime import date

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

from api.serializers import FlightSerializer, TailNumberSerializer
from flights.aircraft_tail_integrity import aircraft_tail_integrity_issues
from flights.forms import FlightForm, TailNumberForm
from flights.models import Aircraft, Flight, TailNumber


class AircraftTailConstraintTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.bulk_create([get_user_model()(username='pair-owner')])[0]
        cls.first, cls.second = Aircraft.objects.bulk_create([
            Aircraft(user=cls.user, aircraft_type='A320'), Aircraft(user=cls.user, aircraft_type='B737')])
        cls.tail_a, cls.tail_b = TailNumber.objects.bulk_create([
            TailNumber(user=cls.user, aircraft=cls.first, registration='N123A', is_91=True),
            TailNumber(user=cls.user, aircraft=cls.second, registration='N123B', is_91=True)])
        cls.flight = Flight.objects.bulk_create([Flight(user=cls.user, aircraft_type=cls.first,
            registration=cls.tail_a, date=date(2026, 1, 1), route='KIAH-KLAX', duration=1, pilot_in_command=True)])[0]

    def rejects(self, action):
        with self.assertRaises(IntegrityError), transaction.atomic():
            action()
            connection.check_constraints()

    def test_database_rejects_mismatched_inserts_and_partial_updates(self):
        self.rejects(lambda: Flight.objects.bulk_create([Flight(user=self.user, aircraft_type=self.second,
            registration=self.tail_a, date=date(2026, 1, 1), route='KIAH-KLAX', duration=1)]))
        before = Flight.objects.filter(pk=self.flight.pk).values().get()
        self.rejects(lambda: Flight.objects.filter(pk=self.flight.pk).update(aircraft_type=self.second))
        self.rejects(lambda: Flight.objects.filter(pk=self.flight.pk).update(registration=self.tail_b))
        self.assertEqual(Flight.objects.filter(pk=self.flight.pk).values().get(), before)

    def test_reassigning_used_tailnumber_cannot_invalidate_historical_flights(self):
        self.rejects(lambda: TailNumber.objects.filter(pk=self.tail_a.pk).update(aircraft=self.second))
        self.tail_a.refresh_from_db()
        self.assertEqual(self.tail_a.aircraft_id, self.first.pk)
        self.flight.refresh_from_db()
        self.assertEqual(self.flight.aircraft_type_id, self.first.pk)

    def test_unused_tailnumber_reassignment_and_matched_flight_corrections_work(self):
        unused = TailNumber.objects.bulk_create([TailNumber(user=self.user, aircraft=self.first, registration='NFREE')])[0]
        TailNumber.objects.filter(pk=unused.pk).update(aircraft=self.second)
        Flight.objects.filter(pk=self.flight.pk).update(aircraft_type=self.second, registration=self.tail_b)
        connection.check_constraints()
        self.assertEqual(aircraft_tail_integrity_issues(apps, 'default'), [])

    def test_explicit_atomic_correction_of_tailnumber_and_all_linked_flights_is_allowed(self):
        with transaction.atomic():
            TailNumber.objects.filter(pk=self.tail_a.pk).update(aircraft=self.second)
            Flight.objects.filter(registration=self.tail_a).update(aircraft_type=self.second)
            connection.check_constraints()
        self.assertEqual(aircraft_tail_integrity_issues(apps, 'default'), [])

    def test_web_and_api_return_field_errors_before_database_write(self):
        form = FlightForm(user=self.user, data={'date': '01/01/2026', 'route': 'KIAH-KLAX',
            'duration': '1.0', 'pilot_in_command': True, 'aircraft_type': self.second.pk, 'registration': self.tail_a.pk})
        self.assertIn('registration', form.errors)
        request = type('Request', (), {'user': self.user})()
        serializer = FlightSerializer(instance=self.flight, data={'aircraft_type': 'B737'}, partial=True,
                                      context={'request': request})
        self.assertFalse(serializer.is_valid())
        self.assertIn('registration', serializer.errors)
        tail_form = TailNumberForm(user=self.user, instance=self.tail_a,
            data={'registration': 'N123A', 'aircraft': self.second.pk, 'is_91': True})
        self.assertIn('aircraft', tail_form.errors)
        tail_serializer = TailNumberSerializer(instance=self.tail_a, data={'aircraft': 'B737'}, partial=True,
                                              context={'request': request})
        self.assertFalse(tail_serializer.is_valid())
        self.assertIn('aircraft', tail_serializer.errors)


class AircraftTailMigrationTests(TransactionTestCase):
    def test_legacy_mismatch_aborts_without_changing_history(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        before, after = [('flights', '0070_matching_ownership')], [('flights', '0071_matching_aircraft_tailnumber')]
        executor.migrate(before)
        old = executor.loader.project_state(before).apps
        user_model = old.get_model('auth', 'User')
        aircraft_model, tail_model, flight_model = [old.get_model('flights', name) for name in ('Aircraft', 'TailNumber', 'Flight')]
        user = user_model.objects.create(username='legacy-pair-owner')
        try:
            first = aircraft_model.objects.create(user_id=user.pk, aircraft_type='A320')
            second = aircraft_model.objects.create(user_id=user.pk, aircraft_type='B737')
            tail = tail_model.objects.create(user_id=user.pk, aircraft_id=first.pk, registration='N123A')
            flight = flight_model.objects.create(user_id=user.pk, aircraft_type_id=second.pk, registration_id=tail.pk,
                date=date(2026, 1, 1), route='KIAH-KLAX', duration=1)
            snapshot = flight_model.objects.filter(pk=flight.pk).values().get()
            self.assertTrue(aircraft_tail_integrity_issues(old, 'default'))
            with self.assertRaisesMessage(RuntimeError, 'mismatch'):
                MigrationExecutor(connection).migrate(after)
            self.assertEqual(flight_model.objects.filter(pk=flight.pk).values().get(), snapshot)
            flight_model.objects.filter(pk=flight.pk).update(aircraft_type_id=first.pk)  # Only this disposable fixture.
            MigrationExecutor(connection).migrate(after)
        finally:
            user_model.objects.filter(pk=user.pk).delete()
            MigrationExecutor(connection).migrate(latest)
