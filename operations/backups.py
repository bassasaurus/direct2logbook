"""Export, encrypt/upload through rclone crypt, and download-verify PostgreSQL backups."""
import configparser
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import uuid

from django.conf import settings
from django.core.mail import send_mail
from django.db import connections

logger = logging.getLogger('django.operations.backups')


class BackupError(RuntimeError):
    pass


def _run(args, env=None, timeout=3600):
    try:
        result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BackupError(f'{Path(args[0]).name} could not finish.') from exc
    if result.returncode:
        # Never expose subprocess output: remote configuration or SQL may contain secrets.
        raise BackupError(f'{Path(args[0]).name} exited with status {result.returncode}.')
    return result.stdout


def _sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _configuration():
    remote = settings.DB_BACKUP_REMOTE
    if not re.fullmatch(r'[A-Za-z0-9_-]+:[A-Za-z0-9_/-]*', remote or ''):
        raise BackupError('Set DB_BACKUP_REMOTE to an encrypted rclone remote and optional subfolder.')
    if '..' in remote.split(':', 1)[1].split('/'):
        raise BackupError('Backup remote must not contain parent path segments.')
    config_path = Path(settings.DB_BACKUP_RCLONE_CONFIG).expanduser()
    if not settings.DB_BACKUP_RCLONE_CONFIG or not config_path.is_file():
        raise BackupError('Set DB_BACKUP_RCLONE_CONFIG to a private rclone config file.')
    if config_path.stat().st_uid != os.geteuid() or stat.S_IMODE(config_path.stat().st_mode) & 0o077:
        raise BackupError('The rclone config must belong to this user and have mode 600 or stricter.')
    config = configparser.ConfigParser(interpolation=None)
    try:
        config.read(config_path)
        section = config[remote.split(':', 1)[0]]
        upstream = section['remote'].split(':', 1)[0]
        if section['type'] != 'crypt' or config[upstream]['type'] not in ('drive', 'b2'):
            raise KeyError('Expected crypt over Backblaze B2 or Google Drive')
        if section.get('filename_encryption', 'standard') != 'standard':
            raise KeyError('Filename encryption must be standard')
        if not section.get('password'):
            raise KeyError('Encryption password is missing')
        if section.getboolean('no_data_encryption', fallback=False) or not section.getboolean('directory_name_encryption', fallback=True):
            raise KeyError('Data and directory encryption must be enabled')
    except (configparser.Error, KeyError, UnicodeError, ValueError):
        raise BackupError('Configure a crypt remote over Backblaze B2 or Google Drive with standard filename encryption.')
    if not settings.DB_BACKUP_STATE_DIR:
        raise BackupError('Set DB_BACKUP_STATE_DIR to a private directory outside the web/static/media roots.')
    state_dir = Path(settings.DB_BACKUP_STATE_DIR).expanduser().resolve()
    roots = [getattr(settings, name, '') for name in ('BASE_DIR', 'STATIC_ROOT', 'MEDIA_ROOT')]
    roots.extend(getattr(settings, 'STATICFILES_DIRS', []))
    if any(root and state_dir.is_relative_to(Path(root).resolve()) for root in roots if isinstance(root, (str, Path))):
        raise BackupError('Backup state must be outside the project, static, and media directories.')
    state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    if state_dir.stat().st_uid != os.geteuid() or stat.S_IMODE(state_dir.stat().st_mode) & 0o077:
        raise BackupError('The backup state directory must belong to this user and have mode 700.')
    if not settings.DB_BACKUP_ALERT_EMAIL:
        raise BackupError('Set DB_BACKUP_ALERT_EMAIL so backup failures can be reported.')
    tools = {name: shutil.which(name) for name in ('pg_dump', 'pg_restore', 'rclone')}
    if not all(tools.values()):
        raise BackupError('Install pg_dump, pg_restore, and rclone before enabling backups.')
    return remote.rstrip('/'), config_path, state_dir, tools


