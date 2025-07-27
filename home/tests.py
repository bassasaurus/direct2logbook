from django.test import SimpleTestCase
from django.urls import reverse, resolve
from home.views import index_view, HomeView


class TestHomeURLs(SimpleTestCase):

    def test_index_url_resolves(self):
        url = reverse('index')
        self.assertEqual(resolve(url).func, index_view)

    def test_home_url_resolves(self):
        url = reverse('home')
        self.assertEqual(resolve(url).func.view_class, HomeView)
