from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from profile.forms import CertificatesForm
from profile.models import Profile


@override_settings(SECURE_SSL_REDIRECT=False)
class CertificateProfileTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('certificate-owner')
        self.other = get_user_model().objects.create_user('certificate-other')
        self.user.profile.free_access = True
        self.user.profile.save(update_fields=['free_access'])
        self.client.force_login(self.user)

    def test_profile_displays_independent_checkboxes_without_inferred_selections(self):
        page = self.client.get(reverse('profile'))
        for text in ('Certificates Held', 'Student Pilot', 'Sport Pilot', 'Recreational Pilot',
                     'Private Pilot', 'Commercial Pilot', 'Airline Transport Pilot (ATP)',
                     'Flight Instructor', 'Instrument Instructor', 'Multi-Engine Instructor'):
            self.assertContains(page, text)
        for field in CertificatesForm.Meta.fields:
            self.assertFalse(getattr(self.user.profile, field))
            self.assertContains(page, f'type="checkbox" name="{field}"')

    def test_multiple_certificates_save_to_authenticated_account_only(self):
        selected = ['private_pilot_certificate', 'commercial_pilot_certificate', 'atp_certificate']
        data = {field: 'on' for field in selected}
        data.update(user=self.other.pk, id=self.other.profile.pk)
        response = self.client.post(reverse('profile'), data)
        self.assertRedirects(response, reverse('profile'))
        self.user.profile.refresh_from_db()
        self.other.profile.refresh_from_db()
        for field in CertificatesForm.Meta.fields:
            self.assertEqual(getattr(self.user.profile, field), field in selected)
            self.assertFalse(getattr(self.other.profile, field))
        self.client.post(reverse('profile'), {})
        self.user.profile.refresh_from_db()
        self.assertFalse(any(getattr(self.user.profile, field) for field in CertificatesForm.Meta.fields))

    def test_instructor_ratings_also_record_flight_instructor(self):
        for field in ('instrument_instructor', 'multi_engine_instructor'):
            self.client.post(reverse('profile'), {field: 'on'})
            self.user.profile.refresh_from_db()
            self.assertTrue(getattr(self.user.profile, field))
            self.assertTrue(self.user.profile.flight_instructor_certificate)
        page = self.client.get(reverse('profile'))
        self.assertContains(page, 'name="flight_instructor_certificate"')

    def test_database_rejects_instructor_rating_without_flight_instructor(self):
        for field in ('instrument_instructor', 'multi_engine_instructor'):
            with self.assertRaises(IntegrityError), transaction.atomic():
                Profile.objects.filter(pk=self.user.profile.pk).update(**{field: True})

    def test_anonymous_posts_cannot_change_certificates(self):
        self.client.logout()
        response = self.client.post(reverse('profile'), {'atp_certificate': 'on'})
        self.assertEqual(response.status_code, 302)
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.atp_certificate)
