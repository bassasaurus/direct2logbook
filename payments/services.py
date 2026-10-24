from django.db import models
import uuid
import stripe
from datetime import datetime, timedelta, timezone
from allauth.account.models import EmailAddress
from django.conf import settings
from django.db import transaction
from django.utils import timezone as django_timezone

from payments.models import BillingProvisioning
from profile.models import Profile


class BillingProvisioningError(Exception):
    pass


def inspect_stripe_provisioning(user):
    """
    Inspect Stripe resources associated with a user's billing provisioning.

    This function only retrieves existing Stripe resources. It never
    creates customers or subscriptions and never modifies local records.

    A missing local Stripe ID does not prove that Stripe failed to create
    the resource. Such cases still require reconciliation.
    """

    record = BillingProvisioning.objects.get(user=user)
    profile = Profile.objects.get(user=user)

    stripe.api_key = settings.STRIPE_SECRET_KEY

    customer_id = (
        record.stripe_customer_id
        or profile.customer_id
    )

    subscription_id = (
        record.stripe_subscription_id
        or profile.subscription_id
    )

    result = {
        "customer_id": customer_id or None,
        "subscription_id": subscription_id or None,
        "customer": None,
        "subscription": None,
        "requires_manual_review": record.outcome_uncertain,
    }

    if customer_id:
        result["customer"] = stripe.Customer.retrieve(
            customer_id
        )

    if subscription_id:
        result["subscription"] = stripe.Subscription.retrieve(
            subscription_id
        )

    return result


def inspect_stripe_trial_subscriptions(user):
    """
    Find Stripe subscriptions matching this user's billing provisioning.

    This function is read-only:
    - Never creates Stripe resources.
    - Never modifies database records.
    - Searches all subscription statuses.
    - Uses metadata to identify matching subscriptions.

    Missing or multiple matches require manual review.
    """

    record = BillingProvisioning.objects.get(user=user)
    profile = Profile.objects.get(user=user)

    customer_id = (
        record.stripe_customer_id
        or profile.customer_id
    )

    if not customer_id:
        return {
            "customer_id": None,
            "matching_subscriptions": [],
            "requires_manual_review": True,
        }

    stripe.api_key = settings.STRIPE_SECRET_KEY

    matching_subscriptions = []

    subscriptions = stripe.Subscription.list(
        customer=customer_id,
        status="all",
        limit=100,
    )

    for subscription in subscriptions.auto_paging_iter():
        metadata = subscription.get("metadata") or {}

        if (
            metadata.get("direct2logbook_user_id") == str(user.pk)
            and metadata.get("billing_provisioning_id") == str(record.pk)
        ):
            matching_subscriptions.append(subscription)

    return {
        "customer_id": customer_id,
        "matching_subscriptions": matching_subscriptions,
        "requires_manual_review": len(matching_subscriptions) != 1,
    }


def recover_stripe_trial_subscription(user):
    """
    Recover an existing Stripe trial subscription.

    Only recover a single matching, currently active trial.
    Never create Stripe resources or overwrite conflicting local IDs.
    """

    inspection = inspect_stripe_trial_subscriptions(user)
    matches = inspection["matching_subscriptions"]

    if len(matches) != 1:
        raise BillingProvisioningError(
            "Exactly one matching subscription is required"
        )

    subscription = matches[0]
    record = BillingProvisioning.objects.get(user=user)

    customer_id = inspection["customer_id"]
    metadata = subscription.get("metadata") or {}
    trial_end = subscription.get("trial_end")

    if (
        subscription.get("customer") != customer_id
        or metadata.get("direct2logbook_user_id") != str(user.pk)
        or metadata.get("billing_provisioning_id") != str(record.pk)
        or subscription.get("status") != "trialing"
        or not isinstance(trial_end, int)
        or trial_end <= int(django_timezone.now().timestamp())
        or not subscription.get("id")
    ):
        raise BillingProvisioningError(
            "Subscription requires manual review"
        )

    with transaction.atomic():
        record = (
            BillingProvisioning.objects
            .select_for_update()
            .get(user=user)
        )

        profile = (
            Profile.objects
            .select_for_update()
            .get(user=user)
        )

        # Only recover a previously failed, uncertain attempt.
        if (
            record.status != BillingProvisioning.Status.FAILED
            or not record.outcome_uncertain
        ):
            raise BillingProvisioningError(
                "Provisioning state does not permit recovery"
            )

        if (
            (
                record.stripe_customer_id
                and record.stripe_customer_id != customer_id
            )
            or (
                profile.customer_id
                and profile.customer_id != customer_id
            )
            or (
                record.stripe_subscription_id
                and record.stripe_subscription_id != subscription["id"]
            )
            or (
                profile.subscription_id
                and profile.subscription_id != subscription["id"]
            )
        ):
            raise BillingProvisioningError(
                "Conflicting local billing records"
            )

        profile.customer_id = customer_id
        profile.subscription_id = subscription["id"]
        profile.trial = True
        profile.end_date = datetime.fromtimestamp(
            trial_end,
            tz=timezone.utc,
        ).date()

        profile.save(
            update_fields=[
                "customer_id",
                "subscription_id",
                "trial",
                "end_date",
            ]
        )

        record.stripe_customer_id = customer_id
        record.stripe_subscription_id = subscription["id"]
        record.status = BillingProvisioning.Status.COMPLETED
        record.outcome_uncertain = False
        record.last_error = ""

        record.save(
            update_fields=[
                "stripe_customer_id",
                "stripe_subscription_id",
                "status",
                "outcome_uncertain",
                "last_error",
                "updated_at",
            ]
        )

    return profile

