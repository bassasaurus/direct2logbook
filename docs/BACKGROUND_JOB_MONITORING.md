# Background-job alerts

`check_background_jobs` reads the saved PDF, CSV and trial-provisioning records
and emails one combined digest. It runs independently of Celery, so a stopped
worker does not prevent it detecting queued jobs that have stopped progressing.
It never queues, retries, cancels, or changes jobs, contacts Stripe, or sends a
user's PDF. Existing PDF/CSV reconciliation commands keep their current behavior.

## What it reports

| Job | Eligible problem |
| --- | --- |
| PDF | Queued, unconfirmed, processing, retrying or sending without progress for more than 15 minutes; failure updated within 24 hours; any unresolved delivery uncertainty |
| CSV | Unfinished queued, unconfirmed or processing without progress for at least 20 minutes; failure updated within 24 hours |
| Trial | Failed or uncertain attempt; pending for at least 15 minutes; processing started at least 15 minutes ago or missing its start timestamp |

Recently queued/running jobs, CSV previews, and successful jobs do not alert.
A pending trial record is now saved in the verification/signup transaction before
its on-commit publication callback. If the broker rejects publication, or that
callback never runs, the pending record remains visible to this monitor. This
adds visibility for **new** requests; it cannot reconstruct old requests that
were never recorded. No automatic trial recovery has been enabled.

The digest includes totals, record IDs, statuses and last-update timestamps, with
at most the oldest 30 rows per job type. It excludes account emails, CSV content,
raw exceptions and Stripe credentials. The alert is a point-in-time observation:
a worker can subsequently complete a job. Inspect its current state before acting.

A database row lock serializes invocations and persists a one-hour email cooldown.
The cooldown applies to the whole digest, including new problems arriving within
that hour. At a five-minute cron interval, a problem normally alerts on the first
eligible check; one arriving during cooldown waits for a subsequent check after
that hour. Unchanged problems repeat hourly while still eligible. Old PDF/CSV
failures age out after 24 hours; uncertainty and unresolved billing failures do not.
A successful job no longer appears. There is no recovery email.

If email delivery raises or returns zero, cooldown is not advanced and the command
fails for the next cron invocation to retry. Email acceptance and the database
commit cannot be atomic, so a crash/commit failure after email acceptance can
produce another digest. These messages are operational notifications, not customer
job retries.

## Deployment and verification

Deploy through the existing workflow. This change includes migration
`operations.0001_initial`, which creates the monitor cooldown table.

Set this in the production `.env`:

```dotenv
BACKGROUND_JOB_ALERT_EMAIL=admin@direct2logbook.com
```

No recipient is enabled by default in local development or CI. Restart the app
services if changing their environment after deployment. The management command
reads the environment fresh each invocation.

First inspect without email, monitor-state changes, or job changes:

```bash
cd /home/blakepowell/app
/home/blakepowell/venv312/bin/python manage.py check_background_jobs --dry-run
```

Then send a clearly labelled test and confirm actual inbox receipt:

```bash
/home/blakepowell/venv312/bin/python manage.py check_background_jobs --send-test
```

The test does not set the cooldown. Finally run the real command and review any
reported jobs before scheduling it:

```bash
/home/blakepowell/venv312/bin/python manage.py check_background_jobs
```

Add one new entry alongside the existing webhook, PDF, CSV, backup and disk checks:

```cron
*/5 * * * * cd /home/blakepowell/app && /home/blakepowell/venv312/bin/python manage.py check_background_jobs >> /home/blakepowell/logs/background-job-monitor.log 2>&1
```

Keep existing `reconcile_pdf_requests` and `cleanup_csv_previews` entries: this
monitor does not replace their cleanup. Review the new log after its first run
and include it in log rotation. No production environment or cron entries are
changed by adding this code.

For a PDF with uncertain delivery, inspect email delivery before any manual
resend. For a trial, use `inspect_billing_provisioning` and reconcile the Stripe
customer/subscription before a recovery attempt. Do not blindly replay CSV or
billing tasks. See each feature's reliability documentation.

This is job-state monitoring, not a worker heartbeat: an idle dead worker is only
detected when a queued job exceeds the threshold. Database, cron, host or email
outages can prevent the monitor from sending email. Existing independent uptime
and Sentry monitoring remain necessary; this command does not configure a Sentry
cron monitor. A passing unit test does not prove production cron or email delivery.

## Tests

```bash
python manage.py test operations.tests.test_job_monitoring payments.tests.test_signals accounts.tests.test_google_signin
python manage.py makemigrations --check --dry-run
```
