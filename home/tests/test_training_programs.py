from datetime import date
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.template.loader import render_to_string
from rest_framework.test import APIClient
from flights.forms import FlightForm
from flights.models import Aircraft, Flight, TailNumber
from home.training_programs import training_program_totals


@override_settings(SECURE_SSL_REDIRECT=False)
class TrainingProgramTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('training-programs')
        self.aircraft = Aircraft.objects.create(user=self.user, aircraft_type='B737', aircraft_category='A', aircraft_class='MEL')
        self.tail = TailNumber.objects.create(user=self.user, aircraft=self.aircraft, registration='N123', is_91=True)

    def session(self, hours, program='', device='FFS', **extra):
        values = dict(user=self.user, aircraft_type=self.aircraft, registration=self.tail, date=date(2026, 11, 1),
                      route='IAH-IAH', duration=hours, simulator=True, device_type=device, device_id='SIM-1', training_program=program)
        values.update(extra)
        return Flight.objects.bulk_create([Flight(**values)])[0]

    def test_totals_match_records_exclude_other_users_future_and_aircraft(self):
        self.session('2.3', '141')
        self.session('1.7', '141', 'FTD')
        self.session('3.2', '142')
        self.session('1.5', '', 'ATD')
        self.session('0.8', '', '')
        self.session('9.0', '', simulator=False)
        self.session('9.0', '142', date=date(2027, 1, 1))
        other = get_user_model().objects.create_user('other-programs')
        other_aircraft = Aircraft.objects.create(user=other, aircraft_type='C172')
        other_tail = TailNumber.objects.create(user=other, aircraft=other_aircraft, registration='N999', is_91=True)
        self.session('9.0', '141', user=other, aircraft_type=other_aircraft, registration=other_tail)
        with patch('home.training_programs.timezone.localdate', return_value=date(2026, 11, 27)):
            rows = training_program_totals(self.user)
            client = APIClient()
            client.force_authenticate(self.user)
            response = client.get('/api/mobile/stats/')
        self.assertEqual([r['total'] for r in rows], [Decimal('4.0'), Decimal('3.2'), Decimal('2.3')])
        self.assertEqual(rows[0]['ffs'], Decimal('2.3'))
        self.assertEqual(rows[0]['ftd'], Decimal('1.7'))
        self.assertEqual(rows[2]['unclassified'], Decimal('0.8'))
        self.assertEqual(rows[2]['atd'], Decimal('1.5'))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['simulator_program_totals'], rows)
        html = render_to_string('home/training_programs.html', {'simulator_program_totals': rows})
        self.assertIn('Part 141', html)
        self.assertIn('Part 142', html)
        self.assertIn('4.0', html)

    def test_database_rejects_unknown_program_and_program_on_aircraft_flight(self):
        for extra in [dict(training_program='999'), dict(training_program='141', simulator=False)]:
            with self.assertRaises(IntegrityError), transaction.atomic():
                self.session('1.0', **extra)

    def test_web_form_saves_program_and_allows_unspecified(self):
        for program in ('141', '142', ''):
            form = FlightForm(user=self.user, data={'date': '2026-11-01', 'duration': '2.0', 'aircraft_type': self.aircraft.pk,
                'simulator': True, 'device_type': 'FFS', 'device_id': 'SIM-1', 'training_program': program, 'dual': True})
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.save(commit=False).training_program, program)
