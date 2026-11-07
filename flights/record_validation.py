"""Validation shared by web forms and API writes for logbook records."""
import re

FLIGHT_ROLES = ('pilot_in_command', 'second_in_command', 'solo', 'dual')
AIRCRAFT_SELECTIONS = {
    'engine': ('turbine', 'piston'),
    'weight_category': ('superr', 'heavy', 'large', 'medium', 'small', 'light_sport'),
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
    roles = effective_values(data, instance, FLIGHT_ROLES)
    if fields_changed(roles, instance, bool) and not any(roles.values()):
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


def validate_aircraft(data, instance):
    errors = {}
    designator = effective_values(data, instance, ('aircraft_type',))
    if fields_changed(designator, instance) and not re.fullmatch(r'[A-Za-z0-9-]{1,10}', designator['aircraft_type'] or ''):
        errors['aircraft_type'] = 'Use 1–10 letters, numbers or hyphens.'

    classification = effective_values(data, instance, ('aircraft_category', 'aircraft_class'))
    if fields_changed(classification, instance):
        category = classification['aircraft_category']
        aircraft_class = classification['aircraft_class']
        if not category:
            errors['aircraft_category'] = 'Choose an aircraft category.'
        if not aircraft_class:
            errors['aircraft_class'] = 'Choose an aircraft class.'
        elif category and (category == 'R') != (aircraft_class in ('HELO', 'GYRO')):
            errors['aircraft_class'] = 'Aircraft category and class must agree.'

    for group, fields in AIRCRAFT_SELECTIONS.items():
        choices = effective_values(data, instance, fields)
        if fields_changed(choices, instance, bool) and sum(map(bool, choices.values())) != 1:
            errors[group] = f"Choose one {group.replace('_', ' ')}."
    return errors


def validate_tailnumber(data, instance):
    errors = {}
    registration = effective_values(data, instance, ('registration',))
    if fields_changed(registration, instance) and not 3 <= len(registration['registration'] or '') <= 8:
        errors['registration'] = 'Use 3–8 characters.'
    rules = effective_values(data, instance, OPERATING_RULES)
    if fields_changed(rules, instance, bool) and sum(map(bool, rules.values())) != 1:
        errors['operating_rules'] = 'Select one operating rule.'
    return errors
