from django.db import models
from signature_pad import SignaturePadField
from django.contrib.auth.models import User, Group


class Signature(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    signature = SignaturePadField(blank=False, null=True)
