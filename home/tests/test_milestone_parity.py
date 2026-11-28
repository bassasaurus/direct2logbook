from datetime import date
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from flights.models import Aircraft, Total
from profile.models import Reminder
from home.reminders import reminder_notice, ordered_reminders


@override_settings(SECURE_SSL_REDIRECT=False)
class MilestoneParityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('milestone-parity')
        self.user.profile.active = True
        self.user.profile.free_access = True
        self.user.profile.save()
        self.client.force_login(self.user)
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_every_kind_uses_ten_hours_and_distinguishes_plain_green_from_completed(self):
        aircraft = Aircraft.objects.create(user=self.user, aircraft_type='C172')
        for kind in ('flight_time', 'time_in_type', 'crew_in_type', 'company_time', 'flight_condition'):
            row = Reminder(user=self.user, kind=kind, target_hours=100, aircraft=aircraft,
                           crew_position='pilot_in_command', condition='pilot_in_command',
                           company='Example', company_start_date=date(2026, 1, 1))
            self.assertIsNone(reminder_notice(row, date.today(), Decimal('89.9')))
            approaching = reminder_notice(row, date.today(), Decimal('90'))
            self.assertEqual(approaching['milestone_state'], 'approaching')
            self.assertEqual(approaching['severity'], 'success')
            self.assertFalse(approaching['banner'])
            completed = reminder_notice(row, date.today(), Decimal('100'))
            self.assertTrue(completed['banner'])
            self.assertEqual(completed['milestone_state'], 'completed')
            row.dismissed_key = approaching['key'] + ':approaching'  # Older app's saved dismissal.
            self.assertIsNone(reminder_notice(row, date.today(), Decimal('100')))

    def test_dismissal_stays_hidden_through_completion_and_restore_is_shared(self):
        row = Reminder.objects.create(user=self.user, kind='flight_time', target_hours=100)
        Total.objects.filter(user=self.user, total='All').update(total_time=95)
        notice = self.api.get(reverse('mobile_reminders')).data['reminders'][0]
        home = self.client.get(reverse('home'))
        self.assertContains(home, reverse('dismiss_dashboard_reminder', args=[row.pk]))
        self.assertNotContains(home, f'id="snooze-{row.pk}"')
        profile = self.user.profile
        profile.web_reminder_preferences = {str(row.pk): {'until': '2099-01-01', 'title': 'Old snooze'}}
        profile.save(update_fields=['web_reminder_preferences'])
        self.assertEqual(len(self.client.get(reverse('home')).context['reminders']), 1)
        self.assertNotContains(self.client.get(reverse('manage_reminders'), {'group': 'milestones'}), 'Old snooze')
        self.client.post(reverse('dismiss_dashboard_reminder', args=[row.pk]), {'key': notice['key']})
        Total.objects.filter(user=self.user, total='All').update(total_time=101)
        self.assertEqual(self.api.get(reverse('mobile_reminders')).data['reminders'], [])
        self.assertEqual(self.client.get(reverse('home')).context['reminders'], [])
        manage = self.client.get(reverse('manage_reminders'), {'group': 'milestones'})
        self.assertContains(manage, 'Dismissed')
        self.assertContains(manage, reverse('restore_dashboard_reminder', args=[row.pk]))
        self.assertRedirects(self.client.post(reverse('restore_dashboard_reminder', args=[row.pk])), reverse('manage_reminders') + '?group=milestones')
        restored = self.api.get(reverse('mobile_reminders')).data['reminders'][0]
        self.assertEqual(restored['milestone_state'], 'completed')
        self.assertTrue(restored['banner'])
        self.api.post(reverse('mobile_reminder_dismiss', args=[row.pk]), {'key': restored['key']})
        self.assertEqual(self.client.get(reverse('home')).context['reminders'], [])
        edited = self.api.put(reverse('mobile_manage_reminder', args=[row.pk]), {'kind': 'flight_time', 'target_hours': '105.0'}, format='json')
        self.assertEqual(edited.status_code, 200, edited.data)
        self.assertFalse(edited.data['dismissed'])
        self.assertEqual(self.api.get(reverse('mobile_reminders')).data['reminders'][0]['milestone_state'], 'approaching')

    def test_web_shows_distant_goals_without_changing_mobile_alert_threshold(self):
        row = Reminder.objects.create(user=self.user, kind='flight_time', target_hours=5000)
        home = self.client.get(reverse('home'))
        self.assertIn(row.pk, [item['id'] for item in home.context['reminders']])
        group = next(item for item in home.context['reminder_groups'] if item['key'] == 'milestones')
        self.assertEqual(len(group['preview_rows']), 1)
        self.assertEqual(group['extra_rows'], [])
        self.assertContains(home, '>Hide</button>')
        self.assertContains(home, 'class="card reminder-banner')
        self.assertEqual(self.api.get(reverse('mobile_reminders')).data['reminders'], [])
        key = next(item['key'] for item in home.context['reminders'] if item['id'] == row.pk)
        self.client.post(reverse('dismiss_dashboard_reminder', args=[row.pk]), {'key': key})
        row.refresh_from_db()
        self.assertTrue(row.dismissed_key)
        self.assertNotIn(row.pk, [item['id'] for item in self.client.get(reverse('home')).context['reminders']])
        manage = self.client.get(reverse('manage_reminders'), {'group': 'milestones'})
        self.assertContains(manage, reverse('restore_dashboard_reminder', args=[row.pk]))
        self.client.post(reverse('restore_dashboard_reminder', args=[row.pk]))
        self.assertIn(row.pk, [item['id'] for item in self.client.get(reverse('home')).context['reminders']])

    def test_sort_is_completed_then_hours_remaining_not_percentage(self):
        rows = [dict(id=1, severity='success', milestone_state='approaching', hours_remaining='9', completion_percent='99'),
                dict(id=2, severity='success', milestone_state='completed', hours_remaining='0', completion_percent='100'),
                dict(id=3, severity='success', milestone_state='approaching', hours_remaining='2', completion_percent='50')]
        self.assertEqual([r['id'] for r in ordered_reminders(rows)], [2, 3, 1])
