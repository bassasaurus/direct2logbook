import json
import time
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import jwt
import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import SimpleTestCase
from oauthlib.oauth2 import MismatchingStateError
from requests_oauthlib import OAuth1Session, OAuth2Session

from allauth.socialaccount.providers.google.views import _verify_and_decode
from allauth.socialaccount.providers.oauth2.client import OAuth2Error


class GoogleJWTCompatibilityTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.app = SimpleNamespace(client_id='test-google-client')

    def payload(self, **changes):
        payload = {'iss': 'https://accounts.google.com', 'aud': self.app.client_id,
                   'sub': 'test-google-user', 'email': 'google@example.com',
                   'email_verified': True, 'exp': int(time.time()) + 300}
        payload.update(changes)
        return payload

    def verify(self, payload, key=None):
        token = jwt.encode(payload, key or self.private_key, algorithm='RS256', headers={'kid': 'test-key'})
        # Keep real JWT signature/claim validation; replace only the remote key lookup.
        with patch('allauth.socialaccount.internal.jwtkit.fetch_key',
                   return_value=('RS256', self.private_key.public_key())):
            return _verify_and_decode(self.app, token)

    def test_signed_google_token_is_accepted(self):
        decoded = self.verify(self.payload())
        self.assertEqual(decoded['sub'], 'test-google-user')
        self.assertTrue(decoded['email_verified'])

    def test_invalid_claims_are_rejected_through_allauth(self):
        for changes in ({'iss': 'https://accounts.google.com.attacker.example'},
                        {'aud': 'different-client'}, {'exp': int(time.time()) - 60},
                        {'exp': []}):
            with self.subTest(changes=changes), self.assertRaises(OAuth2Error):
                self.verify(self.payload(**changes))

    def test_wrong_signature_is_rejected(self):
        wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        with self.assertRaises(OAuth2Error):
            self.verify(self.payload(), key=wrong_key)

    def test_public_key_cannot_be_used_as_hmac_secret(self):
        public_der = self.private_key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        with self.assertRaises(jwt.InvalidKeyError):
            jwt.encode(self.payload(), public_der, algorithm='HS256')


class OAuthClientCompatibilityTests(SimpleTestCase):
    def session(self):
        return OAuth2Session('test-client', redirect_uri='https://example.com/callback',
                             scope=['profile', 'email'], state='test-state', pkce='S256')

    def test_pkce_authorization_and_token_exchange(self):
        session = self.session()
        url, state = session.authorization_url('https://provider.example/authorize')
        params = parse_qs(urlsplit(url).query)
        self.assertEqual(state, 'test-state')
        self.assertEqual(params['code_challenge_method'], ['S256'])
        self.assertTrue(params['code_challenge'][0])
        response = requests.Response()
        response.status_code = 200
        response.request = requests.Request('POST', 'https://provider.example/token').prepare()
        response._content = json.dumps({'access_token': 'fake-access-token', 'token_type': 'Bearer'}).encode()
        with patch.object(session, 'request', return_value=response) as request:
            token = session.fetch_token('https://provider.example/token',
                                        authorization_response='https://example.com/callback?code=test-code&state=test-state')
        self.assertEqual(token['access_token'], 'fake-access-token')
        self.assertIn('code_verifier', request.call_args.kwargs['data'])

    def test_wrong_state_is_rejected_before_token_exchange(self):
        session = self.session()
        session.authorization_url('https://provider.example/authorize')
        with patch.object(session, 'request') as request, self.assertRaises(MismatchingStateError):
            session.fetch_token('https://provider.example/token',
                                authorization_response='https://example.com/callback?code=test-code&state=wrong')
        request.assert_not_called()

    def test_oauth1_request_signing_still_works(self):
        session = OAuth1Session('test-client', client_secret='test-secret',
                                resource_owner_key='test-owner', resource_owner_secret='test-owner-secret')
        request = session.prepare_request(requests.Request('GET', 'https://provider.example/resource'))
        self.assertIn(b'oauth_signature=', request.headers['Authorization'])
