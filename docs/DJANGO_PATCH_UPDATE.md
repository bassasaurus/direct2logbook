# Django 5.2 security patch update

Pin Django to 5.2.18, the current published patch release on the 5.2 LTS series,
from the base 5.2 release. Python 3.10 is compatible; existing asgiref, sqlparse
and typing-extensions pins meet its declared requirements. No other dependencies
are upgraded in this change. Remaining dependency advisories require separate fixes.

Reference: https://docs.djangoproject.com/en/5.2/releases/5.2.18/

Local validation: pip check, full Django suite, makemigrations --check --dry-run,
and migrate --plan. No model changes or planned local migrations were detected.
Local tests do not validate production's exact data, services or proxy configuration.

After merging/pulling on the production server, install requirements before
restarting both services:

```sh
cd /home/blakepowell/app
/home/blakepowell/venv/bin/python -m pip install -r requirements.txt
/home/blakepowell/venv/bin/python -m django --version
/home/blakepowell/venv/bin/python -m pip check
/home/blakepowell/venv/bin/python manage.py check
/home/blakepowell/venv/bin/python manage.py migrate --plan
```

Require Django 5.2.18. If the plan shows unrelated pending migrations, review them
before applying; this patch itself adds no application model changes. Once checks
pass, restart the existing Supervisor services:

```sh
sudo supervisorctl restart logbook celery
sudo supervisorctl status logbook celery
```

Django's packaged admin assets may have changed across patch releases. If production
serves collected Django static assets, run the normal deployment collectstatic:

```sh
/home/blakepowell/venv/bin/python manage.py collectstatic --noinput
```

Smoke-check public website/login, authenticated home, a flight list/detail, admin,
and one PDF request through completion. Keep uptime, error and cron monitoring
active. Production requirements installation is necessary: a git pull alone does
not update the virtual environment.

Rollback: revert the pin, reinstall the previous requirements and restart both
services. The old Django 5.2 pin has known advisories; a rollback is temporary
incident mitigation, not a security-complete end state.
