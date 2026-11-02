from flights.models import Flight
from django.db.models.signals import post_save
from django.dispatch import receiver
from flights.airport_resolution import flight_resolution, warning_values


@receiver(post_save, sender=Flight, dispatch_uid='flight_route_warnings')
def update_route_warnings(sender, instance, **kwargs):
    values = warning_values(flight_resolution(instance))
    Flight.objects.filter(user_id=instance.user_id, pk=instance.pk).update(**values)
    for field, value in values.items():
        setattr(instance, field, value)


@receiver(post_save, sender=Flight)
def flight_misc_error(sender, instance, dispatch_uid='flight_misc_error', **kwargs):

    user = instance.user

    if not instance.aircraft_type:
        aircraft_type_error = "Please select an aircraft type"
        Flight.objects.filter(user=user).filter(pk=instance.pk).update(aircraft_type_error=aircraft_type_error)
    else:
        Flight.objects.filter(user=user).filter(pk=instance.pk).update(aircraft_type_error='')

    if not instance.registration:
        registration_error = "Please select a tailnumber"
        Flight.objects.filter(user=user).filter(pk=instance.pk).update(registration_error=registration_error)
    else:
        Flight.objects.filter(user=user).filter(pk=instance.pk).update(registration_error='')

    data = (instance.pilot_in_command, instance.second_in_command, instance.dual, instance.instructor, instance.solo)
    if not any(data):
        crew_error = "Please select a crew position"
        Flight.objects.filter(user=user).filter(pk=instance.pk).update(crew_error=crew_error)
    else:
        Flight.objects.filter(user=user).filter(pk=instance.pk).update(crew_error='')
