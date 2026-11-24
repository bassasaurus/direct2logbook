from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from flights.models import Aircraft, Flight
from home.instrument_credit import instrument_airplane_device_credit


@override_settings(SECURE_SSL_REDIRECT=False)
class InstrumentDeviceCreditTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('instrument-student')
        self.aircraft = Aircraft.objects.create(user=self.user, aircraft_type='C172', aircraft_category='A', aircraft_class='SEL')

    def session(self, kind, hours, **kwargs):
        values = dict(user=self.user, date=date(2026,11,23), aircraft_type=self.aircraft,
                      registration=None, simulator=True, route='', duration=Decimal(str(hours)),
                      simulated_instrument=Decimal(str(hours)), dual=True, device_id='Trainer42',
                      instrument_credit_eligible=True,
                      device_type='ATD' if kind in ('BATD','AATD') else kind,
                      atd_type=kind if kind in ('BATD','AATD') else '')
        values.update(kwargs)
        return Flight.objects.bulk_create([Flight(**values)])[0]

    def test_device_limits_and_combined_cap_do_not_double_count(self):
        self.session('BATD', 15)
        self.session('AATD', 25)
        self.session('FFS', 25)
        self.session('FTD', 25)
        result = instrument_airplane_device_credit(self.user)
        rows = {row['type']: row for row in result['rows']}
        self.assertEqual(rows['BATD']['within_type_limit'], Decimal('10.0'))
        self.assertEqual(rows['AATD']['within_type_limit'], Decimal('20.0'))
        self.assertEqual(rows['FFS']['within_type_limit'], Decimal('20.0'))
        self.assertEqual(result['device_credit'], Decimal('20.0'))

    def test_logged_time_is_not_credited_without_approved_instruction_confirmation(self):
        self.session('FFS', 4, instrument_credit_eligible=False)
        self.session('AATD', 3, dual=False)
        self.session('BATD', 2, device_id='')
        self.session('', 5)
        result = instrument_airplane_device_credit(self.user)
        self.assertEqual(result['device_credit'], Decimal('0.0'))
        self.assertEqual(result['unclassified_instrument'], Decimal('5.0'))
        self.assertEqual(result['rows'][0]['logged'], Decimal('4.0'))

    def test_instrument_portion_is_used_not_session_duration(self):
        self.session('FFS', 4, simulated_instrument=Decimal('2.5'))
        self.assertEqual(instrument_airplane_device_credit(self.user)['device_credit'], Decimal('2.5'))

    def test_accounts_aircraft_categories_and_future_dates_stay_separate(self):
        self.session('FFS', 3)
        self.session('FFS', 9, date=date.today()+timedelta(days=10))
        rotor = Aircraft.objects.create(user=self.user, aircraft_type='R44', aircraft_category='R', aircraft_class='HELO')
        self.session('FFS', 9, aircraft_type=rotor)
        other = get_user_model().objects.create_user('other-student')
        other_aircraft = Aircraft.objects.create(user=other, aircraft_type='C172')
        self.session('FFS', 9, user=other, aircraft_type=other_aircraft)
        self.assertEqual(instrument_airplane_device_credit(self.user)['device_credit'], Decimal('3.0'))

    def test_api_delivers_same_calculation_as_web(self):
        self.session('FTD', 3)
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get('/api/mobile/stats/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['instrument_device_credit'], instrument_airplane_device_credit(self.user))

    def test_credit_never_exceeds_logged_duration_even_for_malformed_legacy_values(self):
        self.session('FFS', 2, simulated_instrument=Decimal('8.0'))
        self.assertEqual(instrument_airplane_device_credit(self.user)['device_credit'], Decimal('2.0'))

    def test_api_rejects_credit_claim_without_subtype_or_instrument_instruction(self):
        from api.serializers import FlightSerializer
        from types import SimpleNamespace
        payload = dict(date='11/23/2026', aircraft_type='C172', simulator=True,
                       device_type='ATD', device_id='A42', duration='2.0',
                       instrument_credit_eligible=True, pilot_in_command=True, approaches=[])
        serializer = FlightSerializer(data=payload, context={'request': SimpleNamespace(user=self.user)})
        self.assertFalse(serializer.is_valid())
        self.assertIn('atd_type', serializer.errors)
        self.assertNotIn('dual', serializer.errors)
        self.assertNotIn('simulated_instrument', serializer.errors)
        payload['atd_type'] = 'AATD'
        serializer = FlightSerializer(data=payload, context={'request': SimpleNamespace(user=self.user)})
        self.assertFalse(serializer.is_valid())
        self.assertIn('dual', serializer.errors)
        payload.update(atd_type='AATD', dual=True, simulated_instrument='1.5')
        serializer = FlightSerializer(data=payload, context={'request': SimpleNamespace(user=self.user)})
        self.assertTrue(serializer.is_valid(), serializer.errors)
