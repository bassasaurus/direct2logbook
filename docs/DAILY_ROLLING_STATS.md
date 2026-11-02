# Daily rolling flight statistics

The stored rolling columns previously changed only when flight or historical
summary save/delete signals ran. With no edits, old hours could remain in a
30/60/90-day window and YTD could carry over into the next year.

## Calculation

The new `refresh_rolling_stats` command refreshes the existing aircraft-type
`Stat` rows and overall/category `Total` rows:

- 30, 60, 90 days, 6mo, 12mo, 24mo, and YTD use dated `Flight` records only.
  CSV imports create `Flight` records, so they participate normally.
- Historical `Imported` summary balances still contribute to lifetime totals.
  Their rolling inputs are retained in the source records but are no longer added
  to current rolling columns: there are no underlying flight dates to age them.
- Last Flown uses the latest non-future dated flight or historical last-flown
  date; no known date produces NULL, rather than a fabricated 1900 date.
- Existing window definitions remain inclusive: today minus 30/60/90/180/365/730
  days through today. Thus the existing 6mo/12mo/24mo labels retain their fixed-day
  definitions; this does not switch them to calendar-month arithmetic.
- YTD begins January 1 of the current year. Future flights are excluded until
  their date arrives. The application timezone is UTC.

Save signals use the same helper, so editing a flight cannot restore an old
historical snapshot into a current rolling column. Daily maintenance updates only
these eight fields; it does not change flight records, historical input records,
lifetime totals, or other crew/statistics fields. It refreshes existing summary
rows, rather than rebuilding every historical derived table.

The command locks one user and their summary rows at a time in a transaction.
Repeated runs are idempotent. If it fails after earlier users were committed,
correct the cause and rerun it; the current user's changes roll back. No queue,
Celery worker, email delivery or Stripe API is involved.

Separately, type-currency cutoffs now use each call's current date, rather than
the date the Python process started. The no-medical-class fallback also uses the
current request date. No medical validity formulas are changed.

## Deployment

No migration or dependency changes are required. Deploy using the existing manual
workflow, then run these on the server:

```bash
cd /home/blakepowell/app
/home/blakepowell/venv312/bin/python manage.py refresh_rolling_stats --dry-run
/home/blakepowell/venv312/bin/python manage.py refresh_rolling_stats
```

Refresh the home page to inspect the aircraft and total tables. The dry run
calculates without saving or locking summaries. To inspect one account, append
`--user-id` followed by its numeric ID; it is an operator command, not a public URL.

Add this entry to `crontab -e`, retaining existing backup and monitor entries:

```cron
0 0 * * * cd /home/blakepowell/app && /home/blakepowell/venv312/bin/python manage.py refresh_rolling_stats >> /home/blakepowell/logs/rolling-stats-refresh.log 2>&1
```

This is 00:00 each day on the production server's UTC clock. If the server timezone
changes, adjust the cron schedule to align with the application's UTC day.
Yesterday's cached totals remain visible until the midnight job finishes.
There is no daily database write in the page request itself. Missed cron runs
leave the stored windows stale until the next successful refresh.

Verify the first scheduled run with:

```bash
tail -n 20 /home/blakepowell/logs/rolling-stats-refresh.log
```

Look for the current as-of date and updated row counts. Include the new log in
log rotation. This change does not install the cron entry automatically or add
email/Sentry cron alerts for this maintenance command.

## Tests

```bash
python manage.py test flights.tests.test_rolling_stats home.tests.test_currency_rollover
```

Tests cover all six inclusive rolling boundaries, daily aging without edits, YTD
year rollover, future dates, historical last-flown dates, historical snapshot
exclusion, lifetime-total preservation, owner/category separation, save-signal
consistency, dry-run behavior and repeatability. Currency tests move the mocked
clock without reimporting the module to model a long-running server process.

## Legacy category labels

The refresh accepts known Total categories regardless of case or surrounding
whitespace (for example, `ALL`, `All`, and ` all `). It does not rename, delete,
or combine historical summary rows. Unknown categories are left unchanged and
reported on stderr by Total row ID; they do not block other rows or users.
Review any skipped IDs to determine the intended category before correcting data.
A run reporting skips has refreshed only recognized rows, not every summary.
