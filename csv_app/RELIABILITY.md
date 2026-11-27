# CSV import reliability and security

## Wizard foundation

The web flow is Upload → Columns → Dates → Review → Import. Known canonical
layouts skip Columns. The Dates step is automatic unless a numeric date could
mean different days. `forms.py` owns file selection and column matching;
`formats.py` recognizes source layouts and translates them into the existing
validated import format. The upload page accepts the supported base headings in
any order, including existing aliases and optional device/launch headings. The
worker receives canonical columns through the same owner-scoped batch mechanism.
Other well-formed CSVs open the provider-neutral matching screen. Malformed or
oversized files are rejected before staging. Duplicate candidate headings are
never guessed; the user chooses a column by its original position and samples.

The first registered adapter covers Direct2Logbook's current and legacy exports.
Generic matching recognizes exact common headings and aliases without fuzzy
inference from values or filenames. Neither provider selection nor competing
product names belong in the UI. Add
verified sample-export fixtures before registering another source. Every adapter
must share row limits, validation, preflight, and atomic import services.

`mapping.py` accepts at most 100 source columns and the existing 10,000-row/20 MB
limits. Date, Aircraft Type, and Duration require a source column or an explicit
shared value. Other fields can be mapped, supplied as shared values, or omitted;
normal row validation still requires route/registration for actual flights and
the appropriate device details for classified simulator rows. Departure and
destination may be combined into Route; conflicting route mappings are rejected.
Nonempty unused columns require explicit ignore confirmation, which the browser
resets whenever a mapping changes. Mapping errors preserve the original staged
file for correction. HH:MM hour values become decimal hours; true/false and
yes/no selections apply the full Duration. Numeric PIC/SIC/Dual/CFI/Solo/XC
amounts must match Duration or require explicit row correction/exclusion.
Flight records retain one Duration with whole-entry role selections.

Departure and destination are temporary mapping inputs, never new Flight fields.
The Route control automatically selects the airport builder when both inputs are
matched. Explicit airport-code headings prefer ICAO, then IATA, then FAA; generic
Departure/Arrival time values are not matched as airports. `airports.py` checks
actual-flight routes using the existing airport resolver, including historical
aliases and ambiguity rules. Known airports become ICAO codes where available,
then IATA, then FAA/legacy identifiers. A preferred code must still identify the
same airport unambiguously; no K prefix is invented. Airport reads are batched
across the preview. Unknown/ambiguous airports produce row-numbered errors and
leave mapping open for correction; simulator routes skip this validation. Only
the resulting Route is stored, and existing flights are not rewritten.

Migration `0005_batch_column_mapping` stores the confirmed mapping and marks
incomplete mappings. Existing previews/jobs default to complete for compatibility.
Both queue submission and the importer reject incomplete mappings. Mapping and
date forms use owner-scoped, CSRF-protected previews, the same ten-minute expiry,
and row locks. Accepted mappings are immutable for that batch; another upload
starts an independent review. No flights are written by either step.

`csv/template/` downloads a compatible example template. It includes one sample
flight, which the page explicitly tells users to replace. Review calls out the
role-hour conversion, holding and typed approach counts. No flights are
saved until the user confirms. Styles, JavaScript, and templates now live inside
`csv_app` so the import interface can evolve independently of other pages.

`dates.py` examines all numeric dates together. Day values above 12 can establish
the order for the entire file; conflicting month/day orders fail validation.
Ambiguous dates show both interpretations with no default selected. Identical
interpretations, ISO dates, and named-month dates do not require a choice. Date
order is never inferred from aircraft, route, locale, or filename.

Migration `0004_batch_date_order` adds preview metadata only; existing batches
retain their current interpretation. A pending date choice uses the existing
owner-scoped preview and ten-minute expiry. Both queue submission and the import
service reject pending choices. Choosing an order saves ISO dates, which are
used in the human-readable preview and by the background worker. Repeated date
submissions cannot reinterpret an already reviewed or submitted batch. Start a
new upload to change the interpretation. No flight data changes at this step.

