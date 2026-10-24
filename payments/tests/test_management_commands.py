import uuid
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from payments.models import BillingProvisioning


User = get_user_model()


class InspectBillingProvisioningCommandTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="command_stale_user",
            email="command_stale@example.com",
            password="testpassword123",
        )

        self.record = BillingProvisioning.objects.create(
            user=self.user,
            status=BillingProvisioning.Status.PROCESSING,
            processing_token=uuid.uuid4(),
            processing_started_at=timezone.now() - timedelta(minutes=20),
        )

    def run_command(self, *args):
        output = StringIO()

        call_command(
            "inspect_billing_provisioning",
            *args,
            stdout=output,
        )

        return output.getvalue()

    def test_no_stale_records(self):
        self.record.processing_started_at = timezone.now()
        self.record.save(update_fields=["processing_started_at"])

        output = self.run_command()

        self.assertIn(
            "No potentially abandoned provisioning attempts found.",
            output,
        )

    def test_stale_record_is_reported(self):
        output = self.run_command()

        self.assertIn("Found 1 potentially abandoned", output)
        self.assertIn(f"User: {self.user.pk}", output)
        self.assertIn(f"Provisioning: {self.record.pk}", output)
        self.assertIn("Duration: 20 minutes", output)
        self.assertIn(f"Token: {self.record.processing_token}", output)
        self.assertIn("Reconciliation required: Yes", output)

    def test_custom_threshold(self):
        output = self.run_command("--minutes", "30")
        self.assertIn("No potentially abandoned", output)

        output = self.run_command("--minutes", "10")
        self.assertIn("Found 1 potentially abandoned", output)

    def test_invalid_threshold(self):
        for minutes in (0, -1):
            with self.subTest(minutes=minutes):
                with self.assertRaisesRegex(
                    CommandError,
                    "--minutes must be a positive integer",
                ):
                    self.run_command("--minutes", str(minutes))

    def test_missing_timestamp_is_reported_as_unknown(self):
        self.record.processing_started_at = None
        self.record.save(update_fields=["processing_started_at"])

        output = self.run_command()

        self.assertIn("Found 1 potentially abandoned", output)
        self.assertIn("Duration: Unknown", output)

    def test_command_is_read_only_and_does_not_contact_stripe(self):
        original_status = self.record.status
        original_token = self.record.processing_token
        original_started_at = self.record.processing_started_at
        original_updated_at = self.record.updated_at

        with patch(
            "payments.services.stripe.Customer.create"
        ) as customer_create, patch(
            "payments.services.stripe.Subscription.create"
        ) as subscription_create, patch(
            "payments.services.stripe.Customer.retrieve"
        ) as customer_retrieve, patch(
            "payments.services.stripe.Subscription.retrieve"
        ) as subscription_retrieve:
            output = self.run_command()

        self.assertIn("Found 1 potentially abandoned", output)

        customer_create.assert_not_called()
        subscription_create.assert_not_called()
        customer_retrieve.assert_not_called()
        subscription_retrieve.assert_not_called()

        self.record.refresh_from_db()

        self.assertEqual(self.record.status, original_status)
        self.assertEqual(self.record.processing_token, original_token)
        self.assertEqual(
            self.record.processing_started_at,
            original_started_at,
        )
        self.assertEqual(self.record.updated_at, original_updated_at)
