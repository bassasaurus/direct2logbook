from django.apps import AppConfig


class FlightsConfig(AppConfig):
    name = 'flights'

    def ready(self):

        import profile.signal_profile

        import flights.signal_stat
        import flights.signal_total
        import flights.signal_extra

        import flights.signal_error_flight

        import flights.signal_route_data
