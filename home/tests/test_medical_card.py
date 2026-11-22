from datetime import date, datetime, timezone
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from home.medical_reminders import medical_generation


@override_settings(SECURE_SSL_REDIRECT=False)
class MedicalCardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('medical-card-owner')
        self.user.profile.free_access = True
        self.user.profile.active = True
        self.user.profile.first_class = True
        self.user.profile.over_40 = True
        self.user.profile.medical_issue_date = date(2026, 5, 10)
        self.user.profile.save()
        self.client.force_login(self.user)
        self.mobile = APIClient()
        self.mobile.force_authenticate(self.user)
        self.url = reverse('mobile_medical_preferences')

    @patch('django.utils.timezone.localdate')
    def test_show_card_never_changes_preferences_and_thresholds_match_api(self, today):
        for day, severity, visible in [(date(2026, 10, 15), 'success', False),
                (date(2026, 10, 16), 'warning', True), (date(2026, 11, 1), 'danger', True)]:
            today.return_value = day
            web = self.client.get(reverse('home'))
            card = self.mobile.get(reverse('mobile_reminders')).data['medical_card']
            self.assertEqual(card['severity'], severity)
            self.assertEqual(web.context['medical_card_visible'], visible)
            self.assertContains(web, 'Show Medical Certificate')
            self.assertContains(web, 'First Class')
            self.user.profile.refresh_from_db()
            self.assertEqual(self.user.profile.web_reminder_preferences, {})
            self.assertContains(self.client.get(reverse('manage_reminders')), 'medical-certificate-card')

    @patch('django.utils.timezone.localdate', return_value=date(2026, 10, 20))
    def test_phone_dismissal_hides_web_until_red_and_show_now_restores(self, today):
        result = self.mobile.put(self.url, {'caution_due': '2026-11-30'}, format='json')
        self.assertEqual(result.status_code, 200)
        web = self.client.get(reverse('home'))
        self.assertFalse(web.context['medical_card_visible'])
        self.assertContains(self.client.get(reverse('manage_reminders')), 'Hidden until red')
        self.assertContains(web, 'Show Medical Certificate')
        with patch('django.utils.timezone.localdate', return_value=date(2026, 11, 1)):
            self.assertTrue(self.client.get(reverse('home')).context['medical_card_visible'])
        self.mobile.put(self.url, {}, format='json')
        self.assertTrue(self.client.get(reverse('home')).context['medical_card_visible'])

    @patch('django.utils.timezone.localdate', return_value=date(2026, 10, 20))
    def test_web_snooze_is_available_to_phone_and_ends_at_0000z(self, today):
        web = self.client.get(reverse('home'))
        token = web.context['medical_card_notice']['web_action_token']
        self.client.post(reverse('web_reminder_action'), {'key': token, 'action': 'snooze', 'days': '7'})
        self.assertEqual(self.mobile.get(self.url).data['preference']['until'], '2026-10-27')
        self.assertFalse(self.client.get(reverse('home')).context['medical_card_visible'])
        with patch('django.utils.timezone.localdate', return_value=date(2026, 10, 27)):
            self.assertTrue(self.client.get(reverse('home')).context['medical_card_visible'])

    @patch('django.utils.timezone.localdate', return_value=date(2026, 10, 20))
    def test_edit_invalidates_older_offline_snooze_and_preserves_other_preferences(self, today):
        profile = self.user.profile
        profile.web_reminder_preferences = {'medical': {'until': '2026-10-27'}, 'ifr': {'dismissed': True}}
        profile.save()
        response = self.mobile.patch('/api/mobile/profile/', {'medical': {'over_40': True}}, format='json')
        self.assertEqual(response.status_code, 200)
        profile.refresh_from_db()
        self.assertNotIn('medical', profile.web_reminder_preferences)
        self.assertTrue(profile.web_reminder_preferences['ifr']['dismissed'])
        self.assertEqual(medical_generation(profile), 1)
        replay = self.mobile.put(self.url, {'until': '2026-10-27', 'generation': 0}, format='json')
        self.assertEqual(replay.data['preference'], {})
        self.assertEqual(replay.data['generation'], 1)

    @patch('django.utils.timezone.localdate', return_value=date(2026, 10, 20))
    def test_preferences_are_owned_and_absolute_snoozes_are_idempotent(self, today):
        for _ in range(2):
            self.assertEqual(self.mobile.put(self.url, {'until': '2026-10-27'}, format='json').data['preference']['until'], '2026-10-27')
        other = get_user_model().objects.create_user('other-medical-card-owner')
        self.mobile.force_authenticate(other)
        self.assertEqual(self.mobile.get(self.url).data['preference'], {})
        self.assertEqual(self.mobile.put(self.url, {'until': '2030-01-01'}, format='json').status_code, 400)
        self.assertEqual(self.mobile.put(self.url, {'user': self.user.pk}, format='json').status_code, 400)
        self.mobile.force_authenticate(None)
        self.assertIn(self.mobile.get(self.url).status_code, (401, 403))
