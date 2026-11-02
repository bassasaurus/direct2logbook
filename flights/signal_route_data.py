from flights.models import Flight
from django.db.models.signals import post_save
from django.dispatch import receiver
from flights.airport_resolution import flight_resolution, map_values


@receiver(post_save, sender=Flight)
def save_route_data(sender, instance, **kwargs):
    route_data = map_values(flight_resolution(instance))['route_data']
    Flight.objects.filter(pk=instance.pk, user_id=instance.user_id).update(route_data=route_data)
    instance.route_data = route_data
    return route_data
