from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from flights.forms import FlightForm, ImportedForm, TailNumberForm
from flights.models import Aircraft, Flight, Imported, TailNumber


@override_settings(SECURE_SSL_REDIRECT=False)
class FormRelationshipOwnershipTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='form_owner')
        self.other = get_user_model().objects.create_user(username='form_other')
        self.aircraft = Aircraft.objects.create(user=self.user, aircraft_type='C172')
        self.other_aircraft = Aircraft.objects.create(user=self.other, aircraft_type='A320')
        self.tail = TailNumber.objects.create(
            user=self.user, aircraft=self.aircraft, registration='NOWN',
        )
        self.other_tail = TailNumber.objects.create(
            user=self.other, aircraft=self.other_aircraft, registration='NOTHER',
        )
        self.flight = Flight.objects.create(
            user=self.user, aircraft_type=self.aircraft, registration=self.tail,
            date=date(2026, 1, 1), route='KJFK-KLAX', duration='1.0',
        )
        self.imported = Imported.objects.create(
            user=self.user, aircraft_type=self.aircraft, total_time='1.0',
        )
        profile = self.user.profile
        profile.active = True
        profile.expired = False
        profile.save(update_fields=['active', 'expired'])
        self.client.force_login(self.user)

    def flight_data(self):
        data = {
            'date': '01/02/2026', 'route': 'KJFK-KLAX', 'duration': '1.5',
            'aircraft_type': self.aircraft.pk, 'registration': self.tail.pk,
        }
        for prefix in ('approach_set', 'holding_set'):
            data.update({
                prefix + '-TOTAL_FORMS': '0', prefix + '-INITIAL_FORMS': '0',
                prefix + '-MIN_NUM_FORMS': '0', prefix + '-MAX_NUM_FORMS': '4',
            })
        return data

    def cases(self):
        return [
            (FlightForm, 'flight_create', 'flight_update', self.flight,
             self.flight_data(), 'aircraft_type', self.other_aircraft.pk),
            (FlightForm, 'flight_create', 'flight_update', self.flight,
             self.flight_data(), 'registration', self.other_tail.pk),
            (TailNumberForm, 'tailnumber_create', 'tailnumber_update', self.tail,
             {'registration': 'NNEW', 'aircraft': self.aircraft.pk},
             'aircraft', self.other_aircraft.pk),
            (ImportedForm, 'imported_create', 'imported_update', self.imported,
             {'aircraft_type': self.aircraft.pk, 'total_time': '2.0'},
             'aircraft_type', self.other_aircraft.pk),
        ]

    def test_missing_user_context_exposes_no_relationship_choices(self):
        for form_class, _, _, _, data, field, foreign in self.cases():
            with self.subTest(form=form_class.__name__, field=field):
                form = form_class(data=data)
                self.assertFalse(form.fields[field].queryset.exists())
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)

    def test_owner_relationships_are_valid(self):
        for form_class, _, _, _, data, field, foreign in self.cases():
            with self.subTest(form=form_class.__name__, field=field):
                form = form_class(data=data, user=self.user)
                self.assertTrue(form.is_valid(), form.errors)
                self.assertFalse(form.fields[field].queryset.filter(pk=foreign).exists())

    def test_foreign_relationships_are_rejected_by_forms(self):
        for form_class, _, _, _, data, field, foreign in self.cases():
            with self.subTest(form=form_class.__name__, field=field):
                data[field] = foreign
                form = form_class(data=data, user=self.user)
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)

    def test_create_views_supply_the_authenticated_owner(self):
        for _, create, _, _, _, field, foreign in self.cases():
            with self.subTest(view=create, field=field):
                response = self.client.get(reverse(create))
                self.assertEqual(response.status_code, 200)
                choices = response.context['form'].fields[field].queryset
                self.assertTrue(choices.exists())
                self.assertFalse(choices.exclude(user=self.user).exists())

    def test_update_views_supply_the_authenticated_owner(self):
        for _, _, update, obj, _, field, foreign in self.cases():
            with self.subTest(view=update, field=field):
                response = self.client.get(reverse(update, args=[obj.pk]))
                self.assertEqual(response.status_code, 200)
                choices = response.context['form'].fields[field].queryset
                self.assertTrue(choices.exists())
                self.assertFalse(choices.exclude(user=self.user).exists())

    def test_crafted_create_submissions_cannot_use_foreign_relationships(self):
        for _, create, _, obj, data, field, foreign in self.cases():
            with self.subTest(view=create, field=field):
                before = type(obj).objects.count()
                data[field] = foreign
                response = self.client.post(reverse(create), data)
                self.assertEqual(response.status_code, 200)
                self.assertIn(field, response.context['form'].errors)
                self.assertEqual(type(obj).objects.count(), before)

    def test_crafted_update_submissions_leave_relationships_unchanged(self):
        for _, _, update, obj, data, field, foreign in self.cases():
            with self.subTest(view=update, field=field):
                before = getattr(obj, field + '_id')
                data[field] = foreign
                response = self.client.post(reverse(update, args=[obj.pk]), data)
                self.assertEqual(response.status_code, 200)
                self.assertIn(field, response.context['form'].errors)
                obj.refresh_from_db()
                self.assertEqual(getattr(obj, field + '_id'), before)
                self.assertEqual(obj.user_id, self.user.pk)
