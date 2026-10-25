import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from pdf_output.models import PDFRequest


logger = logging.getLogger('django.pdf_output')


class Command(BaseCommand):
    help = 'Close PDF requests with no progress for 15 minutes; never requeue or resend email.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Report stale counts without changing requests.')

    def handle(self, *args, **options):
        now = timezone.now()
        cutoff = now - timedelta(minutes=15)
        # Each attempt's hard limit is 11 minutes. Even if a worker survives
        # that limit, its conditional send transition prevents a late email.
        pre_send = PDFRequest.objects.filter(
            updated_at__lt=cutoff,
            status__in=[PDFRequest.Status.QUEUED, PDFRequest.Status.UNCONFIRMED,
                        PDFRequest.Status.PROCESSING, PDFRequest.Status.RETRYING],
        )
        sending = PDFRequest.objects.filter(
            updated_at__lt=cutoff, status=PDFRequest.Status.SENDING,
        )
        if options['dry_run']:
            self.stdout.write(f'Stale before sending: {pre_send.count()}; stale sending: {sending.count()}. No changes made.')
            return
        # Predicates are rechecked in each UPDATE: a worker that advanced in
        # the meantime is not accidentally overwritten. Repeated runs are safe.
        failed = pre_send.update(status=PDFRequest.Status.FAILED, updated_at=now)
        uncertain = sending.update(status=PDFRequest.Status.UNCERTAIN, updated_at=now)
        if failed or uncertain:
            logger.warning('Closed stale PDF requests: failed=%s delivery_uncertain=%s', failed, uncertain)
        self.stdout.write(f'Closed stale PDF requests: failed={failed}, delivery_uncertain={uncertain}. No jobs requeued.')
