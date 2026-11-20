from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from allauth.account.models import EmailAddress, EmailConfirmation
from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token

from accounts.management.commands.cleanup_unverified_signups import candidates
from flights.models import Aircraft
from payments.models import BillingProvisioning
from profile.models import Reminder
from signature.models import Signature


class UnverifiedSignupCleanupTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.user = self.make_user('abandoned')

    def make_user(self, name, age=8, **kwargs):
        user = get_user_model().objects.create_user(username=name, email=f'{name}@example.com', **kwargs)
        get_user_model().objects.filter(pk=user.pk).update(date_joined=self.now - timedelta(days=age))
        return user

    def run_cleanup(self, **kwargs):
        output = StringIO()
        call_command('cleanup_unverified_signups', stdout=output, **kwargs)
        return output.getvalue()

    def test_dry_run_preserves_account_and_reports_count(self):
        self.assertIn('Would remove 1', self.run_cleanup(dry_run=True))
        self.assertTrue(get_user_model().objects.filter(pk=self.user.pk).exists())

    def test_removes_abandoned_signup_and_related_confirmation_and_token(self):
        email = EmailAddress.objects.create(user=self.user, email=self.user.email, verified=False)
        confirmation = EmailConfirmation.objects.create(email_address=email, sent=self.now, key='unused')
        token = Token.objects.create(user=self.user)
        user_id = self.user.pk
        self.assertIn('Removed 1', self.run_cleanup())
        self.assertFalse(get_user_model().objects.filter(pk=user_id).exists())
        self.assertFalse(EmailAddress.objects.filter(pk=email.pk).exists())
        self.assertFalse(EmailConfirmation.objects.filter(pk=confirmation.pk).exists())
        self.assertFalse(Token.objects.filter(pk=token.pk).exists())
        self.assertIn('Removed 0', self.run_cleanup())

    def test_preserves_verified_accounts_including_changed_unverified_email(self):
        EmailAddress.objects.create(user=self.user, email='old@example.com', verified=True)
        EmailAddress.objects.create(user=self.user, email=self.user.email, verified=False)
        self.assertIn('Removed 0', self.run_cleanup())

    def test_preserves_recent_logged_in_staff_and_superuser_accounts(self):
        self.make_user('recent', age=6)
        self.make_user('staff', is_staff=True)
        self.make_user('superuser', is_superuser=True)
        logged_in = self.make_user('logged-in')
        get_user_model().objects.filter(pk=logged_in.pk).update(last_login=self.now)
        self.assertIn('Removed 1', self.run_cleanup())
        self.assertEqual(get_user_model().objects.count(), 4)

    def test_preserves_billing_and_free_access_even_without_verified_email(self):
        for field, value in (('customer_id', 'cus_test'), ('subscription_id', 'sub_test'), ('active', True), ('free_access', True)):
            user = self.make_user(field)
            setattr(user.profile, field, value)
            user.profile.save()
        provisioned = self.make_user('provisioned')
        BillingProvisioning.objects.create(user=provisioned)
        self.assertIn('Removed 1', self.run_cleanup())
        self.assertEqual(get_user_model().objects.count(), 5)

    def test_preserves_aircraft_and_reminders(self):
        Aircraft.objects.create(user=self.user, aircraft_type='C172', aircraft_category='A', aircraft_class='SEL', piston=True, small=True)
        reminder_user = self.make_user('reminder')
        Reminder.objects.create(user=reminder_user, title='BFR', kind=Reminder.Kind.EXPIRATION, due_date=self.now.date())
        self.assertIn('Removed 0', self.run_cleanup())

    def test_rechecks_eligibility_after_initial_scan(self):
        original = candidates
        calls = 0
        def verify_between_scans(cutoff):
            nonlocal calls
            calls += 1
            if calls == 2:
                EmailAddress.objects.create(user=self.user, email=self.user.email, verified=True)
            return original(cutoff)
        with patch('accounts.management.commands.cleanup_unverified_signups.candidates', side_effect=verify_between_scans):
            self.assertIn('skipped 1', self.run_cleanup())
        self.assertTrue(get_user_model().objects.filter(pk=self.user.pk).exists())

    def test_limit_and_invalid_options(self):
        self.make_user('second')
        self.assertIn('Removed 1', self.run_cleanup(limit=1))
        self.assertEqual(get_user_model().objects.count(), 1)
        for options in ({'days': 0}, {'days': 6}, {'limit': 0}):
            with self.assertRaises(CommandError):
                self.run_cleanup(**options)

    def test_exact_grace_boundary_is_preserved_until_older(self):
        get_user_model().objects.filter(pk=self.user.pk).update(date_joined=self.now - timedelta(days=7))
        with patch('accounts.management.commands.cleanup_unverified_signups.timezone.now', return_value=self.now):
            self.assertIn('Removed 0', self.run_cleanup())
        with patch('accounts.management.commands.cleanup_unverified_signups.timezone.now', return_value=self.now + timedelta(seconds=1)):
            self.assertIn('Removed 1', self.run_cleanup())

    def test_preserves_drawn_signature_but_not_empty_default_signature(self):
        Signature.objects.update_or_create(user=self.user, defaults={'signature': 'data:image/png;base64,example'})
        empty = self.make_user('empty-signature')
        Signature.objects.update_or_create(user=empty, defaults={'signature': ''})
        self.assertIn('Removed 1', self.run_cleanup())
        self.assertTrue(get_user_model().objects.filter(pk=self.user.pk).exists())
