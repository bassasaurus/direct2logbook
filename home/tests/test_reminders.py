from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from flights.models import Aircraft, Flight, Imported, TailNumber, Total
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
    def test_medical_alert_thresholds_match_on_home_and_mobile(self, localdate):
        profile = self.user.profile
        profile.active = True
        profile.first_class = True
        profile.over_40 = True
        profile.medical_issue_date = date(2026, 5, 10)
        profile.save(update_fields=['active', 'first_class', 'over_40', 'medical_issue_date'])
        expiry = date(2026, 11, 30)
        for days, severity in [(61, None), (60, 'warning'), (31, 'warning'),
                               (30, 'danger'), (0, 'danger'), (-1, 'danger')]:
            with self.subTest(days=days):
                localdate.return_value = expiry - timedelta(days=days)
                mobile = self.mobile.get(reverse('mobile_reminders'))
                web = self.client.get(reverse('home'))
                self.assertEqual(mobile.status_code, 200)
                self.assertEqual(web.status_code, 200)
                alert = mobile.json()['medical_alert']
                self.assertEqual(web.context['medical_alert'], alert)
                if severity is None:
                    self.assertIsNone(alert)
                else:
                    self.assertEqual(alert['severity'], severity)
                    self.assertContains(web, f'class="text-{severity} mb-0"><strong>Medical certificate</strong>')
                    self.assertEqual(alert['message'], f'{"Expired" if days < 0 else "Expires"} Nov 30, 2026.')
                    self.assertContains(web, reverse('profile_update', args=[profile.pk]))

        localdate.return_value = expiry - timedelta(days=60)
        key = self.mobile.get(reverse('mobile_reminders')).json()['medical_alert']['key']
        self.assertRedirects(self.client.post(
            reverse('dismiss_dashboard_medical_warning'), {'key': key},
        ), reverse('home'))
        self.assertIsNone(self.mobile.get(reverse('mobile_reminders')).json()['medical_alert'])
        self.assertNotContains(self.client.get(reverse('home')), 'Expires Nov 30, 2026.')

        localdate.return_value = expiry - timedelta(days=30)
        dismiss_url = reverse('mobile_medical_warning_dismiss')
        red = self.mobile.post(dismiss_url, {'key': key}, format='json').json()['medical_alert']
        self.assertEqual(red['severity'], 'danger')
        self.assertNotIn('key', red)
        self.assertContains(self.client.get(reverse('home')), red['message'])

        profile.medical_issue_date = date(2026, 6, 10)
        profile.save(update_fields=['medical_issue_date'])
        localdate.return_value = date(2026, 11, 1)
        renewed = self.mobile.get(reverse('mobile_reminders')).json()['medical_alert']
        self.assertEqual(renewed['severity'], 'warning')
        self.assertNotEqual(renewed['key'], key)
        response = self.mobile.post(dismiss_url, {'key': renewed['key']}, format='json')
        self.assertEqual(response.json(), {'medical_alert': None})
        self.assertIsNone(self.client.get(reverse('home')).context['medical_alert'])

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
        self.user.profile.active = True
        self.user.profile.save(update_fields=['active'])
        Total.objects.filter(user=self.user, total='All').update(total_time=489.9)
        self.assertEqual(self.notices(), [])
        self.assertNotContains(self.client.get(reverse('home')), 'hours to go')
        Total.objects.filter(user=self.user, total='All').update(total_time=490)
        approaching, = self.notices()
        self.assertEqual(approaching['severity'], 'warning')
        self.assertIn('10.0 hours to go', approaching['message'])
        page = self.client.get(reverse('home'))
        self.assertContains(page, '10.0 hours to go. 490.0 / 500.0 total flight hours.', count=1)
        self.assertNotContains(page, 'First 500 hours')
        self.assertContains(self.client.get(reverse('manage_reminders')), '490.0 / 500.0 total flight hours')
        dismiss = reverse('mobile_reminder_dismiss', args=[reminder.pk])
        web_dismiss = reverse('dismiss_dashboard_reminder', args=[reminder.pk])
        self.assertRedirects(self.client.post(web_dismiss, {'key': approaching['key']}), reverse('home'))
        self.assertNotContains(self.client.get(reverse('home')), '10.0 hours to go')
        self.assertEqual(self.notices(), [])
        Total.objects.filter(user=self.user, total='All').update(total_time=500)
        notice, = self.notices()
        self.assertEqual(notice['severity'], 'success')
        self.assertContains(self.client.get(reverse('home')), 'You reached 500.0 total flight hours.')
        self.mobile.post(dismiss, {'key': notice['key']})
        Total.objects.filter(user=self.user, total='All').update(total_time=501)
        self.assertEqual(self.notices(), [])
        saved, = self.mobile.get(reverse('mobile_manage_reminders')).json()['reminders']
        self.assertEqual(saved['progress_label'], '501.0 / 500.0 total flight hours')

    def test_type_milestones_use_logged_and_imported_hours_for_selected_type_and_role(self):
        aircraft = Aircraft.objects.create(user=self.user, aircraft_type='A320')
        other_type = Aircraft.objects.create(user=self.user, aircraft_type='B737')
        registration = TailNumber.objects.create(user=self.user, aircraft=aircraft, registration='N320')
        Imported.objects.create(user=self.user, aircraft_type=aircraft, total_time=90, pilot_in_command=40)
        Imported.objects.create(user=self.user, aircraft_type=other_type, total_time=200, pilot_in_command=200)
        for kind, title, target, position in [
            ('time_in_type', 'A320 time', '100.0', ''),
            ('crew_in_type', 'A320 PIC', '50.0', 'pilot_in_command'),
        ]:
            response = self.mobile.post(reverse('mobile_manage_reminders'), {
                'kind': kind, 'title': title, 'aircraft': aircraft.pk,
                'crew_position': position, 'target_hours': target,
            }, format='json')
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(response.data['aircraft'], aircraft.pk)
        self.assertEqual([notice['severity'] for notice in self.notices()], ['warning', 'warning'])
        flight = Flight.objects.create(user=self.user, aircraft_type=aircraft, registration=registration,
                                       date=self.today, route='KIAH-KLAS', duration='10.0', second_in_command=True)
        time_notice, crew_notice = self.notices()
        self.assertEqual(time_notice['message'], 'You reached 100.0 hours in A320.')
        self.assertEqual(crew_notice['severity'], 'warning')
        flight.second_in_command = False
        flight.pilot_in_command = True
        flight.save()
        time_notice, crew_notice = self.notices()
        self.assertEqual(crew_notice['message'], 'You reached 50.0 PIC hours in A320.')
        response = self.mobile.post(reverse('mobile_reminder_dismiss', args=[crew_notice['id']]),
                                    {'key': crew_notice['key']}, format='json')
        self.assertEqual(response.json()['reminders'], [time_notice])
        self.assertContains(self.client.get(reverse('manage_reminders')), '50.0 PIC hours in A320')

    def test_implied_milestone_titles_are_filled_when_omitted(self):
        aircraft = Aircraft.objects.create(user=self.user, aircraft_type='A320')
        response = self.client.post(reverse('manage_reminders'), {'kind': 'flight_time', 'target_hours': '500.0'})
        self.assertRedirects(response, reverse('manage_reminders'))
        self.assertEqual(Reminder.objects.get(user=self.user, kind='flight_time').title, 'Total flight time')

        for kind, fields, title in (
            ('time_in_type', {'aircraft': aircraft.pk}, 'Time in Type'),
            ('crew_in_type', {'aircraft': aircraft.pk, 'crew_position': 'pilot_in_command'}, 'Crew Position in Type'),
            ('company_time', {'company': 'Example Air', 'company_start_date': '2026-11-02'}, 'Time at Company'),
        ):
            with self.subTest(kind=kind):
                response = self.mobile.post(reverse('mobile_manage_reminders'), {
                    'kind': kind, 'target_hours': '100.0', **fields,
                }, format='json')
                self.assertEqual(response.status_code, 201, response.data)
                self.assertEqual(response.data['title'], title)

    def test_type_milestones_require_an_owned_aircraft_and_crew_position(self):
        foreign = Aircraft.objects.create(user=self.other, aircraft_type='A320')
        payload = {'kind': 'crew_in_type', 'title': 'A320 PIC', 'target_hours': '50.0', 'aircraft': foreign.pk}
        response = self.mobile.post(reverse('mobile_manage_reminders'), payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('aircraft', response.data)
        self.assertIn('crew_position', response.data)
        self.assertFalse(Reminder.objects.exists())

    @patch('home.reminders.timezone.localdate')
    def test_company_milestone_counts_each_flight_in_period_regardless_of_crew_position(self, localdate):
        localdate.return_value = self.today
        aircraft = Aircraft.objects.create(user=self.user, aircraft_type='A320')
        tailnumber = TailNumber.objects.create(user=self.user, aircraft=aircraft, registration='N320')
        for day, role, hours in [(1, 'solo', '9.0'), (2, 'pilot_in_command', '1.0'),
                                 (5, 'second_in_command', '2.0'), (6, 'dual', '3.0')]:
            Flight.objects.create(user=self.user, aircraft_type=aircraft, registration=tailnumber,
                                  date=date(2026, 11, day), duration=hours, **{role: True})
        other_aircraft = Aircraft.objects.create(user=self.other, aircraft_type='B737')
        other_tailnumber = TailNumber.objects.create(user=self.other, aircraft=other_aircraft, registration='N737')
        Flight.objects.create(user=self.other, aircraft_type=other_aircraft, registration=other_tailnumber,
                              date=date(2026, 11, 3), duration='9.0')
        url = reverse('mobile_manage_reminders')
        payload = {'kind': 'company_time', 'title': 'Company milestone', 'company': 'Example Air',
                   'company_start_date': '2026-11-02', 'company_end_date': '2026-11-05'}
        invalid = self.mobile.post(url, {**payload, 'company_end_date': '2026-11-01',
                                         'target_hours': '3.0'}, format='json')
        self.assertEqual(invalid.status_code, 400)
        self.assertIn('company_end_date', invalid.data)

        response = self.mobile.post(url, {**payload, 'target_hours': '3.0'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['goal_label'], '3.0 hours at Example Air')
        self.assertEqual(response.data['progress_label'], '3.0 / 3.0 hours at Example Air')
        self.assertEqual(response.data['company_start_date'], '2026-11-02')
        notice, = self.notices()
        self.assertEqual(notice['message'], 'You reached 3.0 hours at Example Air.')

        detail = reverse('mobile_manage_reminder', args=[response.data['id']])
        higher_goal = {**payload, 'target_hours': '4.0'}
        self.assertEqual(self.mobile.put(detail, higher_goal, format='json').status_code, 200)
        approaching, = self.notices()
        self.assertEqual(approaching['severity'], 'warning')
        self.assertIn('1.0 hours to go', approaching['message'])
        self.assertEqual(self.mobile.put(detail, {**higher_goal, 'company_end_date': None}, format='json').status_code, 200)
        notice, = self.notices()
        self.assertEqual(notice['message'], 'You reached 4.0 hours at Example Air.')
        self.assertContains(self.client.get(reverse('manage_reminders')), 'Nov 2, 2026 – Present')

    def test_new_company_milestone_prefills_from_profile_without_overwriting_saved_company(self):
        url = reverse('manage_reminders')
        self.assertContains(self.client.get(url), 'Add a company in your profile to prefill future milestones.')
        self.user.profile.company = 'Current Air'
        self.user.profile.save(update_fields=['company'])
        self.assertEqual(self.client.get(url).context['form']['company'].value(), 'Current Air')

        reminder = Reminder.objects.create(user=self.user, kind='company_time', title='Previous job',
                                           company='Former Air', company_start_date=self.today, target_hours=500)
        edit = self.client.get(reverse('edit_reminder', args=[reminder.pk]))
        self.assertEqual(edit.context['form']['company'].value(), 'Former Air')

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
