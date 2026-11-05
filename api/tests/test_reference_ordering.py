from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from flights.models import Aircraft, TailNumber


@override_settings(SECURE_SSL_REDIRECT=False)
class ReferenceOrderingTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='reference-owner')
        self.other = get_user_model().objects.create_user(username='reference-other')
        self.client.force_authenticate(self.user)

    def test_aircraft_types_are_alphabetical_ignoring_case(self):
        for code in ['C172', 'a320', 'BE58']:
            Aircraft.objects.create(user=self.user, aircraft_type=code)
        Aircraft.objects.create(user=self.other, aircraft_type='A100')
        response = self.client.get('/api/aircraft/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['aircraft_type'] for row in response.data['results']], ['a320', 'BE58', 'C172'])

    def test_tailnumbers_are_numerical_across_aircraft_and_support_international_marks(self):
        first = Aircraft.objects.create(user=self.user, aircraft_type='A320')
        second = Aircraft.objects.create(user=self.user, aircraft_type='C172')
        registrations = ['N100', 'N10', 'N2B', 'N2A', 'N2', 'G-ABCD', 'C-FABC', 'N001', 'N-3', '9H-ABC']
        for index, registration in enumerate(registrations):
            TailNumber.objects.create(user=self.user, aircraft=first if index % 2 else second, registration=registration)
        other_aircraft = Aircraft.objects.create(user=self.other, aircraft_type='A100')
        TailNumber.objects.create(user=self.other, aircraft=other_aircraft, registration='N0')
        response = self.client.get('/api/tailnumbers/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['registration'] for row in response.data['results']],
                         ['9H-ABC', 'C-FABC', 'G-ABCD', 'N001', 'N2', 'N2A', 'N2B', 'N-3', 'N10', 'N100'])
        # Ordering aliases must not interfere with the owned detail/update querysets.
        tail = TailNumber.objects.get(user=self.user, registration='N10')
        response = self.client.patch(f'/api/tailnumbers/{tail.pk}/', {'is_91': True}, format='json')
        self.assertEqual(response.status_code, 200)
