# Image and TLS dependency updates

Prepared and checked on Python 3.10.12:

| Package | Previous | New |
|---|---|---|
| Pillow | 9.4.0 | 12.3.0 |
| cryptography | 41.0.1 | 50.0.2 |
| cffi | 1.15.1 | 2.1.1 |
| certifi | 2019.3.9 | 2026.10.23 |
| requests | 2.32.4 | 2.34.2 |
| urllib3 | 2.5.0 | 2.8.0 |
| idna | 2.8 | 3.20 |

CFFI >=2 is required by cryptography. Other pinned packages satisfy their declared
constraints according to pip check. pycparser stays at 2.19; the newest pycparser
requires Python >=3.11 and is not required for this update. No application code,
models, credentials, or TLS verification settings change.

## Remaining security work

Pillow 12.3.0 is the newest published release supporting Python 3.10; Pillow 13.0.0
requires >=3.11 and fixes additional advisories. The re-scan still flags 38 distinct
Pillow advisory IDs (aliases may describe overlapping issues), all listing 13.0.0
as the fixed release. This is an interim risk reduction, NOT complete remediation
of image processing vulnerabilities. Upgrade Python, then Pillow 13, as a separate
migration. Python 3.10 is upstream end-of-life; check server vendor coverage too.
The six other changed packages have no current PyPI advisory matches in this scan.
The complete environment still has 14 flagged packages; do not call the entire
application vulnerability-free.

Sources:
- https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html
- https://cryptography.io/en/stable/changelog/
- https://pypi.org/pypi/requests/json
- https://pypi.org/pypi/urllib3/json
- https://pypi.org/pypi/idna/json
- https://devguide.python.org/versions/

## Validation

- pip check and the full Django suite, including real PDF/PNG signature rendering.
- A verified public HTTPS request through Requests/urllib3/certifi, without user
  credentials or disabling certificate/hostname verification.
- Existing PyJWT RSA token round-trip using cryptography/CFFI-generated keys.
- Existing Stripe SDK webhook signature verification using synthetic data; no
  Stripe API call, payment, subscription, email, or cloud mutation was performed.
- Pillow PNG, JPEG and WebP encoding/decoding.
- Binary wheels downloaded successfully for CPython 3.10 on Linux x86_64 with
  glibc compatibility matching Ubuntu 22.04; these native Linux wheels were not
  executed on the Mac. The actual production environment still needs smoke checks.

## Deployment

After merge/pull on production, install the pinned dependencies before restarting
both services. Fetch binary wheels for the native packages rather than silently
building against a different system OpenSSL:

```sh
cd /home/blakepowell/app
/home/blakepowell/venv/bin/python -m pip install --only-binary=Pillow,cryptography,cffi -r requirements.txt
/home/blakepowell/venv/bin/python -m pip check
/home/blakepowell/venv/bin/python manage.py check
sudo supervisorctl restart logbook celery
sudo supervisorctl status logbook celery
```

No migrations or collectstatic required. If pip cannot find compatible wheels,
stop before restarting and inspect Python version, architecture and pip version.
Do not disable TLS validation. Record installed versions if troubleshooting:

```sh
/home/blakepowell/venv/bin/python -m pip show Pillow cryptography cffi certifi requests urllib3 idna
```

Verify normal sign-in, social sign-in if enabled, a PDF request through email
receipt with its signature visible, and production error/uptime monitoring.
A live Sentry verification event can confirm the updated TLS transport if needed.
Do not trigger real charges or subscription changes as a dependency smoke test.
Cloud-storage/email/auth provider compatibility is not fully established by
mock-based tests or the one public HTTPS request.

Rollback by reverting the requirements changes, reinstalling the earlier pins and
restarting both services. Earlier pins have known issues, so rollback is temporary
incident mitigation, not the security end state.
