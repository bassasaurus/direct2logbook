# Staged Python 3.12 migration

**Do not install this branch's requirements into the existing Python 3.10 venv.**
Keep `/home/blakepowell/venv` and the system Python in place for rollback. Build
`/home/blakepowell/venv312` separately; do not rename or move either venv (entry-point
shebangs contain absolute paths). No production changes have been made by this work.

## What changed and why

Target Python 3.12.16, including its October 2026 security fixes. runtime.txt was
stale at 3.7.6 and is corrected, but runtime.txt does not install Python on this
native Supervisor deployment. Python 3.12 has upstream security support to Oct 2028.

- Pillow 13.0.0 addresses remaining 12.3.0 advisory matches and needs >=3.11.
- Native packages updated for Python 3.12 wheels: NumPy 2.5.4, pandas 3.1.0,
  lxml 6.1.3, psycopg2-binary 2.9.13. pandas is only imported in the legacy Flica
  scraper; that scraper was not executed (it initiates real external requests).
- six 1.17.0, python-decouple 3.8, importlib-metadata 10.1.0 and zipp 4.1.2
  replace versions relying on removed Python internals. The old six and decouple
  caused real startup failures in the rehearsal; these were fixed, not ignored.
- Stripe 5.5.0 replaces 2.49.0, whose vendored six cannot import on Python 3.12.
  Both versions default stripe.api_version to None (account default). SDK >=6
  changes API-version defaults, so that separate billing API migration is excluded.
  The SDK is still an older release; current SDK/API migration remains future work.
  Real SDK serialization tests check customer/subscription endpoint paths,
  idempotency keys, email, trial days, plan item and absence of Stripe-Version.
  No actual Stripe API calls, charges or subscription changes were made.
- Removed unused historical tooling pins from production requirements: astroid,
  pylint, typed-ast, python-jsonrpc-server, lazy-object-proxy, wrapt. No application
  imports were found. python-jsonrpc-server 0.2.0 failed to build on 3.12. Modern
  editor/linter tools should use a separate development environment rather than
  reinstalling these obsolete pins into production.
- Three application modules use raw regex strings to eliminate Python 3.12
  invalid-escape warnings without changing regex behavior.
- deploy/gunicorn_start accepts APP_VENV, defaulting to the original venv. Merely
  pulling this branch does not change a running service's interpreter.

## Local evidence and limits

An isolated CPython 3.12.16 interpreter and venv were created under /tmp; the existing
Mac Python 3.10 app environment was left unchanged. All dependency pins installed,
uv pip check passed, Django check/migration checks passed, and the full suite passed.
Actual three-worker Gunicorn Unix-socket checks returned login 200, protected
logbook 302, missing URL 404 and rejected malformed headers (400/501). Celery PDF,
CSV and billing tasks imported without broker connection. Native imports and a
verified public HTTPS request passed. The suite includes real PDF/PNG signature
rendering. Updated native binary wheels also downloaded for Linux x86_64 / CPython
3.12 compatible with Ubuntu 22.04; they were not executed on the Mac.

Re-audit reports no current matches for Pillow 13, lxml, NumPy, pandas, psycopg2,
Stripe, importlib-metadata and zipp. Ten other packages remain flagged; this migration
is not a claim that the whole environment is vulnerability-free. Full provider
sign-in, email delivery, S3 access, Linux libraries and production billing account
behavior still require appropriate smoke verification. Do not make test charges.

## 1. Record rollback state on production BEFORE pulling

```sh
cd /home/blakepowell/app
git rev-parse HEAD > /home/blakepowell/app-before-python312.txt
cp requirements.txt /home/blakepowell/requirements-before-python312.txt
cp /home/blakepowell/gunicorn_start /home/blakepowell/gunicorn_start.before-python312
sudo cp /etc/supervisor/conf.d/logbook.conf /etc/supervisor/conf.d/logbook.conf.before-python312
crontab -l > /home/blakepowell/crontab-before-python312.txt
```

Confirm recent verified off-server backup and rollback files. Commit/merge normally,
then pull into app. Do not run the usual old-venv pip install or switch services yet.

## 2. Install a separate interpreter/tooling environment

The server reported python3.12 not found. Use a separate tooling venv; the existing
app venv and `/usr/bin/python3` are not modified. These use official PyPI/Astral
packages and Astral's python-build-standalone runtime:

