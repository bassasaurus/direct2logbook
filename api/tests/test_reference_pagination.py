from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase
from flights.models import Aircraft, TailNumber


@override_settings(SECURE_SSL_REDIRECT=False, REST_FRAMEWORK={
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination', 'PAGE_SIZE': 5,
})
class ReferencePaginationTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='reference-pages')
        self.client.force_authenticate(self.user)
        aircraft = [Aircraft.objects.create(user=self.user, aircraft_type=f'A{i:03}') for i in range(7)]
        for i in range(7):
            TailNumber.objects.create(user=self.user, aircraft=aircraft[i], registration=f'N{i:03}')

    def test_unpaginated_references_never_advertise_missing_pages(self):
        for endpoint in ['aircraft', 'tailnumbers']:
            for query in ['', '?limit=2', '?limit=2&offset=2']:
                response = self.client.get(f'/api/{endpoint}/{query}')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data['count'], 7)
                self.assertEqual(len(response.data['results']), 7)
                self.assertIsNone(response.data['next'])
                self.assertIsNone(response.data['previous'])
