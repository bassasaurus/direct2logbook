"""Validation shared by web forms and API writes for logbook records."""
import re
from decimal import Decimal, InvalidOperation
from flights.aircraft_classification import CLASSES_BY_CATEGORY, class_required
from flights.aircraft_characteristics import ENGINE_FIELDS, WAKE_FIELDS, engine_required

FLIGHT_ROLES = ('pilot_in_command', 'second_in_command', 'solo', 'dual')
AIRCRAFT_SELECTIONS = {
    'engine': ENGINE_FIELDS,
    'weight_category': WAKE_FIELDS,
}
OPERATING_RULES = ('is_91', 'is_135', 'is_121')


def effective_values(data, instance, fields):
    """Merge submitted fields with stored values for updates, including PATCH."""
    return {name: data.get(name, getattr(instance, name, None)) for name in fields}


def fields_changed(values, instance, normalize=lambda value: value):
    if instance is None or instance._state.adding:
        return True
    return any(normalize(value) != normalize(getattr(instance, name))
               for name, value in values.items())


def validate_flight(data, instance):
    errors = {}
    landing = effective_values(data, instance, ('night_landings_full_stop', 'landings_night', 'night'))
    if landing['night_landings_full_stop']:
        if not (landing['landings_night'] or 0) > 0:
            errors['night_landings_full_stop'] = 'Enter Night landings.'
        if not (landing['night'] or 0) > 0:
            errors['night'] = 'Night time required for Full Stop.'
    hours = effective_values(data, instance, ('night', 'duration'))
    try:
        night = Decimal(str(hours['night'] or 0))
        duration = Decimal(str(hours['duration']))
        if night.is_finite() and duration.is_finite() and duration >= 0 and night > duration:
            errors['night'] = 'Night cannot exceed Duration.'
    except (InvalidOperation, TypeError, ValueError):
        pass  # Numeric/required field validators provide the relevant error.
    from flights.launch_methods import validate_launch_method
    errors.update(validate_launch_method(data, instance))
    links = effective_values(data, instance, ('aircraft_type', 'registration'))
    aircraft, tail = links['aircraft_type'], links['registration']
    if aircraft is not None and tail is not None and tail.aircraft_id != aircraft.pk:
        errors['registration'] = f'{tail.registration} is assigned to {tail.aircraft.aircraft_type}. Choose a tailnumber for {aircraft.aircraft_type}.'
    device = effective_values(data, instance, ('simulator', 'device_type', 'device_id', 'atd_type',
        'instrument_credit_eligible', 'dual', 'simulated_instrument', 'duration'))
    if not device['simulator']:
        if tail is None:
            errors['registration'] = 'Choose a tailnumber.'
        if not data.get('route', getattr(instance, 'route', '')):
            errors['route'] = 'Enter a route.'
        if device['device_type'] or device['device_id']:
            errors['device_type'] = 'Select Sim first.'
        if device['instrument_credit_eligible']:
            errors['instrument_credit_eligible'] = 'Select Sim first.'
    if device['atd_type'] and device['device_type'] != 'ATD':
        errors['atd_type'] = 'Requires ATD.'
    metadata = {name: device[name] or '' for name in ('device_type', 'device_id', 'atd_type')}
    previous = {name: getattr(instance, name, '') or '' for name in metadata}
    require_device = any(name in data for name in metadata) or metadata != previous
    require_device = require_device or (instance and not instance._state.adding and not instance.simulator)
    from flights.simulator_validation import validate_simulator_entry
    simulator_errors = validate_simulator_entry(device, require_device=require_device,
        aircraft_category=getattr(aircraft, 'aircraft_category', None))
    errors.update(simulator_errors)
    roles = effective_values(data, instance, FLIGHT_ROLES)
    if not simulator_errors and fields_changed(roles, instance, bool) and not any(roles.values()):
        errors['pilot_in_command'] = 'Select PIC, SIC, Solo, or Dual.'

    solo_landings = effective_values(data, instance, ('solo', 'landings_day', 'landings_night'))
    if (fields_changed(solo_landings, instance, lambda value: value or 0)
            and solo_landings['solo']
            and not any((solo_landings[field] or 0) > 0 for field in ('landings_day', 'landings_night'))):
        errors['landings_day'] = 'Enter Day or Night landings for Solo.'

    sim_and_xc = effective_values(data, instance, ('simulator', 'cross_country'))
    if fields_changed(sim_and_xc, instance, bool) and all(sim_and_xc.values()):
        errors['cross_country'] = 'Select either Sim or Cross-country.'
    return errors


