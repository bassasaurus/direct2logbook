from datetime import date
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from flights.models import Total
from home.reminder_forms import MilestoneForm
from home.reminders import milestone_hours, reminder_notice, reminder_groups
from profile.models import Reminder


@override_settings(SECURE_SSL_REDIRECT=False)
class FlightConditionMilestoneTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('condition-milestones')
        self.other = get_user_model().objects.create_user('other-condition-milestones')
        self.client.force_login(self.user)
        self.mobile = APIClient()
        self.mobile.force_authenticate(self.user)
        self.values = {key: Decimal(index * 10) + Decimal('0.3')
                       for index, key in enumerate(Reminder.FlightCondition.values, start=1)}
        Total.objects.filter(user=self.user, total='All').update(**self.values)
        Total.objects.filter(user=self.other, total='All').update(pilot_in_command=999)

    def test_every_condition_uses_its_full_logbook_total_for_the_owner(self):
        for condition, label in Reminder.FlightCondition.choices:
            with self.subTest(condition=condition):
                form = MilestoneForm({'kind': 'flight_condition', 'condition': condition, 'target_hours': '100'}, user=self.user)
                self.assertTrue(form.is_valid(), form.errors)
                reminder = form.save_for_user(self.user)
                hours = milestone_hours(reminder, date.today())
                self.assertEqual(hours, self.values[condition])
                self.assertEqual(reminder.milestone_label(hours), f'{label} {hours:.1f} / 100.0')
                self.assertIsNone(reminder.aircraft_id)
                self.assertEqual(reminder_groups([{'kind': reminder.kind}])[1]['rows'], [{'kind': reminder.kind}])

    def test_choice_required_and_invalid_values_rejected(self):
        for value in ('', 'night', 'total_time', 'user_id'):
            form = MilestoneForm({'kind': 'flight_condition', 'condition': value, 'target_hours': '100'}, user=self.user)
            self.assertFalse(form.is_valid())
            self.assertIn('condition', form.errors)
        for value in ('', 'bad'):
            with self.assertRaises(IntegrityError), transaction.atomic():
                Reminder.objects.create(user=self.user, title='Flight Conditions', kind='flight_condition', condition=value, target_hours=100)

    def test_api_returns_progress_and_condition_and_edit_clears_dismissal(self):
        url = reverse('mobile_manage_reminders')
        response = self.mobile.post(url, {'kind': 'flight_condition', 'condition': 'instructor', 'target_hours': '60'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['progress_label'], 'CFI 50.3 / 60.0 | -9.7')
        self.assertEqual(response.data['condition'], 'instructor')
        reminder = Reminder.objects.get(pk=response.data['id'])
        notice = reminder_notice(reminder, date.today(), Decimal('50.3'))
        self.assertIsNotNone(notice)
        reminder.dismissed_key = notice['key']
        reminder.save()
        response = self.mobile.put(reverse('mobile_manage_reminder', args=[reminder.pk]),
            {'kind': 'flight_condition', 'condition': 'simulator', 'target_hours': '100'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        reminder.refresh_from_db()
        self.assertEqual(reminder.dismissed_key, '')
        self.assertEqual(response.data['progress_label'], 'Sim 60.3 / 100.0 | -39.7')

    def test_switching_kind_clears_condition(self):
        reminder = Reminder.objects.create(user=self.user, kind='flight_condition', title='Flight Conditions', condition='solo', target_hours=100)
        form = MilestoneForm({'kind': 'flight_time', 'target_hours': '200'}, instance=reminder, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save_for_user(self.user).condition, '')
