from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase, override_settings

from errors.views import error_400, error_403, error_404, error_500


@override_settings(DEBUG=False, SECURE_SSL_REDIRECT=False)
class ErrorResponseStatusTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get('/missing-page/')
        self.request.user = AnonymousUser()

    def test_bad_request_returns_400(self):
        response = error_400(self.request, ValueError('Bad request'))
        self.assertEqual(response.status_code, 400)

    def test_forbidden_returns_403(self):
        response = error_403(self.request, PermissionError('Forbidden'))
        self.assertEqual(response.status_code, 403)

    def test_not_found_returns_404(self):
        response = error_404(self.request, Exception('Not found'))
        self.assertEqual(response.status_code, 404)

    def test_server_error_returns_500(self):
        response = error_500(self.request)
        self.assertEqual(response.status_code, 500)