@contextmanager
def _lock(folder):
    fd = os.open(folder / 'backup.lock', os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise BackupError('Another database backup is already running.')
        yield
    finally:
        os.close(fd)


def _save_state(folder, payload):
    with tempfile.NamedTemporaryFile(mode='w', dir=folder, delete=False) as handle:
        json.dump(payload, handle, indent=2)
        temporary = Path(handle.name)
    os.replace(temporary, folder / 'last-success.json')


def run_database_backup():
    remote, config, folder, tools = _configuration()
    database = connections['default']
    if database.vendor != 'postgresql':
        raise BackupError('Database backups require PostgreSQL.')
    params = database.get_connection_params()
    env = os.environ.copy()
    # Libpq environment avoids putting a password or DATABASE_URL in process arguments.
    for key, value in [('PGHOST', params.get('host', '')), ('PGPORT', params.get('port', '5432')),
                       ('PGUSER', params.get('user', '')), ('PGPASSWORD', params.get('password', '')),
                       ('PGDATABASE', params['dbname'])]:
        env[key] = str(value)
    for parameter, variable in [('sslmode', 'PGSSLMODE'), ('sslrootcert', 'PGSSLROOTCERT'),
                                 ('sslcert', 'PGSSLCERT'), ('sslkey', 'PGSSLKEY'),
                                 ('sslcrl', 'PGSSLCRL'), ('options', 'PGOPTIONS')]:
        if params.get(parameter):
            env[variable] = str(params[parameter])
    now = datetime.now(timezone.utc)
    run_id = now.strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex
    destination = remote + ('/' if not remote.endswith(':') else '') + run_id
    with _lock(folder), tempfile.TemporaryDirectory(prefix='backup-', dir=folder) as directory:
        work = Path(directory)
        archive, downloaded = work / 'database.dump', work / 'downloaded.dump'
        version = _run([tools['pg_dump'], '--version'], timeout=30).strip()
        previous_umask = os.umask(0o077)
        try:
            _run([tools['pg_dump'], '--format=custom', '--file=' + str(archive)], env=env)
        finally:
            os.umask(previous_umask)
        if not archive.is_file() or archive.stat().st_size == 0:
            raise BackupError('pg_dump did not create a nonempty archive.')
        _run([tools['pg_restore'], '--list', str(archive)], timeout=120)
        digest = _sha256(archive)
        rclone = [tools['rclone'], '--config', str(config), '--immutable', '--retries', '3', '--contimeout', '15s', '--timeout', '5m']
        _run(rclone + ['copyto', str(archive), destination + '/database.dump'])
        _run(rclone + ['copyto', destination + '/database.dump', str(downloaded)])
        if not downloaded.is_file() or _sha256(downloaded) != digest:
            raise BackupError('Downloaded backup does not match the original archive.')
        _run([tools['pg_restore'], '--list', str(downloaded)], timeout=120)
        manifest = {'created_at': now.isoformat(), 'verified_at': datetime.now(timezone.utc).isoformat(),
                    'run_id': run_id, 'bytes': archive.stat().st_size, 'sha256': digest,
                    'pg_dump_version': version, 'verification': 'downloaded-and-hash-matched'}
        manifest_file = work / 'manifest.json'
        manifest_file.write_text(json.dumps(manifest, indent=2))
        _run(rclone + ['copyto', str(manifest_file), destination + '/manifest.json'])
        _save_state(folder, dict(manifest, remote=destination))
    return dict(manifest, remote=destination)


def alert_failure(message):
    if not settings.DB_BACKUP_ALERT_EMAIL:
        return
    try:
        send_mail('[Direct2Logbook] Database backup failed',
                  'The off-server database backup did not complete successfully.\n' + message,
                  settings.DEFAULT_FROM_EMAIL, [settings.DB_BACKUP_ALERT_EMAIL], fail_silently=False)
    except Exception:
        logger.error('Backup failure email could not be sent. Inspect the backup cron log.')


def check_database_backups(max_age_hours=26):
    remote, config, folder, tools = _configuration()
    try:
        status = json.loads((folder / 'last-success.json').read_text())
        verified_at = datetime.fromisoformat(status['verified_at'])
        if verified_at.tzinfo is None:
            raise ValueError('Timestamp must be timezone-aware')
        age = (datetime.now(timezone.utc) - verified_at).total_seconds()
        expected_prefix = remote + ('/' if not remote.endswith(':') else '')
        if not status['remote'].startswith(expected_prefix):
            raise ValueError('Backup location does not match configuration')
    except (OSError, ValueError, KeyError, TypeError):
        raise BackupError('No readable verified backup record exists. Run backup_database first.')
    if age < -300 or age > max_age_hours * 3600:
        raise BackupError(f'No verified database backup within {max_age_hours} hours.')
    output = _run([tools['rclone'], '--config', str(config), '--contimeout', '15s', '--timeout', '60s',
                   'lsjson', status['remote'], '--files-only'], timeout=120)
    try:
        files = {entry['Name']: entry['Size'] for entry in json.loads(output)}
        if files.get('database.dump') != status['bytes'] or 'manifest.json' not in files:
            raise ValueError('Missing or unexpected backup files')
    except (ValueError, KeyError, TypeError):
        raise BackupError('The verified backup is missing or has an unexpected size on Google Drive.')
    return status
