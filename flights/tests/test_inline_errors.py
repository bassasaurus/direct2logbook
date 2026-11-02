from datetime import date
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from flights.error_checks import flight_error_filter, route_warning_values
from flights.models import Aircraft, Flight, MapData, Stat, TailNumber, Total
from flights.signal_error_flight import update_route_warnings


@override_settings(SECURE_SSL_REDIRECT=False)
class InlineErrorTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='inline_owner')
        self.other = get_user_model().objects.create_user(username='inline_other')
        self.user.profile.trial = True
        self.user.profile.save()
        self.aircraft = Aircraft.objects.create(user=self.user, aircraft_type='C172', piston=True,
            simple=True, small=True, aircraft_category='A', aircraft_class='SEL')
        self.tail = TailNumber.objects.create(user=self.user, aircraft=self.aircraft, registration='N123A', is_91=True)
        self.client.force_login(self.user)
        self.first = MapData.objects.create(icao='KAAA', iata='AAA', country='United States')
        MapData.objects.create(icao='KBBB', iata='BBB', country='United States')

    def flight(self, user=None, **kwargs):
        values = dict(user=user or self.user, date=date(2025, 1, 1), aircraft_type=self.aircraft,
                      registration=self.tail, route='KAAA-KBBB', duration=1, pilot_in_command=True)
        values.update(kwargs)
        return Flight.objects.bulk_create([Flight(**values)])[0]

    def test_error_row_uses_red_text_and_update_link(self):
        bad = self.flight(map_error='Unknown airport codes: XXXX')
        good = self.flight()
        response = self.client.get(reverse('flight_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'text-danger logbook-row-error')
        self.assertContains(response, f'href="{reverse("flight_update", args=[bad.pk])}" class="btn btn-sm btn-outline-danger">Update')
        self.assertContains(response, f'href ="{reverse("flight_detail", args=[good.pk])}" class="btn btn-sm btn-outline-primary">View')
        self.assertContains(response, '1 flight needs attention')
        self.assertContains(response, 'Unknown airport codes: XXXX')

    def test_summary_finds_errors_beyond_page_and_never_leaks_other_users(self):
        for index in range(40):
            self.flight(date=date(2026, 1, 1))
        bad = self.flight(map_error='OWNER-ERROR')
        foreign = self.flight(user=self.other, map_error='FOREIGN-ERROR')
        response = self.client.get(reverse('flight_list'))
        self.assertEqual(response.context['flight_error_count'], 1)
        self.assertNotIn(bad.pk, [flight.pk for flight in response.context['object_list']])
        self.assertContains(response, reverse('flight_update', args=[bad.pk]))
        self.assertNotContains(response, 'FOREIGN-ERROR')
        self.assertNotContains(response, reverse('flight_update', args=[foreign.pk]))

    def test_error_filter_preserves_pagination_and_summary_is_bounded(self):
        for index in range(41):
            self.flight(crew_error='Please select a crew position.')
        good = self.flight()
        response = self.client.get(reverse('flight_list') + '?errors=1')
        self.assertEqual(response.context['paginator'].count, 41)
        self.assertEqual(len(response.context['flight_error_summary']), 10)
        self.assertContains(response, '?errors=1&amp;page=2')
        self.assertNotIn(good.pk, [flight.pk for flight in response.context['object_list']])
        response = self.client.get(reverse('flight_list') + '?errors=1&page=2')
        self.assertEqual(len(response.context['object_list']), 1)

    def test_null_and_short_duration_match_displayed_error_predicate(self):
        for duration in (None, 0):
            flight = self.flight(duration=duration)
            self.assertTrue(flight.has_errors)
            self.assertTrue(Flight.objects.filter(pk=flight.pk).filter(flight_error_filter()).exists())
            self.assertIn('Please check the duration of this flight.', flight.validation_errors)
        self.assertFalse(self.flight(duration=Decimal('0.1')).has_errors)

    def test_healthy_logbook_has_no_error_summary(self):
        self.flight()
        response = self.client.get(reverse('flight_list'))
        self.assertNotContains(response, '<details class="alert alert-danger"')
        response = self.client.get(reverse('flight_list') + '?errors=1')
        self.assertContains(response, 'No flights need attention.')

    @patch('flights.views.get_map_data')
    def test_flight_errors_are_above_content_and_escaped_without_modal(self, map_data):
        flight = self.flight(map_error='<script>unsafe</script>')
        response = self.client.get(reverse('flight_detail', args=[flight.pk]))
        self.assertContains(response, 'aria-label="Flight errors"')
        self.assertContains(response, '&lt;script&gt;unsafe&lt;/script&gt;')
        self.assertNotContains(response, '<script>unsafe</script>')
        self.assertNotContains(response, 'id="errors"')
        self.assertLess(response.content.index(b'aria-label="Flight errors"'), response.content.index(b'Previous Flight'))

    @patch('flights.views.get_map_data')
    def test_aircraft_and_tail_errors_are_inline_and_healthy_notices_hidden(self, map_data):
        aircraft_url = reverse('aircraft_detail', args=[self.aircraft.pk])
        tail_url = reverse('tailnumber_detail', args=[self.tail.pk])
        self.assertNotContains(self.client.get(aircraft_url), 'aria-label="Aircraft errors"')
        self.assertNotContains(self.client.get(tail_url), 'aria-label="Tailnumber errors"')
        Aircraft.objects.filter(pk=self.aircraft.pk).update(piston=False)
        TailNumber.objects.filter(pk=self.tail.pk).update(is_91=False)
        for url, label in [(aircraft_url, 'Aircraft'), (tail_url, 'Tailnumber')]:
            response = self.client.get(url)
            self.assertContains(response, f'aria-label="{label} errors"')
            self.assertContains(response, 'class="detail-update btn btn-outline-danger">Update</a>')
            self.assertNotContains(response, 'id="errors"')
        self.assertContains(self.client.get(aircraft_url), 'Please select Piston or Turbine.')
        self.assertContains(self.client.get(tail_url), 'Please select FAR 91, 135 or 121.')

    def test_invalid_codes_survive_valid_later_legs_and_repeat_codes_are_deduplicated(self):
        values = route_warning_values('KAAA-XXXX-YYYY-XXXX-KBBB')
        self.assertEqual(values['map_error'], 'Unknown airport codes: XXXX, YYYY')
        self.assertEqual(values['duplicate_error'], '')

    def test_ambiguous_codes_survive_valid_later_legs_and_clear_after_correction(self):
        MapData.objects.create(icao='KCCC', iata='AAA', country='United States')
        flight = self.flight(route='AAA-KBBB')
        update_route_warnings(Flight, flight)
        flight.refresh_from_db()
        self.assertEqual(flight.duplicate_error, 'Confirm airport locations: AAA')
        self.assertEqual(flight.map_error, '')
        flight.route = 'KAAA-KBBB'
        Flight.objects.filter(pk=flight.pk).update(route=flight.route)
        update_route_warnings(Flight, flight)
        flight.refresh_from_db()
        self.assertFalse(flight.has_errors)

    def test_warning_backfill_dry_run_owner_scope_and_idempotence(self):
        bad = self.flight(route='KAAA-XXXX-KBBB')
        foreign = self.flight(user=self.other, route='YYYY-KBBB')
        args = ('refresh_flight_route_warnings', '--user-id', str(self.user.pk))
        call_command(*args, '--dry-run', stdout=StringIO())
        bad.refresh_from_db()
        self.assertIsNone(bad.map_error)
        totals_before = list(Total.objects.order_by('pk').values())
        stats_before = list(Stat.objects.order_by('pk').values())
        call_command(*args, stdout=StringIO())
        self.assertEqual(list(Total.objects.order_by('pk').values()), totals_before)
        self.assertEqual(list(Stat.objects.order_by('pk').values()), stats_before)
        bad.refresh_from_db()
        foreign.refresh_from_db()
        self.assertEqual(bad.map_error, 'Unknown airport codes: XXXX')
        self.assertIsNone(foreign.map_error)
        self.assertEqual(bad.duration, 1)
        output = StringIO()
        call_command(*args, stdout=output)
        self.assertIn('Updated route warnings for 0 flight(s)', output.getvalue())

    def test_backfill_cannot_overwrite_warnings_after_a_concurrent_route_edit(self):
        flight = self.flight(route='KAAA-XXXX-KBBB')
        def edited(route, rows, choices=None):
            Flight.objects.filter(pk=flight.pk).update(route='KAAA-KBBB', map_error='')
            return {'map_error': 'Unknown airport codes: XXXX', 'duplicate_error': ''}
        with patch('flights.management.commands.refresh_flight_route_warnings.route_warning_values', side_effect=edited):
            call_command('refresh_flight_route_warnings', stdout=StringIO())
        flight.refresh_from_db()
        self.assertEqual(flight.route, 'KAAA-KBBB')
        self.assertEqual(flight.map_error, '')

    @patch('flights.views.get_map_data')
    def test_existing_detail_update_links_change_color_without_duplicate_buttons(self, map_data):
        flight = self.flight()
        pages = [
            ('flight_detail', 'flight_update', flight.pk),
            ('aircraft_detail', 'aircraft_update', self.aircraft.pk),
            ('tailnumber_detail', 'tailnumber_update', self.tail.pk),
        ]
        for detail, update, pk in pages:
            response = self.client.get(reverse(detail, args=[pk]))
            self.assertContains(response, 'class="text-danger detail-delete">Delete</a>', count=1)
            self.assertContains(response, f'href="{reverse(update, args=[pk])}" class="detail-update text-primary">Update</a>', count=1)
            self.assertEqual(response.content.count(f'href="{reverse(update, args=[pk])}"'.encode()), 1)
        Flight.objects.filter(pk=flight.pk).update(crew_error='Please select a crew position.')
        Aircraft.objects.filter(pk=self.aircraft.pk).update(piston=False)
        TailNumber.objects.filter(pk=self.tail.pk).update(is_91=False)
        for detail, update, pk in pages:
            response = self.client.get(reverse(detail, args=[pk]))
            self.assertContains(response, 'class="text-danger detail-delete">Delete</a>', count=1)
            self.assertContains(response, f'href="{reverse(update, args=[pk])}" class="detail-update btn btn-outline-danger">Update</a>', count=1)
            self.assertEqual(response.content.count(f'href="{reverse(update, args=[pk])}"'.encode()), 1)
