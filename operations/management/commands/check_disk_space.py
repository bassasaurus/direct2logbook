"""Check the server root filesystem without relying on PostgreSQL or Celery."""
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import stat
import tempfile

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Email at 80% root filesystem use; remind daily and email on recovery. Run hourly.'

    def add_arguments(self, parser):
        parser.add_argument('--send-test', action='store_true', help='Send a test email without changing alert state.')

    def handle(self, *args, **options):
        try:
            self.check(send_test=options['send_test'])
        except CommandError:
            raise
        except Exception:
            raise CommandError('Disk monitor could not finish. Check filesystem permissions and email configuration.') from None

    def check(self, send_test=False):
        recipient = settings.DISK_ALERT_EMAIL
        state_dir = settings.DISK_ALERT_STATE_DIR
        if not recipient or not state_dir:
            raise CommandError('Set DISK_ALERT_EMAIL and DISK_ALERT_STATE_DIR, or the existing backup email/state settings.')
        folder = Path(state_dir).expanduser().resolve()
        roots = [settings.BASE_DIR, getattr(settings, 'STATIC_ROOT', ''), getattr(settings, 'MEDIA_ROOT', '')]
        roots.extend(getattr(settings, 'STATICFILES_DIRS', []))
        if any(root and folder.is_relative_to(Path(root).resolve()) for root in roots):
            raise CommandError('Disk alert state must be outside the project, static and media directories.')
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        if folder.stat().st_uid != os.geteuid() or stat.S_IMODE(folder.stat().st_mode) & 0o077:
            raise CommandError('Disk alert state directory must belong to this user and have mode 700.')
        with (folder / 'monitor.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise CommandError('Another disk check is already running.')
            usage = os.statvfs('/')
            used = usage.f_blocks - usage.f_bfree
            available = max(0, usage.f_bavail)
            if used < 0 or used + available <= 0:
                raise CommandError('Could not determine root filesystem capacity.')
            percent = 100 * used / (used + available)
            free_gib = available * usage.f_frsize / 1024 ** 3
            detail = f'Root filesystem (/): {percent:.1f}% used; {free_gib:.2f} GiB available.'
            state_file = folder / 'state.json'
            now = datetime.now(timezone.utc)
            if send_test:
                self.notify('TEST disk-space notification', detail, recipient)
                self.stdout.write('Test email submitted. ' + detail)
                return
            previous = json.loads(state_file.read_text()) if state_file.exists() else {}
            alerted_at = datetime.fromisoformat(previous['alerted_at']) if previous.get('alerted_at') else None
            if alerted_at and (alerted_at.tzinfo is None or alerted_at > now):
                raise CommandError('Disk alert state has an invalid timestamp.')
            if percent >= 80:
                if not alerted_at or (now - alerted_at).total_seconds() >= 86400:
                    self.notify('Disk space warning', detail + '\nUsage has reached the 80% alert threshold. Investigate disk growth.', recipient)
                    self.save_state(folder, {'alerted_at': now.isoformat()})
                    self.stdout.write('Warning email submitted. ' + detail)
                else:
                    self.stdout.write('Warning already reported; reminder limited to once per 24 hours. ' + detail)
                raise CommandError('Root filesystem usage is at or above 80%.')
            # Hysteresis prevents repeated warning/recovery emails near 80%.
            if alerted_at and percent < 75:
                self.notify('Disk space recovered', detail + '\nUsage is below the 75% recovery threshold.', recipient)
                self.save_state(folder, {})
                self.stdout.write('Recovery email submitted. ' + detail)
            else:
                self.stdout.write('No email needed. ' + detail)

    def notify(self, subject, body, recipient):
        sent = send_mail('[Direct2Logbook] ' + subject, body,
                         settings.DEFAULT_FROM_EMAIL, [recipient], fail_silently=False)
        if sent != 1:
            raise CommandError('Mail backend did not submit the disk notification.')

    def save_state(self, folder, data):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', dir=folder, delete=False) as handle:
                temporary = Path(handle.name)
                json.dump(data, handle)
            os.replace(temporary, folder / 'state.json')
        finally:
            if temporary and temporary.exists():
                temporary.unlink()
