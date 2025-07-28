# accounts/tests/test_urls.py

from django.test import SimpleTestCase
from django.urls import reverse, resolve
from accounts.views import (
    UserUpdateView, EmailView, ConnectionsView, PasswordSetView,
    PasswordChangeView, PasswordResetView, PasswordResetDoneView,
    PasswordResetFromKeyView
)
from allauth.account.views import PasswordResetFromKeyDoneView as AllauthPasswordResetFromKeyDoneView


class TestAccountsURLs(SimpleTestCase):

    def test_user_update_url_resolves(self):
        url = reverse('user_update', kwargs={'pk': 1})
        self.assertEqual(resolve(url).func.view_class, UserUpdateView)

    def test_account_email_url_resolves(self):
        url = reverse('account_email')
        self.assertEqual(resolve(url).func.view_class, EmailView)

    # def test_social_connections_url_resolves(self):
    #     url = reverse('socialaccount_connections')
    #     self.assertEqual(resolve(url).func.view_class, ConnectionsView)

    def test_password_set_url_resolves(self):
        url = reverse('account_set_passwoçrd')
        self.assertEqual(resolve(url).func.view_class, PasswordSetView)

    def test_password_change_url_resolves(self):
        url = reverse('account_change_password')
        self.assertEqual(resolve(url).func.view_class, PasswordChangeView)

    def test_password_reset_url_resolves(self):
        # NOTE: Duplicate name in your urlpatterns
        url = reverse('account_change_password')
        # Also maps to PasswordResetView
        self.assertEqual(resolve(url).func.view_class, PasswordChangeView)

    def test_password_reset_done_url_resolves(self):
        url = reverse('account_password_reset_done')
        self.assertEqual(resolve(url).func.view_class, PasswordResetDoneView)

    def test_password_reset_from_key_url_resolves(self):
        url = reverse('account_reset_password_from_key', kwargs={
                      'uidb36': 'abc123', 'key': 'key123'})
        self.assertEqual(resolve(url).func.view_class,
                         PasswordResetFromKeyView)

    def test_password_reset_from_key_done_url_resolves(self):
        url = reverse('account_reset_password_from_key_done')
        self.assertEqual(resolve(url).func.view_class,
                         AllauthPasswordResetFromKeyDoneView)
