# CI and manually triggered production deployment

## What runs automatically

GitHub Actions runs **CI / Django and JavaScript** for every pull request targeting
master and every push to master. The workflow uses Ubuntu, Python 3.12.16, Node 22
and an isolated PostgreSQL 16 service. The service container runs on GitHub's
runner; no Docker installation is needed on the production server.

The job installs uv 0.13.6 in a separate tools environment, creates an application
virtualenv, and synchronizes it to the exact requirement pins. It checks dependency
compatibility, Django configuration and missing migrations; runs the full Python
suite and JavaScript map tests; applies migrations to the empty CI database;
collects static files and checks deployment script syntax. Third-party actions are
pinned to verified commit SHAs and receive read-only repository permissions.

`logbook.settings_ci` supplies fake service keys, in-memory mail/broker/cache and
local file storage. No production secrets, broker or database are required by PR
tests. DATABASE_URL must be explicit; the workflow supplies its throwaway database.
Production continues to use logbook.settings.

## What runs manually

After this workflow is merged into master and production setup is complete:

1. Open **Actions → Deploy production → Run workflow**.
2. Select **master**. Other refs fail the branch guard.
3. The selected commit runs CI again before deployment can access production secrets.
4. GitHub's production environment protections, if configured, require approval.
5. The server verifies it is clean/on master and that the requested exact SHA is
   still the current master head. If master advanced, run the workflow again.
6. A fresh backup is uploaded and download-verified before service changes begin.
7. Django and Celery stop for a short maintenance window. Code fast-forwards,
   dependencies synchronize (including removal of unused packages), checks and
   migrations run, and static files are collected.
8. Both services start; Supervisor and a public HTTPS login-page check must pass.

Deployment runs are serialized in GitHub and locked on the server. A failed
backup leaves the running app unchanged. Failures after stopping services leave
them stopped for reviewed repair rather than guessing at a database rollback.
The script records previous/target/success revisions in the private
`/home/blakepowell/deploy-state` directory. Deployment never changes server cron
schedules, Nginx configuration, startup scripts or environment files.

This is an in-place deployment matching the current server layout, with planned
downtime. It is not a zero-downtime release system. Cron jobs still run on their
existing schedules; review migrations that could conflict with those jobs.

## One-time production setup

These steps grant GitHub's production deployment job access to the app account.
Do not place a private key in the repository, chat, or PR. Use a dedicated key,
not your personal SSH key, and keep it only in the production environment secret.

### 1. Verify the existing paths/tools on the server

```bash
/home/blakepowell/venv312/bin/python --version
/home/blakepowell/python-upgrade-tools/bin/uv --version
command -v supervisorctl
command -v flock
command -v curl
cd /home/blakepowell/app
git status --short
```

Expected: Python 3.12, uv 0.13.6, Supervisor at `/usr/bin/supervisorctl`, and a
reviewed clean checkout. If necessary, update uv in its tools environment only:

```bash
/home/blakepowell/python-upgrade-tools/bin/python -m pip install 'uv==0.13.6'
```

Verify backups remain configured and `manage.py backup_database` succeeds using
the production app environment. Confirm Supervisor already uses venv312 for both
services. Review any untracked server files rather than deleting them blindly.

### 2. Create a dedicated SSH key on your Mac

```bash
ssh-keygen -t ed25519 -f ~/.ssh/direct2logbook-actions -C direct2logbook-actions
```

For unattended deployment this dedicated key must have an empty passphrase.
Add the public key (`.pub`) to `/home/blakepowell/.ssh/authorized_keys` on the
server, prefixed with `restrict ` to disable forwarding and PTY access. This still
allows commands as blakepowell, including access to the application configuration.
Keep the existing personal SSH key entries intact.

### 3. Allow only the required unattended Supervisor commands

On the server, use `sudo visudo -f /etc/sudoers.d/direct2logbook-deploy` to add:

```sudoers
blakepowell ALL=(root) NOPASSWD: /usr/bin/supervisorctl stop logbook celery, /usr/bin/supervisorctl start logbook celery, /usr/bin/supervisorctl status logbook celery
```

