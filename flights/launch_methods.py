"""Per-flight launch method; self-launch capability is aircraft metadata."""
LAUNCH_CHOICES = (('AEROTOW', 'Aerotow'), ('GROUND', 'Ground Launch'), ('SELF', 'Self-launch'))


def launch_choices(aircraft):
    return [choice for choice in LAUNCH_CHOICES if choice[0] != 'SELF' or getattr(aircraft, 'self_launch_capable', False)]


def validate_launch_method(values, instance=None):
    get = lambda key: values.get(key, getattr(instance, key, None))
    aircraft = get('aircraft_type')
    method = get('launch_method') or ''
    actual_glider = getattr(aircraft, 'aircraft_category', '') == 'GL' and not get('simulator')
    if not actual_glider:
        return {'launch_method': 'Glider flight required.'} if method else {}
    if method and method not in dict(LAUNCH_CHOICES):
        return {'launch_method': 'Choose a launch method.'}
    if method == 'SELF' and not aircraft.self_launch_capable:
        return {'launch_method': 'Aircraft is not self-launch capable.'}
    if not method:
        return {'launch_method': 'Choose a launch method.'}
    return {}
