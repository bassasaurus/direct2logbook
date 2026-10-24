import uuid
from datetime import datetime, timedelta, timezone as datetime_timezone
from django.utils import timezone
from unittest.mock import Mock, patch

from allauth.account.models import EmailAddress
from django.contrib.auth.models import User
from django.test import TestCase

from payments.models import BillingProvisioning
from payments.services import (
    BillingProvisioningError,
    inspect_stripe_provisioning,
    inspect_stripe_trial_subscriptions,
    provision_trial,
    recover_stripe_trial_subscription,
    inspect_stale_provisioning,
)

from profile.models import Profile


class TrialProvisioningTests(TestCase):

    @patch("payments.services.stripe.Subscription.create")
    @patch("payments.services.stripe.Customer.create")
    def test_provision_trial(
        self,
        mock_customer_create,
        mock_subscription_create,
    ):
        mock_customer_create.return_value = Mock(
            id="cus_test123"
        )

        mock_subscription_create.return_value = Mock(
            id="sub_test123",
            trial_end=1893456000,
        )

        user = User.objects.create_user(
            username="trialuser",
            email="trial@example.com",
            password="testpassword123",
        )

        EmailAddress.objects.update_or_create(
            user=user,
            email=user.email,
            defaults={
                "verified": True,
                "primary": True,
            },
        )

        profile = provision_trial(user)

        self.assertEqual(
            profile.customer_id,
            "cus_test123",
        )

        self.assertEqual(
            profile.subscription_id,
            "sub_test123",
        )

        self.assertTrue(profile.trial)

        mock_customer_create.assert_called_once()
        mock_subscription_create.assert_called_once()

        # Verify Stripe receives the correct provisioning metadata.
        subscription_kwargs = mock_subscription_create.call_args.kwargs

        self.assertEqual(
            subscription_kwargs["metadata"],
            {
                "direct2logbook_user_id": str(user.pk),
                "billing_provisioning_id": str(
                    BillingProvisioning.objects.get(user=user).pk
                ),
            },
        )

    @patch("payments.services.stripe.Subscription.create")
    @patch("payments.services.stripe.Customer.create")
    def test_duplicate_provisioning_does_not_create_subscription(
        self,
        mock_customer_create,
        mock_subscription_create,
    ):
        mock_customer_create.return_value = Mock(
            id="cus_test123"
        )

        mock_subscription_create.return_value = Mock(
            id="sub_test123",
            trial_end=1893456000,
        )

        user = User.objects.create_user(
            username="duplicateuser",
            email="duplicate@example.com",
            password="testpassword123",
        )

        EmailAddress.objects.update_or_create(
            user=user,
            email=user.email,
            defaults={
                "verified": True,
                "primary": True,
            },
        )

        provision_trial(user)
        provision_trial(user)

        mock_customer_create.assert_called_once()
        mock_subscription_create.assert_called_once()


class BillingProvisioningFailureTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="billing_recovery_user",
            email="billing-recovery@example.com",
            password="testpassword123",
        )

    def verify_email(self):
        EmailAddress.objects.update_or_create(
            user=self.user,
            email=self.user.email,
            defaults={
                "verified": True,
                "primary": True,
            },
        )

    def test_unverified_email_does_not_contact_stripe(self):
        with patch(
            "payments.services.stripe.Customer.create"
        ) as create_customer, patch(
            "payments.services.stripe.Subscription.create"
        ) as create_subscription:

            with self.assertRaises(BillingProvisioningError):
                provision_trial(self.user)

        create_customer.assert_not_called()
        create_subscription.assert_not_called()

        self.assertFalse(
            BillingProvisioning.objects.filter(
                user=self.user
            ).exists()
        )

    def test_customer_creation_failure_requires_reconciliation(self):
        self.verify_email()

        with patch(
            "payments.services.stripe.Customer.create",
            side_effect=TimeoutError("timeout"),
        ), patch(
            "payments.services.stripe.Subscription.create"
        ) as create_subscription:

            with self.assertRaises(BillingProvisioningError):
                provision_trial(self.user)

        record = BillingProvisioning.objects.get(user=self.user)

        self.assertEqual(
            record.status,
            BillingProvisioning.Status.FAILED,
        )
        self.assertTrue(record.outcome_uncertain)
        self.assertEqual(record.attempts, 1)
        self.assertTrue(record.customer_request_key)

        create_subscription.assert_not_called()

    def test_subscription_failure_preserves_customer_id(self):
        self.verify_email()

        with patch(
            "payments.services.stripe.Customer.create",
            return_value=Mock(id="cus_mock_recovery"),
        ), patch(
            "payments.services.stripe.Subscription.create",
            side_effect=TimeoutError("timeout"),
        ):

            with self.assertRaises(BillingProvisioningError):
                provision_trial(self.user)

        profile = Profile.objects.get(user=self.user)
        record = BillingProvisioning.objects.get(user=self.user)

        self.assertEqual(
            profile.customer_id,
            "cus_mock_recovery",
        )
        self.assertEqual(
            record.stripe_customer_id,
            "cus_mock_recovery",
        )
        self.assertFalse(profile.subscription_id)

        self.assertEqual(
            record.status,
            BillingProvisioning.Status.FAILED,
        )
        self.assertTrue(record.outcome_uncertain)

    def test_uncertain_outcome_blocks_new_stripe_requests(self):
        self.verify_email()

        with patch(
            "payments.services.stripe.Customer.create",
            side_effect=TimeoutError("timeout"),
        ):
            with self.assertRaises(BillingProvisioningError):
                provision_trial(self.user)

        with patch(
            "payments.services.stripe.Customer.create"
        ) as create_customer, patch(
            "payments.services.stripe.Subscription.create"
        ) as create_subscription:

            with self.assertRaises(BillingProvisioningError):
                provision_trial(self.user)

        create_customer.assert_not_called()
        create_subscription.assert_not_called()

        record = BillingProvisioning.objects.get(user=self.user)
        self.assertEqual(record.attempts, 1)

    def test_success_and_repeat_call_create_only_one_subscription(self):
        self.verify_email()

        trial_end = int(
            (
                datetime.now(datetime_timezone.utc)
                + timedelta(days=14)
            ).timestamp()
        )

        with patch(
            "payments.services.stripe.Customer.create",
            return_value=Mock(id="cus_mock_success"),
        ) as create_customer, patch(
            "payments.services.stripe.Subscription.create",
            return_value=Mock(
                id="sub_mock_success",
                trial_end=trial_end,
            ),
        ) as create_subscription:

            first = provision_trial(self.user)
            second = provision_trial(self.user)

        self.assertEqual(
            first.subscription_id,
            "sub_mock_success",
        )
        self.assertEqual(
            second.subscription_id,
            "sub_mock_success",
        )

        create_customer.assert_called_once()
        create_subscription.assert_called_once()

        record = BillingProvisioning.objects.get(user=self.user)

        self.assertEqual(
            record.status,
            BillingProvisioning.Status.COMPLETED,
        )
        self.assertFalse(record.outcome_uncertain)
        self.assertEqual(record.attempts, 1)
        self.assertEqual(
            record.stripe_subscription_id,
            "sub_mock_success",
        )


