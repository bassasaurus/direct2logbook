# Sentry SDK upgrade

This branch pins sentry-sdk 2.73.0 (Python 3.10 supported) and preserves the existing
Django and Celery integrations and send_default_pii setting. Error reporting stays
disabled under DEBUG or an empty SENTRY_DSN. Tracing, profiling and Sentry Logs are
explicitly disabled. Existing error logs/breadcrumbs keep their default integration.

SENTRY_DSN can override the existing project DSN; its default retains production
reporting without an .env change. SENTRY_ENVIRONMENT defaults to production when
DEBUG is false. Local verification uses an in-memory transport and sends nothing
to hosted Sentry. Live delivery still needs the production check below.

After merging and pulling on the server, install the pinned dependency before
restarting Django and Celery:

```sh
cd /home/blakepowell/app
/home/blakepowell/venv/bin/python -m pip install 'sentry-sdk==2.73.0'
/home/blakepowell/venv/bin/python -m pip check
sudo supervisorctl restart logbook celery
sudo supervisorctl status logbook celery
```

Send one deliberate informational event without breaking a web request:

```sh
/home/blakepowell/venv/bin/python manage.py shell -c "import sentry_sdk; event_id = sentry_sdk.capture_message('Sentry SDK upgrade verification', level='info'); sentry_sdk.flush(timeout=10); print('Verification event ID:', event_id)"
```

Confirm that exact event ID appears in the hosted project with the production
environment and SDK version 2.73.0. A printed event ID alone does not establish
server acceptance. If missing, check network/TLS/DSN and Sentry filters/quotas.
The certificate bundle in this project's requirements is old; investigate it if
TLS fails rather than disabling certificate checks.

The upgrade does not add backup cron check-ins. Configure and instrument the
backup monitor separately, including start, success, error and missed-run alerts.
No migrations or collectstatic are needed for this dependency/configuration change.

Rollback: revert this branch, reinstall sentry-sdk==0.16.3, and restart both
Supervisor services. Dependency changes must match the checked-out code.
