# Allauth upgrade and Google sign-in

Updates django-allauth from 65.9.0 to 65.21.0. The login page shows a
Sign in with Google button only when a Google SocialApp is configured for
the current Django Site. Existing email/password authentication remains available.

New social users review a signup form before account creation, whether they
started on the sign-in or signup page. First and last names are required and
prefilled from Google when available. Generated usernames use first initial plus
last name, such as `srogers`; collisions receive allauth's unique suffix.

Google OAuth begins with a CSRF-protected POST and uses PKCE and OAuth state.
Only profile and email scopes are requested. Email matching does not automatically
authenticate or connect an existing account. Existing users should sign in with
their password, then connect Google at `/accounts/social/connections/`.

After completing signup, Google users whose email is already verified queue trial provisioning after
the database transaction commits. Unverified users must confirm their email first.
Returning Google users do not queue another signup trial. Stripe provisioning
continues to use its existing idempotency protections.

New Google-verified users also queue a separate welcome email after signup commits.
The email confirms creation of the account and explains that trial setup is in
progress. Returning Google logins do not queue another welcome. Mail submission
failures surface as Celery task failures; broker publication failures are logged
without failing signup. Automatic email retries are disabled to avoid duplicate
messages when delivery is uncertain. Restart Celery to load `accounts.tasks.send_google_welcome`.

Linking Google while signed in to an existing account queues a separate connection
confirmation email to the local account's email address. It includes a link to
review connections and instructions if the user did not authorize the change.
It does not create another trial or send the signup welcome email. Restart Celery
to load `accounts.tasks.send_google_connected` as well.

## Google configuration

In Google Cloud, use an OAuth client with application type **Web application**.
This is separate from the abandoned rclone desktop client.
Configure the consent screen/audience for the intended users and publish it for
public use when ready. During testing, add permitted test users if Google requires it.

Register the exact callback URL for each origin actually used:

- `https://direct2logbook.com/accounts/google/login/callback/`
- `https://www.direct2logbook.com/accounts/google/login/callback/` (if used)
- `http://localhost:8000/accounts/google/login/callback/` (local testing)

In Django admin, open **Social applications** and edit or create the Google app.
Set provider Google, the web client's client ID and secret, and attach the correct
Site. Keep exactly one applicable Google app per Site. Do not also configure the
same credentials through settings; duplicate apps can cause selection errors.
Do not paste client secrets or OAuth tokens into chat or commit them.

## Deployment

After merging and pulling, use the production Python 3.12 environment:

```bash
/home/blakepowell/venv312/bin/python -m pip install -r requirements.txt
/home/blakepowell/venv312/bin/python -m pip check
/home/blakepowell/venv312/bin/python manage.py check
/home/blakepowell/venv312/bin/python manage.py migrate --plan
```

Review planned upstream migrations, then apply with `manage.py migrate` using
the same interpreter. Restart `logbook` and `celery` through Supervisor.
Verify the next scheduled database backup/Sentry check-in before deploying.

## Manual checks

- Password login, signup/email confirmation, reset password and logout.
- Google button hidden when no applicable Google SocialApp exists.
- New Google signup, profile name, verified email and exactly one trial provisioning.
- Returning Google login and inactive-account rejection.
- Existing password account: sign in first, connect Google, sign out, sign in with Google.
- Cancel Google consent and try again; an external `next` URL must not redirect off site.

Automated OAuth tests replace Google's network responses, not allauth's signup,
session, email, state or billing-signal processing. A real browser consent/callback
test with the deployed client is still required.

Sources:
- https://docs.allauth.org/en/latest/release-notes/
- https://docs.allauth.org/en/latest/socialaccount/providers/google.html
- https://developers.google.com/identity/branding-guidelines

The button uses the Google material button HTML and multicolor SVG supplied by
the user, with a full-width light outline and CSS interaction states. Run
`collectstatic` when deploying the updated CSS.
