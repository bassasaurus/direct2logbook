# Encrypted PostgreSQL backups to Backblaze B2

This uses the existing native Django/PostgreSQL deployment plus rclone and cron.
There is no Docker dependency. Nothing uploads until an operator connects B2
and configures the destination. Backups use custom pg_dump archives and require
pg_restore for restoration; the old Desktop/latest.dump was plain SQL instead.

## What the commands do

`python manage.py backup_database`:

1. Checks that the rclone destination is crypt over a Backblaze B2 remote, with
   data, filename, and directory encryption enabled. Config must belong to the
   invoking user and have permissions 600; state directory must be private (700)
   and outside the source tree/static/media roots.
2. Locks against overlapping backup runs and exports the default PostgreSQL
   database using pg_dump -Fc. Database credentials come from Django's existing
   configuration, passed via libpq environment rather than process arguments.
3. Checks that the archive is readable with pg_restore --list and computes SHA-256.
4. Copies to a unique UTC/UUID destination through rclone crypt with --immutable,
   downloads it, and verifies its decrypted bytes and archive listing.
5. Uploads an encrypted success manifest only after verification and writes an
   atomic private local last-success.json. Temporary plaintext files are removed.
6. Exits nonzero and emails DB_BACKUP_ALERT_EMAIL on failure. Subprocess output
   is not included in alerts/logs because it can contain sensitive configuration.

An archive listing and downloaded checksum are integrity checks, not a full SQL
restore drill. Continue isolated restores periodically and after database upgrades.
The backup contains database data/schema/privileges, not PostgreSQL global role
passwords, media objects, the application .env, or the server configuration.

`python manage.py check_database_backups` checks that the last verified backup
is no older than 26 hours, and that its archive and manifest still exist in B2
with the expected archive size. Run hourly. It does not redownload all contents
hourly; the backup job already performs the full round-trip checksum check.
It also emails and exits nonzero if unhealthy. A complete server/mail outage
cannot alert from these commands; independent infrastructure monitoring is separate.

## One-time operator setup

1. Install PostgreSQL client tools matching the production server major version,
   and rclone from a reputable package source. Verify pg_dump --version,
   pg_restore --version, and rclone version. Run as blakepowell, not root.
2. Create a private Backblaze B2 bucket named `direct2logbook-backups` and a
   Read and Write application key restricted to that bucket. Keep credentials
   private. In rclone config create `b2backups`, type `b2`, using the key ID and
   application key. Keep hard_delete false.
3. Confirm bucket access with `rclone lsf b2backups:direct2logbook-backups`.
4. Create a second remote named `d2lbackups`, type crypt, wrapping
   `b2backups:direct2logbook-backups`. Choose standard filename encryption and
   directory encryption. Generate strong encryption passwords in rclone's
   interactive prompts. Keep data encryption enabled.
5. Store the encryption password(s), salt password, and a secure copy of the
   rclone config in a password manager or another secure recovery location that
   survives loss of the app server. These are required to decrypt the backups.
   Do not store the only recovery copy beside the encrypted archives.
6. Run rclone config file to locate the config, then chmod 600 that file.
   This command expects rclone's plain config format protected by Unix
   permissions; it does not parse an encrypted config-file format. Its backup
   contents are still encrypted by crypt. Do not commit the config to Git.

Reference: [B2 configuration](https://rclone.org/b2/) and
[crypt configuration/recovery passwords](https://rclone.org/crypt/).

## Application configuration

Deploy this branch before using the commands. No database migration is added.
Add these values to the production app .env, adjusting the actual config path
reported by rclone config file:

```dotenv
DB_BACKUP_REMOTE=d2lbackups:postgresql
DB_BACKUP_RCLONE_CONFIG=/home/blakepowell/.config/rclone/rclone.conf
DB_BACKUP_STATE_DIR=/home/blakepowell/db-backup-state
DB_BACKUP_ALERT_EMAIL=admin@direct2logbook.com
```

Create the private state directory and perform the first verified backup:

```sh
install -d -m 700 /home/blakepowell/db-backup-state
cd /home/blakepowell/app
/home/blakepowell/venv/bin/python manage.py backup_database
/home/blakepowell/venv/bin/python manage.py check_database_backups
```

Require both commands to pass before scheduling. Use rclone lsd
`d2lbackups:postgresql` to confirm the run directories can be decrypted. Backblaze's
web interface will show encrypted names/content. A failed partial upload has no
success manifest and should be inspected before manual removal.

## Schedule after the first verified upload

Add entries to the existing user's crontab; keep current monitoring entries.
The following uses server clock time. First check `date`/`timedatectl`; on a UTC
server the nightly run is 08:00 UTC (03:00 Chicago in winter, 04:00 in summer).
Adjust with the operator if a different backup window is needed.

```cron
0 8 * * * cd /home/blakepowell/app && /home/blakepowell/venv/bin/python manage.py backup_database >> /home/blakepowell/logs/database-backup.log 2>&1
30 * * * * cd /home/blakepowell/app && /home/blakepowell/venv/bin/python manage.py check_database_backups >> /home/blakepowell/logs/database-backup-check.log 2>&1
```

Check the first cron runs and include logs in server log rotation. A nightly
schedule means up to roughly one day of data loss between successful backups.
No automatic remote deletion or retention pruning is enabled. Unique backups
accumulate until an operator chooses a retention policy. Monitor B2 storage and transaction allowances;
insufficient space will fail the backup and freshness check. No live upload,
cloud authorization, cron change, or remote deletion is performed by the tests.

## Restore drill

Retrieve one successful run's database.dump and manifest.json using the crypt
remote so rclone decrypts them. Compare SHA-256 with the manifest. Restore only
into a newly created, isolated test database with pg_restore --exit-on-error;
do not use --create or --clean against the application database. Verify table
counts/content, foreign keys, migration history, and application reads with
outbound integrations disabled. Do not start Celery against restored production
queues or send real emails/payments while testing. Keep the source archive intact.

The earlier production-dump drill verified 56 tables and their COPY-content hashes.
A Backblaze B2 round-trip and a restore of its retrieved encrypted backup still
need to be completed after account connection; unit tests cannot establish that
Backblaze access and the server's installed binaries are configured correctly.
