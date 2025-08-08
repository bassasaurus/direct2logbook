# profile/tests/test_views.py
from types import SimpleNamespace
import time
from unittest.mock import patch

from django.contrib.auth.models import User, Group
from django.db.models.signals import post_save
from django.test import TestCase
from django.urls import reverse

# import your signal module so we can (dis)connect the exact receiver
import profile.signal_profile as profile_signals
from profile.models import Profile


class ProfileViewsTest(TestCase):
    def setUp(self):
        # Ensure the group your signal expects exists
        Group.objects.get_or_create(name="clients")

        # Mock Stripe calls inside the signal module
        self.patcher_customer = patch(
            "profile.signal_profile.stripe.Customer.create",
            return_value=SimpleNamespace(id="cus_test")
        )
        self.patcher_subscription = patch(
            "profile.signal_profile.stripe.Subscription.create",
            return_value=SimpleNamespace(
                id="sub_test", trial_end=int(time.time()) + 14 * 24 * 3600)
        )
        self.patcher_customer.start()
        self.patcher_subscription.start()
        self.addCleanup(self.patcher_customer.stop)
        self.addCleanup(self.patcher_subscription.stop)

        # Disconnect the handler that assumes profile already exists
        try:
            post_save.disconnect(
                receiver=profile_signals.save_user_profile,
                sender=User,
            )
            # Reconnect after each test
            self.addCleanup(
                lambda: post_save.connect(
                    profile_signals.save_user_profile,
                    sender=User,
                )
            )
        except Exception:
            # If it was already disconnected, keep going
            pass

        # Create a user (this will run create_user_profile and make a Profile)
        self.user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="secret123",
        )

        # If for any reason a Profile wasn't created (signal ordering),
        # ensure we have one so views can render.
        if not hasattr(self.user, "profile"):
            Profile.objects.create(user=self.user)

        self.client.login(username="alice", password="secret123")

    def test_profile_update_view_owner_can_access(self):
        url = reverse("profile_update", args=[self.user.profile.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        # adjust if your template name differs
        self.assertTemplateUsed(resp, "profile/profile_update.html")

    def test_profile_update_view_non_owner_redirects_to_profile(self):
        # Make a second user and try to edit the first user's profile
        bob = User.objects.create_user(
            username="bob", email="bob@example.com", password="secret123"
        )
        self.client.login(username="bob", password="secret123")

        url = reverse("profile_update", args=[self.user.profile.pk])
        resp = self.client.get(url, follow=False)
        # Your OwnObjectProfileMixin is supposed to redirect to 'profile'
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.headers.get("Location"), reverse("profile"))

    def test_profile_view_renders_and_sets_context(self):
        url = reverse("profile")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        # Sanity-check a couple context bits your template likely uses
        self.assertIn("profile", resp.context)
        self.assertEqual(resp.context["profile"].user, self.user)
