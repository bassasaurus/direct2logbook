from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.template.loader import render_to_string

from api.mobile_recency import instrument_payload
from flights.models import Aircraft, Flight, Approach, TailNumber
from home.currency import instrument_recency
from profile.models import Reminder


class InstrumentPresentationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('instrument-display')
        self.aircraft = Aircraft.objects.create(user=self.user, aircraft_type='C172', aircraft_category='A', aircraft_class='SEL')
        self.tail = TailNumber.objects.create(user=self.user, aircraft=self.aircraft, registration='N123', is_91=True)

    def ipc(self, completed):
        return Reminder.objects.create(user=self.user, kind='ipc', title='IPC', ipc_category='A', ipc_completed_date=completed)

    def approaches(self, completed, count=6, hold=True):
        flight = Flight.objects.bulk_create([Flight(user=self.user, aircraft_type=self.aircraft, registration=self.tail,
            date=completed, route='IAH-IAH', duration='1.0', instrument='.2', hold=hold)])[0]
        Approach.objects.bulk_create([Approach(flight_object=flight, approach_type='ILS', number=count)])

    def snapshot(self, today):
        with patch('django.utils.timezone.localdate', return_value=today):
            return instrument_recency(self.user, category='A')

    def test_recent_ipc_sets_month_end_expiry_without_contradictory_missing_tasks(self):
        self.ipc(date(2026, 1, 12))
        result = self.snapshot(date(2026, 3, 1))
        self.assertEqual(result['instrument_review_date'], date(2026, 7, 31))
        self.assertEqual(result['instrument_currency_source'], 'ipc')
        self.assertEqual(result['instrument_display']['status'], 'Until Jul 31, 2026')
        self.assertEqual(result['instrument_display']['approaches'], '0/6')
        self.assertEqual(result['instrument_display']['holding'], 'Not separately logged')
        self.assertEqual(instrument_payload(result)['display'], result['instrument_display'])

    def test_older_recency_cannot_shorten_ipc_period(self):
        self.ipc(date(2026, 1, 12))
        self.approaches(date(2025, 12, 15))
        result = self.snapshot(date(2026, 3, 1))
        self.assertEqual(result['instrument_review_date'], date(2026, 7, 31))
        self.assertEqual(result['instrument_display']['basis'], 'IPC')

    def test_later_recency_takes_precedence_and_dates_are_chronological(self):
        self.ipc(date(2026, 1, 12))
        self.approaches(date(2026, 3, 1), 2)
        self.approaches(date(2026, 3, 15), 4)
        result = self.snapshot(date(2026, 3, 20))
        self.assertEqual(result['instrument_review_date'], date(2026, 9, 30))
        self.assertEqual(result['instrument_currency_source'], 'recency')
        self.assertEqual(result['instrument_display']['basis'], 'Logged approaches and holding')
        self.assertEqual(result['instrument_display']['approach_dates'], ['Mar 1']*2+['Mar 15']*4)

    def test_equal_dates_prefer_recency(self):
        self.ipc(date(2026, 1, 12))
        self.approaches(date(2026, 1, 15))
        self.assertEqual(self.snapshot(date(2026, 3, 1))['instrument_currency_source'], 'recency')

    def test_expired_ipc_shows_expired_date_and_correct_next_action(self):
        self.ipc(date(2025, 1, 12))
        result = self.snapshot(date(2026, 3, 1))
        self.assertEqual(result['instrument_display']['status'], 'Expired Jul 31, 2025')
        self.assertIn('IPC may be required', result['instrument_display']['next_action'])
        self.assertNotIn('Log 6 more', result['instrument_display']['approaches'])

    def test_missing_hold_is_distinct_from_sufficient_approaches(self):
        self.approaches(date(2026, 3, 15), hold=False)
        result = self.snapshot(date(2026, 3, 20))
        self.assertFalse(result['ifr_current'])
        self.assertEqual(result['instrument_display']['holding'], 'Holding required')
        self.assertEqual(result['instrument_display']['approaches'], '6/6')

    def test_ipc_without_approaches_replaces_next_action_on_web_and_api(self):
        self.ipc(date(2026, 1, 12))
        result = self.snapshot(date(2026, 3, 1))
        summary = result['instrument_display']['ipc_summary']
        self.assertEqual(summary, {'logged_date': date(2026, 1, 12), 'expiry_date': date(2026, 7, 31)})
        html = render_to_string('home/ifr_currency.html', {**result, 'instrument_display': result['instrument_display']})
        self.assertIn('Logged Jan 12, 2026', html)
        self.assertIn('Expiry Jul 31, 2026', html)
        self.assertNotIn('Next action', html)
        self.assertNotIn('Last IPC', html)
        self.assertEqual(instrument_payload(result)['display']['ipc_summary'], summary)

    def test_approaches_keep_next_action_instead_of_ipc_summary(self):
        self.ipc(date(2026, 1, 12))
        self.approaches(date(2026, 3, 1), 2)
        result = self.snapshot(date(2026, 3, 2))
        self.assertIsNone(result['instrument_display']['ipc_summary'])
        html = render_to_string('home/ifr_currency.html', {**result, 'instrument_display': result['instrument_display']})
        self.assertIn('Next action', html)
        self.assertIn('Last IPC', html)

    def test_six_approaches_without_ipc_use_earliest_qualifying_month(self):
        self.approaches(date(2026, 5, 12), 2)
        self.approaches(date(2026, 8, 20), 4)
        result = self.snapshot(date(2026, 9, 1))
        self.assertIsNone(result['ipc_completed_date'])
        self.assertTrue(result['ifr_current'])
        self.assertEqual(result['instrument_currency_source'], 'recency')
        self.assertEqual(result['instrument_review_date'], date(2026, 11, 30))
        display = result['instrument_display']
        self.assertEqual(display['status'], 'Until Nov 30, 2026')
        self.assertEqual(display['basis'], 'Logged approaches and holding')
        self.assertIn('By Nov 30, 2026: 2 approaches', display['next_action'])
        self.assertIsNone(display['ipc_summary'])
        html = render_to_string('home/ifr_currency.html', {**result, 'instrument_display': display})
        self.assertIn('Until Nov 30, 2026', html)
        self.assertIn('By Nov 30, 2026: 2 approaches', html)
        self.assertEqual(instrument_payload(result)['display'], display)
        self.assertTrue(self.snapshot(date(2026, 11, 30))['ifr_current'])
        expired = self.snapshot(date(2026, 12, 1))
        self.assertFalse(expired['ifr_current'])
        self.assertEqual(expired['appr_quantity'], 4)
        self.assertEqual(expired['instrument_display']['status'], 'Expired Nov 30, 2026')

    def test_seventh_approach_replaces_oldest_and_extends_expiry(self):
        self.approaches(date(2026, 5, 12), 1)
        self.approaches(date(2026, 6, 20), 1)
        self.approaches(date(2026, 8, 20), 5)
        result = self.snapshot(date(2026, 9, 1))
        self.assertTrue(result['ifr_current'])
        self.assertEqual(result['appr_quantity'], 7)
        self.assertEqual(result['instrument_review_date'], date(2026, 12, 31))
        self.assertEqual(result['instrument_display']['approach_dates'], ['Jun 20'] + ['Aug 20'] * 5)

    def test_expired_ipc_does_not_block_current_logged_recency(self):
        self.ipc(date(2025, 1, 12))
        self.approaches(date(2026, 5, 12), 2)
        self.approaches(date(2026, 8, 20), 4)
        result = self.snapshot(date(2026, 9, 1))
        self.assertTrue(result['ifr_current'])
        self.assertEqual(result['instrument_currency_source'], 'recency')
        self.assertEqual(result['instrument_display']['status'], 'Until Nov 30, 2026')

    def test_earlier_holding_expiry_limits_recency_even_with_six_approaches(self):
        self.approaches(date(2026, 5, 12), 1, hold=True)
        self.approaches(date(2026, 8, 20), 6, hold=False)
        result = self.snapshot(date(2026, 9, 1))
        self.assertTrue(result['ifr_current'])
        self.assertEqual(result['appr_current_date'], date(2027, 2, 28))
        self.assertEqual(result['instrument_review_date'], date(2026, 11, 30))
        self.assertEqual(result['next_instrument_requirement']['approaches_needed'], 0)
        self.assertTrue(result['next_instrument_requirement']['holding_needed'])
