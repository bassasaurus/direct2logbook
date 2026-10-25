from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(SECURE_SSL_REDIRECT=False)
class UserNameUpdateSecurityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='name_owner', first_name='Owner', last_name='Original',
        )
        self.other = get_user_model().objects.create_user(
            username='name_other', first_name='Private', last_name='Other',
        )
        self.client.force_login(self.user)
        self.own_url = reverse('user_update', args=[self.user.pk])
        self.other_url = reverse('user_update', args=[self.other.pk])

    def assert_names_unchanged(self):
        self.user.refresh_from_db()
        self.other.refresh_from_db()
        self.assertEqual((self.user.first_name, self.user.last_name), ('Owner', 'Original'))
        self.assertEqual((self.other.first_name, self.other.last_name), ('Private', 'Other'))

    def test_owner_can_view_name_form(self):
        response = self.client.get(self.own_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'profile/user_update.html')
        self.assertEqual(response.context['form'].instance.pk, self.user.pk)

    def test_owner_can_update_own_name(self):
        response = self.client.post(self.own_url, {
            'first_name': 'Updated', 'last_name': 'Name',
            'user': self.other.pk,
        })

        self.assertRedirects(response, reverse('profile'), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.other.refresh_from_db()
        self.assertEqual((self.user.first_name, self.user.last_name), ('Updated', 'Name'))
        self.assertEqual((self.other.first_name, self.other.last_name), ('Private', 'Other'))

    def test_other_users_name_form_is_not_accessible(self):
        response = self.client.get(self.other_url)

        self.assertEqual(response.status_code, 404)
        self.assert_names_unchanged()

    def test_other_users_name_cannot_be_changed(self):
        response = self.client.post(self.other_url, {
            'first_name': 'Changed', 'last_name': 'Without permission',
        })

        self.assertEqual(response.status_code, 404)
        self.assert_names_unchanged()

    def test_anonymous_get_requires_login(self):
        self.client.logout()
        response = self.client.get(self.own_url)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login', response.url)
        self.assert_names_unchanged()

    def test_anonymous_post_requires_login(self):
        self.client.logout()
        response = self.client.post(self.own_url, {
            'first_name': 'Changed', 'last_name': 'Anonymously',
        })

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login', response.url)
        self.assert_names_unchanged()
