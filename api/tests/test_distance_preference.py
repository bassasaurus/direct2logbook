from django.contrib.auth import get_user_model
from django.middleware.csrf import CSRF_SESSION_KEY
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from flights.mileage import format_distance


@override_settings(SECURE_SSL_REDIRECT=False)
class DistancePreferenceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='units')
        self.other = get_user_model().objects.create_user(username='other_units')
        self.url = reverse('distance_preference')
        self.mobile = APIClient()
        self.mobile.force_authenticate(self.user)

    def test_default_and_account_scoped_preference_persist(self):
        self.assertEqual(self.mobile.get(self.url).json(), {'unit': 'nm'})
        for unit in ('mi', 'km', 'nm'):
            self.assertEqual(self.mobile.put(self.url, {'unit': unit}, format='json').status_code, 200)
            self.assertEqual(self.mobile.get(self.url).json(), {'unit': unit})
        self.other.profile.refresh_from_db()
        self.assertEqual(self.other.profile.distance_unit, 'nm')

    def test_invalid_and_anonymous_updates_are_rejected(self):
        self.assertEqual(self.mobile.put(self.url, {'unit': 'meters'}, format='json').status_code, 400)
        self.assertEqual(APIClient().put(self.url, {'unit': 'km'}, format='json').status_code, 401)
        self.assertEqual(self.mobile.get(self.url).json(), {'unit': 'nm'})

    def test_web_form_requires_csrf_and_redirects_only_locally(self):
        browser = APIClient(enforce_csrf_checks=True)
        browser.force_login(self.user)
        self.assertEqual(browser.post(self.url, {'unit': 'km'}).status_code, 403)
        session = browser.session
        session[CSRF_SESSION_KEY] = 'a' * 32
        session.save()
        response = browser.post(self.url, {'unit': 'km', 'next': '/flights/by_date/'}, HTTP_X_CSRFTOKEN='a' * 32)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/flights/by_date/')
        response = browser.post(self.url, {'unit': 'mi', 'next': 'https://evil.example/'}, HTTP_X_CSRFTOKEN='a' * 32)
        self.assertEqual(response['Location'], reverse('home'))
        self.assertEqual(self.mobile.get(self.url).json(), {'unit': 'mi'})

    def test_conversion_and_grouping(self):
        self.assertEqual(format_distance(1000), '1,000.0 NM')
        self.assertEqual(format_distance(1000, 'mi'), '1,150.8 mi')
        self.assertEqual(format_distance(1000, 'km'), '1,852.0 km')
        self.assertEqual(format_distance(None), 'Unavailable')
