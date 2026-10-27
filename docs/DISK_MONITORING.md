# Root filesystem email monitoring

The management command `check_disk_space` works without database queries, Celery,
or rclone. It checks `/` (the production server's current root/data filesystem).
It uses statvfs available blocks to account for filesystem reservations like df.
It emails at >=80%, reminds at most once per 24 hours, and sends recovery mail
below 75% to avoid flapping. Full disks still attempt an alert before saving state.
Separate mounted data volumes are not covered by this root-only check.

Recipient defaults to DB_BACKUP_ALERT_EMAIL; state defaults to a disk-monitor
subdirectory of DB_BACKUP_STATE_DIR. Both already exist in production configuration.
Optional overrides are DISK_ALERT_EMAIL and DISK_ALERT_STATE_DIR. The state folder
must be private (700), owned by the cron user, and outside source/static/media.
State writes are atomic/private and a file lock prevents overlapping checks.
Email submission failure leaves the alert eligible to retry on the next run.
High usage exits nonzero, even while suppressing a repeat email; logs still show it.

After deploying, run as the usual server user:

```sh
cd /home/blakepowell/app
/home/blakepowell/venv/bin/python manage.py check_disk_space
/home/blakepowell/venv/bin/python manage.py check_disk_space --send-test
```

Confirm the deliberately labelled test email arrives before scheduling. It uses
real current disk usage and does not fake high usage or change incident state.
No database migration, dependency install, collectstatic or service restart is
required for this cron-only command. Each invocation reads settings anew.

Append to the user's existing crontab, leaving backup and other jobs intact:

```cron
15 * * * * cd /home/blakepowell/app && /home/blakepowell/venv/bin/python manage.py check_disk_space >> /home/blakepowell/logs/disk-space-monitor.log 2>&1
```

Runs hourly at :15 in server time. Confirm `crontab -l`, inspect the first automatic
run's log, and include that log in normal rotation. This does not clean up files.
Server/cron/email outages cannot notify through this command: uptime monitoring
remains separate. Sentry may also receive command errors through existing logging;
this command does not create a separate Sentry cron monitor.
