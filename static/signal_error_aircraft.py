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

    data =  (instance.superr, instance.heavy, instance.large, instance.medium, instance.small)
    if not any(data):
        weight_error = "Please select a weight category"
        Aircraft.objects.filter(pk=instance.pk).update(weight_error=weight_error)
    else:
        Aircraft.objects.filter(pk=instance.pk).update(weight_error='')

    if not instance.aircraft_category:
        category_error = "Please select an aircraft category"
        Aircraft.objects.filter(pk=instance.pk).update(category_error=category_error)
    else:
        Aircraft.objects.filter(pk=instance.pk).update(category_error='')

    if not instance.aircraft_class:
        class_error = "Please select an aircraft class"
        Aircraft.objects.filter(pk=instance.pk).update(class_error=class_error)
    else:
        Aircraft.objects.filter(pk=instance.pk).update(class_error='')
