import uuid

from django.db import models
from django.utils import timezone


class AccountDeletionCleanup(models.Model):
    """Temporary external-resource pointers; removed after cleanup succeeds."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer_ids = models.JSONField(default=list)
    subscription_ids = models.JSONField(default=list)
    media_names = models.JSONField(default=list)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=100, blank=True)
    next_attempt_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
