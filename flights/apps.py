from django.apps import AppConfig

class FlightsConfig(AppConfig):
    name = 'flights'

    def ready(self):
        import flights.signal_total
        import flights.signal_stat
        import flights.signal_airplane_land
        import flights.signal_airplane_sea
        import flights.signal_rotorcraft
        import flights.signal_extra
        
