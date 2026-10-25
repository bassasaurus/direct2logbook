import uuid

from django.conf import settings
from django.db import models


class PDFRequest(models.Model):
    class Status(models.TextChoices):
        QUEUED = 'queued', 'Queued'
        UNCONFIRMED = 'unconfirmed', 'Submission unconfirmed'
        PROCESSING = 'processing', 'Processing'
        RETRYING = 'retrying', 'Retrying'
        SENDING = 'sending', 'Sending'
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'
        UNCERTAIN = 'delivery_uncertain', 'Delivery uncertain'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    task_id = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.QUEUED)
    render_attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
