from datetime import date

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from flights.models import Aircraft, Approach, Flight, TailNumber


@override_settings(SECURE_SSL_REDIRECT=False)
class FlightApproachOwnershipTests(APITestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username='approach_owner')
        self.other = get_user_model().objects.create_user(username='approach_other')
        self.flight = self.make_flight(self.owner, 'OWNER')
        self.other_flight = self.make_flight(self.other, 'OTHER')
        self.sibling_flight = self.make_flight(self.owner, 'SIBLING')
        self.approach = Approach.objects.create(
            flight_object=self.flight, approach_type='ILS', number=1,
        )
        self.other_approach = Approach.objects.create(
            flight_object=self.other_flight, approach_type='ILS', number=1,
        )
        self.sibling_approach = Approach.objects.create(
            flight_object=self.sibling_flight, approach_type='ILS', number=1,
        )
        self.client.force_authenticate(self.owner)
        self.url = f'/api/flights/{self.flight.pk}/'

    def make_flight(self, user, suffix):
        aircraft = Aircraft.objects.create(user=user, aircraft_type=suffix)
        tail = TailNumber.objects.create(
            user=user, aircraft=aircraft, registration='N' + suffix,
        )
        return Flight.objects.create(
            user=user, aircraft_type=aircraft, registration=tail,
            date=date(2026, 1, 1), route='KJFK-KLAX', duration='1.0',
            remarks='Original',
        )

    def patch_approaches(self, rows, **fields):
        return self.client.patch(self.url, {'approaches': rows, **fields}, format='json')

    def test_other_users_approach_is_rejected(self):
        response = self.patch_approaches([
            {'id': self.other_approach.pk, 'approach_type': 'GPS', 'number': 3},
        ])

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.other_approach.refresh_from_db()
        self.assertEqual(self.other_approach.number, 1)
        self.assertEqual(self.other_approach.approach_type, 'ILS')
        self.assertEqual(self.other_approach.flight_object_id, self.other_flight.pk)

    def test_same_users_other_flight_approach_is_rejected(self):
        response = self.patch_approaches([
            {'id': self.sibling_approach.pk, 'approach_type': 'GPS', 'number': 3},
        ])

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.sibling_approach.refresh_from_db()
        self.assertEqual(self.sibling_approach.number, 1)

    def test_mixed_payload_cannot_partially_modify_flight_or_approaches(self):
        response = self.patch_approaches([
            {'id': self.approach.pk, 'approach_type': 'GPS', 'number': 2},
            {'approach_type': 'VOR', 'number': 1},
            {'id': self.other_approach.pk, 'approach_type': 'GPS', 'number': 3},
        ], remarks='Changed')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.flight.refresh_from_db()
        self.approach.refresh_from_db()
        self.assertEqual(self.flight.remarks, 'Original')
        self.assertEqual(self.approach.number, 1)
        self.assertEqual(Approach.objects.filter(flight_object=self.flight).count(), 1)

    def test_approach_cannot_be_reparented(self):
        response = self.patch_approaches([
            {'id': self.approach.pk, 'flight_object': self.other_flight.pk,
             'approach_type': 'GPS', 'number': 2},
        ])

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.approach.refresh_from_db()
        self.assertEqual(self.approach.flight_object_id, self.flight.pk)

    def test_owner_can_update_and_add_approaches(self):
        response = self.patch_approaches([
            {'id': self.approach.pk, 'flight_object': self.flight.pk,
             'approach_type': 'GPS', 'number': 2},
            {'approach_type': 'VOR', 'number': 1},
        ])

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.approach.refresh_from_db()
        self.assertEqual(self.approach.number, 2)
        self.assertEqual(self.approach.approach_type, 'GPS')
        self.assertTrue(Approach.objects.filter(
            flight_object=self.flight, approach_type='VOR', number=1,
        ).exists())

    def test_invalid_nested_number_is_rejected_before_flight_changes(self):
        response = self.patch_approaches([
            {'id': self.approach.pk, 'approach_type': 'GPS', 'number': -1},
        ], remarks='Changed')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.flight.refresh_from_db()
        self.assertEqual(self.flight.remarks, 'Original')

    def test_missing_approach_id_is_rejected(self):
        unused_id = max(self.approach.pk, self.other_approach.pk, self.sibling_approach.pk) + 1
        response = self.patch_approaches([
            {'id': unused_id, 'approach_type': 'GPS', 'number': 2},
        ])

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_other_users_flight_cannot_be_updated(self):
        response = self.client.patch(
            f'/api/flights/{self.other_flight.pk}/',
            {'approaches': [], 'remarks': 'Changed'}, format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.other_flight.refresh_from_db()
        self.assertEqual(self.other_flight.remarks, 'Original')
