from django.test import SimpleTestCase
from django.urls import reverse, resolve
from profile.views import ProfileView, ProfileUpdateView


class TestProfileURLs(SimpleTestCase):

    def test_profile_view_url_resolves(self):
        url = reverse('profile')
        self.assertEqual(resolve(url).func.view_class, ProfileView)

    def test_profile_update_view_url_resolves(self):
        url = reverse('profile_update', kwargs={'pk': 1})
        self.assertEqual(resolve(url).func.view_class, ProfileUpdateView)