## Upload and confirmation

Inspection, confirmation, download, and status require login. Confirmation is a
CSRF-protected POST. A preview validates the entire UTF-8 file (including a BOM)
before any flight data changes. Limits are 20 MB and 10,000 entries. Dates accept
YYYY-MM-DD, MM/DD/YYYY, and MM-DD-YYYY; numeric values must be finite and
nonnegative. Per-flight hours cannot exceed 99.9 and are rounded to one decimal.
Counts must be whole numbers. Aircraft type is at most ten characters, matching the aircraft model;
registration uses the existing ten-character database limit because nationality
prefixes mean a five-character total limit would reject legitimate registrations.
Headers accept the 19-column format or the older 18-column download, which has
zero approaches inserted. Downloads append four optional device columns:
`device type`, `device id`, `atd type`, and `instrument credit eligible` (1 or 0).
Existing 18/19-column files remain accepted. Simulator rows may omit registration
and route; no placeholder tailnumber is created. Unclassified legacy simulator
rows remain unclassified. Classified devices require FFS/FTD/ATD, a Device ID,
and BATD/AATD when ATD is selected. Claiming instrument credit also requires Dual,
instrument time, and an aircraft represented in the Airplane category.
Device metadata survives export/import; existing source records are not rewritten.
Downloads also append `launch method`, `holding` and `approach types`. Typed
approaches use `ILS: 2; LPV: 1`, accepting supported approach codes and labels.
Counts without a type remain unspecified rather than being assigned ILS. Holding
accepts Yes/No or nonnegative counts (positive means Yes), and is saved in both
the Flight flag and the normal Holding related record. Typed approaches and
holding survive export/import. Type/count disagreements and unknown types require
row correction. Overlap review includes approach types/counts and holding, so
changes invalidate a previously approved match.

Each preview gets a UUID batch belonging to the user. Tabs keep separate batch
IDs; raw CSV content is stored in the batch table rather than the session. Preview
content expires after ten minutes unless confirmation has submitted it for work.
Another user's token returns 404, an invalid/missing token 400, and an expired
preview 410. Separate previews of the same uploaded contents share one submitted
import receipt. Similar-looking flights in different files are not silently
deduplicated. See Duplicate uploaded files below.

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
File selection and inspection share a compact toolbar. Inspect is disabled until
selection and shows Inspecting during preview submission. Import stays in place
and changes through Submitting, Queued, Importing, and Imported; the final state
links to the logbook. Expired/failed previews offer Choose another CSV. Transport
uncertainty offers Check request, which safely resubmits the same batch token.

The worker claims queued/unconfirmed batches with a matching task ID, then locks
the user's row and the batch for the import transaction. This serializes imports
for a user, including totals signals. Duplicate workers cannot repeat the import.

The background worker saves and validates each flight, retaining map and warning
signals, while summary calculations are deferred in a context-local import scope.
After the last row, it rebuilds account-wide summaries once and aircraft stats
once per affected type, before committing the same transaction. A summary failure
rolls back the imported flights too. Signals are never globally disconnected;
other requests and accounts retain normal behavior. Adding workers is a separate
capacity decision, not a prerequisite for batching.
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

## Operational email alerts

The separate `check_background_jobs` command reports recent failed imports and
stalled queued/processing jobs in a combined operator email digest. It does not
import, replay, or close batches; retain the existing cleanup command.
See [background-job monitoring](../docs/BACKGROUND_JOB_MONITORING.md) for setup.


## Aircraft and tailnumber resolution

The wizard now proceeds through Upload → Columns → Rows → Dates → Records → Review →
Import. The Records step matches aircraft types and registrations case-insensitively
within the signed-in account. Known matches skip directly to Review. Missing
matches and aircraft/tailnumber conflicts must be resolved before queueing.

