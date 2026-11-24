from datetime import date
from decimal import Decimal
from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from api.revisions import flight_revision
from flights.forms import FlightForm
from flights.models import Aircraft, Flight, Imported, MapData, Stat, TailNumber, Total
from home.iacra import device_totals, iacra_tables


@override_settings(SECURE_SSL_REDIRECT=False)
class SimulatorDeviceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='sim-pilot')
        self.aircraft = Aircraft.objects.create(user=self.user, aircraft_type='B737',
            aircraft_category='A', aircraft_class='MEL', turbine=True, large=True)
        self.tail = TailNumber.objects.create(user=self.user, aircraft=self.aircraft,
            registration='N737', is_121=True)
        MapData.objects.create(icao='KIAH', iata='IAH', name='Houston')
        MapData.objects.create(icao='KLAX', iata='LAX', name='Los Angeles')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def flight(self, **kwargs):
        values = dict(user=self.user, date=date(2026, 11, 23), aircraft_type=self.aircraft,
                      registration=self.tail, route='IAH-LAX', duration=Decimal('2.0'),
                      pilot_in_command=True)
        values.update(kwargs)
        return Flight.objects.create(**values)

    def payload(self, **kwargs):
        values = dict(date='11/23/2026', aircraft_type='B737', registration='', route='',
                      duration='4.0', simulator=True, device_type='FFS', device_id='737-123', dual=True,
                      approaches=[])
        values.update(kwargs)
        return values

    def test_api_creates_device_session_without_a_tailnumber_or_route(self):
        # Exercise the shared serializer regardless of URL conventions.
        from api.serializers import FlightSerializer
        serializer = FlightSerializer(data=self.payload(), context={'request': SimpleNamespace(user=self.user)})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        flight = serializer.save(user=self.user)
        self.assertEqual(flight.aircraft_type, self.aircraft)
        self.assertIsNone(flight.registration)
        self.assertEqual(flight.device_id, '737-123')
        self.assertEqual(FlightSerializer(flight).data['device_type'], 'FFS')
        self.assertFalse(flight.has_errors)
        self.assertIsNone(flight.distance_nm)

    def test_web_form_requires_device_details_for_new_sim_entries(self):
        values = dict(date='2026-11-23', aircraft_type=self.aircraft.pk, duration='4.0',
                      simulator=True, dual=True, device_type='FTD', device_id='Trainer-42')
        form = FlightForm(values, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.save().registration)
        values.update(device_id='', device_type='')
        form = FlightForm(values, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('device_type', form.errors)
        self.assertNotIn('device_id', form.errors)
        values['device_type'] = 'FTD'
        form = FlightForm(values, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('device_id', form.errors)

    def test_regular_flights_still_require_route_and_tailnumber(self):
        form = FlightForm(dict(date='2026-11-23', aircraft_type=self.aircraft.pk,
                              duration='2.0', pilot_in_command=True), user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('registration', form.errors)
        self.assertIn('route', form.errors)

    def test_simulator_duration_and_roles_do_not_inflate_aircraft_summaries(self):
        flight = self.flight(night='0.3', landings_night=1)
        sim = self.flight(simulator=True, device_type='FFS', device_id='DEV',
                          duration='4.0', night='3.0', simulated_instrument='2.5', landings_night=6)
        for row in (Total.objects.get(user=self.user, total='All'),
                    Total.objects.get(user=self.user, total='AMEL'),
                    Stat.objects.get(user=self.user, aircraft_type='B737')):
            self.assertEqual(row.total_time, Decimal('2.0'))
            self.assertEqual(row.pilot_in_command, Decimal('2.0'))
            self.assertEqual(row.simulator, Decimal('4.0'))
            self.assertEqual(row.night, Decimal('0.3'))
            self.assertEqual(row.landings_night, 1)
        sim.duration = Decimal('5.0')
        sim.save()
        row = Total.objects.get(user=self.user, total='All')
        self.assertEqual(row.total_time, flight.duration)
        self.assertEqual(row.simulator, Decimal('5.0'))
        sim.delete()
        self.assertEqual(Total.objects.get(user=self.user, total='All').simulator, 0)

    def test_simulator_only_aircraft_retains_stat_with_zero_flight_time(self):
        self.flight(simulator=True, device_type='ATD', device_id='A1', registration=None, route='')
        stat = Stat.objects.get(user=self.user, aircraft_type='B737')
        self.assertEqual(stat.total_time, 0)
        self.assertEqual(stat.simulator, Decimal('2.0'))
        self.assertIsNone(stat.last_flown)
        migration = import_module('flights.migrations.0074_separate_simulator_summaries')
        schema = SimpleNamespace(connection=connection)
        migration.restore(apps, schema)
        migration.rebuild(apps, schema)
        stat.refresh_from_db()
        self.assertEqual(stat.total_time, 0)
        self.assertEqual(stat.simulator, Decimal('2.0'))
        self.assertIsNone(stat.last_flown)
        self.assertEqual(stat.last_30, 0)
        self.assertEqual(Total.objects.get(user=self.user, total='All').total_time, 0)

    def test_legacy_metadata_can_remain_blank_and_revisions_stay_compatible(self):
        from api.serializers import FlightSerializer
        old = self.flight(simulator=True)
        before = flight_revision(old)
        data = self.payload(registration='N737', route='IAH-LAX')
        data.pop('device_type')
        data.pop('device_id')
        serializer = FlightSerializer(old, data=data, context={'request': SimpleNamespace(user=self.user)})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        result = serializer.save()
        self.assertEqual(result.registration, self.tail)
        self.assertEqual(result.device_type, '')
        baseline = flight_revision(result)
        Flight.objects.filter(pk=result.pk).update(device_id='NEW')
        result.refresh_from_db()
        self.assertNotEqual(flight_revision(result), baseline)
        self.assertEqual(len(before), 64)

    def test_iacra_device_rows_separate_types_and_keep_other_pilots_out(self):
        self.flight(simulator=True, device_type='FFS', device_id='F1', duration='4.0', dual=True, simulated_instrument='2.5')
        self.flight(simulator=True, device_type='FTD', device_id='T1', duration='1.5')
        self.flight(simulator=True, duration='3.0')  # No guessed classification.
        other = get_user_model().objects.create_user(username='sim-other')
        ac = Aircraft.objects.create(user=other, aircraft_type='B737')
        Flight.objects.create(user=other, aircraft_type=ac, simulator=True,
                              device_type='FFS', device_id='Foreign', route='', date=date.today(), duration='9.0')
        totals = device_totals(self.user)
        self.assertEqual(totals['FFS'][0], Decimal('4.0'))
        self.assertEqual(totals['FFS'][1], Decimal('4.0'))
        self.assertEqual(totals['FFS'][9], Decimal('2.5'))
        self.assertEqual(totals['FTD'][0], Decimal('1.5'))

    def test_rebuild_migration_preserves_source_rows_and_imported_balances(self):
        self.flight(simulator=True, device_type='FFS', device_id='F1', duration='4.0')
        Imported.objects.create(user=self.user, aircraft_type=self.aircraft,
                                total_time='10.0', simulator='3.0', pilot_in_command='8.0')
        before = list(Flight.objects.values())
        migration = import_module('flights.migrations.0074_separate_simulator_summaries')
        schema = SimpleNamespace(connection=connection)
        migration.rebuild(apps, schema)
        total = Total.objects.get(user=self.user, total='All')
        self.assertEqual(total.total_time, Decimal('10.0'))
        self.assertEqual(total.simulator, Decimal('7.0'))
        self.assertEqual(list(Flight.objects.values()), before)
        migration.rebuild(apps, schema)  # Idempotent.
        self.assertEqual(Total.objects.get(pk=total.pk).total_time, total.total_time)

    def test_night_landings_populate_requested_iacra_count_columns(self):
        row = iacra_tables({'airplane_ldg_night': 7, 'airplane_night_ldg_pic': 5,
                            'airplane_night_ldg_sic': 2})['iacra_rows'][0]
        self.assertEqual([row['cells'][i]['value'] for i in (11, 14, 15)], [7, 5, 2])

    def test_sync_roundtrip_replays_device_metadata_without_duplicate(self):
        import uuid
        request = {'operation_id': str(uuid.uuid4()), 'action': 'create', 'data': self.payload(
            device_type='ATD', atd_type='AATD', simulated_instrument='2.5', instrument_credit_eligible=True)}
        first = self.client.post('/api/mobile/flight-sync/', request, format='json')
        self.assertEqual(first.status_code, 200, first.data)
        replay = self.client.post('/api/mobile/flight-sync/', request, format='json')
        self.assertEqual(first.json(), replay.json())
        self.assertEqual(Flight.objects.filter(user=self.user).count(), 1)
        self.assertIsNone(first.data['flight']['registration'])
        self.assertEqual(first.data['flight']['atd_type'], 'AATD')
        self.assertTrue(first.data['flight']['instrument_credit_eligible'])
        update = {'operation_id': str(uuid.uuid4()), 'action': 'update',
                  'flight_id': first.data['flight']['id'], 'base_revision': first.data['flight']['revision'],
                  'data': {**request['data'], 'device_id': 'Corrected device'}}
        response = self.client.post('/api/mobile/flight-sync/', update, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Flight.objects.filter(user=self.user).count(), 1)
        self.assertEqual(response.data['flight']['device_id'], 'Corrected device')

    def test_current_forms_require_atd_subtype_even_without_credit_claim(self):
        from api.serializers import FlightSerializer
        data = self.payload(device_type='ATD', atd_type='')
        serializer = FlightSerializer(data=data, context={'request': SimpleNamespace(user=self.user)})
        self.assertFalse(serializer.is_valid())
        self.assertIn('atd_type', serializer.errors)
        data['atd_type'] = 'BATD'
        serializer = FlightSerializer(data=data, context={'request': SimpleNamespace(user=self.user)})
        self.assertTrue(serializer.is_valid(), serializer.errors)


    def test_aircraft_rename_moves_summary_to_current_type_without_changing_hours(self):
        self.flight(duration='2.0')
        self.flight(simulator=True, device_type='FFS', device_id='F1', duration='4.0')
        self.aircraft.aircraft_type = 'B738'
        self.aircraft.save()
        self.assertFalse(Stat.objects.filter(user=self.user, aircraft_type='B737').exists())
        stat = Stat.objects.get(user=self.user, aircraft_type='B738')
        self.assertEqual(stat.total_time, Decimal('2.0'))
        self.assertEqual(stat.simulator, Decimal('4.0'))

    def test_rebuild_recovers_a_summary_left_under_a_previous_aircraft_name(self):
        self.flight(duration='2.0')
        self.flight(simulator=True, device_type='FFS', device_id='F1', duration='4.0')
        Imported.objects.create(user=self.user, aircraft_type=self.aircraft, total_time='10.0')
        Aircraft.objects.filter(pk=self.aircraft.pk).update(aircraft_type='B738')
        before = list(Flight.objects.values())
        migration = import_module('flights.migrations.0074_separate_simulator_summaries')
        migration.rebuild(apps, SimpleNamespace(connection=connection))
        self.assertFalse(Stat.objects.filter(user=self.user, aircraft_type='B737').exists())
        stat = Stat.objects.get(user=self.user, aircraft_type='B738')
        self.assertEqual(stat.total_time, Decimal('12.0'))
        self.assertEqual(stat.simulator, Decimal('4.0'))
        self.assertEqual(list(Flight.objects.values()), before)