class StripeProvisioningInspectionTests(TestCase):
    """
    Verify that Stripe inspection retrieves existing resources
    without creating resources or changing provisioning state.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="inspection_user",
            email="inspection@example.com",
            password="testpassword123",
        )

        self.profile = Profile.objects.get(user=self.user)

        self.record = BillingProvisioning.objects.create(
            user=self.user,
        )

    @patch("payments.services.stripe.Subscription.retrieve")
    @patch("payments.services.stripe.Customer.retrieve")
    @patch("payments.services.stripe.Subscription.create")
    @patch("payments.services.stripe.Customer.create")
    def test_missing_stripe_ids_does_not_contact_stripe(
        self,
        mock_customer_create,
        mock_subscription_create,
        mock_customer_retrieve,
        mock_subscription_retrieve,
    ):
        result = inspect_stripe_provisioning(self.user)

        self.assertIsNone(result["customer_id"])
        self.assertIsNone(result["subscription_id"])
        self.assertIsNone(result["customer"])
        self.assertIsNone(result["subscription"])

        mock_customer_create.assert_not_called()
        mock_subscription_create.assert_not_called()
        mock_customer_retrieve.assert_not_called()
        mock_subscription_retrieve.assert_not_called()

    @patch("payments.services.stripe.Subscription.retrieve")
    @patch("payments.services.stripe.Customer.retrieve")
    def test_existing_customer_is_retrieved(
        self,
        mock_customer_retrieve,
        mock_subscription_retrieve,
    ):
        self.profile.customer_id = "cus_inspection123"
        self.profile.save(update_fields=["customer_id"])

        customer = Mock(id="cus_inspection123")
        mock_customer_retrieve.return_value = customer

        result = inspect_stripe_provisioning(self.user)

        self.assertEqual(
            result["customer_id"],
            "cus_inspection123",
        )
        self.assertIs(result["customer"], customer)
        self.assertIsNone(result["subscription"])

        mock_customer_retrieve.assert_called_once_with(
            "cus_inspection123"
        )
        mock_subscription_retrieve.assert_not_called()

    @patch("payments.services.stripe.Subscription.retrieve")
    @patch("payments.services.stripe.Customer.retrieve")
    def test_existing_customer_and_subscription_are_retrieved(
        self,
        mock_customer_retrieve,
        mock_subscription_retrieve,
    ):
        self.record.stripe_customer_id = "cus_record123"
        self.record.stripe_subscription_id = "sub_record123"
        self.record.save(
            update_fields=[
                "stripe_customer_id",
                "stripe_subscription_id",
            ]
        )

        customer = Mock(id="cus_record123")
        subscription = Mock(id="sub_record123")

        mock_customer_retrieve.return_value = customer
        mock_subscription_retrieve.return_value = subscription

        result = inspect_stripe_provisioning(self.user)

        self.assertEqual(
            result["customer_id"],
            "cus_record123",
        )
        self.assertEqual(
            result["subscription_id"],
            "sub_record123",
        )
        self.assertIs(result["customer"], customer)
        self.assertIs(result["subscription"], subscription)

        mock_customer_retrieve.assert_called_once_with(
            "cus_record123"
        )
        mock_subscription_retrieve.assert_called_once_with(
            "sub_record123"
        )

    @patch("payments.services.stripe.Subscription.retrieve")
    @patch("payments.services.stripe.Customer.retrieve")
    def test_uncertain_outcome_preserves_database_state(
        self,
        mock_customer_retrieve,
        mock_subscription_retrieve,
    ):
        self.record.status = BillingProvisioning.Status.FAILED
        self.record.outcome_uncertain = True
        self.record.attempts = 1
        self.record.last_error = "Stripe timeout"
        self.record.save()

        result = inspect_stripe_provisioning(self.user)

        self.assertTrue(result["requires_manual_review"])

        self.record.refresh_from_db()

        self.assertEqual(
            self.record.status,
            BillingProvisioning.Status.FAILED,
        )
        self.assertTrue(self.record.outcome_uncertain)
        self.assertEqual(self.record.attempts, 1)
        self.assertEqual(self.record.last_error, "Stripe timeout")

        mock_customer_retrieve.assert_not_called()
        mock_subscription_retrieve.assert_not_called()


class StripeTrialSubscriptionInspectionTests(TestCase):
    """
    Test read-only Stripe subscription reconciliation.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="trial_inspection_user",
            email="trial-inspection@example.com",
            password="testpassword123",
        )

        self.profile = Profile.objects.get(user=self.user)

        self.record = BillingProvisioning.objects.create(
            user=self.user,
            status=BillingProvisioning.Status.FAILED,
            outcome_uncertain=True,
            attempts=1,
        )

    def subscription(self, subscription_id, *, matches=True):
        return {
            "id": subscription_id,
            "metadata": {
                "direct2logbook_user_id": str(self.user.pk),
                "billing_provisioning_id": (
                    str(self.record.pk)
                    if matches
                    else "wrong-record"
                ),
            },
        }

    @patch("payments.services.stripe.Subscription.list")
    def test_no_customer_id_does_not_contact_stripe(
        self,
        mock_list,
    ):
        result = inspect_stripe_trial_subscriptions(self.user)

        self.assertIsNone(result["customer_id"])
        self.assertEqual(
            result["matching_subscriptions"],
            [],
        )
        self.assertTrue(result["requires_manual_review"])

        mock_list.assert_not_called()

    @patch("payments.services.stripe.Subscription.list")
    def test_one_matching_subscription(
        self,
        mock_list,
    ):
        self.profile.customer_id = "cus_trial_inspection"
        self.profile.save(update_fields=["customer_id"])

        matching = self.subscription("sub_matching")
        unrelated = self.subscription(
            "sub_other",
            matches=False,
        )

        mock_list.return_value.auto_paging_iter.return_value = iter(
            [unrelated, matching]
        )

        result = inspect_stripe_trial_subscriptions(self.user)

        self.assertEqual(
            result["customer_id"],
            "cus_trial_inspection",
        )
        self.assertEqual(
            result["matching_subscriptions"],
            [matching],
        )
        self.assertFalse(result["requires_manual_review"])

        mock_list.assert_called_once_with(
            customer="cus_trial_inspection",
            status="all",
            limit=100,
        )

    @patch("payments.services.stripe.Subscription.list")
    def test_no_matching_subscription_requires_review(
        self,
        mock_list,
    ):
        self.profile.customer_id = "cus_trial_inspection"
        self.profile.save(update_fields=["customer_id"])

        mock_list.return_value.auto_paging_iter.return_value = iter(
            [
                self.subscription(
                    "sub_unrelated",
                    matches=False,
                )
            ]
        )

        result = inspect_stripe_trial_subscriptions(self.user)

        self.assertEqual(
            result["matching_subscriptions"],
            [],
        )
        self.assertTrue(result["requires_manual_review"])

    @patch("payments.services.stripe.Subscription.list")
    def test_multiple_matches_require_review_and_preserve_state(
        self,
        mock_list,
    ):
        self.record.last_error = "Stripe timeout"
        self.record.save(update_fields=["last_error"])

        self.profile.customer_id = "cus_trial_inspection"
        self.profile.save(update_fields=["customer_id"])

        first = self.subscription("sub_first")
        second = self.subscription("sub_second")

        mock_list.return_value.auto_paging_iter.return_value = iter(
            [first, second]
        )

        with patch(
            "payments.services.stripe.Customer.create"
        ) as create_customer, patch(
            "payments.services.stripe.Subscription.create"
        ) as create_subscription:

            result = inspect_stripe_trial_subscriptions(self.user)

        self.assertEqual(
            result["matching_subscriptions"],
            [first, second],
        )
        self.assertTrue(result["requires_manual_review"])

        create_customer.assert_not_called()
        create_subscription.assert_not_called()

        self.record.refresh_from_db()
        self.profile.refresh_from_db()

        self.assertEqual(
            self.record.status,
            BillingProvisioning.Status.FAILED,
        )
        self.assertTrue(self.record.outcome_uncertain)
        self.assertEqual(self.record.attempts, 1)
        self.assertEqual(
            self.record.last_error,
            "Stripe timeout",
        )
        self.assertFalse(self.profile.subscription_id)


