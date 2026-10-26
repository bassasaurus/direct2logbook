# CSV integrity and security

CSV inspection, import, and download require login. Import is a CSRF-protected
POST. It still executes synchronously; the existing Celery-decorated callable is
invoked directly, not published to the broker. Do not enqueue HttpRequest objects.

## Validation and atomic saving

Preview reads at most 2 MB plus one byte and accepts UTF-8 (including a BOM).
A file may contain up to 1,000 flights. All rows are parsed before saving flights.
Headers must match the displayed format, accepting common label aliases; the
older 18-column download is also accepted with zero approaches inserted.

Supported dates are YYYY-MM-DD, MM/DD/YYYY, and MM-DD-YYYY. Hours must be finite,
nonnegative, and no greater than 99.9, and are rounded to one decimal place.
Approach and landing counts must be nonnegative whole numbers within the database
integer range. Aircraft/registration/route are required. Aircraft type is limited to four
characters. Registration retains the database field limit of ten characters;
there is no universal five-character limit including the nationality prefix.
Country-specific registration format validation is not yet implemented. Error messages identify the data row where possible.
Uploading an invalid replacement file clears the previously staged session file.

The complete import, including newly created aircraft, registrations, approaches,
and normal signal-driven map/statistics/totals writes, runs in one transaction.
Imports acquire the user's database row lock to serialize concurrent imports for
that user. A registration assigned to a different aircraft type is rejected.
No automatic cleanup changes the user's existing aircraft assignments.

The completion notification runs after commit, with a valid unique Message-ID.
Notification exceptions are logged without converting a completed import into a
failure. It is not automatically resent. The page reports the actual import
response, and general errors conservatively ask the user to check the logbook
before retrying because commit acknowledgements can themselves be ambiguous.

Downloads now include the approaches column. The format represents approach
counts and the importer assigns their type as ILS, as advertised by the existing
upload form. This does not preserve distinct approach types or holding data.

## Remaining work

Web confirmation now uses durable, owner-scoped batch tokens as described below.
The low-level importer still requires its caller to enforce idempotency; future
background tasks must carry a batch identifier, never just repeat the raw import.

Imports remain synchronous and use existing per-flight signals, so large imports
can be slow. The file/row caps bound input, not execution time. Stage payloads
are stored in the batch table and cleared on successful completion. Unconfirmed previews expire after 10 minutes; their CSV content is cleared by
the scheduled command documented below. Minimal receipt metadata is retained. Notification delivery is logged, not
tracked in a dedicated state machine.

## Manual checks

```sh
python manage.py test csv_app.tests
python manage.py test
```

Migration `csv_app.0001_importbatch` is required for durable confirmations. Tests cover typed approaches, validation, rollback of
partial writes and totals, post-commit notifications, authentication/CSRF, and
export/import column alignment. They mock email and do not run real imports
against the user's database. The assistant runs tests with user authorization and reports their terminal
output in the chat. Syntax and whitespace checks are also performed.


## Durable batch confirmation

Every validated preview creates a UUID batch belonging to the signed-in user.
The preview button submits that token with the CSRF-protected POST. Uploaded
payloads are no longer stored in the session. Distinct tabs keep distinct tokens;
a newer preview cannot silently replace the file confirmed in an older tab.

Confirmation locks the user's row and the batch in a transaction. Flight writes,
derived totals, completion timestamp, row count, and clearing the staged payload
commit together. Concurrent or repeated confirmations wait for the first outcome,
then return the same receipt without adding flights or scheduling email again.
A write failure rolls everything back, leaving the same batch retryable. A lost
response can safely be checked by repeating the same confirmation.

Other users' tokens and nonexistent UUIDs return 404. Missing or malformed tokens
return 400. Legacy session-only preview pages must be inspected again after
upgrading. Separate previews, even of identical file contents, remain separate
imports: legitimate identical flights are not silently removed or merged.

Deploy migration `0001_importbatch` before accepting new CSV previews. Restart
Django and Celery together during deployment to load the current import code.
The import remains synchronous; no new queued CSV task or automatic retry policy
has been enabled. Completion receipts do not expire. Unconfirmed previews expire after 10 minutes
and return 410, even if scheduled cleanup is temporarily unavailable.

Tests include PostgreSQL concurrent confirmations on separate database
connections, ownership isolation, repeat submissions, failure/retry, email errors,
and independent previews. No test imports into the live local application database.


## Expired preview cleanup

`python manage.py cleanup_csv_previews --dry-run` counts unconfirmed previews
older than 10 minutes that still contain CSV data. Without `--dry-run`, it clears
their content. It never deletes imported flights or completed confirmation
receipts. Minimal expired-batch metadata also remains, so old tokens return 410
with instructions to inspect the file again. Other users still receive 404.

The confirmation service enforces the deadline even if cron is down. Successful
confirmation is checked before expiry: old completed tokens return their original
receipt without importing again. The cleanup UPDATE checks pending status and
age in the database; an import that holds the row lock can finish and commit
before cleanup rechecks its predicates. A failed import rolls back and can then
be cleaned up if expired.

No additional migration is required for expiry; it uses created_at and completed
from `0001_importbatch`. Test and preview the operation before scheduling:

```sh
python manage.py test csv_app.tests
python manage.py test
python manage.py cleanup_csv_previews --dry-run
```

After deploying/restarting the current code, add a five-minute entry beside the
existing monitoring jobs in the production user's crontab:

```cron
*/5 * * * * cd /home/blakepowell/app && /home/blakepowell/venv/bin/python manage.py cleanup_csv_previews >> /home/blakepowell/logs/csv-preview-cleanup.log 2>&1
```

Verify paths before installation and include this log in rotation. Payloads become
ineligible for import at 10 minutes and are cleared at the next five-minute run; scheduler
outages delay removal but never extend token validity. Check the first run's log
for the number cleared. Database backups have their own retention policy; this
command does not alter them.
