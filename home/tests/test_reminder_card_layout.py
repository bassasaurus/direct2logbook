from datetime import date
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from profile.models import Reminder


@override_settings(SECURE_SSL_REDIRECT=False)
class ReminderCardLayoutTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('card-layout-owner')
        self.user.profile.active = True
        self.user.profile.free_access = True
        self.user.profile.save()
        self.client.force_login(self.user)
        self.api = APIClient(); self.api.force_authenticate(self.user)

    @patch('django.utils.timezone.localdate', return_value=date(2026, 11, 30))
    def test_hidden_reminder_has_one_card_with_its_details_status_and_restore(self, clock):
        row = Reminder.objects.create(user=self.user, kind='expiration', title='Review documents', due_date=date(2026, 12, 20))
        response = self.api.post(reverse('mobile_regulatory_preferences'), {
            'key': f'regulatory:{row.pk}', 'action': 'dismiss', 'generation': 0,
            'due': '2026-12-20', 'severity': 'warning',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        page = self.client.get(reverse('manage_reminders'), {'group': 'regulatory'})
        self.assertContains(page, f'data-reminder-id="{row.pk}"', count=1)
        self.assertNotContains(page, 'Hidden Reminders')
        card = page.content.decode().split(f'data-reminder-id="{row.pk}"')[1].split('</li>')[0]
        for content in ('Review documents', 'Dec 20, 2026', 'Hidden until red', 'Restore', 'Edit', 'Remove'):
            self.assertIn(content, card)
        token = page.context['web_hidden_reminders'][0]['token']
        self.client.post(reverse('web_reminder_action'), {'key': token, 'action': 'restore'})
        page = self.client.get(reverse('manage_reminders'), {'group': 'regulatory'})
        self.assertContains(page, f'data-reminder-id="{row.pk}"', count=1)
        self.assertNotContains(page, 'Hidden until red')

    def test_completion_details_have_no_redundant_label(self):
        row = Reminder.objects.create(user=self.user, kind='flight_review', title='BFR',
            last_qualifying_date=date(2026, 11, 30), completion_type='wings', due_date=date(2028, 11, 30))
        page = self.client.get(reverse('manage_reminders'), {'group': 'regulatory'})
        self.assertContains(page, 'Nov 30, 2026 — Completed WINGS Phase')
        self.assertNotContains(page, 'Last recorded completion:')
        self.assertContains(page, f'data-reminder-id="{row.pk}"', count=1)
