# Database constraint audit

Date: 2026-11-15. Branch: `audit/database-constraints`.

This is an audit, not a schema change. Findings were checked against the local
PostgreSQL catalog (`pg_constraint`, `pg_indexes`), current Django models and
shared form/API validators. Four database probe tests ran in a disposable test
database; it was destroyed afterward. No application or production records were
modified. Production schema/data were not inspected in this audit.

## What PostgreSQL currently enforces

| Area | Actual database protection |
| --- | --- |
| Aircraft | Exact `(user_id, aircraft_type)` uniqueness; at most one default aircraft per user via a partial unique index. |
| Tailnumbers | Exact `(user_id, registration)` uniqueness. The same registration is allowed for another user. |
| Flights | Non-null date, owner, aircraft and tailnumber references; valid foreign-key targets; nonnegative day/night landing counts. |
| Profiles and billing provisioning | One row per user through unique user foreign keys. |
| Mobile sync | Unique `(user_id, operation_id)` receipts, providing a database backstop against duplicate acknowledgments. |
| Stripe webhook receipts | Unique event ID via the primary key. |
| PDF requests | Unique task ID and nonnegative render attempt count. |
| Airport sources | Unique non-null OurAirports source ID; unique `(airport, code, kind)` aliases. Multiple null source IDs are permitted. |
| Accounts | Unique username. `auth_user.email` is not unique. Allauth email rows have `(user_id, email)` uniqueness, one primary row per user, and uniqueness of verified email values. |
| Field storage | SQL types, varchar length, numeric precision, NOT NULL and declared foreign keys are enforced independently of forms. |

Aircraft and tailnumber uniqueness is case-sensitive in the inspected database:
`A320`/`a320` and `N123A`/`n123a` were both accepted by probe tests. There are no
functional uppercase/trim unique indexes on those fields. Normalizing in an app
path does not make other writing paths case-insensitively unique.

## Rules that are not database constraints

| Rule | Current gap |
| --- | --- |
| Required text | `NOT NULL` rejects NULL, but permits an empty or whitespace-only aircraft type, registration or route. `blank=False` is validation metadata. |
| Required duration | `Flight.duration` is nullable even though it is required by normal entry flows. |
| Positive hours | Duration, night and instrument fields have no nonnegative database checks. Negative values were accepted by direct updates. Landing counts do have checks. |
| Aircraft selections | Category/class choice membership and compatibility, exactly one engine, and exactly one weight selection are application rules. Invalid strings and conflicting booleans were accepted by probes. |
| Tailnumber operating rules | All three booleans allow NULL. No check requires exactly one of Part 91/135/121. All false/null or multiple true values can be stored. |
| Flight combinations | Role selection, Solo requiring a landing, and Sim/XC exclusion have no database checks. |
| Ownership and matching | Foreign keys require existing rows, but do not require the aircraft/tailnumber to belong to the flight owner, or the tailnumber to match the flight aircraft. Cross-owner links were accepted by probes. Form/API ownership checks remain important. |
| Reminder validity | Kind/crew choices, positive targets, required fields by kind and company date ordering are form/API rules, not database checks. Invalid kind and negative target were accepted by probes. |
| Summary row identity | Stat and Total have no unique constraint for user/type or user/total category. Duplicate logical summary rows are not prevented by PostgreSQL. |
| Flight duplicates | No unique constraint prevents repeated flights. Such entries may be legitimate; do not introduce route/date/duration uniqueness blindly. |

`save()` does not automatically run Django `full_clean()`. In this project the
shared validators in `flights/record_validation.py` are called by web forms and
serializers, not by a database trigger. `QuerySet.update()`, bulk operations and
SQL do not inherit those form rules. Foreign-key existence also does not provide
row-level user authorization.

Some new rules intentionally apply only on creation or when relevant fields
change, preserving older logbook entries. An unconditional database check would
change that policy and can reject an unrelated edit to an older invalid row.

## Existing local data considerations

Read-only aggregate queries found one tailnumber with no selected operating rule
and three with multiple selected rules. They found no empty aircraft types,
empty registrations, empty routes, null flight durations, cross-owner links or
flight/tailnumber aircraft mismatches. These counts describe local data only.
No cleanup was attempted and no operating rule was guessed.

## Recommended order for hardening

1. Inventory the production schema and aggregate invalid data before migrations.
2. Add low-ambiguity checks: nonblank trimmed identifiers, nonnegative logged
   hours, and case-insensitive uniqueness after a duplicate review.
3. Decide how legacy aircraft/operating-rule/flight-role entries should behave;
   correct records explicitly before enforcing selection checks. Do not turn
   nullable booleans into required booleans without choosing how old NULLs map.
