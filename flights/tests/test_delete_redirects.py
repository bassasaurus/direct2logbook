from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from flights.models import Aircraft, TailNumber


@override_settings(SECURE_SSL_REDIRECT=False)
class AircraftDeleteRedirectTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='delete_redirect')
        self.user.profile.active = True
        self.user.profile.expired = False
        self.user.profile.save()
        self.client.force_login(self.user)
        self.aircraft = Aircraft.objects.create(user=self.user, aircraft_type='C172')
        self.registration = TailNumber.objects.create(user=self.user, aircraft=self.aircraft, registration='N726T')

    def test_aircraft_delete_returns_to_existing_aircraft_page(self):
        response = self.client.post(reverse('aircraft_delete', args=[self.aircraft.pk]))
        self.assertFalse(Aircraft.objects.filter(pk=self.aircraft.pk).exists())
        self.assertRedirects(response, reverse('aircraft_list'))

    def test_registration_delete_returns_to_existing_aircraft_page(self):
        response = self.client.post(reverse('tailnumber_delete', args=[self.registration.pk]))
        self.assertFalse(TailNumber.objects.filter(pk=self.registration.pk).exists())
        self.assertTrue(Aircraft.objects.filter(pk=self.aircraft.pk).exists())
        self.assertRedirects(response, reverse('aircraft_list'))
