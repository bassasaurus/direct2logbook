from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token
from flights.models import Aircraft, Flight, Imported, TailNumber


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
        self.registration.delete()
        response = self.client.post(reverse('aircraft_delete', args=[self.aircraft.pk]))
        self.assertFalse(Aircraft.objects.filter(pk=self.aircraft.pk).exists())
        self.assertRedirects(response, reverse('aircraft_list'))

    def test_registration_delete_returns_to_existing_aircraft_page(self):
        response = self.client.post(reverse('tailnumber_delete', args=[self.registration.pk]))
        self.assertFalse(TailNumber.objects.filter(pk=self.registration.pk).exists())
        self.assertTrue(Aircraft.objects.filter(pk=self.aircraft.pk).exists())
        self.assertRedirects(response, reverse('aircraft_list'))

    def assert_delete_blocked(self, resource, pk, api_resource):
        delete_url = reverse(f'{resource}_delete', args=[pk])
        update_url = reverse(f'{resource}_update', args=[pk])
        detail = self.client.get(reverse(f'{resource}_detail', args=[pk]))
        self.assertNotContains(detail, f'href="{delete_url}"')
        self.assertContains(detail, f'href="{update_url}"')
        for method in (self.client.get, self.client.post):
            response = method(delete_url)
            self.assertContains(response, 'cannot be deleted', status_code=409)
            self.assertContains(response, f'href="{update_url}"', status_code=409)
        self.assertEqual(self.client.delete(delete_url).status_code, 409)
        token, _ = Token.objects.get_or_create(user=self.user)
        response = self.client.delete(f'/api/{api_resource}/{pk}/', HTTP_AUTHORIZATION=f'Token {token.key}')
        self.assertEqual(response.status_code, 409)

    def test_aircraft_with_tailnumber_cannot_be_deleted(self):
        self.assert_delete_blocked('aircraft', self.aircraft.pk, 'aircraft')
        self.assertTrue(TailNumber.objects.filter(pk=self.registration.pk, aircraft=self.aircraft).exists())

    def test_aircraft_with_imported_totals_cannot_be_deleted(self):
        self.registration.delete()
        imported = Imported.objects.create(user=self.user, aircraft_type=self.aircraft)
        self.assert_delete_blocked('aircraft', self.aircraft.pk, 'aircraft')
        self.assertTrue(Imported.objects.filter(pk=imported.pk, aircraft_type=self.aircraft).exists())

    def test_flight_added_after_confirmation_blocks_tailnumber_delete(self):
        delete_url = reverse('tailnumber_delete', args=[self.registration.pk])
        detail = self.client.get(reverse('tailnumber_detail', args=[self.registration.pk]))
        self.assertContains(detail, f'href="{delete_url}"')
        self.assertContains(self.client.get(delete_url), 'Delete Tailnumber')

        flight = Flight.objects.create(user=self.user, aircraft_type=self.aircraft, registration=self.registration,
                                       date='2025-11-04', route='KIAH-KLAS', duration='1.0')
        self.assert_delete_blocked('tailnumber', self.registration.pk, 'tailnumbers')
        self.assertTrue(Flight.objects.filter(pk=flight.pk, registration=self.registration).exists())
