"""Committed interruption and correction recovery, with real signals and totals."""
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection, close_old_connections, DatabaseError
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from kombu.exceptions import OperationalError

from csv_app.models import CSVImportBatch
from csv_app.tasks import import_csv_batch
from csv_app.tests.test_atomic_import import content, row
from csv_app.tests.airport_fixtures import seed_airports
from csv_app.tests.record_fixtures import seed_records
from flights.models import Aircraft, TailNumber, Flight, Approach, Total


@override_settings(SECURE_SSL_REDIRECT=False)
class CSVImportRecoveryTests(TransactionTestCase):
    def setUp(self):
        seed_airports()
        self.user = get_user_model().objects.create_user('csv-recovery', email='recovery@example.com')
        self.aircraft, self.tail = seed_records(self.user)
        self.client.force_login(self.user)
        self.original = Flight.objects.create(user=self.user, aircraft_type=self.aircraft,
            registration=self.tail, date='2026-10-19', route='KIAH-KCLL', duration=Decimal('0.8'),
            pilot_in_command=True, simulator=False)
        self.payload = content([
            row(**{'0': '2026-10-20', '2': self.tail.registration, '3': 'KIAH-KCLL'}),
            row(**{'0': '2026-10-21', '2': self.tail.registration, '3': 'KCLL-KIAH', '4': '1.2', '5': '1.2', '7': '1.2'}),
        ])
        notify = patch('csv_app.csv_import.email_confirmation')
        self.notify = notify.start()
        self.addCleanup(notify.stop)
        self.baseline_catalog = (set(Aircraft.objects.values_list('pk', flat=True)),
                                 set(TailNumber.objects.values_list('pk', flat=True)))

    def upload_response(self):
        return self.client.post(reverse('csv_inspect'), {
            'file': SimpleUploadedFile('recovery.csv', self.payload.encode())})

    def upload(self):
        response = self.upload_response()
        self.assertTrue(response.context['preview_ready'])
        return response.context['batch']

    def queue(self, batch, *, lose_ack=False):
        with patch('csv_app.submission.import_csv_batch.apply_async') as publish:
            if lose_ack:
                publish.side_effect = OperationalError('publication acknowledgement lost')
                with self.assertLogs('django.csv_app', level='ERROR'):
                    response = self.client.post(reverse('csv_upload'), {'batch_id': batch.pk})
            else:
                response = self.client.post(reverse('csv_upload'), {'batch_id': batch.pk})
        self.assertEqual(response.status_code, 503 if lose_ack else 202)
        self.assertEqual(publish.call_count, 1)
        batch.refresh_from_db()
        return batch.task_id

    def run_worker(self, batch, task_id=None):
        import_csv_batch.push_request(id=task_id or batch.task_id)
        try:
            import_csv_batch.run(self.user.pk, str(batch.pk))
        finally:
            import_csv_batch.pop_request()
        batch.refresh_from_db()

    def snapshot(self):
        values = list(Flight.objects.filter(user=self.user).order_by('pk').values(
            'pk', 'date', 'aircraft_type_id', 'registration_id', 'route', 'duration',
            'pilot_in_command', 'second_in_command', 'cross_country', 'night', 'instrument'))
        totals = Total.objects.filter(user=self.user).order_by('pk').values(
            'pk', 'total', 'total_time', 'pilot_in_command', 'cross_country', 'landings_day')
        return values, list(totals), list(Approach.objects.order_by('pk').values('pk', 'flight_object_id', 'number'))

    def assert_completed_once(self, batch):
        self.assertTrue(batch.completed)
        self.assertEqual(batch.status, CSVImportBatch.Status.COMPLETED)
        self.assertEqual(batch.row_count, 2)
        self.assertEqual(Flight.objects.filter(user=self.user).count(), 3)
        self.assertEqual(Approach.objects.filter(flight_object__user=self.user).count(), 2)
        self.assertEqual(Total.objects.get(user=self.user, total='All').total_time, Decimal('3.5'))
        self.notify.assert_called_once()

    def assert_replays_do_not_change_data(self, batch, old_batch=None):
        before = self.snapshot()
        self.run_worker(batch)
        self.run_worker(batch, task_id='duplicate-delivery-with-a-new-id')
        if old_batch:
            self.run_worker(old_batch)
        response = self.client.post(reverse('csv_upload'), {'batch_id': batch.pk})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['already_completed'])
        uploaded_again = self.upload_response()
        self.assertIn('already been imported', uploaded_again.context['duplicate_upload'])
        self.assertEqual(self.snapshot(), before)
        self.notify.assert_called_once()

    def test_interrupted_second_flight_rolls_back_then_same_file_retry_imports_once(self):
        batch = self.upload()
        self.queue(batch)
        baseline = self.snapshot()
        save = Flight.save
        attempted = []
        def interrupted_save(instance, *args, **kwargs):
            creating = instance._state.adding
            result = save(instance, *args, **kwargs)
            if creating:
                attempted.append(instance.pk)
                if len(attempted) == 2:
                    raise RuntimeError('worker interrupted after saving second flight')
            return result
        with patch.object(Flight, 'save', autospec=True, side_effect=interrupted_save):
            with self.assertLogs('django.csv_app', level='ERROR'):
                with self.assertRaisesRegex(RuntimeError, 'worker interrupted'):
                    self.run_worker(batch)
        self.assertEqual(len(attempted), 2)
        self.assertEqual(self.snapshot(), baseline)
        self.notify.assert_not_called()
        batch.refresh_from_db()
        self.assertEqual(batch.status, CSVImportBatch.Status.FAILED)
        retry = self.upload()
        self.assertNotEqual(retry.pk, batch.pk)
        self.assertEqual(retry.source_digest, batch.source_digest)
        self.queue(retry)
        self.run_worker(retry)
        self.assert_completed_once(retry)
        self.assertEqual(self.baseline_catalog, (set(Aircraft.objects.values_list('pk', flat=True)),
            set(TailNumber.objects.values_list('pk', flat=True))))
        self.assert_replays_do_not_change_data(retry, old_batch=batch)

    def test_lost_acknowledgement_after_real_commit_preserves_receipt_and_ids(self):
        from csv_app.csv_import import confirm_csv_import
        batch = self.upload()
        self.queue(batch)
        def commit_then_lose_ack(*args, **kwargs):
            result = confirm_csv_import(*args, **kwargs)
            self.assertTrue(CSVImportBatch.objects.get(pk=batch.pk).completed)
            raise OperationalError('worker lost acknowledgement after commit')
        with patch('csv_app.tasks.confirm_csv_import', side_effect=commit_then_lose_ack):
            with self.assertLogs('django.csv_app', level='ERROR'):
                with self.assertRaises(OperationalError):
                    self.run_worker(batch)
        batch.refresh_from_db()
        self.assert_completed_once(batch)
        self.assert_replays_do_not_change_data(batch)

    def test_dropped_worker_database_connection_rolls_back_then_retry_imports_once(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Backend-termination recovery requires PostgreSQL.')
        self.assertTrue(connection.settings_dict['NAME'].startswith('test_'))
        batch = self.upload()
        self.queue(batch)
        before = self.snapshot()
        paused, release = Event(), Event()
        worker_pid, attempted = [], []
        save = Flight.save
        def pause_after_two_saves(instance, *args, **kwargs):
            creating = instance._state.adding
            result = save(instance, *args, **kwargs)
            if creating:
                attempted.append(instance.pk)
                if len(attempted) == 2:
                    paused.set()
                    if not release.wait(timeout=10):
                        raise RuntimeError('Test did not release interrupted worker')
            return result
        def worker():
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_backend_pid()')
                    worker_pid.append(cursor.fetchone()[0])
                self.run_worker(batch)
            finally:
                connection.close()
        with patch.object(Flight, 'save', autospec=True, side_effect=pause_after_two_saves):
            with self.assertLogs('django.csv_app', level='ERROR'):
                with ThreadPoolExecutor(max_workers=1) as executor:
                    pending = executor.submit(worker)
                    try:
                        self.assertTrue(paused.wait(timeout=10))
                        # Kill only this test worker's connection to this disposable DB.
                        with connection.cursor() as cursor:
                            cursor.execute('SELECT datname FROM pg_stat_activity WHERE pid = %s', [worker_pid[0]])
                            self.assertEqual(cursor.fetchone()[0], connection.settings_dict['NAME'])
                            cursor.execute('SELECT pg_terminate_backend(%s)', [worker_pid[0]])
                            self.assertTrue(cursor.fetchone()[0])
                        self.assertEqual(self.snapshot(), before)
                    finally:
                        release.set()
                    with self.assertRaises(DatabaseError):
                        pending.result(timeout=10)
        batch.refresh_from_db()
        if batch.status == CSVImportBatch.Status.PROCESSING:
            # A dead connection may prevent writing a failure receipt. Exercise
            # the normal stalled-worker recovery, without waiting 20 minutes.
            CSVImportBatch.objects.filter(pk=batch.pk).update(updated_at=timezone.now() - timedelta(minutes=21))
            call_command('cleanup_csv_previews', stdout=StringIO())
            batch.refresh_from_db()
        self.assertEqual(batch.status, CSVImportBatch.Status.FAILED)
        self.assertEqual(self.snapshot(), before)
        self.notify.assert_not_called()
        retry = self.upload()
        self.queue(retry)
        self.run_worker(retry)
        self.assert_completed_once(retry)
        self.assert_replays_do_not_change_data(retry, old_batch=batch)

    def test_unconfirmed_publication_does_not_publish_or_import_twice(self):
        batch = self.upload()
        self.queue(batch, lose_ack=True)
        self.assertEqual(batch.status, CSVImportBatch.Status.UNCONFIRMED)
        before = self.snapshot()
        with patch('csv_app.submission.import_csv_batch.apply_async') as publish:
            response = self.client.post(reverse('csv_upload'), {'batch_id': batch.pk})
        self.assertEqual(response.status_code, 503)
        publish.assert_not_called()
        self.assertEqual(self.snapshot(), before)
        self.run_worker(batch)
        self.assert_completed_once(batch)
        self.assert_replays_do_not_change_data(batch)

    def test_changed_tail_assignment_returns_to_same_batch_and_imports_once(self):
        tail = TailNumber.objects.create(user=self.user, aircraft=self.aircraft, registration='N54321', is_91=True)
        other = Aircraft.objects.create(user=self.user, aircraft_type='PA28', aircraft_category='A',
            aircraft_class='SEL', piston=True, small=True)
        self.payload = self.payload.replace(self.tail.registration, tail.registration)
        batch = self.upload()
        self.queue(batch)
        tail.aircraft = other
        tail.save()
        before = self.snapshot()
        old_task_id = batch.task_id
        self.run_worker(batch)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(batch.status, CSVImportBatch.Status.PREVIEW)
        self.assertTrue(batch.content)
        self.assertTrue(batch.row_data)
        self.assertFalse(batch.records_complete)
        status = self.client.get(reverse('csv_import_status', args=[batch.pk])).json()
        self.assertEqual(status['status'], 'needs_review')
        self.assertEqual(status['review_url'], reverse('csv_records', args=[batch.pk]))
        response = self.client.get(status['review_url'])
        self.assertEqual(len(response.context['record_rows']), 1)
        self.assertContains(response, 'belongs to PA28')
        self.assertContains(response, 'No flights were imported')
        self.assertEqual(response.context['record_rows'][0]['source'], tail.registration)
        response = self.client.post(status['review_url'], {'aircraft_0': other.pk, 'tailnumber_0': tail.pk})
        self.assertTrue(response.context['preview_ready'])
        batch.refresh_from_db()
        self.assertEqual(batch.error_message, '')
        self.assertFalse(batch.record_resolution.get('needs_review'))
        retry = batch
        self.queue(retry)
        self.assertNotEqual(retry.task_id, old_task_id)
        self.run_worker(retry, task_id=old_task_id)
        self.assertEqual(self.snapshot(), before)
        self.run_worker(retry)
        self.assert_completed_once(retry)
        imported = Flight.objects.exclude(pk=self.original.pk)
        self.assertEqual(imported.filter(aircraft_type=other, registration=tail).count(), 2)
        self.assertEqual(TailNumber.objects.get(pk=tail.pk).aircraft_id, other.pk)
        self.assert_replays_do_not_change_data(retry, old_batch=batch)


    def test_changed_pair_before_submission_returns_owned_review_url_and_preserves_file(self):
        tail = TailNumber.objects.create(user=self.user, aircraft=self.aircraft, registration='N54321', is_91=True)
        other = Aircraft.objects.create(user=self.user, aircraft_type='PA28', aircraft_category='A',
            aircraft_class='SEL', piston=True, small=True)
        self.payload = self.payload.replace(self.tail.registration, tail.registration)
        batch = self.upload()
        source = batch.content
        digest = batch.source_digest
        tail.aircraft = other
        tail.save()
        with patch('csv_app.submission.import_csv_batch.apply_async') as publish:
            response = self.client.post(reverse('csv_upload'), {'batch_id': batch.pk})
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()['status'], 'needs_review')
            publish.assert_not_called()
        batch.refresh_from_db()
        self.assertEqual(batch.content, source)
        self.assertEqual(batch.source_digest, digest)
        reopened_at = batch.created_at
        response = self.client.post(reverse('csv_upload'), {'batch_id': batch.pk})
        self.assertEqual(response.json()['review_url'], reverse('csv_records', args=[batch.pk]))
        batch.refresh_from_db()
        self.assertEqual(batch.created_at, reopened_at)
        self.assertEqual(self.client.get(reverse('csv_inspect')).context['latest_import'].pk, batch.pk)
        self.client.logout()
        self.assertEqual(self.client.get(response.json()['review_url']).status_code, 302)
        self.assertEqual(Flight.objects.count(), 1)

        other_user = get_user_model().objects.create_user('unrelated-recovery')
        self.client.force_login(other_user)
        self.assertEqual(self.client.get(reverse('csv_records', args=[batch.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('csv_import_status', args=[batch.pk])).status_code, 404)
        self.client.force_login(self.user)
        CSVImportBatch.objects.filter(pk=batch.pk).update(created_at=timezone.now() - timedelta(minutes=11))
        expired = self.client.get(reverse('csv_import_status', args=[batch.pk])).json()
        self.assertEqual(expired['status'], 'expired')
        self.assertNotIn('review_url', expired)
        self.assertEqual(self.client.get(reverse('csv_records', args=[batch.pk])).status_code, 410)
        self.assertEqual(self.client.post(reverse('csv_upload'), {'batch_id': batch.pk}).status_code, 410)
