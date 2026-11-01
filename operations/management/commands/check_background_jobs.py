from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from operations.job_monitoring import problem_jobs
from operations.models import BackgroundJobMonitor


class Command(BaseCommand):
    help = 'Email a digest of failed or stalled PDF, CSV and trial jobs; never retry jobs.'

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group()
        group.add_argument('--dry-run', action='store_true', help='Report problems without email or state changes.')
        group.add_argument('--send-test', action='store_true', help='Send a clearly labelled test email without changing alert state.')

    def notify(self, subject, body):
        try:
            sent = send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
                             [settings.BACKGROUND_JOB_ALERT_EMAIL], fail_silently=False)
        except Exception:
            raise CommandError('Background-job alert email failed; cooldown was not advanced.') from None
        if sent != 1:
            raise CommandError('Background-job alert email was not sent; cooldown was not advanced.')

    def handle(self, *args, **options):
        if options['dry_run']:
            problems = problem_jobs(timezone.now())
            for count, detail in problems:
                self.stdout.write(detail)
            self.stdout.write(f'Unresolved jobs: {sum(count for count, detail in problems)}. No email or state changes.')
            return
        if not settings.BACKGROUND_JOB_ALERT_EMAIL:
            raise CommandError('Set BACKGROUND_JOB_ALERT_EMAIL before scheduling this command.')
        if options['send_test']:
            self.notify('[Direct2Logbook] Background-job monitor test',
                        'This is a test of background-job alert email delivery. No jobs were changed.')
            self.stdout.write('Background-job monitor test email sent. Confirm receipt in your inbox.')
            return
        with transaction.atomic():
            BackgroundJobMonitor.objects.get_or_create(name='background-jobs')
            monitor = BackgroundJobMonitor.objects.select_for_update().get(name='background-jobs')
            now = timezone.now()
            problems = problem_jobs(now)
            if not problems:
                self.stdout.write('No background jobs need an alert.')
                return
            if monitor.last_alerted_at and monitor.last_alerted_at > now - timedelta(hours=1):
                self.stdout.write('Background-job problems remain; hourly email cooldown is active.')
                return
            count = sum(count for count, detail in problems)
            body = '\n\n'.join([
                'Direct2Logbook background jobs need review. No jobs were retried or changed.',
                *[detail for count, detail in problems],
                'Review server logs and the stored request before taking action. For PDF delivery '
                'uncertainty, check delivery before resending. For trials, inspect billing provisioning '
                'and reconcile Stripe state before recovery. Do not blindly replay jobs.',
                'PDF/CSV failures are included for 24 hours; delivery uncertainty and unresolved '
                'billing failures remain eligible. Unchanged problems repeat at most hourly.',
            ])
            self.notify('[Direct2Logbook] Background jobs need attention', body)
            monitor.last_alerted_at = now
            monitor.save(update_fields=['last_alerted_at'])
        self.stdout.write(f'Background-job alert sent for {count} unresolved job(s). No jobs changed.')
