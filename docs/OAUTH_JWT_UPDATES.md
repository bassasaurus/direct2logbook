# OAuth and JWT dependency updates

Updates the existing authentication dependencies together:

| Package | Before | After |
| --- | --- | --- |
| PyJWT | 2.10.1 | 2.15.1 |
| OAuthlib | 3.0.2 | 4.0.0 |
| Requests-OAuthlib | 1.2.0 | 2.0.0 |

Python 3.12.16, Django 5.2.18, allauth 65.21.0 and DRF 3.18.3 are retained.
No application authentication settings, credentials, account-linking rules or
database models are changed.

## Security and compatibility

PyJWT's releases since 2.10.1 harden HMAC key validation, claim validation,
malformed token handling and JWKS handling. The 2.15.1 patch also accepts valid
trailing Base64URL padding while continuing to reject non-alphabet junk.
This upgrade does not add JWT authentication to the mobile API; that API continues
to use its existing DRF authentication.

OAuthlib 4 removes JSONP support from token revocation and changes validation in
OAuth authorization-server grants. This app is an OAuth client and does not enable
allauth's identity-provider server. These server-side breaking changes do not
require application configuration changes here. Older OAuthlib advisories may
apply to provider/server deployments rather than this app's Google login path.

Requests-OAuthlib 2 is updated alongside OAuthlib to use the maintained client
wrapper, including PKCE support and correct handling of the session's TLS verify
setting during token exchanges. TLS verification remains enabled.

## Validation

The existing Google signup, login, account linking and email tests remain in use.
New tests pass real RSA-signed tokens through allauth's Google JWT decoder, with
only the remote key lookup mocked. They check valid tokens, wrong signatures,
issuer/audience mismatch, expiry, malformed claims and public-key/HMAC confusion.
Client integration tests cover a PKCE authorization/token exchange, state mismatch
before an HTTP exchange, and OAuth1 signed request preparation. All tokens, keys
and HTTP responses used in these tests are synthetic; no real Google login,
email or Stripe action is performed by the tests.

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

No migrations or static-asset changes are introduced by this branch. Review any
unrelated operations shown in the migration plan. Verify an existing Google login
and normal email/password login, then check Sentry for authentication errors.
Keep the previous deployed revision and requirements for rollback.

## Upstream sources

- https://pyjwt.readthedocs.io/en/stable/changelog.html
- https://github.com/oauthlib/oauthlib/blob/v4.0.0/CHANGELOG.rst
- https://pypi.org/project/requests-oauthlib/2.0.0/
