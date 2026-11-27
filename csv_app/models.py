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
    source_digest = models.CharField(max_length=64, blank=True, default='', db_index=True)
    mapping_complete = models.BooleanField(default=True)
    source_metadata = models.JSONField(default=dict, blank=True)
    column_mapping = models.JSONField(default=dict, blank=True)
    rows_complete = models.BooleanField(default=True)
    row_data = models.JSONField(default=dict, blank=True)
    records_complete = models.BooleanField(default=True)
    record_resolution = models.JSONField(default=dict, blank=True)
    overlap_review = models.JSONField(default=dict, blank=True)
    date_order = models.CharField(max_length=12, blank=True, default='',
        choices=[('pending', 'Needs a date format'), ('mdy', 'Month/Day/Year'),
                 ('dmy', 'Day/Month/Year'), ('unambiguous', 'Unambiguous')])
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

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=['user', 'source_digest'],
            condition=~models.Q(source_digest='') & models.Q(status__in=('queued', 'unconfirmed', 'processing', 'completed')),
            name='csv_unique_submitted_source'), models.CheckConstraint(
            condition=models.Q(status__in=('preview', 'queued', 'unconfirmed', 'processing', 'completed', 'failed')),
            name='csv_import_status_valid')]

    @property
    def expires_at(self):
        return self.created_at + CSV_PREVIEW_MAX_AGE

    @property
    def is_expired(self):
        return not self.completed and self.status == self.Status.PREVIEW and timezone.now() >= self.expires_at
