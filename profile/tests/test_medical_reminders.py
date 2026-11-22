from datetime import date
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(SECURE_SSL_REDIRECT=False)
class MedicalRemindersTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('medical-reminder-owner')
        self.other = get_user_model().objects.create_user('medical-reminder-other')
        self.profile = self.user.profile
        self.profile.free_access = True
        self.profile.active = True
        self.profile.company = 'Original Company'
        self.profile.first_class = True
        self.profile.over_40 = True
        self.profile.medical_issue_date = date(2026, 5, 10)
        self.profile.save()
        self.client.force_login(self.user)

    def test_medical_details_live_on_reminders_and_company_remains_on_profile(self):
        reminders = self.client.get(reverse('manage_reminders'))
        self.assertContains(reminders, 'Medical Certificate')
        home = self.client.get(reverse('home'))
        self.assertContains(home, 'First Class')
        card = home.content.decode().split('data-medical-reminder', 1)[1].split('</li>', 1)[0]
        self.assertLess(card.index('First Class'), card.index('40 or older'))
        self.assertLess(card.index('40 or older'), card.index('Issued'))
        self.assertLess(card.index('Issued'), card.index('Due by') if 'Due by' in card else card.index('Was due by'))
        self.assertContains(home, '40 or older at examination')
        self.assertContains(reminders, 'Nov 30, 2026')
        self.assertContains(reminders, reverse('medical_update'))
        profile = self.client.get(reverse('profile'))
        self.assertNotContains(profile, 'medical-heading')
        self.assertNotContains(profile, 'Update medical info')
        self.assertContains(profile, 'Original Company')
        self.assertContains(profile, reverse('profile_update', args=[self.profile.pk]))

    def test_medical_edit_returns_to_reminders_without_changing_company_or_another_user(self):
        before = self.other.profile.medical_issue_date
        response = self.client.post(reverse('medical_update'), {
            'medical_issue_date': '10/06/2026', 'first_class': 'on', 'over_40': 'on',
            'company': 'Injected Company', 'user': self.other.pk,
        })
        self.assertRedirects(response, reverse('manage_reminders'))
        self.profile.refresh_from_db()
        self.other.profile.refresh_from_db()
        self.assertEqual(self.profile.medical_issue_date, date(2026, 6, 10))
        self.assertEqual(self.profile.company, 'Original Company')
        self.assertEqual(self.other.profile.medical_issue_date, before)
        self.assertContains(self.client.get(reverse('manage_reminders')), 'Dec 31, 2026')

    def test_medical_form_has_reminders_breadcrumb_and_no_company_field(self):
        response = self.client.get(reverse('medical_update'))
        self.assertEqual(response.context['parent_link'], reverse('manage_reminders'))
        self.assertContains(response, 'Update Medical')
        self.assertNotContains(response, 'name="company"')
        self.assertContains(response, 'name="medical_issue_date"')

    def test_company_update_does_not_change_medical_fields(self):
        response = self.client.post(reverse('profile_update', args=[self.profile.pk]), {
            'company': 'Updated Company', 'medical_issue_date': '01/01/2000', 'third_class': 'on',
        })
        self.assertRedirects(response, reverse('profile'))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.company, 'Updated Company')
        self.assertEqual(self.profile.medical_issue_date, date(2026, 5, 10))
        self.assertTrue(self.profile.first_class)
        self.assertFalse(self.profile.third_class)

    def test_anonymous_medical_access_is_rejected_and_invalid_date_is_not_saved(self):
        response = self.client.post(reverse('medical_update'), {'medical_issue_date': 'bad-date'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('medical_issue_date', response.context['form'].errors)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.medical_issue_date, date(2026, 5, 10))
        self.client.logout()
        self.assertEqual(self.client.get(reverse('medical_update')).status_code, 302)
        self.assertEqual(self.client.post(reverse('medical_update'), {'medical_issue_date': '10/06/2026'}).status_code, 302)

    def test_named_date_display_legacy_day_first_input_and_primary_save_button(self):
        response = self.client.get(reverse('medical_update'))
        self.assertContains(response, 'placeholder="Nov 30, 2026"')
        self.assertContains(response, 'value="May 10, 2026"')
        self.assertContains(response, 'class="btn btn-primary" type="submit">Save</button>')
        self.assertNotContains(response, '>Cancel</a>')
        response = self.client.post(reverse('medical_update'), {
            'medical_issue_date': '05/06/2026', 'first_class': 'on', 'over_40': 'on',
        })
        self.assertRedirects(response, reverse('manage_reminders'))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.medical_issue_date, date(2026, 6, 5))
