from flights.models import MapData


def seed_airports():
    for icao, iata, name in [('KIAH', 'IAH', 'Houston'), ('KMCO', 'MCO', 'Orlando'), ('KCLL', 'CLL', 'College Station')]:
        MapData.objects.get_or_create(icao=icao, defaults={'iata': iata, 'name': name, 'country': 'United States'})
