from datetime import date
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from flights.models import Aircraft, TailNumber, Flight, Approach
from home.currency import instrument_recency
from home.reminder_forms import RegulatoryReminderForm
from home.reminders import medical_expiration_alert, ordered_reminders, reminder_rows
from profile.models import Reminder


@override_settings(SECURE_SSL_REDIRECT=False)
class RegulatoryDateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('regulatory-dates')
        self.user.profile.active = True
        self.user.profile.save()
        self.client.force_login(self.user)
        self.mobile = APIClient(); self.mobile.force_authenticate(self.user)
        self.aircraft = Aircraft.objects.create(user=self.user, aircraft_type='C172')
        self.tail = TailNumber.objects.create(user=self.user, aircraft=self.aircraft, registration='N12345')

    def approaches(self, completed, number, hold=True):
        flight = Flight.objects.create(user=self.user, aircraft_type=self.aircraft, registration=self.tail,
                                      date=completed, route='IAH-DEN', duration=1, instrument='0.2', hold=hold)
        Approach.objects.create(flight_object=flight, approach_type='ILS', number=number)

    def test_january_and_june_approaches_drop_at_august_rollover_and_reminder_matches(self):
        self.approaches(date(2026, 1, 5), 2)
        self.approaches(date(2026, 6, 5), 4)
        reminder = Reminder.objects.create(user=self.user, title='Instrument Currency Review (IPC)', kind='ipc',
                                          ipc_completed_date=date(2025, 12, 1))
        for today, count in [(date(2026, 6, 30), 6), (date(2026, 7, 31), 6), (date(2026, 8, 1), 4)]:
            with self.subTest(today=today), patch('django.utils.timezone.localdate', return_value=today):
                snapshot = instrument_recency(self.user)
                self.assertEqual(snapshot['appr_quantity'], count)
                self.assertEqual(snapshot['appr_current_date'], date(2026, 7, 31))
                self.assertEqual(snapshot['instrument_review_date'], date(2026, 7, 31))
                self.assertEqual(snapshot['next_instrument_requirement']['approaches_needed'], 2)
                self.assertFalse(snapshot['next_instrument_requirement']['holding_needed'])
                self.assertEqual(snapshot['next_instrument_requirement']['due_date'], date(2026, 7, 31) if today.month != 8 else today)
                saved = self.mobile.get(reverse('mobile_manage_reminders')).data['reminders']
                self.assertEqual(saved[0]['due_date'], '2026-07-31')
                home = self.client.get(reverse('home'))
                self.assertEqual(home.context['instrument_review_date'], date(2026, 7, 31))
                if today.month == 8:
                    alert = next(row for row in reminder_rows(self.user) if row['id'] == reminder.pk)
                    self.assertEqual(alert['severity'], 'warning')
                    self.assertNotIn('Expired', alert['message'])
        self.approaches(date(2026, 7, 3), 2)
        with patch('django.utils.timezone.localdate', return_value=date(2026, 8, 1)):
            self.assertEqual(instrument_recency(self.user)['instrument_review_date'], date(2026, 12, 31))
            notice = next(row for row in reminder_rows(self.user) if row['id'] == reminder.pk)
            self.assertEqual(notice['message'], 'Based on logged information:\nRequired by Dec 31, 2026')
            self.assertEqual(notice['severity'], 'success')

    def test_dedicated_forms_and_month_end_dates(self):
        cases = [(RegulatoryReminderForm, {'kind': 'instructor_renewal', 'instructor_period_start': '2024-02-29'}, date(2026, 2, 28)),
                 (RegulatoryReminderForm, {'kind': 'ipc', 'ipc_completed_date': '2026-01-05'}, date(2026, 7, 31)),
                 (RegulatoryReminderForm, {'kind': 'flight_review', 'last_qualifying_date': '2024-11-05', 'completion_type': 'wings'}, date(2026, 11, 30))]
        for cls, data, expected in cases:
            form = cls(data, user=self.user)
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.save_for_user(self.user).due_date, expected)
        for page, title in [('instructor_renewal', 'FIRC'), ('ipc_reminder', 'IPC'), ('flight_review_reminder', 'BFR')]:
            response = self.client.get(reverse(page))
            self.assertContains(response, title)
            self.assertEqual(response.context['form'].fields['kind'].widget.input_type, 'select')

    def test_missing_medical_is_persistent_red_and_first(self):
        alert = medical_expiration_alert(None)
        self.assertEqual(alert['severity'], 'danger')
        self.assertNotIn('key', alert)
        rows = ordered_reminders([{'severity': 'danger', 'days_remaining': -100}, {**alert, 'medical': True}])
        self.assertTrue(rows[0]['medical'])
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Medical expiration date not recorded.')
        self.assertTrue(response.context['dashboard_reminders'][0]['medical'])
        self.assertTrue(self.mobile.get('/api/mobile/profile/').data['medical_missing'])

    def test_holding_deadline_can_arrive_before_approaches(self):
        self.approaches(date(2026, 1, 10), 0, hold=True)
        self.approaches(date(2026, 6, 10), 6, hold=False)
        with patch('django.utils.timezone.localdate', return_value=date(2026, 7, 10)):
            result = instrument_recency(self.user)['next_instrument_requirement']
            self.assertEqual(result['due_date'], date(2026, 7, 31))
            self.assertEqual(result['approaches_needed'], 0)
            self.assertTrue(result['holding_needed'])
            self.assertEqual(result['message'], 'By Jul 31, 2026: holding')

    def test_no_logged_instrument_experience_requires_six_approaches_and_holding_now(self):
        result = instrument_recency(self.user)['next_instrument_requirement']
        self.assertEqual(result['approaches_needed'], 6)
        self.assertTrue(result['holding_needed'])
        self.assertEqual(result['message'], 'Check logbook: 6 approaches, holding')

    def test_custom_title_only_and_one_integrated_dropdown(self):
        custom = RegulatoryReminderForm({'kind': 'expiration', 'title': 'My check', 'due_date': '2027-01-01'}, user=self.user)
        self.assertTrue(custom.is_valid(), custom.errors)
        self.assertEqual(custom.save_for_user(self.user).title, 'My check')
        for kind, data, expected in [
            ('flight_review', {'last_qualifying_date': '2025-01-01', 'completion_type': 'wings'}, 'BFR'),
            ('ipc', {'ipc_completed_date': '2025-01-01'}, 'IPC'),
            ('instructor_renewal', {'instructor_period_start': '2025-01-01'}, 'FIRC'),
        ]:
            form = RegulatoryReminderForm({'kind': kind, 'title': 'Unwanted duplicate title', **data}, user=self.user)
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.save_for_user(self.user).title, expected)
        form = RegulatoryReminderForm(user=self.user)
        self.assertEqual(list(form.fields)[:2], ['kind', 'title'])
        self.assertEqual(list(form.fields['kind'].choices), [('expiration', 'Custom'), ('flight_review', 'BFR'), ('ipc', 'IPC'), ('instructor_renewal', 'FIRC')])

    def test_current_until_is_shared_and_missing_hold_never_implies_current_from_approaches_alone(self):
        self.approaches(date(2026, 6, 5), 6, hold=False)
        with patch('django.utils.timezone.localdate', return_value=date(2026, 7, 1)):
            incomplete = instrument_recency(self.user)
            self.assertFalse(incomplete['ifr_current'])
            self.assertIn('holding', incomplete['instrument_status_message'])
            self.assertIsNotNone(incomplete['instrument_holding_warning'])
        self.approaches(date(2026, 6, 6), 0, hold=True)
        with patch('django.utils.timezone.localdate', return_value=date(2026, 7, 1)):
            current = instrument_recency(self.user)
            self.assertTrue(current['ifr_current'])
            self.assertEqual(current['instrument_status_message'], 'Based on logged information:\nRequired by Dec 31, 2026')
            self.assertIsNone(current['instrument_holding_warning'])
            home = self.client.get(reverse('home'))
            self.assertContains(home, 'Based on logged information:<br>Required by Dec 31, 2026')
            notice = self.mobile.get(reverse('mobile_reminders')).data['instrument_alert']
            self.assertEqual(notice['message'], current['instrument_status_message'])
            api = self.mobile.get('/api/mobile/recency/').data['instrument']
            self.assertEqual(api['status_message'], current['instrument_status_message'])

    def test_recent_ipc_can_establish_currency_but_missing_separate_hold_is_reported(self):
        obj = Reminder.objects.create(user=self.user, kind='ipc', title='IPC', ipc_completed_date=date(2026, 6, 5))
        with patch('django.utils.timezone.localdate', return_value=date(2026, 7, 1)):
            notice = next(row for row in reminder_rows(self.user) if row['id'] == obj.pk)
            self.assertIn('Based on logged information:\nRequired by Dec 31, 2026', notice['message'])
            self.assertEqual(notice['holding_warning'], 'Holding required')
            self.assertNotIn('Holding required', notice['message'])
            saved = self.mobile.get(reverse('mobile_manage_reminders')).data['reminders'][0]
            self.assertEqual(saved['status_message'], notice['message'])

    def test_automatic_ifr_alert_at_30_day_boundary_and_after_all_experience_ages_out(self):
        self.approaches(date(2026, 1, 5), 6, hold=True)
        for today, severity in [(date(2026, 6, 30), 'success'), (date(2026, 7, 1), 'warning'),
                                (date(2026, 7, 31), 'warning'), (date(2026, 8, 1), 'warning')]:
            with self.subTest(today=today), patch('django.utils.timezone.localdate', return_value=today):
                alert = self.mobile.get(reverse('mobile_reminders')).data['instrument_alert']
                self.assertEqual(alert['severity'], severity)
                if severity == 'warning':
                    self.assertIn('6 approaches, holding', alert['message'])
                home = self.client.get(reverse('home'))
                self.assertTrue(any(row.get('id') == 'instrument-currency' for row in home.context['dashboard_reminders']))
        self.assertFalse(Reminder.objects.filter(user=self.user).exists())

    def test_saved_ipc_alert_uses_same_30_day_rule_without_duplicate_derived_alert(self):
        obj = Reminder.objects.create(user=self.user, kind='ipc', title='IPC', ipc_completed_date=date(2026, 1, 5))
        with patch('django.utils.timezone.localdate', return_value=date(2026, 7, 1)):
            data = self.mobile.get(reverse('mobile_reminders')).data
            self.assertIsNone(data['instrument_alert'])
            notice = next(row for row in data['reminders'] if row['id'] == obj.pk)
            self.assertEqual(notice['severity'], 'warning')
            self.assertIn('6 approaches, holding', notice['message'])

    def test_upcoming_missing_hold_appears_in_the_same_ifr_alert(self):
        self.approaches(date(2026, 1, 5), 0, hold=True)
        self.approaches(date(2026, 6, 5), 6, hold=False)
        with patch('django.utils.timezone.localdate', return_value=date(2026, 7, 1)):
            alert = self.mobile.get(reverse('mobile_reminders')).data['instrument_alert']
            self.assertEqual(alert['severity'], 'warning')
            self.assertIn('By Jul 31, 2026: holding', alert['message'])
            self.assertNotIn('approaches', alert['message'])

    def test_no_actual_or_hood_time_excludes_automatic_ifr_even_with_approach_entries(self):
        from flights.models import Total
        self.approaches(date(2026, 6, 5), 6)
        Flight.objects.filter(user=self.user).update(instrument=None, simulated_instrument=None)
        Total.objects.filter(user=self.user).update(instrument=0, simulated_instrument=0)
        with patch('django.utils.timezone.localdate', return_value=date(2026, 7, 1)):
            snapshot = instrument_recency(self.user)
            self.assertFalse(snapshot['instrument_applicable'])
            self.assertIsNone(self.mobile.get(reverse('mobile_reminders')).data['instrument_alert'])
            self.assertFalse(self.mobile.get('/api/mobile/recency/').data['instrument']['applicable'])
            home = self.client.get(reverse('home'))
            self.assertFalse(home.context['instrument_applicable'])
        Flight.objects.filter(user=self.user).update(simulated_instrument='0.2')
        with patch('django.utils.timezone.localdate', return_value=date(2026, 7, 1)):
            self.assertTrue(instrument_recency(self.user)['instrument_applicable'])

    def test_ipc_required_after_six_additional_calendar_months_not_immediately_after_lapse(self):
        self.approaches(date(2025, 1, 5), 6, hold=True)
        for today, required in [(date(2025, 8, 1), False), (date(2026, 1, 31), False), (date(2026, 2, 1), True)]:
            with self.subTest(today=today), patch('django.utils.timezone.localdate', return_value=today):
                snapshot = instrument_recency(self.user)
                self.assertEqual(snapshot['ipc_required'], required)
                self.assertEqual(snapshot['instrument_recovery_until'], date(2026, 1, 31))
                if required:
                    self.assertEqual(snapshot['instrument_status_message'],
                                     'An IPC may be due by Jan 31, 2026.\nVerify your records.')
                else:
                    self.assertIn('Review IFR currency', snapshot['instrument_status_message'])

    def test_explicit_ipc_stays_visible_without_instrument_hour_entries(self):
        Reminder.objects.create(user=self.user, kind='ipc', title='IPC', ipc_completed_date=date(2026, 6, 5))
        with patch('django.utils.timezone.localdate', return_value=date(2026, 7, 1)):
            snapshot = instrument_recency(self.user)
            self.assertTrue(snapshot['instrument_applicable'])
            self.assertEqual(snapshot['instrument_currency_source'], 'ipc')

    def test_ifr_shortfalls_use_caution_without_changing_calculated_status(self):
        self.approaches(date(2026, 6, 5), 6, hold=False)
        with patch('django.utils.timezone.localdate', return_value=date(2026, 7, 1)):
            snapshot = instrument_recency(self.user)
            self.assertFalse(snapshot['ifr_current'])
            notice = self.mobile.get(reverse('mobile_reminders')).data['instrument_alert']
            self.assertEqual(notice['severity'], 'warning')
            self.assertEqual(notice['holding_warning'], 'Holding required')
        self.approaches(date(2026, 6, 6), 0, hold=True)
        with patch('django.utils.timezone.localdate', return_value=date(2026, 7, 1)):
            notice = self.mobile.get(reverse('mobile_reminders')).data['instrument_alert']
            self.assertEqual(notice['severity'], 'success')

    def test_recorded_ipc_with_missing_logged_tasks_also_uses_caution(self):
        obj = Reminder.objects.create(user=self.user, kind='ipc', title='IPC', ipc_completed_date=date(2026, 6, 5))
        with patch('django.utils.timezone.localdate', return_value=date(2026, 7, 1)):
            notice = next(row for row in reminder_rows(self.user) if row['id'] == obj.pk)
            self.assertEqual(notice['severity'], 'warning')
            self.assertEqual(notice['holding_warning'], 'Holding required')
