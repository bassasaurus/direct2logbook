from datetime import date
from django.contrib.auth import get_user_model
from django.test import TestCase, SimpleTestCase
from flights.models import Flight
from flights.remarks import validate_remarks
from django.core.exceptions import ValidationError
from csv_app.tests.record_fixtures import seed_records
from csv_app.tests.airport_fixtures import seed_airports
from csv_app.tests.test_atomic_import import content, row
from csv_app.validation import parse_csv, CSVValidationError


class RemarksValidationTests(SimpleTestCase):
    def test_commas_and_tabs_are_errors_and_tab_positions_are_visible(self):
        with self.assertRaisesMessage(ValidationError,'Remove commas to prevent export corruption.'):
            validate_remarks('Low cloud, improving')
        with self.assertRaisesMessage(ValidationError,'Remove tabs to prevent export corruption.'):
            validate_remarks('ILS\tLPV\t')
        for value in (None, '', 'No change.\nSecond line.'):
            validate_remarks(value)

    def test_csv_requires_correction_and_preserves_valid_text(self):
        for text in ('ILS, LPV', 'ILS\tLPV', '\tILS', 'ILS\t'):
            with self.subTest(text=text), self.assertRaisesRegex(CSVValidationError,'Remarks: Remove'):
                parse_csv(content([row(**{'18':text})]))
        parsed, preview = parse_csv(content([row(**{'18':'ILS / LPV'})]))
        self.assertEqual(parsed[0]['remarks'], 'ILS / LPV')
        self.assertEqual(preview[0][18], 'ILS / LPV')


class SavedFlightRemarksTests(TestCase):
    def test_create_update_and_partial_save(self):
        seed_airports()
        user = get_user_model().objects.create_user('remarks-test')
        aircraft, tail = seed_records(user)
        data=dict(user=user, aircraft_type=aircraft, registration=tail,
            date=date(2026,1,1), route='KIAH-KCLL', duration='1.2', pilot_in_command=True)
        for value in ('Low cloud, improving', 'ILS\tLPV'):
            with self.assertRaises(ValidationError):
                Flight.objects.create(**data, remarks=value)
        self.assertFalse(Flight.objects.filter(user=user).exists())
        flight = Flight.objects.create(**data, remarks='Low cloud')
        flight.refresh_from_db()
        self.assertEqual(flight.remarks, 'Low cloud')
        for value in ('ILS,LPV', 'ILS\tLPV'):
            flight.remarks=value
            with self.assertRaises(ValidationError):
                flight.save(update_fields=['remarks'])
            flight.refresh_from_db()
            self.assertEqual(flight.remarks, 'Low cloud')
        flight.remarks='Not, saved'
        flight.save(update_fields=['date'])
        flight.refresh_from_db()
        self.assertEqual(flight.remarks, 'Low cloud')
        from flights.forms import FlightForm
        from api.serializers import FlightSerializer
        from rest_framework.exceptions import ValidationError as APIValidationError
        form_data={**data,'aircraft_type':aircraft.pk,'registration':tail.pk,'remarks':'Bad,\ttext'}
        form_data.pop('user')
        form=FlightForm(user=user,data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('Remove commas to prevent export corruption.',form.errors['remarks'])
        self.assertIn('Remove tabs to prevent export corruption.',form.errors['remarks'])
        with self.assertRaises(APIValidationError):
            FlightSerializer().fields['remarks'].run_validation('Bad,\ttext')
        with self.assertRaises(APIValidationError):
            FlightSerializer().fields['remarks'].run_validation('\tText\t')
        form_data['remarks']='\tText\t'
        self.assertIn('Remove tabs to prevent export corruption.',FlightForm(user=user,data=form_data).errors['remarks'])

    def test_separator_preview_escapes_text_and_marks_red_badges(self):
        from flights.templatetags.flights_filters import visible_remarks_separators
        rendered=str(visible_remarks_separators('<script>,ILS\tLPV'))
        self.assertIn('&lt;script&gt;',rendered)
        self.assertNotIn('<script>',rendered)
        self.assertEqual(rendered.count('border-danger'),2)
        self.assertIn('>comma</span>',rendered)
        self.assertIn('>tab</span>',rendered)
