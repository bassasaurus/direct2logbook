from datetime import date, timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from home.regulatory_preferences import hidden, key_for, apply_action
from home.reminders import web_reminder_token
from profile.models import Reminder


@override_settings(SECURE_SSL_REDIRECT=False)
class RegulatoryPreferenceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('regulatory-owner')
        self.user.profile.active = True
        self.user.profile.free_access = True
        self.user.profile.save()
        self.client.force_login(self.user)
        self.api = APIClient(); self.api.force_authenticate(self.user)
        self.row = Reminder.objects.create(user=self.user, title='Review', kind='expiration', due_date=date(2026, 12, 20))
        self.url = reverse('mobile_regulatory_preferences')
        self.clock = patch('django.utils.timezone.localdate', return_value=date(2026, 11, 30))
        self.clock.start(); self.addCleanup(self.clock.stop)

    def alert(self):
        return self.api.get(reverse('mobile_reminders')).data['regulatory_alerts'][0]

    def act(self, action, until=None, row=None):
        row = row or self.alert()
        payload = {'key': row['preference_key'], 'generation': row['preference_generation'], 'action': action,
                   'due': str(row['due_date']), 'severity': row['severity']}
        if until: payload['until'] = until
        return self.api.post(self.url, payload, format='json')

    def test_yellow_dismissal_is_shared_and_escalates_to_red(self):
        self.assertEqual(self.alert()['severity'], 'warning')
        self.assertEqual(self.act('dismiss').status_code, 200)
        self.assertNotIn(self.row.pk, [r['id'] for r in self.client.get(reverse('home')).context['dashboard_reminders']])
        self.assertContains(self.client.get(reverse('manage_reminders')), 'Hidden until red')
        with patch('django.utils.timezone.localdate', return_value=date(2026, 12, 10)):
            self.assertEqual(self.alert()['severity'], 'danger')
            self.assertIn(self.row.pk, [r['id'] for r in self.client.get(reverse('home')).context['dashboard_reminders']])

    def test_yellow_snooze_is_overridden_by_red_and_restore_is_shared(self):
        self.act('snooze', '2026-12-14')
        self.assertNotIn(self.row.pk, [r['id'] for r in self.client.get(reverse('home')).context['dashboard_reminders']])
        with patch('django.utils.timezone.localdate', return_value=date(2026, 12, 6)):
            self.assertIn(self.row.pk, [r['id'] for r in self.client.get(reverse('home')).context['dashboard_reminders']])
        self.act('restore')
        self.assertEqual(self.api.get(self.url).data['preferences'], {})

    def test_red_dismissal_returns_at_0000z_after_30_days_and_replay_does_not_extend(self):
        with patch('django.utils.timezone.localdate', return_value=date(2026, 12, 21)):
            row = self.alert()
            self.assertEqual(self.act('dismiss', '2027-01-20', row).status_code, 200)
        with patch('django.utils.timezone.localdate', return_value=date(2027, 1, 19)):
            self.act('dismiss', '2027-01-20', row)
            self.assertNotIn(self.row.pk, [r['id'] for r in self.client.get(reverse('home')).context['dashboard_reminders']])
        with patch('django.utils.timezone.localdate', return_value=date(2027, 1, 20)):
            self.assertIn(self.row.pk, [r['id'] for r in self.client.get(reverse('home')).context['dashboard_reminders']])

    def test_web_actions_are_reflected_in_phone_and_restore(self):
        row = self.alert()
        profile = self.user.profile; profile.refresh_from_db()
        token = web_reminder_token(self.user, row)
        self.client.post(reverse('web_reminder_action'), {'key': token, 'action': 'snooze', 'days': '3'})
        self.assertEqual(self.api.get(self.url).data['preferences'][row['preference_key']]['until'], '2026-12-03')
        self.client.post(reverse('web_reminder_action'), {'key': token, 'action': 'restore'})
        self.assertEqual(self.api.get(self.url).data['preferences'], {})
        self.assertContains(self.client.get(reverse('home')), 'Snooze')

    def test_edit_clears_choice_and_rejects_older_offline_operation(self):
        row = self.alert()
        self.act('dismiss', row=row)
        response = self.api.put(reverse('mobile_manage_reminder', args=[self.row.pk]),
            {'kind': 'expiration', 'title': 'Edited', 'due_date': '2026-12-20'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.act('dismiss', row=row)
        state = self.api.get(self.url).data
        self.assertEqual(state['preferences'], {})
        self.assertEqual(state['generations'][row['preference_key']], 1)

    def test_account_isolation_validation_and_category_separation(self):
        self.assertEqual(self.act('snooze', '2026-12-15').status_code, 400)
        other = get_user_model().objects.create_user('regulatory-other')
        self.api.force_authenticate(other)
        payload = {'key': 'regulatory:' + str(self.row.pk), 'action': 'dismiss', 'generation': 0,
                   'due': '2026-12-20', 'severity': 'warning'}
        self.assertEqual(self.api.post(self.url, payload, format='json').data['preferences'], {})
        self.assertNotEqual(key_for({'kind': 'ipc', 'category': 'airplane'}), key_for({'kind': 'ipc', 'category': 'helicopter'}))
        self.api.force_authenticate(None)
        self.assertIn(self.api.get(self.url).status_code, (401, 403))

    def test_pure_escalation_and_midnight_rules(self):
        yellow = {'kind': 'expiration', 'due_date': date(2026, 12, 20), 'severity': 'warning'}
        pref = {'due': '2026-12-20', 'severity': 'warning', 'mode': 'until', 'until': '2026-12-03'}
        self.assertTrue(hidden(pref, yellow, date(2026, 12, 2)))
        self.assertFalse(hidden(pref, yellow, date(2026, 12, 3)))
        self.assertFalse(hidden(pref, {**yellow, 'severity': 'danger'}, date(2026, 12, 2)))


    def test_deletion_clears_preferences_and_old_offline_actions_cannot_restore_them(self):
        row = self.alert()
        self.act('dismiss', row=row)
        result = self.api.delete(reverse('mobile_manage_reminder', args=[self.row.pk]))
        self.assertEqual(result.status_code, 204)
        self.act('dismiss', row=row)
        self.assertEqual(self.api.get(self.url).data['preferences'], {})
