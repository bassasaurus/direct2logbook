from allauth.account.adapter import get_adapter
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, SimpleTestCase, override_settings


@override_settings(ALLAUTH_TRUSTED_PROXY_COUNT=1, ALLAUTH_TRUSTED_CLIENT_IP_HEADER=None)
class ProxyClientIPTests(SimpleTestCase):
    def request(self, forwarded=None, remote=''):
        headers = {'REMOTE_ADDR': remote}
        if forwarded is not None:
            headers['HTTP_X_FORWARDED_FOR'] = forwarded
        return RequestFactory().post('/accounts/login/', **headers)

    def test_unix_socket_uses_ip_appended_by_nginx(self):
        self.assertEqual(get_adapter().get_client_ip(self.request('203.0.113.10')), '203.0.113.10')

    def test_spoofed_prefix_cannot_replace_nginx_peer(self):
        self.assertEqual(get_adapter().get_client_ip(
            self.request('198.51.100.99, 203.0.113.10')), '203.0.113.10')

    def test_ipv6_visitor(self):
        self.assertEqual(get_adapter().get_client_ip(self.request('2001:db8::1')), '2001:db8::1')

    def test_missing_or_invalid_ip_still_fails_closed(self):
        for forwarded in (None, 'not-an-ip'):
            with self.subTest(forwarded=forwarded), self.assertRaises(PermissionDenied):
                get_adapter().get_client_ip(self.request(forwarded))

    @override_settings(ALLAUTH_TRUSTED_PROXY_COUNT=0)
    def test_local_direct_requests_ignore_untrusted_forwarded_header(self):
        self.assertEqual(get_adapter().get_client_ip(
            self.request('198.51.100.99', remote='127.0.0.1')), '127.0.0.1')
