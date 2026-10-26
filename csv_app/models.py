import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

CSV_PREVIEW_MAX_AGE = timedelta(minutes=10)
CSV_IMPORT_STALE_AFTER = timedelta(minutes=20)


class CSVImportBatch(models.Model):
    class Status(models.TextChoices):
        PREVIEW = 'preview', 'Preview'
        QUEUED = 'queued', 'Queued'
        UNCONFIRMED = 'unconfirmed', 'Queue unconfirmed'
        PROCESSING = 'processing', 'Importing'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    row_count = models.PositiveIntegerField()
    completed = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PREVIEW, db_index=True)
    task_id = models.CharField(max_length=255, null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(default=timezone.now)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    @property
    def expires_at(self):
        return self.created_at + CSV_PREVIEW_MAX_AGE

    @property
    def is_expired(self):
        return not self.completed and self.status == self.Status.PREVIEW and timezone.now() >= self.expires_at
