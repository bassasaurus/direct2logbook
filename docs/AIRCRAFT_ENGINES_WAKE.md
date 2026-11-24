# Aircraft engines and ATC wake classes: Step 3

## Decisions and sources

Engine tracking is an application summary feature, not a general requirement to
select an engine type in a pilot logbook. The category relationships follow
[14 CFR 1.1](https://www.ecfr.gov/current/title-14/chapter-I/subchapter-A/part-1/section-1.1).
Airplane, Rotorcraft, Powered-Lift and Airship entries require exactly one of
Piston, Turbine or Electric when creating/changing the relevant information.
Glider and Balloon hide engine selection and normalize their tracked engine
flags to false on form/API writes. Gliders have a separate Self-launch capable
checkbox; it does not establish an endorsement or select a launch method for
every flight.

The four weight choices are **ATC wake classes**, not Part 1 Small/Large or
airman class ratings. Their source is the
[FAA Pilot/Controller Glossary, Aircraft Classes](https://www.faa.gov/air_traffic/publications/atpubs/pcg_html/glossary-a.html):

- Small: maximum certificated takeoff weight of 41,000 lb or less.
- Large: more than 41,000 lb and less than 300,000 lb.
- Heavy: capable of takeoff weights of 300,000 lb or more.
- Super: the specified Super designation (currently A380-800), not a guessed
  numerical threshold.

No exact weights are inferred from type names. Light-Sport is not offered as a
weight or equipment choice. It has separate certification rules and is deferred
until requested.

## Database audit and migration

The local production-copy audit before implementation found 28 aircraft:
13 Small, 9 Large, 2 Medium, 4 with no weight selected, and **zero Light-Sport**
selections. All engine selections were unambiguous: 11 Piston and 17 Turbine.
These are local-copy observations, not a separate production audit.

Migration 0078 checks the database it is actually migrating before dropping any
columns. It refuses to continue if Light-Sport selections or conflicting old
weight selections are found. Within the migration transaction it then:

1. Converts Medium selections to Small; leaves missing weights unassigned.
2. Rebuilds the four wake summaries from dated flights and imported balances,
   excluding simulator duration; retires Medium/LSA summary groups.
3. Removes the obsolete Medium/Light-Sport aircraft fields.
4. Adds Electric tracking to Aircraft/Power and self-launch capability to Aircraft.

The data conversion does not automatically reverse on a populated database:
original Medium selections cannot be reconstructed from Small. Restore a
verified backup for a full rollback. Empty-database reversal remains available
for isolated historical migration tests. Never bypass the destination audit to
drop unexpected data.

## Compatibility justified by the existing records

Unchanged aircraft revisions retain their installed-app fingerprint: unused new
false fields are omitted from hashing, and retired false fields retain their
old hash representation. On the audited local copy, **only the two actually
recategorized aircraft changed revision**. The 26 unaffected aircraft retained
their exact revisions.

The API accepts a write-only Medium alias for older payloads and maps it to
Small. It is not a database field or a returned choice. No Light-Sport alias or
new Light-Sport UI is introduced. Edits queued against a genuinely changed
aircraft continue to use the existing conflict-resolution flow.

## Verification and reporting

The local migration's before/after fingerprints matched for Flight, Imported,
TailNumber, Total and Stat. The two Medium aircraft changed to Small;
no flight records, durations or overall/per-type summaries were rewritten.
Four unknown weights remain for user review. Electric power summaries use the
same PIC/SIC convention as the existing engine summaries, while excluding
simulator sessions and the categories whose engine selection is hidden.

Tests exercise the real historical schema migration, the destination guard,
engine requirements, Electric totals, unchanged revision hashes, legacy Medium
payloads, the old simulator migration on its historical schema, and idempotent
current summary rebuilding. Web and mobile retain the same form order and
conditional engine logic.


## Equipment rules and retired Simple choice

Public web/mobile forms and API/admin normalization use the same matrix:

| Category | Equipment choices |
| --- | --- |
| Airplane | Type Rating Required, Tailwheel, Complex, High Performance |
| Rotorcraft (Helicopter/Gyroplane) | Type Rating Required |
| Powered-Lift | Type Rating Required, automatically true and locked |
| Glider | None; Self-launch capable remains a separate option |
| Lighter-Than-Air (Balloon/Airship) | None |

Changing category clears inapplicable equipment flags. Optional equipment can
all be unchecked; absence of endorsements is not an aircraft configuration error.
Type-rating requirements for a particular airplane or rotorcraft remain user
selected; ATC wake classes must not be used to infer the 12,500 lb type-rating
threshold. Powered-Lift is handled separately under 14 CFR 61.31(a)(3).

The Nov 24, 2026 local audit found 28 aircraft, all Airplane. Simple was true on
6 aircraft, representing 720 actual flights and 1,136.0 hours; the three stored
Simple summary rows reconcile to 1,136.0 hours. There were no imported Simple
balances or non-airplane aircraft to backfill.

Simple is retired from editable forms, detail displays, and visible web/PDF
endorsement summaries. Its database field, legacy API representation, and
historical summary calculation remain intact. Normal airplane edits preserve
an existing Simple flag even when a request omits or attempts to change it;
new aircraft do not acquire one. Changing to a non-airplane category clears it.
Mobile retains that existing hidden metadata in offline edits. No schema or
production-data cleanup is required for this change.
