# Gunicorn upgrade

Pin Gunicorn 26.2.0, the newest non-yanked stable package published on PyPI when
checked, replacing 19.9.0. Requires Python >=3.10. Upstream news also mentions
26.2.1/26.2.2, but neither was available in the PyPI release inventory at review;
this pin is not a claim that 26.2.0 is the newest upstream source revision.
No extra worker/parser/HTTP2 dependencies are installed.

The user supplied production Supervisor config and /home/blakepowell/gunicorn_start.
Supervisor runs the script as blakepowell, with three default sync workers bound to
unix:/home/blakepowell/run/gunicorn.sock, app directory /home/blakepowell/app and
the /home/blakepowell/venv virtual environment. These options remain supported.
The reviewed script is provided as deploy/gunicorn_start. No production files were
changed automatically.

Startup script adjustments:
- Quote paths/arguments and fail immediately if setup fails.
- Invoke the virtualenv executable directly; activation is unnecessary.
- Preserve three sync workers, socket location, name, user/group and logging.
- Omit the old forwarded-allow-ips="*"; non-IP Unix socket peers are already trusted.
- Disable the new optional control socket (--no-control-socket). Supervisor still
  manages restarts. This avoids an additional unused management socket.

Gunicorn 26.0 removed the eventlet worker. This deployment uses sync, so no eventlet
migration is needed. Keep strict request parsing; do not add permissive flags to
work around malformed requests. Unix socket access and reverse-proxy header
sanitization remain important. Nginx config was not supplied or modified.

## Local verification

- gunicorn --check-config logbook.wsgi:application
- pip check
- Django full test suite
- Actual Gunicorn worker startup, Django login 200, protected logbook 302 and 404.
- Three sync workers on a temporary Unix socket, matching production topology.
- Duplicate Content-Length rejected with HTTP 400; unsupported transfer coding
  rejected with HTTP 501. These are bounded local parser checks, not exhaustive
  request-smuggling or production-proxy tests.
- Graceful worker/master shutdown. Sentry disabled for smoke checks; no emails,
  payments or Celery jobs were submitted.
- pip-audit reports no current advisory matches for gunicorn 26.2.0. Other pinned
  dependencies still have advisories and remain separate work.

The first parser test expected 400 for unsupported transfer coding, but Gunicorn
correctly returned 501. The assertion was corrected and the smoke checks rerun.

## Production deployment

After commit/merge/pull, install the dependency before replacing the startup script:

```sh
cd /home/blakepowell/app
/home/blakepowell/venv/bin/python -m pip install -r requirements.txt
/home/blakepowell/venv/bin/gunicorn --version
/home/blakepowell/venv/bin/python -m pip check
```

Require 26.2.0. Make a copy of the existing startup script, then install the reviewed
script at the exact path Supervisor already launches:

```sh
cp /home/blakepowell/gunicorn_start /home/blakepowell/gunicorn_start.before-upgrade
install -m 750 deploy/gunicorn_start /home/blakepowell/gunicorn_start
bash -n /home/blakepowell/gunicorn_start
/home/blakepowell/gunicorn_start --check-config
sudo nginx -t
```

Require all checks to pass. --check-config imports the application but does not
start another server or replace the live Unix socket. No migrations or collectstatic
are needed for this package/startup-script change.

```sh
sudo supervisorctl restart logbook
sudo supervisorctl status logbook
sudo supervisorctl tail logbook stdout
```

No Supervisor reread/update is needed: the configured command path is unchanged.
Celery does not run Gunicorn and need not restart for this upgrade.
Verify HTTPS through Nginx (use the canonical live hostname):

```sh
curl -I https://direct2logbook.com/accounts/login/
curl -I https://direct2logbook.com/flights/logbook/
```

Expect a successful public login page and an unauthenticated redirect for the
protected logbook, following any normal canonical-host redirect as necessary.
Then sign in normally and view home/flights, check existing uptime monitoring and
Sentry for errors. A RUNNING Supervisor status alone does not prove proxy service.

If startup/proxy checks fail, preserve error output, restore the previous script,
revert the dependency pin/install to 19.9.0 and restart logbook. The old version has
known security issues; rollback is temporary incident mitigation, not a final fix.

References:
- https://gunicorn.org/news/
- https://gunicorn.org/reference/settings/#forwarded_allow_ips
- https://pypi.org/pypi/gunicorn/json
