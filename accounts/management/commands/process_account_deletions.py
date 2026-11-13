from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from accounts.deletion import clean_external_resources
from accounts.models import AccountDeletionCleanup


class Command(BaseCommand):
    help = 'Retry pending Stripe and uploaded-file cleanup after account deletion.'

    def handle(self, *args, **options):
        ids = list(AccountDeletionCleanup.objects.filter(next_attempt_at__lte=timezone.now()).order_by(
            'created_at').values_list('pk', flat=True)[:100])
        failed = 0
        for cleanup_id in ids:
            try:
                clean_external_resources(cleanup_id)
            except Exception:
                failed += 1
        self.stdout.write(f'Account cleanup: completed={
                          len(ids) - failed}, pending retries={failed}.')
        if failed:
            raise CommandError(
                'Account cleanup remains pending. Inspect AccountDeletionCleanup and retry after resolving the error.')
