from unittest.mock import patch

from allauth.account.models import EmailAddress
from allauth.account.signals import email_confirmed, user_signed_up
from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import RequestFactory, TestCase
from kombu.exceptions import OperationalError


class EmailConfirmedProvisioningTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="confirmed_trial_user",
            email="confirmed_trial@example.com",
            password="testpassword123",
        )
        self.email_address, _ = EmailAddress.objects.update_or_create(
            user=self.user,
            email=self.user.email,
            defaults={"verified": True, "primary": True},
        )
        self.request = RequestFactory().get("/")

    def send_confirmation(self):
        email_confirmed.send(
            sender=EmailAddress,
            request=self.request,
            email_address=self.email_address,
        )

    @patch("payments.signals.provision_trial_task.apply_async")
    def test_confirmation_queues_once_after_commit(self, delay):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.send_confirmation()
            delay.assert_not_called()

        self.assertEqual(len(callbacks), 1)
        delay.assert_called_once_with(args=(self.user.pk,), retry=False)

    @patch("payments.signals.provision_trial_task.apply_async")
    def test_rollback_discards_queued_callback(self, delay):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            with transaction.atomic():
                self.send_confirmation()
                transaction.set_rollback(True)

        self.assertEqual(callbacks, [])
        delay.assert_not_called()

    @patch("payments.signals.provision_trial_task.apply_async")
    def test_unverified_email_does_not_queue(self, delay):
        self.email_address.verified = False
        self.email_address.save(update_fields=["verified"])

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.send_confirmation()

        self.assertEqual(callbacks, [])
        delay.assert_not_called()

    @patch("payments.signals.provision_trial_task.apply_async")
    def test_signup_does_not_queue_before_confirmation(self, delay):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            user_signed_up.send(
                sender=get_user_model(),
                request=self.request,
                user=self.user,
            )

        self.assertEqual(callbacks, [])
        delay.assert_not_called()

    @patch("payments.tasks.provision_trial")
    @patch(
        "payments.signals.provision_trial_task.apply_async",
        side_effect=OperationalError("Broker unavailable"),
    )
    def test_broker_failure_preserves_verification_and_logs_user(
        self, publish, provision
    ):
        self.email_address.verified = False
        self.email_address.save(update_fields=["verified"])
        following_callback = []

        with self.assertLogs("django.payments", level="ERROR") as logs:
            with self.captureOnCommitCallbacks(execute=True):
                self.email_address.verified = True
                self.email_address.save(update_fields=["verified"])
                self.send_confirmation()
                transaction.on_commit(lambda: following_callback.append(True))

        self.email_address.refresh_from_db()
        self.assertTrue(self.email_address.verified)
        publish.assert_called_once_with(args=(self.user.pk,), retry=False)
        provision.assert_not_called()
        self.assertEqual(following_callback, [True])
        self.assertIn(f"user_id={self.user.pk}", logs.output[0])
        self.assertIn("Delivery may be uncertain", logs.output[0])

    @patch("payments.signals.provision_trial_task.apply_async")
    def test_manual_recovery_can_publish_after_broker_returns(self, publish):
        from payments.signals import publish_trial_provisioning

        publish.side_effect = OperationalError("Broker unavailable")
        with self.assertLogs("django.payments", level="ERROR"):
            with self.captureOnCommitCallbacks(execute=True):
                self.send_confirmation()

        publish.assert_called_once_with(args=(self.user.pk,), retry=False)
        publish.reset_mock(side_effect=True)

        # An operator explicitly requests recovery after inspecting billing state.
        publish_trial_provisioning(self.user.pk)

        publish.assert_called_once_with(args=(self.user.pk,), retry=False)
