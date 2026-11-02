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
