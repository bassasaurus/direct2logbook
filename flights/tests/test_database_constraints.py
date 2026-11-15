from datetime import date
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase

from api.serializers import AircraftSerializer, TailNumberSerializer
from flights.forms import AircraftForm, TailNumberForm
from flights.models import Aircraft, Flight, Imported, TailNumber
from flights.record_integrity import record_integrity_issues


class DatabaseConstraintTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner, cls.other = get_user_model().objects.bulk_create([
            get_user_model()(username='constraints-owner'), get_user_model()(username='constraints-other')])
        cls.aircraft = Aircraft.objects.bulk_create([Aircraft(user=cls.owner, aircraft_type='A320')])[0]
        cls.tail = TailNumber.objects.bulk_create([TailNumber(user=cls.owner, aircraft=cls.aircraft, registration='N123AB')])[0]
        cls.flight = Flight.objects.bulk_create([Flight(user=cls.owner, aircraft_type=cls.aircraft,
            registration=cls.tail, date=date(2026, 1, 1), route='IAH-LAX', duration=Decimal('1.0'))])[0]
        cls.imported = Imported.objects.bulk_create([Imported(user=cls.owner, aircraft_type=cls.aircraft)])[0]

    def rejects(self, action):
        with self.assertRaises(IntegrityError), transaction.atomic():
            action()

    def test_nonempty_identifiers_and_routes_block_raw_updates(self):
        for model, pk, field in [(Aircraft, self.aircraft.pk, 'aircraft_type'),
                                 (TailNumber, self.tail.pk, 'registration'), (Flight, self.flight.pk, 'route')]:
            for value in ('', '   ', '\t\n'):
                with self.subTest(model=model.__name__, value=repr(value)):
                    self.rejects(lambda: model.objects.filter(pk=pk).update(**{field: value}))

    def test_case_insensitive_uniqueness_is_per_owner_and_handles_updates(self):
        self.rejects(lambda: Aircraft.objects.bulk_create([Aircraft(user=self.owner, aircraft_type='a320')]))
        self.rejects(lambda: TailNumber.objects.bulk_create([TailNumber(user=self.owner, aircraft=self.aircraft, registration='n123ab')]))
        other_aircraft = Aircraft.objects.bulk_create([Aircraft(user=self.other, aircraft_type='a320')])[0]
        TailNumber.objects.bulk_create([TailNumber(user=self.other, aircraft=other_aircraft, registration='n123ab')])
        extra = Aircraft.objects.bulk_create([Aircraft(user=self.owner, aircraft_type='B737')])[0]
        self.rejects(lambda: Aircraft.objects.filter(pk=extra.pk).update(aircraft_type='a320'))
        # Changing only a record's own case remains valid.
        Aircraft.objects.filter(pk=self.aircraft.pk).update(aircraft_type='a320')
        TailNumber.objects.filter(pk=self.tail.pk).update(registration='n123ab')

    def test_hours_reject_negatives_but_preserve_zero_and_optional_null(self):
        for model, pk, fields in [(Flight, self.flight.pk, ('duration', 'night', 'instrument', 'simulated_instrument')),
            (Imported, self.imported.pk, ('total_time', 'pilot_in_command', 'second_in_command', 'cross_country',
                'instructor', 'dual', 'solo', 'instrument', 'night', 'simulated_instrument', 'simulator'))]:
            for field in fields:
                with self.subTest(model=model.__name__, field=field):
                    self.rejects(lambda: model.objects.filter(pk=pk).update(**{field: -0.1}))
                    model.objects.filter(pk=pk).update(**{field: 0})
                    model.objects.filter(pk=pk).update(**{field: None})

    def test_form_and_api_duplicate_checks_return_field_errors(self):
        aircraft_data = {'aircraft_type': 'a320', 'aircraft_category': 'A', 'aircraft_class': 'MEL',
                         'turbine': True, 'small': True}
        tail_data = {'registration': 'n123ab', 'aircraft': self.aircraft.pk, 'is_91': True}
        for form, field in [(AircraftForm(data=aircraft_data, user=self.owner), 'aircraft_type'),
                            (TailNumberForm(data=tail_data, user=self.owner), 'registration')]:
            self.assertFalse(form.is_valid())
            self.assertIn(field, form.errors)
        request = type('Request', (), {'user': self.owner})()
        for serializer, data, field in [(AircraftSerializer, aircraft_data, 'aircraft_type'),
                                        (TailNumberSerializer, tail_data, 'registration')]:
            instance = serializer(data=data, context={'request': request})
            self.assertFalse(instance.is_valid())
            self.assertIn(field, instance.errors)

    def test_preflight_passes_without_writes_and_reports_blockers(self):
        self.assertEqual(record_integrity_issues(apps, 'default'), [])
        output = StringIO()
        call_command('check_record_integrity', stdout=output)
        self.assertIn('No records changed', output.getvalue())
        with patch('flights.management.commands.check_record_integrity.record_integrity_issues',
                   return_value=['Aircraft.aircraft_type: duplicate group IDs [1, 2]']):
            with self.assertRaisesMessage(CommandError, 'duplicate group IDs'):
                call_command('check_record_integrity')


class ConstraintMigrationPreflightTests(TransactionTestCase):
    def test_migration_refuses_dirty_data_without_rewriting_records(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        from django.db.migrations.recorder import MigrationRecorder
        latest = MigrationExecutor(connection).loader.graph.leaf_nodes()
        before = [('flights', '0067_alter_holding_flight_object')]
        after = [('flights', '0068_core_record_constraints')]
        executor = MigrationExecutor(connection)
        executor.migrate(before)
        old = executor.loader.project_state(before).apps
        user_model = old.get_model('auth', 'User')
        aircraft_model = old.get_model('flights', 'Aircraft')
        user = user_model.objects.create(username='migration-preflight-owner')
        try:
            first = aircraft_model.objects.create(user_id=user.pk, aircraft_type='A320')
            second = aircraft_model.objects.create(user_id=user.pk, aircraft_type='a320')
            blank = aircraft_model.objects.create(user_id=user.pk, aircraft_type=' \t')
            original = list(aircraft_model.objects.filter(user_id=user.pk).order_by('pk').values_list('pk', 'aircraft_type'))
            with self.assertRaisesMessage(RuntimeError, 'case-insensitive duplicate'):
                MigrationExecutor(connection).migrate(after)
            self.assertEqual(list(aircraft_model.objects.filter(user_id=user.pk).order_by('pk').values_list('pk', 'aircraft_type')), original)
            self.assertFalse(MigrationRecorder(connection).migration_qs.filter(app='flights', name='0068_core_record_constraints').exists())
            # Only the test fixture is corrected, explicitly, before the successful retry.
            aircraft_model.objects.filter(pk__in=[second.pk, blank.pk]).delete()
            MigrationExecutor(connection).migrate(after)
            self.assertTrue(aircraft_model.objects.filter(pk=first.pk, aircraft_type='A320').exists())
        finally:
            user_model.objects.filter(pk=user.pk).delete()
            MigrationExecutor(connection).migrate(latest)
