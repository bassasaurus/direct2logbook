import os.path
import django

os.environ["DJANGO_SETTINGS_MODULE"] = "logbook.settings"
django.setup()

from flights.models import Flight

for flight in Flight.objects.all():
    print(flight.route_data)