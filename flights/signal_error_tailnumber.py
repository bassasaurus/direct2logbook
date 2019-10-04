from flights.models import TailNumber
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=TailNumber)
def tainumber_error(sender, instance, dispatch_uid='tailnumber_error', **kwargs):

    user = instance.user

    if not instance.is_91 and not instance.is_135 and not instance.is_121:
        reg_error = "Please indicate if FAR 91, FAR 135, or FAR 121"
        TailNumber.objects.filter(user=user).filter(pk=instance.pk).update(reg_error=reg_error)
    else:
        TailNumber.objects.filter(user=user).filter(pk=instance.pk).update(reg_error='')
