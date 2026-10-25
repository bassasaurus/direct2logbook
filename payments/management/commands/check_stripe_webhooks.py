from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from payments.models import StripeWebhookEvent, StripeWebhookFailure


class Command(BaseCommand):
    help = 'Email unresolved Stripe webhook failures (run every five minutes).'

    def handle(self, *args, **options):
        recipient = settings.STRIPE_WEBHOOK_ALERT_EMAIL
        if not recipient:
            raise CommandError('Set STRIPE_WEBHOOK_ALERT_EMAIL before scheduling this command.')
        now = timezone.now()
        # Lock rows through sending so overlapping invocations cannot send the same alert.
        with transaction.atomic():
            failures = list(
                StripeWebhookFailure.objects.select_for_update()
                .exclude(event_id__in=StripeWebhookEvent.objects.values('event_id'))
                .filter(Q(attempts__gte=3) | Q(first_failed_at__lte=now - timedelta(minutes=15)))
                .filter(Q(last_alerted_at=None) | Q(last_alerted_at__lte=now - timedelta(hours=1)))
                .order_by('first_failed_at')[:100]
            )
            if not failures:
                self.stdout.write('No webhook failures need an alert.')
                return
            lines = [
                'Stripe webhook events remain unresolved in Direct2Logbook.',
                'Review Stripe Workbench event deliveries and the Django server logs.',
                'After fixing the cause, resend the event from Stripe.',
                '',
            ]
            lines.extend(
                f'{failure.event_id} | {failure.event_type} | attempts={failure.attempts} | '
                f'first_failed={failure.first_failed_at.isoformat()} | '
                f'last_failed={failure.last_failed_at.isoformat()}'
                for failure in failures
            )
            sent = send_mail(
                '[Direct2Logbook] Unresolved Stripe webhook failures',
                '\n'.join(lines), settings.DEFAULT_FROM_EMAIL, [recipient],
                fail_silently=False,
            )
            if sent != 1:
                raise CommandError('Alert email was not sent; failures remain eligible for retry.')
            StripeWebhookFailure.objects.filter(pk__in=[f.pk for f in failures]).update(
                last_alerted_at=now,
            )
        self.stdout.write(f'Alert sent for {len(failures)} unresolved event(s).')
