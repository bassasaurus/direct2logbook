from django.test import SimpleTestCase, Client
from decouple import config


class AuthTests(SimpleTestCase):

    def test_login(self):

        test_password = config('TEST_PASSWORD')
        test_email = config('TEST_EMAIL')

        client = Client(enforce_csrf_checks=True)

        response = client.post(
            '/accounts/login/',
            {
                'email': test_email,
                'password': test_password,
            })

        self.assertRedirects(
            response,
            'home/',
            status_code=302,
            target_status_code=200,
            msg_prefix='',
            fetch_redirect_response=True,
        )