```sh
python3 -m venv /home/blakepowell/python-upgrade-tools
/home/blakepowell/python-upgrade-tools/bin/python -m pip install uv
export UV_PYTHON_INSTALL_DIR=/home/blakepowell/python-runtimes
/home/blakepowell/python-upgrade-tools/bin/uv python install 3.12.16 --no-bin
/home/blakepowell/python-upgrade-tools/bin/uv venv --python 3.12.16 --seed /home/blakepowell/venv312
/home/blakepowell/venv312/bin/python --version
```

Require Python 3.12.16. If either target venv directory already contains another
environment, stop and inspect it rather than overwriting. Do not replace system
Python, install Docker, or move the old application venv.

## 3. Install and validate while old services keep running

```sh
cd /home/blakepowell/app
/home/blakepowell/venv312/bin/python -m pip install --only-binary=Pillow,numpy,pandas,lxml,psycopg2-binary,cffi,cryptography -r requirements.txt
/home/blakepowell/venv312/bin/python -m pip check
/home/blakepowell/venv312/bin/python manage.py check
/home/blakepowell/venv312/bin/python manage.py makemigrations --check --dry-run
/home/blakepowell/venv312/bin/python manage.py migrate --plan
bash -n deploy/gunicorn_start
APP_VENV=/home/blakepowell/venv312 bash deploy/gunicorn_start --check-config
```

Require all checks to pass; no app model migrations are expected. Review any
unrelated pending migrations instead of applying blindly. A config check imports
the app but does not start a worker, bind the live socket or execute Celery jobs.
Do not run another normal Gunicorn instance against the live production socket.

## 4. Cut over explicitly

Wait for active CSV/PDF/billing tasks to finish. Preserve queued RabbitMQ messages.
Supervisor already uses a warm shutdown timeout for Celery. Install the reviewed
startup script at the same path (its default remains the old venv until configured):

```sh
install -m 750 deploy/gunicorn_start /home/blakepowell/gunicorn_start
```

Edit `/etc/supervisor/conf.d/logbook.conf`:

- Under `[program:logbook]`, add `environment=APP_VENV="/home/blakepowell/venv312"`.
  If an environment line exists, merge this key and preserve its other variables.
  Keep command=/home/blakepowell/gunicorn_start and all other options.
- Under `[program:celery]`, change ONLY the executable path to
  `/home/blakepowell/venv312/bin/celery`; retain all current worker arguments.

In `crontab -e`, replace `/home/blakepowell/venv/bin/` with
`/home/blakepowell/venv312/bin/` for this application's jobs. Keep every schedule,
command, recipient and log redirection. This includes Stripe webhook checks,
CSV cleanup, PDF reconciliation, scheduled backups, backup freshness and disk
checks. Do not leave monitors silently using the old runtime.

```sh
sudo supervisorctl reread
sudo supervisorctl update logbook celery
sudo supervisorctl status logbook celery
crontab -l
```

The update applies changed configuration and restarts the affected groups; a plain
restart would not load the new environment/command settings. Require both RUNNING.
Expect a brief restart window. No Nginx changes or collectstatic are needed.

## 5. Verify before retiring anything

- Confirm normal HTTPS sign-in/home/logbook/admin and configured social sign-in.
- Request a PDF, confirm delivery and signature, and check CSV task completion.
- Check Sentry events/uptime and absence of new worker errors.
- Run a manual backup via the NEW venv and confirm Sentry's successful check-in:

```sh
/home/blakepowell/venv312/bin/python /home/blakepowell/app/manage.py scheduled_database_backup
/home/blakepowell/venv312/bin/python /home/blakepowell/app/manage.py check_disk_space
```

Check the next automatic cron runs. Existing monitors/settings/state and encryption
keys are shared and should not be reset. No user data or schema is migrated merely
by changing Python. Retain old venv and interpreter for rollback until the new
runtime and scheduled jobs have been observed successfully.

## Rollback

Restore the saved Supervisor configuration and startup script, restore the saved
crontab, and check out the recorded pre-upgrade app commit. Do not reinstall the
new requirements into the old venv. Run Supervisor reread/update for logbook/celery,
then verify HTTPS and scheduled jobs. Keep the new venv for diagnosis. There are no
planned schema migrations to reverse in this branch.

References:
- https://www.python.org/downloads/release/python-31216/
- https://devguide.python.org/versions/
- https://docs.astral.sh/uv/guides/install-python/
- https://github.com/stripe/stripe-python/wiki/Migration-guide-for-v6
- https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html
