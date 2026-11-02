from django.db.models.signals import post_save
from django.dispatch import receiver
from flights.models import Flight
from flights.airport_resolution import flight_resolution, map_values


@receiver(post_save, sender=Flight, dispatch_uid='app_data_update')
def make_json_field(sender, instance, created=False, **kwargs):
    values = map_values(flight_resolution(instance))
    values.pop('route_data')
    Flight.objects.filter(pk=instance.pk, user_id=instance.user_id).update(**values)
    for field, value in values.items():
        setattr(instance, field, value)
