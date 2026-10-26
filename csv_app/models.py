import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

CSV_PREVIEW_MAX_AGE = timedelta(minutes=10)


class CSVImportBatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    row_count = models.PositiveIntegerField()
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    @property
    def expires_at(self):
        return self.created_at + CSV_PREVIEW_MAX_AGE

    @property
    def is_expired(self):
        return not self.completed and timezone.now() >= self.expires_at
