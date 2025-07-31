from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.contrib.auth.models import Group
import django_recaptcha


class AccountViewsTest(TestCase):
    def setUp(self):
        # Ensure 'clients' group exists before creating users
        Group.objects.get_or_create(name='clients')

        self.username = "testuser"
        self.password = "testpass123"
        self.user = get_user_model().objects.create_user(
            username=self.username,
            email="test@example.com",
            password=self.password
        )

    def test_login_view_get(self):
        response = self.client.get(reverse('account_login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'account/login.html')

    def test_login_view_post_valid(self):
        response = self.client.post(reverse('account_login'), {
            'login': self.user.email,
            'password': self.password
        })
        self.assertRedirects(response, reverse(
            'account_email_verification_sent'))

    def test_logout_view(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(reverse('account_logout'))
        self.assertRedirects(response, '/')

    def test_signup_view_get(self):
        response = self.client.get(reverse('account_signup'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'account/signup.html')


@patch('django_recaptcha.fields.ReCaptchaField.clean')
def test_signup_view_post_valid(self, mock_clean):
    mock_clean.return_value = ''  # Pretend captcha was valid

    response = self.client.post(reverse('account_signup'), {
        'username': 'newuser',
        'email': 'newuser@example.com',
        'password1': 'Testpass123!',
        'password2': 'Testpass123!',
        'first_name': 'Test',
        'last_name': 'User',
        'g-recaptcha-response': 'PASSED'
    })

    self.assertEqual(response.status_code, 302)
    self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_password_change_view(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(reverse('account_change_password'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'account/password_change.html')

    def test_password_reset_view(self):
        response = self.client.get(reverse('account_reset_password'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'account/password_reset.html')

    def test_email_view_requires_login(self):
        response = self.client.get(reverse('account_email'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
