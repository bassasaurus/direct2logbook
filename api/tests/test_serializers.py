# api/tests/test_serializers.py
from unittest import mock
from unittest.mock import patch
from types import SimpleNamespace
from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from flights.models import Aircraft, TailNumber, Flight
from api.serializers import TailNumberSerializer
from api.serializers import AircraftSerializer
from api.serializers import FlightSerializer


User = get_user_model()


class TailNumberSerializerTests(TestCase):
    def setUp(self):
        # Ensure the "clients" group exists for signals that may expect it
        Group.objects.get_or_create(name='clients')
        self.user = User.objects.create_user(
            username="ser_user",
            email="ser_user@example.com",
            password="pw12345",
        )
        # Keep this minimal; just what TailNumberSerializer expects to resolve.
        self.aircraft = Aircraft.objects.create(
            user=self.user,
            aircraft_type="C172",   # whatever your __str__ uses is fine
        )

    def test_create_uses_initial_data_to_resolve_aircraft_fk(self):
        """
        TailNumberSerializer.create should grab `aircraft` from initial_data,
        set the FK, and persist a real TailNumber.
        """
        data = {
            "user": self.user.id,
            "registration": "N123AB",
            "aircraft": self.aircraft.pk,  # important: pk passed via initial_data
            "is_121": False,
            "is_135": False,
            "is_91": True,
        }
        ser = TailNumberSerializer(data=data)
        self.assertTrue(ser.is_valid(), ser.errors)

        obj = ser.save()
        self.assertIsInstance(obj, TailNumber)
        self.assertEqual(obj.user, self.user)
        self.assertEqual(obj.registration, "N123AB")
        self.assertEqual(obj.aircraft, self.aircraft)
        self.assertTrue(obj.is_91)
        self.assertFalse(obj.is_121)
        self.assertFalse(obj.is_135)

    def test_read_serialization_returns_string_related_aircraft(self):
        """
        Read-serialize a TailNumber and ensure `aircraft` uses StringRelatedField.
        """
        tn = TailNumber.objects.create(
            user=self.user,
            registration="N987XY",
            aircraft=self.aircraft,
            is_121=False,
            is_135=True,
            is_91=False,
        )

        ser = TailNumberSerializer(instance=tn)
        payload = ser.data

        # Fields explicitly listed in serializer
        self.assertEqual(payload["id"], tn.id)
        self.assertEqual(payload["user"], self.user.id)
        self.assertEqual(payload["registration"], "N987XY")
        # StringRelatedField: should be the string form of the aircraft
        self.assertEqual(payload["aircraft"], str(self.aircraft))
        self.assertEqual(payload["is_121"], False)
        self.assertEqual(payload["is_135"], True)
        self.assertEqual(payload["is_91"], False)


class AircraftSerializerTests(TestCase):
    def setUp(self):
        # Avoid signal explosions that expect the group to exist.
        Group.objects.get_or_create(name='clients')

        self.user = User.objects.create_user(
            username="air_user",
            email="air_user@example.com",
            password="pw12345",
        )

        # Keep the model usage minimal — only fields we know exist.
        self.aircraft = Aircraft.objects.create(
            user=self.user,
            aircraft_type="C172",
        )

    def test_create_aircraft(self):
        """
        AircraftSerializer should create an Aircraft tied to the given user.
        """
        data = {
            "user": self.user.id,
            "aircraft_type": "PA-28",
        }
        ser = AircraftSerializer(data=data)
        self.assertTrue(ser.is_valid(), ser.errors)

        obj = ser.save()
        self.assertIsInstance(obj, Aircraft)
        self.assertEqual(obj.user, self.user)
        self.assertEqual(obj.aircraft_type, "PA-28")

    def test_update_aircraft(self):
        """
        AircraftSerializer should update editable fields (e.g., aircraft_type).
        """
        ser = AircraftSerializer(instance=self.aircraft, data={
                                 "aircraft_type": "DA40"}, partial=True)
        self.assertTrue(ser.is_valid(), ser.errors)

        obj = ser.save()
        self.assertEqual(obj.pk, self.aircraft.pk)
        self.assertEqual(obj.aircraft_type, "DA40")

    def test_read_serialization_includes_id_and_maybe_fields(self):
        """
        Read-serialize the Aircraft. We assert the ID always, and if the
        serializer exposes 'aircraft_type' or 'user', we check their values.
        (Some projects intentionally omit 'user' from read payloads.)
        """
        ser = AircraftSerializer(instance=self.aircraft)
        payload = ser.data

        # id should always be present from a ModelSerializer
        self.assertIn("id", payload)
        self.assertEqual(payload["id"], self.aircraft.id)

        # If aircraft_type is in the serializer, it should match.
        if "aircraft_type" in payload:
            self.assertEqual(payload["aircraft_type"], "C172")

        # If user is exposed, it should be the user's id
        if "user" in payload:
            self.assertEqual(payload["user"], self.user.id)


