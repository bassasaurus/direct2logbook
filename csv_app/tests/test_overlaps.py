from types import SimpleNamespace
from unittest.mock import patch
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from csv_app.csv_import import csv_import, confirm_csv_import
from csv_app.models import CSVImportBatch
from csv_app.overlaps import possible_overlaps, OverlapReviewRequired
from csv_app.tests.test_atomic_import import content, row
from csv_app.tests.record_fixtures import seed_records
from csv_app.tests.airport_fixtures import seed_airports
from flights.models import Aircraft, AirportCode, Flight, MapData, TailNumber
from flights.airport_resolution import resolve_route


@override_settings(SECURE_SSL_REDIRECT=False)
class OverlappingExportTests(TestCase):
    def setUp(self):
        seed_airports()
        self.user=get_user_model().objects.create_user('overlapping-exports')
        seed_records(self.user)
        self.request=SimpleNamespace(user=self.user)
        self.client.force_login(self.user)
        csv_import.run(self.request,content())
        self.existing=Flight.objects.get(user=self.user)

    def upload(self, rows=None):
        response=self.client.post(reverse('csv_inspect'),{'file':SimpleUploadedFile('new-export.csv',content(rows).encode())})
        self.assertTrue(response.context['overlap_choice'])
        return response.context['batch'],response

    def decision(self,batch,action='include',issues=None):
        issues=issues or possible_overlaps(batch,self.user)
        return {key:value for issue in issues[:10] for key,value in (
            (f'decision_{issue["line"]}',action),(f'token_{issue["line"]}',issue['token']))}

    def test_existing_entry_is_compared_without_import_or_default_choice(self):
        batch,response=self.upload()
        self.assertContains(response,'Already in Direct2Logbook')
        self.assertContains(response,f'View entry #{self.existing.pk}')
        self.assertContains(response,'Import anyway')
        self.assertNotContains(response,' checked')
        self.assertEqual(Flight.objects.count(),1)
        with self.assertRaises(OverlapReviewRequired):
            confirm_csv_import(self.request,batch.pk)
        with patch('csv_app.submission.import_csv_batch.apply_async') as publish:
            response=self.client.post(reverse('csv_upload'),{'batch_id':batch.pk})
        self.assertEqual(response.status_code,400)
        self.assertEqual(response.json()['review_url'],reverse('csv_overlaps',args=[batch.pk]))
        publish.assert_not_called()

    def test_equivalent_airport_codes_match_existing_route(self):
        Flight.objects.filter(pk=self.existing.pk).update(route='IAH-MCO')
        batch,_=self.upload([row(**{'3':'KIAH-KMCO'})])
        self.assertEqual(possible_overlaps(batch,self.user)[0]['matches'][0]['pk'],self.existing.pk)

    def prepare_local_cfi_flights(self):
        airport = MapData.objects.create(icao='KAXH', name='Houston Southwest')
        AirportCode.objects.create(airport=airport, code='AXH', kind='faa')
        self.aircraft, self.tail = seed_records(self.user)
        self.second_tail = TailNumber.objects.create(
            user=self.user, aircraft=self.aircraft, registration='N54321', is_91=True)
        self.second_aircraft = Aircraft.objects.create(
            user=self.user, aircraft_type='PA28', aircraft_category='A',
            aircraft_class='SEL', piston=True, small=True)
        self.other_aircraft_tail = TailNumber.objects.create(
            user=self.user, aircraft=self.second_aircraft, registration='N67890', is_91=True)
        Flight.objects.filter(pk=self.existing.pk).update(
            route='AXH-AXH', instructor=True, cross_country=False)

    def cfi_row(self, **changes):
        return row(**{'3': 'AXH-AXH', '7': '0', '14': '1.5', **changes})

    def test_same_day_local_cfi_flights_with_different_aircraft_tail_or_duration_are_distinct(self):
        self.prepare_local_cfi_flights()
        rows = [
            self.cfi_row(**{'2': self.second_tail.registration}),
            self.cfi_row(**{'1': self.second_aircraft.aircraft_type,
                            '2': self.other_aircraft_tail.registration}),
            self.cfi_row(**{'4': '1.2', '5': '1.2', '14': '1.2'}),
        ]
        response = self.client.post(reverse('csv_inspect'), {
            'file': SimpleUploadedFile('local-cfi.csv', content(rows).encode())})
        self.assertTrue(response.context['preview_ready'])
        batch = response.context['batch']
        self.assertEqual(possible_overlaps(batch, self.user), [])
        confirm_csv_import(self.request, batch.pk)
        flights = Flight.objects.filter(user=self.user).order_by('pk')
        self.assertEqual(flights.count(), 4)
        self.assertTrue(all(flight.instructor for flight in flights))
        self.assertEqual(
            [(flight.aircraft_type_id, flight.registration_id, str(flight.duration))
             for flight in flights],
            [(self.aircraft.pk, self.tail.pk, '1.5'),
             (self.aircraft.pk, self.second_tail.pk, '1.5'),
             (self.second_aircraft.pk, self.other_aircraft_tail.pk, '1.5'),
             (self.aircraft.pk, self.tail.pk, '1.2')])

    def test_identical_local_cfi_flight_requires_review_but_can_be_imported(self):
        self.prepare_local_cfi_flights()
        batch, _ = self.upload([self.cfi_row(**{'3': 'KAXH-KAXH'})])
        issues = possible_overlaps(batch, self.user)
        self.assertEqual(len(issues), 1)
        self.assertEqual([match['pk'] for match in issues[0]['matches']], [self.existing.pk])
        self.assertEqual(Flight.objects.count(), 1)
        response = self.client.post(reverse('csv_overlaps', args=[batch.pk]), self.decision(batch))
        self.assertTrue(response.context['preview_ready'])
        confirm_csv_import(self.request, batch.pk)
        self.assertEqual(Flight.objects.count(), 2)
        self.assertTrue(all(flight.instructor for flight in Flight.objects.all()))

    def test_round_trips_keep_direction_and_same_destination_alone_is_not_a_match(self):
        for icao, iata in [('KBNA', 'BNA'), ('KMEM', 'MEM')]:
            MapData.objects.create(icao=icao, iata=iata, name=iata)
        # The same rule applies to any resolvable airport pair, not specific codes.
        for index, (outbound, returning, same_destination) in enumerate([
            ('BNA-MEM', 'MEM-BNA', 'IAH-MEM'),
            ('KIAH-KMCO', 'KMCO-KIAH', 'KCLL-KMCO'),
            ('CLL-IAH', 'IAH-CLL', 'MCO-IAH'),
        ]):
            with self.subTest(outbound=outbound, returning=returning):
                day = f'2026-10-{21 + index}'
                csv_import.run(self.request, content([row(**{'0': day, '3': outbound})]))
                original = Flight.objects.get(user=self.user, date=day)
                response = self.client.post(reverse('csv_inspect'), {
                    'file': SimpleUploadedFile(f'round-trip-{index}.csv', content([
                        row(**{'0': day, '3': returning}),
                        row(**{'0': day, '3': same_destination}),
                    ]).encode())})
                self.assertTrue(response.context['preview_ready'])
                batch = response.context['batch']
                self.assertEqual(possible_overlaps(batch, self.user), [])
                confirm_csv_import(self.request, batch.pk)
                saved_routes = list(Flight.objects.filter(user=self.user, date=day)
                                    .values_list('route', flat=True))
                self.assertEqual(len(saved_routes), 3)
                # Import normalizes airport aliases; compare resolved airports in order.
                def airport_ids(route):
                    return tuple(item['airport'].pk for item in resolve_route(route))
                self.assertEqual({airport_ids(route) for route in saved_routes},
                                 {airport_ids(route) for route in
                                  (outbound, returning, same_destination)})
                self.assertTrue(Flight.objects.filter(pk=original.pk).exists())

    def test_excluding_overlap_imports_only_new_entry_and_preserves_existing(self):
        batch,_=self.upload([row(),row(**{'0':'2026-10-21'})])
        original=list(Flight.objects.filter(pk=self.existing.pk).values())[0]
        response=self.client.post(reverse('csv_overlaps',args=[batch.pk]),self.decision(batch,'exclude'))
        self.assertTrue(response.context['preview_ready'])
        self.assertEqual(response.context['import_summary']['entry_count'],1)
        self.assertEqual(response.context['excluded_count'],1)
        confirm_csv_import(self.request,batch.pk)
        self.assertEqual(Flight.objects.count(),2)
        self.assertEqual(list(Flight.objects.filter(pk=self.existing.pk).values())[0],original)

    def test_import_anyway_is_explicit_and_adds_another_record(self):
        batch,_=self.upload()
        response=self.client.post(reverse('csv_overlaps',args=[batch.pk]),self.decision(batch))
        self.assertTrue(response.context['preview_ready'])
        self.assertContains(response,'1 possible match explicitly included')
        confirm_csv_import(self.request,batch.pk)
        self.assertEqual(Flight.objects.count(),2)
        self.assertTrue(Flight.objects.filter(pk=self.existing.pk).exists())

    def test_excluding_everything_finishes_without_import_and_can_be_restored(self):
        batch,_=self.upload()
        response=self.client.post(reverse('csv_overlaps',args=[batch.pk]),self.decision(batch,'exclude'))
        self.assertContains(response,'Nothing to import')
        self.assertEqual(Flight.objects.count(),1)
        batch.refresh_from_db()
        self.assertEqual(batch.row_count,0)
        self.assertFalse(batch.rows_complete)
        self.assertTrue(batch.row_data['rows'][0]['excluded'])
        self.assertEqual(self.client.get(reverse('csv_rows',args=[batch.pk])).status_code,200)

    def test_other_users_records_are_not_exposed_or_matched(self):
        other=get_user_model().objects.create_user('other-overlap-owner')
        seed_records(other)
        self.client.force_login(other)
        response=self.client.post(reverse('csv_inspect'),{'file':SimpleUploadedFile('other.csv',content().encode())})
        self.assertTrue(response.context['preview_ready'])
        self.assertNotContains(response,f'View entry #{self.existing.pk}')
        self.assertEqual(self.client.get(reverse('csv_overlaps',args=[response.context['batch'].pk])).status_code,302)

    def test_changed_existing_record_invalidates_stale_decision(self):
        batch,_=self.upload()
        old=self.decision(batch)
        Flight.objects.filter(pk=self.existing.pk).update(remarks='Changed after preview')
        response=self.client.post(reverse('csv_overlaps',args=[batch.pk]),old)
        self.assertContains(response,'Matching entries changed')
        self.assertContains(response,'Changed after preview')
        batch.refresh_from_db()
        self.assertFalse(batch.overlap_review)
        self.assertEqual(Flight.objects.count(),1)

    def test_worker_rechecks_for_new_matches_after_queueing(self):
        response=self.client.post(reverse('csv_inspect'),{'file':SimpleUploadedFile('new.csv',content([row(**{'0':'2026-10-21'})]).encode())})
        batch=response.context['batch']
        self.assertTrue(response.context['preview_ready'])
        csv_import.run(self.request,content([row(**{'0':'2026-10-21'})]))
        with self.assertRaises(OverlapReviewRequired):
            confirm_csv_import(self.request,batch.pk)
        self.assertEqual(Flight.objects.count(),2)

    def test_review_requires_decision_and_honors_owner_expiry_and_csrf(self):
        batch,_=self.upload()
        response=self.client.post(reverse('csv_overlaps',args=[batch.pk]),{})
        self.assertContains(response,'Choose Exclude incoming row or Import anyway.')
        from django.test import Client
        guarded=Client(enforce_csrf_checks=True)
        guarded.force_login(self.user)
        self.assertEqual(guarded.post(reverse('csv_overlaps',args=[batch.pk]),self.decision(batch)).status_code,403)
        other=get_user_model().objects.create_user('foreign-overlap')
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('csv_overlaps',args=[batch.pk])).status_code,404)
        self.client.force_login(self.user)
        CSVImportBatch.objects.filter(pk=batch.pk).update(created_at=timezone.now()-timedelta(minutes=11))
        self.assertEqual(self.client.get(reverse('csv_overlaps',args=[batch.pk])).status_code,410)


    def test_decisions_are_paged_without_losing_exclusions(self):
        batch,_=self.upload([row() for _ in range(11)])
        response=self.client.post(reverse('csv_overlaps',args=[batch.pk]),self.decision(batch,'exclude'))
        self.assertTrue(response.context['overlap_choice'])
        self.assertEqual(response.context['overlap_remaining'],1)
        batch.refresh_from_db()
        response=self.client.post(reverse('csv_overlaps',args=[batch.pk]),self.decision(batch,issues=[issue for issue in possible_overlaps(batch,self.user) if not issue['approved']]))
        self.assertTrue(response.context['preview_ready'])
        self.assertEqual(response.context['excluded_count'],10)
        self.assertEqual(response.context['import_summary']['entry_count'],1)

    def test_editing_incoming_rows_resets_previous_choices(self):
        batch,_=self.upload()
        self.client.post(reverse('csv_overlaps',args=[batch.pk]),self.decision(batch))
        self.client.get(reverse('csv_rows',args=[batch.pk]))
        batch.refresh_from_db()
        self.assertEqual(batch.overlap_review,{})

    def test_background_worker_stops_if_a_new_overlap_appears(self):
        from csv_app.tasks import import_csv_batch
        response=self.client.post(reverse('csv_inspect'),{'file':SimpleUploadedFile('later.csv',content([row(**{'0':'2026-10-21'})]).encode())})
        batch=response.context['batch']
        csv_import.run(self.request,content([row(**{'0':'2026-10-21'})]))
        CSVImportBatch.objects.filter(pk=batch.pk).update(status='queued',task_id='overlap-race-test')
        with self.assertRaises(OverlapReviewRequired):
            import_csv_batch.apply(args=[self.user.pk,str(batch.pk)],task_id='overlap-race-test',throw=True)
        batch.refresh_from_db()
        self.assertEqual(batch.status,'failed')
        self.assertIn('Upload the file again',batch.error_message)
        self.assertEqual(Flight.objects.count(),2)
