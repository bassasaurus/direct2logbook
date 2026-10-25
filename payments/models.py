from django.conf import settings
from django.db import models


class BillingProvisioning(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="billing_provisioning",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    attempts = models.PositiveIntegerField(default=0)

    customer_request_key = models.CharField(max_length=100, blank=True)
    subscription_request_key = models.CharField(max_length=100, blank=True)
    stripe_customer_id = models.CharField(max_length=100, blank=True)
    stripe_subscription_id = models.CharField(max_length=100, blank=True)

    outcome_uncertain = models.BooleanField(default=False)

    last_error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    processing_started_at = models.DateTimeField(null=True, blank=True,)
    processing_token = models.UUIDField(null=True, blank=True, editable=False,)

    def __str__(self):
        return f"{self.user_id}: {self.status}"


class StripeWebhookEvent(models.Model):
    """A receipt committed only after a signed event is handled successfully."""
    event_id = models.CharField(max_length=255, primary_key=True)
    event_type = models.CharField(max_length=255)
    outcome = models.CharField(max_length=40, default='processed')
    processed_at = models.DateTimeField(auto_now_add=True)
