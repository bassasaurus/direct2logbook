from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from flights.forms import FlightForm
from flights.models import Flight
from csv_app.tests.record_fixtures import seed_records
from csv_app.tests.airport_fixtures import seed_airports
from csv_app.tests.test_atomic_import import content, row
from csv_app.validation import parse_csv, CSVValidationError
from csv_app.rows import stage_rows, validate_rows
from csv_app.csv_import import csv_import


@override_settings(SECURE_SSL_REDIRECT=False)
class NightDurationTests(APITestCase):
    def setUp(self):
        seed_airports()
        self.user=get_user_model().objects.create_user('night-duration')
        self.aircraft,self.tail=seed_records(self.user)
        self.client.force_authenticate(self.user)
        self.data={'date':'2026-10-20','duration':'1.2','route':'KIAH-KCLL','pilot_in_command':True}
        self.web={**self.data,'aircraft_type':self.aircraft.pk,'registration':self.tail.pk}
        self.api={**self.data,'date':'10/20/2026','aircraft_type':'C172','registration':'N12345'}

    def test_new_web_and_api_accept_equal_less_zero_and_blank_night(self):
        for night in ('1.2','0.3','0',''):
            with self.subTest(night=night):
                form=FlightForm(user=self.user,data={**self.web,'night':night})
                self.assertTrue(form.is_valid(),form.errors)
                response=self.client.post('/api/flights/',{**self.api,'night':night},format='json')
                self.assertEqual(response.status_code,201,response.data)

    def test_web_and_api_reject_excess_night_without_saving(self):
        form=FlightForm(user=self.user,data={**self.web,'night':'1.3'})
        self.assertEqual(form.errors['night'],['Night cannot exceed Duration.'])
        response=self.client.post('/api/flights/',{**self.api,'night':'1.3'},format='json')
        self.assertEqual(response.status_code,400,response.data)
        self.assertEqual(str(response.data['night'][0]),'Night cannot exceed Duration.')
        self.assertFalse(Flight.objects.filter(user=self.user).exists())

    def test_duration_only_and_night_only_updates_check_stored_other_value(self):
        flight=Flight.objects.create(user=self.user,aircraft_type=self.aircraft,registration=self.tail,
            date=date(2026,10,20),duration=Decimal('1.5'),night=Decimal('1.2'),route='KIAH-KCLL',pilot_in_command=True)
        form=FlightForm(user=self.user,instance=flight,data={**self.web,'duration':'1.0','night':'1.2'})
        self.assertIn('night',form.errors)
        for changes in ({'duration':'1.1'},{'night':'1.6'}):
            response=self.client.patch(f'/api/flights/{flight.pk}/',changes,format='json')
            self.assertEqual(response.status_code,400,response.data)
            self.assertIn('night',response.data)
            flight.refresh_from_db()
            self.assertEqual((flight.duration,flight.night),(Decimal('1.5'),Decimal('1.2')))
        response=self.client.patch(f'/api/flights/{flight.pk}/',{'duration':'1.0','night':'1.0'},format='json')
        self.assertEqual(response.status_code,200,response.data)

    def test_csv_row_error_is_editable_and_invalid_import_is_atomic(self):
        invalid=content([row(),row(**{'8':'1.6'})])
        with self.assertRaisesRegex(CSVValidationError,'Night: Night cannot exceed Duration.'):
            csv_import(SimpleNamespace(user=self.user),invalid)
        self.assertFalse(Flight.objects.filter(user=self.user).exists())
        data=stage_rows(invalid)
        errors=validate_rows(self.user,data)
        self.assertEqual(errors[3]['night'],'Night cannot exceed Duration.')
        data['rows'][1]['values'][8]='1.5'
        self.assertEqual(validate_rows(self.user,data),{})
        for night in ('','0','0.3','1.5'):
            parsed,_=parse_csv(content([row(**{'8':night})]))
            self.assertLessEqual(parsed[0]['night'],parsed[0]['duration'])
