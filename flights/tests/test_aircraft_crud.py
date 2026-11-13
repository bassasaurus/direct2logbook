# flights/tests/test_aircraft_crud.py

from flights.models import Aircraft, TailNumber
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse


class AircraftCRUDTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass')

    def test_type_rated_aircraft_is_not_flagged_for_tailnumber_errors(self):
        self.user.profile.active = True
        self.user.profile.save(update_fields=['active'])
        aircraft = Aircraft.objects.create(
            user=self.user, aircraft_type='737', turbine=True,
            requires_type=True, aircraft_category='A', aircraft_class='MEL', large=True,
        )
        tailnumber = TailNumber.objects.create(user=self.user, aircraft=aircraft, registration='N737')
        self.client.force_login(self.user)
        response = self.client.get(reverse('aircraft_list'))
        self.assertRegex(response.content.decode(), rf'<a\s+class="text-dark"\s+href="{reverse("aircraft_detail", args=[aircraft.pk])}">\s*<h4 data-aircraft-type>737</h4>')
        self.assertRegex(response.content.decode(), rf'<a data-tailnumber\s+class="text-danger"\s+href="{reverse("tailnumber_detail", args=[tailnumber.pk])}">N737</a>')

    def test_create_aircraft(self):
        aircraft = Aircraft.objects.create(
            user=self.user,
            aircraft_type='C172',
            turbine=False,
            piston=True,
            requires_type=False,
            tailwheel=False,
            simple=True,
            compleks=False,
            high_performance=False,
            aircraft_category='A',
            aircraft_class='SEL',
            superr=False,
            heavy=False,
            large=False,
            medium=False,
            small=True,
            light_sport=False,
        )
        self.assertIsNotNone(aircraft.pk)
        self.assertEqual(aircraft.aircraft_type, 'C172')

    def test_read_aircraft(self):
        ac = Aircraft.objects.create(
            user=self.user,
            aircraft_type='PA28',
            turbine=False,
            piston=True,
            requires_type=False,
            tailwheel=False,
            simple=False,
            compleks=False,
            high_performance=False,
            aircraft_category='A',
            aircraft_class='SEL',
            superr=False,
            heavy=False,
            large=False,
            medium=False,
            small=True,
            light_sport=False,
        )
        fetched = Aircraft.objects.get(pk=ac.pk)
        self.assertEqual(fetched.aircraft_type, 'PA28')

    def test_update_aircraft(self):
        ac = Aircraft.objects.create(
            user=self.user,
            aircraft_type='B737',
            turbine=True,
            piston=False,
            requires_type=False,
            tailwheel=False,
            simple=False,
            compleks=False,
            high_performance=False,
            aircraft_category='A',
            aircraft_class='MEL',
            superr=False,
            heavy=False,
            large=True,
            medium=False,
            small=False,
            light_sport=False,
        )
        ac.simple = True
        ac.large = False
        ac.medium = True
        ac.save()

        updated = Aircraft.objects.get(pk=ac.pk)
        self.assertTrue(updated.simple)
        self.assertFalse(updated.large)
        self.assertTrue(updated.medium)

    def test_delete_aircraft(self):
        ac = Aircraft.objects.create(
            user=self.user,
            aircraft_type='DA40',
            turbine=False,
            piston=True,
            requires_type=False,
            tailwheel=False,
            simple=True,
            compleks=False,
            high_performance=False,
            aircraft_category='A',
            aircraft_class='SEL',
            superr=False,
            heavy=False,
            large=False,
            medium=False,
            small=True,
            light_sport=False,
        )
        pk = ac.pk
        ac.delete()
        with self.assertRaises(Aircraft.DoesNotExist):
            Aircraft.objects.get(pk=pk)
