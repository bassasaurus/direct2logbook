"""Exercise deployment ordering/failures without contacting a server or broker."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from django.test import SimpleTestCase


SCRIPT = Path(__file__).resolve().parents[2] / 'deploy' / 'production.sh'
TARGET = 'a' * 40
PREVIOUS = 'b' * 40
SHIM = '''import json, os, sys
from pathlib import Path
name = Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['TRACE_PATH'], 'a') as trace:
    trace.write(json.dumps([name] + args) + '\\n')
command = ' '.join(args)
if os.environ.get('FAIL_COMMAND') == name + ' ' + command:
    sys.exit(1)
if name == 'git':
    if args[:1] == ['symbolic-ref']:
        print(os.environ.get('FAKE_BRANCH', 'master'))
    elif args[:1] == ['diff']:
        sys.exit(int(os.environ.get('FAKE_DIRTY', '0')))
    elif args[:1] == ['rev-parse']:
        print(os.environ.get('FAKE_MASTER', 'a' * 40) if args[1] == 'origin/master' else 'b' * 40)
elif name == 'uv' and args == ['--version']:
    print('uv 0.13.6')
elif name == 'sudo' and 'status' in args:
    print('logbook RUNNING pid 123, uptime 0:00:15\\ncelery RUNNING pid 456, uptime 0:00:15')
'''


class DeploymentScriptTests(SimpleTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.app = self.root / 'app'
        self.app.mkdir()
        self.trace = self.root / 'trace'
        for name in ('git', 'uv', 'app-python', 'sudo', 'flock', 'curl'):
            executable = self.bin / name
            executable.write_text('#!' + sys.executable + '\n' + SHIM)
            executable.chmod(0o700)
        self.env = {
            **os.environ,
            'PATH': str(self.bin) + os.pathsep + os.environ['PATH'],
            'TRACE_PATH': str(self.trace),
            'D2L_APP_DIR': str(self.app),
            'D2L_APP_PYTHON': str(self.bin / 'app-python'),
            'D2L_UV_BIN': str(self.bin / 'uv'),
            'D2L_DEPLOY_STATE_DIR': str(self.root / 'state'),
        }

    def run_deploy(self, target=TARGET, **changes):
        return subprocess.run(['bash', str(SCRIPT), target], env={**self.env, **changes},
                              capture_output=True, text=True, timeout=15)

    def commands(self):
        return [json.loads(line) for line in self.trace.read_text().splitlines()] if self.trace.exists() else []

    def test_success_backs_up_before_stopping_and_syncs_before_migration(self):
        result = self.run_deploy()
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = self.commands()
        backup = commands.index(['app-python', 'manage.py', 'backup_database'])
        stop = commands.index(['sudo', '-n', '/usr/bin/supervisorctl', 'stop', 'logbook', 'celery'])
        sync = next(i for i, c in enumerate(commands) if c[:3] == ['uv', 'pip', 'sync'])
        migrate = commands.index(['app-python', 'manage.py', 'migrate', '--noinput'])
        start = commands.index(['sudo', '-n', '/usr/bin/supervisorctl', 'start', 'logbook', 'celery'])
        self.assertLess(backup, stop)
        self.assertLess(stop, sync)
        self.assertLess(sync, migrate)
        self.assertLess(migrate, start)
        self.assertTrue(any(c[0] == 'curl' for c in commands))
        self.assertIn('deployed=' + TARGET, (self.root / 'state' / 'last-success').read_text())

    def test_invalid_revision_is_rejected_without_external_commands(self):
        self.assertNotEqual(self.run_deploy('master; unsafe').returncode, 0)
        self.assertEqual(self.commands(), [])

    def test_dirty_checkout_is_rejected_before_backup_or_service_changes(self):
        self.assertNotEqual(self.run_deploy(FAKE_DIRTY='1').returncode, 0)
        self.assertFalse(any(c[0] in ('sudo', 'app-python') for c in self.commands()))

    def test_stale_workflow_commit_cannot_deploy_over_new_master(self):
        self.assertNotEqual(self.run_deploy(FAKE_MASTER='c' * 40).returncode, 0)
        self.assertFalse(any(c[0] in ('sudo', 'app-python') for c in self.commands()))

    def test_failed_backup_does_not_stop_services_or_change_code(self):
        result = self.run_deploy(FAIL_COMMAND='app-python manage.py backup_database')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(c[0] == 'sudo' or c[:2] == ['git', 'merge'] for c in self.commands()))

    def test_failed_migration_leaves_services_stopped_and_no_success_marker(self):
        result = self.run_deploy(FAIL_COMMAND='app-python manage.py migrate --noinput')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any('start' in c or c[0] == 'curl' for c in self.commands()))
        self.assertFalse((self.root / 'state' / 'last-success').exists())
        self.assertIn(PREVIOUS, result.stderr)

    def test_failed_health_check_stops_services_again(self):
        # The fake curl command receives the same fixed arguments on every run.
        self.env['FAIL_COMMAND'] = 'curl --fail --silent --show-error --location --max-time 15 --retry 4 --retry-delay 3 --retry-connrefused --retry-all-errors https://direct2logbook.com/accounts/login/'
        self.assertNotEqual(self.run_deploy().returncode, 0)
        self.assertEqual(self.commands()[-1], ['sudo', '-n', '/usr/bin/supervisorctl', 'stop', 'logbook', 'celery'])
        self.assertFalse((self.root / 'state' / 'last-success').exists())
