from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from accounts.models import AccountDeletionCleanup


class LegacyAccountMigrationTests(TransactionTestCase):
    def tearDown(self):
        MigrationExecutor(connection).migrate([('accounts', '0002_ensure_deletion_cleanup_table')])
        super().tearDown()

    def test_legacy_initial_history_without_cleanup_table_is_repaired(self):
        MigrationExecutor(connection).migrate([('accounts', '0001_initial')])
        with connection.schema_editor() as editor:
            editor.delete_model(AccountDeletionCleanup)
        self.assertNotIn(AccountDeletionCleanup._meta.db_table, connection.introspection.table_names())
        with self.assertRaisesMessage(CommandError, 'accounts_accountdeletioncleanup'):
            call_command('check_database_schema', stdout=StringIO())
        MigrationExecutor(connection).migrate([('accounts', '0002_ensure_deletion_cleanup_table')])
        call_command('check_database_schema', stdout=StringIO())
        job = AccountDeletionCleanup.objects.create(customer_ids=['cus_test'])
        self.assertTrue(AccountDeletionCleanup.objects.filter(pk=job.pk).exists())

    def test_existing_cleanup_table_and_pending_job_are_preserved(self):
        job = AccountDeletionCleanup.objects.create(customer_ids=['cus_test'])
        MigrationExecutor(connection).migrate([('accounts', '0001_initial')])
        MigrationExecutor(connection).migrate([('accounts', '0002_ensure_deletion_cleanup_table')])
        self.assertEqual(AccountDeletionCleanup.objects.get(pk=job.pk).customer_ids, ['cus_test'])
