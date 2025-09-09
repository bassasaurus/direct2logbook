# flights/tests/test_aircraft_crud.py

from flights.models import Aircraft
from django.test import TestCase
from django.contrib.auth.models import User
from django.db.models.signals import post_save

# Import both of your profile signal receivers:
from profile.signal_profile import create_user_profile, save_user_profile

# Disconnect them so no profile logic (and no Stripe/network calls) fire during tests:
post_save.disconnect(create_user_profile, sender=User)
post_save.disconnect(save_user_profile,   sender=User)


class AircraftCRUDTests(TestCase):
    def setUp(self):
        # Now this won’t blow up on User.profile
        self.user = User.objects.create_user(
            username='testuser', password='testpass')

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