# Stripe trial provisioning


def inspect_stale_provisioning(
    *,
    stale_after=timedelta(minutes=15),
):
    """
    Identify provisioning attempts that may have been abandoned.

    This function is read-only.

    It does not:
    - Modify provisioning records.
    - Contact Stripe.
    - Retry provisioning.
    - Reassign worker ownership.

    A stale processing record requires reconciliation before
    another worker can safely attempt provisioning.
    """

    if stale_after <= timedelta(0):
        raise ValueError(
            "stale_after must be a positive duration"
        )

    now = django_timezone.now()
    cutoff = now - stale_after

    records = (
        BillingProvisioning.objects
        .filter(
            status=BillingProvisioning.Status.PROCESSING,
        )
        .filter(
            models.Q(processing_started_at__lte=cutoff)
            | models.Q(processing_started_at__isnull=True)
        )
        .order_by("created_at")
    )

    results = []

    for record in records:
        started_at = record.processing_started_at

        processing_duration = (
            now - started_at
            if started_at is not None
            else None
        )

        results.append(
            {
                "provisioning_id": record.pk,
                "user_id": record.user_id,
                "status": record.status,
                "processing_token": record.processing_token,
                "processing_started_at": started_at,
                "processing_duration": processing_duration,
                "requires_reconciliation": True,
            }
        )

    return results


def verify_provisioning_owner(record, processing_token):
    """
    Verify that the current worker still owns provisioning.
    Must be called while holding a database row lock.
    """

    if (
        record.status != BillingProvisioning.Status.PROCESSING
        or record.processing_token != processing_token

    ):
        raise BillingProvisioningError(
            "Provisioning ownership has changed"
        )