Users can select an existing record or create an Aircraft/Tailnumber with the
same validated forms used elsewhere in the application. Creation explicitly saves
that account record immediately; abandoning the CSV does not delete it. No flights
are saved before final import. Existing aircraft and tailnumber assignments are
never rewritten by resolution. Selecting a different pairing changes only the
staged CSV rows. Simulator sessions may explicitly omit a tailnumber.

Unresolved aircraft types are shown first, followed by tailnumber pairs. Lists
are processed in groups of 25 so a large file does not exceed form-field limits.
New batches cannot bypass the Records step by posting directly to Import. A
snapshot of the matched IDs, names and tailnumber assignments is verified before
queueing and rechecked under row locks in the import transaction. If a matched
record was changed or removed after Review, import stops with a friendly message
rather than silently recreating it. Legacy queued batches retain their previous
behavior through the migration defaults.

Migration `0006_csvimportbatch_record_resolution_and_more` adds the resolution
state. Apply migrations and restart both Django and Celery when deploying this
wizard, and collect the app-scoped static assets. Regression tests cover owned
matches, conflicts, explicit creation, missing required details, pagination,
CSRF/expiry, changed matches, and a final import with unchanged record identities
and verified totals.


## Row corrections and exclusions

After column matching, invalid rows open a correction screen. Each row retains
its source row number, original values, current values and exclusion flag.
Numeric/date/length errors and airport errors are shown together where possible.
Model and device validation is also run once the referenced account records can
be resolved. Original CSV files and saved flights are never edited by this step.

All fields are editable, with 20 rows per page to keep form submissions below
Django's field-count limit. Page navigation saves current edits. Excluded rows
remain available to include again, and are counted separately in final Review;
they never enter the import payload. At least one included flight is required.
A Review link also lets users edit or exclude otherwise valid rows. Opening
corrections disables submission until all included rows pass validation again.
Changing references resets the saved matches and routes back through Records.
Ambiguous numeric dates still require the Dates choice; no date order is guessed.

Migration `0007_csvimportbatch_row_data_csvimportbatch_rows_complete` stores staged
corrections and the validation gate. Submission and worker services both enforce
that gate. Staged row values are cleared alongside the raw content on completion,
failure, and expiry. Restart Django/Celery after migration and collect static assets.


## Evidence-backed CSV / TSV adapters

The generic Columns step recognizes native Logbook Pro, LogTen, ForeFlight and
MyFlightbook headers without a product selector or product names in interface
copy. CSV, TSV and semicolon-separated files are supported. Original columns
remain available to inspect and override. Derived route, duration and aircraft
columns explain their purpose using neutral labels. Dependencies used to build
those columns are not falsely listed as unused.

Numeric native times require an explicit decimal-hours/minutes choice; HH:MM is
converted separately. Ambiguous month/day order still opens Dates. Two-digit
years require explicit confirmation of the displayed century rule. Unsupported
columns require explicit acknowledgement before omission; unknown or duplicate
columns are never silently chosen. Native exports allow up to 500 columns, with
the same 20 MB / 10,000-entry limits. Generic files retain their 100-column limit.

ForeFlight's separate aircraft/flight tables are joined by AircraftID; represented
aircraft type and explicit FFS/FTD/BATD/AATD metadata are preserved. Missing or
conflicting matches need correction. MyFlightbook files without Model may look up
the type using only tailnumbers owned by the importing account. Missing matches
still require aircraft resolution. No aircraft classification is inferred from an
unverified source category. Routes combine From, intermediate Route and To while
avoiding duplicated endpoints and preserving round trips.

ForeFlight `Approach1`, `Approach2`, etc. are parsed using the documented
`count;type;runway;airport;comments;circle` structure. Supported types/counts are
combined, including repeated types, CAT II/III and generic RNAV (GPS) without
inventing a minima line. ASR/SRA maps to ASR. Ambiguous combined types (such as
ILS OR LOC), GCA, generic RNAV (RNP), malformed cells and missing types require
row correction. Valid approaches remain visible alongside any error. Original
structured details are appended to Remarks using readable separators; oversized
Remarks require correction rather than silent truncation. Source approach cells
are marked used by the prepared count/type/remarks columns.

