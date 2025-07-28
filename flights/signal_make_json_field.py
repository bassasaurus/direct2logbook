import re
from django.db.models.signals import post_save
from django.dispatch import receiver
from flights.models import Flight, MapData


@receiver(post_save, sender=Flight, dispatch_uid="app_data_update")
def make_json_field(sender, instance, created, **kwargs):
    """
    Populate app_markers and app_polylines JSON fields after a Flight is saved.
    Runs on creation and any time the route is updated.
    """
    # Temporarily disconnect to prevent recursion
    post_save.disconnect(make_json_field, sender=sender,
                         dispatch_uid="app_data_update")

    # Normalize and split route into airport codes
    segments = [seg for seg in re.split(
        r'[^A-Za-z0-9]+', instance.route.upper()) if seg]

    coordinates = []
    markers = []

    for idx, seg in enumerate(segments):
        airport = None
        # Try IATA (3-letter)
        if len(seg) == 3:
            airport = MapData.objects.filter(iata=seg).first()
        # Try ICAO (4-letter)
        if not airport and len(seg) == 4:
            airport = MapData.objects.filter(icao=seg).first()
        # Fallback: ICAO for 3-letter
        if not airport and len(seg) == 3:
            airport = MapData.objects.filter(icao=seg).first()
        # Skip unknown codes
        if not airport:
            continue

        coord = {"latitude": airport.latitude, "longitude": airport.longitude}
        coordinates.append(coord)
        markers.append({
            "key": idx,
            "icao": airport.icao,
            "iata": airport.iata,
            "title": airport.name,
            "coordinates": coord,
        })

    # Assign to instance and save only JSON fields
    instance.app_markers = markers
    instance.app_polylines = {"coordinates": coordinates}
    instance.save(update_fields=["app_markers", "app_polylines"])

    # Reconnect the signal
    post_save.connect(make_json_field, sender=sender,
                      dispatch_uid="app_data_update")
