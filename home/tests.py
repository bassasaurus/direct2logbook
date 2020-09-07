from django.test import TestCase


class TestHomeUrls(TestCase):

    def test_index_url(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200, f"/ returned {response.status_code}")

    def test_home_url_if_logged_in(self):
        response = self.client.get('home/')
        self.assertEqual(response.status_code, 200, f"/home returned {response.status_code}")
