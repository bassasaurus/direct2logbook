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
    if flight.night_landings_full_stop is not None:
        values['night_landings_full_stop'] = flight.night_landings_full_stop
    # Empty new metadata must not invalidate revisions queued by older clients.
    for name in ('device_type', 'device_id', 'atd_type', 'instrument_credit_eligible', 'launch_method'):
        if getattr(flight, name, ''):
            values[name] = getattr(flight, name)
    # Preserve existing mobile revision fingerprints across the float-to-decimal migration.
    # These values are only serialized for hashing, never used for arithmetic here.
    for name in ('night', 'instrument', 'simulated_instrument'):
        if values[name] is not None:
            values[name] = float(values[name])
    values['approaches'] = list(Approach.objects.filter(flight_object=flight).order_by('pk').values())
    values['holding'] = list(Holding.objects.filter(flight_object=flight).order_by('pk').values())
    return hashlib.sha256(json.dumps(values, sort_keys=True, default=str).encode()).hexdigest()


def aircraft_revision(aircraft):
    # File contents are managed separately; the path participates in conflicts.
    values = {field.attname: str(getattr(aircraft, field.attname))
              for field in aircraft._meta.concrete_fields if field.attname != 'is_default'}
    # Adding an unused engine option or an equivalent wake label must not
    # invalidate edits queued before this schema upgrade.
    if not aircraft.electric:
        values.pop('electric', None)
    if not aircraft.self_launch_capable:
        values.pop('self_launch_capable', None)
    if not aircraft.default_crew_role:
        values.pop('default_crew_role', None)
    if not aircraft.default_cross_country:
        values.pop('default_cross_country', None)
    values.update(medium='False', light_sport='False')
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()
