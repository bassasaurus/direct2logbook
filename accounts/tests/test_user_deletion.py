import uuid
import json
from io import StringIO
from datetime import date
from unittest.mock import patch

import stripe
from allauth.account.models import EmailAddress, EmailConfirmation
from allauth.socialaccount.models import SocialAccount, SocialToken, SocialApp
from django.contrib.admin.models import LogEntry, ADDITION
from django.contrib.auth import get_user_model, SESSION_KEY
from django.contrib.contenttypes.models import ContentType
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase, override_settings
from django.core.management import call_command
from django_celery_results.models import TaskResult
from django.utils import timezone
from django.urls import reverse
from rest_framework.authtoken.models import Token

from accounts.deletion import clean_external_resources
from accounts.models import AccountDeletionCleanup
from api.models import MobileSyncReceipt
from csv_app.models import CSVImportBatch
from flights.models import Aircraft, Flight, TailNumber, Approach, Holding, Imported
from payments.models import BillingProvisioning
from profile.models import Reminder
from signature.models import Signature
from pdf_output.models import PDFRequest


class UserDeletionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='delete_me', email='delete@example.com')
        self.other = get_user_model().objects.create_user(username='keep_me')
        self.aircraft = Aircraft.objects.create(
            user=self.user, aircraft_type='C172', aircraft_category='A', aircraft_class='SEL', piston=True, small=True)
        self.tail = TailNumber.objects.create(
            user=self.user, aircraft=self.aircraft, registration='N123', is_91=True)
        self.flight = Flight.objects.create(user=self.user, aircraft_type=self.aircraft, registration=self.tail,
                                            date=date(2026, 1, 1), duration=1, pilot_in_command=True, route='KAAA-KBBB')

    def test_model_and_queryset_deletion_remove_every_owned_relation(self):
        for bulk in (False, True):
            with self.subTest(bulk=bulk), transaction.atomic():
                self.populate_related_records()
                user_id = self.user.pk
                if bulk:
                    get_user_model().objects.filter(pk=user_id).delete()
                else:
                    self.user.delete()
                self.assertFalse(get_user_model().objects.filter(pk=user_id).exists())
                for relation in get_user_model()._meta.related_objects:
                    self.assertFalse(relation.related_model.objects.filter(
                        **{relation.field.name + '_id': user_id}).exists(), relation.related_model._meta.label)
                self.assertFalse(Approach.objects.filter(pk=self.approach.pk).exists())
                self.assertFalse(Holding.objects.filter(pk=self.holding.pk).exists())
                self.assertFalse(Session.objects.filter(pk=self.session_key).exists())
                self.assertTrue(Session.objects.filter(pk=self.other_session_key).exists())
                self.assertTrue(get_user_model().objects.filter(pk=self.other.pk).exists())
                self.assertTrue(self.other.total_set.filter(total='All').exists())
                # Reuse exactly the same fixture for the two deletion entry points.
                transaction.set_rollback(True)
            self.user.pk = user_id
            self.user.refresh_from_db()

    def populate_related_records(self):
        email = EmailAddress.objects.create(user=self.user, email=self.user.email, verified=True)
        EmailConfirmation.objects.create(email_address=email, sent=timezone.now(), key='key')
        account = SocialAccount.objects.create(
            user=self.user, provider='google', uid='deletion-google')
        app = SocialApp.objects.create(provider='google', name='Google')
        SocialToken.objects.create(app=app, account=account, token='fake-oauth-token')
        Token.objects.create(user=self.user)
        self.approach = Approach.objects.create(
            flight_object=self.flight, approach_type='ILS', number=1)
        self.holding = Holding.objects.create(flight_object=self.flight, hold=True)
        Imported.objects.create(user=self.user, aircraft_type=self.aircraft, total_time=2)
        Signature.objects.create(user=self.user, signature='data:image/png;base64,example')
        Reminder.objects.create(user=self.user, title='BFR',
                                kind=Reminder.Kind.EXPIRATION, due_date=date(2027, 1, 1))
        PDFRequest.objects.create(user=self.user, task_id='pdf-deletion')
        CSVImportBatch.objects.create(user=self.user, content='private csv', row_count=1)
        MobileSyncReceipt.objects.create(user=self.user, operation_id=uuid.uuid4(
        ), request_hash='a' * 64, response={'id': self.flight.pk})
        LogEntry.objects.create(user=self.user, content_type=ContentType.objects.get_for_model(
            Flight), object_id=str(self.flight.pk), object_repr='private flight', action_flag=ADDITION)
        BillingProvisioning.objects.create(user=self.user)
        session = SessionStore()
        session[SESSION_KEY] = str(self.user.pk)
        session.save()
        self.session_key = session.session_key
        session = SessionStore()
        session[SESSION_KEY] = str(self.other.pk)
        session.save()
        self.other_session_key = session.session_key

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_admin_single_delete_removes_subject_log_and_reports_pending_stripe(self):
        self.other.is_staff = True
        self.other.is_superuser = True
        self.other.save()
        self.client.force_login(self.other)
        self.user.profile.customer_id = 'cus_delete'
        self.user.profile.save()
        user_id = self.user.pk
        response = self.client.post(reverse('admin:auth_user_delete', args=[
                                    user_id]), {'post': 'yes'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Stripe/file cleanup is queued after commit.')
        self.assertFalse(get_user_model().objects.filter(pk=user_id).exists())
        self.assertFalse(LogEntry.objects.filter(content_type=ContentType.objects.get_for_model(
            get_user_model()), object_id=str(user_id)).exists())
        self.assertEqual(AccountDeletionCleanup.objects.count(), 1)

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_admin_bulk_delete_removes_user_without_recreating_summaries(self):
        self.other.is_staff = True
        self.other.is_superuser = True
        self.other.save()
        self.client.force_login(self.other)
        user_id = self.user.pk
        response = self.client.post(reverse('admin:auth_user_changelist'), {
            'action': 'delete_selected', '_selected_action': [str(user_id)], 'post': 'yes'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(get_user_model().objects.filter(pk=user_id).exists())
        self.assertFalse(self.user.total_set.exists())

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_admin_shows_provisioning_protection_instead_of_a_server_error(self):
        self.other.is_staff = True
        self.other.is_superuser = True
        self.other.save()
        self.client.force_login(self.other)
        BillingProvisioning.objects.create(
            user=self.user, status=BillingProvisioning.Status.PROCESSING)
        response = self.client.post(reverse('admin:auth_user_delete',
                                            args=[self.user.pk]), {'post': 'yes'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Billing is in progress or needs reconciliation.')
        self.assertTrue(get_user_model().objects.filter(pk=self.user.pk).exists())

    def test_admin_subject_logs_and_task_results_are_removed_without_touching_others(self):
        logs = []
        for model, obj in ((get_user_model(), self.user), (Flight, self.flight), (Aircraft, self.aircraft)):
            logs.append(LogEntry.objects.create(user=self.other, content_type=ContentType.objects.get_for_model(model),
                                                object_id=str(obj.pk), object_repr='private data', action_flag=ADDITION).pk)
        unrelated = LogEntry.objects.create(user=self.other, content_type=ContentType.objects.get_for_model(get_user_model()),
                                            object_id=str(self.other.pk), object_repr='keep', action_flag=ADDITION)
        PDFRequest.objects.create(user=self.user, task_id='own-pdf')
        TaskResult.objects.create(task_id='own-pdf', result='private failure', status='FAILURE')
        probe = TaskResult.objects.create(
            task_id='own-probe', result=json.dumps({'env': {}, 'user': self.user.pk}), status='SUCCESS')
        other_probe = TaskResult.objects.create(
            task_id='other-probe', result=json.dumps({'env': {}, 'user': self.other.pk}), status='SUCCESS')
        self.user.delete()
        self.assertFalse(LogEntry.objects.filter(pk__in=logs).exists())
        self.assertTrue(LogEntry.objects.filter(pk=unrelated.pk).exists())
        self.assertFalse(TaskResult.objects.filter(task_id__in=['own-pdf', 'own-probe']).exists())
        self.assertTrue(TaskResult.objects.filter(pk=other_probe.pk).exists())

    def test_cross_owner_link_prevents_deleting_another_users_records(self):
        foreign = Flight.objects.create(user=self.other, aircraft_type=self.aircraft,
                                        registration=self.tail, date=date(2026, 1, 2), route='KAAA-KBBB', duration=1)
        with self.assertRaises(ProtectedError), transaction.atomic():
            self.user.delete()
        self.assertTrue(Flight.objects.filter(pk=foreign.pk).exists())

    @patch('accounts.tasks.cleanup_deleted_account.apply_async')
    def test_aircraft_file_is_captured_before_its_row_disappears(self, publish):
        Aircraft.objects.filter(pk=self.aircraft.pk).update(image='aircraft/private.png')
        with self.captureOnCommitCallbacks(execute=True):
            self.user.delete()
        self.assertEqual(AccountDeletionCleanup.objects.get().media_names, ['aircraft/private.png'])
        publish.assert_called_once()

    @patch('accounts.tasks.cleanup_deleted_account.apply_async')
    def test_external_cleanup_is_queued_only_after_commit(self, publish):
        self.user.profile.customer_id = 'cus_delete'
        self.user.profile.save()
        BillingProvisioning.objects.create(
            user=self.user, stripe_customer_id='cus_second', stripe_subscription_id='sub_delete')
        with self.captureOnCommitCallbacks(execute=True):
            self.user.delete()
            publish.assert_not_called()
            job = AccountDeletionCleanup.objects.get()
            self.assertEqual(job.customer_ids, ['cus_delete', 'cus_second'])
            self.assertEqual(job.subscription_ids, ['sub_delete'])
        publish.assert_called_once_with(args=(str(job.pk), 'default'), retry=False)

    @patch('accounts.tasks.cleanup_deleted_account.apply_async')
    def test_rollback_preserves_account_and_does_not_publish(self, publish):
        self.user.profile.customer_id = 'cus_delete'
        self.user.profile.save()
        user_id = self.user.pk
        with self.captureOnCommitCallbacks(execute=True):
            with transaction.atomic():
                self.user.delete()
                transaction.set_rollback(True)
        self.assertTrue(get_user_model().objects.filter(pk=user_id).exists())
        self.assertFalse(AccountDeletionCleanup.objects.exists())
        publish.assert_not_called()

    @patch('accounts.tasks.cleanup_deleted_account.apply_async', side_effect=ConnectionError('broker down'))
    def test_broker_failure_does_not_lose_cleanup(self, publish):
        self.user.profile.customer_id = 'cus_delete'
        self.user.profile.save()
        with self.assertLogs('accounts.deletion', level='ERROR'), self.captureOnCommitCallbacks(execute=True):
            self.user.delete()
        self.assertEqual(AccountDeletionCleanup.objects.get().customer_ids, ['cus_delete'])

    def test_inflight_or_uncertain_provisioning_blocks_deletion(self):
        record = BillingProvisioning.objects.create(user=self.user)
        for status, uncertain in [(BillingProvisioning.Status.PROCESSING, False), (BillingProvisioning.Status.FAILED, True)]:
            record.status = status
            record.outcome_uncertain = uncertain
            record.save()
            with self.subTest(status=status), self.assertRaises(ProtectedError), transaction.atomic():
                self.user.delete()
            self.assertTrue(get_user_model().objects.filter(pk=self.user.pk).exists())

    def test_shared_stripe_mapping_blocks_deletion(self):
        for user in (self.user, self.other):
            user.profile.customer_id = 'cus_shared'
            user.profile.save()
        with self.assertRaises(ProtectedError), transaction.atomic():
            self.user.delete()


class ExternalCleanupTests(TestCase):
    @patch('accounts.deletion.default_storage.delete')
    @patch('accounts.deletion.stripe.Customer.delete', return_value={'deleted': True})
    @patch('accounts.deletion.stripe.Subscription.retrieve', return_value={'customer': 'cus_from_subscription'})
    def test_customer_deletion_covers_all_known_customers_and_media(self, subscription, customer, storage):
        job = AccountDeletionCleanup.objects.create(customer_ids=['cus_profile'], subscription_ids=[
                                                    'sub_one'], media_names=['aircraft/owned.png'])
        clean_external_resources(job.pk)
        self.assertEqual({call.args[0] for call in customer.call_args_list}, {
                         'cus_profile', 'cus_from_subscription'})
        storage.assert_called_once_with('aircraft/owned.png')
        self.assertFalse(AccountDeletionCleanup.objects.exists())
        clean_external_resources(job.pk)
        self.assertEqual(customer.call_count, 2)

    @patch('accounts.deletion.stripe.Customer.delete', side_effect=TimeoutError('customer private data'))
    def test_failure_keeps_retry_without_recording_personal_data(self, customer):
        job = AccountDeletionCleanup.objects.create(customer_ids=['cus_delete'])
        with self.assertRaises(TimeoutError):
            clean_external_resources(job.pk)
        job.refresh_from_db()
        self.assertEqual(job.attempts, 1)
        self.assertEqual(job.last_error, 'TimeoutError')
        self.assertGreater(job.next_attempt_at, timezone.now())

    @patch('accounts.deletion.stripe.Customer.delete')
    def test_retry_after_already_deleted_customer(self, customer):
        customer.side_effect = stripe.error.InvalidRequestError(
            'gone', 'id', code='resource_missing', http_status=404)
        job = AccountDeletionCleanup.objects.create(customer_ids=['cus_deleted'])
        clean_external_resources(job.pk)
        self.assertFalse(AccountDeletionCleanup.objects.exists())

    @patch('accounts.deletion.stripe.Customer.delete')
    def test_active_account_reference_prevents_remote_deletion(self, customer):
        user = get_user_model().objects.create_user(username='keep')
        user.profile.customer_id = 'cus_shared'
        user.profile.save()
        job = AccountDeletionCleanup.objects.create(customer_ids=['cus_shared'])
        with self.assertRaisesMessage(Exception, 'StripeResourceStillReferenced'):
            clean_external_resources(job.pk)
        customer.assert_not_called()

    @patch('accounts.deletion.default_storage.delete', side_effect=OSError('storage down'))
    @patch('accounts.deletion.stripe.Customer.delete', return_value={'deleted': True})
    def test_storage_failure_preserves_retry_after_stripe_success(self, customer, storage):
        job = AccountDeletionCleanup.objects.create(
            customer_ids=['cus_delete'], media_names=['aircraft/owned.png'])
        with self.assertRaises(OSError):
            clean_external_resources(job.pk)
        self.assertTrue(AccountDeletionCleanup.objects.filter(pk=job.pk).exists())

    @patch('accounts.deletion.stripe.Customer.delete', return_value={'deleted': True})
    def test_scheduled_command_drains_pending_cleanup(self, customer):
        AccountDeletionCleanup.objects.create(customer_ids=['cus_delete'])
        output = StringIO()
        call_command('process_account_deletions', stdout=output)
        self.assertIn('completed=1, pending retries=0', output.getvalue())
        self.assertFalse(AccountDeletionCleanup.objects.exists())

    @patch('accounts.deletion.default_storage.delete')
    def test_shared_media_is_not_deleted(self, storage):
        user = get_user_model().objects.create_user(username='shared-file-owner')
        Aircraft.objects.create(user=user, aircraft_type='C172', image='aircraft/shared.png')
        job = AccountDeletionCleanup.objects.create(media_names=['aircraft/shared.png'])
        clean_external_resources(job.pk)
        storage.assert_not_called()
        self.assertFalse(AccountDeletionCleanup.objects.exists())
