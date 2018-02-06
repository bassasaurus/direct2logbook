from flights.models import Aircraft
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=Aircraft)
def aircraft_error(sender, instance, **kwargs):

    if not instance.turbine and not instance.piston:
        power_error = "Please select 'Piston' or 'Turbine'"
        Aircraft.objects.filter(pk=instance.pk).update(power_error=power_error)
    else:
        Aircraft.objects.filter(pk=instance.pk).update(power_error='')


    if not instance.simple and not instance.compleks:
        config_error = "Please select 'Simple' or 'Complex'"
        Aircraft.objects.filter(pk=instance.pk).update(config_error=config_error)
    else:
        Aircraft.objects.filter(pk=instance.pk).update(config_error='')
