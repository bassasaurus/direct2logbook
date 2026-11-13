# User deletion audit

Deleting a user through Django admin, `user.delete()`, or a User queryset now removes the active account and its owned database records. No real accounts or Stripe resources were deleted during this audit; external services are mocked in the tests.

## What is removed

- User, groups/permission memberships, profile, signature, reminders, allauth email addresses and confirmation links, Google connections and OAuth tokens, and DRF API tokens.
- Flights, aircraft, tailnumbers, imported summaries, totals/statistics and other calculated summaries, approaches, and holding entries.
- CSV preview/import payloads, PDF request records, and mobile sync receipts.
- Database sessions identifying the user, admin log entries about the user or their owned records, and recorded PDF/CSV task results associated with their request IDs. Historical diagnostic results containing the user's ID are also removed. New diagnostic tasks no longer store results.
- Referenced aircraft uploads, once external cleanup runs. A file still referenced by another aircraft is preserved.
- Known Stripe customers from both Profile and BillingProvisioning. Stored subscription IDs are also resolved to their customers, including when the Profile customer ID is missing. Stripe customer deletion immediately cancels active subscriptions on that customer.

Shared airports, provider configuration, SocialApp credentials, groups, permissions and unrelated users' records are preserved.

## Gaps fixed

1. No previous account deletion hook contacted Stripe.
2. Summary `post_delete` handlers could recreate records already included in a user cascade. They now skip user cascades while continuing to update summaries for ordinary flight/aircraft deletions.
3. Holding entries used `SET_NULL`, leaving orphaned rows after their flight disappeared. They now cascade with the flight.
4. Sessions, subject-oriented admin logs and legacy diagnostic results had indirect user references not covered by a user foreign key.
5. Deletion-triggered Stripe webhooks could produce reconciliation failures. Events for a pending deletion or a confirmed deleted Stripe customer are acknowledged without recreating an account. Unknown live customer mappings still require reconciliation.

## Stripe and file cleanup is asynchronous

Database transactions cannot atomically commit a Stripe API operation or a storage deletion. The account is removed locally first, while a temporary `AccountDeletionCleanup` row is committed in the same transaction. It contains only the Stripe identifiers and referenced file keys necessary to complete cleanup, not a user foreign key, email, name, signature or flight data.

After commit, Celery processes the row. The row is removed only after Stripe confirms customer deletion and file cleanup succeeds. Failures retain the row, a sanitized error code and a retry time. Celery retries every five minutes up to six times; the scheduled command below provides continued recovery, including broker outages. An API outage can therefore delay subscription cancellation; a local deletion alone does not mean Stripe cleanup has completed.

Django admin exposes a read-only **Account deletion cleanups** queue with a retry action. Cleanup rows cannot be discarded through that admin. The existing `check_background_jobs` monitor alerts for failed cleanup attempts or jobs waiting at least 15 minutes, without exposing Stripe IDs or file names in the digest.

Deletion refuses to proceed while billing provisioning is running or has an uncertain outcome. Reconcile that attempt first using the existing billing recovery tools. The billing claim and deletion use the same user-first row locking order. Deletion also refuses inconsistent cross-owner logbook links or Stripe mappings shared with another local account. The cleanup worker checks for surviving billing references again before contacting Stripe.

## Deployment

Apply migrations and restart Django and Celery using the normal deployment workflow. Add this recovery entry to the existing production crontab:

```cron
*/5 * * * * cd /home/blakepowell/app && /usr/bin/flock -n /home/blakepowell/logs/account-deletion-cleanup.lock /home/blakepowell/venv312/bin/python manage.py process_account_deletions >> /home/blakepowell/logs/account-deletion-cleanup.log 2>&1
```

To inspect/retry due cleanup manually:

```sh
/home/blakepowell/venv312/bin/python manage.py process_account_deletions
```

The command handles at most 100 due jobs per run, reports completion/failure counts, and exits nonzero if cleanup fails. The existing background-job monitor remains read-only; it alerts but does not retry cleanup.

After a deletion, check that the cleanup queue has cleared before considering external cleanup complete. Always test with an expendable test account in the appropriate Stripe mode. Never identify customers for deletion by email alone.

## Boundaries

- [Stripe retains a deleted customer/history record](https://docs.stripe.com/api/customers/delete), removes payment details and prevents further customer operations. Deletion is not an API for erasing historical invoices, payments or Stripe's records.
- Existing backups, logs, already-delivered emails/PDFs, observability records, and data cached on an offline phone are not retroactively erased. The deleted account's API token is removed immediately; the server rejects it on reconnection. Queued work checks missing account/request records, but an external operation already in flight cannot be recalled.
- Signature data is stored in the Signature database row in the current model; the local audit found no legacy signature URLs. Unreferenced historical storage objects cannot safely be attributed to a user from this schema alone.
- Historical Holding rows already lacking a flight cannot be attributed to an account. This migration prevents new orphans; it does not indiscriminately purge old orphan rows.
- Raw SQL, `TRUNCATE`, restoring an older backup, or bypassing Django's deletion collector do not run these hooks. Use the tested Django deletion paths.
