# Remove unused dotenv packages

Removes dotenv 0.9.9 and python-dotenv 1.1.1. Application settings use
python-decouple 3.8, which remains installed. No application imports or calls to
dotenv/load_dotenv/dotenv_values/set_key/unset_key were found. The only installed
package requiring python-dotenv was the dotenv compatibility package itself.

This removes the last flagged package from the reviewed requirements. The
python-dotenv advisory concerns local symlink handling during .env rewrites; the
affected write operations were not used by this application. No .env files,
credentials, settings values or configuration-loading behavior are changed.

Both packages were uninstalled locally before running the full Django suite,
dependency checks, system checks, migration checks and a refreshed pinned-package
advisory scan. No database migrations or static-asset changes are introduced.

## Deploy after merge

```bash
cd /home/blakepowell/app
git pull --ff-only origin master
/home/blakepowell/venv312/bin/python -m pip install -r requirements.txt
/home/blakepowell/venv312/bin/python -m pip uninstall -y dotenv python-dotenv
/home/blakepowell/venv312/bin/python -m pip check
/home/blakepowell/venv312/bin/python manage.py check
/home/blakepowell/venv312/bin/python manage.py migrate --plan
sudo supervisorctl restart logbook celery
sudo supervisorctl status logbook celery
```

Review unrelated pending migrations if the plan shows any. Installing requirements
alone does not uninstall removed packages; automatic synchronization remains part
of the future CI/CD work. Verify login/logbook behavior and check Sentry after
deployment. Keep the previous deployment revision and requirements for rollback.

The advisory scan covers exact Python requirement pins against published
advisories; it does not certify the live server, OS packages, JavaScript, or the
absence of unknown vulnerabilities.

Advisory: https://github.com/advisories/GHSA-mf9w-mj56-hr94
