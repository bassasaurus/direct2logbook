from datetime import date
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient
from home.flight_reviews import flight_review_due_date, flight_review_currency
from home.reminder_forms import ReminderForm
from profile.models import Reminder


class FlightReviewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='reviewer')
        self.client_api = APIClient()
        self.client_api.force_authenticate(self.user)
        self.data = {'kind': 'flight_review', 'last_qualifying_date': '2024-02-29', 'completion_type': 'wings'}

    def test_month_end_calendar_calculation(self):
        for completed, expected in [(date(2024, 2, 29), date(2026, 2, 28)),
                                    (date(2026, 11, 21), date(2028, 11, 30)),
                                    (date(2023, 4, 1), date(2025, 4, 30))]:
            self.assertEqual(flight_review_due_date(completed), expected)

    def test_all_qualifying_types_and_server_due_date(self):
        for kind in Reminder.CompletionType.values:
            form = ReminderForm({**self.data, 'completion_type': kind, 'due_date': '2099-01-01'}, user=self.user)
            self.assertTrue(form.is_valid(), form.errors)
            obj = form.save_for_user(self.user)
            self.assertEqual(obj.due_date, date(2026, 2, 28))
            self.assertEqual(obj.title, 'BFR')
            obj.delete()

    def test_required_fields_future_date_and_invalid_choice(self):
        for values in [{'last_qualifying_date': ''}, {'completion_type': ''},
                       {'completion_type': 'ordinary_training'}, {'last_qualifying_date': '2099-01-01'}]:
            self.assertFalse(ReminderForm({**self.data, **values}, user=self.user).is_valid())

    def test_api_create_update_and_ownership(self):
        url = '/api/mobile/reminders/manage/'
        response = self.client_api.post(url, self.data, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['due_date'], '2026-02-28')
        self.assertEqual(response.data['completion_type_label'], 'Completed WINGS Phase')
        pk = response.data['id']
        self.assertEqual(self.client_api.post(url, self.data, format='json').status_code, 400)
        response = self.client_api.put(f'{url}{pk}/', {**self.data, 'last_qualifying_date': '2025-04-02'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['due_date'], '2027-04-30')
        other = get_user_model().objects.create_user(username='otherreviewer')
        self.client_api.force_authenticate(other)
        self.assertEqual(self.client_api.put(f'{url}{pk}/', self.data, format='json').status_code, 404)
        self.assertIsNone(flight_review_currency(other))

    def test_currency_inclusive_and_database_uniqueness(self):
        form = ReminderForm(self.data, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        obj = form.save_for_user(self.user)
        with patch('home.flight_reviews.timezone.localdate', return_value=obj.due_date):
            self.assertTrue(flight_review_currency(self.user)['current'])
        with patch('home.flight_reviews.timezone.localdate', return_value=date(2026, 3, 1)):
            self.assertFalse(flight_review_currency(self.user)['current'])
        with self.assertRaises(IntegrityError), transaction.atomic():
            Reminder.objects.create(user=self.user, title='Duplicate', kind='flight_review',
                last_qualifying_date=date(2024, 2, 29), completion_type='wings')

    def test_currency_table_empty_and_recorded(self):
        from django.template.loader import render_to_string
        empty = render_to_string('home/flight_review_currency.html', {'flight_review_currency': None})
        self.assertIn('Add Flight Review', empty)
        form = ReminderForm(self.data, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        obj = form.save_for_user(self.user)
        table = render_to_string('home/flight_review_currency.html', {'flight_review_currency': flight_review_currency(self.user)})
        self.assertIn('Completed WINGS Phase', table)
        self.assertIn('02/28/2026', table)
        self.assertIn('table table-bordered', table)
        obj.dismissed_key = 'old'
        obj.save()
        form = ReminderForm({**self.data, 'last_qualifying_date': '2025-01-10'}, instance=obj, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save_for_user(self.user).dismissed_key, '')
