from datetime import date
from django.test import SimpleTestCase, TestCase, override_settings
from django.template import Template, Context
from django.utils.formats import date_format
from logbook.date_formats import display_date, parse_date
from logbook.date_fields import NamedDateInput
from flights.forms import FlightForm, ImportedForm
from profile.forms import MedicalForm
from home.reminder_forms import RegulatoryReminderForm
from django.contrib.auth import get_user_model
from rest_framework import serializers
from api.serializers import FlightSerializer


class DisplayDateTests(SimpleTestCase):
    def test_named_dates_do_not_pad_days_and_invalid_dates_do_not_roll_over(self):
        self.assertEqual(display_date(date(2026, 11, 30)), 'Nov 30, 2026')
        self.assertEqual(display_date(date(2026, 2, 3)), 'Feb 3, 2026')
        self.assertEqual(display_date(None), '')
        self.assertEqual(parse_date('Nov 30, 2026'), date(2026, 11, 30))
        for value in ('2026-11-30', '11/30/2026', '11-30-2026', 'November 30, 2026'):
            self.assertEqual(parse_date(value), date(2026, 11, 30))
        with self.assertRaises(ValueError):
            parse_date('Feb 29, 2026')

    def test_default_template_and_date_widget_use_named_dates(self):
        self.assertEqual(date_format(date(2026, 2, 3)), 'Feb 3, 2026')
        self.assertIn('Feb 3, 2026', NamedDateInput().render('date', date(2026, 2, 3)))
        self.assertEqual(Template('{{ value }}').render(Context({'value': date(2026, 2, 3)})), 'Feb 3, 2026')

    def test_flight_and_imported_forms_keep_legacy_dates_and_accept_named_dates(self):
        for cls, field in ((FlightForm, 'date'), (ImportedForm, 'last_flown')):
            for value in ('Nov 30, 2026', '11/30/2026', '2026-11-30'):
                self.assertEqual(cls().fields[field].clean(value), date(2026, 11, 30))
        for value in ('30/11/2026', '2026-11-30', 'Nov 30, 2026'):
            self.assertEqual(MedicalForm().fields['medical_issue_date'].clean(value), date(2026, 11, 30))

    def test_flight_api_date_contract_is_unchanged(self):
        field = FlightSerializer().fields['date']
        self.assertEqual(field.to_representation(date(2026, 11, 30)), '11/30/2026')
        self.assertEqual(field.run_validation('11/30/2026'), date(2026, 11, 30))
        iso = serializers.DateField(format='%Y-%m-%d', input_formats=['%Y-%m-%d'])
        self.assertEqual(iso.to_representation(date(2026, 11, 30)), '2026-11-30')


class ReminderDateInputTests(TestCase):
    def test_named_and_existing_iso_inputs_share_the_same_saved_date(self):
        user = get_user_model().objects.create_user('date-format-owner')
        for raw in ('2026-11-30', 'Nov 30, 2026'):
            form = RegulatoryReminderForm({'kind': 'expiration', 'title': 'Review', 'due_date': raw}, user=user)
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data['due_date'], date(2026, 11, 30))