def validate_aircraft_classification(data, instance):
    errors = {}
    classification = effective_values(data, instance, ('aircraft_category', 'aircraft_class'))
    if not fields_changed(classification, instance):
        return errors
    category = classification['aircraft_category']
    aircraft_class = classification['aircraft_class'] or ''
    if category not in CLASSES_BY_CATEGORY:
        errors['aircraft_category'] = 'Choose an aircraft category.'
    elif class_required(category):
        if not aircraft_class:
            errors['aircraft_class'] = 'Choose an aircraft class.'
        elif aircraft_class not in CLASSES_BY_CATEGORY[category]:
            errors['aircraft_class'] = 'Aircraft category and class must agree.'
    elif aircraft_class:
        errors['aircraft_class'] = 'Class does not apply to this category.'
    return errors


def validate_aircraft(data, instance, user=None):
    errors = {}
    designator = effective_values(data, instance, ('aircraft_type',))
    if fields_changed(designator, instance) and not re.fullmatch(r'[A-Za-z0-9-]{1,10}', designator['aircraft_type'] or ''):
        errors['aircraft_type'] = 'Use 1–10 letters, numbers or hyphens.'

    errors.update(validate_aircraft_classification(data, instance))

    classification = effective_values(data, instance, ('aircraft_category', 'aircraft_class'))
    for group, fields in AIRCRAFT_SELECTIONS.items():
        choices = effective_values(data, instance, fields)
        if group == 'engine' and not engine_required(classification['aircraft_category'], classification['aircraft_class']):
            continue
        changed = fields_changed(choices, instance, bool)
        if group == 'engine':
            changed = changed or fields_changed(classification, instance)
        if changed and sum(map(bool, choices.values())) != 1:
            errors[group] = 'Choose one engine.' if group == 'engine' else 'Choose a wake category.'
    if case_duplicate('Aircraft', 'aircraft_type', designator['aircraft_type'], instance, user):
        errors['aircraft_type'] = 'This aircraft type already exists in your logbook.'
    return errors


def validate_tailnumber(data, instance, user=None):
    errors = {}
    registration = effective_values(data, instance, ('registration',))
    if fields_changed(registration, instance) and not 3 <= len(registration['registration'] or '') <= 8:
        errors['registration'] = 'Use 3–8 characters.'
    if case_duplicate('TailNumber', 'registration', registration['registration'], instance, user):
        errors['registration'] = 'This tailnumber already exists in your logbook.'
    aircraft = effective_values(data, instance, ('aircraft',))['aircraft']
    if instance is not None and instance.pk and aircraft is not None and aircraft.pk != instance.aircraft_id:
        from flights.models import Flight
        if Flight.objects.filter(registration_id=instance.pk).exclude(aircraft_type_id=aircraft.pk).exists():
            errors['aircraft'] = f'{instance.registration} has flights logged as {instance.aircraft.aircraft_type}. Keep {instance.aircraft.aircraft_type}, or correct those flights first.'
    rules = effective_values(data, instance, OPERATING_RULES)
    if fields_changed(rules, instance, bool) and sum(map(bool, rules.values())) != 1:
        errors['operating_rules'] = 'Select one operating rule.'
    return errors


def case_duplicate(model_name, field, value, instance, user):
    from django.apps import apps
    owner_id = getattr(user, 'pk', None) or getattr(instance, 'user_id', None)
    if not owner_id or not value:
        return False
    rows = apps.get_model('flights', model_name).objects.filter(user_id=owner_id, **{field + '__iexact': value})
    if instance and instance.pk:
        rows = rows.exclude(pk=instance.pk)
    return rows.exists()
