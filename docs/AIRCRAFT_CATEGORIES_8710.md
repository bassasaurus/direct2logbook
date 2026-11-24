# Aircraft categories/classes: Step 2

The registry in `flights/aircraft_classification.py` represents pilot category
and class ratings under [14 CFR 61.5(b)](https://www.ecfr.gov/current/title-14/chapter-I/subchapter-D/part-61/subpart-A/section-61.5).
It does not represent aircraft certification categories such as Normal or
Transport, engine technologies, or the pilot's qualifications.

| Category code | Category | Class codes |
| --- | --- | --- |
| A | Airplane | SEL, MEL, SES, MES |
| R | Rotorcraft | HELO, GYRO |
| GL | Glider | Empty string; no separate class selection |
| PL | Powered-Lift | Empty string; no separate class selection |
| LTA | Lighter-Than-Air | BALLOON, AIRSHIP |

These five categories match the category rows in [FAA Form 8710-1 Section III](https://www.faa.gov/documentLibrary/media/Form/FAA_8710-1_03-2026_v12_final.pdf).
Powered Parachute and Weight-Shift-Control are not added in this step.

## Forms and API

- Both forms start with Category/Class, then Aircraft Type, Engine, equipment
  options and Weight Category.
- New aircraft require Category and a compatible Class for A/R/LTA. Glider and
  Powered-Lift hide Class and store an empty string, displayed as “Not applicable.”
- On web/mobile, changing Category clears an incompatible Class. Save is disabled
  until the resulting classification is valid. Server validation independently
  rejects missing, incompatible and inapplicable classes.
- Existing incomplete classifications remain editable when classification fields
  are unchanged. Changing classification requires a valid combination. No
  automatic backfill or new database check constraint is introduced.
- The admin uses the same classification validation. Its standard controls still
  render independently of the public website's conditional JavaScript.
- Existing category/class codes, API fields, revisions and protocol versions are
  preserved. The model-state migration changes choices and `blank` only; it does
  not rewrite existing aircraft, flights or imports.
- Editing classification explains that the aircraft's existing flights/totals
  will be regrouped. Public web/API updates commit classification and summary
  refreshes in one transaction.

## Summary integrity

The existing Total/rolling filters now use the registry. The new summary keys
are `GL`, `PL`, `BALLOON`, `AIRSHIP`; the previous keys retain their meaning.
Changing classification refreshes all affected saved category/class totals,
including clearing the previous group's values. Actual flight time, simulator
time and imported balances retain the existing calculation rules. No flight or
tailnumber needs to be rewritten to change its aircraft's classification.

The full new IACRA cells, launch/flight counts and expanded summary presentation
remain later stages. Existing CSV creation of incompletely classified aircraft
is deliberately preserved.

## Step 2 boundary

Engine and weight fields and validation are unchanged. Consequently the new
categories still encounter the existing engine/weight requirements in this
intermediate development state. Removing those requirements where inappropriate
(including Glider/Balloon), self-launch capability and additional propulsion
decisions are not implemented or inferred in Step 2. Do not treat this stage as
the completed category-aware aircraft form release.

The subsequent engine/wake implementation is documented in
`AIRCRAFT_ENGINES_WAKE.md`; the paragraph above describes the Step 2 checkpoint.

## Verification

Tests cover the full category/class matrix, conditional controls, incomplete
legacy records, field errors through sync, idempotent retries, regrouping across
all new categories, unchanged source records and transaction rollback. The
Step 1 read-only audit understands the new registry for subsequent baselines.
