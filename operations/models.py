from django.db import models


class BackgroundJobMonitor(models.Model):
    """One locked row serializes alert delivery and persists its cooldown."""
    name = models.CharField(max_length=40, primary_key=True)
    last_alerted_at = models.DateTimeField(null=True, blank=True)