Field specification:
https://support.foreflight.com/hc/en-us/articles/215647217-What-are-the-formatting-requirements-for-each-field-in-the-Logbook-template

Remarks containing commas or tabs require user correction. The importer does not
strip or replace those characters. Web flight forms and CSV correction cards
show escaped previews with red outlined `comma` and `tab` markers at their
positions. Model saves, form validation and API field validation share the same
validator; pre-existing stored remarks are not rewritten. This is application
validation, not a database constraint on bulk SQL writes.

Large mixed-file browser check (Nov 27, 2026, disposable local database): 506
source rows, eight corrections, one unusable row excluded and five existing
matches excluded. Imported 300 flights / 455.0 hours and 200 device sessions /
285.0 hours in approximately 5.5 seconds including summary rebuilding. Verified
every saved value, approaches, Holding, map data and lifetime/rolling totals;
1,047 earlier records unchanged. Re-uploading the same file added no entries.
That run exposed Night greater than Duration being accepted; the sample was
corrected manually before import. Shared web/API/CSV validation now rejects it
with “Night cannot exceed Duration.” CSV errors attach to the editable Night
field. Equality, blank/zero Night and valid partial updates remain supported.

Trello #180 split-role regression: a 2.0-hour row containing 0.5 PIC / 1.5 SIC
requires review before saving. All six role amounts must match Duration or be
cleared; unsupported partial amounts can also be excluded with the entire row.
Native and mapped numeric export columns contain hours. Historical canonical
templates retain their 0/1 checkbox semantics. Manual web/mobile forms and the
Flight model retain one Duration with boolean role selections. Summaries, PDFs
and CSV downloads attribute the full Duration to selected roles.

Simulator-only duration is retained as device time, not actual flight totals.
Non-flight duties require explicit row exclusion. Migration 0082 adds only the
nullable night Full Stop flag, leaving historical status unrecorded. Full Stop
applies to all night landings in an entry and requires both a positive count
and Night time. Only confirmed Full Stop entries count toward night-landing
currency; ordinary landing totals remain unchanged. Grouped daily routes remain
one entry; leg counts never fabricate
per-leg durations. Shared Approach Types and Holding fields are supported; vendor
specific structured metadata, unrelated custom fields and runway/location details
are not claimed as lossless imports. Unused source fields require acknowledgement.
Explicit device descriptions normalize to FFS/FTD/ATD; BATD/AATD preserve their
subtype. Generic Simulator/FTD labels do not establish a device category. Missing
classifications, IDs and contradictory ATD subtypes need row correction.

Safelog's vendor documentation confirms configurable layouts and example headings
Date / Aircraft Type / Aircraft Registration / Duration of Flight / Instrument
Approaches. These headings enable the Safelog-style adapter. Additional fields in
our synthetic fixture exercise shared mappings; this is not a vendor-certified
export schema. https://www.dauntless-soft.com/helpdesk/issue_view.asp?CATE=0&ID=671

Migration `0008_csvimportbatch_source_metadata` stores the source semantics and
units alongside staged corrections, so validation cannot lose that context.
Apply migrations, collect static files, and restart Django and Celery together.
Tests use reconstructed native-shaped samples, not vendor-certified customer
exports; field aliases are evidence-based and users still confirm every mapping.

Readable Logbook Pro-style headings also support Aircraft Type / Aircraft Ident /
Route / Duration, Dual Received / Dual Given, Actual Instrument / Simulated
Instrument, Flight Simulator and Day / Night Landings. This variant is based on
the headings supplied by the user in a search-summary screenshot, not a captured
vendor export. Tests use synthetic values; official export compatibility remains
provisional. Takeoff counts and custom reference fields remain unassigned and
require acknowledgement rather than being silently substituted for landings.

