# Airport country rules and per-flight confirmation

The shared resolver in `flights/airport_resolution.py` uses the airport's country
stored in MapData. It does not use browser location, IP address, account country,
or a remembered account-wide preference.

## Selection rules

- Three-character code with one distinct US airport match: select that airport
  without a warning. A US match means country, after trimming/case normalization,
  is `United States`. Other matching countries are not selected by this code.
- Several distinct US matches: ask the user to select among those US airports.
- Three-character code with no US match: ask the user to confirm the matching
  non-US airport, even when there is only one candidate.
- Four-character code: match ICAO directly, including non-US airports.
- No match: retain the unknown-code warning so the route can be corrected.

No route codes are converted or renamed. For example, with the existing data,
`BQN-BBG-LBX` selects TJBQ, KBBG and KLBX automatically. `RPLU` selects Lubang
instead. To log Lubang when a US airport matches LBX, enter its four-character
code, rather than relying on an account preference from another flight.

Entries with the same nonempty ICAO identifier count as one airport. If ICAO is
missing, only identical normalized name and coordinates are collapsed. This
avoids treating distinct locations as duplicates solely because their names are
similar. Duplicate database rows are not deleted or rewritten. A US entry for
the same ICAO airport retains the known US-country classification.

## Confirmation UI and persistence

The flight detail and edit pages show inline radio choices, airport names,
locations, and supporting ICAO identifiers. New choices have no preselected
candidate. The prominent **Confirm airports** button posts a CSRF-protected form
to an authenticated, owner-scoped endpoint. GET requests cannot save choices.

A JSON field, `Flight.route_airport_choices`, stores the original route snapshot
and airport IDs keyed by the airport's position in that route. This permits the
same code to mean different airports at different occurrences. The field is not
editable through the ordinary Flight model form or the existing API serializer.

The server validates submitted IDs against the current permitted candidates and
rejects stale route text. Confirmation locks the owned flight, then updates only
the choices, route warnings, and derived map data. It leaves route text, hours,
statistics, and other flight data unchanged. It publishes no tasks or email.

**Review airport choices** allows correcting saved manual choices. Editing any
part of the route through the model/form clears its saved choices. Confirmations
on other flights are never inherited. If a chosen airport disappears or stops
matching the rule, the next resolution requires confirmation again.

## Shared map behavior

Warnings, the pickled web `route_data`, app markers/polylines, CSV imports, and the
legacy route-save helper now use the same resolver. `get_map_data.py` consumes the
resolved `route_data`; it does not implement another selection policy. It also
tolerates missing old route data.

While any leg is unknown or awaiting confirmation, the flight's derived map
payload is empty, avoiding a made-up route through arbitrary first matches or
across a missing leg. Once all airports resolve, map geometry is rebuilt in route
order. Flight logging and time totals are not blocked by unresolved airports.

App JSON is written with QuerySet.update instead of recursively saving Flight or
temporarily disconnecting a global signal. This avoids duplicate statistics
recalculation and leaves signal registration intact on exceptions/timeouts.

## Deployment and existing records

This change requires migration `flights.0064_flight_route_airport_choices`, applied
by the deployment workflow. No new packages or external APIs are needed.

After deployment, recheck warnings and rebuild old map data with the same rules:

```bash
cd /home/blakepowell/app
/home/blakepowell/venv312/bin/python manage.py refresh_flight_route_warnings --refresh-maps --dry-run
/home/blakepowell/venv312/bin/python manage.py refresh_flight_route_warnings --refresh-maps
```

The optional `--user-id` restricts this maintenance to one account. It is not a new
cron job. The command preserves valid confirmations and does not call Flight.save
or change hours/totals. Conditional updates protect concurrent route/choice edits.
With `--refresh-maps`, all inspected map payloads are rebuilt, so reported update
counts need not be zero on a repeated run even though the results are idempotent.
Without that flag the command updates warnings only.

Old pickled/map payloads retain their previous airports until the flight is saved,
confirmed, or refreshed using this command. After a confirmation redirect, the
flight detail page rebuilds its web map cache using the saved resolution. Existing
map caches expire after one minute; fresh page loads regenerate them.

## Verification

```bash
python manage.py test flights.tests.test_airport_resolution flights.tests.test_inline_errors flights.tests.test_monthly_map csv_app.tests.test_background_import
python manage.py makemigrations --check --dry-run
```

Coverage includes the BQN/BBG/LBX cases, duplicate airport rows, non-US single
matches, direct four-character matches, multiple US candidates, per-occurrence
choices, ownership/CSRF protection, stale forms, invalid IDs, route edits, review,
web/app/CSV consistency, legacy map refresh, and map generation without recursive
Flight saves. No tests send customer mail or call a geolocation service.
