import os.path
import django

os.environ["DJANGO_SETTINGS_MODULE"] = "logbook.settings"
django.setup()

from django.core.serializers import serialize
from flights.models import Flight, MapData


serialize('geojson', Flight.objects.all(),
          geometry_field='point',
          fields=('name',))
