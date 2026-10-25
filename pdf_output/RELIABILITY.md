# PDF task reliability

## Implemented: durable requests and user-visible status

Each new PDF submission creates a `PDFRequest` before publishing to Celery.
Its UUID identifies an authenticated, owner-scoped status URL. The home page
shows the latest request and checks status every ten seconds for up to five
minutes. Reloading the page resumes checking. Status responses are not cached.

The worker atomically claims queued or unconfirmed requests before rendering.
Duplicate deliveries of the same request do not send another email. Rendering
failures are recorded as failed. Mail submission exceptions are conservatively
recorded as delivery uncertain, and are not automatically retried. Sent means
the mail backend accepted the message, not that it reached the recipient's inbox.
Message IDs are now valid and specific to the request. No PDF bytes or error
details are stored in the tracking table or returned by the status endpoint.

Requests without progress for 15 minutes display a delay warning; interrupted
sending displays an uncertain-delivery warning. These are read-only status
interpretations: they do not automatically requeue jobs or reset claims.
Older queued messages containing only a user ID remain supported and acquire a
tracking record using their Celery task ID.

### Manual validation and deployment

```sh
python manage.py test pdf_output.tests
python manage.py test
python manage.py makemigrations --check --dry-run
```

Tests mock the renderer and email/broker boundaries; they do not send live email.
After these pass, manually request a PDF and verify both its contents and the
status message. The existing rendering code is preserved.

Deploy during a brief maintenance window: stop new submissions, pull the code,
run `python manage.py migrate`, and restart both Django and the Celery worker
before reopening submissions. An old worker cannot accept the new request_id
argument. This change adds `pdf_output.0008_pdfrequest`, a self-contained baseline for the
current PDF request model. The historical 0001-0007 files were removed from the
repository, but their records can remain in existing databases. The new name
avoids treating the old 0001 record as proof that the request table exists; it does not require
collectstatic because the status script is in the home template.

No automatic retries, late acknowledgement, hard limits, or recovery command
are enabled in this first step. Separate user submissions still represent separate
requests and may each send an email. Request rows are retained until explicitly
cleaned up; deleting a user cascades to their requests.

## Original audit

## Current behavior

The authenticated POST endpoint publishes `pdf_generate(user_pk)` and returns
202 after broker confirmation. Publication errors return an ambiguous 503:
the task may have reached the broker. The frontend confirmation does not report
generation or email delivery completion.

The task builds the PDF in memory, attaches it to an email, and calls
`EmailMessage.send()`. It has no explicit task retry policy or time limits.
There is no PDF request model or status endpoint; the Celery result backend is
configured, but it is not exposed to the requesting user. No explicit late
acknowledgement or worker-loss recovery policy is configured for this task.

## Findings, in priority order

1. **Accepted requests can fail without user-visible status.** Rendering,
   database, storage, or mail failures can occur after the queued confirmation.
   Create a durable request record before publishing, and offer an authenticated,
   owner-scoped status endpoint. Track queued, processing, retrying, sent,
   failed, and delivery-uncertain outcomes, including last progress timestamps.
   Queue confirmation must remain distinct from completion.
2. **Blind retries can duplicate email.** The mail provider may accept an email
   even when the worker receives a timeout. Record the transition into sending
   before contacting the provider. Treat an interrupted or ambiguous send as
   delivery uncertain; do not automatically resend it. A local success flag or
   Message-ID does not guarantee exactly-once delivery. The current fixed
   `Message-ID: logbook` also needs replacement with a valid per-request ID.
3. **No bounded execution or safe transient retries.** Add task-specific soft
   and hard limits, and bounded retries for known transient failures before the
   send boundary. Configure network timeouts as appropriate. Separate rendering
   from sending so retry behavior can reflect the operation that failed.
   Handle exhausted retries and soft timeouts in the request record. A hard
   kill cannot reliably run cleanup; stale-job reconciliation is still needed.
4. **Worker crashes and ambiguous publication need recovery.** Reuse a request
   identifier across deliveries, claim jobs atomically, and skip requests
   already sent or in an uncertain send state. Reconcile stale queued/running
   jobs before enabling worker-loss redelivery. Do not automatically replay
   every stale task, because it may already have sent mail.
5. **Signature loading failures are currently nonfatal.** The renderer logs a
   warning and produces a PDF without the signature. Surface this as an export
   warning so the user can decide whether the PDF is suitable for their needs.

## Suggested first implementation

Start with durable PDF requests, owner-scoped status, and distinct confirmed,
failed, and uncertain email outcomes. Preserve the existing queued confirmation.
Then add bounded rendering retries, time limits, duplicate-delivery protection,
and stale-job reconciliation around those records. Verify behavior with mocked
broker, renderer, and mail boundaries before a live manual export test.

The audit preceded the first implementation above. The remaining priorities
are bounded rendering retries/time limits, stale-job reconciliation, and signature
warnings. No test suite was run by the assistant; tests are run manually by the user.
