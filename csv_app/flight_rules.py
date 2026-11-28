"""Use the Flight form's rules for imported flights, without saving anything."""
from flights.models import Flight
from flights.record_validation import validate_flight


def flight_errors(values, aircraft=None, tailnumber=None):
    attrs = {name: value for name, value in values.items()
             if name not in ('aircraft', 'registration', 'approaches', 'approach_details')}
    instance = Flight(aircraft_type=aircraft, registration=tailnumber, **attrs)
    data = {**attrs, 'aircraft_type': aircraft, 'registration': tailnumber}
    for name in ('device_type', 'device_id', 'atd_type'):
        data.setdefault(name, '')
    errors = validate_flight(data, instance)
    # The file's names are validated before this point. Resolve their identities
    # and category-dependent requirements after completing Aircraft/Tailnumbers.
    if values.get('registration') and tailnumber is None:
        errors.pop('registration', None)
    if aircraft is None:
        errors.pop('launch_method', None)
        if errors.get('instrument_credit_eligible') == 'Airplane device required.':
            errors.pop('instrument_credit_eligible')
    return errors
