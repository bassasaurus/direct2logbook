from csv_app.validation import HEADERS, OPTIONAL_HEADERS
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from csv_app.csv_import import csv_import
from csv_app.validation import parse_csv, CSVValidationError
from csv_app.tests.test_atomic_import import content, row
from flights.models import Aircraft, Flight, TailNumber


@override_settings(SECURE_SSL_REDIRECT=False)
class GliderLaunchCSVTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='glider-csv')
        self.user.profile.active = True
        self.user.profile.save()
        self.client.force_login(self.user)
        self.aircraft = Aircraft.objects.create(user=self.user, aircraft_type='GL1', aircraft_category='GL', self_launch_capable=True)
        self.tail = TailNumber.objects.create(user=self.user, aircraft=self.aircraft, registration='N12345')

    def csv(self, method):
        return content([row(**{'1': 'GL1'}) + [method]], HEADERS + ['launch method'])

    def import_file(self, text):
        with patch('csv_app.csv_import._notify_import_complete'):
            return csv_import(SimpleNamespace(user=self.user), text)

    def test_all_methods_round_trip_through_export_and_atomic_import(self):
        for method in ('AEROTOW', 'GROUND', 'SELF'):
            Flight.objects.create(user=self.user, date=date(2026, 11, 24), aircraft_type=self.aircraft,
                registration=self.tail, route='SEA-PDX', duration='1.5', pilot_in_command=True, launch_method=method)
        response = self.client.get(reverse('csv_download'))
        parsed, preview = parse_csv(response.content.decode())
        self.assertEqual({item['launch_method'] for item in parsed}, {'AEROTOW', 'GROUND', 'SELF'})
        self.assertEqual(self.import_file(response.content.decode()), 3)
        for method in ('AEROTOW', 'GROUND', 'SELF'):
            self.assertEqual(Flight.objects.filter(launch_method=method).count(), 2)
        self.assertEqual(len(preview[0]), len(HEADERS + OPTIONAL_HEADERS))

    def test_readable_labels_are_accepted_and_unknown_methods_rejected(self):
        for label, method in [('Aerotow', 'AEROTOW'), ('Ground Launch', 'GROUND'), ('Self-launch', 'SELF')]:
            self.assertEqual(parse_csv(self.csv(label))[0][0]['launch_method'], method)
        with self.assertRaisesRegex(CSVValidationError, 'Choose Aerotow'):
            parse_csv(self.csv('BOGUS'))

    def test_missing_or_unsupported_launch_does_not_partially_import_gliders(self):
        with self.assertRaisesRegex(CSVValidationError, 'Choose a launch method'):
            self.import_file(content([row(**{'1': 'GL1'})]))
        self.aircraft.self_launch_capable = False
        self.aircraft.save()
        with self.assertRaisesRegex(CSVValidationError, 'not self-launch capable'):
            self.import_file(self.csv('SELF'))
        self.assertFalse(Flight.objects.exists())
