from django.apps import AppConfig

class FlightsConfig(AppConfig):
    name = 'flights'

    def ready(self):
        import flights.signal_stat


        import flights.signal_total
        import flights.signal_import
        import flights.signal_error_flight
        import flights.signal_error_aircraft
        import flights.signal_error_tailnumber
        import flights.signal_route_data
        import flights.signal_extra

        import accounts.signal_profile
