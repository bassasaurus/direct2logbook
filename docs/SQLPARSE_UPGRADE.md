# sqlparse 0.6.0

Updates Django's sqlparse dependency from 0.5.3 to 0.6.0 on Python 3.12.16 and
Django 5.2.18. No application code, models or authentication settings are changed.

The release fixes resource-exhaustion issues in lexing, grouping, comment handling
and reindentation, plus escaping in generated Python/PHP snippets. These are
library findings; the app does not expose a raw SQL formatting endpoint.
Python 3.10+ is required, which is compatible with the deployed Python 3.12 setup.

Validation includes the full Django test suite, dependency checks, migration
checks and direct checks of Django's SQL-script preparation with quoted semicolons
and PostgreSQL dollar-quoted blocks. No production database changes are required.

## Deployment after merge

```bash
cd /home/blakepowell/app
git pull --ff-only origin master
/home/blakepowell/venv312/bin/python -m pip install -r requirements.txt
/home/blakepowell/venv312/bin/python -m pip check
/home/blakepowell/venv312/bin/python manage.py check
/home/blakepowell/venv312/bin/python manage.py migrate --plan
sudo supervisorctl restart logbook celery
sudo supervisorctl status logbook celery
```

No migrations or static-asset changes are introduced. Review any unrelated pending
migrations shown by the plan. Check normal login/logbook operation and Sentry after
deployment. Keep the previous deployment revision and requirements for rollback.

## Sources

- https://sqlparse.readthedocs.io/en/stable/changes.html
- https://pypi.org/project/sqlparse/0.6.0/
