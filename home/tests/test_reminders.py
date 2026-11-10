from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from flights.models import Total
from profile.models import Reminder


class ReminderTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('reminder-owner')
        self.other = get_user_model().objects.create_user('reminder-other')
        self.client.force_login(self.user)
        self.mobile = APIClient()
        self.mobile.force_authenticate(self.user)
        self.today = date(2026, 11, 9)

    def notices(self):
        response = self.mobile.get(reverse('mobile_reminders'))
        self.assertEqual(response.status_code, 200)
        return response.json()['reminders']

    @patch('home.reminders.timezone.localdate')
    def test_web_dismissal_reappears_on_mobile_at_next_expiration_stage(self, localdate):
        localdate.return_value = self.today
        response = self.client.post(reverse('manage_reminders'), {
            'title': 'LCP expiration', 'kind': 'expiration', 'due_date': '2026-11-30',
        })
        self.assertRedirects(response, reverse('manage_reminders'))
        notice, = self.notices()
        self.assertEqual(notice['severity'], 'warning')
        self.client.post(reverse('dismiss_dashboard_reminder', args=[notice['id']]), {'key': notice['key']})
        self.assertEqual(self.notices(), [])

        localdate.return_value = self.today + timedelta(days=14)
        urgent, = self.notices()
        self.assertEqual(urgent['severity'], 'danger')
        dismiss = reverse('mobile_reminder_dismiss', args=[notice['id']])
        self.assertEqual(self.mobile.post(dismiss, {'key': notice['key']}).json()['reminders'], [urgent])
        self.assertEqual(self.mobile.post(dismiss, {'key': urgent['key']}).json()['reminders'], [])

        localdate.return_value = self.today + timedelta(days=22)
        expired, = self.notices()
        self.assertIn('Expired', expired['message'])

    def test_milestone_uses_full_logbook_total_and_stays_dismissed(self):
        reminder = Reminder.objects.create(user=self.user, kind='flight_time', title='First 500 hours', target_hours=500)
        Total.objects.filter(user=self.user, total='All').update(total_time=499.9)
        self.assertEqual(self.notices(), [])
        Total.objects.filter(user=self.user, total='All').update(total_time=500)
        notice, = self.notices()
        self.mobile.post(reverse('mobile_reminder_dismiss', args=[reminder.pk]), {'key': notice['key']})
        Total.objects.filter(user=self.user, total='All').update(total_time=501)
        self.assertEqual(self.notices(), [])

    def test_other_users_cannot_read_or_change_a_reminder(self):
        reminder = Reminder.objects.create(user=self.other, kind='expiration', title='Private reminder', due_date=self.today)
        self.assertEqual(self.notices(), [])
        self.assertEqual(self.client.get(reverse('edit_reminder', args=[reminder.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('remove_reminder', args=[reminder.pk])).status_code, 404)
        self.assertEqual(self.mobile.post(
            reverse('mobile_reminder_dismiss', args=[reminder.pk]), {'key': 'irrelevant'},
        ).status_code, 404)
        self.assertTrue(Reminder.objects.filter(pk=reminder.pk).exists())

    @patch('home.reminders.timezone.localdate')
    def test_mobile_can_manage_saved_reminders_across_web_and_logbook(self, localdate):
        localdate.return_value = self.today
        collection = reverse('mobile_manage_reminders')
        response = self.mobile.post(collection, {
            'title': 'BFR', 'kind': 'expiration', 'due_date': '2026-12-31',
            'target_hours': None, 'user': self.other.pk,
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        record = response.json()
        self.assertEqual(record['due_date'], '2026-12-31')
        self.assertEqual(self.mobile.get(collection).json(), {'reminders': [record]})
        self.assertEqual(self.notices(), [])
        self.assertContains(self.client.get(reverse('manage_reminders')), 'BFR')
        self.assertEqual(Reminder.objects.get(pk=record['id']).user, self.user)

        detail = reverse('mobile_manage_reminder', args=[record['id']])
        localdate.return_value = date(2026, 12, 20)
        notice, = self.notices()
        self.mobile.post(reverse('mobile_reminder_dismiss', args=[record['id']]), {'key': notice['key']})
        self.assertEqual(self.mobile.get(collection).json(), {'reminders': [record]})
        update = {'title': 'BFR updated', 'kind': 'expiration', 'due_date': record['due_date']}
        self.assertEqual(self.mobile.put(detail, update, format='json').status_code, 200)
        self.assertEqual(self.notices(), [])

        Total.objects.filter(user=self.user, total='All').update(total_time=500)
        update = {'title': 'First 500 hours', 'kind': 'flight_time', 'target_hours': '500.0', 'due_date': None}
        response = self.mobile.put(detail, update, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNone(response.json()['due_date'])
        self.assertEqual(response.json()['target_hours'], '500.0')
        self.assertEqual(Reminder.objects.get(pk=record['id']).dismissed_key, '')
        self.assertEqual(self.notices()[0]['title'], 'First 500 hours')

        self.assertEqual(self.mobile.delete(detail).status_code, 204)
        self.assertEqual(self.mobile.get(collection).json(), {'reminders': []})
        self.assertEqual(self.notices(), [])

    def test_mobile_management_validates_input_and_requires_ownership(self):
        collection = reverse('mobile_manage_reminders')
        for kind, value, field in [
            ('expiration', '2026-02-30', 'due_date'),
            ('expiration', ['2026-11-30'], 'due_date'),
            ('flight_time', '0.0', 'target_hours'),
            ('flight_time', '50.01', 'target_hours'),
        ]:
            with self.subTest(kind=kind, value=value):
                response = self.mobile.post(collection, {'title': 'Test', 'kind': kind, field: value}, format='json')
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())
        self.assertFalse(Reminder.objects.exists())

        private = Reminder.objects.create(user=self.other, title='Private', kind='expiration', due_date=self.today)
        detail = reverse('mobile_manage_reminder', args=[private.pk])
        self.assertEqual(self.mobile.get(collection).json(), {'reminders': []})
        self.assertEqual(self.mobile.put(detail, {
            'title': 'Changed', 'kind': 'expiration', 'due_date': '2026-12-31',
        }, format='json').status_code, 404)
        self.assertEqual(self.mobile.delete(detail).status_code, 404)
        self.assertTrue(Reminder.objects.filter(pk=private.pk, title='Private').exists())
        self.assertIn(APIClient().get(collection).status_code, (401, 403))
