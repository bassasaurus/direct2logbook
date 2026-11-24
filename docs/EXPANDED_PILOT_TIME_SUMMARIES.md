# Expanded category/class summaries and IACRA

`home/pilot_time.py` supplies the web IACRA tab and the mobile stats API from the
same account-scoped grouped queries. This is a read-only report; no migration,
reclassification, source-record rewrite, or daily cron change is required.

## Categories and classes

The report supports the five categories represented in
[FAA Form 8710-1 Section III, March 2026](https://www.faa.gov/documentLibrary/media/Form/FAA_8710-1_03-2026_v12_final.pdf):
Airplane, Rotorcraft, Powered-Lift, Glider and Lighter-Than-Air. Class totals cover
SEL/MEL/SES/MES, Helicopter/Gyroplane, and Balloon/Airship. Glider and Powered-Lift
have no separate class choice.

Compact summaries and the mobile report omit unrepresented categories/classes.
The web IACRA tab always displays the full Section III form: all eight aircraft/
device rows, all airplane/rotorcraft/lighter-than-air class sections, all device
class rows, and both flight-count rows. Empty applicable cells show zero;
nonapplicable cells remain shaded. Known unavailable imported breakdowns retain
their dash. Categories/classes belonging to saved aircraft remain available in
the mobile IACRA report even before the first flight. Totals
cards/rows retain their nonzero filtering, including simulator-only balances.
A 0.1-hour balance is shown rather than excluded. API identifiers remain stable;
`display_name` supplies readable labels for the new categories.

## Calculations

- Aircraft hours and their PIC, SIC, Solo, Instruction, instrument, XC and night
  breakdowns exclude all simulator sessions.
- Recorded night hours are summed as decimal hours; night landings supply the
  takeoff/landing counts under the existing user convention.
- Each actual glider Flight row is one flight and one launch. Its selected launch
  method supplies Aerotow, Ground Launch or Self-launch counts. Landings do not
  multiply launch counts. PIC and Dual counts independently reflect their flags;
  a flight with both flags still counts once in Total flights.
- Lighter-Than-Air PIC/Dual flight counts also use individual Flight rows. Glider
  launch methods do not apply to these rows.
- Imported balances contribute their explicitly stored hours and landing counts,
  but never inferred flight/launch counts. If imported balances contain XC, night
  hours or night landings without their joint role breakdowns, the affected
  combination cells display a dash rather than a guessed or partial total.
- FFS/FTD/ATD rows and device class breakdowns use separately classified simulator
  sessions. Unclassified simulator hours remain in existing Simulator totals;
  they are not assigned an inferred device qualification. Simulator hours in
  imported balances are not treated as aircraft flight hours.
- Section III's shaded cells remain not applicable. A dash denotes unavailable
  information, not zero. This report does not determine certification eligibility
  or calculate new simulator training credit.

## Mobile

`GET /api/mobile/stats/` adds `iacra` (category rows, class totals, flight/launch
counts, device classes and a source note) without changing the existing version-1
fields. Mobile formats these server values, without deriving hours or counts.
The report uses the existing account-scoped offline stats snapshot. An expandable
IACRA card contains category breakdowns and class totals; Glider's ordinary totals
card also shows flight/launch counts when expanded. Prior cached snapshots remain
readable and obtain the report at their next refresh.

## Verification

Tests reconcile the new category summaries against individual and imported
records, cover all launch methods, edits/deletions, overlapping crew flags,
simulator exclusion, account isolation, web/API parity, missing categories,
malformed snapshots and durable offline snapshot storage. The report uses five
SELECTs regardless of aircraft count.

## Section III Instrument hours

For individual aircraft flights, Instrument combines Actual Instrument and
Simulated Instrument (hood time). Each field is summed independently with
blank treated as zero. FFS, FTD and ATD sessions remain excluded from aircraft
rows and report their instrument time in their own device rows. This changes
only the shared Section III report; the underlying Actual Instrument and
Simulated Instrument fields and their separate logbook totals remain intact.
Existing imported-balance handling is unchanged; no missing device breakdown
is inferred from aggregate balances. Web and mobile receive the same report,
and mobile caches the supplied values without calculating them on-device.
