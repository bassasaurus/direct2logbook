import datetime
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from home.currency import medical_expiry_date, medical_duration


class MedicalValidityTests(SimpleTestCase):
    def test_all_classes_and_age_bands_use_correct_month_end(self):
        for selected, older, expected in [
            ('first_class', False, date(2027, 1, 31)),
            ('first_class', True, date(2026, 7, 31)),
            ('second_class', False, date(2027, 1, 31)),
            ('second_class', True, date(2027, 1, 31)),
            ('third_class', False, date(2031, 1, 31)),
            ('third_class', True, date(2028, 1, 31)),
        ]:
            profile = SimpleNamespace(medical_issue_date=date(2026, 1, 5), over_40=older,
                first_class=selected == 'first_class', second_class=selected == 'second_class', third_class=selected == 'third_class')
            with self.subTest(selected=selected, age_40_or_older=older):
                self.assertEqual(medical_expiry_date(profile), expected)

    def test_leap_day_and_aging_are_based_on_age_at_examination(self):
        profile = SimpleNamespace(medical_issue_date=date(2024, 2, 29), over_40=True,
                                  first_class=False, second_class=False, third_class=True)
        self.assertEqual(medical_expiry_date(profile), date(2026, 2, 28))
        profile.over_40 = False
        self.assertEqual(medical_expiry_date(profile), date(2029, 2, 28))


@override_settings(SECURE_SSL_REDIRECT=False)
class SharedMedicalValidityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('medical-validity')
        self.user.profile.active = True
        self.user.profile.medical_issue_date = date(2026, 1, 5)
        self.user.profile.save()
        self.client.force_login(self.user)
        self.mobile = APIClient(); self.mobile.force_authenticate(self.user)

    def test_web_and_mobile_use_corrected_second_and_third_class_due_dates(self):
        for second, older, expected in [(True, False, '2027-01-31'), (False, True, '2028-01-31')]:
            profile = self.user.profile
            profile.first_class = False
            profile.second_class = second
            profile.third_class = not second
            profile.over_40 = older
            profile.save()
            self.assertEqual(self.mobile.get('/api/mobile/profile/').data['medical_due_date'], expected)
            home = self.client.get(reverse('home'))
            self.assertEqual(home.context['expiry_date'].isoformat(), expected)
            manage = self.client.get(reverse('manage_reminders'))
            self.assertEqual(manage.context['medical_due_date'].isoformat(), expected)

    def test_valid_through_expiration_day_and_expired_the_following_day(self):
        self.user.profile.second_class = True
        self.user.profile.save()
        for today, current, expired in [(date(2027, 1, 31), True, False), (date(2027, 2, 1), False, True)]:
            with patch('home.currency.datetime', wraps=datetime) as clock:
                clock.date.today.return_value = today
                result = medical_duration(self.user)
                self.assertEqual((result[4], result[3]), (current, expired))
