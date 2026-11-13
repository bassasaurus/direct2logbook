"""Account deletion with transactional, retryable external-resource cleanup."""
import json
import logging
from datetime import timedelta
from functools import partial

import stripe
from django.conf import settings
from django.contrib.auth import get_user_model, SESSION_KEY
from django.contrib.sessions.models import Session
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import F, Q
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from accounts.models import AccountDeletionCleanup
from flights.models import Aircraft, Flight, Imported, TailNumber, Approach, Holding
from payments.models import BillingProvisioning
from profile.models import Profile, Reminder

logger = logging.getLogger(__name__)


class CleanupBlocked(Exception):
    """A safe operational reason that may be shown in the cleanup queue."""


def account_deletion_resources(user, using, lock=False):
    # Serialize against sync/import transactions and billing claims.
    if lock:
        get_user_model().objects.using(using).select_for_update().get(pk=user.pk)
    records = BillingProvisioning.objects.using(using).filter(user_id=user.pk)
    record = (records.select_for_update() if lock else records).first()
    if record and (record.status == BillingProvisioning.Status.PROCESSING or record.outcome_uncertain):
        raise ProtectedError(
            'Billing is in progress or needs reconciliation. Resolve it before deleting this account.', [user])
    # Legacy cross-owner links must not cascade into someone else's logbook.
    foreign_links = (
        Flight.objects.using(using).exclude(user_id=user.pk).filter(
            Q(aircraft_type__user_id=user.pk) | Q(registration__user_id=user.pk)),
        TailNumber.objects.using(using).exclude(user_id=user.pk).filter(aircraft__user_id=user.pk),
        Imported.objects.using(using).exclude(
            user_id=user.pk).filter(aircraft_type__user_id=user.pk),
        Reminder.objects.using(using).exclude(user_id=user.pk).filter(aircraft__user_id=user.pk),
    )
    if any(query.exists() for query in foreign_links):
        raise ProtectedError(
            'Another account references this logbook. Correct the ownership links before deleting.', [user])
    profile = Profile.objects.using(using).filter(user_id=user.pk).first()
    customers = sorted({value for value in (getattr(profile, 'customer_id', ''),
                                            getattr(record, 'stripe_customer_id', '')) if value})
    subscriptions = sorted({value for value in (
        getattr(profile, 'subscription_id', ''), getattr(record, 'stripe_subscription_id', '')) if value})
    if (Profile.objects.using(using).exclude(user_id=user.pk).filter(Q(customer_id__in=customers) | Q(subscription_id__in=subscriptions)).exists()
            or BillingProvisioning.objects.using(using).exclude(user_id=user.pk).filter(Q(stripe_customer_id__in=customers) | Q(stripe_subscription_id__in=subscriptions)).exists()):
        raise ProtectedError(
            'Another account references these Stripe resources. Reconcile billing before deleting.', [user])
    media = list(Aircraft.objects.using(using).filter(user_id=user.pk).exclude(
        image='').exclude(image=None).values_list('image', flat=True))
    return customers, subscriptions, media


def prepare_account_deletion(user, using):
    customers, subscriptions, media = account_deletion_resources(user, using, lock=True)
    if customers or subscriptions or media:
        cleanup = AccountDeletionCleanup.objects.using(using).create(
            customer_ids=customers, subscription_ids=subscriptions, media_names=sorted(set(media)))
        transaction.on_commit(partial(publish_cleanup, str(cleanup.pk), using), using=using)
    purge_indirect_records(user, using)
    # Database sessions contain the user ID in their encoded payload, not a FK.
    keys = [s.session_key for s in Session.objects.using(using).iterator(
        chunk_size=500) if str(s.get_decoded().get(SESSION_KEY, '')) == str(user.pk)]
    Session.objects.using(using).filter(session_key__in=keys).delete()


