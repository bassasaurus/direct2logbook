from unittest.mock import patch

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from kombu.exceptions import OperationalError

from accounts.tasks import send_google_welcome, send_google_connected
from accounts.signals import publish_google_welcome


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class GoogleWelcomeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='srogers', first_name='Steve', email='steve@example.com',
        )
        self.address = EmailAddress.objects.create(
            user=self.user, email=self.user.email, primary=True, verified=True,
        )

    def test_welcome_email_has_name_and_link_without_claiming_trial_is_ready(self):
        send_google_welcome.run(self.user.pk, 'http://localhost:8000/home/')
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['steve@example.com'])
        self.assertEqual(message.subject, 'Welcome to Direct2Logbook')
        self.assertIn('Hi Steve', message.body)
        self.assertIn('http://localhost:8000/home/', message.body)
        self.assertIn("We're setting up your 30-day free trial", message.body)

    def test_unverified_user_does_not_receive_welcome(self):
        self.address.verified = False
        self.address.save()
        send_google_welcome.run(self.user.pk, 'http://localhost:8000/home/')
        self.assertEqual(len(mail.outbox), 0)

    def test_connection_email_goes_to_existing_account_address(self):
        account = SocialAccount.objects.create(user=self.user, provider='google', uid='connected-user',
                                                extra_data={'email': 'different-google@example.com'})
        send_google_connected.run(self.user.pk, account.pk, 'http://localhost:8000/accounts/social/connections/')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        self.assertIn('successfully linked', mail.outbox[0].body)
        self.assertIn('If you did not make this change', mail.outbox[0].body)

    def test_disconnected_account_does_not_send_delayed_notification(self):
        account = SocialAccount.objects.create(user=self.user, provider='google', uid='removed-user')
        pk = account.pk
        account.delete()
        send_google_connected.run(self.user.pk, pk, 'http://localhost:8000/accounts/social/connections/')
        self.assertEqual(len(mail.outbox), 0)

    def test_deleted_user_task_is_harmless(self):
        pk = self.user.pk
        self.user.delete()
        send_google_welcome.run(pk, 'http://localhost:8000/home/')
        self.assertEqual(len(mail.outbox), 0)

    @patch('accounts.tasks.send_mail', return_value=0)
    def test_mail_not_submitted_is_reported_as_failure(self, send):
        with self.assertRaisesRegex(RuntimeError, 'did not submit'):
            send_google_welcome.run(self.user.pk, 'http://localhost:8000/home/')

    @patch('accounts.signals.send_google_welcome.apply_async', side_effect=OperationalError('offline'))
    def test_broker_failure_is_logged_without_breaking_signup(self, publish):
        with self.assertLogs('accounts.signals', level='ERROR'):
            publish_google_welcome(self.user.pk, 'http://localhost:8000/home/')
