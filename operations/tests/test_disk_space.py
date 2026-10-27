from datetime import datetime, timedelta, timezone
from io import StringIO
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

MODULE = 'operations.management.commands.check_disk_space'


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', DISK_ALERT_EMAIL='admin@example.com')
class DiskSpaceTests(SimpleTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name) / 'private-state'
        settings = override_settings(DISK_ALERT_STATE_DIR=str(self.folder))
        settings.enable()
        self.addCleanup(settings.disable)
        patcher = patch(MODULE + '.os.statvfs')
        self.usage = patcher.start()
        self.addCleanup(patcher.stop)
        self.set_usage(50)
        self.output = StringIO()

    def set_usage(self, percent):
        self.usage.return_value = SimpleNamespace(f_blocks=100, f_bfree=100-percent,
                                                 f_bavail=100-percent, f_frsize=1024**3)

    def run_check(self, **options):
        call_command('check_disk_space', stdout=self.output, **options)

    def warning(self):
        with self.assertRaisesMessage(CommandError, 'at or above 80%'):
            self.run_check()

    def test_healthy_capacity_sends_no_email(self):
        self.run_check()
        self.assertEqual(len(mail.outbox), 0)
        self.assertIn('50.0%', self.output.getvalue())

    def test_exact_threshold_emails_once_and_reminds_after_24_hours(self):
        self.set_usage(80)
        self.warning()
        self.warning()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['admin@example.com'])
        self.assertEqual((self.folder / 'state.json').stat().st_mode & 0o777, 0o600)
        state = self.folder / 'state.json'
        state.write_text(json.dumps({'alerted_at': (datetime.now(timezone.utc)-timedelta(hours=25)).isoformat()}))
        self.warning()
        self.assertEqual(len(mail.outbox), 2)

    def test_recovery_hysteresis_and_later_incident(self):
        self.set_usage(85)
        self.warning()
        self.set_usage(79)
        self.run_check()
        self.assertEqual(len(mail.outbox), 1)
        self.set_usage(74)
        self.run_check()
        self.run_check()
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn('recovered', mail.outbox[1].subject)
        self.set_usage(81)
        self.warning()
        self.assertEqual(len(mail.outbox), 3)

    def test_failed_mail_does_not_suppress_next_attempt(self):
        self.set_usage(90)
        with patch(MODULE + '.send_mail', return_value=0):
            with self.assertRaises(CommandError):
                self.run_check()
        self.assertFalse((self.folder / 'state.json').exists())
        self.warning()
        self.assertEqual(len(mail.outbox), 1)

    def test_test_email_does_not_change_incident_state(self):
        self.run_check(send_test=True)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('TEST', mail.outbox[0].subject)
        self.assertFalse((self.folder / 'state.json').exists())

    def test_reserved_blocks_are_excluded_like_df(self):
        self.usage.return_value = SimpleNamespace(f_blocks=110, f_bfree=30, f_bavail=20, f_frsize=4096)
        self.warning()
        self.assertIn('80.0%', mail.outbox[0].body)

    def test_corrupt_state_is_not_silently_reset(self):
        self.folder.mkdir(mode=0o700)
        (self.folder / 'state.json').write_text('invalid')
        with self.assertRaises(CommandError):
            self.run_check()
        self.assertEqual(len(mail.outbox), 0)
