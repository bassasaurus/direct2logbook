#!/usr/bin/env python3
"""Run local-copy commands with console mail, Stripe test mode and a local queue."""
import os
from pathlib import Path
import sys


def main():
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root))
    os.chdir(root)
    if any(arg == '--settings' or arg.startswith('--settings=') for arg in sys.argv[1:]):
        raise SystemExit('This wrapper always uses logbook.settings_local_restore; omit --settings.')
    os.environ['DJANGO_SETTINGS_MODULE'] = 'logbook.settings_local_restore'
    args = sys.argv[1:] or ['help']
    if args[0] == 'restore':
        args[0] = 'restore_local_backup'
    if args[0] == 'worker':
        os.execv(sys.executable, [sys.executable, '-m', 'celery', '-A', 'logbook',
                                 'worker', '-l', 'info', '--concurrency=1', '--without-gossip', '--without-mingle', *args[1:]])
    from django.core.management import execute_from_command_line
    execute_from_command_line([str(root / 'manage.py'), *args])


if __name__ == '__main__':
    main()
