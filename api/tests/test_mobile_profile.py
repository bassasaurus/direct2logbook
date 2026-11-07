from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase


@override_settings(SECURE_SSL_REDIRECT=False)
class MobileProfileTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='profile-owner', email='owner@example.com')
        self.other = get_user_model().objects.create_user(username='profile-other', first_name='Other')
        self.url = '/api/mobile/profile/'

    def test_authentication_and_owner_scope(self):
        self.assertIn(self.client.get(self.url).status_code, (401, 403))
        self.client.force_authenticate(self.user)
        data = self.client.get(self.url + '?user_id=' + str(self.other.pk)).data
        self.assertEqual(data['account']['email'], 'owner@example.com')
        self.assertNotIn('customer_id', data['subscription'])

    def test_name_company_and_medical_update(self):
        self.client.force_authenticate(self.user)
        response = self.client.patch(self.url, {'account': {'first_name': 'Sam', 'company': 'Airline'},
            'medical': {'medical_issue_date': '2026-01-02', 'first_class': True, 'second_class': False,
                        'third_class': False, 'over_40': True}}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['account']['company'], 'Airline')
        self.assertTrue(response.data['medical']['first_class'])
        self.other.refresh_from_db()
        self.assertEqual(self.other.first_name, 'Other')

    def test_rejects_privilege_and_identity_changes(self):
        self.client.force_authenticate(self.user)
        for payload in ({'active': True}, {'account': {'email': 'new@example.com'}},
                        {'medical': {'free_access': True}}, {'account': None}):
            response = self.client.patch(self.url, payload, format='json')
            self.assertEqual(response.status_code, 400)

    def test_invalid_medical_rolls_back_account_change(self):
        self.client.force_authenticate(self.user)
        response = self.client.patch(self.url, {'account': {'first_name': 'Bad'},
            'medical': {'first_class': True, 'second_class': True}}, format='json')
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, '')

    def test_subscription_states(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get(self.url).data['subscription']['status'], 'Setting up')
        self.user.profile.free_access = True
        self.user.profile.save()
        self.assertEqual(self.client.get(self.url).data['subscription']['status'], 'Free access')

    def test_invalid_payloads_and_dates_do_not_save(self):
        self.client.force_authenticate(self.user)
        for payload in ([], {}, {'medical': None}, {'medical': {'medical_issue_date': 'bad'}},
                        {'account': {'company': 'x' * 51}}, {'account': {'is_staff': True}}):
            response = self.client.patch(self.url, payload, format='json')
            self.assertEqual(response.status_code, 400, response.data)

    def test_ready_subscription_states_and_private_cache_headers(self):
        import datetime
        from django.utils import timezone
        self.client.force_authenticate(self.user)
        profile = self.user.profile
        profile.customer_id = 'private-customer'
        profile.subscription_id = 'private-subscription'
        profile.end_date = timezone.now().date() + datetime.timedelta(days=10)
        for field, expected in (('trial', 'Free trial'), ('trial_expiring', 'Expiring soon'),
                                ('canceled', 'Canceled'), ('active', 'Active')):
            profile.trial = profile.trial_expiring = profile.canceled = False
            setattr(profile, field, True)
            profile.save()
            response = self.client.get(self.url)
            self.assertEqual(response.data['subscription']['status'], expected)
            self.assertIn('no-store', response['Cache-Control'])
            self.assertNotIn('private-customer', str(response.data))
        profile.end_date = timezone.now().date()
        profile.save()
        self.assertEqual(self.client.get(self.url).data['subscription']['status'], 'Expired')
