# Airport reference data refresh

`sync_airports` reads the official OurAirports worldwide airports, countries, and
regions CSV downloads from https://davidmegginson.github.io/ourairports-data/.
The data is public domain: https://ourairports.com/data/.
Schema: https://ourairports.com/help/data-dictionary.html.

## Protected initial production update

After deployment and migration, run this once, separately from the monthly job:

```bash
cd /home/blakepowell/app
set -o pipefail
/usr/bin/flock -n /home/blakepowell/logs/airport-sync.lock /home/blakepowell/venv312/bin/python manage.py initial_airport_sync 2>&1 | tee -a /home/blakepowell/logs/airport-sync-initial.log
```

This creates a fresh full database backup using the existing encrypted Backblaze
storage, downloads and verifies it, and only then applies the airport update.
Any backup or verification failure stops the update. It does not modify cron or
prune backups. Preserve the printed backup remote path, SHA-256, and JSON report.
Future daily backup retention still applies; keep a separate protected copy if
this checkpoint needs to outlive normal retention.

Database write failures roll back the airport transaction. If an unforeseen data
problem appears later, disable the monthly airport entry first. Retrieve the exact
pre-update backup using `DATABASE_BACKUPS.md`, verify its recorded SHA-256, and
restore it into a separate recovery database with
`pg_restore --exit-on-error --no-owner --no-privileges`. Compare affected
`flights_mapdata` and `flights_airportcode` rows with the audit report before a
targeted correction. Existing airport IDs are retained. Do not blindly delete new
airports, since users may have selected them after the update.

A full production restore is a disaster fallback requiring stopped web/workers
and a plan for newer records: it would also roll back flights, accounts and billing
state created since the backup. Recovery is manual to avoid overwriting newer user
data. A verified archive is an integrity check, not a guarantee of correct source
semantics or a replacement for an isolated restore test.

Check existing flights/maps, route validation, and CSV preview after the initial
run, then enable the monthly entry below. The local database already received its
initial update; its pre-update dump is `/tmp/d2l-before-airport-sync.dump`.

## Monthly automatic cron job

The normal production path is `scheduled_airport_sync`. Each invocation downloads
fresh official datasets and **applies safe additions and updates automatically**.
There are no prompts or manual approval steps. Closed/missing airports remain,
and uncertain identities are skipped while the rest of the refresh proceeds.

After deploying this branch (including migration `flights.0065_airport_source_and_codes`),
append the entry from `deploy/airport-sync.cron` to the existing production user's
crontab with `crontab -e`. Do not replace the existing backup/monitor entries.

```cron
30 8 1 * * cd /home/blakepowell/app && /usr/bin/flock -n /home/blakepowell/logs/airport-sync.lock /home/blakepowell/venv312/bin/python manage.py scheduled_airport_sync >> /home/blakepowell/logs/airport-sync.log 2>&1
```

The server runs UTC, so this is **08:30Z on the first of every month**, after the
existing 08:00Z database backup. `flock` prevents overlapping scheduled runs.

- Cron output: `/home/blakepowell/logs/airport-sync.log`.
- Each run writes a separate dated JSON report under
  `/home/blakepowell/logs/airport-sync/`, including source hashes, changes, and
  skipped identities. The directory is created automatically outside the Git
  checkout. `AIRPORT_SYNC_REPORT_DIR` or `--report-dir` can override it.
- Download/schema/database failures exit nonzero and are sent to the existing
  Sentry service when production monitoring is active. These alerts use the
  existing Sentry issue notification rules. A missed cron invocation is not
  detected by exception reporting alone.
- Skipped matches are recorded in the report, rather than stopping the monthly
  update or requiring interaction. They remain eligible for a later review.

To run the same job immediately while keeping the cron schedule:

```bash
/home/blakepowell/venv312/bin/python manage.py scheduled_airport_sync
```

The cron entry is prepared in the repository, not installed by deployment. Add it
once after deployment. The existing logs directory must already be writable by
`blakepowell`. Reports should be included in normal log retention planning.

## Optional preview and manual commands

`sync_airports` remains available for previews and troubleshooting. Without
`--apply`, it writes no airport records. `--dry-run` is also accepted.

```bash
python manage.py sync_airports --report /tmp/airport-sync-preview.json
```

