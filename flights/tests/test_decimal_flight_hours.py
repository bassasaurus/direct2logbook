import json
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.test import TestCase, TransactionTestCase
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from rest_framework.exceptions import ValidationError
from rest_framework.renderers import JSONRenderer

from api.revisions import flight_revision
from api.serializers import FlightSerializer
from flights.models import Aircraft, Flight, TailNumber


FIELDS = ('night', 'instrument', 'simulated_instrument')


class DecimalFlightHoursTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username='decimal-hours')
        aircraft = Aircraft.objects.create(user=user, aircraft_type='C172',
                                           aircraft_category='A', aircraft_class='SEL')
        tail = TailNumber.objects.create(user=user, aircraft=aircraft, registration='N123')
        self.flight = Flight.objects.create(user=user, aircraft_type=aircraft,
                                            registration=tail, date=date(2026, 1, 1),
                                            duration='1.0', pilot_in_command=True, route='IAH-LAX')

    def test_database_stores_tenths_and_keeps_nulls(self):
        for field in FIELDS:
            with self.subTest(field=field):
                Flight.objects.filter(pk=self.flight.pk).update(**{field: Decimal('1.25')})
                self.flight.refresh_from_db()
                self.assertEqual(getattr(self.flight, field), Decimal('1.3'))
                self.assertIsInstance(getattr(self.flight, field), Decimal)
                Flight.objects.filter(pk=self.flight.pk).update(**{field: None})
                self.flight.refresh_from_db()
                self.assertIsNone(getattr(self.flight, field))

    def test_aggregation_is_exact_decimal_arithmetic(self):
        for value in ('0.1', '0.2'):
            flight = self.flight
            flight.pk = None
            for field in FIELDS:
                setattr(flight, field, Decimal(value))
            flight.save()
        for field in FIELDS:
            total = Flight.objects.aggregate(value=Sum(field))['value']
            self.assertEqual(total, Decimal('0.3'))
            self.assertIsInstance(total, Decimal)

    def test_api_accepts_tenths_and_rejects_extra_precision(self):
        fields = FlightSerializer().fields
        for name in FIELDS:
            with self.subTest(field=name):
                field = fields[name]
                self.assertEqual(field.run_validation('1.2'), Decimal('1.2'))
                self.assertIsNone(field.run_validation(None))
                for value in ('1.23', '-0.1'):
                    with self.assertRaises(ValidationError):
                        field.run_validation(value)
                rendered = JSONRenderer().render({'value': field.to_representation(Decimal('1.2'))})
                self.assertEqual(json.loads(rendered), {'value': 1.2})

    def test_mobile_revision_is_unchanged_by_storage_type_conversion(self):
        for field in FIELDS:
            setattr(self.flight, field, 1.2)
        previous = flight_revision(self.flight)
        for field in FIELDS:
            setattr(self.flight, field, Decimal('1.2'))
        self.assertEqual(flight_revision(self.flight), previous)


class DecimalHoursMigrationTests(TransactionTestCase):
    def test_existing_float_hours_and_blanks_convert_to_exact_tenths(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        before = [('flights', '0071_matching_aircraft_tailnumber')]
        executor.migrate(before)
        old = executor.loader.project_state(before).apps
        User = old.get_model('auth', 'User')
        Aircraft = old.get_model('flights', 'Aircraft')
        TailNumber = old.get_model('flights', 'TailNumber')
        Flight = old.get_model('flights', 'Flight')
        user = User.objects.create(username='decimal-migration')
        try:
            aircraft = Aircraft.objects.create(user_id=user.pk, aircraft_type='C172')
            tail = TailNumber.objects.create(user_id=user.pk, aircraft_id=aircraft.pk, registration='N123')
            ids = []
            for value in (0.1, 0.2, 1.25, None, 0.0):
                row = Flight.objects.create(user_id=user.pk, aircraft_type_id=aircraft.pk, registration_id=tail.pk,
                                           date=date(2026, 1, 1), route='IAH-LAX', duration=1,
                                           **{field: value for field in FIELDS})
                ids.append(row.pk)
            MigrationExecutor(connection).migrate(latest)
            from flights.models import Flight as CurrentFlight
            expected = [Decimal('0.1'), Decimal('0.2'), Decimal('1.3'), None, Decimal('0.0')]
            for field in FIELDS:
                self.assertEqual(list(CurrentFlight.objects.filter(pk__in=ids).order_by('pk').values_list(field, flat=True)), expected)
        finally:
            MigrationExecutor(connection).migrate(latest)
            get_user_model().objects.filter(pk=user.pk).delete()
