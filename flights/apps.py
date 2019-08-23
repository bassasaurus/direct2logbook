from django.apps import AppConfig

class FlightsConfig(AppConfig):
    name = 'flights'

    def ready(self):
        import flights.signal_stat
        import flights.signal_airplane_land
        import flights.signal_airplane_sea
        import flights.signal_rotorcraft
        import flights.signal_extra
        import flights.signal_total

        import flights.signal_route_data

        import flights.signal_error_flight
        import flights.signal_error_aircraft
        import flights.signal_error_tailnumber

        import accounts.signal_profile

        import payments.signal_create_and_subscribe
