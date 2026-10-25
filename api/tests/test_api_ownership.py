from datetime import date

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from flights.models import Aircraft, Flight, TailNumber


@override_settings(SECURE_SSL_REDIRECT=False)
class APIRecordOwnershipTests(APITestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username='api_owner')
        self.other = get_user_model().objects.create_user(username='api_other')
        self.aircraft = Aircraft.objects.create(user=self.owner, aircraft_type='C172')
        self.other_aircraft = Aircraft.objects.create(user=self.other, aircraft_type='A320')
        self.tail = TailNumber.objects.create(
            user=self.owner, aircraft=self.aircraft, registration='NOWN',
        )
        self.other_tail = TailNumber.objects.create(
            user=self.other, aircraft=self.other_aircraft, registration='NOTHER',
        )
        self.flight = self.make_flight(self.owner, self.aircraft, self.tail)
        self.other_flight = self.make_flight(self.other, self.other_aircraft, self.other_tail)
        self.client.force_authenticate(self.owner)

    def make_flight(self, user, aircraft, tail):
        return Flight.objects.create(
            user=user, aircraft_type=aircraft, registration=tail,
            date=date(2026, 1, 1), route='KJFK-KLAX', duration='1.0',
            remarks='Original',
        )

    def flight_payload(self, **overrides):
        data = {
            'user': self.other.pk,
            'date': '01/02/2026', 'route': 'KJFK-KLAX', 'duration': '1.5',
            'aircraft_type': self.aircraft.aircraft_type,
            'registration': self.tail.registration, 'approaches': [],
        }
        data.update(overrides)
        return data

    def test_aircraft_creation_ignores_spoofed_owner(self):
        response = self.client.post('/api/aircraft/', {
            'user': self.other.pk, 'aircraft_type': 'DA40',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(Aircraft.objects.get(pk=response.data['id']).user_id, self.owner.pk)

    def test_aircraft_owner_cannot_be_changed(self):
        response = self.client.patch(f'/api/aircraft/{self.aircraft.pk}/', {
            'user': self.other.pk, 'aircraft_type': 'DA40',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.aircraft.refresh_from_db()
        self.assertEqual(self.aircraft.user_id, self.owner.pk)

    def test_tail_creation_ignores_spoofed_owner_and_accepts_type_string(self):
        response = self.client.post('/api/tailnumbers/', {
            'user': self.other.pk, 'registration': 'NNEW',
            'aircraft': self.aircraft.aircraft_type,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        tail = TailNumber.objects.get(pk=response.data['id'])
        self.assertEqual(tail.user_id, self.owner.pk)
        self.assertEqual(tail.aircraft_id, self.aircraft.pk)

    def test_tail_owner_cannot_be_changed(self):
        response = self.client.patch(f'/api/tailnumbers/{self.tail.pk}/', {
            'user': self.other.pk,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.tail.refresh_from_db()
        self.assertEqual(self.tail.user_id, self.owner.pk)

    def test_tail_creation_rejects_another_users_aircraft(self):
        response = self.client.post('/api/tailnumbers/', {
            'user': self.other.pk, 'registration': 'NBAD',
            'aircraft': self.other_aircraft.pk,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(TailNumber.objects.filter(registration='NBAD').exists())

    def test_tail_update_rejects_foreign_aircraft_before_changes(self):
        response = self.client.patch(f'/api/tailnumbers/{self.tail.pk}/', {
            'registration': 'NCHANGED', 'aircraft': self.other_aircraft.aircraft_type,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.tail.refresh_from_db()
        self.assertEqual(self.tail.registration, 'NOWN')
        self.assertEqual(self.tail.aircraft_id, self.aircraft.pk)

    def test_flight_creation_ignores_spoofed_owner(self):
        response = self.client.post('/api/flights/', self.flight_payload(), format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        flight = Flight.objects.get(pk=response.data['id'])
        self.assertEqual(flight.user_id, self.owner.pk)
        self.assertEqual(flight.aircraft_type_id, self.aircraft.pk)
        self.assertEqual(flight.registration_id, self.tail.pk)

    def test_flight_creation_does_not_require_client_owner(self):
        data = self.flight_payload()
        data.pop('user')
        response = self.client.post('/api/flights/', data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['user'], self.owner.pk)

    def test_flight_creation_rejects_foreign_relationships(self):
        before = Flight.objects.count()
        for field, value in (
            ('aircraft_type', self.other_aircraft.aircraft_type),
            ('registration', self.other_tail.registration),
        ):
            with self.subTest(field=field):
                response = self.client.post(
                    '/api/flights/', self.flight_payload(**{field: value}), format='json',
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(Flight.objects.count(), before)

    def test_flight_owner_cannot_be_changed(self):
        response = self.client.patch(f'/api/flights/{self.flight.pk}/', {
            'user': self.other.pk, 'remarks': 'Updated',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.flight.refresh_from_db()
        self.assertEqual(self.flight.user_id, self.owner.pk)
        self.assertEqual(self.flight.remarks, 'Updated')

    def test_flight_update_rejects_foreign_tail_before_changes(self):
        response = self.client.patch(f'/api/flights/{self.flight.pk}/', {
            'registration': self.other_tail.registration, 'remarks': 'Changed',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.flight.refresh_from_db()
        self.assertEqual(self.flight.registration_id, self.tail.pk)
        self.assertEqual(self.flight.remarks, 'Original')

    def test_other_users_records_cannot_be_read_updated_or_deleted(self):
        for resource, obj in (
            ('aircraft', self.other_aircraft), ('tailnumbers', self.other_tail),
            ('flights', self.other_flight),
        ):
            url = f'/api/{resource}/{obj.pk}/'
            for method in ('get', 'patch', 'delete'):
                with self.subTest(resource=resource, method=method):
                    response = getattr(self.client, method)(url, {}, format='json')
                    self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
            self.assertTrue(type(obj).objects.filter(pk=obj.pk, user=self.other).exists())

    def test_duplicate_aircraft_validates_against_authenticated_owner(self):
        response = self.client.post('/api/aircraft/', {
            'user': self.other.pk, 'aircraft_type': self.aircraft.aircraft_type,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Aircraft.objects.filter(user=self.owner, aircraft_type='C172').count(), 1)

    def test_duplicate_tail_validates_against_authenticated_owner(self):
        response = self.client.post('/api/tailnumbers/', {
            'user': self.other.pk, 'registration': self.tail.registration,
            'aircraft': self.aircraft.pk,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(TailNumber.objects.filter(user=self.owner, registration='NOWN').count(), 1)
