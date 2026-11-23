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

    def test_privacy_policy_is_public(self):
        response = self.client.get(reverse('privacy_policy'), secure=True)
        self.assertContains(response, '<h1 class="mb-4">Privacy Policy</h1>', html=True)
        self.assertTemplateUsed(response, 'blocks/privacy_policy.html')

    def test_landing_page_does_not_load_retired_analytics(self):
        response = self.client.get(reverse('index'), secure=True)
        self.assertEqual(response.status_code, 200)
        for retired in ('googletagmanager.com', 'google-analytics.com', "gtag('", 'UA-156431149-1'):
            self.assertNotContains(response, retired)

    def test_public_policy_describes_each_social_signin_provider(self):
        response = self.client.get(reverse('privacy_policy'), secure=True)
        for link in ('https://policies.google.com/privacy',
                     'https://www.apple.com/legal/privacy/',
                     'https://www.facebook.com/privacy/policy/'):
            self.assertContains(response, link)
        self.assertContains(response, 'Hide My Email')
        self.assertContains(response, 'We do not use Google Analytics on the website.')
        self.assertNotContains(response, 'page includes Google Analytics code')
