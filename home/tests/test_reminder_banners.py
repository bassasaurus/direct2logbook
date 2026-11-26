from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from flights.models import Total
from home.reminders import medical_expiration_alert, ordered_reminders
from profile.models import Reminder


@override_settings(SECURE_SSL_REDIRECT=False)
class ReminderBannerTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('reminder-banner-owner')
        self.user.profile.free_access = True
        self.user.profile.active = True
        self.user.profile.save()
        self.client.force_login(self.user)
        self.mobile = APIClient(); self.mobile.force_authenticate(self.user)
        self.today = date(2026, 11, 21)
        Total.objects.filter(user=self.user, total='All').update(total_time=Decimal('100'))

    def test_medical_45_day_and_due_month_boundaries(self):
        expiry = date(2026, 11, 30)
        for today, severity, banner in [(date(2026, 10, 15), 'success', False),
                (date(2026, 10, 16), 'warning', True), (date(2026, 10, 31), 'warning', True),
                (date(2026, 11, 1), 'danger', True), (date(2026, 11, 30), 'danger', True),
                (date(2026, 12, 1), 'danger', True)]:
            with self.subTest(today=today), patch('home.reminders.timezone.localdate', return_value=today):
                result = medical_expiration_alert(expiry)
                self.assertEqual((result['severity'], result['banner']), (severity, banner))
                self.assertEqual('key' in result, severity == 'warning')

    @patch('home.reminders.timezone.localdate')
    def test_saved_reminders_home_and_mobile_share_priority_and_unreached_milestones_are_neutral(self, localdate):
        localdate.return_value = self.today
        future = Reminder.objects.create(user=self.user, kind='expiration', title='Future', due_date=self.today + timedelta(days=60))
        neutral = Reminder.objects.create(user=self.user, kind='flight_time', target_hours=110)
        orange = Reminder.objects.create(user=self.user, kind='expiration', title='Approaching', due_date=self.today + timedelta(days=20))
        red = Reminder.objects.create(user=self.user, kind='expiration', title='Expired', due_date=self.today - timedelta(days=1))
        green = Reminder.objects.create(user=self.user, kind='flight_time', target_hours=90)
        saved = self.mobile.get(reverse('mobile_manage_reminders')).json()['reminders']
        self.assertEqual([r['id'] for r in saved], [red.pk, orange.pk, future.pk, green.pk, neutral.pk])
        self.assertEqual([r['severity'] for r in saved], ['danger', 'warning', 'success', 'success', 'success'])
        home = self.client.get(reverse('home'))
        self.assertEqual([r['id'] for r in home.context['reminders']], [red.pk, orange.pk, future.pk, green.pk, neutral.pk])
        for severity in ('danger', 'warning', 'success'):
            self.assertContains(home, 'reminder-banner-' + severity)
        manage = self.client.get(reverse('manage_reminders'))
        self.assertContains(manage, 'reminder-banner-danger')
        milestones = self.client.get(reverse('manage_reminders'), {'group': 'milestones'})
        self.assertContains(milestones, 'reminder-banner-plain')
        alerts = self.mobile.get(reverse('mobile_reminders')).json()['reminders']
        self.assertEqual([r['severity'] for r in alerts], ['danger', 'warning', 'success', 'success'])

    @patch('home.reminders.timezone.localdate')
    def test_mobile_alerts_include_exact_deadlines(self, localdate):
        localdate.return_value = self.today
        due = self.today + timedelta(days=5)
        reminder = Reminder.objects.create(user=self.user, kind='expiration', title='Check', due_date=due)
        alerts = self.mobile.get(reverse('mobile_reminders')).json()['reminders']
        self.assertEqual(next(row for row in alerts if row['id'] == reminder.pk)['due_date'], due.isoformat())
        self.assertEqual(medical_expiration_alert(due)['due_date'], due)

    def test_priority_sort_is_stable_and_does_not_mutate_input(self):
        rows = [{'severity': 'neutral', 'id': 1}, {'severity': 'warning', 'id': 2},
                {'severity': 'danger', 'id': 3}, {'severity': 'warning', 'id': 4}]
        self.assertEqual([r['id'] for r in ordered_reminders(rows)], [3, 2, 4, 1])
        self.assertEqual(rows[0]['id'], 1)

    def test_dates_sort_earliest_first_inside_each_color_and_color_always_wins(self):
        rows = [{'id': 1, 'severity': 'neutral', 'completion_percent': '99.9'},
                {'id': 2, 'severity': 'danger', 'days_remaining': 4},
                {'id': 3, 'severity': 'danger', 'days_remaining': -10},
                {'id': 4, 'severity': 'warning', 'days_remaining': 22},
                {'id': 5, 'severity': 'warning', 'days_remaining': 16},
                {'id': 6, 'severity': 'success', 'days_remaining': 80},
                {'id': 7, 'severity': 'success', 'days_remaining': 40}]
        self.assertEqual([r['id'] for r in ordered_reminders(rows)], [3, 2, 5, 4, 7, 6, 1])

    @patch('home.reminders.timezone.localdate')
    def test_black_milestones_sort_by_percentage_not_absolute_hours(self, localdate):
        localdate.return_value = self.today
        low = Reminder.objects.create(user=self.user, kind='flight_time', target_hours=200)
        high = Reminder.objects.create(user=self.user, kind='flight_time', target_hours=110)
        data = self.mobile.get(reverse('mobile_manage_reminders')).json()['reminders']
        self.assertEqual([r['id'] for r in data], [high.pk, low.pk])
        self.assertEqual([r['completion_percent'] for r in data], ['90.9', '50.0'])
        self.assertEqual([r['severity'] for r in data], ['success', 'neutral'])
        web = self.client.get(reverse('manage_reminders'))
        cards = [card for card in web.context['reminder_cards'] if not card.get('medical')]
        self.assertEqual([card['reminder'].pk for card in cards], [high.pk, low.pk])

    def test_completion_rounding_cannot_mark_an_unreached_goal_complete(self):
        from home.reminders import reminder_metrics
        pending = Reminder(user=self.user, kind='flight_time', target_hours=Decimal('99999.9'))
        metrics = reminder_metrics(pending, self.today, Decimal('99999.8'))
        self.assertEqual(metrics['completion_percent'], '99.9')
        reached = reminder_metrics(pending, self.today, Decimal('100000.0'))
        self.assertEqual(reached['completion_percent'], '100.0')
        self.assertEqual(reached['hours_remaining'], '0')

    def test_groups_separate_date_reminders_from_milestones(self):
        from home.reminders import reminder_groups
        rows = [
            {'medical': True, 'title': 'Medical'},
            {'kind': 'expiration', 'title': 'IPC'},
            {'kind': 'expiration', 'title': 'BFR'},
            {'kind': 'flight_review'},
            *({'kind': kind} for kind in ('flight_time', 'time_in_type', 'crew_in_type', 'company_time')),
        ]
        groups = reminder_groups(rows)
        self.assertEqual(groups[0]['rows'], rows[:4])
        self.assertEqual(groups[1]['rows'], rows[4:])
        saved = {'reminder': Reminder(kind='expiration', title='IPC')}
        self.assertEqual(reminder_groups([saved])[0]['rows'], [saved])
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Reminders')
        self.assertContains(response, 'Milestones')

    def test_first_three_visible_and_chevron_only_for_overflow(self):
        from html.parser import HTMLParser

        class Sections(HTMLParser):
            def __init__(self, content):
                super().__init__()
                self.sections = {}
                self.active = None
                self.section_depth = 0
                self.in_details = False
                self.feed(content.decode())

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == 'section':
                    if self.active:
                        self.section_depth += 1
                    elif attrs.get('aria-label') in ('Reminders', 'Milestones'):
                        self.active = attrs['aria-label']
                        self.sections[self.active] = {'visible': 0, 'expanders': 0}
                        self.section_depth = 1
                if self.active and tag == 'details':
                    self.in_details = True
                    self.sections[self.active]['expanders'] += 1
                if self.active and tag == 'li' and not self.in_details:
                    self.sections[self.active]['visible'] += 1

            def handle_endtag(self, tag):
                if tag == 'details':
                    self.in_details = False
                if tag == 'section' and self.active:
                    self.section_depth -= 1
                    if not self.section_depth:
                        self.active = None

        for number in range(4):
            Reminder.objects.create(user=self.user, kind='expiration', title=f'Check {number}',
                                    due_date=self.today + timedelta(days=number + 1))
        for page in ('home', 'manage_reminders'):
            sections = Sections(self.client.get(reverse(page)).content).sections
            self.assertEqual(sections['Reminders'], {'visible': 3, 'expanders': 2 if page == 'home' else 1})
            if page == 'home':
                self.assertEqual(sections['Milestones']['expanders'], 0)
            else:
                milestone_sections = Sections(self.client.get(reverse(page), {'group': 'milestones'}).content).sections
                self.assertEqual(milestone_sections['Milestones']['expanders'], 0)
        Reminder.objects.filter(user=self.user).delete()
        sections = Sections(self.client.get(reverse('home')).content).sections
        self.assertEqual(sections['Reminders']['expanders'], 1)

    def test_milestone_delta_sign_and_decimal_precision(self):
        reminder = Reminder(kind='flight_time', target_hours=Decimal('11393.5'))
        for hours, expected in [('11383.5', '-10'), ('11403.5', '+10'), ('11393.5', '0'),
                                ('11393.4', '-0.1'), ('11393.6', '+0.1')]:
            self.assertEqual(reminder.milestone_progress_label(Decimal(hours)),
                             f'Total {Decimal(hours):.1f}/11393.5 | {expected}')

    @patch('django.utils.timezone.localdate', return_value=date(2026, 11, 21))
    def test_medical_stays_outside_collapsible_reminders_at_every_severity(self, localdate):
        profile = self.user.profile
        profile.first_class = True
        profile.over_40 = True
        for issue, severity in [(date(2026, 11, 1), 'success'), (date(2026, 6, 1), 'warning'),
                                (date(2026, 4, 1), 'danger')]:
            with self.subTest(severity=severity):
                profile.medical_issue_date = issue
                profile.save()
                response = self.client.get(reverse('home'))
                group = response.context['reminder_groups'][0]
                preview = [row for row in group['preview_rows'] if row.get('medical')]
                extra = [row for row in group['extra_rows'] if row.get('medical')]
                self.assertEqual(preview, [])
                self.assertEqual(extra, [])
                self.assertEqual(response.context['medical_card_notice']['severity'], severity)
                self.assertEqual(response.context['medical_card_visible'], severity != 'success')
                html = response.content.decode()
                self.assertLess(html.index('data-medical-reminder'), html.index('id="regulatory-content"'))
                self.assertContains(response, 'data-medical-reminder')
                self.assertContains(self.client.get(reverse('manage_reminders')), 'medical-certificate-card')

    @patch('django.utils.timezone.localdate')
    def test_web_medical_caution_dismissal_returns_red_and_red_can_be_snoozed(self, localdate):
        profile = self.user.profile
        profile.first_class = True
        profile.over_40 = True
        profile.medical_issue_date = date(2026, 5, 1)
        profile.save()
        localdate.return_value = date(2026, 10, 16)
        def medical_rows():
            response = self.client.get(reverse('home'))
            return [response.context['medical_card_notice']] if response.context['medical_card_visible'] else []
        warning = medical_rows()[0]
        self.assertEqual(warning['severity'], 'warning')
        self.client.post(reverse('web_reminder_action'), {'key': warning['web_action_token'], 'action': 'dismiss_caution'})
        self.assertEqual(medical_rows(), [])
        self.assertContains(self.client.get(reverse('manage_reminders')), 'Hidden until red')
        localdate.return_value = date(2026, 11, 1)
        red = medical_rows()[0]
        self.assertEqual(red['severity'], 'danger')
        self.assertEqual(self.mobile.get(reverse('mobile_reminders')).data['medical_alert']['severity'], 'danger')
        self.client.post(reverse('web_reminder_action'), {'key': red['web_action_token'], 'action': 'snooze', 'days': '3'})
        self.assertEqual(medical_rows(), [])
        localdate.return_value = date(2026, 11, 4)
        self.assertEqual(medical_rows()[0]['severity'], 'danger')
