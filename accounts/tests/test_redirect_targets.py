import inspect
from urllib.parse import urlsplit
from unittest.mock import patch
from types import SimpleNamespace

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, RequestFactory, override_settings
from django.urls import resolve, reverse
from django.views import View
from allauth.account.forms import default_token_generator
from allauth.account.utils import user_pk_to_url_str

from accounts import views as account_views
from profile import views as profile_views
from flights import views as flight_views
from signature import views as signature_views


class RedirectTargetTests(SimpleTestCase):
    def test_static_view_redirect_destinations_resolve_without_append_slash(self):
        for module in (account_views, profile_views, flight_views, signature_views):
            for name, cls in inspect.getmembers(module, inspect.isclass):
                if cls.__module__ != module.__name__ or not issubclass(cls, View):
                    continue
                for attribute in ('success_url', 'login_url'):
                    value = getattr(cls, attribute, None)
                    if value:
                        with self.subTest(view=name, attribute=attribute):
                            resolve(urlsplit(str(value)).path)

    def test_configured_account_redirect_destinations_resolve(self):
        for name in ('LOGIN_REDIRECT_URL', 'ACCOUNT_LOGOUT_REDIRECT_URL',
                     'ACCOUNT_EMAIL_CONFIRMATION_ANONYMOUS_REDIRECT_URL',
                     'ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL'):
            with self.subTest(setting=name):
                resolve(getattr(settings, name))

    @override_settings(ALLOWED_HOSTS=['localhost', 'www.direct2logbook.com'])
    @patch('profile.views.stripe.checkout.Session.create', return_value=SimpleNamespace(id='cs_test'))
    def test_checkout_returns_use_current_origin_and_actual_routes(self, checkout):
        for origin in ('http://localhost:8000', 'https://www.direct2logbook.com'):
            for method in ('session_monthly', 'session_yearly'):
                with self.subTest(origin=origin, method=method):
                    view = profile_views.ProfileView()
                    view.request = RequestFactory().get(
                        reverse('profile'), secure=origin.startswith('https:'),
                        HTTP_HOST=urlsplit(origin).netloc,
                    )
                    view.request.user = SimpleNamespace(pk=12)
                    getattr(view, method)('cus_test')
                    kwargs = checkout.call_args.kwargs
                    for key, expected in [('success_url', 'payment_success'), ('cancel_url', 'payment_canceled')]:
                        parts = urlsplit(kwargs[key])
                        self.assertEqual(parts.scheme + '://' + parts.netloc, origin)
                        self.assertEqual(resolve(parts.path).url_name, expected)
                        self.assertEqual(resolve(parts.path).kwargs, {'user': 12})


@override_settings(SECURE_SSL_REDIRECT=False, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AnonymousPasswordResetTests(TestCase):
    def test_valid_email_reset_link_does_not_require_login(self):
        user = get_user_model().objects.create_user(username='reset_redirect', email='reset@example.com', password='old-secret123')
        token = default_token_generator.make_token(user)
        url = reverse('account_reset_password_from_key', kwargs={
            'uidb36': user_pk_to_url_str(user), 'key': token,
        })
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'account/password_reset_from_key.html')
        self.assertFalse(any(reverse('account_login') in target for target, code in response.redirect_chain))
        self.assertFalse(response.context.get('token_fail', False))
        self.assertIn('password1', response.context['form'].fields)

    def test_reset_form_can_submit_without_prior_login(self):
        user = get_user_model().objects.create_user(username='reset_submit', email='submit@example.com', password='old-secret123')
        token = default_token_generator.make_token(user)
        url = reverse('account_reset_password_from_key', kwargs={
            'uidb36': user_pk_to_url_str(user), 'key': token,
        })
        response = self.client.get(url, follow=True)
        response = self.client.post(response.context['action_url'], {
            'password1': 'New-pass-for-test-4927!', 'password2': 'New-pass-for-test-4927!',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password('New-pass-for-test-4927!'))

    def test_invalid_token_does_not_display_reset_form(self):
        user = get_user_model().objects.create_user(username='reset_invalid')
        url = reverse('account_reset_password_from_key', kwargs={
            'uidb36': user_pk_to_url_str(user), 'key': 'invalid-token',
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['token_fail'])
        self.assertNotContains(response, 'name="password1"')
