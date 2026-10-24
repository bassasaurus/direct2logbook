from datetime import date

from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.test import TestCase

from profile.forms import ProfileForm
from profile.models import Profile
from profile.signal_profile import create_user_profile, save_user_profile


class ProfileFormTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Avoid Stripe calls and profile side effects while testing form validation.
        post_save.disconnect(create_user_profile, sender=User)
        post_save.disconnect(save_user_profile, sender=User)

    @classmethod
    def tearDownClass(cls):
        try:
            post_save.connect(create_user_profile, sender=User)
            post_save.connect(save_user_profile, sender=User)
        finally:
            super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass',
        )
        self.profile = Profile.objects.create(
            user=self.user,
            company='Test Company',
            medical_issue_date=date.today(),
        )

    def test_profile_form_valid_data(self):
        form = ProfileForm(data={
            'company': 'Delta Airlines',
            'medical_issue_date': date.today(),
            'first_class': True,
            'second_class': False,
            'third_class': False,
            'over_40': True,
        }, instance=self.profile)
        self.assertTrue(form.is_valid(), form.errors)

    def test_profile_form_invalid_date(self):
        form = ProfileForm(data={
            'company': 'Test Co',
            'medical_issue_date': 'invalid-date',
        }, instance=self.profile)
        self.assertFalse(form.is_valid())
        self.assertIn('medical_issue_date', form.errors)

    def test_profile_form_missing_required_fields(self):
        form = ProfileForm(data={
            'company': '',
            'medical_issue_date': '',
        }, instance=self.profile)
        self.assertFalse(form.is_valid())
        self.assertIn('company', form.errors)
        self.assertIn('medical_issue_date', form.errors)

    def test_profile_form_missing_company(self):
        form = ProfileForm(data={
            'company': '',
            'medical_issue_date': date.today(),
        }, instance=self.profile)
        self.assertFalse(form.is_valid())
        self.assertIn('company', form.errors)
        self.assertNotIn('medical_issue_date', form.errors)