def purge_indirect_records(user, using):
    from django.contrib.admin.models import LogEntry
    from django.contrib.contenttypes.models import ContentType
    from django_celery_results.models import TaskResult
    from allauth.account.models import EmailConfirmation
    from allauth.socialaccount.models import SocialToken
    from csv_app.models import CSVImportBatch
    from pdf_output.models import PDFRequest

    # Admin's actor FK does not cover records ABOUT a deleted user or their data.
    subjects = [(get_user_model(), [user.pk])]
    for relation in get_user_model()._meta.related_objects:
        if relation.related_model is LogEntry:
            continue
        ids = list(relation.related_model.objects.using(using).filter(
            **{relation.field.name + '_id': user.pk}).values_list('pk', flat=True))
        subjects.append((relation.related_model, ids))
    for model, lookup in ((Approach, 'flight_object__user_id'), (Holding, 'flight_object__user_id'),
                          (EmailConfirmation, 'email_address__user_id'), (SocialToken, 'account__user_id')):
        subjects.append((model, list(model.objects.using(using).filter(
            **{lookup: user.pk}).values_list('pk', flat=True))))
    for model, ids in subjects:
        if ids:
            content_type = ContentType.objects.db_manager(using).get_for_model(model)
            LogEntry.objects.using(using).filter(content_type_id=content_type.pk,
                                                 object_id__in=[str(pk) for pk in ids]).delete()

    task_ids = list(PDFRequest.objects.using(using).filter(
        user_id=user.pk).values_list('task_id', flat=True))
    task_ids += list(CSVImportBatch.objects.using(using).filter(user_id=user.pk)
                     .exclude(task_id=None).values_list('task_id', flat=True))
    TaskResult.objects.using(using).filter(task_id__in=task_ids).delete()
    # The legacy diagnostic probe stored a user ID in its result without a FK.
    results = TaskResult.objects.using(using).filter(
        Q(task_name='pdf_output.pdf_generate_task.celery_debug_probe') |
        Q(task_name__isnull=True, result__contains='"env"'))
    for result in results.iterator(chunk_size=500):
        try:
            payload = json.loads(result.result or 'null')
        except (ValueError, TypeError):
            continue
        if isinstance(payload, dict) and 'env' in payload and str(payload.get('user')) == str(user.pk):
            result.delete(using=using)


def publish_cleanup(cleanup_id, using='default'):
    from accounts.tasks import cleanup_deleted_account
    try:
        cleanup_deleted_account.apply_async(args=(cleanup_id, using), retry=False)
    except Exception:
        # The database record survives broker outages for the scheduled drain.
        logger.exception(
            'Could not queue account cleanup %s; scheduled recovery is required.', cleanup_id)


def missing_resource(error):
    return error.http_status == 404 and error.code == 'resource_missing'


def clean_external_resources(cleanup_id, using='default'):
    try:
        with transaction.atomic(using=using):
            job = AccountDeletionCleanup.objects.using(
                using).select_for_update().filter(pk=cleanup_id).first()
            if job is None:
                return
            customers = set(job.customer_ids)
            for subscription_id in job.subscription_ids:
                if Profile.objects.using(using).filter(subscription_id=subscription_id).exists() or BillingProvisioning.objects.using(using).filter(stripe_subscription_id=subscription_id).exists():
                    raise CleanupBlocked('StripeResourceStillReferenced')
                try:
                    subscription = stripe.Subscription.retrieve(
                        subscription_id, api_key=settings.STRIPE_SECRET_KEY)
                except stripe.error.InvalidRequestError as error:
                    if missing_resource(error):
                        continue
                    raise
                customer_id = subscription.get('customer')
                if not isinstance(customer_id, str) or not customer_id:
                    raise CleanupBlocked('MissingStripeCustomer')
                customers.add(customer_id)
            # Check every mapping before deleting any remote customer.
            if (Profile.objects.using(using).filter(customer_id__in=customers).exists()
                    or BillingProvisioning.objects.using(using).filter(stripe_customer_id__in=customers).exists()):
                raise CleanupBlocked('StripeResourceStillReferenced')
            for customer_id in sorted(customers):
                try:
                    response = stripe.Customer.delete(
                        customer_id, api_key=settings.STRIPE_SECRET_KEY)
                except stripe.error.InvalidRequestError as error:
                    if missing_resource(error):
                        continue
                    raise
                if response.get('deleted') is not True:
                    raise CleanupBlocked('StripeDeletionNotConfirmed')
            for name in job.media_names:
                if not Aircraft.objects.using(using).filter(image=name).exists():
                    default_storage.delete(name)
            job.delete(using=using)
    except Exception as error:
        # Keep only an exception class, never remote errors containing personal data.
        AccountDeletionCleanup.objects.using(using).filter(pk=cleanup_id).update(
            attempts=F('attempts') + 1, last_error=str(error) if isinstance(error, CleanupBlocked) else type(error).__name__,
            next_attempt_at=timezone.now() + timedelta(minutes=5))
        raise
