from flights.models import MapData, Aircraft, TailNumber
from flights.forms import FlightForm, AircraftForm, TailNumberForm
from django.test import TestCase
from django.contrib.auth.models import User


class FlightFormTests(TestCase):
    def setUp(self):
        MapData.objects.create(icao='KJFK', iata='JFK', name='John F Kennedy', country='United States')
        MapData.objects.create(icao='KLAX', iata='LAX', name='Los Angeles', country='United States')
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
            'pilot_in_command': True,
        }
        form = FlightForm(data=data, user=self.user)
        self.assertTrue(form.is_valid(), msg=form.errors)

    def test_flight_form_invalid_blank_route(self):
        data = {
            'route': '',
            'date': '2021-01-01',
            'duration': '02:30',
        }
        form = FlightForm(data=data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('route', form.errors)


class AircraftFormTests(TestCase):
    def test_radio_choices_save_existing_boolean_fields(self):
        form = AircraftForm(data={'aircraft_type': 'C172', 'aircraft_category': 'A',
            'aircraft_class': 'SEL', 'engine': 'piston', 'weight_category': 'small',
            'turbine': True, 'heavy': True})
        self.assertTrue(form.is_valid(), form.errors)
        aircraft = form.save(commit=False)
        self.assertTrue(aircraft.piston)
        self.assertTrue(aircraft.small)
        self.assertFalse(aircraft.turbine)
        self.assertFalse(aircraft.heavy)

    def test_radio_initial_values_reflect_existing_aircraft(self):
        from flights.models import Aircraft
        form = AircraftForm(instance=Aircraft(piston=True, small=True))
        self.assertEqual(form['engine'].value(), 'piston')
        self.assertEqual(form['weight_category'].value(), 'small')

    def test_conflicting_legacy_choices_are_rejected(self):
        form = AircraftForm(data={'aircraft_type': 'C172', 'aircraft_category': 'A',
            'aircraft_class': 'SEL', 'piston': True, 'turbine': True})
        self.assertFalse(form.is_valid())
        self.assertIn('engine', form.errors)

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
    def test_operating_rules_radio_maps_to_saved_booleans(self):
        from flights.models import Aircraft
        owner = User.objects.create_user(username='radio-owner')
        aircraft = Aircraft.objects.create(user=owner, aircraft_type='C172')
        form = TailNumberForm(user=owner, data={'registration': 'N123AB',
            'aircraft': aircraft.pk, 'operating_rules': 'is_135', 'is_91': True})
        self.assertTrue(form.is_valid(), form.errors)
        tailnumber = form.save(commit=False)
        self.assertTrue(tailnumber.is_135)
        self.assertFalse(tailnumber.is_91)
        self.assertFalse(tailnumber.is_121)

    def test_operating_rules_initial_value(self):
        from flights.models import TailNumber
        form = TailNumberForm(instance=TailNumber(is_121=True))
        self.assertEqual(form['operating_rules'].value(), 'is_121')

    def test_conflicting_legacy_rules_are_rejected(self):
        form = TailNumberForm(data={'is_91': True, 'is_135': True})
        self.assertFalse(form.is_valid())
        self.assertIn('operating_rules', form.errors)

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
        form = TailNumberForm(data=data, user=user)
        self.assertTrue(form.is_valid(), msg=form.errors)

    def test_tailnumber_form_invalid_blank_registration(self):
        data = {
            'registration': '',
            'is_121': False,
        }
        form = TailNumberForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('registration', form.errors)
