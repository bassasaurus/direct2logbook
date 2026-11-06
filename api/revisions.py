import hashlib
import json


def flight_revision(flight):
    """Fingerprint editable values, including nested records and route choices."""
    names = (
        'id', 'user_id', 'date', 'aircraft_type_id', 'registration_id', 'route',
        'duration', 'landings_day', 'landings_night', 'night', 'instrument',
        'cross_country', 'second_in_command', 'pilot_in_command',
        'simulated_instrument', 'instructor', 'simulator', 'dual', 'remarks',
        'solo', 'hold', 'route_airport_choices',
    )
    from flights.models import Approach, Holding
    values = {name: getattr(flight, name) for name in names}
    values['approaches'] = list(Approach.objects.filter(flight_object=flight).order_by('pk').values())
    values['holding'] = list(Holding.objects.filter(flight_object=flight).order_by('pk').values())
    return hashlib.sha256(json.dumps(values, sort_keys=True, default=str).encode()).hexdigest()


def aircraft_revision(aircraft):
    # File contents are managed separately; the path participates in conflicts.
    values = {field.attname: str(getattr(aircraft, field.attname))
              for field in aircraft._meta.concrete_fields if field.attname != 'is_default'}
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()
