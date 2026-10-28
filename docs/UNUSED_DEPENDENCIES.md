# Remove unused production dependencies

Removes the requirement pins for jsonpickle 1.2, django-debug-toolbar 2.2 and
future 0.18.0. None has an application import or an active installed-package
dependency in the reviewed Python 3.12 environment. Debug Toolbar was absent from
INSTALLED_APPS; its disabled middleware and URL comments are also removed.

These pins matched published unsafe-deserialization, SQL-injection and
denial-of-service advisories respectively. The affected application paths were
not found to be active; removing unused software reduces the dependency surface
without introducing replacement functionality.

`__future__` and `concurrent.futures` are standard-library features and remain
unchanged. `django-picklefield` and the existing Flight.route_data database field
are separate from jsonpickle and remain unchanged. No data conversion is performed.

The three packages were explicitly uninstalled locally before running dependency
and Django checks and the full test suite.

## Deploy after merge

```bash
cd /home/blakepowell/app
git pull --ff-only origin master
/home/blakepowell/venv312/bin/python -m pip install -r requirements.txt
/home/blakepowell/venv312/bin/python -m pip uninstall -y jsonpickle django-debug-toolbar future
/home/blakepowell/venv312/bin/python -m pip check
/home/blakepowell/venv312/bin/python manage.py check
/home/blakepowell/venv312/bin/python manage.py migrate --plan
sudo supervisorctl restart logbook celery
sudo supervisorctl status logbook celery
```

Installing requirements does not uninstall removed packages. Automatic dependency
synchronization is deferred to a future CI/CD workflow. No model or static-asset
changes are included; review unrelated pending migrations if the plan shows any.

Verify login, the logbook/map and a PDF request, then check Sentry.

## Advisory sources

- https://github.com/advisories/GHSA-j66q-qmrc-89rx (jsonpickle; unsafe decoding of untrusted data remains unsafe by design)
- https://github.com/advisories/GHSA-pghf-347x-c2gj (Django Debug Toolbar)
- https://github.com/advisories/GHSA-v3c5-jqr6-7qm8 (future)
