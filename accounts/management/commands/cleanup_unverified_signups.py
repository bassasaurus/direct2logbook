from datetime import timedelta

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from api.models import MobileSyncReceipt
from csv_app.models import CSVImportBatch
from flights.models import Aircraft, Flight, Imported, TailNumber
from payments.models import BillingProvisioning
from pdf_output.models import PDFRequest
from profile.models import Profile, Reminder
from signature.models import Signature


def candidates(cutoff):
    users = get_user_model().objects.filter(
        date_joined__lt=cutoff, last_login__isnull=True,
        is_staff=False, is_superuser=False,
    )
    # Default profiles and zero-valued summaries are created at signup. Preserve
    # any account with actual logbook activity or any billing relationship.
    protected = [
        EmailAddress.objects.filter(user_id=OuterRef('pk'), verified=True),
        Profile.objects.filter(user_id=OuterRef('pk')).filter(active=True),
        Profile.objects.filter(user_id=OuterRef('pk')).filter(free_access=True),
        Profile.objects.filter(user_id=OuterRef('pk')).exclude(customer_id=''),
        Profile.objects.filter(user_id=OuterRef('pk')).exclude(subscription_id=''),
        BillingProvisioning.objects.filter(user_id=OuterRef('pk')),
        Signature.objects.filter(user_id=OuterRef('pk')).exclude(signature=None).exclude(signature=''),
    ]
    protected.extend(model.objects.filter(user_id=OuterRef('pk')) for model in (
        Aircraft, Flight, Imported, TailNumber, Reminder,
        CSVImportBatch, PDFRequest, MobileSyncReceipt,
    ))
    for query in protected:
        users = users.filter(~Exists(query))
    return users


class Command(BaseCommand):
    help = 'Remove abandoned, never-verified signups older than seven days; preserve established accounts.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=7, help='Grace period in days (minimum 7).')
        parser.add_argument('--limit', type=int, default=100, help='Maximum accounts per run.')
        parser.add_argument('--dry-run', action='store_true', help='Count candidates without deleting anything.')

    def handle(self, *args, **options):
        if options['days'] < 7 or options['limit'] < 1:
            raise CommandError('Use at least 7 days and a positive limit.')
        cutoff = timezone.now() - timedelta(days=options['days'])
        ids = list(candidates(cutoff).order_by('pk').values_list('pk', flat=True)[:options['limit']])
        if options['dry_run']:
            self.stdout.write(f'Would remove {len(ids)} unverified signup(s) older than {options["days"]} days. No changes made.')
            return
        deleted = skipped = 0
        for user_id in ids:
            try:
                with transaction.atomic():
                    user = get_user_model().objects.select_for_update().filter(pk=user_id).first()
                    # Recheck after locking: a user may have verified or started
                    # using the account since the initial candidate scan.
                    if user is None or not candidates(cutoff).filter(pk=user_id).exists():
                        skipped += 1
                        continue
                    # Use the existing deletion hooks for tokens, confirmations,
                    # sessions and owned rows; never bypass them with raw SQL.
                    user.delete()
                    deleted += 1
            except ProtectedError:
                skipped += 1
        self.stdout.write(f'Removed {deleted} unverified signup(s); skipped {skipped}. Grace period: {options["days"]} days.')