class StripeTrialSubscriptionRecoveryTests(TestCase):
    """
    Verify safe recovery of existing Stripe trial subscriptions.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="recovery_user",
            email="recovery@example.com",
            password="testpassword123",
        )

        self.profile = Profile.objects.get(user=self.user)
        self.profile.customer_id = "cus_recovery123"
        self.profile.save(update_fields=["customer_id"])

        self.record = BillingProvisioning.objects.create(
            user=self.user,
            status=BillingProvisioning.Status.FAILED,
            outcome_uncertain=True,
            attempts=1,
            stripe_customer_id="cus_recovery123",
        )

        self.trial_end = int(
            (
                datetime.now(datetime_timezone.utc)
                + timedelta(days=14)
            ).timestamp()
        )

    def make_subscription(self, subscription_id="sub_recovery123"):
        return {
            "id": subscription_id,
            "customer": "cus_recovery123",
            "status": "trialing",
            "trial_end": self.trial_end,
            "metadata": {
                "direct2logbook_user_id": str(self.user.pk),
                "billing_provisioning_id": str(self.record.pk),
            },
        }

    @patch("payments.services.stripe.Subscription.list")
    def test_successful_recovery(self, mock_list):
        subscription = self.make_subscription()

        mock_list.return_value.auto_paging_iter.return_value = iter(
            [subscription]
        )

        profile = recover_stripe_trial_subscription(self.user)

        self.assertEqual(
            profile.subscription_id,
            "sub_recovery123",
        )
        self.assertTrue(profile.trial)

        self.record.refresh_from_db()

        self.assertEqual(
            self.record.status,
            BillingProvisioning.Status.COMPLETED,
        )
        self.assertFalse(self.record.outcome_uncertain)
        self.assertEqual(
            self.record.stripe_subscription_id,
            "sub_recovery123",
        )

    @patch("payments.services.stripe.Subscription.list")
    def test_missing_subscription_blocks_recovery(self, mock_list):
        mock_list.return_value.auto_paging_iter.return_value = iter([])

        with self.assertRaises(BillingProvisioningError):
            recover_stripe_trial_subscription(self.user)

        self.profile.refresh_from_db()
        self.record.refresh_from_db()

        self.assertFalse(self.profile.subscription_id)
        self.assertTrue(self.record.outcome_uncertain)

    @patch("payments.services.stripe.Subscription.list")
    def test_multiple_matches_block_recovery(self, mock_list):
        mock_list.return_value.auto_paging_iter.return_value = iter(
            [
                self.make_subscription("sub_first"),
                self.make_subscription("sub_second"),
            ]
        )

        with self.assertRaises(BillingProvisioningError):
            recover_stripe_trial_subscription(self.user)

        self.profile.refresh_from_db()

        self.assertFalse(self.profile.subscription_id)

    @patch("payments.services.stripe.Subscription.list")
    def test_expired_trial_blocks_recovery(self, mock_list):
        subscription = self.make_subscription()

        subscription["trial_end"] = int(
            (
                datetime.now(datetime_timezone.utc)
                - timedelta(days=1)
            ).timestamp()
        )

        mock_list.return_value.auto_paging_iter.return_value = iter(
            [subscription]
        )

        with self.assertRaises(BillingProvisioningError):
            recover_stripe_trial_subscription(self.user)

        self.profile.refresh_from_db()

        self.assertFalse(self.profile.subscription_id)

    @patch("payments.services.stripe.Subscription.list")
    def test_conflicting_local_subscription_blocks_recovery(
        self,
        mock_list,
    ):
        self.profile.subscription_id = "sub_existing"
        self.profile.save(update_fields=["subscription_id"])

        mock_list.return_value.auto_paging_iter.return_value = iter(
            [self.make_subscription()]
        )

        with self.assertRaises(BillingProvisioningError):
            recover_stripe_trial_subscription(self.user)

        self.profile.refresh_from_db()

        self.assertEqual(
            self.profile.subscription_id,
            "sub_existing",
        )

    @patch("payments.services.stripe.Subscription.create")
    @patch("payments.services.stripe.Customer.create")
    @patch("payments.services.stripe.Subscription.list")
    def test_recovery_never_creates_stripe_resources(
        self,
        mock_list,
        mock_customer_create,
        mock_subscription_create,
    ):
        mock_list.return_value.auto_paging_iter.return_value = iter(
            [self.make_subscription()]
        )

        recover_stripe_trial_subscription(self.user)

        mock_customer_create.assert_not_called()
        mock_subscription_create.assert_not_called()


class StripeTrialSubscriptionRecoveryStateTests(TestCase):
    """
    Verify recovery refuses incompatible provisioning states.

    Rejected attempts must not modify existing billing records.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="recovery_state_user",
            email="recovery-state@example.com",
            password="testpassword123",
        )

        self.profile = Profile.objects.get(user=self.user)
        self.profile.customer_id = "cus_recovery_state"
        self.profile.save(update_fields=["customer_id"])

        self.record = BillingProvisioning.objects.create(
            user=self.user,
            status=BillingProvisioning.Status.FAILED,
            outcome_uncertain=True,
            attempts=1,
            stripe_customer_id="cus_recovery_state",
            last_error="Previous Stripe timeout",
        )

        self.trial_end = int(
            (
                datetime.now(datetime_timezone.utc)
                + timedelta(days=14)
            ).timestamp()
        )

    def make_subscription(self):
        return {
            "id": "sub_recovery_state",
            "customer": "cus_recovery_state",
            "status": "trialing",
            "trial_end": self.trial_end,
            "metadata": {
                "direct2logbook_user_id": str(self.user.pk),
                "billing_provisioning_id": str(self.record.pk),
            },
        }

    def assert_recovery_rejected(self, status, outcome_uncertain):
        """
        Confirm recovery rejects the state and preserves local records.
        """

        self.record.status = status
        self.record.outcome_uncertain = outcome_uncertain

        self.record.save(
            update_fields=[
                "status",
                "outcome_uncertain",
            ]
        )

        subscription = self.make_subscription()

        with patch(
            "payments.services.stripe.Subscription.list"
        ) as mock_list, patch(
            "payments.services.stripe.Customer.create"
        ) as mock_customer_create, patch(
            "payments.services.stripe.Subscription.create"
        ) as mock_subscription_create:

            mock_list.return_value.auto_paging_iter.return_value = iter(
                [subscription]
            )

            with self.assertRaisesRegex(
                BillingProvisioningError,
                "Provisioning state does not permit recovery",
            ):
                recover_stripe_trial_subscription(self.user)

        mock_customer_create.assert_not_called()
        mock_subscription_create.assert_not_called()

        self.profile.refresh_from_db()
        self.record.refresh_from_db()

        # The existing profile must remain unchanged.
        self.assertEqual(
            self.profile.customer_id,
            "cus_recovery_state",
        )
        self.assertFalse(self.profile.subscription_id)

        # The provisioning record must retain its original state.
        self.assertEqual(self.record.status, status)
        self.assertEqual(
            self.record.outcome_uncertain,
            outcome_uncertain,
        )
        self.assertEqual(self.record.attempts, 1)

        self.assertEqual(
            self.record.stripe_customer_id,
            "cus_recovery_state",
        )
        self.assertFalse(self.record.stripe_subscription_id)

        self.assertEqual(
            self.record.last_error,
            "Previous Stripe timeout",
        )

    def test_pending_state_blocks_recovery(self):
        self.assert_recovery_rejected(
            BillingProvisioning.Status.PENDING,
            False,
        )

    def test_processing_state_blocks_recovery(self):
        self.assert_recovery_rejected(
            BillingProvisioning.Status.PROCESSING,
            False,
        )

    def test_completed_state_blocks_recovery(self):
        self.assert_recovery_rejected(
            BillingProvisioning.Status.COMPLETED,
            False,
        )

    def test_failed_state_without_uncertainty_blocks_recovery(self):
        self.assert_recovery_rejected(
            BillingProvisioning.Status.FAILED,
            False,
        )


