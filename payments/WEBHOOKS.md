# Stripe webhook reliability

The endpoint remains `/stripe_webhook/`. It accepts signed Stripe snapshot
notifications over POST. It stores successful event IDs and reconciles local
billing against the current Stripe subscription rather than trusting an old
event snapshot. It never creates or modifies resources in Stripe.

## Before deployment

1. Run locally:

   ```sh
   python manage.py test payments.tests.test_webhooks
   python manage.py test
   python manage.py makemigrations --check --dry-run
   ```

   Webhook regression tests sign their own test payloads and mock Stripe API
   calls. They do not contact Stripe or require a running Celery worker.

2. In Stripe Workbench, check the existing endpoint's event subscriptions:

   - `checkout.session.completed`
   - `checkout.session.async_payment_succeeded` if asynchronous payment methods are used
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `customer.subscription.trial_will_end`
   - `customer.subscription.paused` and `customer.subscription.resumed` if used
   - `invoice.payment_succeeded` (or `invoice.paid`)
   - `invoice.payment_failed`

   Verify this separately for test and live endpoints. Existing signature
   secrets remain unchanged. Do not switch the endpoint to thin events.

3. Back up the production database. Deploy the code, apply migration
   `payments.0004_stripewebhookevent`, and restart Django before enabling traffic
   to the new handler. Prefer a brief maintenance window so code requiring the
   receipt table cannot receive events before its migration is applied.

4. Check the endpoint's delivery history and Django logs after deployment.
   Use test mode for a Checkout/payment cycle before testing live behavior.

## Expected responses and recovery

- `200`: processed, duplicate, irrelevant event, or event for an older subscription.
- `400`: missing/invalid signature or malformed signed billing event.
- `405`: non-POST request.
- `503`: processing failed; no receipt or profile changes are committed. Stripe
  can retry the same event. Inspect logs and its delivery history for failures.

Receipts contain event ID/type, outcome, and processing time, not raw payloads.
Unrecognized events and standalone charges cannot grant or revoke access.
Unknown customers and missing subscription mappings return a retryable error:
this handles webhooks arriving before provisioning finishes, and also makes
configuration errors visible instead of silently discarding billing updates.

A paid subscription is active only when Stripe currently reports `active`;
`trialing` retains trial access. A scheduled cancellation retains active access
until Stripe changes the subscription state. `past_due`, `unpaid`, `paused`,
`incomplete`, `incomplete_expired`, and `canceled` do not grant paid access.

Checkout can replace an existing subscription only with a more recently created
subscription for the same customer. Equal creation timestamps are deliberately
left for manual review (503), rather than guessing which subscription is newest.
Concurrent updates are serialized per profile; current Stripe state is fetched
while holding that profile lock. This keeps the initial implementation simple
but makes webhook response time dependent on Stripe. If webhook volume grows,
move reconciliation to a durable inbox/background processor.

Receipts are not automatically retried locally, and must not be deleted to
force replay without checking Stripe and local state first. A failed delivery
can be retried through Stripe's delivery tools after fixing its cause.