Evidence:
- MyFlightbook's published import table verifies From/To route construction,
  hours in IMC/Dual Received/CFI/Ground Simulator, separate full-stop day/night
  landings, and its own Flight ID. From/To is combined into Route. SIM is cleared
  from registration only when Ground Simulator is positive; device type/ID must
  still be supplied or corrected. Flight ID never updates Django records. Total
  Landings and display-only Flight Properties have explicit unused-column notes;
  total landings is not guessed into a day/night split.
- https://myflightbook.com/logbook/mvc/pub/ImportTable
- https://myflightbook.com/logbook/mvc/faq
- Coradine's API appendix verifies `flight_selectedAircraftID` and
  `flight_selectedAircraftType`; these are accepted as alternate aircraft fields.
  Competing aircraft aliases still need a user choice. API field names are
  evidence for semantics, not proof of every CSV export layout or numeric unit.
  Plain numeric time units remain explicitly confirmed. Scheduled, takeoff and
  landing timestamps and crew names are not silently mapped onto duration or
  pilot roles. Holding counts become Yes/No with an explicit conversion note;
  supported approach types and counts are preserved through the shared parser.
- https://docs.nc-software.com/display/LPDOCS/Windows+Style
- https://docs.nc-software.com/display/LPDOCS/Export
- https://github.com/AstroPhysX/flightline-tracker/blob/main/app/services/logbook_service.py
- https://github.com/Coradine/logten-api
- https://support.logten.com/en/articles/11661458-exporter-reports
- https://github.com/ericberman/MyFlightbookWeb/blob/master/MyFlightbook.Web/AppCode/Flights/Import/LogTenPro.cs
- https://cloudfront.foreflight.com/docs/ff/16.1/ForeFlight%20Logbook.pdf
- https://github.com/ericberman/MyFlightbookWeb/blob/master/MyFlightbook.Web/AppCode/Flights/Import/ForeFlight.cs
- https://github.com/ericberman/MyFlightbookWeb/blob/master/MyFlightbook.Web/Public/ImportTemplate.csv


## Duplicate uploaded files

Migration `0009` retains a SHA-256 source fingerprint after payload cleanup. It
ignores filenames, UTF-8 BOM, CRLF/LF differences and final blank lines. Identical
uploads already queued, unconfirmed, processing or completed return the existing
account-owned receipt instead of another import. Multiple open previews are
protected at submission by a conditional unique database constraint; worker-side
confirmation also checks the prior receipt. Failed imports may retry. Preview
editing does not change the original upload identity.

This is source-file protection, not fuzzy flight deduplication: changed files or
exports containing overlapping flights still need user review. Completed receipts
from before this migration have no retained source bytes and cannot be backfilled.


## Column mapping presentation and dragging

Required fields are shown first, followed by unresolved ambiguous matches and
matched optional fields. Unmapped optional fields stay in a collapsed Other fields
section. Any field with a validation error is promoted into the visible review
section. Numeric units and short-year confirmation are never collapsed.

On wide screens, the Available columns panel lets users copy a source column onto
a target field. This changes the existing dropdown; it never saves flights, moves
source data, or clears another assignment. A column can supply more than one field.
Dropdowns remain available for keyboard, touch and non-drag interaction. Narrow
screens omit the palette. Upload also accepts one dropped CSV/TSV/TXT file, with
client-side size/type feedback and the existing server-side validation unchanged.

Run Django CSV tests as usual. File-drop behavior tests require no dependencies:
`node --test csv_app/tests/test_import_ui.cjs`.


The mapping screen names the source panel Your File and the destinations
Direct2Logbook. Each source retains its column number and shows its assigned
fields (for example Used → PIC), including prepared-column dependencies. Initial
usage and unselected-column visibility are also rendered by Django, so they do
not depend on JavaScript finishing. Competing aliases stay separate: assigning
PIC does not silently discard a different Pilot in Command column.