4. Assess owner/type matching using composite foreign keys or carefully designed
   triggers; ordinary row CHECK constraints cannot validate other table rows.
   Continue enforcing ownership in every application path meanwhile.
5. Review summary-row cardinality and repair duplicates before unique constraints.
6. Add reminder kind-dependent checks once handling deleted aircraft is decided
   (`Reminder.aircraft` currently uses SET_NULL).

No need to replace legitimate blank optional times with zero. Nonnegative checks
can allow NULL, preserving the zero-to-blank cleanup and existing aggregate logic.

## Verification

Four disposable probe tests passed:

- Exact uniqueness, one-default constraint, required date, nonnegative landings,
  foreign-key existence and varchar length rejected invalid writes.
- Empty required text, nullable duration and invalid aircraft selections were accepted.
- Case variants and cross-owner foreign-key combinations were accepted.
- Negative flight times, invalid flight combinations and malformed reminder data
  were accepted.

These probes establish the current boundary; passing here does not mean the
accepted invalid inputs are desirable. No migrations or production deployment
are included.

Reference: [Django field options](https://docs.djangoproject.com/en/5.2/topics/db/models/)
and [model instance validation](https://docs.djangoproject.com/en/5.2/ref/models/instances/).

## First hardening pass (prepared on this branch)

Local and production read-only preflight checks found no empty aircraft types,
registrations or routes, no negative logged or imported hours, and no
case-insensitive duplicate aircraft types or registrations per user. The checks
found aircraft ID 148 with blank category/class in both databases; classification
constraints remain deferred until that cleanup is confirmed. No user records
were automatically corrected or deleted.

Migration `0068_core_record_constraints` adds:

- Non-whitespace aircraft type, tailnumber registration and flight route checks.
- Per-user case-insensitive aircraft type and registration unique indexes.
- Nonnegative Flight duration/night/instrument/simulated-instrument and Imported
  logged time totals. NULL and zero remain valid where currently permitted;
  summary/rolling fields and selection rules are outside this pass.

The migration performs a frozen preflight before any schema changes and aborts
with sample record IDs if conflicts appear. It runs atomically on PostgreSQL.
It does not uppercase, merge, delete or rewrite any records. The new indexes
replace the previous case-sensitive uniqueness constraints.

Before applying it, run:

```sh
python manage.py check_record_integrity
python manage.py migrate --plan
```

The first command is read-only and exits unsuccessfully when blockers exist.
Normal form/API writes also check case-insensitive duplicates to provide a field
error instead of relying solely on the database rejecting the write. Database
constraints remain the final protection against concurrent duplicate writes.

Verification for this pass:

- Full Django suite: 744 tests passed, including direct database rejection,
  per-owner uniqueness, optional NULL/zero times, form/API errors and a historical
  migration test proving dirty data aborts without rewriting records.
- `makemigrations --check --dry-run`: no changes detected.
- Local migration applied successfully. PostgreSQL row-content fingerprints and
  counts were identical before and after for Aircraft (27), TailNumber (528),
  Flight (3613) and Imported (0). The preflight passed again afterward.
- Production was inspected read-only; no migration or production write was run.

## Classification follow-up

At the user's explicit request, test aircraft ID 148 (DA62) was deleted locally
and in production after checking for linked records. Local deletion removed only
the aircraft. Production deletion removed the aircraft and its one unused
linked tailnumber. No flights, imported summaries or reminders were linked or
deleted. Both databases then had no blank aircraft category/class fields.

Category/class database constraints remain deferred by user choice: CSV imports
currently create incomplete aircraft types for later completion. The existing
CSV workflow must stay unchanged until the import-guide/workflow work is done.
No category/class migration or CSV behavior change was introduced.

## Unique summary-row follow-up

A read-only local/production check found no duplicate `(user, stored summary
key)` groups in any of the six summary tables. An additional case/whitespace
and normalized Total-category audit also found no duplicate logical groups.

| Table | Per-user unique key | Local rows | Production rows |
| --- | --- | ---: | ---: |
| Stat | aircraft_type | 25 | 27 |
| Total | total | 43 | 41 |
| Power | role | 18 | 21 |
| Regs | reg_type | 18 | 21 |
| Endorsement | endorsement | 16 | 19 |
| Weight | weight | 10 | 11 |

Migration `0069_unique_summary_rows` adds unique constraints for those exact
stored keys. This matches the existing summary writers' `get_or_create()` lookup
fields and provides database protection for concurrent creation. It does not
change key spelling, merge rows, recalculate amounts or restrict the same key
belonging to different users. Case/whitespace normalization of summary labels is
outside this migration.

A frozen preflight checks every table before adding any constraints. If duplicate
groups are found, it aborts atomically with sample record IDs for review. The
read-only `check_record_integrity` command now checks these groups too.

Targeted tests verify inserts and updates cannot duplicate a key, another user
can use the same key, repeated/concurrent `get_or_create()` reuses one row,
normal flight saves/deletes keep the correct totals, and dirty historical data
aborts the migration without rewriting either balance.

Summary constraint verification: all 748 Django tests passed. Migration 0069 was
applied locally; row counts and PostgreSQL fingerprints covering every column of
all six summary tables matched before and after. No totals or summary rows were
rewritten. Production remains unchanged; its duplicate audit was read-only.

## Reminder-validity follow-up

Read-only audits found all four local reminders and the one production reminder
valid before introducing these constraints. No goals, dates, labels or dismissal
states were repaired or rewritten.

Migration `profile.0015_reminder_validity` enforces:

- A supported reminder kind and crew-position value.
- Any supplied target must be positive; every milestone requires a target.
- Expiration reminders require a date and a non-whitespace title.
- Time-in-type and crew-in-type milestones require an aircraft.
- Crew-in-type milestones require PIC, SIC, Solo or Dual.
- Company milestones require a non-whitespace company name and a start date.
- An optional company end date requires a start date and cannot precede it.

Milestone titles stay optional, matching the UI's implied-title behavior. Past
expiration dates, targets already reached, and open-ended company date ranges
remain valid. Aircraft ownership is still checked by the forms/API; cross-table
ownership constraints are a separate work item.

Follow-up migration `profile.0016_cascade_aircraft_reminders` uses CASCADE for
Reminder.aircraft, as requested: removing an aircraft removes its linked
reminders as well. Reminders do not block aircraft deletion; existing protections
for linked flights, tailnumbers and imported totals still apply. Unrelated
reminders are retained. Whole-user deletion remains supported.

The migration includes a frozen, read-only preflight that aborts with sample
reminder IDs before any schema changes if an invalid row exists. The shared
`check_record_integrity` command now checks reminder validity too.

Reminder constraint verification: all 755 Django tests passed. The local reminder
migration applied successfully; full-row PostgreSQL fingerprints and counts for
all 4 reminders and 26 aircraft were unchanged. The preflight passed again
following migration. Production reminder data and schema were not changed.

Aircraft/reminder cascade verification: 56 targeted tests passed, covering model,
REST API and mobile sync deletion, replay, unrelated reminder preservation and
whole-user deletion. Migration 0016 was applied locally, with all 4 reminders and
26 aircraft unchanged by the migration itself. Production is unchanged.

## Background-job status follow-up

Read-only local and production audits found identical valid values:

- PDFRequest: 7 `sent` rows.
- CSVImportBatch: 3 `completed` and 2 `preview` rows.
- BillingProvisioning: no rows.

No unsupported values or NULL statuses were found. Background writers use the
existing model enum values. The PDF `delayed` display value is computed for the
response and is not persisted. Stripe's external subscription statuses and
Celery's own result states are outside this change.

Migrations `pdf_output.0010_valid_job_status`, `csv_app.0003_valid_job_status`
and `payments.0006_valid_job_status` add membership CHECK constraints:

| Model | Allowed persisted values |
| --- | --- |
| PDFRequest | queued, unconfirmed, processing, retrying, sending, sent, failed, delivery_uncertain |
| CSVImportBatch | preview, queued, unconfirmed, processing, completed, failed |
| BillingProvisioning | pending, processing, completed, failed |

Each migration has its own frozen preflight and stops with sample job IDs when
an unsupported value exists. No status is automatically repaired, reopened or
requeued. These checks do not impose transition order, modify timestamps, change
retry handling or enforce additional relationships between status and other
fields. Existing NOT NULL constraints continue to reject missing statuses.

`check_record_integrity` now includes job status membership. Tests cover every
enum/default value, rejected inserts and updates, atomic failure of an invalid
bulk update, and historical migrations aborting without changing payloads,
errors, task identifiers or other job data.

Status verification: all 761 Django tests passed. The three status migrations
were applied locally; complete-row PostgreSQL fingerprints and counts matched
before and after (7 PDF requests, 5 CSV batches, 0 billing provisioning rows).
No jobs or status values were changed. `makemigrations --check --dry-run`
reported no changes. Production was inspected read-only and remains unchanged.

## Matching-ownership follow-up

Read-only audits found no cross-user links locally or in production:

| Link | Local linked rows | Production linked rows | Mismatches |
| --- | ---: | ---: | ---: |
| TailNumber → Aircraft | 528 | 616 | 0 |
| Flight → Aircraft | 3613 | 3712 | 0 |
| Flight → TailNumber | 3613 | 3712 | 0 |
| Imported → Aircraft | 0 | 0 | 0 |
| Reminder → Aircraft | 1 | 1 | 0 |

Migration `flights.0070_matching_ownership` adds composite foreign keys from each
child's `(user_id, referenced_id)` to the parent's `(user_id, id)`. Supporting
unique constraints on Aircraft and TailNumber provide the referenced key pairs.
The composite foreign keys are explicit reversible PostgreSQL RunSQL operations;
Django's ordinary ForeignKey fields continue to model their single-column
relationships. Preserve these SQL constraints when changing those columns.

The constraints are DEFERRABLE INITIALLY DEFERRED, matching the existing foreign
keys. Invalid committed links and parent ownership changes are rejected, while
coherent multi-row ownership updates can complete in one transaction. Optional
NULL aircraft references on non-type reminders remain valid. Normal ORM cascade
deletion and whole-user deletion remain supported.

This does not create global aircraft/registration uniqueness, restrict pilots
by company, enforce flight aircraft/tailnumber agreement, or replace request
ownership authorization. Different users may retain their own A320/N123A rows.
Approach/Holding rows inherit ownership through their Flight; they have no
separate user field to compare in this migration.

A frozen migration preflight rejects existing mismatches with sample IDs before
adding constraints. It never guesses an owner, reassigns records or recalculates
totals. `check_record_integrity` now checks these five relationships too.

Reference: [PostgreSQL 16 foreign keys](https://www.postgresql.org/docs/16/ddl-constraints.html#DDL-CONSTRAINTS-FK).

Ownership verification: all 768 Django tests passed, including cross-user insert/
update rejection, parent-owner edits, same aircraft codes across different users,
coherent transactional transfers, user deletion, migration preflight and existing
web/API/CSV behavior. Older privacy/performance fixtures were corrected to give
each pilot their own aircraft/tailnumber rows, retaining their original privacy
and query-count assertions. The legacy deletion safeguard is still exercised in
a rollback-only transaction, since the corrupt link can no longer be committed.

The local ownership migration applied successfully. Full-row fingerprints and
counts for Aircraft (26), TailNumber (528), Flight (3613), Imported (0) and
Reminder (4) were unchanged. Preflight passed afterward and migration/model
state matched. Production was inspected read-only and remains unchanged.

## Matching aircraft/tailnumber follow-up

A read-only audit found zero aircraft/tailnumber mismatches among 3,613 local
and 3,712 production flights. No historical flight or tailnumber was reassigned.

Migration `flights.0071_matching_aircraft_tailnumber` adds a supporting unique
key on TailNumber `(id, aircraft_id)` and a reversible PostgreSQL composite
foreign key from Flight `(registration_id, aircraft_type_id)` to that pair. It
is DEFERRABLE INITIALLY DEFERRED, like the existing ownership foreign keys.

This protects both directions: a mismatched flight cannot be committed, and
reassigning a used tailnumber cannot invalidate the aircraft recorded on its
historical flights. A valid correction can change the flight's aircraft and
registration together. A deliberate multi-row correction may finish in one
transaction, but no existing data is silently rewritten by this migration.

Shared form/API validation returns a registration-field error for a mismatched
flight and an aircraft-field error if a tailnumber reassignment would break
linked flights. An unused tailnumber may still be reassigned. The existing CSV
import checks already reject registration/type mismatches.

The frozen migration preflight aborts with sample flight IDs if a mismatch is
found. `check_record_integrity` now includes this check. Different pilots may
still use the same type and registration in their own accounts.

Aircraft/tailnumber verification: all 774 Django tests passed. Migration 0071
applied locally with identical complete-row fingerprints/counts for Aircraft
(26), TailNumber (528), Flight (3613), Stat (25) and Total (43). No historical
records or totals changed. Production remains unchanged.

## Scope stopping point

Keep this work focused on demonstrated reliability/integrity risks. Additional
coordinate constraints are deferred: the airport importer already checks finite
latitude/longitude and valid ranges (`flights/airport_sync.py`). Category/class
requirements remain deferred to preserve the existing CSV placeholder workflow.
Do not broaden into further speculative constraints before shipping and observing
the changes already prepared on this branch.

## Friendly validation feedback

Web forms and mobile cards use the approved field messages for duplicates,
required fields, negative hours, unavailable references, aircraft/tailnumber
mismatches and reminder targets/dates. Web writes are atomic and retain bound
form values after database failure. Technical database details are logged,
while unexpected failures return a generic retry message. Mobile form failures
remain inline; sync errors preserve the local operation for correction/retry
and omit database diagnostics from validation feedback.

Verification: 779 Django tests passed, 206 mobile tests passed, mobile lint
passed, and makemigrations --check --dry-run reported no changes.
