from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.template.loader import render_to_string
from django.urls import reverse

from flights.aircraft_classification import CLASSES_BY_CATEGORY, CLASS_CHOICES, class_display
from flights.forms import AircraftForm
from flights.models import Aircraft, Flight, Imported, Stat, TailNumber, Total
from flights.record_validation import validate_aircraft_classification


class AircraftClassificationFormTests(TestCase):
    def payload(self, category, klass=''):
        # Engine/weight are deliberately unchanged in Step 2.
        return {'aircraft_type': 'TEST', 'aircraft_category': category, 'aircraft_class': klass,
                'engine': 'piston', 'weight_category': 'small'}

    def test_every_category_class_pair_uses_the_explicit_matrix(self):
        for category, allowed in CLASSES_BY_CATEGORY.items():
            for klass in ('', *(key for key, _ in CLASS_CHOICES)):
                with self.subTest(category=category, klass=klass):
                    form = AircraftForm(data=self.payload(category, klass))
                    self.assertEqual(form.is_valid(), klass in allowed if allowed else klass == '', form.errors)

    def test_no_class_categories_hide_the_control_and_display_not_applicable(self):
        for category in ('GL', 'PL'):
            form = AircraftForm(data=self.payload(category))
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.save(commit=False).aircraft_class, '')
            html = render_to_string('aircraft/aircraft_form.html', {'form': form})
            self.assertIn('data-aircraft-class-field hidden', html)
            self.assertEqual(class_display(category, ''), 'Not applicable')
        self.assertEqual(class_display('A', ''), 'Not recorded')

    def test_engine_is_required_only_for_tracked_categories_and_wake_remains_required(self):
        for category, klass in (('GL', ''), ('PL', ''), ('LTA', 'BALLOON')):
            for field in ('engine', 'weight_category'):
                data = self.payload(category, klass)
                data.pop(field)
                form = AircraftForm(data=data)
                if field == 'engine' and category != 'PL':
                    self.assertTrue(form.is_valid(), form.errors)
                else:
                    self.assertFalse(form.is_valid())
                    self.assertIn(field, form.errors)

    def test_existing_blank_class_is_preserved_until_classification_changes(self):
        user = get_user_model().objects.create_user(username='classification-legacy')
        aircraft = Aircraft.objects.create(user=user, aircraft_type='TEST', aircraft_category='A',
                                           piston=True, small=True)
        form = AircraftForm(instance=aircraft, user=user, data={**self.payload('A'), 'simple': True})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().aircraft_class, '')
        form = AircraftForm(instance=aircraft, user=user, data=self.payload('LTA'))
        self.assertFalse(form.is_valid())
        self.assertIn('aircraft_class', form.errors)

    def test_admin_also_requires_class_and_preserves_untouched_legacy_values(self):
        from flights.admin import AircraftClassificationAdminForm
        user = get_user_model().objects.create_user(username='classification-admin')
        form = AircraftClassificationAdminForm(data={'user': user.pk, 'aircraft_type': 'TEST',
                                                    'aircraft_category': 'LTA', 'aircraft_class': ''})
        self.assertFalse(form.is_valid())
        self.assertIn('aircraft_class', form.errors)
        aircraft = Aircraft.objects.create(user=user, aircraft_type='OLD')
        self.assertEqual(validate_aircraft_classification({'simple': True}, aircraft), {})

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_web_detail_has_no_missing_class_error_for_glider(self):
        user = get_user_model().objects.create_user(username='classification-detail')
        user.profile.active = True
        user.profile.save(update_fields=['active'])
        aircraft = Aircraft.objects.create(user=user, aircraft_type='TEST', aircraft_category='GL',
                                           piston=True, small=True, simple=True)
        TailNumber.objects.create(user=user, aircraft=aircraft, registration='N1234', is_91=True)
        self.client.force_login(user)
        response = self.client.get(reverse('aircraft_detail', args=[aircraft.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['detail_has_errors'])
        self.assertContains(response, 'Class: Not applicable')


class AircraftReclassificationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='reclassification')
        self.aircraft = Aircraft.objects.create(user=self.user, aircraft_type='TEST',
            aircraft_category='A', aircraft_class='SEL', piston=True, small=True)
        self.tail = TailNumber.objects.create(user=self.user, aircraft=self.aircraft, registration='N1234', is_91=True)
        Flight.objects.create(user=self.user, aircraft_type=self.aircraft, registration=self.tail,
            route='SEA-PDX', date=date.today(), duration='1.7', pilot_in_command=True, dual=True)
        Flight.objects.create(user=self.user, aircraft_type=self.aircraft, date=date.today(),
            duration='2.1', simulator=True, device_type='FFS', device_id='TEST')
        Imported.objects.create(user=self.user, aircraft_type=self.aircraft, total_time='10.2',
                                simulator='0.4', pilot_in_command='8.0')

    def test_reclassification_regroups_sources_without_changing_records_or_overall_totals(self):
        sources = {model.__name__: list(model.objects.filter(user=self.user).order_by('pk').values())
                   for model in (Flight, Imported, TailNumber)}
        all_before = Total.objects.get(user=self.user, total='All').total_time
        old_key = 'ASEL'
        for category, klass, key in (('R', 'HELO', 'HELO'), ('GL', '', 'GL'), ('PL', '', 'PL'),
                                     ('LTA', 'BALLOON', 'BALLOON'), ('LTA', 'AIRSHIP', 'AIRSHIP')):
            with self.subTest(category=category, klass=klass):
                self.aircraft.aircraft_category, self.aircraft.aircraft_class = category, klass
                self.aircraft.save(update_fields=['aircraft_category', 'aircraft_class'])
                old = Total.objects.get(user=self.user, total=old_key)
                new = Total.objects.get(user=self.user, total=key)
                self.assertEqual(old.total_time, Decimal('0.0'))
                self.assertEqual(old.simulator, Decimal('0.0'))
                self.assertEqual(new.total_time, Decimal('11.9'))
                self.assertEqual(new.simulator, Decimal('2.5'))
                self.assertEqual(new.pilot_in_command, Decimal('9.7'))
                self.assertEqual(new.last_30, Decimal('1.7'))
                self.assertEqual(Total.objects.get(user=self.user, total='All').total_time, all_before)
                self.assertEqual(Stat.objects.get(user=self.user, aircraft_type='TEST').total_time, all_before)
                old_key = key
        for model in (Flight, Imported, TailNumber):
            self.assertEqual(sources[model.__name__], list(model.objects.filter(user=self.user).order_by('pk').values()))

    def test_unrelated_or_unsaved_classification_edits_do_not_rebuild_totals(self):
        self.aircraft.aircraft_category, self.aircraft.aircraft_class = 'GL', ''
        self.aircraft.simple = True
        with patch('flights.signal_total.total_all_update') as refresh:
            self.aircraft.save(update_fields=['simple'])
        refresh.assert_not_called()

    def test_serializer_failure_rolls_back_classification_and_summary_updates(self):
        from api.serializers import AircraftSerializer
        serializer = AircraftSerializer(self.aircraft, data={'aircraft_category': 'GL', 'aircraft_class': ''}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        with patch('flights.signal_total.total_all_update', side_effect=RuntimeError('Test failure')):
            with self.assertRaises(RuntimeError):
                serializer.save()
        self.aircraft.refresh_from_db()
        self.assertEqual(self.aircraft.aircraft_category, 'A')
        self.assertEqual(self.aircraft.aircraft_class, 'SEL')
        self.assertEqual(Total.objects.get(user=self.user, total='ASEL').total_time, Decimal('11.9'))
