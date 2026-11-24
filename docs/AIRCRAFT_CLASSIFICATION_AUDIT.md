# Aircraft category/class expansion: baseline audit

Step 1 is read-only. It does not add categories, migrate records, call save
signals, repair summaries, or change the API. Classification/schema decisions
remain for the next steps of the feature.

## Run

Use the normal development environment, which on this Mac selects the isolated
`d2l_local_production` copy. Check the target before running against another
environment. The command can audit any configured PostgreSQL database, but
does not connect to production separately or download another backup.

```sh
python manage.py audit_aircraft_classifications \
  --output /absolute/path/to/a-new-baseline.json
```

Optional `--user-id`, `--database` and `--as-of YYYY-MM-DD` narrow the report.
Without `--output`, the report and completion summary are printed to stdout.
Output files are private (0600), and an existing file is never overwritten.
Keep account-specific baseline files outside Git.

The command establishes a PostgreSQL **REPEATABLE READ, READ ONLY** transaction.
All tables are read from the same snapshot, and PostgreSQL rejects writes.
It refuses to run inside an existing transaction or on another database engine
instead of silently weakening that guarantee.

## What is recorded

- Aircraft category/class combinations, engine/weight selections and associated
  flight, training-device, imported-balance and tailnumber counts.
- Per-aircraft and per-account source totals; separate groups for each observed
  category/class pair, including incomplete/unsupported pairs without guessing.
- Independent comparison of every saved numeric/date field in `Total` and
  `Stat` with source records. Missing, unsupported and duplicate summary groups
  are reported. Legacy `ALL` labels are recognized as `All`.
- Exact raw `Total`, `Stat`, `Power`, `Regs`, `Weight` and `Endorsement` snapshots.
  The last four are preserved for later comparison, not independently reconciled
  by this command.
- Counts and SHA-256 fingerprints of the listed source/summary fields. Flight
  fingerprints omit remarks, map caches and error messages; the report explicitly
  lists the covered fields. This is a classification/totals baseline, not a
  full database backup.

## Calculation rules

- Decimal arithmetic; overlapping roles are not added together to infer total
  flight time.
- Simulator duration is separated from actual aircraft flight time. Imported
  simulator balances remain separate too.
- Imported historical balances contribute to lifetime summaries but are not
  assigned invented dates in rolling windows.
- Existing inclusive 30/60/90/180/365/730-day windows and YTD behavior is used;
  future records do not enter rolling figures or Last Flown.
- Null numeric values compare as zero, while raw snapshots preserve the null.
- Lifetime and date-sensitive differences are distinguished in the report.
  A restored development copy can have older rolling figures; a finding alone
  is not evidence of a broken calculation.

## Interpreting findings

Incomplete historical category/class/engine/weight selections are review items,
not a request to rewrite records. In particular, no engine or weight should be
guessed from an aircraft designator. Missing summary rows and mismatched values
remain untouched so the baseline documents the actual starting point.

When comparing a future baseline, use the same database, owner scope and `as_of`
date, and account for any intentional source edits between snapshots. Hashes
must match when the covered records have not changed.

## Mobile compatibility review

The mobile branch includes `classificationCompatibility.test.mjs`, using isolated
SQLite databases and synthetic records rather than a user's device cache. It
verifies preservation of unfamiliar fields through download, form initialization,
disk reopening, queued updates and refreshes, with account isolation.

At the Step 1 baseline, the mobile form only accepted Airplane/Rotorcraft and required
Class, one engine and one weight selection. JSON storage being flexible does
not make those forms ready for additional categories. The statistics parser
accepts additive groups/metadata under schema version 1, but rejects version 2.
No new fields/choices or API contract changes were enabled in Step 1. See
`AIRCRAFT_CATEGORIES_8710.md` for the subsequent Step 2 implementation.
