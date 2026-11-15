import uuid
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

from csv_app.models import CSVImportBatch
from operations.status_integrity import status_integrity_issues
from payments.models import BillingProvisioning
from pdf_output.models import PDFRequest


class JobStatusConstraintTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.bulk_create([get_user_model()(username='job-status-owner')])[0]

    def job(self, model, **values):
        defaults = {'user': self.user}
        if model is PDFRequest:
            defaults['task_id'] = str(uuid.uuid4())
        elif model is CSVImportBatch:
            defaults.update(content='unchanged preview payload', row_count=2)
        return model(**{**defaults, **values})

    def test_every_declared_status_and_defaults_are_accepted(self):
        for model in (PDFRequest, CSVImportBatch, BillingProvisioning):
            with self.subTest(model=model.__name__):
                row = model.objects.bulk_create([self.job(model)])[0]
                self.assertEqual(row.status, model._meta.get_field('status').get_default())
                for status in model.Status.values:
                    model.objects.filter(pk=row.pk).update(status=status)
                    row.refresh_from_db()
                    self.assertEqual(row.status, status)
                # Constraints validate membership, not the order of transitions.
                model.objects.filter(pk=row.pk).update(status=model.Status.values[0])
        self.assertEqual(status_integrity_issues(apps, 'default'), [])

    def test_invalid_inserts_and_updates_do_not_change_existing_jobs(self):
        for model in (PDFRequest, CSVImportBatch, BillingProvisioning):
            for status in ('', ' ', 'procesing', 'QUEUED', 'queued ', None):
                with self.subTest(model=model.__name__, status=status):
                    with self.assertRaises(IntegrityError), transaction.atomic():
                        model.objects.bulk_create([self.job(model, status=status)])
            row = model.objects.bulk_create([self.job(model)])[0]
            snapshot = model.objects.filter(pk=row.pk).values().get()
            for status in ('', 'procesing', None):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    model.objects.filter(pk=row.pk).update(status=status)
                self.assertEqual(model.objects.filter(pk=row.pk).values().get(), snapshot)

    def test_invalid_bulk_update_is_atomic(self):
        jobs = PDFRequest.objects.bulk_create([self.job(PDFRequest), self.job(PDFRequest)])
        snapshot = list(PDFRequest.objects.order_by('pk').values())
        jobs[0].status = PDFRequest.Status.SENT
        jobs[1].status = 'procesing'
        with self.assertRaises(IntegrityError), transaction.atomic():
            PDFRequest.objects.bulk_update(jobs, ['status'])
        self.assertEqual(list(PDFRequest.objects.order_by('pk').values()), snapshot)


class JobStatusMigrationTests(TransactionTestCase):
    def test_invalid_historical_status_aborts_without_reopening_or_changing_job(self):
        latest = MigrationExecutor(connection).loader.graph.leaf_nodes()
        cases = (
            ('pdf_output', 'PDFRequest', '0009_pdfrequest_render_attempts', '0010_valid_job_status', {'task_id': 'unchanged-task'}, 'queued'),
            ('csv_app', 'CSVImportBatch', '0002_background_import', '0003_valid_job_status', {'content': 'unchanged preview', 'row_count': 2}, 'preview'),
            ('payments', 'BillingProvisioning', '0005_stripewebhookfailure', '0006_valid_job_status', {'last_error': 'unchanged error'}, 'pending'),
        )
        for app, name, old_name, new_name, fields, valid in cases:
            with self.subTest(model=name):
                executor = MigrationExecutor(connection)
                executor.migrate([(app, old_name)])
                old = executor.loader.project_state([(app, old_name)]).apps
                user_model, model = old.get_model('auth', 'User'), old.get_model(app, name)
                user = user_model.objects.create(username=f'{app}-status-migration')
                try:
                    job = model.objects.create(user_id=user.pk, status='procesing', **fields)
                    snapshot = model.objects.filter(pk=job.pk).values().get()
                    with patch('operations.status_integrity.JOB_MODELS', (f'{app}.{name}',)):
                        self.assertTrue(status_integrity_issues(old, 'default'))
                    with self.assertRaisesMessage(RuntimeError, 'unsupported status'):
                        MigrationExecutor(connection).migrate([(app, new_name)])
                    self.assertEqual(model.objects.filter(pk=job.pk).values().get(), snapshot)
                    model.objects.filter(pk=job.pk).update(status=valid)  # Only this disposable fixture.
                    MigrationExecutor(connection).migrate([(app, new_name)])
                    self.assertEqual(model.objects.get(pk=job.pk).status, valid)
                finally:
                    user_model.objects.filter(pk=user.pk).delete()
                    MigrationExecutor(connection).migrate(latest)
