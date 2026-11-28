from datetime import date
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import override_settings
from django import forms
from rest_framework.test import APITestCase
from flights.models import Flight
from flights.forms import FlightForm
from csv_app.tests.record_fixtures import seed_records
from csv_app.tests.airport_fixtures import seed_airports


@override_settings(SECURE_SSL_REDIRECT=False)
class NightFullStopTests(APITestCase):
    def setUp(self):
        seed_airports()
        self.user=get_user_model().objects.create_user('night-full-stop')
        self.aircraft,self.tail=seed_records(self.user)
        self.client.force_authenticate(self.user)
        self.base=dict(user=self.user,date=date(2026,11,27),aircraft_type=self.aircraft,
            registration=self.tail,route='KIAH-KCLL',duration=Decimal('2.0'))

    def test_full_stop_requires_count_and_night_but_unrecorded_historical_status_is_allowed(self):
        data={'date':'11/27/2026','duration':'2.0','route':'KIAH-KCLL','aircraft_type':self.aircraft.pk,
              'registration':self.tail.pk,'pilot_in_command':True,'night_landings_full_stop':True}
        form=FlightForm(user=self.user,data=data)
        self.assertIn('night_landings_full_stop',form.errors)
        self.assertIn('night',form.errors)
        form=FlightForm(user=self.user,data={**data,'landings_night':1,'night':'.1'})
        self.assertIsInstance(form.fields['night_landings_full_stop'].widget,forms.CheckboxInput)
        self.assertTrue(form.is_valid(),form.errors)
        f=form.save(commit=False);f.user=self.user;f.save()
        self.assertTrue(f.night_landings_full_stop)
        old=Flight.objects.create(**self.base,landings_night=1,pilot_in_command=True)
        self.assertIsNone(old.night_landings_full_stop)

    def test_api_rejects_full_stop_without_night_and_preserves_unrecorded_on_unrelated_edit(self):
        flight=Flight.objects.create(**self.base,pilot_in_command=True)
        url=f'/api/flights/{flight.pk}/'
        response=self.client.patch(url,{'night_landings_full_stop':True},format='json')
        self.assertEqual(response.status_code,400,response.data)
        self.assertIn('night_landings_full_stop',response.data)
        self.assertIn('night',response.data)
        response=self.client.patch(url,{'remarks':'Updated'},format='json')
        self.assertEqual(response.status_code,200,response.data)
        flight.refresh_from_db()
        self.assertIsNone(flight.night_landings_full_stop)
        response=self.client.patch(url,{'night_landings_full_stop':True,'landings_night':1,'night':'0.1'},format='json')
        self.assertEqual(response.status_code,200,response.data)
        flight.refresh_from_db()
        self.assertTrue(flight.night_landings_full_stop)
