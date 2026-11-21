# Refresh a local database from the latest verified production backup

This opt-in workflow preserves the full database: users, emails, flight history,
tokens, billing identifiers, reminders and all other rows. It does not anonymize,
truncate, recalculate, migrate or update production records. Production backups
are only read; this workflow never uploads, prunes or deletes cloud objects.

The default destination is **d2l_local_production** on the local PostgreSQL server.
Your existing **direct2logbook** development database is not replaced. The
restore itself does not edit `.env`. The restore copies schema and data; database ownership,
privilege grants and tablespace placement are adapted to the local PostgreSQL
role. External files/media and the server's `.env` are not part of the backup.

## One-time setup

Use the project's Python 3.12 virtualenv. Install `rclone` and PostgreSQL client
tools compatible with the production archive; the existing Homebrew tools work
with the PostgreSQL 16 backups. Local PostgreSQL must be running and the local
role must be able to create databases.

Copy the existing encrypted backup configuration into a separate local file,
without replacing the normal rclone config:

```sh
scp blakepowell@104.131.19.138:/home/blakepowell/.config/rclone/rclone.conf "$HOME/.config/rclone/d2l-backups.conf"
chmod 600 "$HOME/.config/rclone/d2l-backups.conf"
```

It contains the B2 credentials and encryption settings. Keep it outside Git.
The default backup location is `d2lbackups:postgresql`. Optional `.env` overrides:

```dotenv
LOCAL_RESTORE_RCLONE_CONFIG=/Users/blakepowell/.config/rclone/d2l-backups.conf
LOCAL_RESTORE_BACKUP_REMOTE=d2lbackups:postgresql
```

Connection credentials come from the existing local `DATABASE_URL`, with only
its database name changed in this process. If that URL targets a remote host,
the script refuses to use it. Override with `LOCAL_RESTORE_DATABASE_URL` when
needed: it must use localhost/127.0.0.1/::1, no URL query parameters, and a database
name starting `d2l_local_`. Never use the production connection URL.

## Local-only management command

`restore_local_backup` runs only with the isolated local settings profile: DEBUG,
console email, Stripe test keys and a loopback `d2l_local_` PostgreSQL database.
Production settings are rejected before any cloud download or database changes.
On this Mac the profile is already the default. Elsewhere, select it explicitly
with `--settings=logbook.settings_local_restore` when running the command.

## Download and verify, without changing any database

From the Django repository:

```sh
python manage.py restore_local_backup
```

The script ignores newer partial uploads without success manifests. It selects
the newest completed backup, checks its manifest and archive size, downloads
through rclone crypt, compares SHA-256 and runs `pg_restore --list`. Corrupt
completed backups fail visibly; they are not silently replaced with older ones.
Temporary downloaded archives are removed after the command finishes.

## Restore the first local copy

```sh
python manage.py restore_local_backup --apply
```

Restoration uses a new staging database and `pg_restore --single-transaction
--exit-on-error`. It checks required tables, counts every public table and checks
for unvalidated constraints before renaming the database to the local-copy name.
An existing local copy is left in place unless `--replace` is specified.
A private summary is saved under
`~/.local/share/direct2logbook/local-restore/last-restore.json`.

## Use the local copy

To make this the default on this Mac, add this **local-only** setting to `.env`:

```dotenv
DJANGO_SETTINGS_MODULE=logbook.settings_local_restore
```

Django's manage.py and Celery honor this selection; without it their default
remains `logbook.settings`. Do not add it to production. Restart existing local
Django and Celery processes after selecting it. Normal `python manage.py
runserver` and `celery -A logbook worker -l info` commands then use the restored
copy and its isolated integrations. The original local database remains intact.

The wrapper also selects the profile explicitly, independent of that `.env`
preference, and is convenient when switching between configurations:

```sh
python scripts/local_db.py runserver
```

In another terminal, if background jobs are needed:

```sh
python scripts/local_db.py worker
```

Stop any existing server on port 8000 before starting this one. The wrapper uses
`logbook.settings_local_restore`, which forces:

- DEBUG on, console email, and Stripe **test** keys (live key prefixes are rejected).
- Loopback PostgreSQL and an isolated `d2l_local_` database name.
- Local RabbitMQ with a dedicated queue/exchange/routing key; no production queue.
- No copied database-backed Beat schedules; no automatic monitoring/backup jobs.
- Local file storage, in-memory runtime cache, distinct browser cookie names,
  and production Sentry reporting disabled.

Existing Stripe customer/subscription IDs remain intact. They belong to live
Stripe and generally cannot be used with test keys; test billing flows need
Stripe test objects. Restoring or browsing does not replace those identifiers.
Emails generated by local requests/jobs print to their terminal instead of
being delivered. Use this worker for the local copy, not the normal worker.
The restore itself does not publish tasks or replay copied queued jobs.

Other local-copy commands use the same wrapper:

```sh
python scripts/local_db.py shell
python scripts/local_db.py check
python scripts/local_db.py migrate --plan
```

Migrations are not run automatically. If the checked-out app is newer than the
backup, review the migration plan and run `python scripts/local_db.py migrate`
when appropriate. This can intentionally change local data/schema.

## Refresh it again

Stop this copy's Django server, Celery worker and any database sessions, then:

```sh
python manage.py restore_local_backup --apply --replace
```

The old local copy is retained as `d2l_local_previous_<random-id>` with new
connections disabled. The script prints its exact name. An active connection
causes replacement to fail without terminating it. Failed downloads, restores
or verification do not replace the previous copy.

To roll back using psql connected to the local `postgres` maintenance database,
substitute the exact printed name and ensure the current copy has no sessions:

```sql
ALTER DATABASE d2l_local_production RENAME TO d2l_local_failed_copy;
ALTER DATABASE d2l_local_previous_REPLACE_WITH_PRINTED_ID RENAME TO d2l_local_production;
ALTER DATABASE d2l_local_production WITH ALLOW_CONNECTIONS true;
```

Old local rollback databases consume disk space and are not deleted
automatically. Remove a specific old `d2l_local_previous_…` database when no
longer needed. Do not schedule automatic replacement while developing; this
one-command refresh is intended to be run when you choose.

## Tests

```sh
python manage.py test operations.tests.test_local_restore operations.tests.test_backups
```

These tests use mocked cloud/PostgreSQL restoration and never change production.
They cover partial backups, corrupt downloads/manifests, local-only destinations,
explicit replacement, failure cleanup, console email/test Stripe configuration,
Celery isolation, and libpq environment sanitization.

For the opt-in native PostgreSQL drill (temporary fixture databases, no cloud
access), run:

```sh
D2L_LOCAL_RESTORE_INTEGRATION=1 python manage.py test operations.tests.test_local_restore_postgres
```

It restores 151 fixture flights with exact decimal totals and intact identifying
fields, exercises local replacement/rollback-copy retention, and verifies that
an open database session blocks replacement without terminating the session.
