from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from threading import Event, Barrier
import time
import uuid
from unittest.mock import patch

from celery.exceptions import SoftTimeLimitExceeded
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection, close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from kombu.exceptions import OperationalError

from csv_app.models import CSVImportBatch
from csv_app.tasks import import_csv_batch
from csv_app.tests.test_atomic_import import content, row
from flights.models import Flight, Approach, Aircraft, TailNumber, Total


@override_settings(SECURE_SSL_REDIRECT=False)
class CSVBackgroundImportTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='csv_background', email='bg@example.com')
        self.other = get_user_model().objects.create_user(username='csv_background_other')
        self.client.force_login(self.user)
        self.batch = CSVImportBatch.objects.create(user=self.user, content=content(), row_count=1)
        publisher = patch('csv_app.submission.import_csv_batch.apply_async')
        self.publish = publisher.start()
        self.addCleanup(publisher.stop)

    def submit(self):
        return self.client.post(reverse('csv_upload'), {'batch_id': self.batch.pk})

    def run_worker(self, user=None, task_id=None):
        self.batch.refresh_from_db()
        import_csv_batch.push_request(id=task_id or self.batch.task_id)
        try:
            import_csv_batch.run((user or self.user).pk, str(self.batch.pk))
        finally:
            import_csv_batch.pop_request()
        self.batch.refresh_from_db()

    def status(self):
        return self.client.get(reverse('csv_import_status', args=[self.batch.pk]))

    def cleanup(self):
        output = StringIO()
        call_command('cleanup_csv_previews', stdout=output)
        return output.getvalue()

    def test_submission_only_publishes_identifiers_and_returns_accepted(self):
        response = self.submit()
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()['status'], 'queued')
        self.assertFalse(Flight.objects.exists())
        self.batch.refresh_from_db()
        self.assertIsNotNone(self.batch.submitted_at)
        self.publish.assert_called_once_with(args=(self.user.pk, str(self.batch.pk)), task_id=self.batch.task_id, retry=False)

    def test_repeated_submission_and_duplicate_task_do_not_repeat_import_or_email(self):
        self.submit()
        response = self.submit()
        self.assertTrue(response.json()['already_submitted'])
        with patch('csv_app.csv_import.email_confirmation') as notify:
            with self.captureOnCommitCallbacks(execute=True):
                self.run_worker()
                self.run_worker()
        self.assertEqual(self.publish.call_count, 1)
        self.assertEqual(Flight.objects.count(), 1)
        self.assertEqual(Approach.objects.count(), 1)
        notify.assert_called_once()
        response = self.submit()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['already_completed'])
        self.assertEqual(self.status().json()['imported_count'], 1)
        self.assertEqual(self.batch.content, '')

    def test_progress_is_owner_scoped_read_only_and_not_cached(self):
        self.submit()
        response = self.status()
        self.assertEqual(response.json()['imported_count'], 0)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(self.client.post(reverse('csv_import_status', args=[self.batch.pk])).status_code, 405)
        self.client.force_login(self.other)
        self.assertEqual(self.status().status_code, 404)
        self.assertEqual(self.submit().status_code, 404)
        self.client.logout()
        self.assertEqual(self.status().status_code, 302)

    def test_wrong_user_or_stale_task_id_cannot_claim_job(self):
        self.submit()
        self.run_worker(user=self.other)
        self.run_worker(task_id='wrong-task-id')
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, CSVImportBatch.Status.QUEUED)
        self.assertFalse(Flight.objects.exists())

    def test_unconfirmed_publication_can_still_be_completed_by_worker(self):
        self.publish.side_effect = OperationalError('broker')
        with self.assertLogs('django.csv_app', level='ERROR'):
            response = self.submit()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['status'], 'unconfirmed')
        self.submit()
        self.assertEqual(self.publish.call_count, 1)
        self.run_worker()
        self.assertTrue(self.batch.completed)

    def test_fast_worker_completion_is_not_overwritten_by_publish_error(self):
        def publish(*args, **kwargs):
            self.run_worker(task_id=kwargs['task_id'])
            raise OperationalError('acknowledgement lost')
        self.publish.side_effect = publish
        with self.assertLogs('django.csv_app', level='ERROR'):
            response = self.submit()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'completed')

    def test_queued_payload_survives_preview_expiry_and_cleanup(self):
        self.submit()
        CSVImportBatch.objects.filter(pk=self.batch.pk).update(created_at=timezone.now() - timedelta(minutes=15))
        self.cleanup()
        self.batch.refresh_from_db()
        self.assertTrue(self.batch.content)
        self.assertFalse(self.batch.is_expired)
        self.run_worker()
        self.assertTrue(self.batch.completed)

    def test_mid_import_failure_rolls_back_all_flights_and_totals(self):
        self.batch.content = content([row(), row(**{'2': 'N54321'})])
        self.batch.row_count = 2
        self.batch.save()
        self.submit()
        original = Approach.objects.create
        count = 0
        def create(**kwargs):
            nonlocal count
            count += 1
            if count == 2:
                raise RuntimeError('internal database detail')
            return original(**kwargs)
        with patch('csv_app.csv_import.Approach.objects.create', side_effect=create):
            with self.assertLogs('django.csv_app', level='ERROR'):
                with self.assertRaises(RuntimeError):
                    self.run_worker()
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, CSVImportBatch.Status.FAILED)
        self.assertEqual(self.batch.content, '')
        self.assertFalse(Flight.objects.exists())
        self.assertFalse(Aircraft.objects.exists())
        self.assertFalse(TailNumber.objects.exists())
        self.assertEqual(Total.objects.get(user=self.user, total='All').total_time, 0)
        self.assertNotIn('internal database detail', self.status().json()['message'])
        self.assertEqual(self.submit().status_code, 409)
        self.assertEqual(self.publish.call_count, 1)

    def test_soft_time_limit_records_failure_after_rollback(self):
        self.submit()
        with patch('csv_app.csv_import.csv_import', side_effect=SoftTimeLimitExceeded()):
            with self.assertLogs('django.csv_app', level='ERROR'):
                with self.assertRaises(SoftTimeLimitExceeded):
                    self.run_worker()
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.status, CSVImportBatch.Status.FAILED)
        self.assertEqual(import_csv_batch.soft_time_limit, 900)
        self.assertEqual(import_csv_batch.time_limit, 960)

    def test_map_signal_reconnects_after_soft_timeout(self):
        from django.db.models.signals import post_save
        from flights.signal_make_json_field import make_json_field
        from types import SimpleNamespace
        instance = SimpleNamespace(route='KAAA-KBBB', save=lambda **kwargs: None)
        with patch.object(instance, 'save', side_effect=SoftTimeLimitExceeded()):
            try:
                with self.assertRaises(SoftTimeLimitExceeded):
                    make_json_field(Flight, instance, created=True)
                self.assertTrue(post_save.disconnect(make_json_field, sender=Flight, dispatch_uid='app_data_update'))
            finally:
                post_save.connect(make_json_field, sender=Flight, dispatch_uid='app_data_update')

    def test_stalled_job_is_closed_and_late_worker_ignored(self):
        self.submit()
        CSVImportBatch.objects.filter(pk=self.batch.pk).update(updated_at=timezone.now() - timedelta(minutes=21))
        self.assertIn('Closed 1 stalled', self.cleanup())
        self.run_worker()
        self.assertEqual(self.batch.status, CSVImportBatch.Status.FAILED)
        self.assertFalse(Flight.objects.exists())

    def test_old_worker_cannot_reopen_a_closed_batch(self):
        self.submit()
        self.batch.refresh_from_db()
        CSVImportBatch.objects.filter(pk=self.batch.pk).update(status='failed', content='')
        self.run_worker()
        self.assertFalse(Flight.objects.exists())

    def test_recent_submitted_batch_is_visible_after_reloading_inspect_page(self):
        old = CSVImportBatch.objects.create(user=self.user, content='', row_count=1, completed=True, status='completed')
        self.submit()
        response = self.client.get(reverse('csv_inspect'))
        self.assertEqual(response.context['latest_import'].pk, self.batch.pk)
        self.assertContains(response, reverse('csv_import_status', args=[self.batch.pk]))

    def test_completed_or_failed_import_message_does_not_reappear_on_page_load(self):
        for state, completed in [('completed', True), ('failed', False)]:
            with self.subTest(state=state):
                CSVImportBatch.objects.filter(pk=self.batch.pk).update(status=state, completed=completed)
                response = self.client.get(reverse('csv_inspect'))
                self.assertIsNone(response.context['latest_import'])
                self.assertNotContains(response, reverse('csv_import_status', args=[self.batch.pk]))

    def test_notification_failure_does_not_trigger_duplicate_data_import(self):
        self.submit()
        with patch('csv_app.csv_import.email_confirmation', side_effect=TimeoutError('mail')):
            with self.assertLogs('django.csv_app', level='ERROR'):
                with self.captureOnCommitCallbacks(execute=True):
                    self.run_worker()
        self.assertTrue(self.batch.completed)
        self.run_worker()
        self.assertEqual(Flight.objects.count(), 1)


