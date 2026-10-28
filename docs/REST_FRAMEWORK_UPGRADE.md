# Django REST Framework 3.18.3

Upgrades DRF from 3.16.0 to 3.18.3 on Django 5.2.18 / Python 3.12.16.

The upstream 3.18.2 security fixes bound Accept-header negotiation
(GHSA-33wh-fxxf-88vv), reject non-text Content-Type charsets
(GHSA-3547-9m27-7rxg), and make admin TokenProxy deletion revoke the actual token
(GHSA-xw6w-gcfp-cf8m). 3.18.3 also fixes an accidental content-negotiation API change.
The upgrade includes JSON request-size enforcement introduced in 3.17.2.

## Mobile API compatibility

DRF 3.18 changes list-serializer validation errors from a list of row errors to
an index-keyed dictionary. Flight approach validation explicitly converts these
row errors back to the existing mobile API list format, preserving empty entries
for valid rows. It does not enable DRF's deprecated global compatibility setting.
Non-row validation errors retain their original structure.

Authentication, endpoint URLs, pagination, date format (MM/DD/YYYY), ownership
checks and successful response structures are unchanged. Malformed requests may
now be rejected earlier. Negotiation processes a bounded header prefix and number
of alternatives; it does not reject every header that exceeds those limits.

## Validation

Existing API tests cover flight/aircraft/registration ownership, spoofed owners,
cross-user nested approaches, numeric validation and serialization.
New regressions exercise actual endpoints for JSON/token authentication,
bounded Accept negotiation, unsupported charsets, JSON upload limits and token
revocation through TokenProxy. A nested-approach regression checks the mobile
error list and verifies that invalid input does not save a partial approach.

## Deployment

After committing, merging and pulling this branch on production:

```bash
cd /home/blakepowell/app
/home/blakepowell/venv312/bin/python -m pip install -r requirements.txt
/home/blakepowell/venv312/bin/python -m pip check
/home/blakepowell/venv312/bin/python manage.py check
/home/blakepowell/venv312/bin/python manage.py migrate --plan
/home/blakepowell/venv312/bin/python manage.py collectstatic --noinput
sudo supervisorctl restart logbook celery
sudo supervisorctl status logbook celery
```

No application model changes are included. Review the migration plan rather than
assuming there are no unrelated pending migrations. Collectstatic updates DRF's
browsable API assets as well as application assets.

Verify mobile sign-in, list/read flight records and create/edit one disposable
flight using aircraft and registrations owned by that user. Check Sentry for new
API errors. Preserve the prior deployment revision and requirement pin for rollback.

## Sources

- https://www.django-rest-framework.org/community/release-notes/
- https://pypi.org/project/djangorestframework/3.18.3/
