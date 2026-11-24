"""Engine tracking and ATC wake classes, separate from pilot ratings."""
ENGINE_FIELDS = ('piston', 'turbine', 'electric')
ENGINE_CHOICES = tuple((key, key.capitalize()) for key in ENGINE_FIELDS)
WAKE_CHOICES = (('small', 'Small'), ('large', 'Large'), ('heavy', 'Heavy'), ('superr', 'Super'))
WAKE_FIELDS = tuple(key for key, _ in WAKE_CHOICES)


def engine_required(category, klass):
    return category != 'GL' and not (category == 'LTA' and klass == 'BALLOON')


def equipment_applicable(category, name):
    if name == 'simple':
        return False
    return category == 'A' or name == 'requires_type' and category in ('R', 'PL')


def normalize_characteristics(data, instance=None):
    """Clear hidden engines; accept the audited legacy Medium transport alias."""
    result = dict(data)
    get = lambda name: result.get(name, getattr(instance, name, None))
    if not engine_required(get('aircraft_category'), get('aircraft_class')):
        result.update({name: False for name in ENGINE_FIELDS})
    category = get('aircraft_category')
    for name in ('requires_type', 'tailwheel', 'compleks', 'high_performance'):
        if category and not equipment_applicable(category, name):
            result[name] = False
    if category == 'PL':
        result['requires_type'] = True
    # Retired from forms; preserve audited historical airplane metadata.
    result['simple'] = bool(getattr(instance, 'simple', False)) if category == 'A' else False
    if get('aircraft_category') != 'GL':
        result['self_launch_capable'] = False
    if result.pop('medium', False):
        result['small'] = True
    return result