Conversion notes beside mapped fields explain combined routes, HH:MM conversion
and numeric minutes conversion; these update when users change columns or units.
The final review remains the authority for converted and rounded values.


## Block Out / Block In duration

The Columns step recognizes separate Block Out and Block In headings (including
Out/In and Gate Out/Gate In). If Duration is missing, Calculate from Block Out and
Block In is suggested. Users can also choose that option instead of a supplied
Duration column. These helper columns are not added to the Flight model; only the
calculated duration is saved. Elapsed time is rounded once to the nearest tenth,
half up, and is never divided again by a numeric-minutes selection.

HH:MM clock times must share a time zone. An earlier clock-only Block In requires
explicit next-day confirmation; equal times are not assumed to mean 24 hours.
ISO timestamps with dates handle overnight automatically and may include explicit
UTC offsets. Mixed dated/undated values, mixed offset-aware/naive values and reverse
dated ranges are not guessed. Bad calculated values go to Rows, where Duration
can be corrected or the row excluded.

If supplied Duration and mapped block times disagree after tenth-hour rounding,
the mapping step requires users to calculate from blocks or explicitly keep the
selected duration. Every row is compared and shown in a scrollable comparison
table. Unreadable mapped block values likewise require explicit review when
keeping a supplied Duration. Final Review repeats the calculation and confirmation
choices. HH:MM duration conversion remains automatic; the numeric units selector
is hidden when no mapped numeric time values need units.


## Final import summary

Review totals are recomputed from the final canonical payload using the importer’s
Decimal parsing and per-entry tenth-hour rounding. Included actual flights and
simulator/device sessions have separate counts and hours. The date range includes
all included entries and excludes removed rows. No summary totals are cached or
written to the user's totals before import.

Row corrections record the explicitly edited fields in staged JSON. Automatic
airport/date normalization does not count as a manual edit. Excluded entries are
listed separately and do not contribute hours, dates or edited-row counts. The
summary and conversion/confirmation notes appear before the Import button. Device
hours are never added to flight hours. Source and row-edit conversion notes are
preserved through preview; staged row edit details follow normal payload cleanup.


## Overlapping exports and loading feedback

After account record resolution, Matches compares incoming entries with the
signed-in user's existing flights using date, aircraft type, registration,
airport-equivalent route, tenth-hour duration and simulator status. Explicit
training-device identity is also compared. Matching entries are candidates for
review, not proven duplicates. Repeated rows within a file and changed-duration
or changed-route exports are not silently deduplicated. Different aircraft,
tailnumbers or durations do not trigger overlap review. Full route order matters:
an outbound route and its return remain separate, for any airport pair. Repeated
same-day local flights (such as AXH–AXH) are only flagged when aircraft, tailnumber
and duration also match, and can still be explicitly imported as separate flights.

Each candidate requires Exclude incoming row or Import anyway, with no default.
Existing records are never updated or deleted. Choices are processed ten rows at
a time and bound to fingerprints of incoming values and current matching records.
Edits reset choices; stale review submissions require fresh decisions. Matches
are rechecked before queueing and under the import's account lock before writes.
If new matches appear after queueing, import fails atomically with instructions
to upload again. All-excluded files show Nothing to import and retain excluded
rows until normal preview cleanup, with no entries added. Migration `0010` adds
staged decisions; apply it and restart Django/Celery when deploying.

Assigned source chips appear to the right of destination fields on wide screens
and leave the source palette. Dragging an assigned chip reassigns it; unassigning
returns it to Your File. Dropdowns continue to support reusing a source. Required
fields have a bordered card. Review File shows Reviewing file… plus a spinner and
progress text while its normal POST runs; double submission is prevented and
Back/Forward restoration resets the button. The file input stays enabled so its
contents remain part of the browser's upload payload.


