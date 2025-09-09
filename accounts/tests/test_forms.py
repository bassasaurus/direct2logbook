from unittest.mock import patch
from django.test import TestCase, override_settings
from django.contrib.auth.models import User, Group
from accounts.forms import CustomSignupForm, UserForm


class CustomSignupFormTest(TestCase):
    @override_settings(DEBUG=True)
    def test_form_valid_without_captcha_in_debug(self):
        form_data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john@example.com',
            'email2': 'john@example.com',  # Match email
            'password1': 'complexpassword123',
            'password2': 'complexpassword123'
        }
        form = CustomSignupForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)

    @override_settings(DEBUG=False)
    def test_form_missing_captcha_outside_debug(self):
        # CAPTCHA should be required when DEBUG=False
        form_data = {
            'first_name': 'Jane',
            'last_name': 'Smith',
            'email': 'jane@example.com',
            'email2': 'jane@example.com',
            'password1': 'complexpassword456',
            'password2': 'complexpassword456'
            # captcha is omitted
        }
        form = CustomSignupForm(data=form_data)
        is_valid = form.is_valid()
        if is_valid:
            self.fail(
                "Form is valid but captcha should be required when DEBUG=False")
        else:
            self.assertIn('captcha', form.errors)

    @patch('profile.signal_profile.create_user_profile')
    @override_settings(DEBUG=True)
    def test_signup_method_sets_names(self, mock_signal):
        Group.objects.create(name='clients')
        form_data = {
            'first_name': 'Alice',
            'last_name': 'Wonderland',
            'email': 'janee@example.com',
            'email2': 'janee@example.com',  # Match email
            'password1': 'password789xyz',
            'password2': 'password789xyz'
        }
        form = CustomSignupForm(data=form_data)
        self.assertTrue(form.is_valid())
        user = User(username='alice', email=form.cleaned_data['email'])
        form.cleaned_data = form_data
        user = form.signup(request=None, user=user)
        self.assertEqual(user.first_name, 'Alice')
        self.assertEqual(user.last_name, 'Wonderland')


class UserFormTest(TestCase):
    @patch('profile.signal_profile.create_user_profile')
    def test_user_form_valid(self, mock_signal):
        Group.objects.create(name='clients')  # Required by the signal
        user = User.objects.create(username='user1', email='user1@example.com')
        form_data = {'first_name': 'New', 'last_name': 'Name'}
        form = UserForm(instance=user, data=form_data)
        self.assertTrue(form.is_valid())
        updated_user = form.save()
        self.assertEqual(updated_user.first_name, 'New')
        self.assertEqual(updated_user.last_name, 'Name')


class CaptchaFieldTest(TestCase):

    @override_settings(DEBUG=False)
    def test_captcha_field_present_when_debug_false(self):
        form = CustomSignupForm()
        self.assertIn('captcha', form.fields,
                      msg="CAPTCHA field should be present when DEBUG is False")

    @override_settings(DEBUG=True)
    def test_captcha_field_absent_when_debug_true(self):
        form = CustomSignupForm()
        self.assertNotIn('captcha', form.fields,
                         msg="CAPTCHA field should be omitted when DEBUG is True")
