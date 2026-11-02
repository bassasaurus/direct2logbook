from flights.airport_resolution import flight_resolution, map_values


def save_route_data(instance):
    instance.route_data = map_values(flight_resolution(instance))['route_data']
    instance.save()
