from django.test import TestCase
from profile.forms import ProfileForm
from profile.models import Profile
from django.contrib.auth.models import User
from datetime import date
from unittest.mock import patch


class ProfileFormTest(TestCase):

    def setUp(self):
        # Patch signal before creating user to prevent automatic profile creation
        self.patcher = patch('profile.signal_profile.create_user_profile')
        self.mock_signal = self.patcher.start()
        self.addCleanup(self.patcher.stop)

        # Patch Profile model's save method before user creation to prevent IntegrityError
        self.profile_save_patcher = patch(
            'profile.models.Profile.save', autospec=True)
        self.mock_save = self.profile_save_patcher.start()
        self.addCleanup(self.profile_save_patcher.stop)

        from django.contrib.auth.models import Group
        Group.objects.create(name='clients')

        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )

        # Also patch save on Profile model to ensure tests don’t fail from missing required fields
        profile_patcher = patch('profile.models.Profile.save', autospec=True)
        self.mock_profile_save = profile_patcher.start()
        self.addCleanup(profile_patcher.stop)

        Profile.objects.create(
            user=self.user,
            company='Test Company',
            medical_issue_date=date.today()
        )

    def test_profile_form_valid_data(self):
        form_data = {
            'company': 'Delta Airlines',
            'medical_issue_date': date.today(),
            'first_class': True,
            'second_class': False,
            'third_class': False,
            'over_40': True,
        }
        form = ProfileForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_profile_form_invalid_date(self):
        form_data = {
            'company': 'Test Co',
            'medical_issue_date': 'invalid-date',
            'first_class': False,
            'second_class': False,
            'third_class': False,
            'over_40': False,
        }
        form = ProfileForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('medical_issue_date', form.errors)

    def test_profile_form_missing_required_fields(self):
        form_data = {
            'first_class': False,
            'second_class': False,
            'third_class': False,
            'over_40': False,
            'company': '',  # required
            'medical_issue_date': ''  # required
        }
        form = ProfileForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('company', form.errors)
        self.assertIn('medical_issue_date', form.errors)

    def test_profile_form_missing_company(self):
        form_data = {
            'company': '',
            # changed to date object for valid input format
            'medical_issue_date': '',
            'first_class': False,
            'second_class': False,
            'third_class': False,
            'over_40': False,
        }
        form = ProfileForm(data=form_data)
        self.assertIn('company', form.errors)
        self.assertIn('medical_issue_date', form.errors)
        self.assertFalse(form.is_valid())
