from flights.models import Aircraft, TailNumber
from flights.forms import FlightForm, AircraftForm, TailNumberForm
from django.test import TestCase
from django.contrib.auth.models import User
from django.db.models.signals import post_save

# Disable profile/Stripe signals during form tests
from profile.signal_profile import create_user_profile, save_user_profile
post_save.disconnect(create_user_profile, sender=User)
post_save.disconnect(save_user_profile, sender=User)


class FlightFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='temp', email='temp@example.com', password='pass')
        self.aircraft = Aircraft.objects.create(
            user=self.user,
            aircraft_type='C172',
            piston=True,
            turbine=False,
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
            light_sport=False
        )
        self.tailnumber = TailNumber.objects.create(
            user=self.user,
            aircraft=self.aircraft,
            registration='N12345',
            is_121=True,
            is_135=False,
            is_91=False
        )

    def test_flight_form_valid(self):
        data = {
            'route': 'KJFK-KLAX',
            'date': '2021-01-01',
            'duration': '2.5',
            'aircraft_type': self.aircraft.pk,
            'registration': self.tailnumber.pk,
        }
        form = FlightForm(data=data)
        self.assertTrue(form.is_valid(), msg=form.errors)

    def test_flight_form_invalid_blank_route(self):
        data = {
            'route': '',
            'date': '2021-01-01',
            'duration': '02:30',
        }
        form = FlightForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('route', form.errors)


class AircraftFormTests(TestCase):
    def test_aircraft_form_valid(self):
        data = {
            'aircraft_type': 'C172',
            'turbine': False,
            'piston': True,
            'requires_type': False,
            'tailwheel': False,
            'simple': True,
            'compleks': False,
            'high_performance': False,
            'aircraft_category': 'A',
            'aircraft_class': 'SEL',
            'superr': False,
            'heavy': False,
            'large': False,
            'medium': False,
            'small': True,
            'light_sport': False,
        }
        form = AircraftForm(data=data)
        self.assertTrue(form.is_valid(), msg=form.errors)

    def test_aircraft_form_invalid_missing_type(self):
        data = {
            'aircraft_type': '',
            'turbine': False,
        }
        form = AircraftForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('aircraft_type', form.errors)


class TailNumberFormTests(TestCase):
    def test_tailnumber_form_valid(self):
        # First create a user and an aircraft for the foreign keys if needed
        user = User.objects.create_user(username='temp', password='pass')
        # Create minimal aircraft if the form includes an aircraft field
        from flights.models import Aircraft
        aircraft = Aircraft.objects.create(
            user=user, aircraft_type='C172', piston=True, turbine=False,
            requires_type=False, tailwheel=False, simple=True, compleks=False,
            high_performance=False, aircraft_category='A', aircraft_class='SEL',
            superr=False, heavy=False, large=False, medium=False, small=True,
            light_sport=False
        )

        data = {
            'registration': 'N12345',
            'aircraft': aircraft.pk,
            'is_121': True,
            'is_135': False,
            'is_91': False,
        }
        form = TailNumberForm(data=data)
        self.assertTrue(form.is_valid(), msg=form.errors)

    def test_tailnumber_form_invalid_blank_registration(self):
        data = {
            'registration': '',
            'is_121': False,
        }
        form = TailNumberForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('registration', form.errors)
