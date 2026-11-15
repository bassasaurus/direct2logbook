from flights.models import Aircraft, TailNumber


def owned_aircraft_and_tail(user, aircraft, tail):
    """Represent another pilot flying the same type/registration in their own account."""
    if aircraft.user_id == user.pk and tail.user_id == user.pk and tail.aircraft_id == aircraft.pk:
        return aircraft, tail
    aircraft, _ = Aircraft.objects.get_or_create(user=user, aircraft_type=aircraft.aircraft_type,
        defaults={'aircraft_category': aircraft.aircraft_category, 'aircraft_class': aircraft.aircraft_class})
    registration = tail.registration
    existing = TailNumber.objects.filter(user=user, registration=registration).first()
    if existing is not None and existing.aircraft_id != aircraft.pk:
        # A different type needs its own fixture tail, never a historical reassignment.
        registration = f'T{aircraft.pk}'
    tail, _ = TailNumber.objects.get_or_create(user=user, registration=registration,
        defaults={'aircraft': aircraft, 'is_91': tail.is_91, 'is_135': tail.is_135, 'is_121': tail.is_121})
    return aircraft, tail