@override_settings(SECURE_SSL_REDIRECT=False)
class CSVBackgroundProgressConcurrencyTests(TransactionTestCase):
    def test_status_and_repeat_submission_do_not_wait_for_import_transaction(self):
        if connection.vendor != 'postgresql':
            self.skipTest('PostgreSQL MVCC regression')
        user = get_user_model().objects.create_user(username='csv_progress_concurrent')
        batch = CSVImportBatch.objects.create(user=user, content=content(), row_count=1,
            status='queued', task_id=str(uuid.uuid4()), submitted_at=timezone.now())
        started, release = Event(), Event()
        def importing(request, payload):
            started.set()
            if not release.wait(timeout=10):
                raise RuntimeError('Test import gate timed out')
            return 1
        def worker():
            close_old_connections()
            import_csv_batch.push_request(id=batch.task_id)
            try:
                import_csv_batch.run(user.pk, str(batch.pk))
            finally:
                import_csv_batch.pop_request()
                connection.close()
        self.client.force_login(user)
        with patch('csv_app.csv_import.csv_import', side_effect=importing):
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(worker)
                try:
                    self.assertTrue(started.wait(timeout=5))
                    before = time.monotonic()
                    status = self.client.get(reverse('csv_import_status', args=[batch.pk]))
                    response = self.client.post(reverse('csv_upload'), {'batch_id': batch.pk})
                    elapsed = time.monotonic() - before
                finally:
                    release.set()
                future.result(timeout=10)
        self.assertEqual(status.json()['status'], 'processing')
        self.assertEqual(response.status_code, 202)
        self.assertLess(elapsed, 2)

    def test_concurrent_initial_submissions_publish_only_once(self):
        if connection.vendor != 'postgresql':
            self.skipTest('PostgreSQL CAS regression')
        from csv_app.submission import queue_csv_import
        user = get_user_model().objects.create_user(username='csv_queue_concurrent')
        batch = CSVImportBatch.objects.create(user=user, content=content(), row_count=1)
        barrier = Barrier(2)
        def submit():
            close_old_connections()
            try:
                worker_user = get_user_model().objects.get(pk=user.pk)
                barrier.wait(timeout=5)
                result, duplicate = queue_csv_import(worker_user, batch.pk)
                return duplicate
            finally:
                connection.close()
        with patch('csv_app.submission.import_csv_batch.apply_async') as publish:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(submit) for _ in range(2)]
                duplicates = [future.result(timeout=10) for future in futures]
        self.assertEqual(sorted(duplicates), [False, True])
        publish.assert_called_once()

    def test_cleanup_skips_stale_row_locked_by_active_import(self):
        if connection.vendor != 'postgresql':
            self.skipTest('PostgreSQL skip-locked regression')
        from django.db import transaction
        user = get_user_model().objects.create_user(username='csv_cleanup_active')
        batch = CSVImportBatch.objects.create(user=user, content=content(), row_count=1,
            status='processing', task_id=str(uuid.uuid4()),
            updated_at=timezone.now() - timedelta(minutes=21))
        locked, release = Event(), Event()
        def active_transaction():
            close_old_connections()
            try:
                with transaction.atomic():
                    CSVImportBatch.objects.select_for_update().get(pk=batch.pk)
                    locked.set()
                    if not release.wait(timeout=10):
                        raise RuntimeError('Test lock gate timed out')
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(active_transaction)
            try:
                self.assertTrue(locked.wait(timeout=5))
                output = StringIO()
                started = time.monotonic()
                call_command('cleanup_csv_previews', stdout=output)
                elapsed = time.monotonic() - started
            finally:
                release.set()
            future.result(timeout=10)
        self.assertLess(elapsed, 2)
        self.assertIn('Closed 0 stalled', output.getvalue())
        batch.refresh_from_db()
        self.assertEqual(batch.status, 'processing')
        self.assertTrue(batch.content)
