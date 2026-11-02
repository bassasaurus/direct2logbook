from datetime import date
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from csv_app.csv_import import save_route_data as csv_route_data
from flights.airport_resolution import resolve_route, map_values, warning_values
from flights.forms import AirportConfirmationForm
from flights.models import Aircraft, Flight, MapData, TailNumber, Total
from flights.signal_error_flight import update_route_warnings
from flights.signal_route_data import save_route_data
from flights.signal_make_json_field import make_json_field


@override_settings(SECURE_SSL_REDIRECT=False)
class AirportResolutionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='airport_owner')
        self.other = get_user_model().objects.create_user(username='airport_other')
        self.user.profile.trial = True
        self.user.profile.save()
        self.aircraft = Aircraft.objects.create(user=self.user, aircraft_type='C172',
                                               aircraft_category='A', aircraft_class='SEL')
        self.tail = TailNumber.objects.create(user=self.user, aircraft=self.aircraft, registration='N123A')
        self.client.force_login(self.user)
        self.bqn_us = self.airport('BQN', 'TJBQ', 'Aguadilla', 'United States', 18.49, -67.12)
        self.bqn_pr = self.airport('BQN', 'TJBQ', 'Rafael Hernandez', 'Puerto Rico', 18.49001, -67.12001)
        self.bbg_us = self.airport('BBG', 'KBBG', 'Branson', 'United States', 36.53, -93.20)
        self.bbg_other = self.airport('BBG', 'NGTU', 'Butaritari', 'Kiribati', 3.08, 172.81)
        self.lbx_us = self.airport('LBX', 'KLBX', 'Texas Gulf Coast', 'United States', 29.10, -95.46)
        self.lbx_other = self.airport('LBX', 'RPLU', 'Lubang', 'Philippines', 13.85, 120.10)
        self.foreign = self.airport('ZZZ', 'EGZZ', 'Foreign airport', 'United Kingdom', 50, -1)

    def airport(self, code, icao, name, country, lat=10, lon=20):
        return MapData.objects.create(iata=code, icao=icao, name=name, city=name,
                                       country=country, latitude=lat, longitude=lon)

    def flight(self, route, user=None, **kwargs):
        return Flight.objects.bulk_create([Flight(user=user or self.user, route=route,
            date=date(2025, 1, 1), aircraft_type=self.aircraft, registration=self.tail,
            duration=1, pilot_in_command=True, **kwargs)])[0]

    def test_bqn_bbg_lbx_use_us_airports_without_warning_or_code_conversion(self):
        resolution = resolve_route('BQN-BBG-LBX')
        self.assertEqual([item['airport'].pk for item in resolution],
                         [self.bqn_us.pk, self.bbg_us.pk, self.lbx_us.pk])
        self.assertEqual(warning_values(resolution), {'map_error': '', 'duplicate_error': ''})

    def test_four_character_icao_selects_foreign_airport_directly(self):
        result = resolve_route('RPLU-NGTU')
        self.assertEqual([item['airport'].pk for item in result], [self.lbx_other.pk, self.bbg_other.pk])
        self.assertFalse(any(item['needs_confirmation'] for item in result))

    def test_country_is_database_value_not_user_location(self):
        self.lbx_us.country = ' united states '
        self.lbx_us.save()
        self.assertEqual(resolve_route('LBX')[0]['airport'].pk, self.lbx_us.pk)
        result = resolve_route('ZZZ')[0]
        self.assertTrue(result['needs_confirmation'])
        self.assertEqual([airport.pk for airport in result['candidates']], [self.foreign.pk])
        self.assertEqual(map_values([result])['route_data'], [])

    def test_two_distinct_us_airports_prompt_but_duplicate_icao_rows_do_not(self):
        self.assertEqual(len(resolve_route('BQN')[0]['candidates']), 1)
        second = self.airport('LBX', 'KXYZ', 'Other US airport', 'United States')
        result = resolve_route('LBX')[0]
        self.assertTrue(result['needs_confirmation'])
        self.assertEqual({airport.pk for airport in result['candidates']}, {self.lbx_us.pk, second.pk})

    def test_web_app_and_csv_resolve_to_same_airports_without_recursive_save(self):
        flight = self.flight('BQN-BBG-LBX')
        update_route_warnings(Flight, flight)
        save_route_data(Flight, flight)
        with patch.object(flight, 'save', side_effect=AssertionError('No recursive save')):
            make_json_field(Flight, flight)
        flight.refresh_from_db()
        expected = [self.bqn_us.pk, self.bbg_us.pk, self.lbx_us.pk]
        self.assertEqual([airport.pk for airport in flight.route_data], expected)
        self.assertEqual([airport.pk for airport in csv_route_data(self.user, flight.route)], expected)
        self.assertEqual([item['icao'] for item in flight.app_markers], ['TJBQ', 'KBBG', 'KLBX'])
        self.assertFalse(flight.map_error or flight.duplicate_error)
        self.assertEqual(flight.route, 'BQN-BBG-LBX')

    def test_confirm_saves_to_flight_only_and_refreshes_maps(self):
        flight = self.flight('BQN-ZZZ')
        original_totals = list(Total.objects.order_by('pk').values())
        response = self.client.post(reverse('confirm_flight_airports', args=[flight.pk]),
                                    {'route': flight.route, 'airport_1': str(self.foreign.pk)})
        self.assertEqual(response.status_code, 302)
        flight.refresh_from_db()
        self.assertEqual(flight.route, 'BQN-ZZZ')
        self.assertEqual(flight.route_airport_choices['airports'], {'1': self.foreign.pk})
        self.assertEqual([airport.pk for airport in flight.route_data], [self.bqn_us.pk, self.foreign.pk])
        self.assertEqual([item['icao'] for item in flight.app_markers], ['TJBQ', 'EGZZ'])
        self.assertFalse(flight.duplicate_error)
        self.assertEqual(list(Total.objects.order_by('pk').values()), original_totals)
        self.assertEqual(flight.duration, 1)
        self.assertTrue(resolve_route('ZZZ')[0]['needs_confirmation'])  # Not a user/global preference.

    def test_choice_is_per_occurrence_and_has_no_preselected_default(self):
        second = self.airport('ZZZ', 'LFZZ', 'Another foreign airport', 'France')
        flight = self.flight('ZZZ-BQN-ZZZ')
        form = AirportConfirmationForm(flight=flight)
        self.assertNotIn('checked', str(form['airport_0']))
        response = self.client.post(reverse('confirm_flight_airports', args=[flight.pk]),
            {'route': flight.route, 'airport_0': str(self.foreign.pk), 'airport_2': str(second.pk)})
        self.assertEqual(response.status_code, 302)
        flight.refresh_from_db()
        self.assertEqual([airport.pk for airport in flight.route_data], [self.foreign.pk, self.bqn_us.pk, second.pk])

    def test_ownership_csrf_and_get_cannot_change_choices(self):
        foreign = self.flight('ZZZ', user=self.other)
        data = {'route': 'ZZZ', 'airport_0': str(self.foreign.pk)}
        self.assertEqual(self.client.post(reverse('confirm_flight_airports', args=[foreign.pk]), data).status_code, 404)
        owned = self.flight('ZZZ')
        url = reverse('confirm_flight_airports', args=[owned.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(csrf.post(url, data).status_code, 403)
        owned.refresh_from_db()
        self.assertEqual(owned.route_airport_choices, {})

    def test_invalid_airport_and_stale_route_are_rejected(self):
        flight = self.flight('ZZZ')
        url = reverse('confirm_flight_airports', args=[flight.pk])
        for data in ({'route': 'ZZZ', 'airport_0': str(self.lbx_other.pk)},
                     {'route': 'OLD', 'airport_0': str(self.foreign.pk)}):
            self.assertEqual(self.client.post(url, data).status_code, 400)
        flight.refresh_from_db()
        self.assertEqual(flight.route_airport_choices, {})

    def test_route_edits_clear_choices_and_a_new_flight_does_not_inherit_them(self):
        flight = self.flight('ZZZ', route_airport_choices={'route': 'ZZZ', 'airports': {'0': self.foreign.pk}})
        flight.route = 'LBX'
        flight.save(update_fields=['route'])
        flight.refresh_from_db()
        self.assertEqual(flight.route_airport_choices, {})
        self.assertEqual(flight.route_data[0].pk, self.lbx_us.pk)
        self.assertTrue(resolve_route('ZZZ')[0]['needs_confirmation'])

    @patch('flights.views.get_map_data')
    def test_confirmation_is_shown_on_detail_and_edit_page(self, get_map):
        flight = self.flight('ZZZ')
        for route in ('flight_detail', 'flight_update'):
            response = self.client.get(reverse(route, args=[flight.pk]))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Which airports did you mean?')
            self.assertContains(response, 'Confirm airports')
            self.assertContains(response, 'btn btn-primary btn-lg')
            self.assertContains(response, 'Foreign airport')

    def test_backfill_preserves_confirmations_and_replaces_wrong_legacy_maps(self):
        flight = self.flight('LBX-ZZZ', route_airport_choices={'route': 'LBX-ZZZ', 'airports': {'1': self.foreign.pk}})
        call_command('refresh_flight_route_warnings', '--refresh-maps', stdout=StringIO())
        flight.refresh_from_db()
        self.assertEqual([airport.pk for airport in flight.route_data], [self.lbx_us.pk, self.foreign.pk])
        self.assertFalse(flight.duplicate_error)
        self.assertEqual(flight.route, 'LBX-ZZZ')

    def test_saved_foreign_choice_can_be_reviewed_and_changed(self):
        second = self.airport('ZZZ', 'LFZZ', 'Another foreign airport', 'France')
        flight = self.flight('ZZZ', route_airport_choices={'route': 'ZZZ', 'airports': {'0': self.foreign.pk}})
        form = AirportConfirmationForm(flight=flight, review=True)
        self.assertEqual(form['airport_0'].value(), str(self.foreign.pk))
        self.assertFalse(form.has_unresolved)
        response = self.client.post(reverse('confirm_flight_airports', args=[flight.pk]),
            {'route': flight.route, 'review': 'True', 'airport_0': str(second.pk)})
        self.assertEqual(response.status_code, 302)
        flight.refresh_from_db()
        self.assertEqual(flight.route_data[0].pk, second.pk)
        self.assertEqual(flight.route, 'ZZZ')

    def test_choice_storage_is_not_editable_in_the_normal_flight_form(self):
        from flights.forms import FlightForm
        self.assertNotIn('route_airport_choices', FlightForm(user=self.user).fields)

    @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
    def test_web_map_consumes_resolved_choices_and_handles_missing_legacy_data(self):
        from types import SimpleNamespace
        from flights.get_map_data import get_map_data
        flight = self.flight('LBX')
        save_route_data(Flight, flight)
        flight.refresh_from_db()
        features, line = get_map_data([flight, SimpleNamespace(route_data=None)], self.user)
        self.assertEqual(len(features['features']), 1)
        self.assertEqual(features['features'][0]['properties']['icao'], 'KLBX')
        self.assertIn(str(self.lbx_us.latitude), line)
        self.assertNotIn(str(self.lbx_other.latitude), line)