def provision_trial(user):
    """
    Provision a 14-day Stripe trial after email verification.

    Prevent concurrent provisioning attempts and block automatic retries
    when the outcome of a Stripe operation is uncertain.
    """

    if not EmailAddress.objects.filter(
        user=user,
        verified=True,
    ).exists():
        raise BillingProvisioningError(
            "Email address must be verified first"
        )

    stripe.api_key = settings.STRIPE_SECRET_KEY

    # Claim provisioning using a short database transaction.
    with transaction.atomic():
        record, _ = BillingProvisioning.objects.get_or_create(
            user=user
        )

        record = (
            BillingProvisioning.objects
            .select_for_update()
            .get(pk=record.pk)
        )

        profile = (
            Profile.objects
            .select_for_update()
            .get(user=user)
        )

        # Existing subscriptions must not be recreated.
        if profile.subscription_id:
            record.status = BillingProvisioning.Status.COMPLETED
            record.save(update_fields=["status", "updated_at"])
            return profile

        # A previous attempt may have reached Stripe.
        if (
            record.outcome_uncertain
            or record.status == BillingProvisioning.Status.PROCESSING
        ):
            raise BillingProvisioningError(
                "Provisioning requires reconciliation"
            )

        record.status = BillingProvisioning.Status.PROCESSING
        record.attempts += 1
        record.last_error = ""

        # Identify the worker that owns this provisioning attempt.
        record.processing_token = uuid.uuid4()
        record.processing_started_at = django_timezone.now()
        processing_token = record.processing_token

        if not record.customer_request_key:
            record.customer_request_key = f"d2l-customer-{user.pk}"

        if not record.subscription_request_key:
            record.subscription_request_key = f"d2l-trial-{user.pk}"

        record.save()

       # Do not hold a database transaction open during Stripe calls.
    name = f"{user.first_name} {user.last_name}".strip()

    try:
        # Create a customer only when necessary.
        if not profile.customer_id:
            customer = stripe.Customer.create(
                name=name,
                email=user.email,
                description=name,
                idempotency_key=record.customer_request_key,
            )

            with transaction.atomic():
                current_record = (
                    BillingProvisioning.objects
                    .select_for_update()
                    .get(pk=record.pk)
                )

                verify_provisioning_owner(
                    current_record,
                    processing_token,
                )

                profile = (
                    Profile.objects
                    .select_for_update()
                    .get(user=user)
                )

                profile.customer_id = customer.id
                profile.save(update_fields=["customer_id"])

                current_record.stripe_customer_id = customer.id
                current_record.save(
                    update_fields=[
                        "stripe_customer_id",
                        "updated_at",
                    ]
                )

        # Verify ownership before contacting Stripe again.
        with transaction.atomic():
            current_record = (
                BillingProvisioning.objects
                .select_for_update()
                .get(pk=record.pk)
            )

            verify_provisioning_owner(
                current_record,
                processing_token,
            )

            profile = (
                Profile.objects
                .select_for_update()
                .get(user=user)
            )

            customer_id = profile.customer_id

        # Create the 14-day trial subscription.
        trial_end = datetime.now(timezone.utc) + timedelta(days=14)

        subscription = stripe.Subscription.create(
            customer=customer_id,
            collection_method="send_invoice",
            days_until_due=14,
            cancel_at_period_end=True,
            items=[
                {"plan": settings.STRIPE_TRIAL_PLAN}
            ],
            trial_end=int(trial_end.timestamp()),
            metadata={
                "direct2logbook_user_id": str(user.pk),
                "billing_provisioning_id": str(record.pk),
            },
            idempotency_key=record.subscription_request_key,
        )

        # Persist subscription and provisioning state together.
        with transaction.atomic():
            current_record = (
                BillingProvisioning.objects
                .select_for_update()
                .get(pk=record.pk)
            )

            verify_provisioning_owner(
                current_record,
                processing_token,
            )

            profile = (
                Profile.objects
                .select_for_update()
                .get(user=user)
            )

            profile.subscription_id = subscription.id
            profile.trial = True
            profile.end_date = datetime.fromtimestamp(
                subscription.trial_end,
                tz=timezone.utc,
            ).date()

            profile.save(
                update_fields=[
                    "subscription_id",
                    "trial",
                    "end_date",
                ]
            )

            current_record.stripe_subscription_id = subscription.id
            current_record.status = BillingProvisioning.Status.COMPLETED
            current_record.outcome_uncertain = False
            current_record.last_error = ""
            current_record.processing_token = None
            current_record.processing_started_at = None

            current_record.save(
                update_fields=[
                    "stripe_subscription_id",
                    "status",
                    "outcome_uncertain",
                    "last_error",
                    "processing_token",
                    "processing_started_at",
                    "updated_at",
                ]
            )

        return profile

    except Exception as exc:
        # Only the owning worker may mark this attempt as failed.
        with transaction.atomic():
            current_record = (
                BillingProvisioning.objects
                .select_for_update()
                .get(pk=record.pk)
            )

            if (
                current_record.status == BillingProvisioning.Status.PROCESSING
                and current_record.processing_token == processing_token
            ):
                current_record.status = BillingProvisioning.Status.FAILED
                current_record.outcome_uncertain = True
                current_record.last_error = (
                    f"{type(exc).__name__}: {str(exc)[:500]}"
                )
                current_record.processing_token = None
                current_record.processing_started_at = None

                current_record.save(
                    update_fields=[
                        "status",
                        "outcome_uncertain",
                        "last_error",
                        "processing_token",
                        "processing_started_at",
                        "updated_at",
                    ]
                )

        if isinstance(exc, BillingProvisioningError):
            raise

        raise BillingProvisioningError(
            f"Provisioning outcome needs reconciliation for user {user.pk}"
        ) from exc
