from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase
from flights.models import Stat, Total


@override_settings(SECURE_SSL_REDIRECT=False)
class MobileStatsTests(APITestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username='stats-owner')
        self.other = get_user_model().objects.create_user(username='stats-other')
        Total.objects.filter(user=self.owner).delete()
        Total.objects.filter(user=self.other).delete()
        Total.objects.create(user=self.owner, total='All', total_time='1234.5', pilot_in_command='900.0')
        Total.objects.create(user=self.other, total='All', total_time='9999.9')
        Stat.objects.create(user=self.owner, aircraft_type='C172', total_time='34.5')
        Stat.objects.create(user=self.other, aircraft_type='SECRET', total_time='99.0')

    def test_requires_authentication(self):
        self.assertIn(self.client.get('/api/mobile/stats/').status_code, (401, 403))

    def test_snapshot_is_owned_complete_and_read_only(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get('/api/mobile/stats/?user_id=' + str(self.other.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['schema_version'], 1)
        self.assertTrue(response.data['downloaded_at'])
        self.assertEqual(len(response.data['totals']), 1)
        self.assertEqual(response.data['totals'][0]['total_time'], '1234.5')
        self.assertEqual(response.data['totals'][0]['pilot_in_command'], '900.0')
        self.assertEqual([row['aircraft_type'] for row in response.data['aircraft']], ['C172'])
        self.assertNotIn('user', response.data['totals'][0])
        self.assertEqual(self.client.post('/api/mobile/stats/', {}, format='json').status_code, 405)

    def test_empty_account_has_empty_lists(self):
        Stat.objects.filter(user=self.owner).delete()
        Total.objects.filter(user=self.owner).delete()
        self.client.force_authenticate(self.owner)
        response = self.client.get('/api/mobile/stats/')
        self.assertEqual(response.data['totals'], [])
        self.assertEqual(response.data['aircraft'], [])
