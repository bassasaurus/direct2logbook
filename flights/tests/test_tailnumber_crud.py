# flights/tests/test_tailnumber_crud.py

from flights.models import Aircraft, TailNumber
from django.test import TestCase
from django.contrib.auth.models import User
from django.db.models.signals import post_save

# Prevent your profile/Stripe signals from running during tests
from profile.signal_profile import create_user_profile, save_user_profile

post_save.disconnect(create_user_profile, sender=User)
post_save.disconnect(save_user_profile, sender=User)


class TailNumberCRUDTests(TestCase):
    def setUp(self):
        # Create a user without hitting external services
        self.user = User.objects.create_user(
            username='testuser', password='testpass')
        # And a minimal Aircraft for the FK
        self.aircraft = Aircraft.objects.create(
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

    def test_create_tailnumber(self):
        tn = TailNumber.objects.create(
            user=self.user,
            registration='N12345',
            aircraft=self.aircraft,
            is_121=True,
            is_135=False,
            is_91=False,
        )
        self.assertIsNotNone(tn.pk)
        self.assertEqual(tn.registration, 'N12345')
        self.assertTrue(tn.is_121)
        self.assertFalse(tn.is_135)
        self.assertFalse(tn.is_91)

    def test_read_tailnumber(self):
        tn = TailNumber.objects.create(
            user=self.user,
            registration='N54321',
            aircraft=self.aircraft,
            is_121=False,
            is_135=True,
            is_91=False,
        )
        fetched = TailNumber.objects.get(pk=tn.pk)
        self.assertEqual(fetched.registration, 'N54321')
        self.assertTrue(fetched.is_135)

    def test_update_tailnumber(self):
        tn = TailNumber.objects.create(
            user=self.user,
            registration='N67890',
            aircraft=self.aircraft,
            is_121=False,
            is_135=False,
            is_91=False,
        )
        # flip a flag and save
        tn.is_91 = True
        tn.save()
        updated = TailNumber.objects.get(pk=tn.pk)
        self.assertTrue(updated.is_91)

    def test_delete_tailnumber(self):
        tn = TailNumber.objects.create(
            user=self.user,
            registration='N00001',
            aircraft=self.aircraft,
            is_121=False,
            is_135=False,
            is_91=True,
        )
        pk = tn.pk
        tn.delete()
        with self.assertRaises(TailNumber.DoesNotExist):
            TailNumber.objects.get(pk=pk)
