"""Download a verified cloud archive and promote a checked, isolated local restore."""
import configparser
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import uuid

from django.conf import settings
import psycopg2
from psycopg2 import sql

from operations.backups import BackupError, _run, _sha256
from operations.local_database import LOCAL_PREFIX

RUN_ID = re.compile(r'\d{8}T\d{6}Z-[0-9a-f]{32}')


def _private(path, mode, description):
    if path.stat().st_uid != os.geteuid() or stat.S_IMODE(path.stat().st_mode) & (0o777 ^ mode):
        raise BackupError(f'{description} must belong to this user and have mode {mode:o} or stricter.')


def _configuration():
    database = settings.DATABASES['default']
    if not (getattr(settings, 'LOCAL_RESTORE_MODE', False) and settings.DEBUG
            and settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend'
            and settings.STRIPE_SECRET_KEY.startswith('sk_test_')
            and settings.STRIPE_PUBLISHABLE_KEY.startswith('pk_test_')):
        raise BackupError('restore_local_backup is local-only. Activate logbook.settings_local_restore before using this command.')
    # Revalidate the connection even if another settings module copied the flag.
    if database.get('ENGINE') != 'django.db.backends.postgresql' or database.get('HOST') not in ('localhost', '127.0.0.1', '::1'):
        raise BackupError('The restore destination must be a loopback PostgreSQL server.')
    name = database.get('NAME', '')
    if not re.fullmatch(r'd2l_local_[a-z0-9_]{1,40}', name):
        raise BackupError('Restore database names must begin with d2l_local_.')
    if database.get('OPTIONS'):
        raise BackupError('Local restore database connection options must be empty.')
    remote = settings.LOCAL_RESTORE_BACKUP_REMOTE.rstrip('/')
    if not re.fullmatch(r'[A-Za-z0-9_-]+:[A-Za-z0-9_/-]+', remote):
        raise BackupError('Set LOCAL_RESTORE_BACKUP_REMOTE to the crypt remote and backup subfolder.')
    if '..' in remote.split(':', 1)[1].split('/'):
        raise BackupError('The backup remote cannot contain parent path segments.')
    config_path = Path(settings.LOCAL_RESTORE_RCLONE_CONFIG).expanduser()
    if not config_path.is_file():
        raise BackupError('Backup rclone configuration not found. Set LOCAL_RESTORE_RCLONE_CONFIG to your private backup config.')
    _private(config_path, 0o600, 'The rclone config')
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(config_path)
        crypt = parser[remote.split(':', 1)[0]]
        upstream = parser[crypt['remote'].split(':', 1)[0]]
        if (crypt['type'] != 'crypt' or upstream['type'] not in ('b2', 'drive')
                or crypt.get('filename_encryption', 'standard') != 'standard'
                or not crypt.get('password') or crypt.getboolean('no_data_encryption', fallback=False)
                or not crypt.getboolean('directory_name_encryption', fallback=True)):
            raise ValueError()
    except (configparser.Error, KeyError, ValueError, UnicodeError):
        raise BackupError('Use the existing encrypted backup remote: crypt over B2/Drive, with data and filename encryption enabled.') from None
    folder = Path(settings.LOCAL_RESTORE_STATE_DIR).expanduser().resolve()
    roots = [getattr(settings, key, '') for key in ('BASE_DIR', 'STATIC_ROOT', 'MEDIA_ROOT')]
    if any(root and folder.is_relative_to(Path(root).resolve()) for root in roots):
        raise BackupError('Local restore state must be outside the project, static and media roots.')
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    _private(folder, 0o700, 'The local restore state directory')
    tools = {key: shutil.which(key) for key in ('rclone', 'pg_restore')}
    if not all(tools.values()):
        raise BackupError('Install rclone and pg_restore before restoring a backup.')
    return database, remote, config_path, folder, tools


