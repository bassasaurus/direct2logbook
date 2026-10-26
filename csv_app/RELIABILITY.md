# CSV import reliability and security

## Upload and confirmation

Inspection, confirmation, download, and status require login. Confirmation is a
CSRF-protected POST. A preview validates the entire UTF-8 file (including a BOM)
before any flight data changes. Limits remain 2 MB and 1,000 flights. Dates accept
YYYY-MM-DD, MM/DD/YYYY, and MM-DD-YYYY; numeric values must be finite and
nonnegative. Per-flight hours cannot exceed 99.9 and are rounded to one decimal.
Counts must be whole numbers. Aircraft type is at most four characters;
registration uses the existing ten-character database limit because nationality
prefixes mean a five-character total limit would reject legitimate registrations.
Headers accept the 19-column format or the older 18-column download, which has
zero approaches inserted. Downloads now include approach counts; imported counts
are assigned ILS, so this is not a lossless export of approach types or holdings.

Each preview gets a UUID batch belonging to the user. Tabs keep separate batch
IDs; raw CSV content is stored in the batch table rather than the session. Preview
content expires after ten minutes unless confirmation has submitted it for work.
Another user's token returns 404, an invalid/missing token 400, and an expired
preview 410. Separate previews of identical files are separate imports; legitimate
identical flights are never silently deduplicated.

## Background submission and progress

The non-atomic HTTP submission view uses a conditional database update to persist
queued state and a task ID before publishing. The Celery task is
`csv_app.tasks.import_csv_batch` and receives only user ID and batch UUID. The
broker task ID matches the batch's stored ID. Never queue the legacy low-level
`csv_import(request, file)` callable, which remains an internal implementation.

Normally POST returns 202 queued/importing, or 200 if the completed receipt is
already available. Publication exceptions return 503 with an unconfirmed status
and owner-scoped status URL. Repeating a POST never republishes an accepted or
unconfirmed batch. A fast completion is not overwritten by publication errors.
Failed jobs return 409 and ask for a fresh preview. The initial publish uses
`retry=False`; there is no automatic import retry policy.

The GET status URL shows queued, importing, completed, failed, or queue
unconfirmed. Responses use Cache-Control: no-store. The page polls every two
seconds for up to twenty minutes; a reload resumes only the latest queued, importing, or queue-unconfirmed batch.
Completed and failed messages do not reappear on a fresh page load.
Progress is phase-based: row counts become imported only when the whole
transaction commits. There are no misleading percentages for uncommitted rows.
A new preview clears the old status display but does not cancel the old job.

The worker claims queued/unconfirmed batches with a matching task ID, then locks
the user's row and the batch for the import transaction. This serializes imports
for a user, including totals signals. Duplicate workers cannot repeat the import.
Repeated HTTP submissions and GET progress reads use MVCC and do not wait for the
long import transaction. Flights, new aircraft/registrations, approaches, totals,
the completion receipt, and clearing CSV content commit together. Failure rolls
these changes back; failure status and clearing its staged content are recorded
afterward. A lost commit acknowledgement cannot overwrite a completed receipt.

Email runs after commit, and notification failure is logged without rerunning or
undoing the import. Email is not automatically resent. CSV receipt completion
means flight data committed, not that email reached an inbox.

## Time limits and interrupted workers

Each task has a 900-second soft limit and 960-second hard limit. Use the prefork
worker pool (the current default). Soft timeouts roll back the import and record
a failure. Hard kills cannot run cleanup; the existing cleanup command closes
unlocked queued/unconfirmed/importing jobs without progress for twenty minutes.
It uses PostgreSQL skip_locked to leave an active import transaction alone.
Closed jobs clear their payload and require a new preview. The worker rechecks
status and task ID under lock, so a late worker cannot reopen a closed batch.

There is no transactional outbox: a process can die between recording queued
state and publishing. Stalled-job cleanup closes such requests rather than
blindly replaying them. No late acknowledgement or automatic broker redelivery
has been enabled. Completion receipts stay indefinitely to prevent reimports.
The map JSON save signal reconnects in a finally block, including after a timeout.

## Preview cleanup and monitoring

`python manage.py cleanup_csv_previews --dry-run` reports expired unconfirmed
preview payloads and stalled background jobs. Without --dry-run, it clears
expired preview data and closes up to 100 eligible stalled jobs per run. Completed
receipts and imported flights are never deleted. Minimal expired/failed batch
metadata remains. Token deadlines are enforced even if cron is down; scheduler
outages delay physical removal but do not extend preview validity.

Keep the existing five-minute cron entry; it now handles both functions:

```cron
*/5 * * * * cd /home/blakepowell/app && /home/blakepowell/venv/bin/python manage.py cleanup_csv_previews >> /home/blakepowell/logs/csv-preview-cleanup.log 2>&1
```

Inspect its output after deployment and include this log in server log rotation.
Backups have their own retention policy. This command does not alter backups or
send alerts. Completely unavailable infrastructure needs independent monitoring.

## Validation and deployment

```sh
python manage.py test csv_app.tests
python manage.py test
python manage.py makemigrations --check --dry-run
python manage.py cleanup_csv_previews --dry-run
```

Tests mock broker/email boundaries and run imports against a disposable test
database. PostgreSQL concurrency tests cover simultaneous submissions, duplicate
workers/confirmations, live progress reads, and cleanup skipping active locks.
The assistant runs tests with user authorization and posts terminal output.

Migration `0002_background_import` adds phase/task metadata and maps existing
completed receipts to completed status. It depends on `0001_importbatch`.
Deploy in a maintenance window after active work finishes: pull the code, migrate,
and restart Django and Celery before accepting new submissions. Every worker
must register `csv_app.tasks.import_csv_batch`; an old worker can discard an
unrecognized task. No static asset was added in this background-import change;
collectstatic is harmless but not newly required by it.

The local migration is applied by the assistant after tests/migration checks.
Before the manual check, restart the local Celery worker with the updated code.
Then inspect a disposable sample and confirm that POST queues it, progress updates,
exactly one import commits, and a repeat confirmation returns the receipt. Do not
import fictional sample flights into a production user's live logbook.