class FlightSerializerTest(TestCase):
    def setUp(self):
        # Create the Group used by your user signals
        Group.objects.get_or_create(name="clients")

        # Mock Stripe in the user profile signals so creating a user is safe.
        stripe_patcher = patch("profile.signal_profile.stripe", autospec=True)
        self.addCleanup(stripe_patcher.stop)
        self.mock_stripe = stripe_patcher.start()

        # Minimal fake responses your signals expect
        self.mock_stripe.Customer.create.return_value = SimpleNamespace(
            id="cus_test_123")
        # trial_end is read in the signal, so give it something date-like (unix ts)
        self.mock_stripe.Subscription.create.return_value = SimpleNamespace(
            id="sub_test_123",
            trial_end=1700000000,
            status="trialing",
        )

        User = get_user_model()
        self.user = User.objects.create_user(
            username="pilot",
            email="pilot@example.com",
            password="secret",
        )

        # Required relateds
        self.aircraft = Aircraft.objects.create(
            user=self.user,
            aircraft_type="A320",
            turbine=True,
            piston=False,
            requires_type=False,
            tailwheel=False,
            simple=False,
            compleks=False,
            high_performance=False,
            aircraft_category="A",
            aircraft_class="MEL",
        )

        self.tail = TailNumber.objects.create(
            user=self.user,
            registration="N123AB",
            aircraft=self.aircraft,
            is_121=False,
            is_135=False,
            is_91=True,
        )

    def test_flight_serializer_create_valid(self):
        data = {
            "user": self.user.id,
            "date": date(2025, 1, 2),
            "aircraft_type": "A320",
            "registration": "N123AB",
            "route": "KJFK-KLAX",
            "duration": "1.5",
            "pilot_in_command": True,
            "landings_day": 2,
            "approaches": [],
        }
        ser = FlightSerializer(data=data)
        self.assertTrue(ser.is_valid(), ser.errors)
        instance = ser.save()
        self.assertIsInstance(instance, Flight)
        self.assertEqual(instance.user, self.user)
        self.assertEqual(instance.aircraft_type, self.aircraft)
        self.assertEqual(instance.registration, self.tail)
        self.assertEqual(str(instance.duration), "1.5")
        self.assertTrue(instance.pilot_in_command)
        self.assertEqual(instance.landings_day, 2)
        self.assertEqual(instance.route, "KJFK-KLAX")

    def test_flight_serializer_rejects_negative_duration(self):
        data = {
            "user": self.user.id,
            "date": date(2025, 1, 2),
            "aircraft_type": "A320",
            "registration": "N123AB",
            "route": "KDEN-KSFO",
            "duration": "-0.1",
            "approaches": [],
        }
        ser = FlightSerializer(data=data)
        self.assertFalse(ser.is_valid())
        # Should flag the validator on duration
        self.assertIn("duration", ser.errors)

    def test_flight_serializer_missing_required_route(self):
        data = {
            "user": self.user.id,
            "date": date(2025, 1, 2),
            "aircraft_type": "A320",
            "registration": "N123AB",
            # Intentionally omit "route" to assert required validation
            "duration": "0.7",
            "approaches": [],
        }
        ser = FlightSerializer(data=data)
        self.assertFalse(ser.is_valid())
        # route should be flagged as required
        self.assertIn("route", ser.errors)