For an exact-source preview/apply, download all three official CSVs and supply
all three local files together. The report includes proposed field changes,
additions, aliases, skipped rows, source SHA-256 hashes, and a UTC timestamp:

```bash
python manage.py sync_airports \
  --airports-file /path/airports.csv \
  --countries-file /path/countries.csv \
  --regions-file /path/regions.csv \
  --report /tmp/airport-sync-preview.json

python manage.py sync_airports --apply \
  --airports-file /path/airports.csv \
  --countries-file /path/countries.csv \
  --regions-file /path/regions.csv \
  --report /path/to/logs/airport-sync-applied.json
```

Omitting local files downloads the current official datasets over HTTPS, with a
timeout, 50 MiB per-file limit, and redirects restricted to the official host.
Download URLs are fixed in the command, not read from CSV contents. No new
external packages are required.

## Identity and preservation

- OurAirports' integer `id` is stored separately from the application's primary
  key. Subsequent syncs match that source ID, even when airport codes change.
- The first sync links an existing row only when its unique ICAO match is in the
  same country and within 2 km, or a unique nearby code match is in the same
  country within 2 km. Duplicate or conflicting identities are skipped/reported.
- Even for linked records, country changes, conflicting current/historical ICAOs, and coordinate
  changes over 10 km require review and are not applied automatically.
- Existing primary keys and saved per-flight airport selections are retained.
  The command never deletes or merges database rows.
- Airports absent from a later source file are retained. Previously linked airports marked `closed`
  are retained and their type is updated. The current dataset clears all codes
  from closed rows; on the first sync, unlinked closed rows without codes cannot
  be matched safely and are skipped. Any corresponding legacy database rows
  remain available for historical routes. Blank source codes do not erase old
  codes; previous codes remain aliases. Historical flights continue to resolve.
- New rows without any source airport codes are skipped/reported. Invalid coordinates/countries/overlong values are reported;
  missing CSV columns, duplicate source IDs, empty/malformed files, or a wholly
  invalid dataset abort the run before airport writes.
- Updates/additions/aliases are applied in one transaction. PostgreSQL's advisory
  lock prevents overlapping apply runs. A failed database write rolls back the
  whole airport change set.
- Reapplying identical input does not create new rows or aliases or rewrite
  unchanged rows. Manual custom rows are retained; uncertain matches are reviewed.

## FAA, IATA, ICAO, and historical codes

The source distinguishes `icao_code`, `iata_code`, `gps_code`, and `local_code`.
US and US-territory local identifiers with three or four alphanumeric characters
are stored as **FAA** aliases. Other local and GPS codes are retained separately as reference metadata. They
are not treated as FAA or IATA aliases in route validation: for example, a local
`BOG` code outside the US must not make IATA `BOG` (Bogota) ambiguous.
Never invent an ICAO code by prefixing a local code with K.

For example Texas Gulf Coast Regional Airport has ICAO `KLBX`, IATA `LJN`, and FAA
`LBX`. All resolve to the same airport. Numeric FAA identifiers such as `1G3` and
`8FL6` also resolve. These are airports, not arbitrary navigation fixes.

The shared resolver is used by live route feedback, FlightForm validation,
normal flight maps and saved warnings, CSV imports, and route-warning/map refresh.
A four-letter alphabetic input still selects ICAO (including historical ICAO
aliases). Alphanumeric FAA codes are allowed. Three-character collisions still
use the airport-country rule: one US match is preferred, otherwise ambiguity
requires confirmation. Matching is based on the airport country, never user/IP
location. Codes remain as entered in the flight record.

The legacy `MapData.iata` field may contain FAA identifiers from earlier FAA
imports; previous values are retained as aliases when the current IATA code is
updated. No bulk conversion of historical route text is performed.

## Existing maps and scheduling

The sync changes reference data only. It does not save flights, recalculate
hours/totals, or rebuild previously stored maps. If desired, preview a map/warning
refresh separately after reviewing the reference changes:

```bash
python manage.py refresh_flight_route_warnings --refresh-maps --dry-run
python manage.py refresh_flight_route_warnings --refresh-maps
```

The monthly schedule refreshes reference data only; it does not automatically
rewrite historical flight maps. The report is an audit trail, not an automatic
rollback mechanism. Existing database backup/restore procedures still apply.
