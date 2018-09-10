from flights.models import TailNumber
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=TailNumber)
def tainumber_error(sender, instance, **kwargs):

    if not instance.is_91 and not instance.is_135 and not instance.is_121:
        print('reg error')
        reg_error = "Please indicate if FAR 91, FAR 135, or FAR 121"
        TailNumber.objects.filter(pk=instance.pk).update(reg_error=reg_error)
    else:
        TailNumber.objects.filter(pk=instance.pk).update(reg_error='')