Validate with `sudo visudo -c`. The workflow does not need unrestricted passwordless
sudo. Stopping Celery respects its configured graceful shutdown/stopwaitsecs.
Before each deployment, let long-running CSV/PDF/billing jobs finish where possible.

### 4. Verify and pin the SSH server host key

Get the trusted fingerprint from your existing server session:

```bash
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

On your Mac, collect the host entry (replace SERVER_HOST with the actual IP/domain):

```bash
ssh-keyscan -t ed25519 SERVER_HOST > /tmp/direct2logbook-known-hosts
ssh-keygen -lf /tmp/direct2logbook-known-hosts
```

Compare fingerprints before trusting the file. The workflow requires strict host
verification; it does not trust a fresh ssh-keyscan result during deployment.

### 5. Configure GitHub's production environment

In **Settings → Environments**, create **production**. Restrict deployment branches
to **master** only. You can also require a reviewer; do not enable prevention of
self-review if you need to approve deployments as the sole maintainer.

Add environment variables:

| Variable | Value |
| --- | --- |
| PRODUCTION_HOST | Server IP/domain used in the verified known-host entry |
| PRODUCTION_USER | blakepowell |
| PRODUCTION_DEPLOY_ENABLED | true, only after all setup checks pass |

Add environment secrets:

| Secret | Contents |
| --- | --- |
| PRODUCTION_SSH_KEY | The dedicated private key from your Mac |
| PRODUCTION_KNOWN_HOSTS | The fingerprint-verified known-host entry |

SSH uses port 22. The enable variable defaults to absent, so deployments fail
before connecting until setup is deliberately completed. Database, Stripe, Mailgun,
Sentry and B2 secrets stay on the server and are not copied into GitHub.

## Required PR check

Once the CI check has succeeded on a PR, protect master and require the
**Django and JavaScript** check from GitHub Actions before merging. Keep it current
with master. Do not use pull_request_target to execute untrusted PR code or pass
production secrets to the CI workflow. A human merge/deployment step remains.

## Failure and rollback

Read the Actions log and `/home/blakepowell/deploy-state/last-attempt`. If services
were stopped, fix the failed step before restarting. Schema changes need a reviewed
rollback plan; blindly checking out older code or restoring a database can discard
new writes or make code incompatible with the schema.

For a reviewed code-only rollback with no incompatible migrations, use the recorded
previous revision, synchronize its requirements with the tools uv against venv312,
run Django checks/collectstatic, then start logbook and celery and verify HTTPS.
Keep the off-server backup and existing restore procedure available.

## Sources

- https://docs.github.com/en/actions/tutorials/use-containerized-services/create-postgresql-service-containers
- https://docs.github.com/en/actions/concepts/workflows-and-actions/deployment-environments
- https://docs.astral.sh/uv/pip/sync/

## Post-deployment smoke checks

After the SSH deployment succeeds, Actions runs `python3 deploy/smoke.py` from the
GitHub runner. It checks the public login/signup forms, signup reCAPTCHA, linked
same-origin CSS/JavaScript, and anonymous redirects for home and CSV upload.
Requests use HTTPS certificate verification and a 15-second timeout each. Missing
content, unexpected redirects, and unavailable assets fail the workflow with the
failed check in its log. This checks HTTP content, not browser rendering or Google
verification. It does not log in, submit forms, create users, send email, or queue jobs.

A smoke-check failure occurs **after deployment**: the new code stays running.
Inspect the failing URL and server logs; do not assume a red workflow rolled back.
The earlier server-side deployment failure handling remains unchanged.

For a manual check from your Mac:

```bash
python deploy/smoke.py
```

After changes affecting authenticated flows, use a dedicated test account and:

1. Sign up and complete email verification (or use Google); confirm trial details.
2. Sign out and sign back in.
3. Create a test flight and confirm it appears correctly in the logbook.
4. Preview and confirm a small CSV import; wait for the completion message and
   verify the imported records, then delete the test records.
5. Request a logbook PDF; confirm the live status completes and the email arrives
   with a readable attachment.

These authenticated checks remain manual until a dedicated production test account
and cleanup procedure are configured. Automated read-only checks do not prove
Celery processing, Stripe provisioning, or actual email delivery.
