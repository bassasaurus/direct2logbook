from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token, TokenProxy
from rest_framework.test import APITestCase


@override_settings(SECURE_SSL_REDIRECT=False)
class FrameworkSecurityTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='framework_security', email='framework@example.com', password='test-password-312',
        )
        self.token, _ = Token.objects.get_or_create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)

    def test_normal_token_authentication_and_json_negotiation_work(self):
        response = self.client.get('/api/aircraft/', HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')

    def test_oversized_accept_header_is_rejected(self):
        response = self.client.get('/api/aircraft/', HTTP_ACCEPT='application/json;' + 'x' * 8192)
        self.assertEqual(response.status_code, 406)

    def test_accept_negotiation_does_not_process_unbounded_alternatives(self):
        alternatives = [f'application/x-test-{index}' for index in range(64)]
        response = self.client.get('/api/aircraft/', HTTP_ACCEPT=','.join(alternatives + ['application/json']))
        self.assertEqual(response.status_code, 406)

    def test_non_text_charset_is_a_validation_error(self):
        response = self.client.post(reverse('api_token_auth'), b'{}',
                                    content_type='application/json; charset=base64_codec')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Unsupported charset', str(response.data))

    @override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=64)
    def test_oversized_json_request_is_rejected(self):
        response = self.client.post(reverse('api_token_auth'),
                                    {'username': 'x' * 128, 'password': 'unused'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_deleting_token_through_admin_proxy_revokes_access(self):
        TokenProxy.objects.get(key=self.token.key).delete()
        self.assertFalse(Token.objects.filter(user=self.user).exists())
        self.assertEqual(self.client.get('/api/aircraft/').status_code, 401)