@contextmanager
def _lock(folder):
    fd = os.open(folder / 'restore.lock', os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise BackupError('Another local restore is already running.') from None
        yield
    finally:
        os.close(fd)


def validate_manifest(manifest, run_id, now=None):
    try:
        now = now or datetime.now(timezone.utc)
        created = datetime.fromisoformat(manifest['created_at'])
        verified = datetime.fromisoformat(manifest['verified_at'])
        if (not RUN_ID.fullmatch(run_id) or manifest['run_id'] != run_id
                or created.tzinfo is None or verified.tzinfo is None
                or created > verified or (verified - now).total_seconds() > 300
                or created.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ') != run_id[:16]
                or manifest['verification'] != 'downloaded-and-hash-matched'
                or type(manifest['bytes']) is not int or manifest['bytes'] <= 0
                or not re.fullmatch(r'[0-9a-f]{64}', manifest['sha256'])):
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise BackupError('The backup verification manifest is invalid. No database was changed.') from None
    return manifest


def latest_verified(command, remote):
    """Ignore incomplete runs; refuse a corrupt completed run rather than hide it."""
    try:
        directories = json.loads(_run(command + ['lsjson', remote, '--dirs-only'], timeout=120))
        names = [item['Name'] for item in directories if RUN_ID.fullmatch(item['Name'])]
        if len(names) != len(set(names)):
            raise ValueError()
        for name in sorted(names, reverse=True):
            destination = remote + '/' + name
            files = json.loads(_run(command + ['lsjson', destination, '--files-only'], timeout=120))
            sizes = {item['Name']: item['Size'] for item in files}
            if 'manifest.json' not in sizes:
                continue  # Upload was never verified; it is not eligible.
            manifest = validate_manifest(json.loads(_run(command + ['cat', destination + '/manifest.json'], timeout=120)), name)
            if sizes.get('database.dump') != manifest['bytes']:
                raise BackupError('The latest verified backup archive is missing or has an unexpected size.')
            return destination, manifest
    except (KeyError, TypeError, ValueError):
        raise BackupError('The remote backup inventory is invalid. No database was changed.') from None
    raise BackupError('No completed, verified backup was found.')


def _connection(database, name):
    host = database['HOST']
    host = '127.0.0.1' if host == 'localhost' else host
    connection = psycopg2.connect(dbname=name, host=host, hostaddr=host,
                                port=database.get('PORT') or 5432,
                                user=database.get('USER') or '', password=database.get('PASSWORD') or '',
                                sslmode='disable', options='', connect_timeout=5,
                                application_name='direct2logbook-local-restore')
    connection.autocommit = True
    return connection


def _exists(cursor, name):
    cursor.execute('SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname = %s)', [name])
    return cursor.fetchone()[0]


def _restore_environment(database, name):
    # Do not inherit PGHOSTADDR/PGSERVICE/PGOPTIONS or any other libpq overrides.
    env = {key: value for key, value in os.environ.items() if not key.startswith('PG')}
    env.update(PGHOST='127.0.0.1' if database['HOST'] == 'localhost' else database['HOST'],
               PGPORT=str(database.get('PORT') or 5432), PGUSER=database.get('USER') or '',
               PGPASSWORD=database.get('PASSWORD') or '', PGDATABASE=name,
               PGSSLMODE='disable', PGCONNECT_TIMEOUT='5')
    return env


def verify_restored_database(database, name):
    connection = _connection(database, name)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")
            tables = [row[0] for row in cursor.fetchall()]
            if not {'auth_user', 'flights_flight', 'django_migrations'}.issubset(tables):
                raise BackupError('The restored database is missing required application tables.')
            counts = {}
            for table in tables:
                cursor.execute(sql.SQL('SELECT COUNT(*) FROM {}.{}').format(sql.Identifier('public'), sql.Identifier(table)))
                counts[table] = cursor.fetchone()[0]
            cursor.execute('SELECT COUNT(*) FROM pg_constraint WHERE NOT convalidated')
            if cursor.fetchone()[0]:
                raise BackupError('The restored database contains unvalidated constraints. The previous copy was not replaced.')
            return counts
    finally:
        connection.close()


def _promote(cursor, stage, target, replace):
    previous = None
    if _exists(cursor, target):
        if not replace:
            raise BackupError('The local copy already exists. Use --replace after stopping its server and worker.')
        cursor.execute(sql.SQL('ALTER DATABASE {} WITH ALLOW_CONNECTIONS false').format(sql.Identifier(target)))
        try:
            cursor.execute('SELECT COUNT(*) FROM pg_stat_activity WHERE datname = %s', [target])
            if cursor.fetchone()[0]:
                raise BackupError('Stop the local-copy Django server, worker and database sessions before replacing it.')
            previous = LOCAL_PREFIX + 'previous_' + uuid.uuid4().hex[:16]
            cursor.execute(sql.SQL('ALTER DATABASE {} RENAME TO {}').format(sql.Identifier(target), sql.Identifier(previous)))
        except Exception:
            cursor.execute(sql.SQL('ALTER DATABASE {} WITH ALLOW_CONNECTIONS true').format(sql.Identifier(target)))
            raise
    try:
        cursor.execute(sql.SQL('ALTER DATABASE {} RENAME TO {}').format(sql.Identifier(stage), sql.Identifier(target)))
    except Exception:
        if previous:
            cursor.execute(sql.SQL('ALTER DATABASE {} RENAME TO {}').format(sql.Identifier(previous), sql.Identifier(target)))
            cursor.execute(sql.SQL('ALTER DATABASE {} WITH ALLOW_CONNECTIONS true').format(sql.Identifier(target)))
        raise
    return previous


def restore_local_backup(*, apply=False, replace=False, progress=lambda message: None):
    database, remote, config, folder, tools = _configuration()
    command = [tools['rclone'], '--config', str(config), '--retries', '3', '--contimeout', '15s', '--timeout', '5m']
    with _lock(folder), tempfile.TemporaryDirectory(prefix='download-', dir=folder) as directory:
        progress('Finding the newest completed, verified backup…')
        destination, manifest = latest_verified(command, remote)
        archive = Path(directory) / 'database.dump'
        progress(f"Downloading {manifest['run_id']} ({manifest['bytes']:,} bytes)…")
        _run(command + ['copyto', destination + '/database.dump', str(archive)])
        archive.chmod(0o600)
        if archive.stat().st_size != manifest['bytes'] or _sha256(archive) != manifest['sha256']:
            raise BackupError('Downloaded backup size or SHA-256 does not match its manifest. No database was changed.')
        _run([tools['pg_restore'], '--list', str(archive)], timeout=120)
        result = {'backup': destination, 'verified_at': manifest['verified_at'], 'sha256': manifest['sha256'],
                  'database': database['NAME'], 'applied': False}
        if not apply:
            return result
        connection = None
        stage = LOCAL_PREFIX + 'stage_' + uuid.uuid4().hex[:16]
        stage_created = False
        try:
            connection = _connection(database, 'postgres')
            with connection.cursor() as cursor:
                cursor.execute('SELECT inet_server_addr()')
                address = cursor.fetchone()[0]
                if not address or not ipaddress.ip_address(address).is_loopback:
                    raise BackupError('The restore connection did not reach a loopback PostgreSQL server.')
                if _exists(cursor, database['NAME']) and not replace:
                    raise BackupError('The local copy already exists. Use --replace after stopping its server and worker.')
                cursor.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(stage)))
                stage_created = True
                progress('Restoring into a new isolated local database…')
                _run([tools['pg_restore'], '--exit-on-error', '--single-transaction', '--no-owner',
                      '--no-privileges', '--no-tablespaces', '--dbname=' + stage, str(archive)],
                     env=_restore_environment(database, stage))
                progress('Checking tables, record counts and constraints…')
                result['table_counts'] = verify_restored_database(database, stage)
                previous = _promote(cursor, stage, database['NAME'], replace)
                stage_created = False
                result.update(applied=True, previous_database=previous, restored_at=datetime.now(timezone.utc).isoformat())
        except psycopg2.Error:
            raise BackupError('Local PostgreSQL restore could not finish. Check that PostgreSQL is running, the role can create databases, and the local copy has no open sessions. No production database is targeted.') from None
        finally:
            if connection:
                try:
                    if stage_created:
                        with connection.cursor() as cursor:
                            cursor.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(stage)))
                finally:
                    connection.close()
        with tempfile.NamedTemporaryFile(mode='w', dir=folder, delete=False) as report:
            json.dump(result, report, indent=2)
            temporary = Path(report.name)
        os.replace(temporary, folder / 'last-restore.json')
        return result
