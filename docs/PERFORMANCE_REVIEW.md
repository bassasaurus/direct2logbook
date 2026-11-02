# Performance review: logbook and monthly map lists

The first measurement uses synthetic records in Django's disposable test database.
It does not load-test production or measure complete browser/network render times.

## Baseline and change

| Measured component | Flights | Before | After |
| --- | ---: | ---: | ---: |
| Logbook queryset and rendered table | 1 | 5 queries | 3 queries |
| Logbook queryset and rendered table | 40 | 161 queries | 3 queries |
| Monthly queryset and registration access | 1 | 2 queries | 1 query |
| Monthly queryset and registration access | 40 | 41 queries | 1 query |

These are component query counts, excluding authentication, pagination counts,
base-template/context queries and other page work. The monthly component count
also excludes archive date-navigation queries. This is not a claim that a full
page executes only one or three queries or loads a corresponding factor faster.

The logbook fetched each flight's aircraft, registration, approaches and holds
individually while rendering. `select_related` now joins the two single-object
relations to the flight query; `prefetch_related` loads approaches and holds in
two additional queries for the displayed page. Pagination remains 40 rows.

The monthly list now joins registrations, and map generation reuses the same
owner-scoped, month-filtered queryset that the template renders, avoiding another
flight query and duplicate loading of route payloads. Map routes, ownership
filters, pagination and displayed fields keep their existing behavior.

## Regression coverage

```bash
python manage.py test flights.tests.test_query_performance flights.tests.test_monthly_map flights.tests.test_flights_CRUD
```

The query tests compare one and forty flights, check that related details still
render, and exclude another user's flight. Existing monthly-map tests check date
and owner filtering and route output. The tests print the component counts.
No migration, dependency or server configuration change is required.

## Remaining review

The home dashboard performs many independent aggregates and should be measured
separately before changing its currency/statistics calculations. Browser asset
sizes, map payload sizes, large-account indexes and production request latency
also remain outside this first change. Avoid broad caching until ownership,
freshness and invalidation requirements are clear.

## Home dashboard: repeated per-request calculations

The next pass measures the complete rendered home response with Django's test
client, synthetic owner/foreign-user flights, and three recent ASEL landings.
Unlike the earlier table-component numbers, these counts include authentication,
context and template work. Counts vary with account contents and cache warmth.

| Dashboard fixture | Before | After |
| --- | ---: | ---: |
| Three flights, one aircraft, cold Site/template caches | 77 queries | 64 queries |
| Three flights, one aircraft, warmed caches | 74 queries | 61 queries |
| Three flights, 21 aircraft, warmed caches | 114 queries | 61 queries |

Each landing-currency helper used to run twice to retrieve its count and current
flag. Each now runs once, unpacking its existing result. The medical helper runs
once instead of five times. No formulas or currency windows change, and nothing
is cached between requests. Missing aircraft registration/import information is
now found with two correlated `Exists` predicates in a single aircraft query,
keeping both child lookups scoped to the logged-in owner. Onboarding flags use
`exists()` rather than loading all aircraft, registrations or flights into memory.

Regression tests verify helper call counts, current/non-current landing results,
medical current status, onboarding flags, owner isolation, registration/import
handling, and a constant query count when adding 20 aircraft. Run:

```bash
python manage.py test home.tests.test_dashboard_performance
```

This reduces duplicate work but does not combine the many independent totals and
aggregates. It does not benchmark production latency or revise aviation currency
rules. Those are separate reviews, not implied by these query-count reductions.
