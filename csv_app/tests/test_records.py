"""Account-scoped resolution, explicit creation, and import identity guarantees."""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from csv_app.models import CSVImportBatch
from csv_app.records import RecordResolution, validate_record_snapshot
from csv_app.forms import RecordResolutionForm
from csv_app.csv_import import confirm_csv_import
from csv_app.submission import queue_csv_import
from csv_app.validation import CSVValidationError, parse_csv
from csv_app.tests.test_atomic_import import content, row, device_row
from csv_app.tests.airport_fixtures import seed_airports
from csv_app.tests.record_fixtures import seed_records
from flights.models import Aircraft, TailNumber, Flight, Total


@override_settings(SECURE_SSL_REDIRECT=False)
class CSVRecordResolutionTests(TestCase):
    def setUp(self):
        seed_airports()
        self.user = get_user_model().objects.create_user('records')
        self.other = get_user_model().objects.create_user('other-records')
        self.aircraft, self.tail = seed_records(self.user)
        self.client.force_login(self.user)

    def upload(self, rows=None):
        return self.client.post(reverse('csv_inspect'), {'file': SimpleUploadedFile('flights.csv', content(rows).encode())})

    def batch(self, rows=None):
        return CSVImportBatch.objects.create(user=self.user, content=content(rows), row_count=len(rows or [row()]),
                                             records_complete=False, date_order='unambiguous')

    def records_url(self, batch):
        return reverse('csv_records', args=[batch.pk])

    def create_url(self, batch, kind, index=0):
        return reverse('csv_create_record', args=[batch.pk, kind, index])

    def test_existing_matches_are_case_insensitive_and_import_exact_ids(self):
        response = self.upload([row(**{'1': 'c172', '2': 'n12345'})])
        self.assertTrue(response.context['preview_ready'])
        batch = response.context['batch']
        self.assertTrue(batch.records_complete)
        self.assertEqual(parse_csv(batch.content)[0][0]['aircraft'], 'C172')
        receipt, duplicate = confirm_csv_import(SimpleNamespace(user=self.user), batch.pk)
        self.assertFalse(duplicate)
        self.assertTrue(receipt.completed)
        flight = Flight.objects.get()
        self.assertEqual((flight.aircraft_type_id, flight.registration_id), (self.aircraft.pk, self.tail.pk))
        self.assertEqual(Aircraft.objects.filter(user=self.user).count(), 1)
        self.assertEqual(TailNumber.objects.filter(user=self.user).count(), 1)
        self.assertEqual(Total.objects.get(user=self.user, total='All').total_time, flight.duration)

    def test_unknown_aircraft_is_not_auto_created_or_matched_across_accounts(self):
        Aircraft.objects.create(user=self.other, aircraft_type='PA28')
        response = self.upload([row(**{'1': 'PA28'})])
        self.assertTrue(response.context['record_choice'])
        self.assertTrue(response.context['aircraft_stage'])
        self.assertFalse(Aircraft.objects.filter(user=self.user, aircraft_type='PA28').exists())
        self.assertFalse(Flight.objects.exists())
        self.assertContains(response, 'Complete Aircraft Details')

    def test_new_tail_uses_file_pair_and_requires_operating_rules(self):
        batch = self.batch([row(**{'2': 'N77777'})])
        url = self.records_url(batch)
        response = self.client.get(url)
        self.assertContains(response, 'C172 / N77777')
        self.assertNotContains(response, 'Choose a tailnumber')
        self.assertNotContains(response, 'data-autocomplete-light-url="/flights/aircraft-autocomplete/')
        missing = self.client.post(url, {'aircraft_0': self.aircraft.pk})
        self.assertContains(missing, 'Choose Part 91, 135, or 121.')
        self.assertFalse(TailNumber.objects.filter(user=self.user, registration='N77777').exists())
        invalid = self.client.post(url, {'aircraft_0': self.aircraft.pk, 'operating_rules_0': 'is_999'})
        self.assertTrue(invalid.context['record_form'].errors)
        before = (self.tail.is_91, self.tail.is_135, self.tail.is_121)
        response = self.client.post(url, {'aircraft_0': self.aircraft.pk, 'operating_rules_0': 'is_121'})
        self.assertTrue(response.context['preview_ready'])
        tail = TailNumber.objects.get(user=self.user, registration='N77777')
        self.assertEqual(tail.aircraft_id, self.aircraft.pk)
        self.assertTrue(tail.is_121)
        self.assertFalse(tail.is_91)
        self.assertFalse(tail.is_135)
        self.tail.refresh_from_db()
        self.assertEqual((self.tail.is_91, self.tail.is_135, self.tail.is_121), before)
        self.assertFalse(Flight.objects.exists())
        self.client.post(url, {'aircraft_0': self.aircraft.pk, 'operating_rules_0': 'is_91'})
        self.assertEqual(TailNumber.objects.filter(user=self.user, registration='N77777').count(), 1)
        tail.refresh_from_db()
        self.assertTrue(tail.is_121)

    def test_new_historical_aircraft_then_new_tail_only_asks_for_missing_details(self):
        from django.db.models.signals import post_save
        saved = []
        def track(sender, instance, created, **kwargs):
            if created:
                saved.append(sender.__name__)
        for model in (Aircraft, TailNumber, Flight):
            post_save.connect(track, sender=model, weak=False)
            self.addCleanup(post_save.disconnect, track, sender=model)
        batch = self.batch([row(**{'1': 'PA28', '2': 'N77778'})])
        self.assertContains(self.client.get(self.records_url(batch)), 'Complete Aircraft Details')
        self.client.post(self.create_url(batch, 'aircraft'), {'aircraft_type': 'PA28',
            'aircraft_category': 'A', 'aircraft_class': 'SEL', 'engine': 'piston', 'weight_category': 'small'})
        aircraft = Aircraft.objects.get(user=self.user, aircraft_type='PA28')
        details = self.client.get(self.records_url(batch))
        self.assertContains(details, 'PA28 / N77778')
        self.assertContains(details, 'Part 135')
        self.assertNotContains(details, 'Choose a tailnumber')
        response = self.client.post(self.records_url(batch), {'aircraft_0': aircraft.pk, 'operating_rules_0': 'is_135'})
        self.assertTrue(response.context['preview_ready'])
        self.assertEqual(TailNumber.objects.get(user=self.user, registration='N77778').aircraft_id, aircraft.pk)
        self.assertFalse(Flight.objects.exists())

        self.assertEqual(saved, ['Aircraft', 'TailNumber'])
        confirm_csv_import(SimpleNamespace(user=self.user), batch.pk)
        self.assertEqual(saved, ['Aircraft', 'TailNumber', 'Flight'])

    def test_missing_tail_is_not_auto_created(self):
        response = self.upload([row(**{'2': 'N77777'})])
        self.assertFalse(response.context['aircraft_stage'])
        self.assertContains(response, 'Operating rules')
        self.assertNotContains(response, 'name="tailnumber_0"')
        self.assertFalse(TailNumber.objects.filter(registration='N77777').exists())

    def test_tailnumber_choices_follow_selected_aircraft_and_reject_other_types(self):
        import json
        other_aircraft = Aircraft.objects.create(user=self.user, aircraft_type='A320')
        other_tail = TailNumber.objects.create(user=self.user, aircraft=other_aircraft, registration='N320XX')
        batch = self.batch([row(**{'2': 'N99999'})])
        resolution = RecordResolution(self.user, batch.content)
        form = RecordResolutionForm(user=self.user, resolution=resolution)
        self.assertEqual(list(form.fields['tailnumber_0'].queryset), [self.tail])
        self.assertIn('aircraft_type', str(form['tailnumber_0']))
        posted = RecordResolutionForm({'aircraft_0': other_aircraft.pk, 'tailnumber_0': other_tail.pk}, user=self.user, resolution=resolution)
        self.assertTrue(posted.is_valid(), posted.errors)
        self.assertEqual(list(posted.fields['tailnumber_0'].queryset), [other_tail])
        bad = RecordResolutionForm({'aircraft_0': self.aircraft.pk, 'tailnumber_0': other_tail.pk}, user=self.user, resolution=resolution)
        self.assertFalse(bad.is_valid())
        self.assertIn('selected aircraft', str(bad.errors))
        url = reverse('tailnumber-autocomplete')
        result = self.client.get(url, {'forward': json.dumps({'aircraft_type': self.aircraft.pk, 'require_aircraft': True})})
        self.assertEqual({str(item['id']) for item in result.json()['results']}, {str(self.tail.pk)})
        empty = self.client.get(url, {'forward': json.dumps({'require_aircraft': True})})
        self.assertEqual(empty.json()['results'], [])

    def test_conflict_requires_explicit_matching_and_never_reassigns_existing_tail(self):
        other_aircraft = Aircraft.objects.create(user=self.user, aircraft_type='PA28')
        other_tail = TailNumber.objects.create(user=self.user, aircraft=other_aircraft, registration='N77777')
        batch = self.batch([row(**{'2': 'N77777'})])
        response = self.client.get(self.records_url(batch))
        self.assertContains(response, 'belongs to PA28')
        response = self.client.post(self.records_url(batch), {'aircraft_0': self.aircraft.pk, 'tailnumber_0': other_tail.pk})
        self.assertTrue(response.context['record_form'].errors)
        response = self.client.post(self.records_url(batch), {'aircraft_0': other_aircraft.pk, 'tailnumber_0': other_tail.pk})
        self.assertTrue(response.context['preview_ready'])
        batch.refresh_from_db()
        self.assertEqual(parse_csv(batch.content)[0][0]['aircraft'], 'PA28')
        other_tail.refresh_from_db()
        self.assertEqual(other_tail.aircraft_id, other_aircraft.pk)
        self.assertFalse(Flight.objects.exists())

    def test_user_can_replace_bad_source_registration_with_existing_owned_tail(self):
        batch = self.batch([row(**{'2': 'TYPO'})])
        response = self.client.post(self.records_url(batch), {'aircraft_0': self.aircraft.pk, 'tailnumber_0': self.tail.pk})
        self.assertTrue(response.context['preview_ready'])
        batch.refresh_from_db()
        self.assertEqual(parse_csv(batch.content)[0][0]['registration'], 'N12345')

    def test_foreign_owned_selections_and_missing_choices_are_rejected(self):
        foreign_aircraft, foreign_tail = seed_records(self.other)
        batch = self.batch([row(**{'2': 'N77777'})])
        for data in [{}, {'aircraft_0': foreign_aircraft.pk, 'tailnumber_0': foreign_tail.pk}]:
            response = self.client.post(self.records_url(batch), data)
            self.assertTrue(response.context['record_form'].errors)
        batch.refresh_from_db()
        self.assertFalse(batch.records_complete)

    def test_create_aircraft_uses_full_validation_then_returns_to_resolution(self):
        batch = self.batch([row(**{'1': 'PA28', '2': 'N77777'})])
        url = self.create_url(batch, 'aircraft')
        response = self.client.get(url)
        self.assertEqual(response.context['form'].initial['aircraft_type'], 'PA28')
        response = self.client.post(url, {'aircraft_type': 'PA28'})
        self.assertTrue(response.context['form'].errors)
        self.assertFalse(Aircraft.objects.filter(user=self.user, aircraft_type='PA28').exists())
        response = self.client.post(url, {'aircraft_type': 'PA28', 'aircraft_category': 'A',
                                          'aircraft_class': 'SEL', 'engine': 'piston', 'weight_category': 'small'})
        self.assertRedirects(response, self.records_url(batch))
        self.assertTrue(Aircraft.objects.filter(user=self.user, aircraft_type='PA28').exists())
        self.assertFalse(Flight.objects.exists())

    def test_create_tail_requires_rules_and_can_correct_registration(self):
        batch = self.batch([row(**{'2': 'N77777'})])
        url = self.create_url(batch, 'tailnumber')
        response = self.client.post(url, {'aircraft': self.aircraft.pk, 'registration': 'N77778'})
        self.assertTrue(response.context['form'].errors)
        self.assertFalse(TailNumber.objects.filter(registration='N77778').exists())
        response = self.client.post(url, {'aircraft': self.aircraft.pk, 'registration': 'N77778', 'operating_rules': 'is_91'})
        self.assertRedirects(response, self.records_url(batch))
        batch.refresh_from_db()
        self.assertTrue(batch.records_complete)
        self.assertEqual(parse_csv(batch.content)[0][0]['registration'], 'N77778')
        self.assertFalse(Flight.objects.exists())
        # A repeated stale creation request cannot add a second record.
        self.assertRedirects(self.client.post(url, {'registration': 'N99999'}), self.records_url(batch))
        self.assertFalse(TailNumber.objects.filter(registration='N99999').exists())

    def test_multiple_pairs_resolve_independently(self):
        batch = self.batch([row(**{'2': 'BAD1'}), row(**{'2': 'BAD2'})])
        response = self.client.post(self.records_url(batch), {'aircraft_0': self.aircraft.pk, 'tailnumber_0': self.tail.pk,
                                                            'aircraft_1': self.aircraft.pk, 'tailnumber_1': self.tail.pk})
        self.assertTrue(response.context['preview_ready'])
        batch.refresh_from_db()
        self.assertEqual([r['registration'] for r in parse_csv(batch.content)[0]], ['N12345', 'N12345'])

    def test_large_unresolved_lists_are_paged_and_progress_is_preserved(self):
        batch = self.batch([row(**{'1': f'X{i}'}) for i in range(26)])
        response = self.client.get(self.records_url(batch))
        self.assertEqual(len(response.context['record_rows']), 25)
        response = self.client.post(self.records_url(batch), {f'aircraft_{i}': self.aircraft.pk for i in range(25)})
        self.assertEqual(len(response.context['record_rows']), 1)
        self.assertEqual(response.context['record_rows'][0]['index'], 25)
        batch.refresh_from_db()
        self.assertEqual(len(batch.record_resolution['aircraft']), 25)

    def test_unresolved_import_is_blocked_in_http_and_worker(self):
        batch = self.batch()
        with patch('csv_app.submission.import_csv_batch.apply_async') as task:
            response = self.client.post(reverse('csv_upload'), {'batch_id': str(batch.pk)})
            self.assertEqual(response.status_code, 400)
            task.assert_not_called()
        with self.assertRaisesRegex(CSVValidationError, 'Resolve the aircraft'):
            confirm_csv_import(SimpleNamespace(user=self.user), batch.pk)
        self.assertFalse(Flight.objects.exists())

    def test_changed_matches_are_rejected_at_submission_and_worker_without_recreation(self):
        batch = self.upload().context['batch']
        self.tail.registration = 'N54321'
        self.tail.save()
        with self.assertRaisesRegex(CSVValidationError, 'changed after review'):
            queue_csv_import(self.user, batch.pk)
        with self.assertRaisesRegex(CSVValidationError, 'changed after review'):
            confirm_csv_import(SimpleNamespace(user=self.user), batch.pk)
        self.assertFalse(TailNumber.objects.filter(registration='N12345').exists())
        self.assertFalse(Flight.objects.exists())
        # Returning via Dates must not silently replace the saved identity snapshot.
        response = self.client.get(reverse('csv_date_order', args=[batch.pk]))
        self.assertContains(response, 'changed after review')

    def test_deleted_match_is_rejected(self):
        batch = self.upload().context['batch']
        self.tail.delete()
        with self.assertRaisesRegex(CSVValidationError, 'changed after review'):
            validate_record_snapshot(batch, self.user)

    def test_expiry_owner_csrf_and_prerequisites(self):
        batch = self.batch()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.records_url(batch)).status_code, 404)
        self.assertEqual(self.client.get(self.create_url(batch, 'tailnumber')).status_code, 404)
        self.client.force_login(self.user)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(csrf.post(self.records_url(batch), {}).status_code, 403)
        self.assertEqual(csrf.post(self.create_url(batch, 'tailnumber'), {}).status_code, 403)
        batch.mapping_complete = False
        batch.save()
        self.assertRedirects(self.client.get(self.records_url(batch)), reverse('csv_mapping', args=[batch.pk]), fetch_redirect_response=False)
        batch.mapping_complete = True
        batch.date_order = 'pending'
        batch.save()
        self.assertRedirects(self.client.get(self.records_url(batch)), reverse('csv_date_order', args=[batch.pk]), fetch_redirect_response=False)
        CSVImportBatch.objects.filter(pk=batch.pk).update(created_at=timezone.now() - timedelta(minutes=11))
        self.assertEqual(self.client.get(self.records_url(batch)).status_code, 410)
        self.assertEqual(self.client.get(self.create_url(batch, 'tailnumber')).status_code, 410)

    def test_simulator_can_explicitly_drop_unmatched_tailnumber(self):
        batch = self.batch([device_row(**{'2': 'DEVICE'})])
        response = self.client.post(self.records_url(batch), {'aircraft_0': self.aircraft.pk, 'skip_tail_0': 'on'})
        self.assertTrue(response.context['preview_ready'])
        batch.refresh_from_db()
        self.assertEqual(parse_csv(batch.content)[0][0]['registration'], '')
        self.assertFalse(TailNumber.objects.filter(registration='DEVICE').exists())

    def test_tail_creation_cannot_use_another_users_aircraft(self):
        foreign_aircraft, _ = seed_records(self.other)
        batch = self.batch([row(**{'2': 'N77777'})])
        response = self.client.post(self.create_url(batch, 'tailnumber'), {
            'aircraft': foreign_aircraft.pk, 'registration': 'N77777', 'operating_rules': 'is_91'})
        self.assertIn('aircraft', response.context['form'].errors)
        self.assertFalse(TailNumber.objects.filter(registration='N77777').exists())

    def test_duplicate_create_is_friendly_and_preserves_existing_record(self):
        batch = self.batch([row(**{'2': 'N77777'})])
        response = self.client.post(self.create_url(batch, 'tailnumber'), {
            'aircraft': self.aircraft.pk, 'registration': 'n12345', 'operating_rules': 'is_91'})
        self.assertTrue(response.context['form'].errors)
        self.assertEqual(TailNumber.objects.filter(user=self.user).count(), 1)
        self.assertNotContains(response, 'IntegrityError')

    def test_known_matches_skip_records_but_still_show_final_review(self):
        response = self.upload()
        self.assertTrue(response.context['preview_ready'])
        self.assertContains(response, 'Review your entries')
        self.assertContains(response, 'data-csv-step="6"')
        self.assertNotIn('record_choice', response.context)
        self.assertFalse(Flight.objects.exists())

    def test_complete_created_records_import_without_duplicate_aircraft_or_tail(self):
        batch = self.batch([row(**{'1': 'PA28', '2': 'N77777'})])
        self.client.post(self.create_url(batch, 'aircraft'), {'aircraft_type': 'PA28', 'aircraft_category': 'A',
            'aircraft_class': 'SEL', 'engine': 'piston', 'weight_category': 'small'})
        aircraft = Aircraft.objects.get(user=self.user, aircraft_type='PA28')
        self.client.post(self.create_url(batch, 'tailnumber'), {
            'aircraft': aircraft.pk, 'registration': 'N77777', 'operating_rules': 'is_135'})
        self.client.get(self.records_url(batch))
        batch.refresh_from_db()
        self.assertTrue(batch.records_complete)
        confirm_csv_import(SimpleNamespace(user=self.user), batch.pk)
        self.assertEqual(Flight.objects.get().aircraft_type_id, aircraft.pk)
        self.assertEqual(Aircraft.objects.filter(user=self.user).count(), 2)
        self.assertEqual(TailNumber.objects.filter(user=self.user).count(), 2)
        self.assertTrue(TailNumber.objects.get(registration='N77777').is_135)
