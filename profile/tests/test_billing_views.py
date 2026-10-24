from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from payments.models import BillingProvisioning


@override_settings(SECURE_SSL_REDIRECT=False)
class ProfileBillingStateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="billing_profile_user",
            email="billing-profile@example.com",
            password="testpassword123",
        )
        self.client.force_login(self.user)
        self.profile = self.user.profile

    @patch("profile.views.stripe.checkout.Session.create")
    def test_new_user_sees_pending_without_stripe_requests(self, checkout):
        response = self.client.get(reverse("profile"))

        self.assertContains(response, "Your trial is being set up.")
        self.assertTrue(response.context["billing_pending"])
        self.assertFalse(response.context["passed_end_date"])
        self.assertNotContains(response, 'id="monthly"')
        self.assertNotContains(response, "redirectToCheckout")
        self.assertNotContains(response, "Subscription active")
        checkout.assert_not_called()

    @patch("profile.views.stripe.checkout.Session.create")
    def test_partially_provisioned_user_does_not_contact_stripe(self, checkout):
        self.profile.customer_id = "cus_partial"
        self.profile.save(update_fields=["customer_id"])
        BillingProvisioning.objects.create(
            user=self.user, status=BillingProvisioning.Status.PROCESSING,
        )

        response = self.client.get(reverse("profile"))

        self.assertContains(response, "Your trial is being set up.")
        checkout.assert_not_called()

    @patch("profile.views.stripe.checkout.Session.create")
    def test_failed_provisioning_remains_accessible_without_checkout(self, checkout):
        BillingProvisioning.objects.create(
            user=self.user,
            status=BillingProvisioning.Status.FAILED,
            outcome_uncertain=True,
        )

        response = self.client.get(reverse("profile"))

        self.assertContains(response, "Your trial is being set up.")
        self.assertContains(response, "contact support")
        checkout.assert_not_called()

    @patch("profile.views.stripe.checkout.Session.create")
    def test_ready_profile_uses_own_customer_in_both_modes(self, checkout):
        self.profile.customer_id = "cus_current_user"
        self.profile.subscription_id = "sub_current_user"
        self.profile.end_date = date.today() + timedelta(days=14)
        self.profile.trial = True
        self.profile.save()
        checkout.return_value = SimpleNamespace(id="cs_test_profile")

        for debug in (True, False):
            with self.subTest(debug=debug), override_settings(DEBUG=debug):
                checkout.reset_mock()
                response = self.client.get(reverse("profile"))

                self.assertContains(response, "Free trial ends")
                self.assertFalse(response.context["billing_pending"])
                self.assertEqual(checkout.call_count, 2)
                for call in checkout.call_args_list:
                    self.assertEqual(call.kwargs["customer"], "cus_current_user")

    @patch("profile.views.stripe.checkout.Session.create")
    def test_free_access_does_not_require_billing(self, checkout):
        self.profile.free_access = True
        self.profile.save(update_fields=["free_access"])

        response = self.client.get(reverse("profile"))

        self.assertContains(response, "You have free access")
        self.assertNotContains(response, "Your trial is being set up.")
        self.assertNotContains(response, "redirectToCheckout")
        checkout.assert_not_called()
