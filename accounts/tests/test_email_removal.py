from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from allauth.account.models import EmailAddress


@override_settings(SECURE_SSL_REDIRECT=False, ACCOUNT_RATE_LIMITS=False)
class EmailRemovalTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='email-owner', email='owner@example.invalid')
        self.primary = EmailAddress.objects.create(user=self.user, email=self.user.email, verified=True, primary=True)
        self.client.force_login(self.user)
        self.url = reverse('account_email')

    def test_only_email_hides_remove_and_direct_post_cannot_delete_it(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="action_remove"')
        response = self.client.post(self.url, {'email': self.primary.email, 'action_remove': ''}, follow=True)
        self.assertContains(response, 'You cannot remove your primary')
        self.assertTrue(EmailAddress.objects.filter(pk=self.primary.pk).exists())
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, self.primary.email)

    def test_secondary_email_can_be_removed_while_primary_stays(self):
        secondary = EmailAddress.objects.create(user=self.user, email='other@example.invalid', verified=True)
        response = self.client.get(self.url)
        self.assertContains(response, 'name="action_remove"')
        response = self.client.post(self.url, {'email': secondary.email, 'action_remove': ''}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(EmailAddress.objects.filter(pk=secondary.pk).exists())
        self.assertTrue(EmailAddress.objects.filter(pk=self.primary.pk).exists())
        self.assertNotContains(response, 'name="action_remove"')

    def test_primary_stays_protected_when_other_email_exists(self):
        EmailAddress.objects.create(user=self.user, email='other@example.invalid', verified=True)
        self.client.post(self.url, {'email': self.primary.email, 'action_remove': ''})
        self.assertTrue(EmailAddress.objects.filter(pk=self.primary.pk).exists())
