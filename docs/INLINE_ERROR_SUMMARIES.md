# Inline error notices

The logbook, flight detail, aircraft detail and tailnumber detail pages now show
record errors above the page content using Bootstrap danger alerts. Only automatic
error modals were replaced: welcome/onboarding, privacy and form dialogs retain
their current behavior. Error notices disappear when the underlying errors are
corrected; they do not require a dismiss button or a modal script.

## Logbook

The existing error predicate is now shared between query filtering, row styling
and the flight-detail notice. It covers persisted route, ambiguous-airport,
aircraft, registration and crew warnings, plus missing/sub-0.1 duration.

Affected rows have red text and a red outlined **Update** button linking directly
to their owner-protected edit form. Row backgrounds are not made red. Healthy rows
retain **View**. A collapsible red area above the table lists the first ten affected
flights and their individual errors, with direct edit links. Its count covers all
of the logged-in user's flights, including errors beyond the visible page.

**Show flights needing attention** switches to an errors-only list. Normal
pagination remains available and preserves that filter. The summary is bounded
at ten records so a long list of errors does not replace the logbook; the filtered
list provides access to every affected flight. The summary uses two additional
queries (count and bounded list) rather than lookups per error. Existing batched
loading for the main table is preserved. Another user's records are never included.

Messages and route strings are escaped normally by Django templates.

## Detail pages

- Flight: all stored warnings plus duration errors.
- Aircraft: existing power/configuration/weight checks plus category, class and
  missing-tailnumber notices, with an Add a tailnumber link.
- Tailnumber: the existing missing FAR 91/135/121 selection warning.

These notices appear above the record and map instead of opening an overlay.
The existing contextual Update action has a red outline when the notice is
present and is a plain blue link otherwise. Delete stays red and the same text
size in both states, with a 10px gap between the actions. The notices do not
duplicate the Update action.
They flag record completeness/airport lookup issues; they do not certify the
operational validity of a flight, prevent saving, or change logged time.

## Route warning correction and existing records

Airport checks now collect every missing/ambiguous code across a route before
saving its warnings. A valid later leg cannot erase an earlier warning, and a
repeated bad code is listed once. Airport lookups are restricted to the route's
codes instead of loading the whole airport table. Correcting a route clears its
old warning on save.

Existing records with missing or stale warnings need one recheck after deployment:

```bash
cd /home/blakepowell/app
/home/blakepowell/venv312/bin/python manage.py refresh_flight_route_warnings --dry-run
/home/blakepowell/venv312/bin/python manage.py refresh_flight_route_warnings
```

This is manual maintenance, not a new cron task. To restrict it to one account,
append `--user-id` and the numeric user ID. The command batches airport lookups,
updates only `map_error` and `duplicate_error`, and does not call Flight.save(),
recalculate totals, send mail, or publish jobs. It checks that the route has not
changed before applying each update, protecting concurrent flight edits. Repeated
runs with unchanged airport data are safe; dry runs do not write anything.

## Validation and deployment

```bash
python manage.py test flights.tests.test_inline_errors flights.tests.test_query_performance
python manage.py makemigrations --check --dry-run
```

No database migration or dependency change. Deploy through the existing workflow,
which collects the updated CSS. After deployment, run the optional recheck above
and inspect a flagged logbook row and each detail-page notice. Automated tests
cover ownership, pagination, output escaping, notice presence/absence, route-leg
ordering, ambiguity, clearing after correction, and safe warning backfill.
