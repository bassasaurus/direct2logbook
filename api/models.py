from django.conf import settings
from django.db import models


class MobileSyncReceipt(models.Model):
    """A durable acknowledgement, committed in the same transaction as its write."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    operation_id = models.UUIDField()
    request_hash = models.CharField(max_length=64)
    response = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=['user', 'operation_id'], name='mobile_sync_user_operation_unique',
        )]