class WorkerOwnershipTests(TestCase):
    """Simulate ownership changes during Stripe API calls."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="ownership_user",
            email="ownership@example.com",
            password="testpassword123",
        )
        EmailAddress.objects.update_or_create(
            user=self.user,
            email=self.user.email,
            defaults={"verified": True, "primary": True},
        )

    def change_owner(self):
        import uuid

        record = BillingProvisioning.objects.get(user=self.user)
        self.original_token = record.processing_token
        self.new_token = uuid.uuid4()
        record.processing_token = self.new_token
        record.save(update_fields=["processing_token"])

    def test_ownership_change_during_customer_creation(self):
        def create_customer(**kwargs):
            self.change_owner()
            return Mock(id="cus_old_worker")

        with patch(
            "payments.services.stripe.Customer.create",
            side_effect=create_customer,
        ) as customer_create, patch(
            "payments.services.stripe.Subscription.create"
        ) as subscription_create:
            with self.assertRaisesRegex(
                BillingProvisioningError,
                "Provisioning ownership has changed",
            ):
                provision_trial(self.user)

        customer_create.assert_called_once()
        subscription_create.assert_not_called()

        record = BillingProvisioning.objects.get(user=self.user)
        profile = Profile.objects.get(user=self.user)

        self.assertEqual(record.status, BillingProvisioning.Status.PROCESSING)
        self.assertEqual(record.processing_token, self.new_token)
        self.assertNotEqual(record.processing_token, self.original_token)
        self.assertFalse(profile.customer_id)
        self.assertFalse(profile.subscription_id)

    def test_ownership_change_during_subscription_creation(self):
        def create_subscription(**kwargs):
            self.change_owner()
            return Mock(id="sub_old_worker", trial_end=1893456000)

        with patch(
            "payments.services.stripe.Customer.create",
            return_value=Mock(id="cus_ownership"),
        ), patch(
            "payments.services.stripe.Subscription.create",
            side_effect=create_subscription,
        ) as subscription_create:
            with self.assertRaisesRegex(
                BillingProvisioningError,
                "Provisioning ownership has changed",
            ):
                provision_trial(self.user)

        subscription_create.assert_called_once()

        record = BillingProvisioning.objects.get(user=self.user)
        profile = Profile.objects.get(user=self.user)

        self.assertEqual(record.status, BillingProvisioning.Status.PROCESSING)
        self.assertEqual(record.processing_token, self.new_token)
        self.assertEqual(profile.customer_id, "cus_ownership")
        self.assertFalse(profile.subscription_id)
        self.assertFalse(record.stripe_subscription_id)

    def test_stale_worker_cannot_overwrite_newer_results(self):
        def create_subscription(**kwargs):
            self.change_owner()

            Profile.objects.filter(user=self.user).update(
                subscription_id="sub_new_worker"
            )
            BillingProvisioning.objects.filter(user=self.user).update(
                stripe_subscription_id="sub_new_worker"
            )

            return Mock(id="sub_old_worker", trial_end=1893456000)

        with patch(
            "payments.services.stripe.Customer.create",
            return_value=Mock(id="cus_ownership"),
        ), patch(
            "payments.services.stripe.Subscription.create",
            side_effect=create_subscription,
        ):
            with self.assertRaises(BillingProvisioningError):
                provision_trial(self.user)

        record = BillingProvisioning.objects.get(user=self.user)
        profile = Profile.objects.get(user=self.user)

        self.assertEqual(profile.subscription_id, "sub_new_worker")
        self.assertEqual(record.stripe_subscription_id, "sub_new_worker")
        self.assertEqual(record.processing_token, self.new_token)

    def test_stale_worker_cannot_mark_newer_attempt_failed(self):
        def create_customer(**kwargs):
            self.change_owner()
            raise TimeoutError("old worker timeout")

        with patch(
            "payments.services.stripe.Customer.create",
            side_effect=create_customer,
        ):
            with self.assertRaises(BillingProvisioningError):
                provision_trial(self.user)

        record = BillingProvisioning.objects.get(user=self.user)

        self.assertEqual(record.status, BillingProvisioning.Status.PROCESSING)
        self.assertEqual(record.processing_token, self.new_token)
        self.assertFalse(record.outcome_uncertain)
        self.assertEqual(record.last_error, "")

    def test_success_clears_processing_token_and_timestamp(self):
        with patch(
            "payments.services.stripe.Customer.create",
            return_value=Mock(id="cus_success_owner"),
        ), patch(
            "payments.services.stripe.Subscription.create",
            return_value=Mock(
                id="sub_success_owner",
                trial_end=1893456000,
            ),
        ):
            provision_trial(self.user)

        record = BillingProvisioning.objects.get(user=self.user)

        self.assertEqual(record.status, BillingProvisioning.Status.COMPLETED)
        self.assertIsNone(record.processing_token)
        self.assertIsNone(record.processing_started_at)

    def test_failure_clears_processing_token_and_timestamp(self):
        with patch(
            "payments.services.stripe.Customer.create",
            side_effect=TimeoutError("Stripe timeout"),
        ):
            with self.assertRaises(BillingProvisioningError):
                provision_trial(self.user)

        record = BillingProvisioning.objects.get(user=self.user)

        self.assertEqual(record.status, BillingProvisioning.Status.FAILED)
        self.assertTrue(record.outcome_uncertain)
        self.assertIsNone(record.processing_token)
        self.assertIsNone(record.processing_started_at)


class StaleProvisioningInspectionTests(TestCase):
    """Tests for read-only detection of abandoned provisioning attempts."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="stale_user",
            email="stale@example.com",
            password="testpassword123",
        )

        self.record = BillingProvisioning.objects.create(
            user=self.user,
            status=BillingProvisioning.Status.PROCESSING,
            processing_token=uuid.uuid4(),
            processing_started_at=timezone.now() - timedelta(minutes=20),
        )

    def test_stale_attempt_is_detected(self):
        results = inspect_stale_provisioning()

        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["provisioning_id"],
            self.record.pk,
        )
        self.assertEqual(results[0]["user_id"], self.user.pk)
        self.assertTrue(results[0]["requires_reconciliation"])
        self.assertEqual(
            results[0]["processing_token"],
            self.record.processing_token,
        )
        self.assertGreaterEqual(
            results[0]["processing_duration"],
            timedelta(minutes=15),
        )

    def test_recent_attempt_is_excluded(self):
        self.record.processing_started_at = timezone.now()
        self.record.save(update_fields=["processing_started_at"])

        results = inspect_stale_provisioning()

        self.assertEqual(results, [])

    def test_missing_timestamp_is_detected(self):
        self.record.processing_started_at = None
        self.record.save(update_fields=["processing_started_at"])

        results = inspect_stale_provisioning()

        self.assertEqual(len(results), 1)
        self.assertIsNone(results[0]["processing_started_at"])
        self.assertIsNone(results[0]["processing_duration"])
        self.assertTrue(results[0]["requires_reconciliation"])

    def test_completed_and_failed_records_are_excluded(self):
        for status in (
            BillingProvisioning.Status.COMPLETED,
            BillingProvisioning.Status.FAILED,
        ):
            with self.subTest(status=status):
                self.record.status = status
                self.record.save(update_fields=["status"])

                results = inspect_stale_provisioning()

                self.assertEqual(results, [])

    def test_custom_timeout_threshold(self):
        # The record is 20 minutes old.
        self.assertEqual(
            inspect_stale_provisioning(
                stale_after=timedelta(minutes=30),
            ),
            [],
        )

        results = inspect_stale_provisioning(
            stale_after=timedelta(minutes=10),
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["provisioning_id"],
            self.record.pk,
        )

    def test_inspection_is_read_only_and_does_not_contact_stripe(self):
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
            results = inspect_stale_provisioning()

        self.assertEqual(len(results), 1)

        customer_create.assert_not_called()
        subscription_create.assert_not_called()
        customer_retrieve.assert_not_called()
        subscription_retrieve.assert_not_called()

        self.record.refresh_from_db()

        self.assertEqual(
            self.record.status,
            BillingProvisioning.Status.PROCESSING,
        )
        self.assertEqual(self.record.processing_token, original_token)
        self.assertEqual(
            self.record.processing_started_at,
            original_started_at,
        )
        self.assertEqual(self.record.updated_at, original_updated_at)
