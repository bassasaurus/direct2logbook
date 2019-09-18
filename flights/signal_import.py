from flights.models import Total, Import
from django.db.models.signals import pre_save, post_save, post_delete
from django.db.models import Sum, Q
import datetime
from flights.queryset_helpers import *
from django.dispatch import receiver

@receiver(post_save, sender=Import)
@receiver(post_delete, sender=Import)
def update_total(sender, instance, **kwargs):
    print("Import signal!")

    return None