Flight form requirements apply to new CSV imports. Actual flights need Date,
Aircraft, Tailnumber, Route, Duration, and a PIC/SIC/Solo/Dual selection. Missing
columns can be supplied explicitly through shared values; they are not guessed.
Solo requires a landing; Sim and XC are mutually exclusive; simulator sessions
require device type/ID and BATD/AATD when applicable. Old saved flights are not
modified. Aircraft category-dependent checks run again after record setup.
Missing aircraft details are saved first, then new tailnumbers require exactly
one operating rule (Part 91/135/121), then flights are imported only after review.


If an aircraft or tailnumber snapshot changes after review, the import returns
to the same batch's Records step without deleting the staged CSV or corrections.
The worker exits the rolled-back import transaction before reopening review.
Recovery keeps ownership checks, grants a fresh 10-minute review window once,
and clears outdated overlap approvals. A corrected submission gets a new task
ID; delayed old tasks cannot claim it. Reopening Upload displays a correction
link rather than forcing a redirect, so a user may choose a different file.
Other unexpected import failures continue to fail atomically and clear payloads.


## 10,000-entry capacity and preview pagination

The application accepts up to 10,000 entries and 20 MiB per source or canonical
file. The UI calls the byte limit 20 MB, matching the previous convention.
All parsing/adaptation/staging services, file selection, drag/drop and displayed
limits use the shared ceilings in `validation.py`. Generic/native column limits
remain 100/500. Whole-file validation still runs; pagination never truncates an
import. Unused source columns still require explicit acknowledgement.

Final Review renders 50 entries per page. First/Previous/Next/Last links use an
owned, read-only preview endpoint with the same expiration and workflow checks.
Every page keeps full-file totals and the full Import count. Invalid page values
are handled by Django's paginator. No database writes occur while paging. Exact
row/byte boundary tests reject 10,001 entries and a file one byte above 20 MiB.

Opt-in PostgreSQL acceptance checks (Nov 27, 2026, disposable test database):

- Two concurrent 10,000-entry accounts plus duplicate worker delivery: 20,000
  imported entries, correct per-account values/maps/totals, approximately 125 s.
- Terminated the actual database connection after saving entry 5,000. All new
  rows/approaches rolled back and the original flight/totals remained unchanged.
  Re-upload and retry committed exactly 10,000 entries; repeated old/new worker
  deliveries added nothing. The retry worker took approximately 226 s.
- A 19,250,152-byte generic export with 10,000 entries and 16 unused columns:
  upload 4.6 s, mapping/preview 14.9 s, worker approximately 328 s. Explicitly
  acknowledged unused columns; verified every stored row, approaches/holding,
  maps and aircraft/device/role/rule totals. Existing records were preserved.
- Ordinary 10,000-entry previews took 11–12 s; page navigation approximately
  2 s. Response bodies contain only 50 preview rows. Summary rebuilds remain
  batched and commit with the flight records.

Run deliberately, outside the normal short suite:

```sh
D2L_RUN_CSV_CAPACITY_TESTS=1 python manage.py test csv_app.tests.test_capacity --noinput
```

These tests require PostgreSQL and refuse connection termination outside a
`test_` database. Mail delivery is replaced; models/signals, HTTP wizard,
transactions, task claiming and receipts run normally. Broker publishing is
replaced so only the test's workers execute the test batches. The 15-minute
soft/16-minute hard worker limits remain unchanged. Peak test-process RSS was
approximately 753 MiB for the near-ceiling file; this includes retained fixture
and test-client data and is not a per-production-worker memory estimate.

Deployment: allow multipart overhead at the reverse proxy, for example
`client_max_body_size 25m;` in the appropriate Nginx server/location, validate
with `nginx -t`, and reload when deploying. Verify worker memory headroom and
request timeouts on the actual production machine. These local acceptance
checks are not a production load test or justification to increase concurrency.
Django's general request-body limit is not raised: file uploads spool through
the existing upload handlers, and correction/record forms remain paginated.
