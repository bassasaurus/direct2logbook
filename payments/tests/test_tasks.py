from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.test import TestCase

from payments.services import BillingProvisioningError
from payments.tasks import provision_trial_task


User = get_user_model()


class ProvisionTrialTaskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="celery_trial_user",
            email="celery_trial@example.com",
            password="testpassword123",
        )

    def test_verified_user_calls_provisioning_service(self):
        EmailAddress.objects.update_or_create(
            user=self.user,
            email=self.user.email,
            defaults={"verified": True, "primary": True},
        )

        with patch("payments.tasks.provision_trial") as provision:
            provision_trial_task.run(self.user.pk)

        provision.assert_called_once_with(self.user)

    def test_missing_user_does_not_call_provisioning_service(self):
        missing_user_id = self.user.pk
        self.user.delete()

        with patch("payments.tasks.provision_trial") as provision:
            result = provision_trial_task.run(missing_user_id)

        self.assertIsNone(result)
        provision.assert_not_called()

    def test_unverified_email_is_rejected(self):
        EmailAddress.objects.update_or_create(
            user=self.user,
            email=self.user.email,
            defaults={"verified": False, "primary": True},
        )

        with patch(
            "payments.services.stripe.Customer.create"
        ) as customer_create, patch(
            "payments.services.stripe.Subscription.create"
        ) as subscription_create:
            with self.assertRaisesRegex(
                BillingProvisioningError,
                "Email address must be verified first",
            ):
                provision_trial_task.run(self.user.pk)

        customer_create.assert_not_called()
        subscription_create.assert_not_called()

    def test_provisioning_failure_propagates_without_retry(self):
        with patch(
            "payments.tasks.provision_trial",
            side_effect=BillingProvisioningError("Reconciliation required"),
        ) as provision, patch.object(provision_trial_task, "retry") as retry:
            with self.assertRaisesRegex(
                BillingProvisioningError,
                "Reconciliation required",
            ):
                provision_trial_task.run(self.user.pk)

        provision.assert_called_once_with(self.user)
        retry.assert_not_called()

    def test_task_configuration_disables_retries_and_results(self):
        self.assertEqual(provision_trial_task.max_retries, 0)
        self.assertTrue(provision_trial_task.ignore_result)
