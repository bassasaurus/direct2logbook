from flights.models import Aircraft, TailNumber


def seed_records(user):
    aircraft = Aircraft.objects.get_or_create(user=user, aircraft_type='C172', defaults={
        'aircraft_category': 'A', 'aircraft_class': 'SEL', 'piston': True, 'small': True})[0]
    tail = TailNumber.objects.get_or_create(user=user, registration='N12345', defaults={'aircraft': aircraft, 'is_91': True})[0]
    return aircraft, tail
