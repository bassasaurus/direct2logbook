"""Smoke failures must fail the deployment check, without touching production."""
from django.test import SimpleTestCase
from deploy.smoke import check


class ProductionSmokeTests(SimpleTestCase):
    def response(self, url):
        if '/static/' in url:
            return 200, url, 'text/css', b'body {}'
        if url.endswith(('/home/', '/csv/upload/')):
            return 200, 'https://example.com/accounts/login/?next=protected', 'text/html', b'login'
        html = b'<input name="login"><input name="password"><input name="email"><input name="password1"><input name="csrfmiddlewaretoken"><div class="g-recaptcha"></div><link rel="stylesheet" href="/static/app.css">'
        return 200, url, 'text/html', html

    def test_checks_forms_static_files_and_protected_redirects(self):
        calls = []
        def get(url):
            calls.append(url)
            return self.response(url)
        check('https://example.com', get=get, report=lambda message: None)
        self.assertEqual(len(calls), 5)

    def test_missing_form_captcha_static_or_redirect_fails(self):
        for broken in ('form', 'captcha', 'static', 'redirect'):
            with self.subTest(broken=broken):
                def get(url):
                    status, final, kind, body = self.response(url)
                    if broken == 'form':
                        body = b'Unexpected page'
                    elif broken == 'captcha':
                        body = body.replace(b'g-recaptcha', b'absent')
                    elif broken == 'static' and '/static/' in url:
                        kind = 'text/html'
                    elif broken == 'redirect' and url.endswith('/home/'):
                        final = url
                    return status, final, kind, body
                with self.assertRaises(RuntimeError):
                    check('https://example.com', get=get, report=lambda message: None)

    def test_network_failure_is_not_hidden(self):
        def get(url):
            raise TimeoutError('timed out')
        with self.assertRaises(TimeoutError):
            check('https://example.com', get=get)

    def test_requires_https_origin(self):
        with self.assertRaises(ValueError):
            check('http://example.com', get=self.response)
