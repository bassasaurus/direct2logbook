import datetime
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase
from flights.models import Aircraft, Approach, Flight, TailNumber, Total
from home.currency import instrument_recency


@override_settings(SECURE_SSL_REDIRECT=False)
class MobileRecencyTests(APITestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username='recency-owner')
        self.other = get_user_model().objects.create_user(username='recency-other')

    def flight(self, user, days=0, landings=3, approaches=6):
        aircraft, _ = Aircraft.objects.get_or_create(user=user, aircraft_type='A320', defaults={
            'aircraft_category': 'A', 'aircraft_class': 'MEL', 'requires_type': True})
        tail, _ = TailNumber.objects.get_or_create(user=user, aircraft=aircraft, registration='NREC')
        flight = Flight.objects.create(user=user, aircraft_type=aircraft, registration=tail,
                                       date=datetime.date.today() - datetime.timedelta(days=days),
                                       route='IAH-LAX', duration='2.0', landings_day=landings,
                                       landings_night=1, hold=True)
        Approach.objects.create(flight_object=flight, approach_type='ILS', number=approaches)
        return flight

    def test_requires_authentication_and_disallows_writes(self):
        self.assertIn(self.client.get('/api/mobile/recency/').status_code, (401, 403))
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.post('/api/mobile/recency/', {}).status_code, 405)

    def test_matches_owned_website_counts_and_excludes_future_and_old_flights(self):
        self.flight(self.owner)
        self.flight(self.owner, days=200, approaches=20)
        self.flight(self.owner, days=-1, approaches=30)
        self.flight(self.other, approaches=40)
        Total.objects.get_or_create(user=self.owner, total='ASES', defaults={'total_time': 0})
        self.client.force_authenticate(self.owner)
        response = self.client.get('/api/mobile/recency/?user_id=' + str(self.other.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['label'] for row in response.data['categories']], ['AMEL'])
        row = response.data['categories'][0]
        self.assertEqual(row['day'], {'count': 3, 'required': 3, 'current': True})
        self.assertFalse(row['night']['current'])
        self.assertEqual(response.data['types'][0]['label'], 'A320')
        self.assertEqual(response.data['types'][0]['day']['count'], 3)
        approaches = response.data['instrument']['approaches']
        self.assertEqual(approaches['count'], 6)
        self.assertTrue(approaches['current'])
        self.assertEqual(approaches['until'], instrument_recency(self.owner)['appr_current_date'])
        self.assertTrue(response.data['instrument']['holding']['current'])

    def test_empty_account_returns_zero_instrument_counts(self):
        self.client.force_authenticate(self.owner)
        data = self.client.get('/api/mobile/recency/').data
        self.assertEqual(data['categories'], [])
        self.assertEqual(data['types'], [])
        self.assertEqual(data['instrument']['approaches']['count'], 0)
        self.assertEqual(data['instrument']['approaches']['still_needed'], 6)
        self.assertIsNone(data['instrument']['approaches']['until'])
        self.assertFalse(data['instrument']['holding']['current'])
