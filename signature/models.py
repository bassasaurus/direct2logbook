from django.db import models
from signature_pad import SignaturePadField
from django.contrib.auth.models import User, Group


class Signature(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    signature = SignaturePadField(blank=True, null=True)
