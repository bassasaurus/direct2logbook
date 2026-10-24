from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import TestCase

from flights.models import Total
from profile.models import Profile


class UserProfileSignalTests(TestCase):

    def setUp(self):
        Group.objects.get_or_create(name='clients')

    @patch('stripe.Subscription.create')
    @patch('stripe.Customer.create')
    def test_creating_user_creates_local_records_without_stripe(
        self,
        mock_customer,
        mock_subscription,
    ):
        user = User.objects.create_user(
            username='testpilot',
            email='testpilot@example.com',
            password='testpassword123',
        )

        self.assertTrue(
            Profile.objects.filter(user=user).exists()
        )

        self.assertTrue(
            Total.objects.filter(
                user=user,
                total='All',
            ).exists()
        )

        self.assertTrue(
            user.groups.filter(name='clients').exists()
        )

        mock_customer.assert_not_called()
        mock_subscription.assert_not_called()

    def test_saving_existing_user_does_not_duplicate_records(self):
        user = User.objects.create_user(
            username='testpilot2',
            email='testpilot2@example.com',
            password='testpassword123',
        )

        user.first_name = 'Updated'
        user.save()

        self.assertEqual(
            Profile.objects.filter(user=user).count(),
            1,
        )

        self.assertEqual(
            Total.objects.filter(
                user=user,
                total='All',
            ).count(),
            1,
        )

    def test_missing_clients_group_does_not_break_registration(self):
        Group.objects.filter(name='clients').delete()

        user = User.objects.create_user(
            username='testpilot3',
            email='testpilot3@example.com',
            password='testpassword123',
        )

        self.assertTrue(
            Profile.objects.filter(user=user).exists()
        )
